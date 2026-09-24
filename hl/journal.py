"""The trade journal — so every trade we make is saved WITH its reasoning, and
every trade that closes is analysed, so we actually learn and grow.

The paper engine (`hl/paper.py`) already stores each position (entry, exit, P&L,
thesis, hash). What it does NOT store is:
  1. the SIGNALS as they were at the moment of entry (funding, 7d momentum, the
     market regime) — without these a post-mortem is guessing what we saw, and
  2. the POST-MORTEM itself — did the thesis play out? why did it win/lose? what
     is the one lesson? — which is where the learning actually happens.

This module adds both, as a layer OVER the positions table (it never writes to the
money engine, only reads it), so it is safe:

  * snapshot(position_id, coin, side, thesis)  -> capture entry signals, at open.
  * record_close(position_id)                  -> at settle, pull the outcome from
        paper.db and store the FACTS of how it went (auto; lesson left for me).
  * add_lesson(position_id, lesson, setup_tag) -> the reasoning layer's post-mortem.
  * review()                                   -> aggregate what is working: win
        rate by side / setup, avg hold, best & worst, every lesson in one place.
  * pending_reviews()                          -> closed trades not yet analysed.

The FACTS are captured by code; the LESSON is written by the reasoning layer,
because only reasoning can say what a loss actually taught us. Recurring lessons
graduate into LEARNINGS_AND_RULES.md.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "journal.db"
PAPER_DB = ROOT / "data" / "paper.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
  position_id TEXT PRIMARY KEY,
  coin TEXT, side TEXT, snapshot_ms INTEGER,
  thesis TEXT, signals TEXT          -- signals = JSON snapshot at entry
);
CREATE TABLE IF NOT EXISTS reviews (
  position_id TEXT PRIMARY KEY,
  coin TEXT, side TEXT, recorded_ms INTEGER,
  entry_px REAL, exit_px REAL, pnl_usd REAL, exit_reason TEXT,
  hold_hours REAL, worked INTEGER,   -- worked = pnl>0 (mechanical)
  entry_signals TEXT, outcome TEXT,  -- outcome = JSON facts of how it moved
  lesson TEXT, setup_tag TEXT        -- filled by the reasoning layer
);
"""


def store() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _ro(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def snapshot(position_id: str, coin: str, side: str, thesis: str = "") -> None:
    """Capture the signals AS THEY ARE at entry, so the post-mortem is honest
    about what we actually saw — not reconstructed later. Safe to call twice."""
    try:
        from hl.research import packet
        pk = packet(coin)
        sig = {k: pk.get(k) for k in
               ("funding_apr", "ret_1d", "ret_7d", "ret_30d", "hl_vs_world_bps",
                "credible_vol_usd", "perp_spot_basis_bps")}
        # market regime at entry (BTC/ETH 7d), from the same daily history
        import os
        f = ROOT / "data" / "carry_cache" / "daily_365.parquet"
        if f.exists():
            import pandas as pd
            px = pd.read_parquet(f)
            for m in ("BTC", "ETH"):
                if m in px.columns:
                    s = px[m].dropna()
                    if len(s) > 8:
                        sig[f"regime_{m}_7d"] = float(s.iloc[-1] / s.iloc[-8] - 1)
        # Phase 6: stamp the REGIME LABEL and the coin's beta/correlation to BTC at
        # entry, so the journal can grade decisions BY regime, not just overall.
        try:
            from hl import regime as _rg
            sig["regime"] = _rg.read().get("regime")
        except Exception:
            pass
        try:
            from hl import preflight as _pf
            sig["corr_btc"] = _pf._corr(coin.upper(), "BTC")
        except Exception:
            pass
    except Exception as e:
        sig = {"error": str(e)}
    conn = store()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO entries (position_id,coin,side,snapshot_ms,thesis,signals) "
            "VALUES (?,?,?,?,?,?)",
            (position_id, coin.upper(), side, int(time.time() * 1000), thesis,
             json.dumps(sig)))
    conn.close()


