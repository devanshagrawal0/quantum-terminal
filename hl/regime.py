"""The Regime Engine — the live, computed read of what the whole market is doing.

The #1 finding of MARKET_DYNAMICS.md: regime decides the game. In a melt-up, momentum-
longs win and shorts die; in Bitcoin-season, own majors not lagging alts; in a real
risk-off, alts are not a haven. Until now that read was my gut. This makes it a NUMBER,
computed each cycle, that the pipeline gates on and the journal grades trades by.

Components (all measured, sources noted):
  * BTC dominance + ETH dominance        (CoinGecko global; the rotation stage)
  * ETH/BTC ratio and its 7d/30d trend   (our prices; the rotation "starting gun")
  * breadth: % of liquid coins green 1d/7d (our prices; risk-on/off + dip vs trend)
  * aggregate funding sign               (Hyperliquid; crowd long/short lean)
  * altseason proxy: % of top coins beating BTC over 90d  (our prices; the ASI)

Emits a single label — risk-off / bitcoin-season / early-rotation / altseason — with the
evidence, so a decision can gate on it and be graded against it later.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
_cache: Dict[str, Any] = {"t": 0.0, "data": None}


def _get(url: str, body: Optional[dict] = None, timeout: int = 10):
    headers = {"User-Agent": "Mozilla/5.0"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _dominance() -> Dict[str, Optional[float]]:
    """BTC/ETH share of total market cap, from CoinGecko global (free, no key)."""
    try:
        d = _get("https://api.coingecko.com/api/v3/global")["data"]
        mcp = d.get("market_cap_percentage", {})
        return {"btc_dom": mcp.get("btc"), "eth_dom": mcp.get("eth"),
                "total_mcap_usd": (d.get("total_market_cap") or {}).get("usd")}
    except Exception:
        return {"btc_dom": None, "eth_dom": None, "total_mcap_usd": None}


def _price_signals() -> Dict[str, Any]:
    """ETH/BTC trend, breadth, altseason proxy — all from our recorded daily closes
    plus live mids so the read is current, not yesterday's close."""
    out: Dict[str, Any] = {}
    try:
        import pandas as pd
        px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
        mids = {k: float(v) for k, v in _get(
            "https://api.hyperliquid.xyz/info", {"type": "allMids"}).items() if v}

        def live(c):
            return mids.get(c)

        def ret(c, n):
            if c in px.columns and live(c):
                s = px[c].dropna()
                if len(s) > n:
                    return live(c) / s.iloc[-n] - 1
            return None

        # ETH/BTC ratio trend — the rotation starting gun
        if live("ETH") and live("BTC"):
            ebr = live("ETH") / live("BTC")
            eb = (px["ETH"] / px["BTC"]).dropna()
            out["eth_btc"] = ebr
            out["eth_btc_7d"] = ebr / eb.iloc[-8] - 1 if len(eb) > 8 else None
            out["eth_btc_30d"] = ebr / eb.iloc[-31] - 1 if len(eb) > 31 else None

        # breadth
        cols = [c for c in px.columns if c in mids]
        r1 = [ret(c, 1) for c in cols]
        r7 = [ret(c, 7) for c in cols]
        r1 = [x for x in r1 if x is not None]
        r7 = [x for x in r7 if x is not None]
        out["n_coins"] = len(r1)
        out["breadth_1d"] = sum(1 for x in r1 if x > 0) / len(r1) if r1 else None
        out["breadth_7d"] = sum(1 for x in r7 if x > 0) / len(r7) if r7 else None

        # altseason proxy: % of liquid coins beating BTC over 90d (the ASI definition)
        b90 = ret("BTC", 90)
        if b90 is not None:
            beat = [1 for c in cols if c != "BTC" and (ret(c, 90) or -9) > b90]
            out["altseason_idx"] = round(len(beat) / max(1, len(cols) - 1) * 100)
        out["btc_1d"] = ret("BTC", 1)
        out["btc_7d"] = ret("BTC", 7)
        out["eth_7d"] = ret("ETH", 7)
    except Exception as e:
        out["error"] = str(e)
    return out


