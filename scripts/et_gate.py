#!/usr/bin/env python3
"""DST gate for GitHub cron.

GitHub cron is UTC and never shifts for daylight saving. So equities.yml fires
FOUR times a day (both the EDT and the EST slot for each of pre-market and
post-close) and this script decides which of those firings is actually the one
you meant. It writes `run=true|false` to $GITHUB_OUTPUT.

  python3 scripts/et_gate.py --slots 08:30,16:30 --tolerance 75

Exit code is always 0 - "wrong slot" is not an error, and a red X should mean
something is actually broken.
"""
from __future__ import annotations

import argparse
import os
import sys

from common import to_et


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slots", required=True, help="HH:MM,HH:MM in ET")
    ap.add_argument("--tolerance", type=int, default=75,
                    help="minutes of slack; GitHub delays scheduled runs")
    a = ap.parse_args()

    et = to_et()
    now = et.hour * 60 + et.minute
    hit = None
    for s in a.slots.split(","):
        h, m = (int(x) for x in s.strip().split(":"))
        target = h * 60 + m
        if abs(now - target) <= a.tolerance:
            hit = s.strip()
            break

    run = hit is not None
    print(f"ET now {et:%Y-%m-%d %H:%M} (weekday {et.weekday()}) "
          f"slots={a.slots} tol={a.tolerance}m -> "
          f"{'RUN (' + hit + ')' if run else 'skip'}")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"run={'true' if run else 'false'}\n")
            f.write(f"slot={hit or ''}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
