#!/usr/bin/env python3
"""Render the three pages from the DB. No build step, no framework, no deps.

    docs/index.html   signals  - what the model says right now
    docs/record.html  record   - the full log, and whether confidence means anything
    docs/news.html    news     - the read-only headline rail

DEV: v1 crammed all of this onto one page and you were right that it was wrong.
Three pages, three jobs. The signal page answers "what now"; the record page
answers "should I believe it"; the news page answers "what's going on". The nav
is on every page and the freshness banner is on every page, because staleness is
never irrelevant.

Rules that survived from v1 and are not up for negotiation:
1. Staleness is loud, and judged PER RAIL, not on the newest row anywhere.
2. The track record travels with the call. You never read the call alone.
3. Every headline wears its source and lean. No anonymous news.
4. up/down and hit/miss always carry a glyph AND a word - never colour alone.
"""
from __future__ import annotations

import html
import json
import os
import sys
from datetime import datetime, timezone

import analytics as A
from common import db, ROOT, to_et, utcnow

OUT_DIR = os.path.join(ROOT, "docs")
CONFIG = os.path.join(ROOT, "scripts", "config.json")

CSS = """
:root{color-scheme:dark;
 --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
 --grid:#2c2c2a; --rule:#383835; --ring:rgba(255,255,255,.10);
 --up:#3987e5; --down:#e66767; --flat:#898781;
 --good:#0ca30c; --warn:#fab219; --serious:#ec835a; --crit:#d03b3b;}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
 font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-text-size-adjust:100%}
.wrap{max-width:600px;margin:0 auto;padding:14px 14px 60px}
h1{font-size:15px;font-weight:600;letter-spacing:.02em;margin:0;color:var(--ink2)}
h2{font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;
 color:var(--muted);margin:26px 0 10px}
nav{display:flex;gap:6px;margin:12px 0 14px}
nav a{flex:1;text-align:center;padding:9px 4px;border-radius:10px;font-size:13px;
 font-weight:600;background:var(--surface);border:1px solid var(--ring);color:var(--ink2)}
nav a.on{background:#20304a;border-color:#3987e5;color:#fff}
nav a:hover{text-decoration:none;color:var(--ink)}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:14px;
 padding:14px;margin-bottom:10px}
.row{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.hero{font-size:46px;font-weight:600;line-height:1.05;margin:2px 0 0}
.sub{color:var(--ink2);font-size:13px}
.muted{color:var(--muted);font-size:12px}
.tiles{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:14px;padding:12px}
.tile .label{color:var(--muted);font-size:11px;letter-spacing:.06em;text-transform:uppercase}
.tile .value{font-size:26px;font-weight:600;margin-top:3px}
.meter{height:8px;border-radius:4px;overflow:hidden;margin-top:9px}
.meter>i{display:block;height:100%;border-radius:4px}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;
 padding:3px 8px;border-radius:999px;border:1px solid var(--ring);color:var(--ink2);
 letter-spacing:.03em;white-space:nowrap}
.dot{width:8px;height:8px;border-radius:50%;flex:none}
.banner{border-radius:14px;padding:11px 13px;margin-bottom:12px;font-size:13px;
 font-weight:600;display:flex;gap:9px;align-items:flex-start;border:1px solid var(--ring)}
.banner.ok{background:rgba(12,163,12,.12);color:#7ee27e}
.banner.warn{background:rgba(250,178,25,.13);color:#f7d488}
.banner.crit{background:rgba(208,59,59,.15);color:#f0a0a0}
table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
th{text-align:left;color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;
 letter-spacing:.06em;padding:6px 6px 6px 0;border-bottom:1px solid var(--rule)}
td{padding:9px 6px 9px 0;border-bottom:1px solid var(--grid);vertical-align:top}
a{color:var(--ink);text-decoration:none}
a:hover{text-decoration:underline}
.news ul{margin:0;padding:0}
.news li{list-style:none;padding:11px 0;border-bottom:1px solid var(--grid)}
.news .meta{margin-top:5px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.bars{display:flex;flex-direction:column;gap:10px;margin-top:4px}
.bar{display:grid;grid-template-columns:50px 1fr 118px;gap:9px;align-items:center;
 font-size:11.5px}
/* FIXED: .track and .fill were spans, which are inline - height and width were
   ignored and every calibration bar rendered as an empty grey stub. */
.bar .track{display:block;height:14px;border-radius:4px;
 background:rgba(255,255,255,.06);overflow:hidden}
.bar .fill{display:block;height:14px;border-radius:4px;min-width:3px}
footer{margin-top:34px;color:var(--muted);font-size:11px;line-height:1.6;
 border-top:1px solid var(--grid);padding-top:14px}
code{font-size:12px;background:rgba(255,255,255,.06);padding:1px 5px;border-radius:4px}
.mk{display:inline-flex;align-items:center;justify-content:center;width:19px;height:19px;
 border-radius:50%;background:#20304a;border:1px solid #3987e5;color:#8bbcf0;
 font-size:11px;font-weight:700;margin-right:7px;flex:none;font-variant-numeric:tabular-nums}
h2 .mk{margin-right:8px}
.note{color:var(--muted);font-size:12px;line-height:1.55;margin-top:10px;
 border-top:1px solid var(--grid);padding-top:9px}
.note b{color:var(--ink2);font-weight:600}
.kv{display:grid;grid-template-columns:1fr auto;gap:6px 10px;font-size:13px;margin-top:2px}
.kv .k{color:var(--muted)}
.kv .v{font-weight:600;font-variant-numeric:tabular-nums}
.big{font-size:30px;font-weight:600;line-height:1.1;font-variant-numeric:tabular-nums}
.range{position:relative;height:34px;margin:14px 0 4px}
.range .axis{position:absolute;top:16px;left:0;right:0;height:2px;background:var(--rule)}
.range .band{position:absolute;top:11px;height:12px;border-radius:3px;
 background:rgba(57,135,229,.28);border:1px solid rgba(57,135,229,.55)}
.range .now{position:absolute;top:6px;width:2px;height:22px;background:var(--ink)}
.range .lbl{position:absolute;top:-2px;font-size:10px;color:var(--muted)}
details{background:var(--surface);border:1px solid var(--ring);border-radius:14px;
 padding:11px 14px;margin-bottom:10px}
details summary{cursor:pointer;color:var(--ink2);font-size:13px;font-weight:600;
 list-style:none}
details summary::-webkit-details-marker{display:none}
details summary::after{content:" ▾";color:var(--muted)}
details[open] summary::after{content:" ▴"}
details ol{margin:10px 0 2px;padding-left:0;list-style:none}
details ol li{padding:7px 0;border-top:1px solid var(--grid);font-size:12.5px;
 color:var(--ink2);line-height:1.55}
"""

