"""Layer 2, the OTHER half — real cash-flow, the only true 'base' crypto has.

The quant half of Layer 2 (relative strength + positioning) is pure price. This is the
FUNDAMENTAL half: which coins are backed by an actual business throwing off fees, and
which are pure narrative/positioning with no cash flow at all. Data is real and free:
DefiLlama protocol fees (2,600+ protocols). For a coin that maps to a protocol we sum
its 30-day fees, annualize them, and read the trend (growing/shrinking). A coin with no
protocol = no on-chain revenue = it lives or dies on story + positioning only.

This is the closest crypto gets to earnings. The mapping is a factual coin->protocol join
(like a ticker), NOT keyword intelligence — and it is honest about its own coverage: only
coins with a real on-chain business appear; everything else is flagged 'narrative-only'.
"""
from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Dict, List

# coin -> DefiLlama protocol name(s) to SUM (matched case-insensitive substring).
# Only revenue-bearing tokens in our tradable set; anything absent = narrative-only.
MAP: Dict[str, List[str]] = {
    "HYPE": ["Hyperliquid Perps", "Hyperliquid Spot", "Hyperliquid HLP"],
    "PUMP": ["pump.fun", "PumpSwap"],
    "AAVE": ["Aave V3", "Aave V2"],
    "UNI": ["Uniswap V3", "Uniswap V4", "Uniswap V2", "Uniswap Labs"],
    "ENA": ["Ethena USDe"],
    "JUP": ["Jupiter Perpetual", "Jupiter Aggregator", "Jupiter DCA"],
    "CRV": ["Curve DEX", "Curve LlamaLend"],
    "CAKE": ["PancakeSwap AMM"],
    "LDO": ["Lido"],
    "JTO": ["Jito Liquid Sta"],
    "RAY": ["Raydium AMM"],
    "GMX": ["GMX V2 Perps", "GMX V1 Perps"],
    "DYDX": ["dYdX V4"],
    "PENDLE": ["Pendle"],
    "MKR": ["MakerDAO", "Sky"], "SKY": ["Sky", "MakerDAO"],
    "AERO": ["Aerodrome"], "DRIFT": ["Drift"], "ETHFI": ["ether.fi"],
    "MORPHO": ["Morpho"], "PErp": ["Perpetual Protocol"],
}

# L1 / base-layer tokens: they DO have a base (chain gas fees + staking yield + monetary
# premium) — it's just chain-level, not in the protocol-fee feed. So they are NOT
# 'narrative-only'; flagged separately so ETH/SOL aren't mislabeled as memes.
L1S = {"ETH", "SOL", "BNB", "AVAX", "ADA", "DOT", "NEAR", "APT", "SUI", "TRX", "ATOM",
       "TON", "SEI", "INJ", "TIA", "ICP", "ALGO", "XTZ", "KAS", "FTM", "S"}

# coin -> CoinGecko id, for market cap (the price half of price-to-fees).
CG_ID: Dict[str, str] = {
    "HYPE": "hyperliquid", "PUMP": "pump-fun", "AAVE": "aave", "UNI": "uniswap",
    "ENA": "ethena", "JUP": "jupiter-exchange-solana", "CRV": "curve-dao-token",
    "CAKE": "pancakeswap-token", "LDO": "lido-dao", "JTO": "jito-governance-token",
    "RAY": "raydium", "GMX": "gmx", "DYDX": "dydx-chain", "PENDLE": "pendle",
    "MKR": "maker", "SKY": "sky", "AERO": "aerodrome-finance", "DRIFT": "drift-protocol",
    "ETHFI": "ether-fi", "MORPHO": "morpho",
}

_cache: Dict[str, Any] = {"t": 0.0, "protos": None}
_mc: Dict[str, Any] = {"t": 0.0, "data": None}


