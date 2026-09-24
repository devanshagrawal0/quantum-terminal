"""The situation assembler: everything we know about one coin, in one place.

This is the decision surface. All the collectors write to five different
databases; nothing until now pulled them together into something a person - or
a reasoning model - could look at and form a view. That assembly is the whole
job here.

What it deliberately does NOT do: decide. It gathers and it ranks the coin
against the universe on the numbers that are structural, but it never says
long or short. The reasoning happens after, reading this, because the edge Dev
is building is reasoning over the whole picture, not a threshold on any one line.

Two honest boundaries, both stated in the output rather than hidden:

  * FUNDING PERCENTILE is the one measured effect we have (high funding coins
    underperform, mostly via the carry you collect shorting them). The coin's
    rank in the cross-section is shown because that is the signal with a pulse.

  * EVENTS ARE NOT COIN-FILTERED. Matching a ticker string to a headline is the
    banned pattern - "ME", "W", "S" are real tickers and a substring match is
    not comprehension. So recent events are surfaced RAW and it is the reasoning
    step's job to decide which one, if any, is about this coin.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
VENUES_DB = ROOT / "data" / "venues.db"
EVENTS_DB = ROOT / "data" / "events.db"
SOCIAL_DB = ROOT / "data" / "social.db"


def _ro(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _pct_rank(value: Optional[float], population: List[float]) -> Optional[float]:
    if value is None or not population:
        return None
    below = sum(1 for x in population if x < value)
    return below / len(population)


def cross_venue_state(coin: str) -> Dict[str, Any]:
    """Latest cross-venue features for the coin, plus its rank in the universe
    on the lines that matter."""
    conn = _ro(VENUES_DB)
    last = conn.execute("SELECT MAX(ts_ms) FROM cv_features").fetchone()[0]
    if not last:
        conn.close()
        return {}
    rows = conn.execute("SELECT * FROM cv_features WHERE ts_ms=?", (last,)).fetchall()
    conn.close()
    universe = {r["coin"]: dict(r) for r in rows}
    me = universe.get(coin)
    if not me:
        return {"as_of_ms": last, "found": False}

    liquid = [v for v in universe.values() if (v["credible_vol_usd"] or 0) > 2e7]
    basis_pop = [v["sp_basis_bps"] for v in liquid if v["sp_basis_bps"] is not None]
    disp_pop = [v["disp_iqr_bps"] for v in liquid if v["disp_iqr_bps"] is not None]
    hldev_pop = [abs(v["hl_dev_bps"]) for v in liquid if v["hl_dev_bps"] is not None]

    return {
        "as_of_ms": last, "found": True,
        "consolidated_price": me["cp"],
        "n_venues": me["n_venues"],
        "credible_vol_usd": me["credible_vol_usd"],
        "hl_dev_bps": me["hl_dev_bps"],
        "hl_dev_pctile": _pct_rank(abs(me["hl_dev_bps"]) if me["hl_dev_bps"] is not None else None, hldev_pop),
        "perp_spot_basis_bps": me["sp_basis_bps"],
        "basis_pctile": _pct_rank(me["sp_basis_bps"], basis_pop),
        "dispersion_bps": me["disp_iqr_bps"],
        "dispersion_pctile": _pct_rank(me["disp_iqr_bps"], disp_pop),
        "hl_spread_bps": me["hl_spread_bps"],
        "hl_vol_share": me["hl_vol_share"],
        "premium_krw_bps": me["premium_krw_bps"],
        "premium_inr_bps": me["premium_inr_bps"],
    }


def funding_state(coin: str) -> Dict[str, Any]:
    """The coin's funding, and where it ranks - this is the one measured signal.

    A coin in the top decile of funding is the short-carry candidate the year of
    data supported. The rank matters more than the level.
    """
    conn = _ro(VENUES_DB)
    last = conn.execute("SELECT MAX(ts_ms) FROM positioning").fetchone()[0]
    rows = conn.execute(
        "SELECT coin, oi_usd, long_frac, top_long_frac, taker_ratio "
        "FROM positioning WHERE ts_ms=?", (last,)).fetchall() if last else []
    pos = {r["coin"]: dict(r) for r in rows}
    conn.close()

    # Current HL funding from the live snapshot's hl_state.
    conn = _ro(VENUES_DB)
    hlast = conn.execute("SELECT MAX(ts_ms) FROM hl_state").fetchone()[0]
    frows = conn.execute("SELECT coin, funding_hourly, oi_base FROM hl_state WHERE ts_ms=?",
                         (hlast,)).fetchall() if hlast else []
    conn.close()
    fund = {r["coin"]: r["funding_hourly"] for r in frows if r["funding_hourly"] is not None}
    me_fund = fund.get(coin)
    pop = list(fund.values())

    me_pos = pos.get(coin, {})
    return {
        "hl_funding_hourly": me_fund,
        "hl_funding_apr": me_fund * 24 * 365 if me_fund is not None else None,
        "funding_pctile": _pct_rank(me_fund, pop),
        "binance_top_long_frac": me_pos.get("top_long_frac"),
        "binance_retail_long_frac": me_pos.get("long_frac"),
        "binance_top_minus_retail": (
            (me_pos.get("top_long_frac") - me_pos.get("long_frac"))
            if me_pos.get("top_long_frac") is not None
            and me_pos.get("long_frac") is not None else None),
        "binance_taker_ratio": me_pos.get("taker_ratio"),
    }


def recent_events(limit: int = 12) -> List[Dict[str, Any]]:
    """The newest events across all sources, RAW and unfiltered. Linking one to
    this coin is a reasoning step, not a string match - see the module note."""
    try:
        conn = _ro(EVENTS_DB)
        rows = conn.execute(
            "SELECT source, title, url, first_seen_ms FROM events "
            "WHERE kind='announcement' ORDER BY first_seen_ms DESC LIMIT ?",
            (limit,)).fetchall()
        changes = conn.execute(
            "SELECT coin, change, detail, ts_ms FROM hl_universe_changes "
            "ORDER BY ts_ms DESC LIMIT 5").fetchall()
        conn.close()
    except sqlite3.Error:
        return []
    out = [{"source": r["source"], "title": r["title"], "url": r["url"],
            "seen_ms": r["first_seen_ms"]} for r in rows]
    for c in changes:
        out.append({"source": "hl_universe", "title": f"{c['coin']} {c['change']} {c['detail']}",
                    "url": "", "seen_ms": c["ts_ms"]})
    return out


def daily_context(coin: str) -> Dict[str, Any]:
    """Recent price behaviour from the cached daily candles, if present."""
    f = ROOT / "data" / "carry_cache" / "daily_365.parquet"
    if not f.exists():
        return {}
    import pandas as pd
    px = pd.read_parquet(f)
    if coin not in px.columns:
        return {}
    s = px[coin].dropna()
    if len(s) < 8:
        return {}
    def ret(n):
        return float(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None
    import numpy as np
    logret = np.log(s).diff().dropna()
    return {
        "ret_1d": ret(1), "ret_3d": ret(3), "ret_7d": ret(7), "ret_30d": ret(30),
        "vol_30d_ann": float(logret.iloc[-30:].std() * np.sqrt(365)) if len(logret) >= 30 else None,
        "dist_from_30d_high": float(s.iloc[-1] / s.iloc[-30:].max() - 1) if len(s) >= 30 else None,
    }


def build(coin: str) -> Dict[str, Any]:
    """The whole situation for one coin, assembled from every collector."""
    coin = coin.upper()
    return {
        "coin": coin,
        "built_ms": int(time.time() * 1000),
        "cross_venue": cross_venue_state(coin),
        "funding": funding_state(coin),
        "daily": daily_context(coin),
        "recent_events_unfiltered": recent_events(),
    }


def render(d: Dict[str, Any]) -> str:
    """Plain-English brief. Written for a person to read and reason over, not a
    machine to parse - the numbers are all here, in words, with their ranks."""
    coin = d["coin"]
    cv = d.get("cross_venue", {})
    fu = d.get("funding", {})
    dy = d.get("daily", {})
    L = [f"=== {coin} — situation as assembled {time.strftime('%H:%M:%S', time.localtime(d['built_ms']/1000))} ==="]

    def pct(x):
        return f"{x*100:.0f}th pctile" if x is not None else "n/a"

    def num(x, f="{:+.1f}"):
        return f.format(x) if x is not None else "n/a"

    if cv.get("found"):
        L.append(f"\nPRICE / CROSS-VENUE  (consolidated {cv['consolidated_price']:,.6g}, "
                 f"{cv['n_venues']} venues, ${(cv['credible_vol_usd'] or 0)/1e6:.0f}m credible vol)")
        L.append(f"  Hyperliquid vs world:  {num(cv['hl_dev_bps'])} bps  ({pct(cv['hl_dev_pctile'])} extreme)")
        L.append(f"  perp vs spot basis:    {num(cv['perp_spot_basis_bps'])} bps  ({pct(cv['basis_pctile'])})")
        L.append(f"  venue disagreement:    {num(cv['dispersion_bps'],'{:.1f}')} bps  ({pct(cv['dispersion_pctile'])})")
        L.append(f"  HL spread:             {num(cv['hl_spread_bps'],'{:.1f}')} bps"
                 f"   HL volume share: {num(cv['hl_vol_share'],'{:.1%}')}")
        if cv.get("premium_krw_bps") is not None:
            L.append(f"  Korea premium: {num(cv['premium_krw_bps'])} bps"
                     + (f"   India premium: {num(cv['premium_inr_bps'])} bps"
                        if cv.get("premium_inr_bps") is not None else ""))
    else:
        L.append("\nPRICE / CROSS-VENUE  not found in the latest snapshot")

    L.append("\nFUNDING / POSITIONING  (funding percentile is our one measured signal)")
    L.append(f"  HL funding:  {num(fu['hl_funding_hourly'],'{:+.6f}')}/hr"
             f"  ({num(fu['hl_funding_apr'],'{:+.1%}')} APR)  {pct(fu['funding_pctile'])}")
    if fu.get("funding_pctile") is not None and fu["funding_pctile"] > 0.9:
        L.append("    -> TOP-DECILE FUNDING: the measured short-carry candidate. "
                 "High funding coins underperform (mostly the carry you collect).")
    if fu.get("binance_top_minus_retail") is not None:
        L.append(f"  Binance top-trader long {num(fu['binance_top_long_frac'],'{:.0%}')} "
                 f"vs retail {num(fu['binance_retail_long_frac'],'{:.0%}')}  "
                 f"(divergence {num(fu['binance_top_minus_retail'],'{:+.0%}')})")

    if dy:
        L.append("\nRECENT PRICE")
        L.append(f"  1d {num(dy.get('ret_1d'),'{:+.1%}')}  3d {num(dy.get('ret_3d'),'{:+.1%}')}  "
                 f"7d {num(dy.get('ret_7d'),'{:+.1%}')}  30d {num(dy.get('ret_30d'),'{:+.1%}')}"
                 f"  |  30d vol {num(dy.get('vol_30d_ann'),'{:.0%}')} ann"
                 f"  |  {num(dy.get('dist_from_30d_high'),'{:+.1%}')} from 30d high")

    evs = d.get("recent_events_unfiltered", [])
    if evs:
        L.append("\nRECENT EVENTS  (universe-wide, NOT filtered to this coin — reasoning must link)")
        for e in evs[:8]:
            t = time.strftime("%H:%M", time.localtime(e["seen_ms"] / 1000))
            L.append(f"  {t} {e['source']:<11}{e['title'][:76]}")

    L.append("\n(No direction is stated. This is the surface to reason over, not a call.)")
    return "\n".join(L)
