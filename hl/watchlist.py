"""The watchlist — coins we MONITOR but do not trade, to learn from contradictions.

The lesson that keeps repeating: signals disagree. EIGEN's price rips +11% while
its news is bearish (ether.fi exited restaking). TAO pushes up while Fidelity
publishes doubt. Momentum says buy; the story says avoid. Instead of guessing which
wins and betting on it, we FLAG the contradiction here, snapshot every quant feature
at that moment, and then watch — does the price keep going (momentum won) or reverse
(the news won)? Over many of these we learn which signal actually dominates in which
regime. That is how we get "very, very aware".

Each entry stores:
  * the two sides of the contradiction (the bull case vs the bear case),
  * a full quant snapshot at flag-time (funding, 1d/7d/30d, vol, attention, basis),
  * the price when flagged — so the LIVE move since tells us which side is winning.

Nothing here places a trade. It is a pure observation log. When a contradiction
clearly resolves, we mark the winner and the lesson graduates into the journal/rules.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "watchlist.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  coin TEXT NOT NULL,
  added_ms INTEGER NOT NULL,
  added_px REAL,
  kind TEXT,                 -- contradiction | breakout-watch | catalyst-pending
  bull_side TEXT,            -- the up / momentum / quant case
  bear_side TEXT,            -- the down / news / fundamental case
  lean TEXT,                 -- which we THINK wins, or 'unsure' (honest)
  quant TEXT,                -- JSON snapshot of every feature at flag-time
  status TEXT NOT NULL,      -- watching | resolved
  resolved_ms INTEGER, winner TEXT, note TEXT
);
CREATE INDEX IF NOT EXISTS idx_wl_status ON watchlist(status);
"""


def store() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _quant_snapshot(coin: str) -> Dict[str, Any]:
    """Every feature we track, at this instant — the thing we compare price against."""
    snap: Dict[str, Any] = {}
    try:
        from hl.research import packet
        p = packet(coin)
        for k in ("funding_apr", "ret_1d", "ret_7d", "ret_30d", "hl_vs_world_bps",
                  "perp_spot_basis_bps", "credible_vol_usd", "premium_krw_bps"):
            if p.get(k) is not None:
                snap[k] = p[k]
    except Exception:
        pass
    # attention: our own social mentions last 24h vs prior 24h
    try:
        import re
        conn = sqlite3.connect(f"file:{ROOT/'data'/'social.db'}?mode=ro", uri=True)
        now = time.time() * 1000
        rows = conn.execute("SELECT first_seen_ms,text FROM posts WHERE first_seen_ms>?",
                            (now - 48 * 3600000,)).fetchall()
        conn.close()
        cur = prev = 0
        pat = re.compile(r'\b' + re.escape(coin.upper()) + r'\b')
        for ts, txt in rows:
            if pat.search((txt or '').upper()):
                if now - ts < 24 * 3600000:
                    cur += 1
                else:
                    prev += 1
        snap["attn_24h"] = cur
        snap["attn_prev"] = prev
    except Exception:
        pass
    return snap


def live_px(coin: str) -> Optional[float]:
    try:
        from hl.paper import live_all_mids
        return live_all_mids().get(coin.upper())
    except Exception:
        return None


def add(coin: str, bull_side: str, bear_side: str, lean: str = "unsure",
        kind: str = "contradiction", note: str = "") -> int:
    coin = coin.upper()
    px = live_px(coin)
    snap = _quant_snapshot(coin)
    conn = store()
    with conn:
        cur = conn.execute(
            "INSERT INTO watchlist (coin,added_ms,added_px,kind,bull_side,bear_side,"
            "lean,quant,status,note) VALUES (?,?,?,?,?,?,?,?,'watching',?)",
            (coin, int(time.time() * 1000), px, kind, bull_side, bear_side, lean,
             json.dumps(snap), note))
    conn.close()
    return cur.lastrowid


def resolve(entry_id: int, winner: str, note: str = "") -> bool:
    conn = store()
    with conn:
        n = conn.execute(
            "UPDATE watchlist SET status='resolved', resolved_ms=?, winner=?, note=? "
            "WHERE id=? AND status='watching'",
            (int(time.time() * 1000), winner, note, entry_id)).rowcount
    conn.close()
    return n > 0


def remove(entry_id: int) -> bool:
    conn = store()
    with conn:
        n = conn.execute("DELETE FROM watchlist WHERE id=?", (entry_id,)).rowcount
    conn.close()
    return n > 0


def list_all(include_resolved: bool = True) -> List[Dict[str, Any]]:
    """Every watchlist entry, with the LIVE move since flagged so we can see which
    side is winning right now (momentum vs the news)."""
    if not DB.exists():
        return []
    conn = _ro()
    q = "SELECT * FROM watchlist"
    if not include_resolved:
        q += " WHERE status='watching'"
    q += " ORDER BY added_ms DESC"
    rows = [dict(r) for r in conn.execute(q)]
    conn.close()
    from hl.paper import live_all_mids
    mids = live_all_mids()
    for r in rows:
        r["quant"] = json.loads(r["quant"] or "{}")
        live = mids.get(r["coin"])
        r["live_px"] = live
        if live and r["added_px"]:
            r["move_pct"] = (live / r["added_px"] - 1) * 100
            r["age_hours"] = (time.time() * 1000 - r["added_ms"]) / 3_600_000
        else:
            r["move_pct"] = None
            r["age_hours"] = (time.time() * 1000 - r["added_ms"]) / 3_600_000
    return rows
