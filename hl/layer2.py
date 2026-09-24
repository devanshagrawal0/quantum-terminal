"""Layer 2 — which coins BEAT the tide (the ~30% idiosyncratic).

Layer 1 (the tide) is BTC's direction — ~70% of every coin's move. Layer 2 is what's
LEFT: after you strip out the tide (the coin's residual, BTC-neutral behaviour), which
names lead and which lag. The two measurable drivers that survived our backtests are:

  relative strength  — the coin's return AFTER removing beta*BTC (tide-removed). Leaders
                       tend to keep leading over ~1-2 weeks (residual momentum, IC t+2.9).
  positioning        — funding: crowded-long (paying) names lag, offside names lead
                       (the funding-carry survivor, IC t+2.4).

Combined cross-sectionally into a −100..+100 "beat-the-tide" score, ranked across the
whole tradable set. LEADS = expected to outperform the tide; LAGS = underperform. This is
a MODEST edge (both pieces are weak individually and decay) — it ranks the field, it does
not promise a winner. The narrative + real-cash-flow half of Layer 2 is not fully
quantifiable and is left to the reasoning layer on top of this ranking.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _rank() -> List[Dict[str, Any]]:
    """Every tradable coin scored + ranked by the tide-removed beat-the-tide score."""
    from hl import signals
    u = signals._universe()
    if not u:
        return []
    raw, z = u["raw"], u["z"]
    rows: List[Dict[str, Any]] = []
    for coin in raw.index:
        zr = z.loc[coin]["resid_7"] if ("resid_7" in z.columns and coin in z.index) else None
        zf = z.loc[coin]["funding_apr"] if ("funding_apr" in z.columns and coin in z.index) else None
        if zr is None or zr != zr:
            continue
        # beat-the-tide = residual strength MINUS crowded funding (both cross-sectional z)
        score = float(zr) - 0.7 * float(zf if (zf is not None and zf == zf) else 0.0)
        r = raw.loc[coin]
        rows.append({
            "coin": coin,
            "score": round(max(-100, min(100, score * 40)), 0),   # clipped to -100..100
            "resid_7_pct": round(float(r.get("resid_7", 0) or 0) * 100, 1),
            "funding_apr_pct": round(float(r.get("funding_apr", 0) or 0) * 100, 0),
            "beta": round(float(r.get("beta_btc", 1) or 1), 2),
            "corr": round(float(r.get("corr_btc", 0) or 0), 2),
        })
    rows.sort(key=lambda x: -x["score"])
    for r in rows:
        r["verdict"] = ("LEADS" if r["score"] >= 25 else "LAGS" if r["score"] <= -25 else "tracks")
    return rows


def leaderboard(top_n: int = 8) -> Dict[str, Any]:
    """Rank the tradable set by the tide-removed 'beat-the-tide' score."""
    try:
        rows = _rank()
    except Exception as e:
        return {"error": str(e), "leaders": [], "laggards": []}
    if not rows:
        return {"error": "no universe", "leaders": [], "laggards": []}
    leaders, laggards = rows[:top_n], rows[-top_n:][::-1]
    # attach the OTHER half — real cash-flow / fundamentals — to the shown rows
    try:
        from hl import fundamentals
        for r in leaders + laggards:
            f = fundamentals.coin(r["coin"])
            r["kind"] = f.get("kind", "narrative")
            r["fees_ann_usd"] = f.get("fees_ann_usd")
            r["pf"] = f.get("pf"); r["valuation"] = f.get("valuation")
            r["unlock_overhang"] = f.get("unlock_overhang")
            r["fund_note"] = f.get("note", "")
    except Exception:
        pass
    return {"n": len(rows), "leaders": leaders, "laggards": laggards,
            "backtest": {"factor": "resid-strength + funding, tide-removed",
                         "resid_ic_t": 2.9, "funding_ic_t": 2.4, "hold_days": 10,
                         "note": "modest edge; validated long-side +0.87% BTC-neutral/pick (tracker backfill)"}}


def coin_verdict(coin: str) -> Dict[str, Any]:
    """One coin's beat-the-tide verdict, for the trade gate. Cheap after the universe
    is warm (signals._universe is cached)."""
    coin = coin.upper()
    try:
        for r in _rank():
            if r["coin"] == coin:
                return r
    except Exception as e:
        return {"coin": coin, "score": None, "verdict": None, "error": str(e)}
    return {"coin": coin, "score": None, "verdict": None}
