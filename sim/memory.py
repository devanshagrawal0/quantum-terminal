"""The learning engine (v2). See docs/LEARNING_ENGINE_V2.md for the reasoning.

Four stores in one SQLite file, all time-locked (a row is visible at simulation time
t only if it was written at or before t):

  experience   one row per CLOSED trade: the numbers it was taken on (feature
               vector), regime, setup, side, thesis + stated confidence, and the full
               grade: net, EXCESS over the universe, best/worst point reached, the
               counterfactual stop/target plans, exit reason, and a lesson text.
  insight      a rule with a lifecycle (ExpeL): proposed -> active -> retired.
               importance rises with agreeing outcomes, falls with disagreeing ones,
               removed at zero. Activation needs OUT-OF-SAMPLE support: outcomes that
               closed after the insight was written.
  evidence     computed on demand, never stored: for a (setup, regime) the DECAYED
               count / mean / spread of excess results, and a Thompson SAMPLE from
               the belief - the thing that keeps every door open.
  similar      computed on demand: the k nearest past situations to a feature
               vector, and what happened to them.

The oracle fallacy is impossible by construction: an experience's text and numbers
are all computed at its close time from the path up to that close.
"""
from __future__ import annotations

import json
import math
import random
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DAY_MS = 86_400_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS experience (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT,
  opened_ts INTEGER NOT NULL, closed_ts INTEGER NOT NULL,
  coin TEXT, side TEXT, setup TEXT, regime TEXT, probation INTEGER DEFAULT 0,
  features TEXT, thesis TEXT, confidence REAL,
  net_bps REAL, excess_bps REAL, mfe_bps REAL, mae_bps REAL,
  exit_reason TEXT, days_held INTEGER, counterfactuals TEXT, lesson TEXT
);
CREATE INDEX IF NOT EXISTS ix_exp_agent_closed ON experience(agent, closed_ts);
CREATE VIRTUAL TABLE IF NOT EXISTS experience_fts USING fts5(
  setup, regime, thesis, lesson, content='experience', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS experience_ai AFTER INSERT ON experience BEGIN
  INSERT INTO experience_fts(rowid, setup, regime, thesis, lesson)
  VALUES (new.id, new.setup, new.regime, new.thesis, new.lesson);
END;
CREATE TABLE IF NOT EXISTS note (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, ts INTEGER NOT NULL,
  kind TEXT NOT NULL, text TEXT NOT NULL, tags TEXT
);
CREATE TABLE IF NOT EXISTS insight (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT,
  created_ts INTEGER NOT NULL, updated_ts INTEGER NOT NULL,
  setup TEXT, regime TEXT, text TEXT NOT NULL, source TEXT,
  importance INTEGER DEFAULT 2, support_n INTEGER DEFAULT 0, oos_n INTEGER DEFAULT 0,
  oos_mean_excess REAL, status TEXT DEFAULT 'proposed'
);
"""


class Memory:
    def __init__(self, path: Path, agent: str, run_id: str = "",
                 half_life_days: float = 90.0, prior_n: float = 4.0, seed: int = 0):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.executescript(SCHEMA)
        self.agent, self.run_id = agent, run_id
        self.half_life, self.prior_n = half_life_days, prior_n
        self.rng = random.Random(seed)
        self._feat_cache = None      # (closed_ts array, matrix, meta) for similarity

    # ------------------------------------------------------------- writing
    def learn(self, *, closed_ts: int, opened_ts: int, coin: str, side: str, setup: str,
              regime: str, features: Dict[str, float], thesis: str, confidence: Optional[float],
              net_bps: float, excess_bps: float, mfe_bps: float, mae_bps: float,
              exit_reason: str, days_held: int, counterfactuals: str, lesson: str,
              probation: bool = False) -> int:
        cur = self.conn.execute(
            "INSERT INTO experience(agent,run_id,opened_ts,closed_ts,coin,side,setup,regime,probation,"
            "features,thesis,confidence,net_bps,excess_bps,mfe_bps,mae_bps,exit_reason,days_held,"
            "counterfactuals,lesson) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.agent, self.run_id, opened_ts, closed_ts, coin, side, setup, regime, int(probation),
             json.dumps({k: (None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v))
                         for k, v in features.items()}),
             thesis, confidence, net_bps, excess_bps, mfe_bps, mae_bps, exit_reason, days_held,
             counterfactuals, lesson))
        self.conn.commit()
        self._feat_cache = None
        self._vote_insights(closed_ts, setup, regime, side, excess_bps)
        return cur.lastrowid

    # ------------------------------------------------------------- evidence
    def evidence(self, setup: str, regime: Optional[str], as_of: int) -> Dict[str, float]:
        """Decayed statistics of EXCESS results for a setup (optionally in a regime),
        using only experiences closed at or before as_of."""
        q = "SELECT closed_ts, excess_bps FROM experience WHERE agent=? AND setup=? AND closed_ts<=?"
        args: list = [self.agent, setup, as_of]
        if regime:
            q += " AND regime=?"; args.append(regime)
        rows = self.conn.execute(q, args).fetchall()
        if not rows:
            return {"n": 0, "n_eff": 0.0, "mean": 0.0, "sd": 0.0, "win": float("nan")}
        w = np.array([0.5 ** ((as_of - ts) / DAY_MS / self.half_life) for ts, _ in rows])
        x = np.array([v for _, v in rows], dtype=float)
        n_eff = float(w.sum())
        mean = float((w * x).sum() / n_eff)
        var = float((w * (x - mean) ** 2).sum() / max(n_eff, 1e-9))
        return {"n": len(rows), "n_eff": n_eff, "mean": mean, "sd": math.sqrt(var),
                "win": float((w * (x > 0)).sum() / n_eff)}

    def sample(self, setup: str, regime: Optional[str], as_of: int) -> float:
        """Thompson sample of the setup's mean excess: a draw from N(m, s/sqrt(n)) with a
        prior of 0 and prior_n pseudo-observations. Weak evidence -> wide draws ->
        the setup keeps getting tried. Strong bad evidence -> rarely positive -> rarely
        taken, but never never."""
        ev = self.evidence(setup, regime, as_of)
        n = ev["n_eff"] + self.prior_n
        m = ev["mean"] * ev["n_eff"] / n
        sd = (max(ev["sd"], 100.0) if ev["n_eff"] > 1 else 400.0)   # floor 100 bps: identical outcomes must not silence a setup
        return self.rng.gauss(m, sd / math.sqrt(n))

    def evidence_table(self, setups: Sequence[str], regimes: Sequence[str], as_of: int) -> List[Dict]:
        out = []
        for s in setups:
            for r in regimes:
                ev = self.evidence(s, r, as_of)
                if ev["n"]:
                    out.append({"setup": s, "regime": r, **ev})
        return out

    # ------------------------------------------------------------- similarity
    def _load_features(self, as_of: int):
        """All experiences with a feature vector, closed at or before as_of. Parsed once per
        (as_of, row count): observe() asks 172 times per day and the rows do not change."""
        n = self.conn.execute("SELECT COUNT(*) FROM experience WHERE agent=? AND closed_ts<=? AND features IS NOT NULL",
                              (self.agent, as_of)).fetchone()[0]
        if self._feat_cache and self._feat_cache[0] == (as_of, n):
            return self._feat_cache[1]
        rows = self.conn.execute(
            "SELECT id, closed_ts, regime, side, features, excess_bps FROM experience "
            "WHERE agent=? AND closed_ts<=? AND features IS NOT NULL", (self.agent, as_of)).fetchall()
        recs = []
        for id_, ts, reg, side, f, ex in rows:
            try:
                d = json.loads(f)
            except Exception:
                continue
            recs.append((id_, ts, reg, side, d, ex))
        self._feat_cache = ((as_of, n), recs)
        return recs

    def similar(self, features: Dict[str, float], as_of: int, k: int = 20,
                regime: Optional[str] = None) -> Dict[str, float]:
        """The k nearest past situations (standardised euclidean over shared feature
        keys, same regime first) and what happened to them, expressed as the excess a
        LONG would have made (shorts flipped). Returns n, mean, win, and the ids."""
        recs = self._load_features(as_of)
        keys = [kk for kk, v in features.items() if v is not None and not (isinstance(v, float) and math.isnan(v))]
        recs = [r for r in recs if all(kk in r[4] and r[4][kk] is not None for kk in keys)]
        if len(recs) < 5 or not keys:
            return {"n": 0, "mean": float("nan"), "win": float("nan"), "ids": []}
        M = np.array([[r[4][kk] for kk in keys] for r in recs], dtype=float)
        mu, sd = M.mean(0), M.std(0) + 1e-9
        q = (np.array([features[kk] for kk in keys], dtype=float) - mu) / sd
        Z = (M - mu) / sd
        d = np.sqrt(((Z - q) ** 2).sum(1))
        if regime:
            d = d + np.array([0.0 if r[2] == regime else 1.5 for r in recs])   # same regime preferred
        idx = np.argsort(d)[:k]
        # express each outcome as "what a long would have made"
        vals = np.array([recs[i][5] * (1.0 if recs[i][3] == "long" else -1.0) for i in idx])
        return {"n": int(len(idx)), "mean": float(vals.mean()), "win": float((vals > 0).mean()),
                "ids": [int(recs[i][0]) for i in idx]}

    # ------------------------------------------------------------- insights
    def propose_insight(self, created_ts: int, setup: str, regime: str, text: str,
                        source: str, support_n: int = 0) -> int:
        cur = self.conn.execute(
            "INSERT INTO insight(agent,run_id,created_ts,updated_ts,setup,regime,text,source,support_n) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (self.agent, self.run_id, created_ts, created_ts, setup, regime, text, source, support_n))
        self.conn.commit()
        return cur.lastrowid

    def _vote_insights(self, ts: int, setup: str, regime: str, side: str, excess_bps: float) -> None:
        """Every new outcome votes on the insights whose condition it matches. An
        insight that says 'skip X in R' is upvoted when X in R loses again, downvoted
        when it wins. Activation needs oos_n >= 10 with the mean on the insight's side."""
        rows = self.conn.execute(
            "SELECT id, importance, oos_n, oos_mean_excess, status, text FROM insight "
            "WHERE agent=? AND setup=? AND regime=? AND status!='retired' AND created_ts<=?",
            (self.agent, setup, regime, ts)).fetchall()
        for id_, imp, oos_n, oos_mean, status, text in rows:
            skip_rule = text.lower().startswith("skip")
            agrees = (excess_bps < 0) if skip_rule else (excess_bps > 0)
            imp = imp + 1 if agrees else imp - 1
            oos_mean = ((oos_mean or 0.0) * oos_n + excess_bps) / (oos_n + 1)
            oos_n += 1
            if imp <= 0:
                status = "retired"
            elif status == "proposed" and oos_n >= 10 and ((oos_mean < 0) == skip_rule):
                status = "active"
            elif status == "active" and oos_n >= 10 and ((oos_mean < 0) != skip_rule):
                status = "retired"
            self.conn.execute("UPDATE insight SET importance=?, oos_n=?, oos_mean_excess=?, status=?, updated_ts=? WHERE id=?",
                              (imp, oos_n, oos_mean, status, ts, id_))
        self.conn.commit()

    def insights(self, as_of: int, status: str = "active") -> List[Dict]:
        rows = self.conn.execute(
            "SELECT id, created_ts, setup, regime, text, importance, support_n, oos_n, oos_mean_excess, status "
            "FROM insight WHERE agent=? AND created_ts<=? AND status=? ORDER BY importance DESC",
            (self.agent, as_of, status)).fetchall()
        keys = ["id", "created_ts", "setup", "regime", "text", "importance", "support_n", "oos_n", "oos_mean_excess", "status"]
        return [dict(zip(keys, r)) for r in rows]

    # ------------------------------------------------------------- notes (market views, evidence, free notes)
    def write_note(self, ts: int, kind: str, text: str, tags: str = "") -> int:
        cur = self.conn.execute("INSERT INTO note(agent,run_id,ts,kind,text,tags) VALUES (?,?,?,?,?,?)",
                                (self.agent, self.run_id, ts, kind, text, tags))
        self.conn.commit()
        return cur.lastrowid

    def notes(self, as_of: int, kind: Optional[str] = None, k: int = 5) -> List[Dict]:
        q = "SELECT ts, kind, text, tags FROM note WHERE agent=? AND ts<=?"
        args: list = [self.agent, as_of]
        if kind:
            q += " AND kind=?"; args.append(kind)
        rows = self.conn.execute(q + " ORDER BY ts DESC LIMIT ?", args + [k]).fetchall()
        return [{"ts": r[0], "kind": r[1], "text": r[2], "tags": r[3]} for r in rows]

    # ------------------------------------------------------------- recall + calibration
    def recall(self, as_of: int, query: str = "", k: int = 6) -> List[Dict]:
        if query.strip():
            # FTS5 treats quotes, hyphens, AND/OR/NOT as syntax: quote every word so any text is a valid query
            query = " ".join('"' + w.replace('"', "") + '"' for w in query.split() if w.replace('"', ""))
            rows = self.conn.execute(
                "SELECT e.id, e.closed_ts, e.regime, e.setup, e.side, e.excess_bps, e.exit_reason, e.lesson "
                "FROM experience_fts JOIN experience e ON e.id=experience_fts.rowid "
                "WHERE experience_fts MATCH ? AND e.closed_ts<=? AND e.agent=? ORDER BY bm25(experience_fts) LIMIT ?",
                (query, as_of, self.agent, k)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT id, closed_ts, regime, setup, side, excess_bps, exit_reason, lesson FROM experience "
                "WHERE closed_ts<=? AND agent=? ORDER BY ABS(excess_bps) DESC, closed_ts DESC LIMIT ?",
                (as_of, self.agent, k)).fetchall()
        keys = ["id", "closed_ts", "regime", "setup", "side", "excess_bps", "exit_reason", "lesson"]
        return [dict(zip(keys, r)) for r in rows]

    def calibration(self, as_of: int) -> List[Dict]:
        """Win rate per stated-confidence bucket: the agent's honesty about itself."""
        rows = self.conn.execute(
            "SELECT confidence, excess_bps FROM experience WHERE agent=? AND closed_ts<=? AND confidence IS NOT NULL",
            (self.agent, as_of)).fetchall()
        out = []
        for lo, hi in ((0.0, 0.55), (0.55, 0.7), (0.7, 0.85), (0.85, 1.01)):
            xs = [ex for c, ex in rows if lo <= c < hi]
            if xs:
                out.append({"bucket": f"{lo:.2f}-{min(hi,1.0):.2f}", "n": len(xs),
                            "win": sum(1 for x in xs if x > 0) / len(xs),
                            "mean_excess": sum(xs) / len(xs)})
        return out

    def stats(self, as_of: Optional[int] = None) -> Dict[str, float]:
        as_of = as_of or int(time.time() * 1000)
        n, avg, wins, prob = self.conn.execute(
            "SELECT COUNT(*), AVG(excess_bps), SUM(excess_bps>0), SUM(probation) FROM experience "
            "WHERE agent=? AND closed_ts<=?", (self.agent, as_of)).fetchone()
        act = self.conn.execute("SELECT COUNT(*) FROM insight WHERE agent=? AND status='active'", (self.agent,)).fetchone()[0]
        ret = self.conn.execute("SELECT COUNT(*) FROM insight WHERE agent=? AND status='retired'", (self.agent,)).fetchone()[0]
        return {"experiences": n or 0, "avg_excess_bps": avg or 0.0,
                "win_rate": (wins / n) if n else float("nan"), "probation_trades": prob or 0,
                "insights_active": act, "insights_retired": ret}
