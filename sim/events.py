"""The event store and the clock (spec 4.3, C1-C15, C45; capability list A1-A10).

Tables in store.db (bitemporal: `observed_at` = when we could have known the row exists,
`scheduled_ts` = when the event happens, UTC ms):

  event_type(id, family, scheduled, default_horizons)
  event_instance(id, event_type, entity, asset_id, scheduled_ts, ts_precision,
                 consensus, consensus_source, realised, realised_source, surprise_z,
                 observed_at, source_url)

Seeds (all fetched 2026-09-16, sources in docs/AGENT_V2_RESEARCH_B_2026-09-16.md B10):
  FOMC 2021-2026 statements 14:00 America/New_York (federalreserve.gov/monetarypolicy/fomccalendars.htm)
  CPI and Employment Situation (NFP) 2021-2026, 08:30 America/New_York (bls.gov/schedule/<year>/home.htm)
  Deribit monthly expiry: last Friday of the month 08:00 UTC (quarterly = Mar/Jun/Sep/Dec)
  Token unlocks from unlocks.db (next event per project) with size and % of max supply
  Hyperliquid listings from asset.first_seen_ms (survivorship-correct universe later uses last_seen)

Realised values: FOMC = change in the effective Fed funds rate (US_FEDFUNDS, macro_series) from
the day before the decision to two days after, in bp - NULL when the series is missing. CPI/NFP
realised prints are not in the store yet -> NULL (never fabricated). Consensus: NULL until the
prediction-market mapping lands (spec C6); surprise_z therefore NULL.

Sessions: `session_of(ts)` -> asia (00-08 UTC) / europe (08-13) / us (13-21) / late (21-24) /
weekend. Used by the calendar tool and the risk desk's event rule.
"""
from __future__ import annotations

import calendar as _cal
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .data import STORE, ROOT

