#!/usr/bin/env python3
"""Snapshot spot + option chain into SQLite.

Usage:
  python3 scripts/fetch_market.py --class equity --symbols SPY --session premarket
  python3 scripts/fetch_market.py --class crypto --symbols BTC-USD,ETH-USD
"""
from __future__ import annotations

import argparse
import json
import sys

from common import db, die, iso, log_run, market_session, to_et
import providers as P


def snapshot(con, symbol: str, asset_class: str, session: str) -> tuple[bool, str]:
    try:
        q = P.get_quote(symbol, asset_class)
    except Exception as e:  # noqa: BLE001
        return False, f"{symbol}: quote failed: {e}"

    spot = q["spot"]
    prev = q.get("prev_close")
    change = round((spot - prev) / prev * 100, 3) if prev else None

    chain_json = None
    chain_note = ""
    if asset_class == "equity":
        try:
            ch = P.get_option_chain(symbol)
            sl = P.atm_slice(ch, spot)
            chain_json = json.dumps(sl, separators=(",", ":"))
            chain_note = f" chain=ok({len(sl['calls'])}c/{len(sl['puts'])}p)"
        except Exception as e:  # noqa: BLE001
            # Not fatal: the spot snapshot is still worth keeping. But say so.
            chain_note = f" chain=FAILED({type(e).__name__})"

    cur = con.execute(
        """INSERT INTO snapshots
           (ts_utc, asset_class, symbol, spot, prev_close, day_change_pct,
            provider, session, chain_json, raw_json)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (iso(), asset_class, symbol, spot, prev, change,
         q["provider"], session, chain_json, json.dumps(q, default=str)))
    con.commit()
    return True, (f"{symbol}: {spot} via {q['provider']} "
                  f"({change:+.2f}%)" if change is not None else
                  f"{symbol}: {spot} via {q['provider']}") + chain_note


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="cls", choices=["equity", "crypto"], required=True)
    ap.add_argument("--symbols", required=True, help="comma separated")
    ap.add_argument("--session", default="auto")
    ap.add_argument("--only-sessions", default="",
                    help="comma list of ET sessions to run in "
                         "(premarket,open,postclose). Empty = always run.")
    a = ap.parse_args()

    # FIXED: this used to be `--skip-if-closed`, gated on market_is_open().
    # market_is_open() is False at 8:30am, so that flag silently skipped the
    # pre-market snapshot - the one you actually act on before the bell. Named
    # sessions make the intent explicit instead of hiding it behind a boolean
    # that means something different than it reads.
    session = a.session if a.session != "auto" else (
        "24h" if a.cls == "crypto" else market_session())

    if a.only_sessions:
        allowed = {s.strip() for s in a.only_sessions.split(",") if s.strip()}
        if session not in allowed:
            print(f"session is '{session}' at {to_et():%Y-%m-%d %H:%M} ET; "
                  f"this job only runs in {sorted(allowed)} - nothing to do")
            return 0

    con = db()
    syms = [s.strip() for s in a.symbols.split(",") if s.strip()]
    oks, msgs = 0, []
    for s in syms:
        ok, msg = snapshot(con, s, a.cls, session)
        oks += ok
        msgs.append(msg)
        print(("  ok  " if ok else "  FAIL ") + msg)

    status = "ok" if oks == len(syms) else ("partial" if oks else "fail")
    log_run(con, f"fetch_market:{a.cls}", status, "; ".join(msgs))
    con.close()

    if oks == 0:
        die("every symbol failed - check scripts/doctor.py output")
    return 0


if __name__ == "__main__":
    sys.exit(main())
