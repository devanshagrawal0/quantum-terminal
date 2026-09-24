"""Conditional trade triggers — the bot acts when a price condition fires.

The reasoning layer (Claude) is not always running, and Dev is not always at the
screen. So a thesis like "short ZEC when its ETF-launch rally cracks" would never
execute unless someone is watching at the exact moment. This module fixes that: it
ARMS a condition, a background loop (`scripts/trigger_loop.py`, under the watchdog)
evaluates it against the LIVE price every cycle, and when it fires it BOTH:
  1. opens the planned paper trade automatically (via `hl/paper.py`), and
  2. writes a loud ALERT row (shown on the dashboard) so it is visible after.

Nothing here is coin-specific — ZEC is just the first armed row. The kinds are
generic price conditions:
  * drop_from_peak   — fire when price falls `pct` from its trailing peak
                       (fade a topping/blow-off rally). Tracks the peak itself, so
                       it trails the top wherever the rally finally ends.
  * rise_from_trough — fire when price rises `pct` from its trailing trough
                       (catch a bottoming reversal).
  * cross_below      — fire when price <= a fixed level.
  * cross_above      — fire when price >= a fixed level.

Stop/target are stored as PERCENTAGES off the fire-time entry (not absolute
levels), because a conditional order does not know the fill price until it fires;
the absolute stop/target are computed from the live entry at the moment it fires.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "triggers.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS triggers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_ms INTEGER NOT NULL,
  coin TEXT NOT NULL,
  kind TEXT NOT NULL,            -- drop_from_peak | rise_from_trough | cross_below | cross_above
  side TEXT NOT NULL,            -- long | short (the trade to place when it fires)
  pct REAL,                      -- for drop/rise kinds: the move fraction (0.05 = 5%)
  level REAL,                    -- for cross kinds: the price level
  floor REAL,                    -- guard: peak/trough must pass this before a fire counts
  peak REAL, trough REAL,        -- running extremes since armed
  stop_pct REAL, target_pct REAL,-- off the fire-time entry (short: stop_pct>0, target_pct<0)
  hold_hours REAL, leverage REAL,
  thesis TEXT,
  status TEXT NOT NULL,          -- armed | fired | cancelled
  fired_ms INTEGER, fired_px REAL, position_id TEXT, fire_detail TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_ms INTEGER NOT NULL,
  coin TEXT, level TEXT,         -- level = INFO | FIRED | ERROR
  message TEXT
);
CREATE INDEX IF NOT EXISTS idx_trig_status ON triggers(status);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts_ms);
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


def arm(coin: str, kind: str, side: str, *, pct: Optional[float] = None,
        level: Optional[float] = None, floor: Optional[float] = None,
        stop_pct: float = 0.06, target_pct: float = -0.10,
        hold_hours: float = 48.0, leverage: float = 2.0, thesis: str = "",
        seed_px: Optional[float] = None) -> int:
    """Arm a condition. seed_px seeds the running peak/trough so a drop_from_peak
    armed at today's price fires on a drop from HERE, not from zero."""
    conn = store()
    with conn:
        cur = conn.execute(
            "INSERT INTO triggers (created_ms,coin,kind,side,pct,level,floor,peak,"
            "trough,stop_pct,target_pct,hold_hours,leverage,thesis,status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'armed')",
            (int(time.time() * 1000), coin.upper(), kind, side.lower(), pct, level,
             floor, seed_px, seed_px, stop_pct, target_pct, hold_hours, leverage,
             thesis))
        alert(conn, coin, "INFO",
              f"ARMED {kind} {side} on {coin}: "
              + (f"fire on {pct*100:.0f}% move" if pct else f"fire at {level}")
              + (f", floor {floor}" if floor else ""))
    conn.close()
    return cur.lastrowid


def alert(conn: sqlite3.Connection, coin: str, level: str, message: str) -> None:
    conn.execute("INSERT INTO alerts (ts_ms,coin,level,message) VALUES (?,?,?,?)",
                 (int(time.time() * 1000), coin.upper(), level, message))


def list_triggers(status: Optional[str] = None) -> List[Dict[str, Any]]:
    if not DB.exists():
        return []
    conn = _ro()
    q = "SELECT * FROM triggers"
    args: tuple = ()
    if status:
        q += " WHERE status=?"
        args = (status,)
    q += " ORDER BY created_ms DESC"
    rows = [dict(r) for r in conn.execute(q, args)]
    conn.close()
    return rows


