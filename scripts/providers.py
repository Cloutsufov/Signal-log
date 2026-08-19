"""Data providers, all free, no API key, no account.

KWAN: Every provider here is (a) free forever with no signup and (b) unofficial
or best-effort. That is the deal you get at $0/month. So each one has a fallback
and every fetch records WHICH provider answered. When Yahoo breaks - and it will
break - you will see the provider column flip to 'stooq' and you will know why
the numbers look different, instead of wondering.

Parsing is separated from fetching in every function so the parsers can be
tested offline against recorded fixtures. See tests/test_parsers.py.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from common import FetchError, http_get, http_json

# ---------------------------------------------------------------- quotes


def parse_yahoo_chart(payload: dict) -> dict:
    """Parse Yahoo v8 chart JSON -> {spot, prev_close, currency, ts}."""
    try:
        res = payload["chart"]["result"][0]
        meta = res["meta"]
    except (KeyError, IndexError, TypeError) as e:
        err = (payload or {}).get("chart", {}).get("error")
        raise FetchError(f"unexpected Yahoo chart shape (error={err}): {e}") from e

    spot = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    if spot is None:
        raise FetchError("Yahoo chart returned no regularMarketPrice")
    return {
        "spot": float(spot),
        "prev_close": float(prev) if prev is not None else None,
        "currency": meta.get("currency"),
        "exchange": meta.get("fullExchangeName"),
        "ts": meta.get("regularMarketTime"),
    }


def yahoo_quote(symbol: str, host: str = "query1") -> dict:
    url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range=5d&interval=1d")
    q = parse_yahoo_chart(http_json(url))
    q["provider"] = f"yahoo-{host}"
    return q


def parse_stooq_csv(text: str) -> dict:
    """Stooq daily CSV -> last close + prior close. Free, no key, very stable."""
    rows = list(csv.DictReader(io.StringIO(text.strip())))
    if len(rows) < 1:
        raise FetchError("stooq returned no rows")
    last = rows[-1]
    prev = rows[-2] if len(rows) > 1 else None
    return {
        "spot": float(last["Close"]),
        "prev_close": float(prev["Close"]) if prev else None,
        "currency": "USD",
        "exchange": "stooq-eod",
        "ts": last.get("Date"),
    }


def stooq_quote(symbol: str) -> dict:
    """NOTE: end-of-day only. This is a fallback for 'is the number roughly
    right', not for intraday. It is labelled as such in the provider column."""
    sym = symbol.lower()
    if not sym.endswith(".us") and "-" not in sym:
        sym += ".us"
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    q = parse_stooq_csv(http_get(url).decode("utf-8", "replace"))
    q["provider"] = "stooq"
    return q


def parse_stooq_light(text: str) -> dict:
    """Stooq's single-quote CSV: Symbol,Date,Time,Open,High,Low,Close,Volume.

    A different endpoint from the daily-history one, and it fails differently -
    when Stooq has no data it returns literal 'N/D' rather than an HTTP error,
    which would otherwise sail through as a float() crash.
    """
    rows = list(csv.DictReader(io.StringIO(text.strip())))
    if not rows:
        raise FetchError("stooq light returned no rows")
    r = rows[0]
    close = (r.get("Close") or "").strip()
    if not close or close.upper() in ("N/D", "N/A"):
        raise FetchError(f"stooq light has no data for this symbol (got {close!r})")
    op = (r.get("Open") or "").strip()
    return {"spot": float(close),
            "prev_close": float(op) if op and op.upper() not in ("N/D", "N/A") else None,
            "currency": "USD", "exchange": "stooq-light",
            "ts": f"{r.get('Date', '')} {r.get('Time', '')}".strip()}


def stooq_light_quote(symbol: str) -> dict:
    sym = symbol.lower()
    if not sym.endswith(".us") and "-" not in sym:
        sym += ".us"
    url = f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv"
    q = parse_stooq_light(http_get(url).decode("utf-8", "replace"))
    q["provider"] = "stooq-light"
    return q


def parse_coinbase_spot(payload: dict) -> dict:
    try:
        return {"spot": float(payload["data"]["amount"]),
                "prev_close": None, "currency": payload["data"]["currency"],
                "exchange": "coinbase", "ts": None}
    except (KeyError, TypeError, ValueError) as e:
        raise FetchError(f"unexpected Coinbase shape: {e}") from e


def coinbase_quote(pair: str) -> dict:
    """pair like BTC-USD. Official, documented, free, no key. Most reliable
    thing in this whole file."""
    url = f"https://api.coinbase.com/v2/prices/{pair}/spot"
    q = parse_coinbase_spot(http_json(url))
    q["provider"] = "coinbase"
    return q


