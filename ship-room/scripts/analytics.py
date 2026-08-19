"""Derived numbers computed from data we already store. No new sources.

MARA: Everything in here comes out of the option chain and the spot history that
are already in the database. That is deliberate. Each function answers a question
that a directional call by itself cannot answer, and most of them answer it
uncomfortably - which is the point.

The single most useful one is expected_move(). A call that says "up" without
knowing what "up" is already priced in is not a view, it's a coin flip with
extra words.
"""
from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone

TRADING_DAYS = 252
STRADDLE_TO_MOVE = 0.85  # standard approximation for the 1-sigma move


# ---------------------------------------------------------------- chain math

def atm_pair(sl: dict) -> tuple[dict | None, dict | None]:
    """The call and put nearest the money in a stored chain slice."""
    spot = sl.get("spot_at_snapshot")
    if not spot:
        return None, None

    def nearest(rows):
        rows = [r for r in rows if r.get("strike") is not None and r.get("mid")]
        return min(rows, key=lambda r: abs(r["strike"] - spot)) if rows else None

    return nearest(sl.get("calls", [])), nearest(sl.get("puts", []))


def atm_iv(sl: dict) -> float | None:
    """Average of ATM call and put implied vol, as a decimal (0.118 = 11.8%)."""
    c, p = atm_pair(sl)
    ivs = [x["iv"] for x in (c, p) if x and x.get("iv")]
    return sum(ivs) / len(ivs) if ivs else None


def expected_move(sl: dict) -> dict | None:
    """What the options market has ALREADY priced in.

    Two estimates, because they disagree in useful ways:
      straddle  - (ATM call mid + ATM put mid) * 0.85, the move to expiry the
                  market is charging for right now
      daily     - spot * IV / sqrt(252), the one-day 1-sigma move

    RIOS: read this before you act on any directional call. If the model says
    "up" and the expected move is 0.6%, a 0.4% rally is not the model being
    right - it is the market doing exactly what it was already priced to do.
    You are not paid for moves inside the expected move.
    """
    spot = sl.get("spot_at_snapshot")
    c, p = atm_pair(sl)
    if not spot or not c or not p:
        return None

    straddle = (c["mid"] or 0) + (p["mid"] or 0)
    if straddle <= 0:
        return None
    move = straddle * STRADDLE_TO_MOVE
    iv = atm_iv(sl)
    daily = spot * iv / math.sqrt(TRADING_DAYS) if iv else None

    return {
        "straddle_cost": round(straddle, 2),
        "move_abs": round(move, 2),
        "move_pct": round(move / spot * 100, 2),
        "daily_abs": round(daily, 2) if daily else None,
        "daily_pct": round(daily / spot * 100, 2) if daily else None,
        "iv": iv,
        "upper": round(spot + move, 2),
        "lower": round(spot - move, 2),
        "strike": c["strike"],
    }


def breakeven(ref: dict, direction: str, spot: float) -> dict | None:
    """Where the underlying must be at expiry for a long option to be flat.

    Long call  -> strike + premium.  Long put -> strike - premium.
    This is the number people skip, and it is why "the direction was right" and
    "I made money" are different sentences.
    """
    if not ref or not ref.get("mid") or direction == "flat":
        return None
    strike, prem = ref["strike"], ref["mid"]
    be = strike + prem if direction == "up" else strike - prem
    need = (be - spot) / spot * 100
    return {"price": round(be, 2), "move_needed_pct": round(need, 2),
            "premium": prem, "strike": strike}


def round_trip_cost(ref: dict) -> float | None:
    """The spread as a percentage of the premium - what you lose on entry+exit
    before the underlying does anything at all."""
    if not ref or not ref.get("mid") or ref.get("spread") is None:
        return None
    if ref["mid"] <= 0:
        return None
    return round(ref["spread"] / ref["mid"] * 100, 1)


# ---------------------------------------------------------------- vol context

