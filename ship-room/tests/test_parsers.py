#!/usr/bin/env python3
"""Offline tests. No network. Run: python3 tests/test_parsers.py

MARA: These test the parsers and the scoring math against fixed inputs, because
those are the parts that can be wrong in a way you never notice. They do NOT
test that Yahoo is up - that is doctor.py's job and it needs the real internet.
Know which question each tool answers.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import common  # noqa: E402
import providers as P  # noqa: E402
import fetch_news  # noqa: E402
import build_site  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("  ok    " if cond else "  FAIL  ") + name + (f"  {detail}" if detail else ""))


def load(fn: str):
    with open(os.path.join(FIX, fn), "rb") as f:
        return f.read()


# ------------------------------------------------------------ quote parsers

def test_yahoo_chart():
    q = P.parse_yahoo_chart(json.loads(load("yahoo_chart.json")))
    check("yahoo chart: spot", q["spot"] == 552.31, str(q["spot"]))
    check("yahoo chart: prev close", q["prev_close"] == 549.02, str(q["prev_close"]))


def test_yahoo_chart_error():
    try:
        P.parse_yahoo_chart({"chart": {"result": None, "error": {"code": "Not Found"}}})
        check("yahoo chart: raises on error payload", False, "no exception")
    except common.FetchError as ex:
        check("yahoo chart: raises on error payload", "Not Found" in str(ex))


def test_stooq():
    q = P.parse_stooq_csv(load("stooq.csv").decode())
    check("stooq: last close", q["spot"] == 552.31, str(q["spot"]))
    check("stooq: prior close", q["prev_close"] == 549.02, str(q["prev_close"]))


def test_coinbase():
    q = P.parse_coinbase_spot(json.loads(load("coinbase.json")))
    check("coinbase: spot", q["spot"] == 64211.55, str(q["spot"]))


# ------------------------------------------------------------ option logic

def test_option_chain():
    ch = P.parse_yahoo_options(json.loads(load("yahoo_options.json")))
    check("options: calls parsed", len(ch["calls"]) == 9, str(len(ch["calls"])))

    sl = P.atm_slice(ch, spot=552.31, width=2)
    strikes = [c["strike"] for c in sl["calls"]]
    check("atm slice: window size", len(strikes) == 5, str(strikes))
    check("atm slice: centred on spot",
          min(strikes) == 550.0 and max(strikes) == 554.0, str(strikes))
    check("atm slice: sorted ascending", strikes == sorted(strikes))

    mids = [c["mid"] for c in sl["calls"] if c["strike"] == 552.0]
    check("atm slice: mid = (bid+ask)/2", mids and abs(mids[0] - 3.15) < 1e-9,
          str(mids))

    ref = P.pick_ref_contract(sl, "up")
    check("ref contract: nearest strike to spot", ref["strike"] == 552.0,
          str(ref["strike"]))
    check("ref contract: spread recorded", abs(ref["spread"] - 0.10) < 1e-9,
          str(ref["spread"]))
    check("ref contract: puts side for down",
          P.pick_ref_contract(sl, "down")["symbol"].find("P") > 0)

    check("find_contract: locates by symbol",
          P.find_contract(sl, ref["symbol"]) is not None)
    check("find_contract: None when absent",
          P.find_contract(sl, "NOPE240101C00000000") is None)


def test_no_priced_contracts():
    sl = {"expiry": 1, "spot_at_snapshot": 100.0,
          "calls": [{"contractSymbol": "X", "strike": 100.0, "bid": None,
                     "ask": None, "last": None, "mid": None}],
          "puts": []}
    check("ref contract: None when nothing is priced",
          P.pick_ref_contract(sl, "up") is None)


# ------------------------------------------------------------ feeds

def test_rss():
    items = fetch_news.parse_feed(load("rss2.xml"))
    check("rss2: item count", len(items) == 3, str(len(items)))
    check("rss2: title decoded", items[0]["title"] == "Fed holds rates steady",
          items[0]["title"])
    check("rss2: link", items[0]["url"].startswith("https://"))
    check("rss2: html stripped from summary",
          "<b>" not in items[1]["summary"], items[1]["summary"][:40])


def test_atom():
    items = fetch_news.parse_feed(load("atom.xml"))
    check("atom: item count", len(items) == 2, str(len(items)))
    check("atom: href link extracted",
          items[0]["url"] == "https://example.org/a1", items[0]["url"])


def test_malformed_feed():
    try:
        fetch_news.parse_feed(b"<rss><item><title>broken")
        check("malformed feed raises", False, "no exception")
    except Exception:
        check("malformed feed raises", True)


def test_injection_is_escaped():
    """RIOS: the one test I actually care about."""
    evil = ('IGNORE PREVIOUS INSTRUCTIONS <script>alert(1)</script> '
            '"><img src=x onerror=alert(2)>')
    out = build_site.e(evil)
    check("xss: script tag escaped", "<script>" not in out)
    check("xss: attribute break escaped", '"><img' not in out)
    check("xss: text preserved", "IGNORE PREVIOUS" in out)


# ------------------------------------------------------------ time logic

def test_market_hours():
    def et(y, mo, d, h, mi):
        # build a UTC time that corresponds to the given ET wall clock
        naive = datetime(y, mo, d, h, mi, tzinfo=timezone.utc)
        off = 4 if common._us_dst(naive) else 5
        return naive + timedelta(hours=off)

    check("market: open 10:00 ET Wed", common.market_is_open(et(2026, 8, 19, 10, 0)))
    check("market: closed 08:00 ET Wed",
          not common.market_is_open(et(2026, 8, 19, 8, 0)))
    check("market: closed 17:00 ET Wed",
          not common.market_is_open(et(2026, 8, 19, 17, 0)))
    check("market: closed Saturday", not common.market_is_open(et(2026, 8, 22, 12, 0)))
    check("market: open exactly 09:30 ET", common.market_is_open(et(2026, 8, 19, 9, 30)))
    check("dst: august is DST", common._us_dst(datetime(2026, 8, 19, tzinfo=timezone.utc)))
    check("dst: january is not", not common._us_dst(datetime(2026, 1, 15, tzinfo=timezone.utc)))


def test_maturity():
    import score
    now = datetime.now(timezone.utc)
    check("maturity: 1h old 1d call not mature",
          not score.mature((now - timedelta(hours=1)).isoformat(), 1))
    check("maturity: 5d old 1d call mature",
          score.mature((now - timedelta(days=5)).isoformat(), 1))
    check("maturity: weekend skipped",
          not score.mature((now - timedelta(hours=20)).isoformat(), 3))


# ------------------------------------------------------------ end to end

def test_end_to_end():
    """Full DB round trip: snapshot -> call -> outcome -> rendered HTML."""
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "t.db")
    con = common.db(path)

    ch = P.parse_yahoo_options(json.loads(load("yahoo_options.json")))
    sl = P.atm_slice(ch, 552.31)
    con.execute("""INSERT INTO snapshots (ts_utc, asset_class, symbol, spot,
                   prev_close, day_change_pct, provider, session, chain_json)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (common.iso(), "equity", "SPY", 552.31, 549.02, 0.599,
                 "fixture", "premarket", json.dumps(sl)))
    ref = P.pick_ref_contract(sl, "up")
    con.execute("""INSERT INTO calls (ts_utc, snapshot_id, symbol, direction,
                   confidence, horizon_days, rationale, model, ref_contract,
                   ref_price, ref_spread, scored)
                   VALUES (?,1,'SPY','up',3,1,'test','fixture',?,?,?,1)""",
                (common.iso(), ref["symbol"], ref["mid"], ref["spread"]))
    con.execute("""INSERT INTO outcomes (call_id, scored_ts_utc, spot_then,
                   spot_now, spot_change_pct, direction_correct, contract_then,
                   contract_now, option_pnl_pct, note)
                   VALUES (1,?,552.31,556.00,0.668,1,3.15,4.40,39.68,'')""",
                (common.iso(),))
    con.execute("""INSERT INTO news (fetched_utc, source, tier, lean, title, url,
                   published, summary) VALUES (?,'Federal Reserve','primary',
                   'data','<script>x</script> FOMC statement',
                   'https://example.org/fomc','','')""", (common.iso(),))
    con.execute("INSERT INTO runs (ts_utc, job, status, detail) VALUES (?,?,?,?)",
                (common.iso(), "test", "ok", "fixture run"))
    con.commit()

    html_out = build_site.build(con)
    check("e2e: html produced", len(html_out) > 3000, f"{len(html_out)} bytes")
    check("e2e: direction rendered", "UP" in html_out)
    check("e2e: option pnl rendered", "+39.7%" in html_out)
    check("e2e: hit rate rendered", "100%" in html_out)
    news_out = build_site.page_news(con, build_site.load_config())
    check("e2e: news title escaped on news page",
          "&lt;script&gt;" in news_out and "<script>x</script>" not in news_out)
    check("e2e: disclaimer present", "not financial advice" in html_out.lower()
          or "financial advice" in html_out.lower())
    check("e2e: single html document", html_out.count("<!doctype html>") == 1)
    con.close()


