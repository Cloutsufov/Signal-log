#!/usr/bin/env python3
"""One entry point for every scheduled and manual job.

KWAN: We shipped six workflow files and the upload lost the `.github` folder,
because it starts with a dot and browsers and file pickers hide those. Six
chances to go wrong. So: ONE workflow file, and all the branching lives here in
Python where I can test it, instead of in YAML where I can't.

The workflow passes what triggered it; this decides what to do.

  ACTION   set by a manual "Run workflow" - bootstrap | record | doctor | fetch
  SCHEDULE the cron string GitHub fired, when it was a scheduled run

Run locally to see what WOULD happen, without doing it:
  python3 scripts/run_job.py --dry-run --schedule "*/30 * * * *"
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from common import market_session, to_et

HERE = os.path.dirname(os.path.abspath(__file__))

# Which cron string means what. Equities fire four times because GitHub cron is
# UTC and never shifts for daylight saving, so both the EST and EDT slot are
# registered and the ET gate below picks the real one.
#
# BUG FOUND WHILE CONSOLIDATING: v1 registered the pre-market slots at 13:30 and
# 14:30 UTC. Eastern Daylight Time is UTC-4, so 13:30 UTC is 09:30 ET - the
# opening bell, not pre-market. For the ~8 months a year the US is on DST, the
# pre-market run would have fired an hour late and then been correctly rejected
# by the session gate, i.e. it would never have run at all. The one you act on.
# Correct: 08:30 ET = 12:30 UTC (EDT) / 13:30 UTC (EST).
#                     16:30 ET = 20:30 UTC (EDT) / 21:30 UTC (EST).
EQUITY_CRONS = {"30 12 * * 1-5", "30 13 * * 1-5", "30 20 * * 1-5", "30 21 * * 1-5"}

# ET wall-clock slots we actually want, in minutes past midnight.
EQUITY_SLOTS = (8 * 60 + 30, 16 * 60 + 30)
SLOT_TOLERANCE_MIN = 55  # < 60 so the EST and EDT crons can never both match
FREQUENT_CRON = "*/30 * * * *"
WEEKLY_CRON = "17 12 * * 1"

def _primary() -> str:
    try:
        with open(os.path.join(os.path.dirname(HERE), "scripts",
                               "config.json")) as f:
            return json.load(f).get("primary_symbol", "SPY")
    except Exception:  # noqa: BLE001
        return "SPY"


EQUITIES = "SPY,QQQ,IWM"
CRYPTO = "BTC-USD,ETH-USD"
PRIMARY = _primary()


def run(*args: str, optional: bool = False) -> bool:
    """Run a script. Returns True on success.

    `optional=True` means a failure is logged and tolerated - used for the rails
    that can be down without the whole run being worthless. The critical steps
    are not optional and will fail the job loudly.
    """
    cmd = [sys.executable, os.path.join(HERE, args[0]), *args[1:]]
    print(f"\n$ {' '.join(cmd[1:])}", flush=True)
    r = subprocess.run(cmd, cwd=os.path.dirname(HERE))
    if r.returncode != 0:
        print(f"  -> exit {r.returncode}" + ("  (tolerated)" if optional else ""),
              flush=True)
    return r.returncode == 0


def now_et_minutes(dt=None) -> int:
    et = to_et(dt)
    return et.hour * 60 + et.minute


def in_equity_slot(minutes: int) -> bool:
    return any(abs(minutes - s) <= SLOT_TOLERANCE_MIN for s in EQUITY_SLOTS)


def plan(action: str, schedule: str, et_minutes: int | None = None) -> list[tuple]:
    """Decide the step list. Pure function so it can be tested without running
    anything - see tests/test_parsers.py."""
    steps: list[tuple] = []

    if action == "bootstrap":
        steps += [("doctor.py", "--prune", "OPT"),
                  ("fetch_market.py", "--class", "equity", "--symbols", EQUITIES, "OPT"),
                  ("fetch_market.py", "--class", "crypto", "--symbols", CRYPTO, "OPT"),
                  ("fetch_news.py", "OPT"),
                  ("make_prompt.py", "--symbol", PRIMARY, "OPT"),
                  ("build_site.py",)]
    elif action == "doctor":
        steps += [("doctor.py", "--prune", "OPT"), ("build_site.py",)]
    elif action == "record":
        steps += [("__record__",), ("build_site.py",)]
    elif action == "fetch":
        steps += [("fetch_market.py", "--class", "equity", "--symbols", EQUITIES, "OPT"),
                  ("fetch_market.py", "--class", "crypto", "--symbols", CRYPTO, "OPT"),
                  ("fetch_news.py", "OPT"),
                  ("score.py", "OPT"),
                  ("make_prompt.py", "--symbol", PRIMARY, "OPT"),
                  ("build_site.py",)]

    elif schedule in EQUITY_CRONS:
        # Gate on the ET wall clock, not on the cron string. Each slot has an
        # EST and an EDT cron registered; exactly one of them lands inside the
        # tolerance window on any given day, so the run happens once, at the
        # right local time, in both halves of the year.
        mins = now_et_minutes() if et_minutes is None else et_minutes
        if in_equity_slot(mins):
            steps += [("fetch_market.py", "--class", "equity",
                       "--symbols", EQUITIES, "OPT"),
                      ("score.py", "OPT"),
                      ("make_prompt.py", "--symbol", PRIMARY, "OPT"),
                      ("build_site.py",)]
        # else: the other half of the DST pair. Nothing to do, not an error.
    elif schedule == FREQUENT_CRON:
        steps += [("fetch_market.py", "--class", "crypto", "--symbols", CRYPTO, "OPT"),
                  ("fetch_news.py", "OPT"),
                  ("score.py", "OPT"),
                  ("build_site.py",)]
    elif schedule == WEEKLY_CRON:
        steps += [("doctor.py", "--prune", "OPT"), ("build_site.py",)]
    else:
        # Unknown trigger: do the safe, useful thing rather than nothing.
        steps += [("build_site.py",)]

    return steps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", default=os.environ.get("ACTION", ""))
    ap.add_argument("--schedule", default=os.environ.get("SCHEDULE", ""))
    ap.add_argument("--symbol", default=os.environ.get("SYMBOL", "SPY"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    action = (a.action or "").strip().lower().replace(" ", "")
    action = {"runbootstrap": "bootstrap", "healthcheck": "doctor",
              "recordacall": "record", "fetchnow": "fetch"}.get(action, action)

    print(f"trigger: action={action or '(none)'} schedule={a.schedule or '(none)'}")
    print(f"ET now:  {to_et():%Y-%m-%d %H:%M} ({market_session()})")

    supplied = (os.environ.get("CALL_DIRECTION", "").strip()
                or os.environ.get("CALL_JSON", "").strip())
    if supplied and action != "record":
        # MARA: green-and-discarded is the worst outcome a form can produce.
        shown = action or "(none)"
        print(f"FATAL: a call was supplied but the action is '{shown}', not "
              f"'record'. Nothing was logged. Re-run with the action dropdown "
              f"set to 'record'.")
        return 1

    steps = plan(action, a.schedule)
    if not steps:
        print("nothing to do for this trigger - exiting clean")
        return 0

    print(f"plan:    {len(steps)} step(s)")
    for s in steps:
        print(f"  - {' '.join(x for x in s if x != 'OPT')}")
    if a.dry_run:
        return 0

    failures = []
    for s in steps:
        optional = s[-1] == "OPT"
        args = [x for x in s if x != "OPT"]

        if args[0] == "__record__":
            direction = os.environ.get("CALL_DIRECTION", "").strip().lower()
            call_json = os.environ.get("CALL_JSON", "").strip()
            if not direction and not call_json:
                print("FATAL: record requested but no call was supplied "
                      "(set the direction/confidence/rationale fields)")
                return 1
            # snapshot first so the reference contract locks in at a live price
            cls = "crypto" if a.symbol.endswith("-USD") else "equity"
            run("fetch_market.py", "--class", cls, "--symbols", a.symbol)
            base = [sys.executable, os.path.join(HERE, "record_call.py"),
                    "--symbol", a.symbol]
            if direction:
                cmd = base + [
                    "--direction", direction,
                    "--confidence", os.environ.get("CALL_CONFIDENCE", "3").strip(),
                    "--rationale", os.environ.get("CALL_RATIONALE", "").strip(),
                    "--invalidation", os.environ.get("CALL_INVALIDATION", "").strip()]
                print(f"\n$ record_call.py --symbol {a.symbol} "
                      f"--direction {direction} (fields)", flush=True)
            else:
                cmd = base + ["--json", call_json]
                print(f"\n$ record_call.py --symbol {a.symbol} --json <pasted>",
                      flush=True)
            if subprocess.run(cmd, cwd=os.path.dirname(HERE)).returncode != 0:
                print("FATAL: the call was not recorded")
                return 1
            continue

        if not run(*args, optional=optional) and not optional:
            failures.append(args[0])

    if failures:
        print(f"\nFAILED: {', '.join(failures)}")
        return 1
    print("\ndone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
