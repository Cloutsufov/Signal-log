#!/usr/bin/env python3
"""Generate the daily prompt from the newest snapshot.

JUNE: This is the honest seam in the whole design, so read it once.

You asked for free. A model call inside GitHub Actions is NOT free - it needs a
paid API key. So the automated half is data + scoring, and the judgment half is
you pasting this file into a chat you already pay nothing extra for. Total cost
stays $0 and nothing about the scoring changes.

The prompt deliberately contains ONLY numbers. No headlines, no vibes, no
'analysts say'. If the model can't make a call from price, IV, and the chain,
it doesn't have a call - and a confident sentence built out of news it read is
exactly the failure mode we are trying to measure our way out of.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from common import db, ROOT, to_et

OUT = os.path.join(ROOT, "PROMPT.md")

TEMPLATE = """# Signal request - {symbol} - {when_et} ET

You are producing ONE directional call for a personal, paper-traded research
log. It will be scored against real option prices in {horizon} trading day(s).
You have no news, no sentiment, no outside context - only the numbers below.
That is intentional.

## Snapshot
- Symbol: {symbol} ({asset_class})
- Spot: {spot}
- Previous close: {prev_close}
- Day change: {change}
- Data provider: {provider}
- Session: {session}
- Snapshot time (UTC): {ts}

## Recent closes
{history}

## ATM option chain{chain_note}
{chain}

## Your track record on {symbol}
{record}

## Output - JSON only, nothing else
{{
  "direction": "up" | "down" | "flat",
  "confidence": 1-5,
  "horizon_days": {horizon},
  "rationale": "<=60 words, cite the specific numbers above that drove this",
  "invalidation": "the price level or condition that proves this call wrong"
}}

Rules:
- confidence 4 or 5 requires a concrete, stated reason from the data above.
- "flat" is a legitimate and often correct answer. Use it.
- If the chain is missing or the spread is wide, say so and lower confidence.
- Do not hedge into meaninglessness. The log needs a falsifiable call.
"""


def fmt_chain(sl: dict | None) -> tuple[str, str]:
    if not sl:
        return "", "  (no chain captured for this snapshot)"
    rows = ["| strike | call mid | call IV | put mid | put IV |",
            "|---|---|---|---|---|"]
    puts = {p["strike"]: p for p in sl.get("puts", [])}
    for c in sl.get("calls", []):
        p = puts.get(c["strike"], {})
        iv = f"{c['iv']:.1%}" if c.get("iv") else "-"
        piv = f"{p['iv']:.1%}" if p.get("iv") else "-"
        rows.append(f"| {c['strike']} | {c.get('mid') or '-'} | {iv} | "
                    f"{p.get('mid') or '-'} | {piv} |")
    return f" (expiry epoch {sl.get('expiry')})", "\n".join(rows)


def track_record(con, symbol: str) -> str:
    r = con.execute("""
        SELECT COUNT(*) n,
               SUM(direction_correct) hits,
               AVG(option_pnl_pct) avg_pnl
        FROM outcomes o JOIN calls c ON c.id = o.call_id
        WHERE c.symbol = ? AND o.direction_correct IS NOT NULL""",
                    (symbol,)).fetchone()
    if not r or not r["n"]:
        return ("No scored calls yet. Treat your own confidence with suspicion "
                "until this table has 30+ rows.")
    hit = r["hits"] / r["n"] * 100
    pnl = r["avg_pnl"]
    return (f"{r['n']} scored calls | direction correct {hit:.0f}% | "
            f"avg option P&L {pnl:+.1f}%" if pnl is not None else
            f"{r['n']} scored calls | direction correct {hit:.0f}%")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="SPY")
    ap.add_argument("--horizon", type=int, default=1)
    a = ap.parse_args()

    con = db()
    s = con.execute("SELECT * FROM snapshots WHERE symbol=? ORDER BY id DESC LIMIT 1",
                    (a.symbol,)).fetchone()
    if not s:
        print(f"no snapshot for {a.symbol} - run fetch_market.py first",
              file=sys.stderr)
        return 1

    hist = con.execute(
        """SELECT ts_utc, spot FROM snapshots WHERE symbol=?
           ORDER BY id DESC LIMIT 10""", (a.symbol,)).fetchall()
    history = "\n".join(f"- {h['ts_utc'][:16]}Z  {h['spot']}" for h in hist)

    sl = json.loads(s["chain_json"]) if s["chain_json"] else None
    note, chain = fmt_chain(sl)

    body = TEMPLATE.format(
        symbol=s["symbol"], asset_class=s["asset_class"], spot=s["spot"],
        prev_close=s["prev_close"] if s["prev_close"] is not None else "n/a",
        change=(f"{s['day_change_pct']:+.2f}%" if s["day_change_pct"] is not None
                else "n/a"),
        provider=s["provider"], session=s["session"], ts=s["ts_utc"],
        when_et=to_et().strftime("%Y-%m-%d %H:%M"), history=history,
        chain_note=note, chain=chain, record=track_record(con, a.symbol),
        horizon=a.horizon)

    with open(OUT, "w") as f:
        f.write(body)
    print(body)
    print(f"\n[written to {OUT} - snapshot id {s['id']}]", file=sys.stderr)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