def test_empty_db_renders():
    tmp = tempfile.mkdtemp()
    con = common.db(os.path.join(tmp, "e.db"))
    out = build_site.build(con)
    check("empty db: still renders",
          ("No data yet" in out or "NO DATA" in out) and len(out) > 2000,
          str(len(out)))
    con.close()


def test_call_json_extraction():
    import record_call
    fenced = 'Sure!\n```json\n{"direction":"up","confidence":4,"rationale":"x"}\n```\nHope that helps'
    d = record_call.extract_json(fenced)
    check("call json: extracted from fenced prose", d["direction"] == "up", str(d))
    d2 = record_call.extract_json('{"direction":"down","confidence":2,"rationale":"y"}')
    check("call json: bare object", d2["confidence"] == 2)
    try:
        record_call.extract_json("no json here")
        check("call json: raises on garbage", False)
    except ValueError:
        check("call json: raises on garbage", True)


# ================================================================
# REGRESSION TESTS - one per bug found in the v1 audit.
# Each of these FAILED against the shipped v1 code. They exist so the same
# mistake cannot come back quietly.
# ================================================================

def test_regression_snapshot_window():
    """BUG A (critical): crypto volume pushed equities off the card entirely.

    v1 read `ORDER BY id DESC LIMIT 60` and picked latest-per-symbol from that
    window. Crypto writes 96 rows/day, equities 2 - so after ~15 hours SPY
    vanished from the page AND from the staleness check, meaning a dead
    equities job could hide behind a green 'all fresh' banner indefinitely.
    """
    import tempfile
    from datetime import datetime as dt
    tmp = tempfile.mkdtemp()
    con = common.db(os.path.join(tmp, "w.db"))
    now = dt.now(timezone.utc)

    for i in range(6):  # SPY: twice a day
        con.execute("""INSERT INTO snapshots (ts_utc,asset_class,symbol,spot,
            prev_close,day_change_pct,provider,session) VALUES (?,?,?,?,?,?,?,?)""",
                    (common.iso(now - timedelta(hours=8 * (6 - i))), "equity",
                     "SPY", 550 + i, 549, 0.2, "yahoo", "open"))
    for i in range(96):  # crypto: every 30 min, two symbols
        for sym in ("BTC-USD", "ETH-USD"):
            con.execute("""INSERT INTO snapshots (ts_utc,asset_class,symbol,spot,
                prev_close,day_change_pct,provider,session) VALUES (?,?,?,?,?,?,?,?)""",
                        (common.iso(now - timedelta(minutes=30 * (96 - i))),
                         "crypto", sym, 60000 + i, 60000, 0.1, "coinbase", "24h"))
    con.commit()

    latest = build_site.latest_per_symbol(con)
    check("regression A: SPY survives crypto volume", "SPY" in latest,
          str(sorted(latest)))
    check("regression A: all three symbols found", len(latest) == 3, str(len(latest)))

    out = build_site.page_index(con, build_site.load_config())
    check("regression A: SPY rendered on the card", "SPY" in out)

    # and the staleness check must now SEE the stale equities rail
    cfg = {"equities": ["SPY"], "crypto": ["BTC-USD", "ETH-USD"],
           "freshness_budget_minutes": {"equity": 60, "crypto": 120}}
    banner = build_site.freshness_banner(con, cfg)
    check("regression A: stale equities rail is reported",
          "STALE" in banner or "PIPELINE DOWN" in banner, banner[:70])
    con.close()