def get_quote(symbol: str, asset_class: str) -> dict:
    """Try providers in order. Record which one answered. Raise only if all fail."""
    if asset_class == "crypto":
        chain = [("coinbase", lambda: coinbase_quote(symbol.replace("-USD", "") + "-USD")),
                 ("yahoo-q1", lambda: yahoo_quote(symbol)),
                 ("yahoo-q2", lambda: yahoo_quote(symbol, "query2"))]
    else:
        # Four providers, because the first real run from a GitHub runner
        # showed the equity rail failing where crypto and news both worked.
        # A datacenter IP is treated very differently from a home IP by these
        # free endpoints, so we try more than one host and more than one shape.
        chain = [("yahoo-q1", lambda: yahoo_quote(symbol)),
                 ("yahoo-q2", lambda: yahoo_quote(symbol, "query2")),
                 ("stooq-light", lambda: stooq_light_quote(symbol)),
                 ("stooq-daily", lambda: stooq_quote(symbol))]

    errors = []
    for name, fn in chain:
        try:
            return fn()
        except Exception as ex:  # noqa: BLE001
            code = getattr(ex, "status", None)
            errors.append(f"{name}: " + (f"HTTP {code}" if code else str(ex)[:120]))
    raise FetchError(f"all providers failed for {symbol}: " + " | ".join(errors))


# ---------------------------------------------------------------- options


def parse_yahoo_options(payload: dict) -> dict:
    """Yahoo v7 options JSON -> expirations + calls/puts for the returned expiry."""
    try:
        res = payload["optionChain"]["result"][0]
    except (KeyError, IndexError, TypeError) as e:
        err = (payload or {}).get("optionChain", {}).get("error")
        raise FetchError(f"unexpected Yahoo options shape (error={err}): {e}") from e

    quote = res.get("quote", {}) or {}
    opts = (res.get("options") or [{}])[0]
    return {
        "spot": quote.get("regularMarketPrice"),
        "expirations": res.get("expirationDates", []),
        "expiry": opts.get("expirationDate"),
        "calls": opts.get("calls", []),
        "puts": opts.get("puts", []),
    }


def yahoo_option_chain(symbol: str, expiry_epoch: int | None = None) -> dict:
    url = f"https://query2.finance.yahoo.com/v7/finance/options/{symbol}"
    if expiry_epoch:
        url += f"?date={expiry_epoch}"
    c = parse_yahoo_options(http_json(url))
    c["provider"] = "yahoo"
    return c


def _mid(o: dict) -> float | None:
    bid, ask = o.get("bid"), o.get("ask")
    if bid and ask and ask > 0:
        return round((bid + ask) / 2, 4)
    last = o.get("lastPrice")
    return float(last) if last else None


def atm_slice(chain: dict, spot: float, width: int = 4) -> dict:
    """MARA: Store a WINDOW around the money, not the whole chain. The whole
    chain is megabytes of strikes nobody will ever look at, committed to git
    forever. Four strikes each side of spot is enough to reprice any realistic
    ATM trade later, and that is the entire point of snapshotting."""
    def near(rows: list[dict]) -> list[dict]:
        rows = [r for r in rows if r.get("strike") is not None]
        rows.sort(key=lambda r: abs(r["strike"] - spot))
        keep = sorted(rows[: width * 2 + 1], key=lambda r: r["strike"])
        return [{
            "contractSymbol": r.get("contractSymbol"),
            "strike": r.get("strike"),
            "bid": r.get("bid"),
            "ask": r.get("ask"),
            "last": r.get("lastPrice"),
            "mid": _mid(r),
            "volume": r.get("volume"),
            "openInterest": r.get("openInterest"),
            "iv": r.get("impliedVolatility"),
            "itm": r.get("inTheMoney"),
        } for r in keep]

    return {"expiry": chain.get("expiry"), "spot_at_snapshot": spot,
            "calls": near(chain.get("calls", [])),
            "puts": near(chain.get("puts", []))}


def pick_ref_contract(sl: dict, direction: str) -> dict | None:
    """The contract we pretend to buy, so scoring is honest.

    RIOS: This is the number that keeps you sane. 'Direction was right' is how
    people convince themselves a losing system works. The ref contract carries
    the real bid/ask you would have crossed.
    """
    side = sl["calls"] if direction == "up" else sl["puts"]
    spot = sl["spot_at_snapshot"]
    priced = [c for c in side if c.get("mid")]
    if not priced:
        return None
    c = min(priced, key=lambda r: abs(r["strike"] - spot))
    spread = None
    if c.get("ask") and c.get("bid") is not None:
        spread = round(c["ask"] - c["bid"], 4)
    return {"symbol": c["contractSymbol"], "strike": c["strike"],
            "mid": c["mid"], "spread": spread, "iv": c.get("iv"),
            "expiry": sl.get("expiry")}


def find_contract(sl: dict, contract_symbol: str) -> dict | None:
    for c in sl.get("calls", []) + sl.get("puts", []):
        if c.get("contractSymbol") == contract_symbol:
            return c
    return None
