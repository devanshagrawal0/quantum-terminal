"""The prediction log: calls written down before the outcome exists.

This is the instrument that measures ME. Everything else in this project
measures the market; nothing until now could tell whether my reasoning is worth
anything, because reasoning that is only ever explained after the fact always
sounds good.

Four properties, each one there to stop a specific way of fooling ourselves:

  WRITTEN FIRST   entry price, direction, horizon, invalidation and the thesis
                  are stored at creation. The row carries a hash of its own
                  content, so an edited call fails verification instead of
                  quietly improving the record.

  SCORED AGAINST  every call is scored twice: raw return, and return minus the
  THE MARKET      equal-weight market over the same window. In a rising market
                  every long looks clever; the excess number is the one that
                  means anything.

  FUNDING         a 7-day long pays 168 funding charges. A call that is right
  CHARGED         about direction and loses money after carry is not right.

  RANDOM CONTROL  the same harness generates random calls on the same universe
                  over the same period. If my calls do not beat the coin-flips,
                  the reasoning is decoration. This is the check that can fail.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
  id            TEXT PRIMARY KEY,
  created_ms    INTEGER NOT NULL,
  source        TEXT NOT NULL,      -- claude | random | rule:<name>
  coin          TEXT NOT NULL,
  direction     TEXT NOT NULL,      -- long | short
  horizon_h     INTEGER NOT NULL,
  entry_px      REAL NOT NULL,      -- consolidated price AT creation
  confidence    REAL,               -- 0..1, for calibration
  size_pct      REAL,               -- intended fraction of book
  invalidation_px REAL,
  thesis        TEXT,               -- why, in words, written before the outcome
  state_json    TEXT,               -- market state at creation, for later study
  resolve_after_ms INTEGER NOT NULL,
  content_hash  TEXT NOT NULL,      -- of everything above

  resolved_ms   INTEGER,
  exit_px       REAL,
  ret_pct       REAL,               -- signed for the direction taken
  funding_pct   REAL,               -- carry paid over the hold, signed
  net_ret_pct   REAL,               -- ret minus funding
  mkt_ret_pct   REAL,               -- equal-weight market over the same window
  excess_pct    REAL,               -- net minus market. the honest score
  outcome       TEXT,               -- win | loss | flat | unresolved | bad_data
  notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_pred_due ON predictions(resolve_after_ms, resolved_ms);
CREATE INDEX IF NOT EXISTS idx_pred_src ON predictions(source, created_ms);
"""

HASHED_FIELDS = ("created_ms", "source", "coin", "direction", "horizon_h",
                 "entry_px", "confidence", "size_pct", "invalidation_px",
                 "thesis", "resolve_after_ms")


