"""One detailed row per tradable Hyperliquid coin, assembled from every source.

The dashboard's market overview reads this. We can only trade Hyperliquid perps,
so the universe is exactly the live (non-delisted) HL perp list - not the 26
venues, not spot. Everything else in the panel is here only to describe those
coins: where they sit versus the rest of the market, their funding, their
regional premia, their recent price.

Ranks are computed across the tradable set so "90th percentile funding" means
90th among coins we could actually take a position in, not among 26 venues.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
VENUES_DB = ROOT / "data" / "venues.db"
DAILY_CACHE = ROOT / "data" / "carry_cache" / "daily_365.parquet"


def _pctile(values: Dict[str, float]) -> Dict[str, float]:
    items = sorted(values.items(), key=lambda kv: kv[1])
    n = len(items)
    return {c: (i / (n - 1) if n > 1 else 0.5) for i, (c, _) in enumerate(items)}


def _daily_returns() -> Dict[str, Dict[str, float]]:
    if not DAILY_CACHE.exists():
        return {}
    try:
        import numpy as np
        import pandas as pd
        px = pd.read_parquet(DAILY_CACHE)
        out = {}
        for c in px.columns:
            s = px[c].dropna()
            if len(s) < 8:
                continue
            def r(n):
                return float(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None
            lr = np.log(s).diff().dropna()
            out[c] = {"ret_1d": r(1), "ret_7d": r(7), "ret_30d": r(30),
                      "vol_30d": float(lr.iloc[-30:].std() * np.sqrt(365)) if len(lr) >= 30 else None}
        return out
    except Exception:
        return {}


def market_overview() -> Dict[str, Any]:
    """Every tradable HL coin + its signals, plus the snapshot timestamps."""
    conn = sqlite3.connect(f"file:{VENUES_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def newest(table):
        # a fresh install has no cv_features until build_features.py runs and no
        # positioning until backfill_positioning.py runs: those columns are empty, not an error
        return conn.execute(f"SELECT MAX(ts_ms) FROM {table}").fetchone()[0] if table in have else None

    cv_ts = newest("cv_features")
    cv = {r["coin"]: dict(r) for r in conn.execute(
        "SELECT * FROM cv_features WHERE ts_ms=?", (cv_ts,)).fetchall()} if cv_ts else {}

    hl_ts = newest("hl_state")
    hl = {r["coin"]: dict(r) for r in conn.execute(
        "SELECT coin, mid, mark, oracle, funding_hourly, oi_base FROM hl_state "
        "WHERE ts_ms=?", (hl_ts,)).fetchall()} if hl_ts else {}

    pos_ts = newest("positioning")
    pos = {r["coin"]: dict(r) for r in conn.execute(
        "SELECT coin, long_frac, top_long_frac FROM positioning WHERE ts_ms=?",
        (pos_ts,)).fetchall()} if pos_ts else {}
    conn.close()

    daily = _daily_returns()

    # tradable universe = coins Hyperliquid is currently pricing (hl_state).
    coins = sorted(hl.keys())
    fund_vals = {c: hl[c]["funding_hourly"] for c in coins
                 if hl[c].get("funding_hourly") is not None}
    liquid_basis = {c: cv[c]["sp_basis_bps"] for c in coins
                    if c in cv and cv[c].get("sp_basis_bps") is not None
                    and (cv[c].get("credible_vol_usd") or 0) > 2e7}
    fund_pct = _pctile(fund_vals)
    basis_pct = _pctile(liquid_basis)

    rows: List[Dict[str, Any]] = []
    for c in coins:
        v = cv.get(c, {})
        h = hl[c]
        p = pos.get(c, {})
        d = daily.get(c, {})
        f = h.get("funding_hourly")
        tmr = (p.get("top_long_frac") - p.get("long_frac")
               if p.get("top_long_frac") is not None and p.get("long_frac") is not None else None)
        rows.append({
            "coin": c,
            "price": v.get("cp") or h.get("mid") or h.get("mark"),
            "funding_apr": f * 24 * 365 if f is not None else None,
            "funding_pctile": fund_pct.get(c),
            "basis_bps": v.get("sp_basis_bps"),
            "basis_pctile": basis_pct.get(c),
            "hl_dev_bps": v.get("hl_dev_bps"),
            "dispersion_bps": v.get("disp_iqr_bps"),
            "n_venues": v.get("n_venues"),
            "premium_krw_bps": v.get("premium_krw_bps"),
            "premium_inr_bps": v.get("premium_inr_bps"),
            "credible_vol_usd": v.get("credible_vol_usd"),
            "hl_spread_bps": v.get("hl_spread_bps"),
            "top_minus_retail": tmr,
            "ret_1d": d.get("ret_1d"), "ret_7d": d.get("ret_7d"),
            "ret_30d": d.get("ret_30d"), "vol_30d": d.get("vol_30d"),
        })

    return {
        "coins": rows,
        "n_tradable": len(rows),
        "as_of": {"cross_venue_ms": cv_ts, "hl_ms": hl_ts, "positioning_ms": pos_ts},
        "n_with_basis": sum(1 for r in rows if r["basis_bps"] is not None),
        "n_with_daily": sum(1 for r in rows if r["ret_7d"] is not None),
    }
