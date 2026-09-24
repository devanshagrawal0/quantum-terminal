"""As-of data for the simulator. Nothing after `now` is reachable through here.

Every accessor takes the simulation clock `t` (a UTC day, ms since epoch) and returns
only what was knowable at the close of that day. That is the whole point of this
module: the agent cannot cheat, because the only door to the data is this one and it
is time-locked.

What is available historically (measured 2026-09-15):
  prices      172 coins, hourly, 2020-01 -> 2026-08 (daily close/high/low built from it)
  features    every feat_* column, all 172 coins, sampled at the 00:00 UTC bar
  positioning 172 coins, 2026-08-02 -> yesterday (NULL before that; the agent sees None)
  funding     daily, last ~365 days (carry_cache) + perp_state since 2026-08-23; None before
  spread      one measured Hyperliquid spread per coin (venues.db cv_features average)

Frames are loaded once and cached under data/sim/cache/ as pickles (no pyarrow here).
Memory: an agent declares the feature columns it needs; only those are loaded.
"""
from __future__ import annotations

import hashlib
import os
import pickle
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "store.db"
VENUES = ROOT / "data" / "venues.db"
CACHE = ROOT / "data" / "sim" / "cache"
DAY_MS = 86_400_000
# the decision moment is the close of the day's LAST hourly bar (the 23:00 bar); every
# as-of read samples that bar, never the 00:00 one (that would be 23 hours stale)
DECIDE_OFF = 23 * 3_600_000

FEATURE_TABLES = ["feat_ret", "feat_volat", "feat_trend", "feat_osc", "feat_bands",
                  "feat_vol_flow", "feat_risk", "feat_candle", "feat_cross"]


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)


def _store_stamp() -> str:
    """The newest candle, funding row and positioning row, plus the candle count; a cache built
    before any of them changed is stale. The count matters: backfilling more coins over the same
    dates leaves every MAX unchanged, and the cache would silently keep the smaller universe."""
    parts = []
    try:
        conn = _ro(STORE)
        parts.append(conn.execute("SELECT MAX(ts_ms) FROM ohlcv WHERE interval='1h'").fetchone()[0])
        parts.append(conn.execute("SELECT COUNT(*) FROM ohlcv WHERE interval='1h'").fetchone()[0])
        parts.append(conn.execute("SELECT MAX(ts_ms) FROM perp_state").fetchone()[0])
        conn.close()
    except Exception:
        parts.append(None)
    try:
        conn = _ro(VENUES)
        parts.append(conn.execute("SELECT MAX(ts_ms) FROM positioning WHERE period='1h'").fetchone()[0])
        conn.close()
    except Exception:
        parts.append(None)
    return "|".join(str(int(x or 0)) for x in parts)


def _cached(name: str, build):
    """Build once per data vintage: the pickle carries the store stamp it was built from
    and is rebuilt when the store has newer candles (or when SIM_REFRESH=1)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{name}.pkl"
    stamp = _store_stamp()
    if p.exists() and os.environ.get("SIM_REFRESH", "0") != "1":
        with open(p, "rb") as f:
            blob = pickle.load(f)
        if isinstance(blob, dict) and blob.get("__stamp__") == stamp and "__obj__" in blob:
            return blob["__obj__"]
    obj = build()
    with open(p, "wb") as f:
        pickle.dump({"__stamp__": stamp, "__obj__": obj}, f, protocol=pickle.HIGHEST_PROTOCOL)
    return obj


def _names(conn) -> Dict[int, str]:
    return {i: s for i, s in conn.execute("SELECT id, symbol FROM asset")}


def daily_ohlc() -> Dict[str, pd.DataFrame]:
    """close / high / low per UTC day, ts index = the day's 00:00 bar (its close is the
    day's close), columns = coins. High/low are the max/min of the day's hourly bars,
    so a stop that would have been hit intraday IS hit in the sim."""
    def build():
        conn = _ro(STORE)
        names = _names(conn)
        df = pd.read_sql_query(
            "SELECT ts_ms, asset_id, c, h, l FROM ohlcv WHERE interval='1h'", conn)
        conn.close()
        df["coin"] = df["asset_id"].map(names)
        df["day"] = (df["ts_ms"] // DAY_MS) * DAY_MS
        close = df.sort_values("ts_ms").groupby(["day", "coin"])["c"].last().unstack()
        high = df.groupby(["day", "coin"])["h"].max().unstack()
        low = df.groupby(["day", "coin"])["l"].min().unstack()
        return {"close": close.sort_index(), "high": high.sort_index(), "low": low.sort_index()}
    return _cached("daily_ohlc", build)


def daily_features(cols: Iterable[str]) -> Dict[str, pd.DataFrame]:
    """{feature: DataFrame(day x coin)} for the requested columns, at the day's 23:00 bar."""
    cols = sorted(set(cols))
    if not cols:
        return {}
    def build():
        conn = _ro(STORE)
        names = _names(conn)
        where = {}
        for t in FEATURE_TABLES:
            have = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
            for c in cols:
                if c in have and c not in where:
                    where[c] = t
        missing = [c for c in cols if c not in where]
        if missing:
            raise KeyError(f"unknown feature columns: {missing}")
        out: Dict[str, pd.DataFrame] = {}
        for t in FEATURE_TABLES:
            tc = [c for c in cols if where[c] == t]
            if not tc:
                continue
            df = pd.read_sql_query(
                f"SELECT ts_ms, asset_id, {', '.join(tc)} FROM {t} WHERE ts_ms % {DAY_MS} = {DECIDE_OFF}", conn)
            df["ts_ms"] = df["ts_ms"] - DECIDE_OFF          # key by day
            df["coin"] = df["asset_id"].map(names)
            for c in tc:
                out[c] = df.pivot(index="ts_ms", columns="coin", values=c).sort_index().astype("float32")
        conn.close()
        return out
    key = hashlib.md5("|".join(cols).encode()).hexdigest()[:10]       # stable across processes (hash() is not)
    return _cached(f"feat_{key}", build)


