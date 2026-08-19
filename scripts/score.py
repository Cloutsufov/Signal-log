#!/usr/bin/env python3
"""Score matured calls against real option prices.

MARA - long version, and I'm earning it because this file is the only reason
the project is worth building:

Direction accuracy is a vanity metric. You can be right on direction 60% of the
time and still go broke on options, because theta eats you on the days you were
'right but slow' and the bid/ask eats you on every single trade. So we score
two numbers and we always show both:

  1. direction_correct - did spot move the way we said
  2. option_pnl_pct    - what the ATM contract we named at call time actually
                         did, marked at the CURRENT MID

We buy at mid and sell at mid, which is already generous - in reality you'd pay
closer to the ask and sell closer to the bid. So treat option_pnl_pct as the
OPTIMISTIC case. If the optimistic case is negative, the real one is worse.

A 'flat' call is scored on spot only, and counts as correct if the move was
under 0.25%. That threshold is arbitrary; it is written down here so it can't
be quietly moved later to make the record look better.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

from common import db, iso, log_run, utcnow
import providers as P

# BUG (found in review, before it could corrupt anything): the flat band was
# 0.25%, written when the primary symbol was SPY. SPY's daily sigma is ~0.8%,
# so 0.25% is about 0.31 sigma - a sensible "nothing happened" width.
#
# BTC's daily sigma is 2-3%. Applying a 0.25% band to it means "flat" is
# essentially never correct: a normal quiet BTC day blows through it. Every
# flat call would have been marked a miss, the model would look bad at exactly
# the calls where it was being honest, and it would learn to stop saying flat.
#
# So the band is expressed in SIGMA, not in percent, and derived from the
# symbol's own realized volatility. The constant below is fixed now, before any
# call has been scored, and is not to be moved afterwards - moving a threshold
# once results exist is how a record gets quietly flattered.
FLAT_BAND_SIGMA = 0.31          # origin: 0.25% / 0.80% daily sigma on SPY
FALLBACK_BAND = {"equity": 0.25, "crypto": 0.60}   # used when history is thin


def flat_band_pct(con, symbol: str, asset_class: str) -> tuple[float, str]:
    """Return (band_pct, how_it_was_derived). Always reported in the outcome
    note so any row can be audited later."""
    try:
        import analytics as A
        rows = con.execute(
            """SELECT ts_utc, spot FROM snapshots WHERE symbol=?
               ORDER BY id DESC LIMIT 200""", (symbol,)).fetchall()
        closes = A.daily_closes(list(reversed(rows)))
        rv = A.realized_vol(closes)
        if rv:
            daily_sigma = rv / (252 ** 0.5) * 100
            band = round(FLAT_BAND_SIGMA * daily_sigma, 3)
            if band > 0:
                return band, (f"{FLAT_BAND_SIGMA} sigma of {daily_sigma:.2f}% "
                              f"daily vol over {len(closes)}d")
    except Exception:  # noqa: BLE001
        pass
    fb = FALLBACK_BAND.get(asset_class, 0.25)
    return fb, f"fallback band for {asset_class} (not enough history)"


def mature(call_ts: str, horizon_days: int, asset_class: str = "equity") -> bool:
    """BUG: this skipped weekends unconditionally, which is right for equities
    and wrong for crypto. With BTC as the primary symbol, a Friday call would
    not have been graded until Tuesday - three days of price movement judged as
    one. Crypto trades every day, so its horizon counts calendar days."""
    t = datetime.fromisoformat(call_ts)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    if asset_class == "crypto":
        return utcnow() >= t + timedelta(days=horizon_days)
    d, added = t, 0
    while added < horizon_days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return utcnow() >= d


def score_one(con, call) -> str:
    sym = call["symbol"]
    snap = con.execute("SELECT * FROM snapshots WHERE id=?",
                       (call["snapshot_id"],)).fetchone()
    spot_then = snap["spot"]

    asset_class = snap["asset_class"]
    try:
        q = P.get_quote(sym, asset_class)
    except Exception as e:  # noqa: BLE001
        return f"call #{call['id']}: cannot score, quote failed: {e}"

    spot_now = q["spot"]
    chg = (spot_now - spot_then) / spot_then * 100
    band, band_why = flat_band_pct(con, sym, asset_class)

    if call["direction"] == "flat":
        correct = 1 if abs(chg) < band else 0
    elif call["direction"] == "up":
        correct = 1 if chg > 0 else 0
    else:
        correct = 1 if chg < 0 else 0

    contract_now, pnl, note = None, None, ""
    if call["ref_contract"] and call["ref_price"]:
        try:
            expiry = json.loads(snap["chain_json"]).get("expiry")
            ch = P.get_option_chain(sym, expiry)
            sl = P.atm_slice(ch, spot_now, width=12)
            found = P.find_contract(sl, call["ref_contract"])
            if found and found.get("mid"):
                contract_now = found["mid"]
                pnl = (contract_now - call["ref_price"]) / call["ref_price"] * 100
            else:
                note = "ref contract not found in chain (expired or off-window)"
        except Exception as e:  # noqa: BLE001
            note = f"chain refetch failed: {type(e).__name__}: {e}"
    else:
        note = "no ref contract"
    note = (note + " | " if note else "") + f"flat band {band:.3f}% ({band_why})"

    con.execute(
        """INSERT OR REPLACE INTO outcomes
           (call_id, scored_ts_utc, spot_then, spot_now, spot_change_pct,
            direction_correct, contract_then, contract_now, option_pnl_pct, note)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (call["id"], iso(), spot_then, spot_now, round(chg, 4), correct,
         call["ref_price"], contract_now,
         round(pnl, 3) if pnl is not None else None, note))
    con.execute("UPDATE calls SET scored=1 WHERE id=?", (call["id"],))
    con.commit()

    p = f" option {pnl:+.1f}%" if pnl is not None else f" ({note})"
    return (f"call #{call['id']} {sym} {call['direction']} c{call['confidence']}: "
            f"spot {chg:+.2f}% -> {'HIT' if correct else 'MISS'}{p}")


