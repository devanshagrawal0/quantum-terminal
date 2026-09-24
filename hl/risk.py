"""Risk monitors — early warning for a BTC top and for a contagion / risk-off flip.

MARKET_DYNAMICS.md §1 and §2 named the two risks we had no alarm for:
  1. the BREAKING POINT — BTC tops when the fuel runs out: OI climbing (or price
     rising on falling OI = deleveraging) while funding is rich and RSI makes
     lower-highs at resistance. No single one is a signal; the CONFLUENCE is.
  2. the CRASH / CONTAGION flip — in a real risk-off, breadth collapses, cross-coin
     correlation spikes toward 1, and high-beta alts fall hardest. Alts are NOT a
     haven then. We measured only bull-regime numbers, so we must WATCH for the flip.

This module computes both as 0-100 scores from real data (our recorder + live HL),
with the components spelled out so a score can never silently "always pass". The
trigger loop evaluates them each cycle and alerts when either is elevated.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
VENUES = ROOT / "data" / "venues.db"


def _ro():
    c = sqlite3.connect(f"file:{VENUES}?mode=ro", uri=True)
    return c


def rsi(coin: str, period: int = 14) -> Optional[float]:
    """Wilder RSI from daily closes + the live mid as today's point."""
    try:
        import pandas as pd
        from hl.paper import live_all_mids
        px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
        if coin not in px.columns:
            return None
        s = px[coin].dropna().tail(period * 4).tolist()
        live = live_all_mids().get(coin)
        if live:
            s = s + [live]
        if len(s) < period + 1:
            return None
        gains, losses = [], []
        for i in range(1, len(s)):
            d = s[i] - s[i - 1]
            gains.append(max(d, 0)); losses.append(max(-d, 0))
        ag = sum(gains[:period]) / period
        al = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            ag = (ag * (period - 1) + gains[i]) / period
            al = (al * (period - 1) + losses[i]) / period
        if al == 0:
            return 100.0
        rs = ag / al
        return 100 - 100 / (1 + rs)
    except Exception:
        return None


def _oi_price_24h(coin: str) -> Dict[str, Optional[float]]:
    """OI and price change over ~24h — the deleveraging tell."""
    try:
        c = _ro()
        now = time.time() * 1000
        cur = c.execute("SELECT mid,oi_base FROM hl_state WHERE coin=? ORDER BY ts_ms DESC LIMIT 1",
                        (coin,)).fetchone()
        old = c.execute("SELECT mid,oi_base FROM hl_state WHERE coin=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1",
                        (coin, now - 24 * 3600000)).fetchone()
        c.close()
        if not cur or not old or not old[0] or not old[1]:
            return {"px_24h": None, "oi_24h": None}
        return {"px_24h": cur[0] / old[0] - 1, "oi_24h": cur[1] / old[1] - 1}
    except Exception:
        return {"px_24h": None, "oi_24h": None}


def _funding_apr(coin: str) -> Optional[float]:
    try:
        import json, urllib.request
        d = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.hyperliquid.xyz/info",
            data=json.dumps({"type": "metaAndAssetCtxs"}).encode(),
            headers={"Content-Type": "application/json"})).read())
        for u, cx in zip(d[0]["universe"], d[1]):
            if u["name"] == coin and cx.get("funding"):
                return float(cx["funding"]) * 24 * 365
    except Exception:
        pass
    return None