def test_regression_missing_symbol_visible():
    """A tracked symbol that never reported must show as MISSING, not vanish."""
    import tempfile
    con = common.db(os.path.join(tempfile.mkdtemp(), "m.db"))
    con.execute("""INSERT INTO snapshots (ts_utc,asset_class,symbol,spot,prev_close,
        day_change_pct,provider,session) VALUES (?,?,?,?,?,?,?,?)""",
                (common.iso(), "equity", "SPY", 550, 549, 0.2, "yahoo", "open"))
    con.commit()
    cfg = {"equities": ["SPY", "QQQ"], "crypto": [],
           "freshness_budget_minutes": {"equity": 1800, "crypto": 120}}
    banner = build_site.freshness_banner(con, cfg)
    check("regression: absent tracked symbol is flagged",
          "NO DATA" in banner and "QQQ" in banner, banner[:80])
    con.close()


def test_regression_news_ordering():
    """BUG B: v1 pinned every primary item above every press item, forever, so a
    three-week-old Fed release outranked breaking news."""
    import tempfile
    from datetime import datetime as dt
    con = common.db(os.path.join(tempfile.mkdtemp(), "n.db"))
    now = dt.now(timezone.utc)

    def ins(src, tier, title, age_h, url):
        pub = now - timedelta(hours=age_h)
        con.execute("""INSERT INTO news (fetched_utc,source,tier,lean,title,url,
            published,published_ts,summary) VALUES (?,?,?,'data',?,?,?,?,'')""",
                    (common.iso(now), src, tier, title, url,
                     common.iso(pub), int(pub.timestamp())))

    ins("Federal Reserve", "primary", "Three week old Fed release", 500, "u1")
    ins("CNBC", "press", "Breaking: market drops four percent", 0, "u2")
    con.commit()

    out = build_site.page_news(con, build_site.load_config())
    check("regression B: fresh press outranks stale primary",
          out.index("Breaking: market drops") < out.index("Three week old"))
    con.close()


