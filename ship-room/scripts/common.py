"""Shared plumbing: HTTP, DB, time. Stdlib only.

KWAN: Zero third-party deps on purpose. Every `pip install` in a CI job is a
thing that can break at 8:29am on a day you cared about. urllib fetches JSON
fine and xml.etree parses RSS fine. If you find yourself wanting pandas here,
you are doing analysis in the wrong layer.
"""
from __future__ import annotations

import gzip
import io
import json
import os
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "signal.db")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# ---------------------------------------------------------------- time

ET_OFFSET_STD = -5
ET_OFFSET_DST = -4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(timezone.utc).isoformat(timespec="seconds")


def _us_dst(dt_utc: datetime) -> bool:
    """US DST: 2nd Sunday March -> 1st Sunday November. Approximate at 07:00Z."""
    y = dt_utc.year

    def nth_sunday(month: int, n: int) -> datetime:
        d = datetime(y, month, 1, 7, tzinfo=timezone.utc)
        d += timedelta(days=(6 - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)

    # Known limitation: the switch actually happens at 02:00 local (06:00Z /
    # 07:00Z). We test at 07:00Z, so on the two changeover Sundays there is a
    # one-hour window where this is off by an hour. Sunday, 2am, markets shut.
    # Documented rather than fixed - fixing it costs more than it's worth.
    return nth_sunday(3, 2) <= dt_utc < nth_sunday(11, 1)


def to_et(dt_utc: datetime | None = None) -> datetime:
    dt_utc = dt_utc or utcnow()
    off = ET_OFFSET_DST if _us_dst(dt_utc) else ET_OFFSET_STD
    return dt_utc.astimezone(timezone(timedelta(hours=off)))


def market_is_open(dt_utc: datetime | None = None) -> bool:
    """Regular US equity session, 9:30 <= t < 16:00 ET, Mon-Fri.

    MARA: Holidays are NOT handled here on purpose. A holiday shows up as a
    stale-quote failure downstream, which is loud and correct. Hardcoding a
    holiday calendar means silently trusting a list that goes out of date.

    FIXED: the close is exclusive. 16:00:00 is the bell, not a moment of trading.
    The old version returned True at exactly 16:00 - a one-minute window a day
    where a "market open" check was wrong. Small, but it is the kind of small
    that shows up as one weird row six months from now.
    """
    et = to_et(dt_utc)
    if et.weekday() >= 5:
        return False
    mins = et.hour * 60 + et.minute
    return 9 * 60 + 30 <= mins < 16 * 60


def market_session(dt_utc: datetime | None = None) -> str:
    """premarket | open | postclose | weekend

    FIXED: fetch_market.py used to gate on market_is_open(), which is False at
    8:30am - so --skip-if-closed silently killed the entire pre-market run, the
    one you actually act on. Sessions are now named, and each job says which
    sessions it accepts, instead of asking a yes/no question that has a
    misleading answer twice a day.
    """
    et = to_et(dt_utc)
    if et.weekday() >= 5:
        return "weekend"
    mins = et.hour * 60 + et.minute
    if mins < 9 * 60 + 30:
        return "premarket"
    if mins < 16 * 60:
        return "open"
    return "postclose"


# ---------------------------------------------------------------- http

class FetchError(RuntimeError):
    pass


def http_get(url: str, *, timeout: int = 20, headers: dict | None = None,
             retries: int = 3, backoff: float = 1.5) -> bytes:
    """GET with retries. Raises FetchError loudly rather than returning junk."""
    hdrs = {"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "gzip"}
    if headers:
        hdrs.update(headers)
    ctx = ssl.create_default_context()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                return raw
        except Exception as e:  # noqa: BLE001 - we re-raise as FetchError
            last = e
            if attempt < retries - 1:
                time.sleep(backoff ** (attempt + 1))
    raise FetchError(f"GET {url} failed after {retries} tries: {last}")


def http_json(url: str, **kw) -> dict:
    raw = http_get(url, **kw)
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError as e:
        raise FetchError(f"non-JSON response from {url}: {e}") from e


# ---------------------------------------------------------------- db

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc        TEXT NOT NULL,
    asset_class   TEXT NOT NULL,          -- equity | crypto
    symbol        TEXT NOT NULL,
    spot          REAL NOT NULL,
    prev_close    REAL,
    day_change_pct REAL,
    provider      TEXT NOT NULL,
    session       TEXT,                   -- premarket | open | postclose | 24h
    chain_json    TEXT,                   -- full ATM option chain slice, JSON
    raw_json      TEXT
);
CREATE INDEX IF NOT EXISTS ix_snap_sym_ts ON snapshots(symbol, ts_utc);

CREATE TABLE IF NOT EXISTS calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc        TEXT NOT NULL,
    snapshot_id   INTEGER NOT NULL REFERENCES snapshots(id),
    symbol        TEXT NOT NULL,
    direction     TEXT NOT NULL,          -- up | down | flat
    confidence    INTEGER NOT NULL,       -- 1..5
    horizon_days  INTEGER NOT NULL DEFAULT 1,
    rationale     TEXT NOT NULL,
    model         TEXT NOT NULL,
    ref_contract  TEXT,                   -- OCC symbol of the ATM contract
    ref_price     REAL,                   -- mid at call time
    ref_spread    REAL,                   -- ask-bid at call time
    scored        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_calls_scored ON calls(scored, ts_utc);

CREATE TABLE IF NOT EXISTS outcomes (
    call_id           INTEGER PRIMARY KEY REFERENCES calls(id),
    scored_ts_utc     TEXT NOT NULL,
    spot_then         REAL NOT NULL,
    spot_now          REAL NOT NULL,
    spot_change_pct   REAL NOT NULL,
    direction_correct INTEGER,            -- 1/0, NULL if unscoreable
    contract_then     REAL,
    contract_now      REAL,
    option_pnl_pct    REAL,               -- the number that actually matters
    note              TEXT
);

CREATE TABLE IF NOT EXISTS news (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_utc TEXT NOT NULL,
    source      TEXT NOT NULL,
    tier        TEXT NOT NULL,            -- primary | press
    lean        TEXT NOT NULL,            -- data | left | center | right | intl | crypto
    title       TEXT NOT NULL,
    url         TEXT NOT NULL UNIQUE,
    published   TEXT,
    summary     TEXT
);
CREATE INDEX IF NOT EXISTS ix_news_pub ON news(published DESC);

CREATE TABLE IF NOT EXISTS runs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc    TEXT NOT NULL,
    job       TEXT NOT NULL,
    status    TEXT NOT NULL,              -- ok | partial | fail
    detail    TEXT
);
"""


MIGRATIONS = [
    # (table, column, DDL) - applied only if the column is missing.
    ("news", "published_ts", "ALTER TABLE news ADD COLUMN published_ts INTEGER"),
]


def db(path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    for table, col, ddl in MIGRATIONS:
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            con.execute(ddl)
    con.commit()
    return con


def log_run(con: sqlite3.Connection, job: str, status: str, detail: str = "") -> None:
    con.execute("INSERT INTO runs (ts_utc, job, status, detail) VALUES (?,?,?,?)",
                (iso(), job, status, detail[:2000]))
    con.commit()


def die(msg: str, code: int = 1):
    """RIOS: fail loudly. A red X in Actions is information. A green check on
    bad data is a lie you will trade on."""
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(code)