LEAN_COLOR = {"data": "#3987e5", "left": "#9085e9", "center": "#898781",
              "right": "#d95926", "intl": "#199e70", "crypto": "#c98500"}
DIR_STYLE = {"up": ("↑", "var(--up)"), "down": ("↓", "var(--down)"),
             "flat": ("→", "var(--flat)")}
PAGES = [("index.html", "Signals"), ("record.html", "Record"), ("news.html", "News")]

DISCLAIMER = """Personal paper-trading research log. Every call here is
unexecuted and hypothetical. Option P&amp;L is marked mid-to-mid and therefore
optimistic: real fills cross the spread and pay commission. Nothing on this page
is financial advice, and none of it is a reason to trade. Built for one user;
not published as a service to anyone."""


def e(s) -> str:
    """RIOS: every string sourced from a feed goes through here. No exceptions."""
    return html.escape(str(s if s is not None else ""), quote=True)


def load_config() -> dict:
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"equities": ["SPY"], "crypto": ["BTC-USD", "ETH-USD"],
                "primary_symbol": "SPY",
                "freshness_budget_minutes": {"equity": 1800, "crypto": 120}}


def age_minutes(ts: str) -> float:
    t = datetime.fromisoformat(ts)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (utcnow() - t).total_seconds() / 60


def human_age(m: float) -> str:
    return (f"{m:.0f}m ago" if m < 90 else
            f"{m / 60:.1f}h ago" if m < 60 * 48 else f"{m / 1440:.1f}d ago")


def human_span(m: float) -> str:
    if m < 90:
        return f"{m:.0f} min"
    if m < 60 * 48:
        return f"{m / 60:.1f} hours"
    return f"{m / 1440:.1f} days"


# ------------------------------------------------------------------ queries

def latest_per_symbol(con) -> dict:
    """FIXED - this is the bug that mattered.

    v1 did `SELECT * FROM snapshots ORDER BY id DESC LIMIT 60` and then picked
    the newest row per symbol out of that window. Crypto writes 96 rows a day
    (2 symbols x every 30 min); equities write 2. So after about fifteen hours
    the 60-row window contained nothing but crypto, SPY silently disappeared
    off the card, AND the staleness check could no longer see the equities rail
    at all - meaning the equities job could have been dead for a month behind a
    green "all fresh" banner. That is the precise failure the banner exists to
    prevent, and v1 shipped it.

    The fix is to ask the database for the newest row PER SYMBOL instead of
    hoping it falls inside an arbitrary window.
    """
    rows = con.execute("""
        SELECT s.* FROM snapshots s
        JOIN (SELECT symbol, MAX(id) AS mx FROM snapshots GROUP BY symbol) m
          ON s.id = m.mx
        ORDER BY s.asset_class, s.symbol""").fetchall()
    return {r["symbol"]: r for r in rows}


def history(con, symbol: str, n: int = 24) -> list[float]:
    return [r["spot"] for r in reversed(con.execute(
        "SELECT spot FROM snapshots WHERE symbol=? ORDER BY id DESC LIMIT ?",
        (symbol, n)).fetchall())]


def record_stats(con, symbol: str | None = None) -> dict:
    where = "WHERE o.direction_correct IS NOT NULL"
    args: tuple = ()
    if symbol:
        where += " AND c.symbol=?"
        args = (symbol,)
    r = con.execute(f"""SELECT COUNT(*) n, SUM(o.direction_correct) hits,
                               AVG(o.option_pnl_pct) pnl,
                               SUM(CASE WHEN o.option_pnl_pct>0 THEN 1 ELSE 0 END) win,
                               SUM(CASE WHEN o.option_pnl_pct IS NOT NULL THEN 1 ELSE 0 END) priced
                        FROM outcomes o JOIN calls c ON c.id=o.call_id {where}""",
                    args).fetchone()
    n = r["n"] or 0
    return {"n": n, "hits": r["hits"] or 0, "pnl": r["pnl"], "win": r["win"] or 0,
            "priced": r["priced"] or 0,
            "hit_pct": (r["hits"] / n * 100) if n else None}


def calibration(con) -> list[dict]:
    """Hit rate broken out BY the confidence the model claimed.

    MARA: This table is the answer to "the confidence should be higher". You
    cannot raise confidence as a setting. Confidence is a CLAIM, and this is
    the only thing that tells you whether the claim means anything. If the c4
    and c5 rows don't beat the c2 row, the number is decoration and should be
    ignored - by you, when you decide how much to care about a call.
    """
    rows = con.execute("""
        SELECT c.confidence conf, COUNT(*) n,
               SUM(o.direction_correct) hits,
               AVG(o.option_pnl_pct) pnl
        FROM outcomes o JOIN calls c ON c.id=o.call_id
        WHERE o.direction_correct IS NOT NULL
        GROUP BY c.confidence ORDER BY c.confidence""").fetchall()
    return [{"conf": r["conf"], "n": r["n"], "hits": r["hits"],
             "hit_pct": r["hits"] / r["n"] * 100, "pnl": r["pnl"]} for r in rows]


