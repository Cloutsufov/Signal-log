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

FLAT_BAND_PCT = 0.25


def mature(call_ts: str, horizon_days: int) -> bool:
    t = datetime.fromisoformat(call_ts)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    # horizon in trading days; skip weekends when counting forward
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

    if call["direction"] == "flat":
        correct = 1 if abs(chg) < FLAT_BAND_PCT else 0
    elif call["direction"] == "up":
        correct = 1 if chg > 0 else 0
    else:
        correct = 1 if chg < 0 else 0

    contract_now, pnl, note = None, None, ""
    if call["ref_contract"] and call["ref_price"]:
        try:
            expiry = json.loads(snap["chain_json"]).get("expiry")
            ch = P.yahoo_option_chain(sym, expiry)
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
    pending = [c for c in con.execute(q + " ORDER BY id").fetchall()
               if a.all or mature(c["ts_utc"], c["horizon_days"])]

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
