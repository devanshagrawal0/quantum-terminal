"""Layer 1 — the crypto risk-on / risk-off regime read (the ~70% 'tide').

Crypto has no valuation anchor; ~70% of all coin movement is one common risk/liquidity
factor. This reads that tide from BTC's own tape — the most robust, least-overfittable
inputs: where price sits vs its 200-day trend, whether that trend is rising, the
volatility regime, and the drawdown from the high. Combined into one −100..+100 score
and a RISK-ON / NEUTRAL / RISK-OFF label.

Nothing here is trusted until validated: `scripts/regime_layer1.py` proves that risk-on
days actually precede higher forward returns and risk-off days precede the drawdowns,
point-in-time, over 9 years, both halves. This module just computes the read.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _components(px: pd.Series) -> pd.DataFrame:
    """Point-in-time regime components for every day (everything uses only past data)."""
    px = px.sort_index()
    ma50 = px.rolling(50).mean()
    ma200 = px.rolling(200).mean()
    ret = np.log(px).diff()
    vol20 = ret.rolling(20).std() * np.sqrt(365)
    vol_pct = vol20.rolling(365, min_periods=120).apply(
        lambda w: (w[:-1] < w[-1]).mean(), raw=True)      # today's vol percentile vs trailing yr
    dd = px / px.rolling(252, min_periods=60).max() - 1.0
    df = pd.DataFrame({
        # trend: how far above/below the 200d, capped at +/-1 (each ~20% = full)
        "trend200": ((px / ma200 - 1.0) / 0.20).clip(-1, 1),
        "trend50": ((px / ma50 - 1.0) / 0.12).clip(-1, 1),
        "slope200": np.sign(ma200 - ma200.shift(20)),      # is the long trend rising
        "vol": (0.5 - vol_pct) * 2.0,                      # low vol -> +1 (risk-on), high vol -> -1
        "drawdown": (dd / 0.25).clip(-1, 1),               # -25% dd -> -1
    })
    return df


def score_series(px: pd.Series) -> pd.DataFrame:
    """Return components + composite score (−100..+100) + label, per day."""
    c = _components(px)
    w = {"trend200": 0.35, "slope200": 0.20, "trend50": 0.15, "vol": 0.15, "drawdown": 0.15}
    comp = sum(c[k] * v for k, v in w.items())
    out = c.copy()
    out["score"] = (comp * 100).round(0)
    out["label"] = np.where(out["score"] >= 25, "RISK-ON",
                     np.where(out["score"] <= -25, "RISK-OFF", "NEUTRAL"))
    return out


def _load_btc() -> Optional[pd.Series]:
    f = ROOT / "data" / "carry_cache" / "seasonality_BTCUSDT.parquet"
    if f.exists():
        return pd.read_parquet(f)["close"].sort_index()
    try:
        from scripts.seasonality import fetch
        return fetch("BTCUSDT").sort_index()
    except Exception:
        return None


def read() -> Dict[str, Any]:
    """The CURRENT regime read for the dashboard."""
    px = _load_btc()
    if px is None or len(px) < 260:
        return {"label": "UNKNOWN", "score": None}
    s = score_series(px).dropna()
    if not len(s):
        return {"label": "UNKNOWN", "score": None}
    last = s.iloc[-1]
    comps = {k: round(float(last[k]), 2) for k in ("trend200", "trend50", "slope200", "vol", "drawdown")}
    return {"label": last["label"], "score": int(last["score"]),
            "as_of": str(s.index[-1].date()), "btc": float(px.iloc[-1]),
            "components": comps,
            "read": {
                "trend200": "above 200d" if comps["trend200"] > 0 else "below 200d",
                "slope200": "trend rising" if comps["slope200"] > 0 else "trend falling",
                "vol": "calm" if comps["vol"] > 0.2 else "stressed" if comps["vol"] < -0.2 else "normal",
                "drawdown": "near highs" if comps["drawdown"] > -0.3 else "deep drawdown",
            }}
