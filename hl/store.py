"""SQLite recorder.

Hyperliquid only keeps the most recent 5000 candles and no history at all for
the order book, open interest or the tape. For 1-7 day trades the useful
signals (OI build, funding regime, depth drying up) only exist if we store them
ourselves, starting now. Everything is upsert-safe so a restart never
duplicates rows.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, Iterable, Optional, Sequence

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
  coin TEXT NOT NULL, interval TEXT NOT NULL,
  open_ms INTEGER NOT NULL, close_ms INTEGER,
  o REAL, h REAL, l REAL, c REAL, v REAL, n INTEGER,
  PRIMARY KEY (coin, interval, open_ms)
);
CREATE TABLE IF NOT EXISTS funding (
  coin TEXT NOT NULL, time INTEGER NOT NULL,
  funding_rate REAL, premium REAL,
  PRIMARY KEY (coin, time)
);
CREATE TABLE IF NOT EXISTS trades (
  tid INTEGER PRIMARY KEY, coin TEXT, time INTEGER,
  px REAL, sz REAL, side TEXT, hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_trades_coin_time ON trades(coin, time);
CREATE TABLE IF NOT EXISTS ctx_snapshots (
  ts_ms INTEGER NOT NULL, coin TEXT NOT NULL,
  mark_px REAL, oracle_px REAL, mid_px REAL,
  open_interest_base REAL, open_interest_usd REAL,
  funding_hourly REAL, premium REAL, day_notional_volume REAL,
  PRIMARY KEY (coin, ts_ms)
);
CREATE TABLE IF NOT EXISTS book_snapshots (
  ts_ms INTEGER NOT NULL, coin TEXT NOT NULL,
  best_bid REAL, best_ask REAL, mid REAL, microprice REAL, spread_bps REAL,
  depth_bid_usd REAL, depth_ask_usd REAL, imbalance REAL,
  buy_slippage_bps REAL, sell_slippage_bps REAL,
  PRIMARY KEY (coin, ts_ms)
);
CREATE TABLE IF NOT EXISTS gaps (
  ts_ms INTEGER NOT NULL, coin TEXT NOT NULL, venue TEXT NOT NULL,
  hl_bid REAL, hl_ask REAL, hl_mid REAL, hl_mark REAL, hl_oracle REAL,
  v_bid REAL, v_ask REAL, v_mid REAL,
  gap_bps REAL, hl_funding_hourly REAL, hl_spread_bps REAL, v_spread_bps REAL,
  suspect INTEGER DEFAULT 0,
  PRIMARY KEY (coin, venue, ts_ms)
);
CREATE INDEX IF NOT EXISTS idx_gaps_ts ON gaps(ts_ms);
CREATE INDEX IF NOT EXISTS idx_gaps_coin ON gaps(coin, ts_ms);
CREATE TABLE IF NOT EXISTS gap_runs (
  ts_ms INTEGER PRIMARY KEY, pairs INTEGER, venues TEXT,
  errors TEXT, took_ms INTEGER, gap_seconds REAL
);
CREATE TABLE IF NOT EXISTS feature_snapshots (
  ts_ms INTEGER NOT NULL, coin TEXT NOT NULL, payload TEXT NOT NULL,
  PRIMARY KEY (coin, ts_ms)
);
"""


