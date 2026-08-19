#!/usr/bin/env python3
"""Probe every live source and report what actually works, right now.

KWAN: I could not run this against the real internet from where I built it -
the build sandbox blocks outbound traffic to Yahoo, Coinbase and every RSS host.
So rather than guess which feeds are alive and hand you a list that reads
confident and is wrong, I wrote the thing that finds out. Run:

    python3 scripts/doctor.py

It tells you, per source: alive/dead, latency, and a sample value. Delete the
dead feeds from sources.json. Expect 3-6 of them to be dead on day one; feeds
rot constantly and anyone who tells you otherwise hasn't checked recently.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from common import http_get, http_json, ROOT
import providers as P


def timed(label: str, fn) -> bool:
    t0 = time.time()
    try:
        val = fn()
        ms = int((time.time() - t0) * 1000)
        print(f"  OK    {label:<34} {ms:>5}ms  {val}")
        return True
    except Exception as e:  # noqa: BLE001
        ms = int((time.time() - t0) * 1000)
        code = getattr(e, "status", None)
        tag = f"HTTP {code}" if code else type(e).__name__
        print(f"  DEAD  {label:<34} {ms:>5}ms  {tag}: {str(e)[:110]}")
        return False


def prune_feeds(dead: list[str]) -> int:
    """Rewrite sources.json without the dead feeds.

    KWAN: Feeds rot constantly and the manual version of this ("delete any dead
    feeds from sources.json") was never going to happen from a phone. So the
    health check can do it. It only removes feeds that FAILED this run - a
    single network blip could take one out, which is why it prints exactly what
    it removed and you can always git-revert one commit.
    """
    if not dead:
        return 0
    path = os.path.join(ROOT, "scripts", "sources.json")
    with open(path) as f:
        cfg = json.load(f)
    before = len(cfg["feeds"])
    cfg["feeds"] = [f for f in cfg["feeds"] if f["source"] not in set(dead)]
    removed = before - len(cfg["feeds"])
    if removed:
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2)
            f.write("\n")
    return removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prune", action="store_true",
                    help="remove feeds that failed this run from sources.json")
    args = ap.parse_args()

    with open(os.path.join(ROOT, "scripts", "config.json")) as f:
        conf = json.load(f)
    equities = conf.get("equities", ["SPY"])
    cryptos = conf.get("crypto", ["BTC-USD", "ETH-USD"])

    print("=== quotes ===")
    ok = total = 0
    for sym in equities:
        total += 4
        ok += timed(f"yahoo q1 {sym}",
                    lambda s=sym: f"spot {P.yahoo_quote(s)['spot']}")
        ok += timed(f"yahoo q2 {sym}",
                    lambda s=sym: f"spot {P.yahoo_quote(s, 'query2')['spot']}")
        ok += timed(f"stooq light {sym}",
                    lambda s=sym: f"spot {P.stooq_light_quote(s)['spot']}")
        ok += timed(f"stooq daily {sym}",
                    lambda s=sym: f"close {P.stooq_quote(s)['spot']}")
    for sym in cryptos:
        total += 1
        ok += timed(f"coinbase {sym}",
                    lambda s=sym: f"spot {P.coinbase_quote(s)['spot']}")

    print("\n=== options ===")

    def chain(sym):
        c = P.yahoo_option_chain(sym)
        return (f"{len(c['calls'])} calls, {len(c['puts'])} puts, "
                f"{len(c['expirations'])} expiries")
    chains = [timed(f"yahoo option chain {s}", lambda x=s: chain(x))
              for s in equities]
    chain_ok = any(chains)

    print("\n=== news feeds ===")
    with open(os.path.join(ROOT, "scripts", "sources.json")) as f:
        cfg = json.load(f)

    from fetch_news import parse_feed
    alive, dead = [], []
    for feed in cfg["feeds"]:
        def probe(u=feed["url"]):
            items = parse_feed(http_get(u, retries=1, timeout=15))
            return f"{len(items)} items | {items[0]['title'][:44] if items else 'EMPTY'}"
        (alive if timed(f"{feed['source']} [{feed['lean']}]", probe)
         else dead).append(feed["source"])

    print(f"\n=== summary ===")
    print(f"  quotes:  {ok}/{total} provider+symbol combinations alive")
    print(f"  options: {sum(chains)}/{len(chains)} chains alive"
          f"{'' if chain_ok else ' - scoring degrades to spot-only'}")
    print(f"  news:    {len(alive)}/{len(alive) + len(dead)} feeds alive")
    if dead:
        if args.prune:
            n = prune_feeds(dead)
            print(f"  PRUNED {n} dead feed(s) from sources.json:\n    " +
                  "\n    ".join(dead))
            print("  (one bad run can remove a good feed - revert the commit "
                  "if a source you want disappears)")
        else:
            print(f"  dead feeds to remove from sources.json:\n    " +
                  "\n    ".join(dead))
            print("  re-run with --prune to remove them automatically")
    if not chain_ok:
        print("\n  NOTE: without a chain, calls still record and score on spot,")
        print("  but option P&L will be blank. That is a degraded mode, not a")
        print("  broken one. Check if Yahoo now requires a cookie+crumb.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