def record_close(position_id: str) -> Optional[Dict[str, Any]]:
    """At settle: pull the closed position's outcome from paper.db and store the
    FACTS (auto). The lesson is added later by the reasoning layer. Idempotent."""
    pconn = _ro(PAPER_DB)
    p = pconn.execute("SELECT * FROM positions WHERE id=? AND status='closed'",
                      (position_id,)).fetchone()
    pconn.close()
    if not p:
        return None
    p = dict(p)
    conn = store()
    ent = conn.execute("SELECT signals FROM entries WHERE position_id=?",
                       (position_id,)).fetchone()
    entry_signals = ent["signals"] if ent else "{}"
    hold_h = ((p["closed_ms"] or 0) - p["opened_ms"]) / 3_600_000
    move = None
    if p["entry_px"] and p["exit_px"]:
        raw = p["exit_px"] / p["entry_px"] - 1
        move = raw if p["side"] == "long" else -raw   # signed in our favour
    outcome = {"price_move_our_way_pct": (move * 100 if move is not None else None),
               "exit_reason": p["exit_reason"], "hold_hours": round(hold_h, 2)}
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO reviews (position_id,coin,side,recorded_ms,entry_px,"
            "exit_px,pnl_usd,exit_reason,hold_hours,worked,entry_signals,outcome,"
            "lesson,setup_tag) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,"
            "COALESCE((SELECT lesson FROM reviews WHERE position_id=?),NULL),"
            "COALESCE((SELECT setup_tag FROM reviews WHERE position_id=?),NULL))",
            (position_id, p["coin"], p["side"], int(time.time() * 1000),
             p["entry_px"], p["exit_px"], p["pnl_usd"], p["exit_reason"],
             round(hold_h, 2), 1 if (p["pnl_usd"] or 0) > 0 else 0,
             entry_signals, json.dumps(outcome), position_id, position_id))
    conn.close()
    return {"position_id": position_id, "coin": p["coin"], "pnl_usd": p["pnl_usd"],
            "reason": p["exit_reason"]}


def add_lesson(position_id: str, lesson: str, setup_tag: str = "") -> bool:
    conn = store()
    with conn:
        n = conn.execute("UPDATE reviews SET lesson=?, setup_tag=? WHERE position_id=?",
                         (lesson, setup_tag, position_id)).rowcount
    conn.close()
    return n > 0


def pending_reviews() -> List[Dict[str, Any]]:
    """Closed trades that have a facts row but no human lesson yet."""
    if not DB.exists():
        return []
    conn = _ro(DB)
    rows = [dict(r) for r in conn.execute(
        "SELECT position_id,coin,side,pnl_usd,exit_reason,outcome FROM reviews "
        "WHERE lesson IS NULL OR lesson='' ORDER BY recorded_ms DESC")]
    conn.close()
    return rows


def review() -> Dict[str, Any]:
    """The learning view: what is actually working, and every lesson in one place."""
    if not DB.exists():
        return {"n": 0}
    conn = _ro(DB)
    rows = [dict(r) for r in conn.execute("SELECT * FROM reviews")]
    conn.close()
    if not rows:
        return {"n": 0}

    def agg(subset):
        if not subset:
            return None
        wins = sum(r["worked"] for r in subset)
        pnl = sum(r["pnl_usd"] or 0 for r in subset)
        return {"n": len(subset), "wins": wins, "win_rate": round(wins / len(subset), 2),
                "total_pnl": round(pnl, 2),
                "avg_hold_h": round(sum(r["hold_hours"] or 0 for r in subset) / len(subset), 1)}

    by_side = {s: agg([r for r in rows if r["side"] == s]) for s in ("long", "short")}
    by_side = {k: v for k, v in by_side.items() if v}
    tags = sorted({r["setup_tag"] for r in rows if r["setup_tag"]})
    by_setup = {t: agg([r for r in rows if r["setup_tag"] == t]) for t in tags}
    by_reason = {}
    for reason in sorted({r["exit_reason"] for r in rows if r["exit_reason"]}):
        by_reason[reason] = agg([r for r in rows if r["exit_reason"] == reason])
    # Phase 6: grade decisions BY the regime they were opened in (from entry_signals)
    def _regime_of(r):
        try:
            return json.loads(r.get("entry_signals") or "{}").get("regime")
        except Exception:
            return None
    regimes = sorted({_regime_of(r) for r in rows if _regime_of(r)})
    by_regime = {rg: agg([r for r in rows if _regime_of(r) == rg]) for rg in regimes}
    ranked = sorted(rows, key=lambda r: r["pnl_usd"] or 0)
    return {
        "n": len(rows), "overall": agg(rows),
        "by_side": by_side, "by_setup": by_setup, "by_exit_reason": by_reason,
        "by_regime": by_regime,
        "worst": [{"coin": r["coin"], "side": r["side"], "pnl": r["pnl_usd"],
                   "reason": r["exit_reason"], "lesson": r["lesson"]} for r in ranked[:3]],
        "best": [{"coin": r["coin"], "side": r["side"], "pnl": r["pnl_usd"],
                  "reason": r["exit_reason"], "lesson": r["lesson"]} for r in ranked[-3:]],
        "lessons": [{"coin": r["coin"], "setup_tag": r["setup_tag"], "lesson": r["lesson"]}
                    for r in rows if r["lesson"]],
    }