def _mcaps():
    """market cap + FDV for all mapped coins, one CoinGecko call, cached 1h."""
    if time.time() - _mc["t"] < 3600 and _mc["data"] is not None:
        return _mc["data"]
    try:
        ids = ",".join(sorted(set(CG_ID.values())))
        d = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=" + ids,
            headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
        _mc["data"] = {c["id"]: {"mcap": c.get("market_cap"), "fdv": c.get("fully_diluted_valuation")}
                       for c in d}
        _mc["t"] = time.time()
    except Exception:
        _mc["data"] = _mc["data"] or {}
    return _mc["data"]


def _valuation(pf):
    if pf is None:
        return None
    return "cheap" if pf < 5 else "fair" if pf < 15 else "rich" if pf < 40 else "expensive"


def _fees():
    if time.time() - _cache["t"] < 3600 and _cache["protos"] is not None:
        return _cache["protos"]
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true",
            headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
        _cache["protos"] = d.get("protocols", [])
        _cache["t"] = time.time()
    except Exception:
        _cache["protos"] = _cache["protos"] or []
    return _cache["protos"]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def coin(sym: str) -> Dict[str, Any]:
    """Fundamentals read for one coin."""
    sym = sym.upper()
    names = MAP.get(sym)
    if not names:
        if sym in L1S:
            return {"coin": sym, "has_revenue": True, "kind": "L1",
                    "note": "L1 base: chain gas fees + staking yield (real, not in protocol-fee feed)"}
        return {"coin": sym, "has_revenue": False, "kind": "narrative",
                "note": "no on-chain revenue — narrative/positioning only"}
    protos = _fees()
    lname = [n.lower() for n in names]
    d30 = d30_prior = d7 = 0.0
    hit = []
    for p in protos:
        nm = (p.get("name") or "").lower()
        if any(l in nm for l in lname):
            v30 = _num(p.get("total30d")); vp = _num(p.get("total60dto30d")); v7 = _num(p.get("total7d"))
            if v30:
                d30 += v30; hit.append(p.get("name"))
            if vp:
                d30_prior += vp
            if v7:
                d7 += v7
    if d30 <= 0:
        return {"coin": sym, "has_revenue": False, "note": "protocol matched but no fee data"}
    ann = d30 / 30 * 365
    growth = (d30 / d30_prior - 1) * 100 if d30_prior > 0 else None
    # run-rate check: is the last 7d pace above/below the 30d pace?
    pace = (d7 / 7) / (d30 / 30) - 1 if d30 > 0 else None
    tier = "large" if ann > 50e6 else "mid" if ann > 5e6 else "small"
    # price-to-fees = market cap / annualized fees (crypto's closest thing to a P/E)
    mc = _mcaps().get(CG_ID.get(sym, ""), {}) if sym in CG_ID else {}
    mcap, fdv = mc.get("mcap"), mc.get("fdv")
    pf = round(mcap / ann, 1) if (mcap and ann) else None
    pf_fdv = round(fdv / ann, 1) if (fdv and ann) else None
    val = _valuation(pf)
    unlock_overhang = (pf_fdv and pf and pf_fdv > pf * 2)   # FDV >> mcap = big supply to come
    vnote = ""
    if pf is not None:
        vnote = f" · P/F {pf}x ({val})" + (f", but {pf_fdv}x fully-diluted (unlock overhang)" if unlock_overhang else "")
    return {"coin": sym, "has_revenue": True, "kind": "protocol", "fees_ann_usd": round(ann),
            "fees_30d_usd": round(d30), "growth_30d_pct": round(growth, 0) if growth is not None else None,
            "pace_7v30_pct": round(pace * 100, 0) if pace is not None else None,
            "tier": tier, "protocols": hit, "mcap_usd": mcap, "fdv_usd": fdv,
            "pf": pf, "pf_fdv": pf_fdv, "valuation": val, "unlock_overhang": bool(unlock_overhang),
            "note": f"${ann/1e6:.0f}M/yr fees, " + (
                (f"growing {growth:+.0f}% vs prior 30d" if growth is not None else "trend n/a")) + vnote}


def all_coins(coins: List[str]) -> Dict[str, Dict[str, Any]]:
    return {c: coin(c) for c in coins}