def daily_positioning() -> Dict[str, pd.DataFrame]:
    """long_frac / top_long_frac / oi_usd at the day's 23:00 row, from venues.db."""
    def build():
        conn = _ro(VENUES)
        df = pd.read_sql_query(
            "SELECT ts_ms, coin, long_frac, top_long_frac, oi_usd FROM positioning "
            f"WHERE period='1h' AND ts_ms % {DAY_MS} = {DECIDE_OFF}", conn)
        conn.close()
        df["ts_ms"] = df["ts_ms"] - DECIDE_OFF
        return {c: df.pivot(index="ts_ms", columns="coin", values=c).sort_index()
                for c in ("long_frac", "top_long_frac", "oi_usd")}
    return _cached("positioning", build)


def daily_funding() -> pd.DataFrame:
    """Daily funding (fraction per day) per coin: carry_cache parquet if readable,
    else built from perp_state hourly funding. NaN where unknown."""
    def build():
        frames = []
        pq = ROOT / "data" / "carry_cache" / "funding_daily_365.parquet"
        if pq.exists():
            try:
                f = pd.read_parquet(pq)
                f.index = (pd.to_datetime(f.index.astype("int64"), unit="ms", utc=True)
                           .floor("D").astype("int64") // 10**6)
                frames.append(f)
            except Exception:
                pass   # no parquet engine on this PC; fall through
        conn = _ro(STORE)
        names = _names(conn)
        df = pd.read_sql_query("SELECT ts_ms, asset_id, funding_hourly FROM perp_state", conn)
        conn.close()
        df["coin"] = df["asset_id"].map(names)
        df["day"] = (df["ts_ms"] // DAY_MS) * DAY_MS
        ps = df.groupby(["day", "coin"])["funding_hourly"].sum().unstack()
        frames.append(ps)
        out = pd.concat(frames).groupby(level=0).last().sort_index()
        return out
    return _cached("funding", build)


def spreads_bps() -> pd.Series:
    conn = _ro(VENUES)
    s = pd.read_sql_query("SELECT coin, AVG(hl_spread_bps) AS s FROM cv_features GROUP BY coin", conn)
    conn.close()
    return s.set_index("coin")["s"]


class AsOf:
    """The time-locked view an agent gets. `t` is a day key (ms at 00:00 UTC)."""

    def __init__(self, feature_cols: Iterable[str] = (), universe: Optional[List[str]] = None):
        ohlc = daily_ohlc()
        self.close, self.high, self.low = ohlc["close"], ohlc["high"], ohlc["low"]
        self.feats = daily_features(feature_cols)
        self.pos = daily_positioning()
        self.funding = daily_funding()
        self.spread = spreads_bps()
        self.days: List[int] = list(self.close.index)
        self.universe = universe or list(self.close.columns)
        from .events import Calendar
        self.calendar = Calendar()                      # event store (time-locked reads by observed_at)
        self.xsec = None                                # cross-sectional layer, attached by the runner

    # ---- time-locked reads -------------------------------------------------
    def price(self, t: int, coin: str) -> Optional[float]:
        v = self.close.at[t, coin] if t in self.close.index and coin in self.close.columns else np.nan
        return None if pd.isna(v) else float(v)

    def closes(self, t: int, n: int, coins: Optional[List[str]] = None) -> pd.DataFrame:
        """The last n daily closes up to and including t."""
        idx = self.close.index.get_indexer([t])[0]
        if idx < 0:
            raise KeyError(f"{t} is not a simulation day")
        block = self.close.iloc[max(0, idx - n + 1): idx + 1]
        return block[coins] if coins else block

    def feature(self, t: int, name: str) -> pd.Series:
        f = self.feats[name]
        if t not in f.index:
            return pd.Series(np.nan, index=self.universe)
        return f.loc[t].reindex(self.universe)

    def positioning(self, t: int, name: str) -> pd.Series:
        f = self.pos[name]
        if t not in f.index:
            return pd.Series(np.nan, index=self.universe)
        return f.loc[t].reindex(self.universe)

    def funding_day(self, t: int) -> pd.Series:
        if t not in self.funding.index:
            return pd.Series(np.nan, index=self.universe)
        return self.funding.loc[t].reindex(self.universe)

    def tradable(self, t: int) -> List[str]:
        row = self.close.loc[t] if t in self.close.index else None
        if row is None:
            return []
        return [c for c in self.universe if c in row.index and not pd.isna(row[c])]

    def day_range(self, t: int, coin: str):
        """(high, low) of day t - used ONLY by the engine to settle stops/targets."""
        return float(self.high.at[t, coin]), float(self.low.at[t, coin])
