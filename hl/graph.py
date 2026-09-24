"""The connection map — a coin's web of cause-and-effect, Obsidian-style.

A coin does not move because of a formula. It moves because of a WEB of forces: other
coins it moves with, news and catalysts, the macro backdrop, the crowd's positioning,
what is being listed or approved. This assembles that web for any coin — every link is
either MEASURED from data or comes from real research — so we can SEE what actually drives
a coin and reason about its next move, the way a trader does.

Node types: coin (center + related coins), driver (news/catalyst, bull or bear),
macro (regime/dominance/sector), crowd (funding/positioning). Every edge has a strength
(0-1) so the strong forces stand out from the noise. The driver nodes are enriched by the
deep web research (research.db) — the more we research a coin, the richer its map.
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
_corr = {"t": 0.0, "m": None}


def _corr_matrix():
    import time as _t
    if _t.time() - _corr["t"] < 600 and _corr["m"] is not None:
        return _corr["m"]
    try:
        import pandas as pd
        px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
        _corr["m"] = px.pct_change(fill_method=None).tail(60).corr()
        _corr["t"] = _t.time()
    except Exception:
        _corr["m"] = None
    return _corr["m"]


def build(coin: str) -> Dict[str, Any]:
    coin = coin.upper()
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen = set()

    # Fetch live prices + funding ONCE (not per node), then look up from the dicts —
    # otherwise a single map fired ~14 API calls and the page hung.
    try:
        from hl.paper import live_all_mids, live_funding
        mids = live_all_mids()
        funds = live_funding()
    except Exception:
        mids, funds = {}, {}

    def _live(c):
        return mids.get(c), funds.get(c)

    def add_node(nid, ntype, label, **kw):
        if nid in seen:
            return
        seen.add(nid)
        nodes.append({"id": nid, "type": ntype, "label": label, **kw})

    price, funding = _live(coin)
    funding_apr = funding * 24 * 365 if funding is not None else None
    add_node(coin, "coin-center", coin, price=price, funding_apr=funding_apr)

    # 1) RELATED COINS — measured 60d correlation (which coins move together)
    m = _corr_matrix()
    if m is not None and coin in m.columns:
        top = m[coin].drop(coin).dropna().sort_values(ascending=False)
        for c, v in list(top.head(6).items()):
            if abs(v) < 0.4:
                continue
            p2, f2 = _live(c)
            add_node(c, "coin", c, price=p2)
            edges.append({"from": coin, "to": c, "strength": round(abs(float(v)), 2),
                          "kind": "moves-with", "dir": "pos" if v > 0 else "neg",
                          "note": f"{v:+.2f} correlation (60d)"})
        # a rare diversifier (lowest correlation) — the one that does NOT move with it
        low = top.tail(1)
        for c, v in low.items():
            if v < 0.2:
                add_node(c, "coin", c)
                edges.append({"from": coin, "to": c, "strength": 0.2, "kind": "independent",
                              "dir": "neutral", "note": f"{v:+.2f} — moves independently (diversifier)"})

    # 2) DRIVERS — from my deep-research notes (news/catalysts, bull vs bear)
    try:
        from hl.research import latest_note
        note = latest_note(coin)
        if note:
            if note.get("sector"):
                add_node("sec:" + coin, "sector", note["sector"][:40])
                edges.append({"from": "sec:" + coin, "to": coin, "strength": 0.6,
                              "kind": "sector", "dir": "neutral", "note": "sector"})
            for field, dirn, base in (("catalysts", "info", 0.7), ("bull", "pos", 0.7), ("bear", "neg", 0.7)):
                txt = (note.get(field) or "").strip()
                if txt and len(txt) > 5:
                    nid = f"{field}:{coin}"
                    add_node(nid, "driver", txt[:90], full=txt)
                    edges.append({"from": nid, "to": coin, "strength": round(base * (note.get("confidence") or 0.5) + 0.2, 2),
                                  "kind": field, "dir": dirn, "note": field})
    except Exception:
        pass

    # 3) NEWS — recent exchange notices that name the coin (last 72h)
    try:
        e = sqlite3.connect(f"file:{ROOT/'data'/'events.db'}?mode=ro", uri=True)
        now = time.time() * 1000
        rows = e.execute("SELECT source,title,first_seen_ms FROM events WHERE first_seen_ms>? "
                         "ORDER BY first_seen_ms DESC", (now - 72 * 3600000,)).fetchall()
        e.close()
        pat = re.compile(r'\b' + re.escape(coin) + r'\b')
        hits = 0
        for src, title, ts in rows:
            if title and pat.search(title.upper()) and hits < 4:
                nid = f"news:{ts}"
                add_node(nid, "news", title[:70], source=src)
                edges.append({"from": nid, "to": coin, "strength": 0.5, "kind": "notice",
                              "dir": "info", "note": src})
                hits += 1
    except Exception:
        pass

    # 4) CROWD — funding / positioning
    if funding_apr is not None and abs(funding_apr) > 0.15:
        crowded = "crowded LONG (paying to hold)" if funding_apr > 0 else "crowded SHORT (shorts paying)"
        add_node("crowd:" + coin, "crowd", f"{funding_apr*100:+.0f}%/yr — {crowded}")
        edges.append({"from": "crowd:" + coin, "to": coin, "strength": min(abs(funding_apr) / 1.0, 1),
                      "kind": "positioning", "dir": "neg" if funding_apr > 0 else "pos",
                      "note": "funding/positioning"})

    # 5) MACRO — the regime everything hangs under
    try:
        from hl import regime
        r = regime.read()
        add_node("REGIME", "macro", f"{r['regime'].replace('-',' ')} · BTC dom {r.get('btc_dom') and round(r['btc_dom'])}%",
                 detail=r.get("why"))
        edges.append({"from": "REGIME", "to": coin, "strength": 0.7, "kind": "regime",
                      "dir": "info", "note": "market regime"})
    except Exception:
        pass

    # 6) SIGNALS — the live ranked factors become weighted driver nodes, so the map
    # shows WHAT is pushing the coin right now (not just static notes). Only the
    # directional, strong ones — the map is for forces that matter, not noise.
    try:
        from hl import signals
        sg = signals.coin_signals(coin)
        strong = [s for s in sg.get("signals", []) if s.get("dir") in ("long", "short") and s.get("strength", 0) >= 0.35]
        strong.sort(key=lambda s: -s["strength"])
        for s in strong[:5]:
            nid = "sig:" + s["name"]
            add_node(nid, "signal", f"{s['name']} · {s['disp']}", full=s.get("read", ""))
            edges.append({"from": nid, "to": coin, "strength": round(min(s["strength"], 1), 2),
                          "kind": "signal", "dir": "pos" if s["dir"] == "long" else "neg",
                          "note": s["name"]})
        comp = sg.get("composite")
        if comp and comp.get("dir") in ("LONG", "AVOID"):
            if comp.get("traded"):
                lab = f"NET LONG · ~{comp['exp_move_pct']}%/{comp.get('hold_days',10)}d" + (" ✓fees" if comp.get("beats_fees") else " ✗fees")
            else:
                lab = "AVOID · short side not traded"
            add_node("COMPOSITE", "composite", lab, full=comp.get("read", ""))
            edges.append({"from": "COMPOSITE", "to": coin, "strength": 0.9, "kind": "composite",
                          "dir": "pos" if comp.get("traded") else "neg", "note": "net signal"})
    except Exception:
        pass

    # 7) CROSS-EFFECTS — how THIS coin drives others (from the deep report), so the
    # map shows outbound influence, not just what flows in. BTC's influence node is
    # the whole point of a connection map.
    try:
        from hl import intel
        rep = intel.get(coin)
        if rep:
            for ce in (rep.get("cross_effects") or [])[:5]:
                tgt = (ce.get("coin") or "").upper()
                if not tgt or tgt == coin:
                    continue
                if tgt not in seen:
                    p3, _ = _live(tgt)
                    add_node(tgt, "coin", tgt, price=p3)
                st = float(ce.get("strength") or 0.5)
                edges.append({"from": coin, "to": tgt, "strength": round(min(st, 1), 2),
                              "kind": "drives", "dir": "info", "note": ce.get("note", "")[:60],
                              "outbound": True})
            for cat in (rep.get("catalysts") or [])[:3]:
                nid = "cat:" + (cat.get("when", "") + cat.get("event", ""))[:24]
                lab = f"{cat.get('when','')} · {cat.get('event','')}"[:60]
                add_node(nid, "catalyst", lab, full=f"{cat.get('event','')} — {cat.get('impact','')}")
                edges.append({"from": nid, "to": coin, "strength": 0.55, "kind": "catalyst",
                              "dir": "pos" if cat.get("dir") == "bull" else "neg" if cat.get("dir") == "bear" else "info",
                              "note": "catalyst"})
    except Exception:
        pass

    return {"coin": coin, "nodes": nodes, "edges": edges,
            "n_nodes": len(nodes), "n_edges": len(edges)}