def daily_closes(rows: list) -> list[float]:
    """One spot per calendar day (the last one), oldest first.

    We snapshot twice a day for equities and 48x a day for crypto; mixing those
    sampling rates into a volatility calc would produce a number that means
    nothing. One observation per day, consistently.
    """
    by_day: dict[str, float] = {}
    for r in rows:
        by_day[r["ts_utc"][:10]] = r["spot"]
    return [by_day[k] for k in sorted(by_day)]


def realized_vol(closes: list[float]) -> float | None:
    """Annualised close-to-close volatility, as a decimal."""
    if len(closes) < 4:
        return None
    rets = [math.log(closes[i] / closes[i - 1])
            for i in range(1, len(closes)) if closes[i - 1] > 0]
    if len(rets) < 3:
        return None
    return statistics.stdev(rets) * math.sqrt(TRADING_DAYS)


def vol_regime(iv: float | None, rv: float | None) -> dict | None:
    """Implied vs realized. Positive premium = options priced above how much
    the thing has actually been moving."""
    if iv is None or rv is None or rv <= 0:
        return None
    ratio = iv / rv
    if ratio >= 1.25:
        verdict, cls = "Options are expensive vs recent movement", "warn"
        detail = ("The market is charging more for a move than this has actually "
                  "been moving. Buying premium here needs a bigger move than "
                  "usual just to break even.")
    elif ratio <= 0.85:
        verdict, cls = "Options are cheap vs recent movement", "ok"
        detail = ("Implied vol is below what this has actually been doing. "
                  "Historically the friendlier side for buying premium - which "
                  "is not the same as a reason to.")
    else:
        verdict, cls = "Options are priced in line with recent movement", "neutral"
        detail = ("Implied and realized vol agree. No edge either way from "
                  "volatility alone.")
    return {"iv": iv, "rv": rv, "ratio": round(ratio, 2), "verdict": verdict,
            "class": cls, "detail": detail}


def iv_percentile(history_ivs: list[float], current: float | None) -> dict | None:
    """Where today's IV sits in the range we have actually recorded.

    Honest caveat carried in the output: with only a few weeks of history this
    is a percentile of a very short window, not the 52-week IV rank a broker
    shows you. It gets meaningful around 60+ observations.
    """
    if current is None or len(history_ivs) < 5:
        return None
    below = sum(1 for x in history_ivs if x < current)
    pct = below / len(history_ivs) * 100
    return {"pct": round(pct, 0), "n": len(history_ivs),
            "reliable": len(history_ivs) >= 60,
            "lo": round(min(history_ivs) * 100, 1),
            "hi": round(max(history_ivs) * 100, 1)}


# ---------------------------------------------------------------- agreement

def agreement(calls: list) -> dict | None:
    """Do the equity calls point the same way?

    DEV: three tickers that all track the US market saying three different
    things is not three signals, it is one signal that is noise. Worth seeing
    at a glance.
    """
    dirs = [c["direction"] for c in calls]
    if len(dirs) < 2:
        return None
    counts = {d: dirs.count(d) for d in set(dirs)}
    top, n = max(counts.items(), key=lambda kv: kv[1])
    if n == len(dirs):
        return {"class": "ok", "label": f"All {len(dirs)} calls agree: {top}",
                "detail": "Consistent read across correlated instruments."}
    if n <= len(dirs) / 2 + 0.001:
        return {"class": "crit", "label": "Calls disagree with each other",
                "detail": ("These instruments track the same market. If the "
                           "calls point different ways, at least one is noise "
                           "and you cannot tell which.")}
    return {"class": "warn", "label": f"Mixed: {n}/{len(dirs)} say {top}",
            "detail": "Partial agreement. Treat the odd one out with suspicion."}


def call_streak(outcomes: list) -> dict | None:
    """Current run of hits or misses, most recent first."""
    if not outcomes:
        return None
    first = outcomes[0]["direction_correct"]
    n = 0
    for o in outcomes:
        if o["direction_correct"] != first:
            break
        n += 1
    return {"kind": "hit" if first else "miss", "n": n}