def test_regression_news_date_parsing():
    """BUG B part 2: RFC-822 and ISO dates were sorted as raw text."""
    want = int(datetime(2026, 8, 18, 14, 0, tzinfo=timezone.utc).timestamp())
    check("regression B: RFC-822 parsed",
          fetch_news.parse_date("Tue, 18 Aug 2026 14:00:00 GMT") == want,
          str(fetch_news.parse_date("Tue, 18 Aug 2026 14:00:00 GMT")))
    check("regression B: ISO-8601 with Z parsed",
          fetch_news.parse_date("2026-08-18T14:00:00Z") == want)
    check("regression B: naive ISO assumed UTC",
          fetch_news.parse_date("2026-08-18T14:00:00") == want)
    check("regression B: offset-aware ISO respected",
          fetch_news.parse_date("2026-08-18T10:00:00-04:00") == want)
    check("regression B: garbage returns None",
          fetch_news.parse_date("last tuesday-ish") is None)
    check("regression B: empty returns None", fetch_news.parse_date("") is None)
    check("regression B: the two formats now compare equal",
          fetch_news.parse_date("Tue, 18 Aug 2026 14:00:00 GMT") ==
          fetch_news.parse_date("2026-08-18T14:00:00Z"))


def test_regression_market_close_boundary():
    """BUG F: 16:00:00 ET is the bell, not a moment of trading."""
    def at(h, m):
        naive = datetime(2026, 8, 19, h, m, tzinfo=timezone.utc)
        return naive + timedelta(hours=4 if common._us_dst(naive) else 5)
    check("regression F: 16:00 ET is closed", not common.market_is_open(at(16, 0)))
    check("regression F: 15:59 ET is open", common.market_is_open(at(15, 59)))


