"""Forward score-tracker — the out-of-sample judge of whether our score is real.

A backtest can be luck: you search until something passes. The only cure is to
commit a score BEFORE the outcome exists and grade it later, over and over. This
does exactly that. Each snapshot records, for every coin the composite calls
LONG/SHORT: the score, the entry price, and BTC's price — hashed with the as-of
date so it can't be edited after. When the 10-day hold matures, grade() looks up
the exit price and scores the pick on its BTC-NEUTRAL move (did LONG picks beat BTC,
did SHORT picks lag it), net of fees.

It is seeded with point-in-time history so the scorecard is populated today (that
part is in-sample, honestly labeled 'backfill'), and every snapshot from 2026-08-25
forward is genuinely out-of-sample ('live'). The scorecard keeps them separate — the
live rows are the ones that actually prove the edge; the backfill only proves the
pipeline works and matches the backtest.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "tracker.db"
HOLD_DAYS = 10
FEE_RT_SLIP = 0.0020

SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_ms INTEGER, as_of TEXT, coin TEXT, mode TEXT,   -- ts_ms: epoch-ms of as-of day
  dir TEXT, score REAL, exp_move REAL,
  entry_px REAL, btc_entry REAL,
  matured INTEGER DEFAULT 0,
  exit_px REAL, btc_exit REAL,
  resid_ret REAL, correct INTEGER,           -- graded outcome
  plan_hash TEXT,
  UNIQUE(ts_ms, coin, mode)
);
"""


def _iso(ts_ms) -> str:
    import datetime as _dt
    return _dt.datetime.utcfromtimestamp(int(ts_ms) / 1000).strftime("%Y-%m-%d")


def _conn():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def _ro():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


# ---- point-in-time composite (mirrors hl/signals.py weights: L12 survivors only) --

def _panel():
    """Return (composite DataFrame [date x coin], prices DataFrame). The score is the
    SAME funding + relative-strength-vs-BTC blend the live engine trades, computed
    point-in-time (everything shift()ed) for every historical day."""
    import numpy as np
    import pandas as pd
    px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
    good = [c for c in px.columns if px[c].notna().sum() > 150]
    px = px[good]
    fp = ROOT / "data" / "carry_cache" / "funding_daily_365.parquet"
    fund = pd.read_parquet(fp) if fp.exists() else None

    ret = px.pct_change(fill_method=None)
    btc = px["BTC"] if "BTC" in px.columns else px.iloc[:, 0]
    btc_ret = btc.pct_change()
    fund_apr = (fund.reindex_like(px) * 365.0) if fund is not None else px * np.nan
    ret7 = px / px.shift(7) - 1.0
    btc7 = btc / btc.shift(7) - 1.0
    beta = ret.rolling(60).cov(btc_ret).div(btc_ret.rolling(60).var(), axis=0)
    resid7 = ret7.sub(beta.mul(btc7, axis=0))
    rv30 = ret.rolling(30).std() * np.sqrt(365)

    def zrows(df):
        return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1).replace(0, np.nan), axis=0)

    comp = ((-1.0 * zrows(fund_apr).fillna(0) + 1.0 * zrows(resid7).fillna(0)) / 2.0)
    comp = comp * (0.6 / rv30).clip(upper=1.5)
    return comp, px, rv30


def _hash(as_of, coin, dir_, score, entry):
    return hashlib.sha256(f"{as_of}|{coin}|{dir_}|{score:.4f}|{entry:.6f}".encode()).hexdigest()[:16]