def calibration_verdict(cal: list[dict]) -> tuple[str, str, str]:
    """(verdict class, headline, explanation). Deliberately blunt."""
    total = sum(c["n"] for c in cal)
    if total < 20:
        return ("warn", "Not enough data to judge confidence",
                f"{total} scored calls. Confidence claims are unfalsifiable "
                f"below ~20 and unreliable below ~50. Until then, treat every "
                f"call as confidence 1 regardless of what it says.")

    lo = [c for c in cal if c["conf"] <= 2]
    hi = [c for c in cal if c["conf"] >= 4]
    if not lo or not hi:
        return ("warn", "Confidence range too narrow to test",
                "The model is only using part of the 1-5 scale, so there is "
                "nothing to compare. Low-confidence and high-confidence calls "
                "both need volume before the number means anything.")

    lo_pct = sum(c["hits"] for c in lo) / sum(c["n"] for c in lo) * 100
    hi_pct = sum(c["hits"] for c in hi) / sum(c["n"] for c in hi) * 100
    gap = hi_pct - lo_pct

    if gap >= 10:
        return ("ok", f"Confidence is informative (+{gap:.0f} pts)",
                f"High-confidence calls hit {hi_pct:.0f}% vs {lo_pct:.0f}% for "
                f"low-confidence. The number is carrying real signal - size "
                f"your attention by it.")
    if gap <= -5:
        return ("crit", f"Confidence is INVERTED ({gap:.0f} pts)",
                f"High-confidence calls hit {hi_pct:.0f}%, LOWER than the "
                f"{lo_pct:.0f}% on low-confidence ones. The model is most wrong "
                f"exactly when it is most sure. Do not act on high-confidence "
                f"calls until this flips.")
    return ("warn", f"Confidence is noise ({gap:+.0f} pts)",
            f"High-confidence calls hit {hi_pct:.0f}% vs {lo_pct:.0f}% for low. "
            f"That gap is inside the noise. The confidence number is currently "
            f"decoration - ignore it when deciding how much to care.")


def bias_stats(con) -> list[dict]:
    rows = con.execute("""
        SELECT c.direction dir, COUNT(*) n, SUM(o.direction_correct) hits,
               AVG(o.option_pnl_pct) pnl
        FROM outcomes o JOIN calls c ON c.id=o.call_id
        WHERE o.direction_correct IS NOT NULL
        GROUP BY c.direction""").fetchall()
    return [{"dir": r["dir"], "n": r["n"], "hits": r["hits"],
             "hit_pct": r["hits"] / r["n"] * 100, "pnl": r["pnl"]} for r in rows]


# ------------------------------------------------------------------ pieces

def sparkline(vals: list[float], w: int = 240, h: int = 44) -> str:
    if len(vals) < 2:
        return '<div class="muted">not enough history for a trend yet</div>'
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    pad = 5
    pts = [(pad + i * (w - 2 * pad) / (len(vals) - 1),
            h - pad - (v - lo) / rng * (h - 2 * pad)) for i, v in enumerate(vals)]
    d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
                 for i, (x, y) in enumerate(pts))
    ex, ey = pts[-1]
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" role="img" '
            f'aria-label="recent price trend, {len(vals)} points, low {lo:.2f} '
            f'high {hi:.2f}"><path d="{d}" fill="none" stroke="var(--up)" '
            f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" fill="var(--up)" '
            f'stroke="var(--surface)" stroke-width="2"/></svg>')


def freshness_banner(con, cfg: dict) -> str:
    latest = latest_per_symbol(con)
    tracked = [(s, "equity") for s in cfg["equities"]] + \
              [(s, "crypto") for s in cfg["crypto"]]
    budget = cfg["freshness_budget_minutes"]

    missing = [s for s, _ in tracked if s not in latest]
    if missing:
        return (f'<div class="banner crit"><span>✕</span><span>NO DATA for '
                f'{e(", ".join(missing))}. Tracked in config.json but never '
                f'snapshotted — that rail has never run, or is failing every '
                f'time. Run <code>python3 scripts/doctor.py</code>.</span></div>')
    if not latest:
        return ('<div class="banner crit"><span>✕</span><span>No data yet. '
                'Run a fetch job or wait for the first scheduled run.</span></div>')

    worst, worst_age, worst_ratio = None, 0.0, 0.0
    for sym, cls in tracked:
        row = latest[sym]
        a = age_minutes(row["ts_utc"])
        ratio = a / budget.get(cls, 120)
        if ratio > worst_ratio:
            worst, worst_age, worst_ratio = sym, a, ratio

    if worst_ratio <= 1:
        return (f'<div class="banner ok"><span>✓</span><span>All rails fresh — '
                f'oldest tracked symbol is {e(worst)} at '
                f'{human_span(worst_age)}.</span></div>')
    if worst_ratio <= 6:
        return (f'<div class="banner warn"><span>⚠</span><span>STALE — '
                f'{e(worst)} last updated {human_span(worst_age)} ago. A '
                f'scheduled run was probably dropped. Do not read these numbers '
                f'as live.</span></div>')
    return (f'<div class="banner crit"><span>✕</span><span>PIPELINE DOWN — '
            f'{e(worst)} last updated {human_span(worst_age)} ago. Run '
            f'<code>python3 scripts/doctor.py</code> to find which source '
            f'died.</span></div>')


def shell(page: str, title: str, body: str) -> str:
    nav = "".join(
        '<a href="{}"{}>{}</a>'.format(f, ' class="on"' if f == page else "", n)
        for f, n in PAGES)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><title>{e(title)}</title>
