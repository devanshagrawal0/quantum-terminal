"""Unified store access layer.

The ONLY module that touches the database file. Collectors call these
helpers; nothing else opens a raw connection.

Why this exists: we had 14 separate SQLite files that could not be JOINed,
`watchdog_events` duplicated across 7 of them, 6 tables built and never
filled, and every script writing its own raw SQL. See data_layer/README.md.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "store.db"
SCHEMA = Path(__file__).resolve().parent / "schema.sql"



def user_agent() -> str:
    """User-Agent for public data APIs. Some (the SEC among them) ask callers to identify
    themselves: CONTACT_EMAIL from the environment, else from the repo's private .env."""
    import os
    mail = os.environ.get("CONTACT_EMAIL", "").strip()
    if not mail:
        try:
            env = Path(__file__).resolve().parents[2] / ".env"
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("CONTACT_EMAIL="):
                    mail = line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
    return "quant-research-bot" + (f" contact:{mail}" if mail else "")


def connect(path: Path | str = DB_PATH, read_only: bool = False) -> sqlite3.Connection:
    """Open the store. WAL mode so collectors can write while we read."""
    if read_only:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    else:
        conn = sqlite3.connect(str(path), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def init(path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Create the store from schema.sql. Idempotent."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()
    return conn


# ------------------------------------------------------------- dimensions
# Ids are resolved once and cached; nothing joins on ticker strings.

_asset_cache: dict[str, int] = {}
_venue_cache: dict[str, int] = {}


def asset_id(conn: sqlite3.Connection, symbol: str, **kw) -> int:
    """Canonical asset id. Creates on first sight."""
    sym = (symbol or "").upper().strip()
    if sym in _asset_cache:
        return _asset_cache[sym]
    now = int(time.time() * 1000)
    conn.execute(
        "INSERT INTO asset(symbol,name,kind,coingecko_id,first_seen_ms,last_seen_ms) "
        "VALUES(?,?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET last_seen_ms=excluded.last_seen_ms",
        (sym, kw.get("name"), kw.get("kind", "crypto"), kw.get("coingecko_id"), now, now),
    )
    rid = conn.execute("SELECT id FROM asset WHERE symbol=?", (sym,)).fetchone()[0]
    _asset_cache[sym] = rid
    return rid


def venue_id(conn: sqlite3.Connection, name: str, **kw) -> int:
    nm = (name or "").lower().strip()
    if nm in _venue_cache:
        return _venue_cache[nm]
    conn.execute(
        "INSERT INTO venue(name,kind,jurisdiction,credibility) VALUES(?,?,?,?) "
        "ON CONFLICT(name) DO NOTHING",
        (nm, kw.get("kind"), kw.get("jurisdiction"), kw.get("credibility", 0.5)),
    )
    rid = conn.execute("SELECT id FROM venue WHERE name=?", (nm,)).fetchone()[0]
    _venue_cache[nm] = rid
    return rid


# ---------------------------------------------------------------- registry

def record_source(conn, name, category, base_url=None, auth="none", free=True,
                  status="unverified", http_status=None, latency_ms=None,
                  rate_limit=None, notes=None, sample_json=None, verified_on=None):
    """Write an EARNED status for a source. Never assume 'verified'."""
    conn.execute(
        """INSERT INTO source(name,category,base_url,auth,free,status,verified_on,
                              http_status,latency_ms,rate_limit,notes,sample_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(name) DO UPDATE SET
             category=excluded.category, base_url=excluded.base_url,
             auth=excluded.auth, free=excluded.free, status=excluded.status,
             verified_on=excluded.verified_on, http_status=excluded.http_status,
             latency_ms=excluded.latency_ms, rate_limit=excluded.rate_limit,
             notes=excluded.notes, sample_json=excluded.sample_json""",
        (name, category, base_url, auth, 1 if free else 0, status, verified_on,
         http_status, latency_ms, rate_limit, notes, sample_json),
    )


def log_run(conn, source_name, ok, rows_new=0, took_ms=0, error=None):
    conn.execute(
        "INSERT INTO collector_run(ts_ms,source_name,ok,rows_new,took_ms,error) VALUES(?,?,?,?,?,?)",
        (int(time.time() * 1000), source_name, 1 if ok else 0, rows_new, took_ms, error),
    )


# --------------------------------------------------------------- bulk write

def insert_many(conn, table, cols, rows, replace=False):
    """Batch insert. Returns rows written."""
    if not rows:
        return 0
    verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
    sql = f"{verb} INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})"
    cur = conn.executemany(sql, rows)
    return cur.rowcount if cur.rowcount and cur.rowcount > 0 else len(rows)


# ------------------------------------------------------------------ reads

def counts(conn) -> dict[str, int]:
    """Row count per table — the health check."""
    out = {}
    for (t,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        try:
            out[t] = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except sqlite3.Error:
            out[t] = -1
    return out


def span(conn, table, ts_col="ts_ms"):
    """(min_ts, max_ts, days) for a time-series table."""
    r = conn.execute(f'SELECT MIN({ts_col}), MAX({ts_col}), COUNT(*) FROM "{table}"').fetchone()
    if not r or r[0] is None:
        return None
    days = (r[1] - r[0]) / 86_400_000
    return {"min_ms": r[0], "max_ms": r[1], "rows": r[2], "days": round(days, 2)}