class Store:
    def __init__(self, path: str = "data/hl.db"):
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        with self.conn:
            self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ---- writers -----------------------------------------------------------
    def save_candles(self, coin: str, interval: str,
                     candles: Sequence[Dict[str, Any]]) -> int:
        rows = [(coin, interval, int(c["t"]), int(c["T"]), float(c["o"]),
                 float(c["h"]), float(c["l"]), float(c["c"]), float(c["v"]),
                 int(c["n"])) for c in candles]
        if not rows:
            return 0
        with self._lock, self.conn:
            self.conn.executemany(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(coin, interval, open_ms) DO UPDATE SET "
                "close_ms=excluded.close_ms, o=excluded.o, h=excluded.h, l=excluded.l, "
                "c=excluded.c, v=excluded.v, n=excluded.n", rows)
        return len(rows)

    def save_funding(self, rows: Sequence[Dict[str, Any]]) -> int:
        recs = [(r["coin"], int(r["time"]), float(r["fundingRate"]),
                 float(r.get("premium", 0.0))) for r in rows]
        if not recs:
            return 0
        with self._lock, self.conn:
            self.conn.executemany(
                "INSERT OR REPLACE INTO funding VALUES (?,?,?,?)", recs)
        return len(recs)

    def save_trades(self, rows: Sequence[Dict[str, Any]]) -> int:
        recs = [(int(r["tid"]), r["coin"], int(r["time"]), float(r["px"]),
                 float(r["sz"]), r.get("side"), r.get("hash")) for r in rows]
        if not recs:
            return 0
        with self._lock, self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO trades VALUES (?,?,?,?,?,?,?)", recs)
        return len(recs)

    def save_ctx(self, ts_ms: int, coin: str, feat: Dict[str, Any]) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO ctx_snapshots VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ts_ms, coin, feat.get("mark_px"), feat.get("oracle_px"),
                 feat.get("mid_px"), feat.get("open_interest_base"),
                 feat.get("open_interest_usd"), feat.get("funding_hourly"),
                 feat.get("premium"), feat.get("day_notional_volume")))

    def save_book(self, ts_ms: int, coin: str, summary: Dict[str, Any],
                  depth_bps: int = 10) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO book_snapshots "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (ts_ms, coin, summary.get("best_bid"), summary.get("best_ask"),
                 summary.get("mid"), summary.get("microprice"),
                 summary.get("spread_bps"),
                 summary.get(f"depth_bid_usd_{depth_bps}bps"),
                 summary.get(f"depth_ask_usd_{depth_bps}bps"),
                 summary.get(f"imbalance_{depth_bps}bps"),
                 summary.get("buy_slippage_bps"), summary.get("sell_slippage_bps")))

    def save_features(self, ts_ms: int, coin: str, row: Dict[str, Any]) -> None:
        payload = {k: v for k, v in row.items()
                   if not k.startswith("_") and isinstance(
                       v, (int, float, str, bool, type(None)))}
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO feature_snapshots VALUES (?,?,?)",
                (ts_ms, coin, json.dumps(payload)))

    def save_gaps(self, rows) -> int:
        """rows: list of tuples matching the gaps table column order."""
        if not rows:
            return 0
        with self._lock, self.conn:
            self.conn.executemany(
                "INSERT OR REPLACE INTO gaps VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        return len(rows)

    def save_gap_run(self, ts_ms: int, pairs: int, venues: str, errors: str,
                     took_ms: int, gap_seconds: float) -> None:
        """One row per pass, including the seconds since the previous pass. A
        silent hole in the panel becomes a fake signal later, so gaps in the
        recording are recorded too."""
        with self._lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO gap_runs VALUES (?,?,?,?,?,?)",
                              (ts_ms, pairs, venues, errors, took_ms, gap_seconds))

    # ---- readers -----------------------------------------------------------
    def read(self, sql: str, params: Iterable[Any] = ()) -> pd.DataFrame:
        return pd.read_sql_query(sql, self.conn, params=list(params))

    def candles_df(self, coin: str, interval: str = "1d") -> pd.DataFrame:
        df = self.read("SELECT * FROM candles WHERE coin=? AND interval=? ORDER BY open_ms",
                       (coin, interval))
        if not df.empty:
            df.index = pd.to_datetime(df["open_ms"], unit="ms", utc=True)
        return df

    def oi_history(self, coin: str) -> pd.DataFrame:
        df = self.read("SELECT ts_ms, open_interest_usd, funding_hourly, mark_px "
                       "FROM ctx_snapshots WHERE coin=? ORDER BY ts_ms", (coin,))
        if not df.empty:
            df.index = pd.to_datetime(df["ts_ms"], unit="ms", utc=True)
        return df

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for t in ("candles", "funding", "trades", "ctx_snapshots",
                  "book_snapshots", "feature_snapshots", "gaps"):
            out[t] = int(self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
        return out
