"""The deep-research layer.

The internal feeds (funding, price, events, our own social scrape) see the
NUMBERS and a thin slice of chatter. They do NOT see: what the coin actually IS
and does, its recent developments, partnerships, team, the sector it sits in and
whether that sector is hot, what analysts and the broader web are saying, upcoming
catalysts not on an exchange notice. That is the human/narrative story crypto
actually trades on, and it lives on the open web.

This module does two things:
  1. `packet(coin)` — assemble everything we ALREADY know internally, so the
     reasoning layer has full context BEFORE it web-searches (no wasted searches).
  2. a research NOTE store — the reasoning layer does the actual deep web research
     (WebSearch/WebFetch) and writes its findings here, timestamped, so a coin's
     research is remembered and not re-done from scratch every time.

The deep research itself is done BY THE REASONING LAYER (Claude), not by this
script — a script cannot judge what a development means. This module is the
scaffolding: prep the context, store the findings, track what is stale.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "research.db"
VENUES_DB = ROOT / "data" / "venues.db"
EVENTS_DB = ROOT / "data" / "events.db"
SOCIAL_DB = ROOT / "data" / "social.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  coin TEXT NOT NULL,
  created_ms INTEGER NOT NULL,
  headline TEXT,           -- one-line: what did the research conclude
  what_it_is TEXT,         -- the coin/project in a sentence
  sector TEXT,             -- and is that sector hot right now
  catalysts TEXT,          -- upcoming/recent, dated where possible
  sentiment TEXT,          -- what the web/crowd is actually saying
  bull TEXT, bear TEXT,    -- the two sides
  verdict TEXT,            -- long | short | avoid | watch
  confidence REAL,
  sources TEXT             -- JSON list of URLs used
);
CREATE INDEX IF NOT EXISTS idx_notes_coin ON notes(coin, created_ms);
"""


def _ro(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def packet(coin: str) -> Dict[str, Any]:
    """Everything we know internally about a coin, to brief the web research."""
    coin = coin.upper()
    out: Dict[str, Any] = {"coin": coin}

    # internal signals
    try:
        conn = _ro(VENUES_DB)
        last = conn.execute("SELECT MAX(ts_ms) FROM cv_features").fetchone()[0]
        cv = conn.execute("SELECT * FROM cv_features WHERE coin=? AND ts_ms=?",
                          (coin, last)).fetchone() if last else None
        hlast = conn.execute("SELECT MAX(ts_ms) FROM hl_state").fetchone()[0]
        hs = conn.execute("SELECT funding_hourly, mid FROM hl_state WHERE coin=? AND ts_ms=?",
                         (coin, hlast)).fetchone() if hlast else None
        conn.close()
        if cv:
            out["price"] = cv["cp"]
            out["perp_spot_basis_bps"] = cv["sp_basis_bps"]
            out["hl_vs_world_bps"] = cv["hl_dev_bps"]
            out["credible_vol_usd"] = cv["credible_vol_usd"]
            out["premium_krw_bps"] = cv["premium_krw_bps"]
        if hs and hs["funding_hourly"] is not None:
            out["funding_apr"] = hs["funding_hourly"] * 24 * 365
    except sqlite3.Error:
        pass

    # recent price behaviour
    f = ROOT / "data" / "carry_cache" / "daily_365.parquet"
    if f.exists():
        try:
            import pandas as pd
            px = pd.read_parquet(f)
            if coin in px.columns:
                s = px[coin].dropna()
                if len(s) > 8:
                    out["ret_1d"] = float(s.iloc[-1] / s.iloc[-2] - 1)
                    out["ret_7d"] = float(s.iloc[-1] / s.iloc[-8] - 1) if len(s) > 8 else None
                    out["ret_30d"] = float(s.iloc[-1] / s.iloc[-31] - 1) if len(s) > 31 else None
        except Exception:
            pass

    # our own social mentions of it (raw, for context — not a signal)
    try:
        conn = _ro(SOCIAL_DB)
        rows = conn.execute(
            "SELECT source, text FROM posts WHERE text LIKE ? "
            "ORDER BY first_seen_ms DESC LIMIT 5", (f"%{coin}%",)).fetchall()
        conn.close()
        out["our_social_mentions"] = [{"source": r["source"], "text": r["text"][:140]}
                                      for r in rows]
    except sqlite3.Error:
        out["our_social_mentions"] = []

    # any prior research note
    out["prior_research"] = latest_note(coin)
    return out


def store() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def log_note(coin: str, headline: str, what_it_is: str = "", sector: str = "",
             catalysts: str = "", sentiment: str = "", bull: str = "", bear: str = "",
             verdict: str = "watch", confidence: float = 0.5,
             sources: Optional[List[str]] = None) -> int:
    conn = store()
    with conn:
        cur = conn.execute(
            "INSERT INTO notes (coin, created_ms, headline, what_it_is, sector, "
            "catalysts, sentiment, bull, bear, verdict, confidence, sources) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (coin.upper(), int(time.time() * 1000), headline, what_it_is, sector,
             catalysts, sentiment, bull, bear, verdict, confidence,
             json.dumps(sources or [])))
    conn.close()
    return cur.lastrowid


def latest_note(coin: str) -> Optional[Dict[str, Any]]:
    if not DB.exists():
        return None
    conn = _ro(DB)
    r = conn.execute("SELECT * FROM notes WHERE coin=? ORDER BY created_ms DESC LIMIT 1",
                     (coin.upper(),)).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    d["age_hours"] = (time.time() * 1000 - d["created_ms"]) / 3_600_000
    return d


def all_notes(limit: int = 50) -> List[Dict[str, Any]]:
    if not DB.exists():
        return []
    conn = _ro(DB)
    rows = conn.execute(
        "SELECT coin, created_ms, headline, verdict, confidence FROM notes "
        "ORDER BY created_ms DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