def test_regression_session_naming():
    """BUG D: --skip-if-closed used market_is_open(), which is False at 8:30am,
    so it silently killed the pre-market run - the one you act on."""
    def at(h, m, day=19):
        naive = datetime(2026, 8, day, h, m, tzinfo=timezone.utc)
        return naive + timedelta(hours=4 if common._us_dst(naive) else 5)
    check("regression D: 08:30 ET is 'premarket'",
          common.market_session(at(8, 30)) == "premarket",
          common.market_session(at(8, 30)))
    check("regression D: 10:00 ET is 'open'", common.market_session(at(10, 0)) == "open")
    check("regression D: 16:30 ET is 'postclose'",
          common.market_session(at(16, 30)) == "postclose")
    check("regression D: Saturday is 'weekend'",
          common.market_session(at(12, 0, day=22)) == "weekend")
    check("regression D: premarket is NOT 'market open'",
          not common.market_is_open(at(8, 30)))


def test_regression_migration_idempotent():
    """The published_ts migration must be safe to run repeatedly."""
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "mig.db")
    for _ in range(3):
        con = common.db(p)
        cols = {r[1] for r in con.execute("PRAGMA table_info(news)")}
        con.close()
    check("regression: migration adds published_ts", "published_ts" in cols)
    check("regression: migration is idempotent", True)


# ---------------------------------------------------------- calibration

def test_calibration():
    """The feature that answers 'confidence should be higher'."""
    import tempfile
    con = common.db(os.path.join(tempfile.mkdtemp(), "cal.db"))
    con.execute("""INSERT INTO snapshots (ts_utc,asset_class,symbol,spot,provider)
                   VALUES (?,'equity','SPY',550,'fixture')""", (common.iso(),))

    def add(conf, correct, pnl):
        cur = con.execute("""INSERT INTO calls (ts_utc,snapshot_id,symbol,direction,
            confidence,horizon_days,rationale,model,scored)
            VALUES (?,1,'SPY','up',?,1,'r','m',1)""", (common.iso(), conf))
        con.execute("""INSERT INTO outcomes (call_id,scored_ts_utc,spot_then,spot_now,
            spot_change_pct,direction_correct,option_pnl_pct)
            VALUES (?,?,550,551,0.18,?,?)""",
                    (cur.lastrowid, common.iso(), correct, pnl))

    # inverted: low confidence right a lot, high confidence wrong a lot
    for _ in range(12):
        add(2, 1, 5.0)
    for _ in range(3):
        add(2, 0, -5.0)
    for _ in range(3):
        add(5, 1, 2.0)
    for _ in range(12):
        add(5, 0, -9.0)
    con.commit()

    cal = build_site.calibration(con)
    check("calibration: groups by confidence", len(cal) == 2, str(len(cal)))
    c2 = next(c for c in cal if c["conf"] == 2)
    c5 = next(c for c in cal if c["conf"] == 5)
    check("calibration: c2 hit rate", abs(c2["hit_pct"] - 80.0) < 0.01,
          f"{c2['hit_pct']:.1f}")
    check("calibration: c5 hit rate", abs(c5["hit_pct"] - 20.0) < 0.01,
          f"{c5['hit_pct']:.1f}")

    cls, head, _ = build_site.calibration_verdict(cal)
    check("calibration: detects INVERTED confidence", cls == "crit", head)
    check("calibration: verdict says inverted", "INVERTED" in head, head)

    # too little data
    cls2, head2, _ = build_site.calibration_verdict(
        [{"conf": 3, "n": 4, "hits": 2, "hit_pct": 50.0, "pnl": 1.0}])
    check("calibration: refuses to judge on tiny samples", cls2 == "warn", head2)
    check("calibration: says so explicitly", "not enough data" in head2.lower())

    out = build_site.page_record(con, build_site.load_config())
    check("calibration: rendered on record page", "conf 5" in out and "INVERTED" in out)
    con.close()