def _funding_lean() -> Dict[str, Any]:
    try:
        d = _get("https://api.hyperliquid.xyz/info", {"type": "metaAndAssetCtxs"})
        uni, ctx = d[0]["universe"], d[1]
        f = [float(c["funding"]) for u, c in zip(uni, ctx) if c.get("funding")]
        pos = sum(1 for x in f if x > 0)
        return {"funding_pos_frac": pos / len(f) if f else None, "n_funded": len(f)}
    except Exception:
        return {"funding_pos_frac": None}


def _label(dom, ps, fl) -> Dict[str, Any]:
    """Turn the components into a regime label + one-line why."""
    btc_dom = dom.get("btc_dom")
    b1 = ps.get("breadth_1d"); b7 = ps.get("breadth_7d")
    asi = ps.get("altseason_idx")
    ebr7 = ps.get("eth_btc_7d")

    # risk-off first: broad, sustained weakness
    if b7 is not None and b7 < 0.4:
        return {"regime": "risk-off",
                "why": f"only {b7*100:.0f}% of coins green over 7d — broad weakness; alts are NOT a haven here"}
    # altseason: alts broadly beating BTC + dominance low
    if asi is not None and asi >= 75 and (btc_dom is None or btc_dom < 55):
        return {"regime": "altseason",
                "why": f"altseason index {asi} + dominance {btc_dom}% — money down the risk curve; own high-beta alts"}
    # early rotation: ETH starting to outperform BTC, dominance rolling but not low yet
    if ebr7 is not None and ebr7 > 0.03 and (asi is None or asi >= 45):
        return {"regime": "early-rotation",
                "why": f"ETH/BTC +{ebr7*100:.0f}% 7d, altseason idx {asi} — rotation stepping out to ETH/large caps"}
    # default in an uptrend: bitcoin-season
    if b7 is not None and b7 >= 0.6:
        return {"regime": "bitcoin-season",
                "why": f"{b7*100:.0f}% green 7d but altseason idx {asi}, dominance {btc_dom}% — BTC/ETH lead, alts lag"}
    return {"regime": "neutral", "why": "mixed signals; no clear regime"}


def read(force: bool = False) -> Dict[str, Any]:
    """The full regime read, cached 3 min (dominance API is rate-limited)."""
    if not force and time.time() - _cache["t"] < 180 and _cache["data"]:
        return _cache["data"]
    dom = _dominance()
    ps = _price_signals()
    fl = _funding_lean()
    lab = _label(dom, ps, fl)
    out = {"ts_ms": int(time.time() * 1000), **lab,
           "btc_dom": dom.get("btc_dom"), "eth_dom": dom.get("eth_dom"),
           "total_mcap_usd": dom.get("total_mcap_usd"),
           "eth_btc": ps.get("eth_btc"), "eth_btc_7d": ps.get("eth_btc_7d"),
           "eth_btc_30d": ps.get("eth_btc_30d"),
           "breadth_1d": ps.get("breadth_1d"), "breadth_7d": ps.get("breadth_7d"),
           "altseason_idx": ps.get("altseason_idx"),
           "btc_1d": ps.get("btc_1d"), "btc_7d": ps.get("btc_7d"), "eth_7d": ps.get("eth_7d"),
           "funding_pos_frac": fl.get("funding_pos_frac"), "n_coins": ps.get("n_coins")}
    _cache["data"] = out
    _cache["t"] = time.time()
    return out


if __name__ == "__main__":
    r = read(force=True)
    print(f"REGIME: {r['regime'].upper()}")
    print(f"  why: {r['why']}")
    print(f"  BTC dominance {r['btc_dom']}%  ETH dominance {r['eth_dom']}%")
    print(f"  ETH/BTC {r['eth_btc'] and round(r['eth_btc'],5)}  (7d {r['eth_btc_7d'] and round(r['eth_btc_7d']*100,1)}%  30d {r['eth_btc_30d'] and round(r['eth_btc_30d']*100,1)}%)")
    print(f"  breadth 1d {r['breadth_1d'] and round(r['breadth_1d']*100)}%  7d {r['breadth_7d'] and round(r['breadth_7d']*100)}%")
    print(f"  altseason idx {r['altseason_idx']}  |  funding positive on {r['funding_pos_frac'] and round(r['funding_pos_frac']*100)}% of coins")
    print(f"  BTC 1d {r['btc_1d'] and round(r['btc_1d']*100,1)}%  7d {r['btc_7d'] and round(r['btc_7d']*100,1)}%")