def breaking_point(coin: str = "BTC") -> Dict[str, Any]:
    """0-100 topping-risk score. Higher = more fragile. Confluence, not any single one."""
    r = rsi(coin)
    op = _oi_price_24h(coin)
    fa = _funding_apr(coin)
    comp = {}
    score = 0.0

    # RSI exhaustion: 70->30pts ramps to 86 (per research 82-86 = high pullback odds)
    if r is not None:
        comp["rsi"] = round(r, 1)
        if r >= 70:
            score += min((r - 70) / 16, 1) * 35     # up to 35 at RSI 86
    # deleveraging into strength: price up while OI down
    if op["px_24h"] is not None and op["oi_24h"] is not None:
        comp["px_24h"] = round(op["px_24h"] * 100, 1)
        comp["oi_24h"] = round(op["oi_24h"] * 100, 1)
        if op["px_24h"] > 0.01 and op["oi_24h"] < 0:
            score += min(abs(op["oi_24h"]) / 0.05, 1) * 25    # up to 25 at -5% OI
        # OR leverage building without price: OI up a lot, price flat/down
        elif op["oi_24h"] > 0.05 and op["px_24h"] < 0.005:
            score += min(op["oi_24h"] / 0.15, 1) * 20
    # funding richness: crowded longs paying dearly
    if fa is not None:
        comp["funding_apr"] = round(fa * 100)
        if fa > 0.20:
            score += min((fa - 0.20) / 0.80, 1) * 30    # up to 30 at +100% APR
    score = round(min(score, 100), 1)
    level = "elevated" if score >= 55 else ("watch" if score >= 35 else "calm")
    return {"coin": coin, "score": score, "level": level, "components": comp}


def crash_signal() -> Dict[str, Any]:
    """0-100 risk-off / contagion score. Breadth collapse + majors falling + correlation
    spiking = the flip where alts stop being independent and fall together."""
    score = 0.0
    comp = {}
    try:
        import pandas as pd, numpy as np, json, urllib.request
        mids = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.hyperliquid.xyz/info", data=json.dumps({"type": "allMids"}).encode(),
            headers={"Content-Type": "application/json"})).read())
        mids = {k: float(v) for k, v in mids.items() if v}
        px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
        cols = [c for c in px.columns if c in mids]

        def ret(c, n):
            s = px[c].dropna()
            return mids[c] / s.iloc[-n] - 1 if len(s) > n and mids.get(c) else None

        # breadth 1d
        r1 = [ret(c, 1) for c in cols]; r1 = [x for x in r1 if x is not None]
        breadth = sum(1 for x in r1 if x > 0) / len(r1) if r1 else None
        comp["breadth_1d"] = round(breadth * 100) if breadth is not None else None
        if breadth is not None and breadth < 0.35:
            score += (0.35 - breadth) / 0.35 * 40     # up to 40 as breadth -> 0

        # majors falling (BTC/ETH/SOL 1d)
        maj = [ret(c, 1) for c in ("BTC", "ETH", "SOL")]
        maj = [x for x in maj if x is not None]
        avg_maj = sum(maj) / len(maj) if maj else 0
        comp["majors_1d"] = round(avg_maj * 100, 1)
        if avg_maj < -0.02:
            score += min(abs(avg_maj) / 0.08, 1) * 35   # up to 35 at majors -8%

        # correlation spike: recent 10d alt<->BTC correlation vs the 90d baseline
        ret10 = px[cols].pct_change(fill_method=None).tail(10)
        ret90 = px[cols].pct_change(fill_method=None).tail(90)
        b10, b90 = ret10["BTC"], ret90["BTC"]
        c10 = np.nanmean([ret10[c].corr(b10) for c in cols if c != "BTC"])
        c90 = np.nanmean([ret90[c].corr(b90) for c in cols if c != "BTC"])
        comp["corr_10d"] = round(float(c10), 2)
        comp["corr_90d"] = round(float(c90), 2)
        if c10 > c90 + 0.15 and c10 > 0.6:
            score += 25    # correlation spiking toward 1 = contagion
    except Exception as e:
        comp["error"] = str(e)
    score = round(min(score, 100), 1)
    level = "risk-off" if score >= 55 else ("caution" if score >= 30 else "calm")
    return {"score": score, "level": level, "components": comp}


def summary() -> Dict[str, Any]:
    """Both monitors, for the dashboard + the trigger loop."""
    return {"breaking_point": breaking_point("BTC"), "crash": crash_signal()}