def test_three_pages():
    import tempfile
    con = common.db(os.path.join(tempfile.mkdtemp(), "p.db"))
    pages = build_site.build_all(con)
    check("pages: three built", set(pages) == {"index.html", "record.html",
                                               "news.html"}, str(sorted(pages)))
    for name, content in pages.items():
        check(f"pages: {name} is a full document",
              content.count("<!doctype html>") == 1 and content.endswith("</html>"))
        check(f"pages: {name} has nav to all three",
              all(p in content for p, _ in build_site.PAGES))
        check(f"pages: {name} carries the disclaimer",
              "financial advice" in content.lower())
    con.close()



# ---------------------------------------------------------- analytics

def test_analytics_expected_move():
    import analytics as A
    ch = P.parse_yahoo_options(json.loads(load("yahoo_options.json")))
    sl = P.atm_slice(ch, 552.31)
    em = A.expected_move(sl)
    c, p = A.atm_pair(sl)
    check("analytics: ATM pair found", c is not None and p is not None)
    check("analytics: ATM strike nearest spot", c["strike"] == 552.0, str(c["strike"]))
    check("analytics: straddle = call mid + put mid",
          abs(em["straddle_cost"] - (c["mid"] + p["mid"])) < 1e-6,
          f"{em['straddle_cost']} vs {c['mid']}+{p['mid']}")
    check("analytics: move = straddle * 0.85",
          abs(em["move_abs"] - em["straddle_cost"] * 0.85) < 0.01)
    check("analytics: band brackets spot",
          em["lower"] < 552.31 < em["upper"], f"{em['lower']}-{em['upper']}")
    check("analytics: move_pct is sane", 0 < em["move_pct"] < 25,
          str(em["move_pct"]))
    check("analytics: daily move smaller than to-expiry move",
          em["daily_pct"] < em["move_pct"], f"{em['daily_pct']} vs {em['move_pct']}")
    check("analytics: None when no chain", A.expected_move({}) is None)


def test_expected_move_inconsistency_flagged():
    """A one-day move larger than the to-expiry move is impossible for a future
    expiry - it means the chain and the spot no longer match. Must be flagged."""
    import tempfile
    con = common.db(os.path.join(tempfile.mkdtemp(), "inc.db"))
    ch = P.parse_yahoo_options(json.loads(load("yahoo_options.json")))
    # chain built at 552 but spot has drifted far away -> strikes no longer ATM
    sl = P.atm_slice(ch, 552.31)
    drifted = 620.0
    sl["spot_at_snapshot"] = drifted
    con.execute("""INSERT INTO snapshots (ts_utc,asset_class,symbol,spot,prev_close,
        day_change_pct,provider,session,chain_json) VALUES (?,?,?,?,?,?,?,?,?)""",
                (common.iso(), "equity", "SPY", drifted, 619.0, 0.16, "fixture",
                 "premarket", json.dumps(sl)))
    con.commit()
    out = build_site.expected_move_card(sl, drifted, "SPY")
    check("analytics: mismatched chain/spot is flagged",
          "not possible for a future expiry" in out, out[:80])
    con.close()