<style>{CSS}</style></head><body><div class="wrap">
<div class="row"><h1>SIGNAL LOG</h1>
<span class="muted">{e(to_et().strftime('%a %b %d, %H:%M ET'))}</span></div>
<nav>{nav}</nav>
{body}
<footer>{DISCLAIMER}<br><br>Generated
{e(utcnow().isoformat(timespec='seconds'))} · free public data sources, may
break without notice.</footer>
</div></body></html>"""


# ------------------------------------------------------------------ pages

MARKERS = "①②③④⑤⑥⑦⑧⑨"


def mk(n: int) -> str:
    return f'<span class="mk">{n}</span>'


def h2(n: int, text: str) -> str:
    return f'<h2>{mk(n)}{e(text)}</h2>'


def note(text: str) -> str:
    """DEV: every box on the page explains itself in place. If a number needs a
    paragraph elsewhere to be safe to read, it is not safe to put on the page."""
    return f'<div class="note">{text}</div>'


LEGEND = """
<details open><summary>How to read this page — start here</summary>
<ol>
<li><b>Nothing on this page is advice.</b> Every box is either a measurement or
a piece of context. The one box that looks like a recommendation is labelled a
<em>logged hypothesis</em>, because that is all it is: a falsifiable guess being
written down so it can be scored against reality tomorrow.</li>
<li><span class="mk">1</span><b>The call.</b> Direction, confidence, and the
reasoning. Read it last, not first.</li>
<li><span class="mk">2</span><b>Already priced in.</b> The move the options
market is charging for. A call that predicts a move smaller than this is
predicting nothing.</li>
<li><span class="mk">3</span><b>What it costs.</b> Breakeven and spread. The
underlying has to move this far before you are flat, never mind ahead.</li>
<li><span class="mk">4</span><b>Volatility context.</b> Whether options are
expensive or cheap versus how much this has actually been moving lately.</li>
<li><span class="mk">5</span><b>Agreement.</b> Whether the correlated
instruments are telling the same story. When they don't, at least one is noise.</li>
<li><span class="mk">6</span><b>Track record.</b> How often this has been right
so far, and what the options actually did. This is the box that decides how much
the others are worth.</li>
<li><span class="mk">7</span><b>Markets.</b> Current prices and freshness per
symbol.</li>
<li><span class="mk">8</span><b>Pipeline health.</b> Whether the machinery ran.</li>
</ol></details>"""


def expected_move_card(sl: dict, spot: float, symbol: str) -> str:
    em = A.expected_move(sl)
    if not em:
        return ('<div class="card muted">No option chain stored for this '
                'snapshot, so there is no expected move to show. Directional '
                'calls without it are much harder to interpret.</div>')

    lo, hi = em["lower"], em["upper"]
    span = (hi - lo) or 1
    pos = max(0.0, min(1.0, (spot - lo) / span)) * 100
    daily = (f'{em["daily_pct"]:.2f}% (±${em["daily_abs"]:.2f})'
             if em["daily_pct"] else "n/a")

    # MARA: the one-day move can never exceed the move to expiry unless the
    # expiry IS today or the chain we stored no longer matches the spot we
    # stored. Both are real conditions and both make this box misleading, so
    # say it out loud instead of rendering two numbers that quietly contradict.
    inconsistency = ""
    if em["daily_pct"] and em["daily_pct"] > em["move_pct"] * 1.02:
        inconsistency = (
            '<div class="banner warn" style="margin:12px 0 0"><span>⚠</span>'
            '<span>The one-day move is larger than the move to expiry, which is '
            'not possible for a future expiry. Either this chain expires today, '
            'or the stored chain no longer matches the stored spot. Treat this '
            'box as unreliable until the next snapshot.</span></div>')
    return f"""<div class="card">
      <div class="row"><span class="muted">{e(symbol)} · priced-in move to expiry</span>
        <span class="muted">ATM {em['strike']}</span></div>
      <div class="big" style="margin-top:4px">±{em['move_pct']:.2f}%</div>
      <div class="range">
        <div class="axis"></div>
        <div class="band" style="left:0;right:0"></div>
        <div class="now" style="left:{pos:.1f}%"></div>
        <div class="lbl" style="left:0">{lo:,.2f}</div>
        <div class="lbl" style="right:0">{hi:,.2f}</div>
      </div>
      <div class="kv">
        <span class="k">ATM straddle cost</span><span class="v">${em['straddle_cost']:.2f}</span>
        <span class="k">Implied vol (ATM)</span><span class="v">{em['iv'] * 100:.1f}%</span>
        <span class="k">One-day expected move</span><span class="v">{daily}</span>
      </div>
      {inconsistency}
      {note('<b>What this is:</b> the market is already charging for a move of '
            f'roughly ±{em["move_pct"]:.2f}% by expiry. That range is the '
            'default expectation, not a forecast. A directional call only means '
            'something if it is claiming a move <em>outside</em> this band — '
            'inside it, being "right" pays nothing, because you already paid '
            'for it.')}
    </div>"""


def cost_card(call, sl: dict, spot: float) -> str:
    ref = None
    if call["ref_contract"] and call["ref_price"]:
        ref = {"strike": None, "mid": call["ref_price"],
               "spread": call["ref_spread"], "symbol": call["ref_contract"]}
        found = A.atm_pair(sl)
        for c in (found[0], found[1]):
            if c and c.get("contractSymbol") == call["ref_contract"]:
                ref["strike"] = c["strike"]
        if ref["strike"] is None:
            for c in sl.get("calls", []) + sl.get("puts", []):
                if c.get("contractSymbol") == call["ref_contract"]:
                    ref["strike"] = c["strike"]

    if not ref or ref["strike"] is None:
        return ('<div class="card muted">No reference contract on this call '
                '(flat call, or no chain), so there is no cost to model.</div>')

    be = A.breakeven(ref, call["direction"], spot)
    rt = A.round_trip_cost(ref)
    em = A.expected_move(sl)

    verdict = ""
    if be and em:
        inside = abs(be["move_needed_pct"]) <= em["move_pct"]
        verdict = (
            '<div class="banner ok" style="margin:12px 0 0"><span>✓</span><span>'
            f'Breakeven move ({be["move_needed_pct"]:+.2f}%) is inside the '
            f'priced-in range (±{em["move_pct"]:.2f}%).</span></div>'
            if inside else
            '<div class="banner warn" style="margin:12px 0 0"><span>⚠</span><span>'
            f'Breakeven needs {be["move_needed_pct"]:+.2f}% but the market is '
            f'only pricing ±{em["move_pct"]:.2f}%. This contract needs a '
            f'bigger-than-expected move just to get to zero.</span></div>')

    rows = [f'<span class="k">Contract</span><span class="v">'
            f'<code>{e(ref["symbol"])}</code></span>',
            f'<span class="k">Premium (mid)</span><span class="v">${ref["mid"]:.2f}</span>']
    if be:
        rows.append(f'<span class="k">Breakeven at expiry</span>'
                    f'<span class="v">${be["price"]:,.2f}</span>')
        rows.append(f'<span class="k">Move needed to break even</span>'
                    f'<span class="v">{be["move_needed_pct"]:+.2f}%</span>')
    if rt is not None:
        rows.append(f'<span class="k">Spread as % of premium</span>'
                    f'<span class="v">{rt:.1f}%</span>')

    return f"""<div class="card">
      <div class="kv">{''.join(rows)}</div>
      {verdict}
      {note('<b>What this is:</b> the arithmetic the direction call does not '
            'contain. You buy near the ask and sell near the bid, so the spread '
            'comes out first — before the underlying does anything. Then the '
            'underlying has to travel to breakeven before you are level. '
            '"Direction was right" and "made money" are different sentences, '
            'and this box is the gap between them.')}
    </div>"""


def vol_card(con, symbol: str, sl: dict) -> str:
    iv = A.atm_iv(sl)
    rows = con.execute("""SELECT ts_utc, spot FROM snapshots WHERE symbol=?
                          ORDER BY id DESC LIMIT 120""", (symbol,)).fetchall()
    closes = A.daily_closes(list(reversed(rows)))
    rv = A.realized_vol(closes)
    regime = A.vol_regime(iv, rv)

    hist = []
    for r in con.execute("""SELECT chain_json FROM snapshots WHERE symbol=?
                            AND chain_json IS NOT NULL
                            ORDER BY id DESC LIMIT 120""", (symbol,)).fetchall():
        try:
            v = A.atm_iv(json.loads(r["chain_json"]))
            if v:
                hist.append(v)
        except (json.JSONDecodeError, TypeError):
            continue
    pct = A.iv_percentile(hist, iv)

    if not regime and not pct:
        return ('<div class="card muted">Not enough stored history yet to place '
                'volatility in context. This box fills in after a couple of '
                'weeks of snapshots.</div>')

    kv = []
    if iv:
        kv.append(f'<span class="k">Implied vol (ATM)</span>'
                  f'<span class="v">{iv * 100:.1f}%</span>')
    if rv:
        kv.append(f'<span class="k">Realized vol ({len(closes)}d)</span>'
                  f'<span class="v">{rv * 100:.1f}%</span>')
    if regime:
        kv.append(f'<span class="k">Implied ÷ realized</span>'
                  f'<span class="v">{regime["ratio"]:.2f}×</span>')
    if pct:
        cav = "" if pct["reliable"] else " (short history)"
        kv.append(f'<span class="k">IV percentile{cav}</span>'
                  f'<span class="v">{pct["pct"]:.0f}%</span>')

    banner = ""
    if regime:
        cls = {"ok": "ok", "warn": "warn", "neutral": "warn"}[regime["class"]]
        icon = "✓" if regime["class"] == "ok" else "⚠" if regime["class"] == "warn" else "•"
        banner = (f'<div class="banner {cls}" style="margin:0 0 12px"><span>{icon}'
                  f'</span><span>{e(regime["verdict"])}</span></div>')

    detail = regime["detail"] if regime else ""
    if pct and not pct["reliable"]:
        detail += (f' The percentile is over only {pct["n"]} stored readings, '
                   f'not the 52 weeks your broker shows — treat it as a hint '
                   f'until this passes 60.')

    return f'<div class="card">{banner}<div class="kv">{"".join(kv)}</div>' \
           f'{note("<b>What this is:</b> " + e(detail))}</div>'


def agreement_card(con, cfg: dict) -> str:
    eq = cfg.get("equities", [])
    if len(eq) < 2:
        return ""
    calls = con.execute("""
        SELECT c.symbol, c.direction, c.confidence, c.ts_utc FROM calls c
        JOIN (SELECT symbol, MAX(id) mx FROM calls GROUP BY symbol) m ON c.id=m.mx
        WHERE c.symbol IN ({})""".format(",".join("?" * len(eq))), eq).fetchall()
    ag = A.agreement(calls)
    if not ag:
        return ""
    chips = " ".join(
        f'<span class="chip">{DIR_STYLE.get(c["direction"], ("?", ""))[0]} '
        f'{e(c["symbol"])} {e(c["direction"])} c{c["confidence"]}</span>'
        for c in calls)
    icon = {"ok": "✓", "warn": "⚠", "crit": "✕"}[ag["class"]]
    return (f'<div class="banner {ag["class"]}"><span>{icon}</span>'
            f'<span>{e(ag["label"])}</span></div>'
            f'<div class="card">{chips}{note("<b>What this is:</b> " + e(ag["detail"]))}'
            f'</div>')


def scoring_mode_banner(con) -> str:
    """MARA: if no snapshot anywhere has an option chain, then every call we
    score is being scored on direction alone - the metric I have called a
    vanity metric in this codebase about six times. It is still worth logging,
    because direction accuracy near 50% is itself a finding. But the page must
    say out loud that the honest half of the scoring is switched off, or the
    record will read as more meaningful than it is."""
    n = con.execute("SELECT COUNT(*) n FROM snapshots "
                    "WHERE chain_json IS NOT NULL").fetchone()["n"]
    if n:
        return ""
    return ('<div class="banner warn"><span>⚠</span><span>DIRECTION-ONLY '
            'SCORING — no option chain data is available, so calls are graded '
            'on whether spot moved the right way and nothing else. That is the '
            'flattering half of the measurement: you can be right on direction '
            'and still lose money to theta and the spread. Treat every hit rate '
            'below as an upper bound.</span></div>')


def page_index(con, cfg: dict) -> str:
    st = record_stats(con)
    latest = latest_per_symbol(con)
    body = [freshness_banner(con, cfg), scoring_mode_banner(con), LEGEND]

    # latest call per symbol that has one
    calls = con.execute("""
        SELECT c.*, s.spot spot_then, s.chain_json FROM calls c
        JOIN snapshots s ON s.id=c.snapshot_id
        JOIN (SELECT symbol, MAX(id) mx FROM calls GROUP BY symbol) m ON c.id=m.mx
        ORDER BY c.id DESC""").fetchall()

    body.append(h2(1, "The call — a logged hypothesis, not a recommendation"))
    if calls:
        for call in calls[:3]:
            glyph, col = DIR_STYLE.get(call["direction"], ("?", "var(--flat)"))
            sym_st = record_stats(con, call["symbol"])
            ref = ""
            if call["ref_contract"]:
                sp = (f' · spread {call["ref_spread"]}'
                      if call["ref_spread"] is not None else "")
                ref = (f'<div class="muted" style="margin-top:8px">ref contract '
                       f'<code>{e(call["ref_contract"])}</code> @ mid '
                       f'{call["ref_price"]}{sp}</div>')
            rec_line = (f'{sym_st["hit_pct"]:.0f}% direction over {sym_st["n"]} '
                        f'scored {e(call["symbol"])} calls'
                        if sym_st["n"] else
                        f'no scored {e(call["symbol"])} calls yet — this call is '
                        f'unproven')
            if sym_st["pnl"] is not None:
                rec_line += f', avg option P&amp;L {sym_st["pnl"]:+.1f}%'
            body.append(f"""
            <div class="card">
              <div class="row"><span class="muted">{e(call['symbol'])} · latest call</span>
                <span class="muted">{e(call['ts_utc'][:16])}Z</span></div>
              <div class="hero" style="color:{col}">{glyph} {e(call['direction'].upper())}</div>
              <div class="sub" style="margin-top:6px">confidence
                {'●' * call['confidence']}{'○' * (5 - call['confidence'])}
                {call['confidence']}/5 · horizon {call['horizon_days']}d ·
                spot at call {call['spot_then']}</div>
              <div style="margin-top:10px;color:var(--ink2)">{e(call['rationale'])}</div>
              {ref}
              <div class="muted" style="margin-top:12px;border-top:1px solid var(--grid);
                   padding-top:10px">Record: {rec_line} —
                   <a href="record.html" style="color:var(--ink2)">see the full log →</a></div>
            </div>""")
    else:
        body.append('<div class="card"><div class="hero" style="font-size:24px;'
                    'color:var(--muted)">No call recorded</div><div class="sub">'
                    'Generate <code>PROMPT.md</code>, get a JSON call back, then '
                    'run <code>record_call.py</code>.</div></div>')

    # --- context boxes, built off the primary symbol's newest chain
    primary = cfg.get("primary_symbol", "SPY")
    psnap = latest.get(primary)
    psl = None
    if psnap and psnap["chain_json"]:
        try:
            psl = json.loads(psnap["chain_json"])
        except json.JSONDecodeError:
            psl = None

    body.append(h2(2, f"Already priced in — {primary}"))
    body.append(expected_move_card(psl, psnap["spot"], primary) if psl else
                '<div class="card muted">No option chain stored yet.</div>')

    body.append(h2(3, "What this trade costs before it can win"))
    pcall = next((c for c in calls if c["symbol"] == primary), None)
    if pcall and psl:
        body.append(cost_card(pcall, psl, psnap["spot"]))
    else:
        body.append('<div class="card muted">No open call with a reference '
                    'contract on the primary symbol yet.</div>')

    body.append(h2(4, "Volatility context"))
    body.append(vol_card(con, primary, psl) if psl else
                '<div class="card muted">Needs a stored option chain.</div>')

    ag = agreement_card(con, cfg)
    if ag:
        body.append(h2(5, "Do the calls agree with each other?"))
        body.append(ag)

    body.append(h2(6, "Track record — the box that grades the others"))

    # tiles
    if st["n"]:
        hp = st["hit_pct"]
        mcol, mtrack = (("#0ca30c", "rgba(12,163,12,.22)") if hp >= 55 else
                        ("#fab219", "rgba(250,178,25,.22)") if hp >= 45 else
                        ("#d03b3b", "rgba(208,59,59,.22)"))
        hit_tile = (f'<div class="value">{hp:.0f}%</div>'
                    f'<div class="meter" style="background:{mtrack}">'
                    f'<i style="width:{min(hp, 100):.0f}%;background:{mcol}"></i></div>'
                    f'<div class="muted" style="margin-top:6px">{st["hits"]}/{st["n"]}'
                    f' · coinflip is 50%</div>')
        if st["pnl"] is not None:
            pnl_tile = (f'<div class="value" style="color:'
                        f'{"var(--good)" if st["pnl"] > 0 else "var(--down)"}">'
                        f'{st["pnl"]:+.1f}%</div><div class="muted" '
                        f'style="margin-top:6px">{st["win"]}/{st["priced"]} '
                        f'profitable · mid-to-mid</div>')
        else:
            pnl_tile = ('<div class="value">—</div><div class="muted" '
                        'style="margin-top:6px">no priced contracts yet</div>')
    else:
        hit_tile = ('<div class="value">—</div><div class="muted" '
                    'style="margin-top:6px">nothing scored yet</div>')
        pnl_tile = ('<div class="value">—</div><div class="muted" '
                    'style="margin-top:6px">nothing scored yet</div>')

    body.append(f"""<div class="tiles">
      <div class="tile"><div class="label">Direction hit rate</div>{hit_tile}</div>
      <div class="tile"><div class="label">Avg option P&amp;L</div>{pnl_tile}</div>
    </div>""")

    streak = A.call_streak(con.execute(
        """SELECT direction_correct FROM outcomes ORDER BY call_id DESC
           LIMIT 40""").fetchall())
    if streak and streak["n"] >= 2:
        body.append(f'<div class="muted" style="margin-top:8px">Current run: '
                    f'{streak["n"]} {streak["kind"]}es in a row. '
                    f'A streak of 3-4 either way is completely normal noise at '
                    f'these sample sizes — it is not the model warming up or '
                    f'breaking down.</div>')

    # markets - now driven by the TRACKED list, so a missing symbol is visible
    body.append(h2(7, "Markets"))
    tracked = [(s, "equity") for s in cfg["equities"]] + \
              [(s, "crypto") for s in cfg["crypto"]]
    for sym, cls in tracked:
        s = latest.get(sym)
        if not s:
            body.append(f'<div class="card"><div class="row"><strong>{e(sym)}</strong>'
                        f'<span class="chip" style="color:#f0a0a0">✕ never fetched</span>'
                        f'</div><div class="muted" style="margin-top:6px">Tracked in '
                        f'config.json but absent from the database.</div></div>')
            continue
        ch = s["day_change_pct"]
        g, c = (("↑", "var(--up)") if (ch or 0) > 0 else
                ("↓", "var(--down)") if (ch or 0) < 0 else ("→", "var(--flat)"))
        a = age_minutes(s["ts_utc"])
        stale = a > cfg["freshness_budget_minutes"].get(cls, 120)
        body.append(f"""
        <div class="card">
          <div class="row"><strong>{e(sym)}</strong>
            <span class="muted" style="{'color:#f7d488' if stale else ''}">
              {'⚠ ' if stale else ''}{e(s['provider'])} · {human_age(a)}</span></div>
          <div class="row" style="margin-top:4px">
            <span style="font-size:24px;font-weight:600">{s['spot']:,.2f}</span>
            <span style="color:{c};font-weight:600">{g}
              {f"{ch:+.2f}%" if ch is not None else "n/a"}</span></div>
          {sparkline(history(con, sym))}
        </div>""")

    runs = con.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 8").fetchall()
    rh = "".join(
        f"<tr><td>{e(r['ts_utc'][5:16])}</td><td>{e(r['job'])}</td>"
        f"<td style=\"color:{'var(--good)' if r['status'] == 'ok' else 'var(--warn)' if r['status'] == 'partial' else 'var(--crit)'}\">"
        f"{e(r['status'])}</td></tr>" for r in runs)
    body.append(f"""{h2(8, 'Pipeline health')}
    <div class="card" style="padding:6px 14px 2px"><table>
    <thead><tr><th>when</th><th>job</th><th>status</th></tr></thead>
    <tbody>{rh or '<tr><td colspan=3 class="muted">no runs yet</td></tr>'}</tbody>
    </table></div>""")

    body.append("""<h2>Watching this on another device</h2>
    <div class="card"><div class="muted">This page is a plain URL on GitHub
    Pages. Open it in any browser — a second phone, a tablet, a desktop next to
    your broker app — and bookmark it or add it to your home screen. There is
    no login and nothing to install, because there is nothing here worth
    protecting: it is public market data and your own logged guesses.<br><br>
    It does <b>not</b> connect to a brokerage account, and it does not need to.
    Your broker shows you positions; this shows you whether the reasoning has
    been any good. Keep them side by side and let each do its job.</div></div>""")

    return shell("index.html", "Signals", "\n".join(body))


def page_record(con, cfg: dict) -> str:
    st = record_stats(con)
    cal = calibration(con)
    body = [freshness_banner(con, cfg), scoring_mode_banner(con)]

    vclass, vhead, vtext = calibration_verdict(cal)
    body.append(f'<div class="banner {vclass}"><span>'
                f'{"✓" if vclass == "ok" else "⚠" if vclass == "warn" else "✕"}'
                f'</span><span>{e(vhead)}</span></div>'
                f'<div class="card muted">{e(vtext)}</div>')

    body.append("<h2>Does confidence mean anything?</h2>")
    if cal:
        bars = []
        for c in cal:
            col = ("#0ca30c" if c["hit_pct"] >= 55 else
                   "#fab219" if c["hit_pct"] >= 45 else "#d03b3b")
            pnl = f"{c['pnl']:+.1f}%" if c["pnl"] is not None else "—"
            bars.append(
                f'<div class="bar"><span class="muted">conf {c["conf"]}</span>'
                f'<span class="track"><i class="fill" style="width:'
                f'{min(c["hit_pct"], 100):.0f}%;background:{col}"></i></span>'
                f'<span class="muted">{c["hit_pct"]:.0f}% · n={c["n"]} · {pnl}</span>'
                f'</div>')
        body.append(f'<div class="card"><div class="bars">{"".join(bars)}</div>'
                    f'<div class="muted" style="margin-top:12px">Bars are '
                    f'direction hit rate at each claimed confidence level; the '
                    f'right column adds sample size and average option P&amp;L. '
                    f'For confidence to be worth anything, these should climb '
                    f'left to right.</div></div>')
    else:
        body.append('<div class="card muted">Nothing scored yet. This is the '
                    'first thing to look at once calls start maturing.</div>')

    body.append("<h2>Directional bias</h2>")
    bias = bias_stats(con)
    if bias:
        brows = []
        for b in bias:
            bpnl = f"{b['pnl']:+.1f}%" if b["pnl"] is not None else "—"
            brows.append(
                f"<tr><td>{DIR_STYLE.get(b['dir'], ('?', ''))[0]} {e(b['dir'])}</td>"
                f"<td>{b['n']}</td><td>{b['hit_pct']:.0f}%</td>"
                f"<td>{bpnl}</td></tr>")
        rows = "".join(brows)
        body.append(f'<div class="card" style="padding:6px 14px 2px"><table>'
                    f'<thead><tr><th>call</th><th>n</th><th>hit rate</th>'
                    f'<th>avg option</th></tr></thead><tbody>{rows}</tbody>'
                    f'</table></div>'
                    f'<div class="muted">If almost every call is "up", the model '
                    f'has a bullish bias rather than a view, and a rising market '
                    f'will flatter it until it doesn\'t.</div>')
    else:
        body.append('<div class="card muted">No scored calls yet.</div>')

    body.append("<h2>Every scored call</h2>")
    outs = con.execute("""SELECT o.*, c.symbol, c.direction, c.confidence, c.ts_utc,
                                 c.rationale, c.ref_contract
                          FROM outcomes o JOIN calls c ON c.id=o.call_id
                          ORDER BY o.call_id DESC LIMIT 200""").fetchall()
    if outs:
        parts = []
        for o in outs:
            glyph = DIR_STYLE.get(o["direction"], ("?", ""))[0]
            hit = bool(o["direction_correct"])
            opnl = (f"{o['option_pnl_pct']:+.1f}%"
                    if o["option_pnl_pct"] is not None else "—")
            parts.append(
                f"<tr><td>{e(o['ts_utc'][:10])}</td><td>{e(o['symbol'])}</td>"
                f"<td>{glyph} {e(o['direction'])} "
                f"<span class=\"muted\">c{o['confidence']}</span></td>"
                f"<td>{o['spot_change_pct']:+.2f}%</td>"
                f"<td style=\"color:{'var(--good)' if hit else 'var(--crit)'}\">"
                f"{'✓ hit' if hit else '✗ miss'}</td><td>{opnl}</td></tr>")
        body.append(f'<div class="card" style="padding:6px 14px 2px"><table>'
                    f'<thead><tr><th>date</th><th>sym</th><th>call</th>'
                    f'<th>spot</th><th>result</th><th>option</th></tr></thead>'
                    f'<tbody>{"".join(parts)}</tbody></table></div>')
    else:
        body.append('<div class="card muted">Nothing scored yet. This table is '
                    'the only reason to trust — or stop trusting — anything on '
                    'the signals page.</div>')

    pending = con.execute("SELECT COUNT(*) n FROM calls WHERE scored=0").fetchone()["n"]
    body.append(f'<div class="muted" style="margin-top:10px">{pending} call(s) '
                f'recorded and not yet matured. {st["n"]} scored. '
                f'{st["n"] - st["priced"]} scored on spot only (no option price '
                f'available at scoring time).</div>')

    return shell("record.html", "Record", "\n".join(body))


def page_news(con, cfg: dict) -> str:
    body = [freshness_banner(con, cfg)]
    body.append('<div class="card muted">These headlines are shown to <em>you</em>, '
                'never fed to the model. Source and lean travel with every line. '
                'Primary sources — central banks, statistics agencies, regulators — '
                'publish numbers rather than narrative, so they lead. Where outlets '
                'disagree, that disagreement is the information.</div>')

    # FIXED: v1 sorted `CASE tier WHEN 'primary' THEN 0 ELSE 1 END, id DESC`,
    # which pinned EVERY primary item above every press item forever - a
    # three-week-old Fed release outranked breaking news. Now primary gets a
    # bounded recency boost (treated as 12h fresher) instead of absolute
    # priority, and sorting is on a parsed epoch rather than a raw date string
    # that could be RFC-822 or ISO depending on the feed.
    rows = con.execute("""
        SELECT *, COALESCE(published_ts, 0) +
                  (CASE tier WHEN 'primary' THEN 43200 ELSE 0 END) AS rank_ts
        FROM news ORDER BY rank_ts DESC, id DESC LIMIT 60""").fetchall()

    if not rows:
        body.append('<div class="card muted">No headlines pulled yet. Run '
                    '<code>python3 scripts/fetch_news.py</code>.</div>')
        return shell("news.html", "News", "\n".join(body))

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["lean"]] = counts.get(r["lean"], 0) + 1
    chips = "".join(
        f'<span class="chip"><span class="dot" style="background:'
        f'{LEAN_COLOR.get(k, "#898781")}"></span>{e(k)} {v}</span> '
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    body.append(f'<div class="card"><div class="muted" style="margin-bottom:8px">'
                f'Spread of the {len(rows)} headlines below</div>{chips}</div>')

    # One mixed feed, ranked. NOT grouped by tier - grouping was how v1
    # reintroduced the same bug visually: a "primary sources" block pinned to
    # the top still floats a three-week-old release above today's news. Primary
    # gets a bounded 12h boost and a badge; if it's old, it sinks like anything
    # else. Recency is on every line so you can see for yourself.
    def item(i) -> str:
        badge = ('<span class="chip" style="border-color:#3987e5;color:#8bbcf0">'
                 'PRIMARY</span>' if i["tier"] == "primary" else "")
        when = (human_age((utcnow().timestamp() - i["published_ts"]) / 60)
                if i["published_ts"] else "undated")
        return f"""
          <li><a href="{e(i['url'])}" rel="noopener noreferrer nofollow"
                 target="_blank">{e(i['title'])}</a>
            <div class="meta">{badge}
              <span class="chip"><span class="dot" style="background:{
                LEAN_COLOR.get(i['lean'], '#898781')}"></span>{e(i['source'])}</span>
              <span class="muted">{e(i['lean'])} · {e(when)}</span>
            </div></li>"""

    body.append("<h2>Latest — all sources, ranked by recency</h2>")
    body.append(f'<div class="news"><ul>{"".join(item(i) for i in rows)}</ul></div>')
    body.append('<div class="muted">Primary sources carry a badge and a small '
                'recency boost, not permanent top billing — an old release is '
                'still old. Every line shows its own age.</div>')

    return shell("news.html", "News", "\n".join(body))


# ------------------------------------------------------------------ main

def build_all(con) -> dict:
    cfg = load_config()
    return {"index.html": page_index(con, cfg),
            "record.html": page_record(con, cfg),
            "news.html": page_news(con, cfg)}


def build(con) -> str:
    """Back-compat single-page entry point (tests, quick checks)."""
    return build_all(con)["index.html"]


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    con = db()
    for name, content in build_all(con).items():
        with open(os.path.join(OUT_DIR, name), "w") as f:
            f.write(content)
        print(f"wrote docs/{name} ({len(content):,} bytes)")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