def snapshot(as_of, mode: str, comp=None, px=None, rv30=None, thresh=0.25) -> int:
    """Record every directional pick as-of a day (as_of = epoch-ms index value).
    Returns rows written."""
    if comp is None:
        comp, px, rv30 = _panel()
    if as_of not in comp.index:
        idx = comp.index[comp.index <= as_of]
        if len(idx) == 0:
            return 0
        as_of = idx[-1]
    ts = int(as_of)
    iso = _iso(ts)
    row = comp.loc[as_of]
    btc_entry = float(px.loc[as_of, "BTC"]) if "BTC" in px.columns else None
    conn = _conn()
    n = 0
    with conn:
        for coin, s in row.items():
            if s != s or abs(s) < thresh:      # NaN or FLAT -> not a pick
                continue
            entry = px.loc[as_of, coin]
            if entry != entry:
                continue
            dir_ = "LONG" if s > 0 else "SHORT"
            rv = rv30.loc[as_of, coin] if coin in rv30.columns else 0.8
            exp = abs(float(s)) * ((rv if rv == rv else 0.8) / 6.0)
            h = _hash(iso, coin, dir_, float(s), float(entry))
            cur = conn.execute(
                "INSERT OR IGNORE INTO signal_log(ts_ms,as_of,coin,mode,dir,score,exp_move,entry_px,btc_entry,plan_hash) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (ts, iso, coin, mode, dir_, float(s), float(exp), float(entry), btc_entry, h))
            n += cur.rowcount
    conn.close()
    return n


def grade(px=None) -> int:
    """Mature any pick past its 10-day hold: pull the exit price, score BTC-neutral.
    A LONG is correct if it BEAT BTC over the window; a SHORT if it LAGGED BTC."""
    import pandas as pd
    if px is None:
        _, px, _ = _panel()
    conn = _conn()
    rows = conn.execute("SELECT * FROM signal_log WHERE matured=0").fetchall()
    graded = 0
    with conn:
        for r in rows:
            ts = int(r["ts_ms"])
            # exit day = ts + HOLD_DAYS trading days, from the (epoch-ms) price index
            fut = px.index[px.index > ts]
            if len(fut) < HOLD_DAYS:
                continue                      # not enough future yet -> stays open
            exit_day = fut[HOLD_DAYS - 1]
            coin = r["coin"]
            if coin not in px.columns:
                continue
            exit_px = px.loc[exit_day, coin]
            btc_exit = float(px.loc[exit_day, "BTC"]) if "BTC" in px.columns else None
            if exit_px != exit_px or r["entry_px"] in (None, 0):
                continue
            coin_ret = exit_px / r["entry_px"] - 1.0
            btc_ret = (btc_exit / r["btc_entry"] - 1.0) if (btc_exit and r["btc_entry"]) else 0.0
            resid = coin_ret - btc_ret        # BTC-neutral move
            edge = resid if r["dir"] == "LONG" else -resid
            correct = 1 if edge - FEE_RT_SLIP > 0 else 0
            conn.execute("UPDATE signal_log SET matured=1,exit_px=?,btc_exit=?,resid_ret=?,correct=? WHERE id=?",
                         (float(exit_px), btc_exit, float(edge), correct, r["id"]))
            graded += 1
    conn.close()
    return graded


def backfill(step: int = 5) -> Dict[str, int]:
    """Seed the log with point-in-time snapshots across history, then grade them.
    In-sample by nature (labeled 'backfill') — proves the pipeline + matches L12."""
    comp, px, rv30 = _panel()
    dates = list(comp.index)
    start = 90                                 # need warmup for the features
    written = 0
    for i in range(start, len(dates) - HOLD_DAYS, step):
        written += snapshot(dates[i], "backfill", comp, px, rv30)
    g = grade(px)
    return {"snapshots": written, "graded": g}


def scorecard() -> Dict[str, Any]:
    """The honest running record: hit-rate + average BTC-neutral edge, split by
    live (out-of-sample, the real proof) vs backfill (in-sample seed)."""
    if not DB.exists():
        return {"live": {}, "backfill": {}, "open": 0}
    conn = _ro()

    def agg(mode):
        rows = conn.execute("SELECT dir,resid_ret,correct FROM signal_log WHERE matured=1 AND mode=?",
                            (mode,)).fetchall()
        if not rows:
            return {"n": 0}
        n = len(rows)
        hit = sum(r["correct"] for r in rows) / n
        avg_edge = sum(r["resid_ret"] for r in rows) / n
        longs = [r for r in rows if r["dir"] == "LONG"]
        shorts = [r for r in rows if r["dir"] == "SHORT"]
        return {"n": n, "hit": round(hit, 3), "avg_edge_pct": round(avg_edge * 100, 3),
                "n_long": len(longs), "n_short": len(shorts),
                "long_edge_pct": round(sum(r["resid_ret"] for r in longs) / len(longs) * 100, 3) if longs else None,
                "short_edge_pct": round(sum(r["resid_ret"] for r in shorts) / len(shorts) * 100, 3) if shorts else None}

    live, back = agg("live"), agg("backfill")
    open_n = conn.execute("SELECT COUNT(*) FROM signal_log WHERE matured=0").fetchone()[0]
    live_open = conn.execute("SELECT COUNT(*) FROM signal_log WHERE matured=0 AND mode='live'").fetchone()[0]
    recent = [dict(r) for r in conn.execute(
        "SELECT as_of,coin,dir,score,mode,matured,resid_ret,correct FROM signal_log "
        "ORDER BY as_of DESC, id DESC LIMIT 12").fetchall()]
    conn.close()
    return {"live": live, "backfill": back, "open": open_n, "live_open": live_open,
            "hold_days": HOLD_DAYS, "recent": recent}


def snapshot_live() -> int:
    """Take today's live snapshot (call daily). Genuinely out-of-sample from here."""
    comp, px, rv30 = _panel()
    return snapshot(comp.index[-1], "live", comp, px, rv30)


def heartbeat(note: str = "") -> None:
    """Freshness beat the watchdog reads to know the tracker loop is alive."""
    conn = _conn()
    with conn:
        conn.execute("CREATE TABLE IF NOT EXISTS tracker_runs (ts_ms INTEGER PRIMARY KEY, note TEXT)")
        conn.execute("INSERT OR REPLACE INTO tracker_runs VALUES (?,?)",
                     (int(time.time() * 1000), note))
    conn.close()