def test_analytics_breakeven():
    import analytics as A
    ref = {"strike": 550.0, "mid": 3.00, "spread": 0.10}
    up = A.breakeven(ref, "up", spot=552.0)
    check("analytics: long call breakeven = strike + premium",
          up["price"] == 553.0, str(up["price"]))
    check("analytics: move needed positive when BE above spot",
          up["move_needed_pct"] > 0, str(up["move_needed_pct"]))
    dn = A.breakeven(ref, "down", spot=552.0)
    check("analytics: long put breakeven = strike - premium",
          dn["price"] == 547.0, str(dn["price"]))
    check("analytics: move needed negative for puts", dn["move_needed_pct"] < 0)
    check("analytics: flat call has no breakeven",
          A.breakeven(ref, "flat", 552.0) is None)
    check("analytics: round trip cost = spread/mid",
          A.round_trip_cost(ref) == round(0.10 / 3.00 * 100, 1),
          str(A.round_trip_cost(ref)))
    check("analytics: zero-premium contract returns None",
          A.round_trip_cost({"mid": 0, "spread": 0.1}) is None)


def test_analytics_vol():
    import analytics as A
    rows = [{"ts_utc": f"2026-08-{d:02d}T20:00:00+00:00", "spot": 100.0 + d}
            for d in range(1, 21)]
    closes = A.daily_closes(rows)
    check("analytics: one close per day", len(closes) == 20, str(len(closes)))
    check("analytics: closes are chronological", closes == sorted(closes))

    dupes = [{"ts_utc": "2026-08-01T13:30:00+00:00", "spot": 100.0},
             {"ts_utc": "2026-08-01T20:30:00+00:00", "spot": 101.0}]
    check("analytics: same-day snapshots collapse to one",
          A.daily_closes(dupes) == [101.0], str(A.daily_closes(dupes)))

    rv = A.realized_vol(closes)
    check("analytics: realized vol computed", rv is not None and rv > 0, str(rv))
    check("analytics: too few closes -> None", A.realized_vol([100.0, 101.0]) is None)

    check("analytics: expensive regime flagged",
          A.vol_regime(0.30, 0.15)["class"] == "warn")
    check("analytics: cheap regime flagged",
          A.vol_regime(0.10, 0.20)["class"] == "ok")
    check("analytics: in-line regime neutral",
          A.vol_regime(0.20, 0.20)["class"] == "neutral")
    check("analytics: zero realized vol -> None", A.vol_regime(0.2, 0) is None)

    pctl = A.iv_percentile([0.10, 0.12, 0.14, 0.16, 0.18], 0.15)
    check("analytics: iv percentile", pctl["pct"] == 60, str(pctl["pct"]))
    check("analytics: short history flagged unreliable", not pctl["reliable"])
    check("analytics: too little iv history -> None",
          A.iv_percentile([0.1], 0.15) is None)


def test_analytics_agreement_and_streak():
    import analytics as A
    same = [{"direction": "up"}, {"direction": "up"}, {"direction": "up"}]
    check("analytics: full agreement", A.agreement(same)["class"] == "ok")
    split = [{"direction": "up"}, {"direction": "down"}, {"direction": "flat"}]
    check("analytics: full disagreement flagged critical",
          A.agreement(split)["class"] == "crit", A.agreement(split)["label"])
    mixed = [{"direction": "up"}, {"direction": "up"}, {"direction": "down"}]
    check("analytics: partial agreement warns", A.agreement(mixed)["class"] == "warn")
    check("analytics: single call has no agreement",
          A.agreement([{"direction": "up"}]) is None)

    outs = [{"direction_correct": 0}, {"direction_correct": 0},
            {"direction_correct": 1}]
    stk = A.call_streak(outs)
    check("analytics: streak counts current run", stk["n"] == 2 and stk["kind"] == "miss",
          str(stk))
    check("analytics: empty outcomes -> None", A.call_streak([]) is None)


