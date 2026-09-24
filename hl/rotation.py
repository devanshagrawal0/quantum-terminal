"""Rotation engine — where in the risk curve the money is, and how our book should tilt.

MARKET_DYNAMICS.md §3: capital ladders BTC -> ETH -> large-cap L1s -> mid -> small ->
memes, with a lag and a strict order. The signals that mark each rung:
  * BTC dominance (high & rising = still at the BTC rung; rolling over = money leaving)
  * ETH/BTC ratio turning UP = the "starting gun" for stepping out to ETH/large caps
  * altseason index (% of coins beating BTC over 90d) = how far the rotation has spread
  * a TOTAL3 proxy (equal-weight alt index ex BTC/ETH) breaking out = small/mid running

This turns those into a STAGE (0 accumulation -> 3 broad altseason) and a concrete BOOK
TILT (majors / eth-led / balanced / alts). It is the counterpart to the manual
rotate-to-majors we did by hand: it tells us, from data, when to step down the risk
curve into alts — and when to step back up into majors.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]


def alt_index() -> Dict[str, Any]:
    """TOTAL3 proxy: equal-weight normalized index of liquid alts (ex BTC/ETH), + its
    distance from the recent high and trend. Breaking out = small/mid caps running."""
    out: Dict[str, Any] = {}
    try:
        import pandas as pd, json, urllib.request
        px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
        mids = {k: float(v) for k, v in json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.hyperliquid.xyz/info", data=json.dumps({"type": "allMids"}).encode(),
            headers={"Content-Type": "application/json"})).read()).items() if v}
        win = px.tail(120)
        alts = [c for c in win.columns if c not in ("BTC", "ETH")
                and c in mids and win[c].notna().sum() >= 115]
        norm = win[alts].apply(lambda col: col / col.dropna().iloc[0], axis=0)
        ix = norm.mean(axis=1)
        cur, hi = float(ix.iloc[-1]), float(ix.max())
        out["from_high"] = (cur / hi - 1)
        out["idx_7d"] = float(cur / ix.iloc[-8] - 1) if len(ix) > 8 else None
        out["idx_30d"] = float(cur / ix.iloc[-31] - 1) if len(ix) > 31 else None
        out["breaking_out"] = cur / hi > 0.97
        out["n_alts"] = len(alts)
    except Exception as e:
        out["error"] = str(e)
    return out


STAGES = {
    0: ("btc-accumulation", "Money in BTC; alts flat/bleeding. TILT: majors (BTC-heavy)."),
    1: ("eth-rotation", "ETH/BTC turning up — rotation stepping out to ETH/large caps. TILT: ETH + majors, prep alts, don't chase small caps yet."),
    2: ("largecap-alts", "Dominance rolling over, large alts leading. TILT: balanced — majors + large-cap alts."),
    3: ("broad-altseason", "Altseason confirmed, small/mid caps breaking out. TILT: alts (high-beta), ride the risk curve down."),
}


def stage() -> Dict[str, Any]:
    """The rotation stage + book tilt, from the regime + alt-index."""
    from hl import regime
    r = regime.read()
    ai = alt_index()
    dom = r.get("btc_dom")
    ebr7 = r.get("eth_btc_7d")
    asi = r.get("altseason_idx")
    breaking = ai.get("breaking_out")

    # decide stage (highest that qualifies)
    s = 0
    if ebr7 is not None and ebr7 > 0.02:
        s = 1                                         # ETH starting to outperform
    if (dom is not None and dom < 57) or (asi is not None and asi >= 55):
        s = 2                                         # dominance rolling / alts spreading
    if (asi is not None and asi >= 75) and breaking:
        s = 3                                         # broad altseason confirmed
    # guard: if ETH not turning up and dominance high, we're still stage 0
    if s == 1 and (ebr7 is None or ebr7 <= 0.02):
        s = 0

    name, tilt = STAGES[s]
    return {"stage": s, "name": name, "tilt": tilt,
            "regime": r.get("regime"),
            "btc_dom": dom, "eth_btc_7d": ebr7, "altseason_idx": asi,
            "alt_index_from_high": ai.get("from_high"), "alt_index_7d": ai.get("idx_7d"),
            "alt_breaking_out": breaking,
            "signal": _signal(s, r, ai)}


def _signal(s: int, r: Dict, ai: Dict) -> str:
    """One-line actionable read for our book right now."""
    ebr7 = r.get("eth_btc_7d"); asi = r.get("altseason_idx")
    if s == 0:
        return "Own majors. Alts are early — wait for ETH/BTC to turn up."
    if s == 1:
        return (f"ETH/BTC +{ebr7*100:.0f}% 7d = rotation starting, but altseason idx {asi} "
                f"not confirmed (<55). Hold majors + ETH; keep alts light until dominance rolls over.")
    if s == 2:
        return "Rotation is real — add large-cap alts (SOL/LINK-tier). Small caps still early."
    return "Broad altseason — tilt to high-beta alts; this is late-cycle, trail stops tight."