def _hash(d: Dict[str, Any]) -> str:
    payload = json.dumps({k: d.get(k) for k in HASHED_FIELDS},
                         sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


@dataclass
class Prediction:
    coin: str
    direction: str
    horizon_h: int
    entry_px: float
    source: str = "claude"
    confidence: Optional[float] = None
    size_pct: Optional[float] = None
    invalidation_px: Optional[float] = None
    thesis: str = ""
    state: Dict[str, Any] = field(default_factory=dict)
    created_ms: int = 0

    def to_row(self) -> Dict[str, Any]:
        created = self.created_ms or int(time.time() * 1000)
        if self.direction not in ("long", "short"):
            raise ValueError("direction must be long or short")
        d = {
            "created_ms": created,
            "source": self.source,
            "coin": self.coin,
            "direction": self.direction,
            "horizon_h": int(self.horizon_h),
            "entry_px": float(self.entry_px),
            "confidence": self.confidence,
            "size_pct": self.size_pct,
            "invalidation_px": self.invalidation_px,
            "thesis": self.thesis,
            "state_json": json.dumps(self.state, default=str),
            "resolve_after_ms": created + int(self.horizon_h) * 3_600_000,
        }
        d["content_hash"] = _hash(d)
        d["id"] = d["content_hash"]
        return d


class PredictionLog:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ---- writing -----------------------------------------------------------
    def add(self, p: Prediction) -> str:
        row = p.to_row()
        cols = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        with self.conn:
            self.conn.execute(f"INSERT OR IGNORE INTO predictions ({cols}) "
                              f"VALUES ({marks})", list(row.values()))
        return row["id"]

    def add_many(self, ps: List[Prediction]) -> int:
        return sum(1 for p in ps if self.add(p))

    # ---- integrity ---------------------------------------------------------
    def verify(self) -> Dict[str, Any]:
        """Recompute every hash. A mismatch means a call was edited after the
        fact, which is the one thing that would make this whole log worthless."""
        bad = []
        cur = self.conn.execute(
            "SELECT id, content_hash, " + ", ".join(HASHED_FIELDS) + " FROM predictions")
        cols = [c[0] for c in cur.description]
        n = 0
        for row in cur.fetchall():
            n += 1
            d = dict(zip(cols, row))
            if _hash(d) != d["content_hash"]:
                bad.append(d["id"])
        return {"checked": n, "tampered": bad}

    # ---- resolving ---------------------------------------------------------
    def due(self, now_ms: Optional[int] = None) -> List[sqlite3.Row]:
        now = now_ms or int(time.time() * 1000)
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(
            "SELECT * FROM predictions WHERE resolved_ms IS NULL "
            "AND resolve_after_ms <= ? ORDER BY resolve_after_ms", (now,)).fetchall()
        self.conn.row_factory = None
        return rows

    def resolve(self, pred_id: str, exit_px: float, mkt_ret_pct: Optional[float],
                funding_pct: float = 0.0, notes: str = "") -> Dict[str, Any]:
        cur = self.conn.execute(
            "SELECT direction, entry_px FROM predictions WHERE id = ?", (pred_id,))
        row = cur.fetchone()
        if not row:
            raise KeyError(pred_id)
        direction, entry = row
        if not entry or entry <= 0 or not exit_px or exit_px <= 0:
            with self.conn:
                self.conn.execute(
                    "UPDATE predictions SET resolved_ms=?, outcome='bad_data', "
                    "notes=? WHERE id=?",
                    (int(time.time() * 1000), notes or "missing price", pred_id))
            return {"outcome": "bad_data"}

        raw = (exit_px / entry - 1.0) * 100.0
        signed = raw if direction == "long" else -raw
        net = signed - funding_pct
        mkt_signed = None
        excess = None
        if mkt_ret_pct is not None:
            mkt_signed = mkt_ret_pct if direction == "long" else -mkt_ret_pct
            excess = net - mkt_signed
        score = excess if excess is not None else net
        outcome = "win" if score > 0 else ("loss" if score < 0 else "flat")
        with self.conn:
            self.conn.execute(
                "UPDATE predictions SET resolved_ms=?, exit_px=?, ret_pct=?, "
                "funding_pct=?, net_ret_pct=?, mkt_ret_pct=?, excess_pct=?, "
                "outcome=?, notes=? WHERE id=?",
                (int(time.time() * 1000), exit_px, signed, funding_pct, net,
                 mkt_signed, excess, outcome, notes, pred_id))
        return {"outcome": outcome, "net_ret_pct": net, "excess_pct": excess}

    # ---- scoring -----------------------------------------------------------
    def scoreboard(self) -> List[Dict[str, Any]]:
        """Per source, and the comparison that matters is claude vs random."""
        cur = self.conn.execute("""
            SELECT source,
                   COUNT(*) AS n,
                   SUM(resolved_ms IS NOT NULL) AS resolved,
                   AVG(CASE WHEN outcome IN ('win','loss','flat') THEN net_ret_pct END) AS avg_net,
                   AVG(CASE WHEN outcome IN ('win','loss','flat') THEN excess_pct END) AS avg_excess,
                   AVG(CASE WHEN outcome IN ('win','loss','flat') THEN (outcome='win') END) AS hit,
                   AVG(confidence) AS avg_conf
            FROM predictions GROUP BY source ORDER BY source""")
        return [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]

    def calibration(self, buckets: int = 4) -> List[Dict[str, Any]]:
        """Do calls made at 70% confidence actually win 70% of the time?"""
        cur = self.conn.execute(
            "SELECT confidence, outcome FROM predictions "
            "WHERE source='claude' AND confidence IS NOT NULL "
            "AND outcome IN ('win','loss','flat')")
        rows = cur.fetchall()
        out = []
        for b in range(buckets):
            lo, hi = b / buckets, (b + 1) / buckets
            sel = [o for c, o in rows if lo <= c < hi or (b == buckets - 1 and c == 1.0)]
            if sel:
                out.append({"bucket": f"{lo:.0%}-{hi:.0%}", "n": len(sel),
                            "actual_win_rate": sum(1 for o in sel if o == "win") / len(sel)})
        return out
