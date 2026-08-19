#!/usr/bin/env python3
"""Record a call against the newest snapshot.

  python3 scripts/record_call.py --symbol SPY --json '{"direction":"up",...}'
  python3 scripts/record_call.py --symbol SPY   # then paste JSON on stdin

Locks in the ATM reference contract AT CALL TIME. That is the whole point:
you cannot go back later and pick a strike that made you look good.
"""
from __future__ import annotations

import argparse
import json
import sys

from common import db, iso
import providers as P

VALID_DIR = {"up", "down", "flat"}


def extract_json(text: str) -> dict:
    """Models like to wrap JSON in prose or fences. Dig it out."""
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in input")
    return json.loads(text[start:end + 1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="SPY")
    ap.add_argument("--json", dest="js")
    ap.add_argument("--model", default="manual")
    # KWAN: separate fields, because JSON-through-a-single-line-web-form is a
    # trap. The first real attempt pasted the pretty-printed version, GitHub's
    # input took the first line, and the whole call arrived as "{". No amount
    # of documentation fixes a form that can silently eat your input - so the
    # form no longer asks for JSON at all.
    ap.add_argument("--direction")
    ap.add_argument("--confidence", type=int)
    ap.add_argument("--rationale")
    ap.add_argument("--invalidation", default="")
    ap.add_argument("--horizon", type=int, default=1)
    a = ap.parse_args()

    if a.direction:
        call = {"direction": a.direction, "confidence": a.confidence,
                "rationale": a.rationale or "", "horizon_days": a.horizon}
        if a.invalidation:
            call["invalidation"] = a.invalidation
    else:
        raw = a.js if a.js else sys.stdin.read()
        try:
            call = extract_json(raw)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"could not parse call JSON: {e}", file=sys.stderr)
            if raw.strip() in ("{", "}", "{}"):
                print("  the input looks TRUNCATED - a single-line web form "
                      "will keep only the first line of pretty-printed JSON. "
                      "Use the separate direction/confidence/rationale fields "
                      "instead.", file=sys.stderr)
            return 1

    d = str(call.get("direction", "")).lower().strip()
    if d not in VALID_DIR:
        print(f"direction must be one of {VALID_DIR}, got {d!r}", file=sys.stderr)
        return 1
    try:
        conf = int(call.get("confidence", 0))
    except (TypeError, ValueError):
        conf = 0
    if not 1 <= conf <= 5:
        print(f"confidence must be 1-5, got {call.get('confidence')!r}",
              file=sys.stderr)
        return 1

    rationale = str(call.get("rationale", "")).strip()
    if not rationale:
        print("rationale is required - an unexplained call is unscoreable",
              file=sys.stderr)
        return 1
    if call.get("invalidation"):
        rationale += f"  [invalidation: {call['invalidation']}]"

    con = db()
    s = con.execute("SELECT * FROM snapshots WHERE symbol=? ORDER BY id DESC LIMIT 1",
                    (a.symbol,)).fetchone()
    if not s:
        print(f"no snapshot for {a.symbol}", file=sys.stderr)
        return 1

    ref = None
    if s["chain_json"] and d != "flat":
        ref = P.pick_ref_contract(json.loads(s["chain_json"]), d)

    cur = con.execute(
        """INSERT INTO calls (ts_utc, snapshot_id, symbol, direction, confidence,
                              horizon_days, rationale, model, ref_contract,
                              ref_price, ref_spread)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (iso(), s["id"], a.symbol, d, conf,
         int(call.get("horizon_days", 1)), rationale, a.model,
         ref["symbol"] if ref else None,
         ref["mid"] if ref else None,
         ref["spread"] if ref else None))
    con.commit()

    print(f"recorded call #{cur.lastrowid}: {a.symbol} {d} conf={conf} "
          f"spot={s['spot']}")
    if ref:
        sp = f", spread {ref['spread']}" if ref["spread"] is not None else ""
        print(f"  ref contract {ref['symbol']} @ mid {ref['mid']}{sp}")
    else:
        print("  no ref contract (flat call or no chain) - "
              "will score on spot only")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
