"""Catalyst Radar — rank coins by the signals that PRECEDE the +60% overnight moves.

MARKET_DYNAMICS.md §4: the big movers are idiosyncratic (low BTC-corr, high vol) and
driven by catalysts. The signals that LEAD them, in order of how tradeable:
  * attention inflection — mentions turning UP from a low base (the one leading signal)
  * funding / OI extremes — crowded one-sided positioning = squeeze fuel
  * fresh exchange notices — a new listing/notice before the crowd fully reacts
  * momentum turning up — the move starting, not already run

This scores every liquid HL coin on those, so we watch the coins *about to* move instead
of chasing after. It does NOT trade — it surfaces candidates for the pipeline to research.
A pending token unlock is flagged as a BEARISH overlay (unlock cliffs ~88% negative).
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]


def _attention() -> Dict[str, Dict[str, int]]:
    """Per-coin mentions last 24h vs prior 24h, from our social scrape."""
    out: Dict[str, Dict[str, int]] = {}
    try:
        import json, urllib.request
        uni = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.hyperliquid.xyz/info", data=json.dumps({"type": "metaAndAssetCtxs"}).encode(),
            headers={"Content-Type": "application/json"})).read())[0]["universe"]
        coins = [u["name"] for u in uni]
        conn = sqlite3.connect(f"file:{ROOT/'data'/'social.db'}?mode=ro", uri=True)
        now = time.time() * 1000
        rows = conn.execute("SELECT first_seen_ms,text FROM posts WHERE first_seen_ms>?",
                            (now - 48 * 3600000,)).fetchall()
        conn.close()
        pats = {c: re.compile(r'\b' + re.escape(c) + r'\b') for c in coins}
        for ts, txt in rows:
            t = (txt or "").upper()
            for c, p in pats.items():
                if p.search(t):
                    d = out.setdefault(c, {"cur": 0, "prev": 0})
                    d["cur" if now - ts < 24 * 3600000 else "prev"] += 1
    except Exception:
        pass
    return out


def scan(min_vol_usd: float = 5e6, top: int = 20) -> List[Dict[str, Any]]:
    """Rank liquid HL coins by catalyst score. Higher = more likely to move soon."""
    import json, urllib.request
    from hl.market import market_overview

    mkt = market_overview()
    attn = _attention()

    # fresh exchange notices (last 24h), matched to coin symbols
    notices: Dict[str, int] = {}
    try:
        e = sqlite3.connect(f"file:{ROOT/'data'/'events.db'}?mode=ro", uri=True)
        now = time.time() * 1000
        for src, title in e.execute(
                "SELECT source,title FROM events WHERE first_seen_ms>? AND kind IN "
                "('listing','announcement','delisting')", (now - 24 * 3600000,)).fetchall():
            T = (title or "").upper()
            for c in [x["coin"] for x in mkt["coins"]]:
                if re.search(r'\b' + re.escape(c) + r'\b', T):
                    notices[c] = notices.get(c, 0) + 1
        e.close()
    except Exception:
        pass

    out = []
    for r in mkt["coins"]:
        c = r["coin"]
        vol = r.get("credible_vol_usd") or 0
        if vol < min_vol_usd:
            continue
        score = 0.0
        why = []
        # attention inflection: rising FROM A LOW BASE. The signal is a coin nobody
        # watched suddenly getting watched — NOT a major that is always loud. So we
        # gate on a low prior base (already-loud majors are excluded here) and score
        # on the RATIO, not the raw delta (which just favours BTC/ETH).
        a = attn.get(c, {"cur": 0, "prev": 0})
        if a["cur"] >= 4 and a["prev"] <= 25 and a["cur"] > a["prev"]:
            ratio = a["cur"] / max(a["prev"], 1)
            lowbase = 1.6 if a["prev"] <= 3 else 1.0        # from ~zero = strongest
            score += min(ratio, 8) * 4 * lowbase
            why.append(f"attn {a['prev']}->{a['cur']} ({ratio:.0f}x)")
        # funding extreme (crowded = squeeze fuel, either side)
        fa = r.get("funding_apr")
        if fa is not None and abs(fa) > 0.30:
            score += min(abs(fa) / 0.30, 3) * 6
            why.append(f"funding {fa*100:+.0f}%")
        # fresh notice
        if notices.get(c):
            score += 25
            why.append(f"{notices[c]} fresh notice(s)")
        # momentum turning up (today's push)
        r1 = r.get("ret_1d")
        if r1 is not None and r1 > 0.05:
            score += min(r1 / 0.05, 4) * 5
            why.append(f"+{r1*100:.0f}% today")
        if score <= 0:
            continue
        # unlock overlay: a near unlock is BEARISH (~88% negative in 72h), so it is a
        # warning on a long candidate, not a plus. Flag it and dock the score.
        unlock_days = unlock_desc = unlock_tokens = unlock_pct_max = None
        try:
            from hl import unlocks
            u = unlocks.for_coin(c)
            if u and u.get("days") is not None and 0 <= u["days"] <= 21:
                unlock_days = u["days"]
                unlock_desc = u["desc"]
                unlock_tokens = u.get("tokens")
                unlock_pct_max = u.get("pct_max")
                score -= 12 if u["days"] <= 7 else 6
                size = (f" ({unlock_pct_max*100:.2f}% of max supply)"
                        if unlock_pct_max is not None else "")
                why.append(f"⚠ unlock in {u['days']:.0f}d{size}")
        except Exception:
            pass
        out.append({"coin": c, "score": round(score, 1), "why": ", ".join(why),
                    "price": r.get("price"), "ret_1d": r1, "ret_7d": r.get("ret_7d"),
                    "funding_apr": fa, "vol_usd": vol,
                    "attn_cur": a["cur"], "attn_prev": a["prev"],
                    "unlock_days": unlock_days, "unlock_desc": unlock_desc,
                    "unlock_tokens": unlock_tokens, "unlock_pct_max": unlock_pct_max})
    out.sort(key=lambda x: -x["score"])
    return out[:top]