def recent_alerts(limit: int = 30) -> List[Dict[str, Any]]:
    if not DB.exists():
        return []
    conn = _ro()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM alerts ORDER BY ts_ms DESC LIMIT ?", (limit,))]
    conn.close()
    return rows


def cancel(trigger_id: int) -> bool:
    conn = store()
    with conn:
        n = conn.execute("UPDATE triggers SET status='cancelled' WHERE id=? AND status='armed'",
                         (trigger_id,)).rowcount
    conn.close()
    return n > 0


def _condition_met(t: sqlite3.Row, live: float) -> bool:
    kind = t["kind"]
    if kind == "drop_from_peak":
        peak = t["peak"] or live
        if t["floor"] and peak < t["floor"]:
            return False               # rally not elevated enough yet
        return live <= peak * (1 - t["pct"])
    if kind == "rise_from_trough":
        trough = t["trough"] or live
        if t["floor"] and trough > t["floor"]:
            return False
        return live >= trough * (1 + t["pct"])
    if kind == "cross_below":
        return live <= t["level"]
    if kind == "cross_above":
        return live >= t["level"]
    return False


def evaluate(prices: Dict[str, float], paper) -> List[Dict[str, Any]]:
    """Check every armed trigger against live prices. Update running peak/trough,
    fire any whose condition is met (open the trade + alert), return what fired."""
    conn = store()
    fired: List[Dict[str, Any]] = []
    for t in conn.execute("SELECT * FROM triggers WHERE status='armed'").fetchall():
        live = prices.get(t["coin"])
        if not live:
            continue
        # track running extremes
        peak = max(t["peak"] or live, live)
        trough = min(t["trough"] or live, live)
        with conn:
            conn.execute("UPDATE triggers SET peak=?, trough=? WHERE id=?",
                         (peak, trough, t["id"]))
        t = conn.execute("SELECT * FROM triggers WHERE id=?", (t["id"],)).fetchone()
        if not _condition_met(t, live):
            continue
        # ALERT-ONLY trigger: just notify, do not open a trade (e.g. "tell me when
        # BTC hits 82k" — we already hold it, we only want the heads-up).
        if t["side"] == "alert":
            with conn:
                conn.execute("UPDATE triggers SET status='fired', fired_ms=?, fired_px=? WHERE id=?",
                             (int(time.time() * 1000), live, t["id"]))
                alert(conn, t["coin"], "FIRED",
                      f"PRICE ALERT: {t['coin']} crossed {live:.6g} "
                      f"({t['kind']} {t['level'] or ''}). {t['thesis'][:100]}")
            fired.append({"ok": True, "trigger_id": t["id"], "coin": t["coin"],
                          "side": "alert", "entry_px": live, "alert": True})
            continue
        # FIRE: compute absolute stop/target from the fire-time live entry
        side = t["side"]
        stop_px = round(live * (1 + t["stop_pct"]), 8)
        target_px = round(live * (1 + t["target_pct"]), 8)
        res = paper.open(t["coin"], side, stop_px=stop_px, target_px=target_px,
                         hold_hours=t["hold_hours"], leverage=t["leverage"],
                         thesis=(t["thesis"] or "") + f" [auto-fired {t['kind']} @ {live:.6g}]")
        with conn:
            if res.get("ok"):
                conn.execute(
                    "UPDATE triggers SET status='fired', fired_ms=?, fired_px=?, "
                    "position_id=?, fire_detail=? WHERE id=?",
                    (int(time.time() * 1000), live, res["id"],
                     json.dumps(res), t["id"]))
                alert(conn, t["coin"], "FIRED",
                      f"FIRED {t['kind']} -> opened {side.upper()} {t['coin']} @ "
                      f"{res['entry_px']:.6g} (peak {t['peak']:.6g}). "
                      f"stop {stop_px:.6g} target {target_px:.6g}. {t['thesis'][:80]}")
            else:
                # condition met but the trade was rejected (e.g. already open) —
                # do NOT keep firing; mark fired with the error so it is visible.
                conn.execute(
                    "UPDATE triggers SET status='fired', fired_ms=?, fired_px=?, "
                    "fire_detail=? WHERE id=?",
                    (int(time.time() * 1000), live, json.dumps(res), t["id"]))
                alert(conn, t["coin"], "ERROR",
                      f"condition met on {t['coin']} @ {live:.6g} but open REJECTED: "
                      f"{res.get('error')}")
        res["trigger_id"] = t["id"]
        fired.append(res)
    conn.close()
    return fired