def test_annotated_page():
    """Every explainer marker must actually appear next to a section."""
    import tempfile
    con = common.db(os.path.join(tempfile.mkdtemp(), "ann.db"))
    ch = P.parse_yahoo_options(json.loads(load("yahoo_options.json")))
    sl = P.atm_slice(ch, 552.31)
    # eight days of history so the volatility box has something to work with
    base = datetime.now(timezone.utc)
    for d in range(8, 0, -1):
        spot = 552.31 - d * 0.9
        con.execute("""INSERT INTO snapshots (ts_utc,asset_class,symbol,spot,
            prev_close,day_change_pct,provider,session,chain_json)
            VALUES (?,?,?,?,?,?,?,?,?)""",
                    (common.iso(base - timedelta(days=d)), "equity", "SPY", spot,
                     spot - 0.4, 0.07, "fixture", "postclose",
                     json.dumps(P.atm_slice(ch, spot))))
    con.execute("""INSERT INTO snapshots (ts_utc,asset_class,symbol,spot,prev_close,
        day_change_pct,provider,session,chain_json) VALUES (?,?,?,?,?,?,?,?,?)""",
                (common.iso(), "equity", "SPY", 552.31, 549.02, 0.6, "fixture",
                 "premarket", json.dumps(sl)))
    ref = P.pick_ref_contract(sl, "up")
    con.execute("""INSERT INTO calls (ts_utc,snapshot_id,symbol,direction,confidence,
        horizon_days,rationale,model,ref_contract,ref_price,ref_spread,scored)
        VALUES (?,(SELECT MAX(id) FROM snapshots),'SPY','up',3,1,'test','m',?,?,?,0)""",
                (common.iso(), ref["symbol"], ref["mid"], ref["spread"]))
    con.commit()

    out = build_site.page_index(con, build_site.load_config())
    check("annotated: legend present", "How to read this page" in out)
    check("annotated: labelled a hypothesis, not advice",
          "logged hypothesis" in out.lower())
    check("annotated: expected move section", "Already priced in" in out)
    check("annotated: cost section", "break even" in out.lower())
    check("annotated: volatility section", "Volatility context" in out)
    check("annotated: track record section", "Track record" in out)
    check("annotated: other-device section", "another device" in out)
    check("annotated: all 8 markers rendered",
          all(f'class="mk">{i}<' in out for i in range(1, 9)),
          [i for i in range(1, 9) if f'class="mk">{i}<' not in out])
    check("annotated: every context box explains itself",
          out.count("What this is") >= 3, str(out.count("What this is")))
    check("annotated: volatility box populated with history",
          "Realized vol" in out and "Implied" in out)
    check("annotated: no broker credentials anywhere",
          "password" not in out.lower() and "api_key" not in out.lower())
    con.close()


def main() -> int:
    print("running offline parser + logic tests\n")
    for fn in [test_yahoo_chart, test_yahoo_chart_error, test_stooq, test_coinbase,
               test_option_chain, test_no_priced_contracts, test_rss, test_atom,
               test_malformed_feed, test_injection_is_escaped, test_market_hours,
               test_maturity, test_call_json_extraction, test_end_to_end,
               test_empty_db_renders,
               test_regression_snapshot_window, test_regression_missing_symbol_visible,
               test_regression_news_ordering, test_regression_news_date_parsing,
               test_regression_market_close_boundary, test_regression_session_naming,
               test_regression_migration_idempotent,
               test_calibration, test_three_pages,
               test_analytics_expected_move, test_expected_move_inconsistency_flagged,
               test_analytics_breakeven,
               test_analytics_vol, test_analytics_agreement_and_streak,
               test_annotated_page]:
        print(f"{fn.__name__}:")
        fn()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("failures:\n  " + "\n  ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
