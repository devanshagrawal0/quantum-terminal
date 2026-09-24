"""Gated-vs-ungated forward experiment — does the gate actually pay?

The whole foundation (tide → beat-the-tide → fundamentals) is enforced at the trade
gate, but all of it is in-sample. This is the honest out-of-sample judge: every day it
records, for EVERY tradable coin, whether the gate would ALLOW a long (tide not risk-off,
not a Layer-2 laggard, not overpaying) or BLOCK it — with the coin's entry price and
BTC's price hashed in. After the 10-day hold it grades each pick's BTC-NEUTRAL return
(coin move minus beta*BTC move). Then: do the ALLOWED coins outperform the BLOCKED coins?
If yes, the gate is smart; if not, we're filtering out winners.

It can only run forward — the gate uses live tide/Layer-2/fundamentals with no history to
backfill — so it starts empty and the first verdict lands ~10 days after the first
snapshot. Wall-clock maturity (grade when 10 real days have passed), prices fetched live.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "gate_exp.db"
HOLD_DAYS = 10
FEE = 0.0020

SCHEMA = """
CREATE TABLE IF NOT EXISTS gate_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_ms INTEGER, as_of TEXT, coin TEXT,
  allowed INTEGER, block_reason TEXT,
  entry_px REAL, btc_entry REAL, beta REAL,
  matured INTEGER DEFAULT 0, exit_px REAL, btc_exit REAL, resid_ret REAL,
  plan_hash TEXT, UNIQUE(as_of, coin)
);
CREATE TABLE IF NOT EXISTS gate_runs (ts_ms INTEGER PRIMARY KEY, note TEXT);
"""


def _conn():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; c.executescript(SCHEMA)
    return c


def _iso(ts):
    import datetime as dt
    return dt.datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")


def snapshot() -> Dict[str, int]:
    """Record today's gate verdict for every coin (empty book so only the coin-quality
    gates fire: tide, Layer-2, fundamentals)."""
    from hl import signals, preflight
    from hl.paper import live_all_mids, betas_to_btc
    u = signals._universe()
    if not u:
        return {"error": 1}
    mids = live_all_mids()
    btc = mids.get("BTC")
    betas = betas_to_btc()
    now = int(time.time() * 1000)
    iso = _iso(now)
    conn = _conn()
    allowed = blocked = 0
    with conn:
        for coin in u["raw"].index:
            entry = mids.get(coin)
            if not entry or not btc:
                continue
            try:
                pf = preflight.check(coin, "long", [])
            except Exception:
                continue
            ok = not pf["blocked"]
            reason = "" if ok else "; ".join(v["msg"][:80] for v in pf["violations"] if v["level"] == "block")
            beta = float(betas.get(coin, 1.0))
            h = hashlib.sha256(f"{iso}|{coin}|{ok}|{entry:.6g}".encode()).hexdigest()[:16]
            cur = conn.execute(
                "INSERT OR IGNORE INTO gate_log(ts_ms,as_of,coin,allowed,block_reason,entry_px,btc_entry,beta,plan_hash) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (now, iso, coin, 1 if ok else 0, reason, float(entry), float(btc), beta, h))
            if cur.rowcount:
                allowed += ok; blocked += (not ok)
        conn.execute("INSERT OR REPLACE INTO gate_runs VALUES(?,?)", (now, f"allowed={allowed} blocked={blocked}"))
    conn.close()
    return {"as_of": iso, "allowed": allowed, "blocked": blocked}


def grade() -> int:
    """Mature any pick past its 10-day hold using LIVE prices; score BTC-neutral."""
    from hl.paper import live_all_mids
    conn = _conn()
    rows = conn.execute("SELECT * FROM gate_log WHERE matured=0").fetchall()
    if not rows:
        conn.close(); return 0
    mids = live_all_mids()
    btc_now = mids.get("BTC")
    now = time.time() * 1000
    graded = 0
    with conn:
        for r in rows:
            if now - r["ts_ms"] < HOLD_DAYS * 86400_000:
                continue
            px = mids.get(r["coin"])
            if not (px and btc_now and r["entry_px"] and r["btc_entry"]):
                continue
            coin_ret = px / r["entry_px"] - 1.0
            btc_ret = btc_now / r["btc_entry"] - 1.0
            resid = coin_ret - (r["beta"] or 1.0) * btc_ret
            conn.execute("UPDATE gate_log SET matured=1,exit_px=?,btc_exit=?,resid_ret=? WHERE id=?",
                         (float(px), float(btc_now), float(resid), r["id"]))
            graded += 1
    conn.close()
    return graded


def scorecard() -> Dict[str, Any]:
    """ALLOWED vs BLOCKED forward BTC-neutral return — the gate's out-of-sample edge."""
    if not DB.exists():
        return {"allowed": {}, "blocked": {}, "open": 0}
    conn = _conn()

    def agg(allowed):
        rows = conn.execute("SELECT resid_ret FROM gate_log WHERE matured=1 AND allowed=?",
                            (allowed,)).fetchall()
        if not rows:
            return {"n": 0}
        r = [x["resid_ret"] for x in rows]
        return {"n": len(r), "avg_pct": round(sum(r) / len(r) * 100, 2),
                "win": round(sum(1 for x in r if x > 0) / len(r), 2)}

    a, b = agg(1), agg(0)
    open_n = conn.execute("SELECT COUNT(*) FROM gate_log WHERE matured=0").fetchone()[0]
    days = conn.execute("SELECT COUNT(DISTINCT as_of) FROM gate_log").fetchone()[0]
    last = conn.execute("SELECT COUNT(*) FROM gate_log WHERE allowed=1"), conn.execute("SELECT COUNT(*) FROM gate_log WHERE allowed=0")
    n_allowed = conn.execute("SELECT COUNT(*) FROM gate_log WHERE allowed=1").fetchone()[0]
    n_blocked = conn.execute("SELECT COUNT(*) FROM gate_log WHERE allowed=0").fetchone()[0]
    conn.close()
    out = {"allowed": a, "blocked": b, "open": open_n, "days_logged": days,
           "hold_days": HOLD_DAYS, "n_allowed": n_allowed, "n_blocked": n_blocked}
    if a.get("avg_pct") is not None and b.get("avg_pct") is not None:
        out["gate_edge_pct"] = round(a["avg_pct"] - b["avg_pct"], 2)
        out["gate_works"] = out["gate_edge_pct"] > 0
    return out