def summary(con) -> None:
    print("\n--- record ---")
    rows = con.execute("""
        SELECT c.symbol,
               COUNT(*) n,
               SUM(o.direction_correct) hits,
               AVG(o.option_pnl_pct) pnl,
               SUM(CASE WHEN o.option_pnl_pct > 0 THEN 1 ELSE 0 END) winners
        FROM outcomes o JOIN calls c ON c.id=o.call_id
        GROUP BY c.symbol""").fetchall()
    if not rows:
        print("  nothing scored yet")
        return
    for r in rows:
        pnl = f"{r['pnl']:+.1f}%" if r["pnl"] is not None else "n/a"
        print(f"  {r['symbol']:<8} {r['n']:>3} calls | "
              f"direction {r['hits'] / r['n'] * 100:>5.1f}% | "
              f"avg option P&L {pnl} | profitable {r['winners']}/{r['n']}")
    print("  reminder: option P&L is marked mid-to-mid. Reality is worse.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="rescore everything")
    a = ap.parse_args()

    con = db()
    q = "SELECT * FROM calls" if a.all else "SELECT * FROM calls WHERE scored=0"
    def cls_of(call) -> str:
        r = con.execute("SELECT asset_class FROM snapshots WHERE id=?",
                        (call["snapshot_id"],)).fetchone()
        return r["asset_class"] if r else "equity"

    pending = [c for c in con.execute(q + " ORDER BY id").fetchall()
               if a.all or mature(c["ts_utc"], c["horizon_days"], cls_of(c))]

    if not pending:
        print("no matured calls to score")
        log_run(con, "score", "ok", "nothing due")
        summary(con)
        return 0

    msgs = [score_one(con, c) for c in pending]
    for m in msgs:
        print("  " + m)
    log_run(con, "score", "ok", f"scored {len(msgs)}")
    summary(con)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