NY = ZoneInfo("America/New_York")
DAY_MS = 86_400_000
UNLOCKS = ROOT / "data" / "unlocks.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS event_type (
  id TEXT PRIMARY KEY, family TEXT NOT NULL, scheduled INTEGER NOT NULL, default_horizons TEXT
);
CREATE TABLE IF NOT EXISTS event_instance (
  id INTEGER PRIMARY KEY, event_type TEXT NOT NULL, entity TEXT, asset_id INTEGER,
  scheduled_ts INTEGER NOT NULL, ts_precision TEXT NOT NULL,
  consensus REAL, consensus_source TEXT, realised REAL, realised_source TEXT, surprise_z REAL,
  observed_at INTEGER NOT NULL, source_url TEXT,
  UNIQUE(event_type, entity, scheduled_ts)
);
CREATE INDEX IF NOT EXISTS ix_evi_ts ON event_instance(scheduled_ts);
"""

EVENT_TYPES = [
    ("fomc", "cb_decision", 1, "1d,3d,7d"), ("cpi", "macro_release", 1, "1d,3d,7d"),
    ("nfp", "macro_release", 1, "1d,3d,7d"), ("opex", "opex", 1, "1d,3d"),
    ("unlock", "unlock", 1, "1d,3d,7d,14d"), ("listing", "listing", 0, "1d,3d,7d,30d"),
]

# ---- seeds (dates as published; times converted from New York local time) -----------------
FOMC = {2021: ["01-27", "03-17", "04-28", "06-16", "07-28", "09-22", "11-03", "12-15"],
        2022: ["01-26", "03-16", "05-04", "06-15", "07-27", "09-21", "11-02", "12-14"],
        2023: ["02-01", "03-22", "05-03", "06-14", "07-26", "09-20", "11-01", "12-13"],
        2024: ["01-31", "03-20", "05-01", "06-12", "07-31", "09-18", "11-07", "12-18"],
        2025: ["01-29", "03-19", "05-07", "06-18", "07-30", "09-17", "10-29", "12-10"],
        2026: ["01-28", "03-18", "04-29", "06-17", "07-29", "09-16", "10-28", "12-09"]}
CPI = {2021: ["01-13", "02-10", "03-10", "04-13", "05-12", "06-10", "07-13", "08-11", "09-14", "10-13", "11-10", "12-10"],
       2022: ["01-12", "02-10", "03-10", "04-12", "05-11", "06-10", "07-13", "08-10", "09-13", "10-13", "11-10", "12-13"],
       2023: ["01-12", "02-14", "03-14", "04-12", "05-10", "06-13", "07-12", "08-10", "09-13", "10-12", "11-14", "12-12"],
       2024: ["01-11", "02-13", "03-12", "04-10", "05-15", "06-12", "07-11", "08-14", "09-11", "10-10", "11-13", "12-11"],
       2025: ["01-15", "02-12", "03-12", "04-10", "05-13", "06-11", "07-15", "08-12", "09-11", "10-24", "12-18"],
       2026: ["01-13", "02-13", "03-11", "04-10", "05-12", "06-10", "07-14", "08-12", "09-11", "10-14", "11-10", "12-10"]}
NFP = {2021: ["01-08", "02-05", "03-05", "04-02", "05-07", "06-04", "07-02", "08-06", "09-03", "10-08", "11-05", "12-03"],
       2022: ["01-07", "02-04", "03-04", "04-01", "05-06", "06-03", "07-08", "08-05", "09-02", "10-07", "11-04", "12-02"],
       2023: ["01-06", "02-03", "03-10", "04-07", "05-05", "06-02", "07-07", "08-04", "09-01", "10-06", "11-03", "12-08"],
       2024: ["01-05", "02-02", "03-08", "04-05", "05-03", "06-07", "07-05", "08-02", "09-06", "10-04", "11-01", "12-06"],
       2025: ["01-10", "02-07", "03-07", "04-04", "05-02", "06-06", "07-03", "08-01", "09-05", "11-20", "12-16"],
       2026: ["01-09", "02-11", "03-06", "04-03", "05-08", "06-05", "07-02", "08-07", "09-04", "10-02", "11-06", "12-04"]}
SRC_FED = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
SRC_BLS = "https://www.bls.gov/schedule/{year}/home.htm"


def ny_to_utc_ms(year: int, md: str, hh: int, mm: int) -> int:
    m, d = (int(x) for x in md.split("-"))
    return int(datetime(year, m, d, hh, mm, tzinfo=NY).astimezone(timezone.utc).timestamp() * 1000)


def last_friday_08utc(year: int, month: int) -> int:
    last = _cal.monthrange(year, month)[1]
    d = datetime(year, month, last, 8, 0, tzinfo=timezone.utc)
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return int(d.timestamp() * 1000)


def session_of(ts_ms: int) -> str:
    d = datetime.fromtimestamp(ts_ms / 1000, timezone.utc)
    if d.weekday() >= 5:
        return "weekend"
    h = d.hour
    return "asia" if h < 8 else "europe" if h < 13 else "us" if h < 21 else "late"


def seed(conn: Optional[sqlite3.Connection] = None) -> Dict[str, int]:
    """Idempotent: INSERT OR IGNORE on (type, entity, scheduled_ts). Returns rows per type."""
    own = conn is None
    conn = conn or sqlite3.connect(STORE)
    conn.executescript(SCHEMA)
    conn.executemany("INSERT OR IGNORE INTO event_type VALUES (?,?,?,?)", EVENT_TYPES)
    rows = []
    jan1 = lambda y: int(datetime(y - 1, 12, 1, tzinfo=timezone.utc).timestamp() * 1000)   # schedules are public by Dec of the prior year
    for y, days in FOMC.items():
        for md in days:
            rows.append(("fomc", "FOMC statement", None, ny_to_utc_ms(y, md, 14, 0), "minute", jan1(y), SRC_FED))
    for y, days in CPI.items():
        for md in days:
            rows.append(("cpi", "US CPI", None, ny_to_utc_ms(y, md, 8, 30), "minute", jan1(y), SRC_BLS.format(year=y)))
    for y, days in NFP.items():
        for md in days:
            rows.append(("nfp", "US Employment Situation", None, ny_to_utc_ms(y, md, 8, 30), "minute", jan1(y), SRC_BLS.format(year=y)))
    for y in range(2021, 2028):
        for m in range(1, 13):
            rows.append(("opex", "Deribit monthly expiry" + (" (quarterly)" if m in (3, 6, 9, 12) else ""), None,
                         last_friday_08utc(y, m), "minute", jan1(y), "rule: last Friday 08:00 UTC"))
    # unlocks (next event per project, with size); observed when the unlock feed refreshed
    ids = {sym: i for sym, i in conn.execute("SELECT symbol, id FROM asset")}     # symbol -> id
    try:
        u = sqlite3.connect(f"file:{UNLOCKS}?mode=ro", uri=True)
        for slug, gid, ts, tokens, pct, desc, upd in u.execute(
                "SELECT slug, gecko_id, next_ts, next_tokens, next_pct_max, next_desc, updated_ms FROM unlocks WHERE next_ts IS NOT NULL"):
            sym = (slug or "").upper()
            rows.append(("unlock", f"{slug} unlock {pct or 0:.2f}% of max supply", ids.get(sym), int(ts), "day",
                         int(upd or ts), "unlocks.db"))
        u.close()
    except Exception:
        pass
    # listings: first time we saw the perp (survivorship: delisting kept in asset.last_seen_ms)
    for sym, first in conn.execute("SELECT symbol, first_seen_ms FROM asset WHERE first_seen_ms IS NOT NULL "
                                   "AND id IN (SELECT DISTINCT asset_id FROM ohlcv)"):
        rows.append(("listing", f"{sym} listed on Hyperliquid", ids.get(sym), int(first), "minute", int(first), "hl universe"))
    conn.executemany("INSERT OR IGNORE INTO event_instance(event_type, entity, asset_id, scheduled_ts, ts_precision, observed_at, source_url) "
                     "VALUES (?,?,?,?,?,?,?)", rows)
    # realised FOMC: effective Fed funds change from T-1 to T+2 (bp)
    ff = pd.read_sql_query("SELECT ts_ms, value FROM macro_series WHERE series_id='US_FEDFUNDS' ORDER BY ts_ms", conn)
    if len(ff):
        ff = ff.set_index("ts_ms")["value"]
        for id_, ts in conn.execute("SELECT id, scheduled_ts FROM event_instance WHERE event_type='fomc' AND realised IS NULL").fetchall():
            before = ff[ff.index <= ts - DAY_MS]; after = ff[ff.index >= ts + 2 * DAY_MS]
            if len(before) and len(after):
                conn.execute("UPDATE event_instance SET realised=?, realised_source='US_FEDFUNDS T-1 -> T+2, bp' WHERE id=?",
                             (round((float(after.iloc[0]) - float(before.iloc[-1])) * 100, 1), id_))
    conn.commit()
    out = dict(conn.execute("SELECT event_type, COUNT(*) FROM event_instance GROUP BY event_type").fetchall())
    if own:
        conn.close()
    return out


# ---- reads (time-locked) ----------------------------------------------------------------
class Calendar:
    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        self.conn = conn or sqlite3.connect(f"file:{STORE}?mode=ro", uri=True)
        self.df = pd.read_sql_query("SELECT * FROM event_instance", self.conn)
        self.names = {i: s for i, s in self.conn.execute("SELECT id, symbol FROM asset")}
        self.df["coin"] = self.df["asset_id"].map(self.names)

    def upcoming(self, t: int, days: int = 7, coins: Optional[List[str]] = None) -> pd.DataFrame:
        """Events known at t (observed_at <= t) scheduled in [t, t + days]."""
        d = self.df[(self.df.observed_at <= t) & (self.df.scheduled_ts >= t) & (self.df.scheduled_ts <= t + days * DAY_MS)]
        if coins is not None:
            d = d[d.coin.isna() | d.coin.isin(coins)]
        return d.sort_values("scheduled_ts")

    def past(self, t: int, event_type: str, coin: Optional[str] = None, horizon_days: int = 7) -> pd.DataFrame:
        """Instances whose outcome horizon has passed by t (no peeking)."""
        d = self.df[(self.df.event_type == event_type) & (self.df.scheduled_ts + horizon_days * DAY_MS <= t) & (self.df.observed_at <= t)]
        if coin:
            d = d[d.coin == coin]
        return d.sort_values("scheduled_ts")

    def next_macro_hours(self, t: int) -> Optional[Dict]:
        d = self.upcoming(t, 30)
        d = d[d.event_type.isin(["fomc", "cpi", "nfp"])]
        if d.empty:
            return None
        r = d.iloc[0]
        return {"event": r.event_type, "entity": r.entity, "hours": round((r.scheduled_ts - t) / 3.6e6, 1),
                "utc": datetime.fromtimestamp(r.scheduled_ts / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}


def outcomes(cal: Calendar, resid: pd.DataFrame, close: pd.DataFrame, t: int, event_type: str,
             target: str = "BTC", coin: Optional[str] = None, horizons=(1, 3, 7)) -> Dict:
    """What `target` (or the event's own coin) did after past instances: residual return
    (coin events) or raw BTC/ETH return (macro events) at each horizon; median, hit rate, n.
    Only instances whose horizon has passed by t."""
    past = cal.past(t, event_type, coin, max(horizons))
    if past.empty:
        return {"event_type": event_type, "n": 0}
    out = {"event_type": event_type, "target": target if coin is None else "own coin", "n": int(len(past)), "horizons": {}}
    for h in horizons:
        vals = []
        for _, r in past.iterrows():
            tgt = r.coin if coin is not None else target
            src = resid if coin is not None else np.log(close).diff()
            if tgt not in src.columns:
                continue
            day = (r.scheduled_ts // DAY_MS) * DAY_MS
            win = src[tgt][(src.index > day) & (src.index <= day + h * DAY_MS)].dropna()
            if len(win):
                vals.append(float(win.sum()) * 100)
        if vals:
            v = np.array(vals)
            out["horizons"][f"{h}d"] = {"median_pct": round(float(np.median(v)), 2), "p25": round(float(np.percentile(v, 25)), 2),
                                        "p75": round(float(np.percentile(v, 75)), 2), "hit_up": round(float((v > 0).mean()), 2), "n": int(len(v))}
    return out


if __name__ == "__main__":
    print(seed())
