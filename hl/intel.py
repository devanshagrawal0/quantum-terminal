"""Per-coin intelligence reports — the deep, scored dossier behind every coin.

The connection map is only a skeleton (coins + a few notes). This is the flesh: for each
coin a rich report combining LONG-TERM story ("this can happen") and SHORT-TERM drivers
("this is happening now"), public SENTIMENT (short & long), SECTOR/market context, how the
coin AFFECTS others, dated CATALYSTS — and the reasoning layer's own 0-100 SCORES on all
of it (news sentiment, catalyst strength, sector heat, influence, outlook). Stored so it
persists, feeds the map, and informs trades — unbiased.

The SCORES and the narrative are written by the reasoning layer (Claude) after deep web
research; this module stores them and computes the MEASURED pieces it can (price
correlations to other coins, social mention/sentiment counts) so the human judgment sits
on top of real numbers, not vibes.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "intel.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
  coin TEXT PRIMARY KEY, updated_ms INTEGER,
  -- scores 0-100 (reasoning layer's judgment)
  short_score INTEGER, long_score INTEGER,          -- outlook bull(>50)/bear(<50)
  sentiment_short INTEGER, sentiment_long INTEGER,
  catalyst_strength INTEGER, sector_heat INTEGER, influence INTEGER,
  conviction INTEGER,
  -- narrative
  short_term TEXT, long_term TEXT, sentiment_note TEXT,
  sector TEXT, sector_context TEXT,
  cross_effects TEXT,      -- JSON [{coin,strength,note}]
  catalysts TEXT,          -- JSON [{when,event,impact,dir}]
  top_traders TEXT,        -- JSON [{who,platform,stance,note}] — smart money on X/sites
  smart_money INTEGER,     -- 0-100: net lean of the top traders (bull>50/bear<50)
  net_read TEXT, verdict TEXT, horizon TEXT,
  sources TEXT             -- JSON list of urls
);
"""


def _store():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; c.executescript(SCHEMA)
    for col, typ in (("top_traders", "TEXT"), ("smart_money", "INTEGER")):
        try:
            c.execute(f"ALTER TABLE reports ADD COLUMN {col} {typ}")
        except Exception:
            pass
    return c


def _ro():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); c.row_factory = sqlite3.Row; return c


# ---- measured pieces (real numbers the judgment sits on) -------------------

def price_correlations(coin: str, n: int = 8) -> List[Dict[str, Any]]:
    """The coins this one actually moves with (60d return correlation)."""
    try:
        import pandas as pd
        px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
        m = px.pct_change(fill_method=None).tail(60).corr()
        if coin not in m.columns:
            return []
        s = m[coin].drop(coin).dropna().sort_values(ascending=False)
        out = [{"coin": c, "corr": round(float(v), 2)} for c, v in s.head(n).items()]
        low = s.tail(2)
        out += [{"coin": c, "corr": round(float(v), 2), "diversifier": True} for c, v in low.items()]
        return out
    except Exception:
        return []


def social_sentiment(coin: str) -> Dict[str, Any]:
    """Mention counts (24h vs prior) + stated sentiment split, from our scrape."""
    try:
        conn = sqlite3.connect(f"file:{ROOT/'data'/'social.db'}?mode=ro", uri=True)
        now = time.time() * 1000
        rows = conn.execute("SELECT first_seen_ms,text,stated_sentiment FROM posts WHERE first_seen_ms>?",
                            (now - 48 * 3600000,)).fetchall()
        conn.close()
        pat = re.compile(r'\b' + re.escape(coin.upper()) + r'\b')
        cur = prev = pos = neg = 0
        for ts, txt, sent in rows:
            if pat.search((txt or "").upper()):
                if now - ts < 24 * 3600000:
                    cur += 1
                    if sent == "positive":
                        pos += 1
                    elif sent == "negative":
                        neg += 1
                else:
                    prev += 1
        return {"mentions_24h": cur, "mentions_prev": prev,
                "inflection": cur - prev, "stated_pos": pos, "stated_neg": neg}
    except Exception:
        return {"mentions_24h": 0, "mentions_prev": 0}


# ---- report store ----------------------------------------------------------

def save(coin: str, **fields) -> None:
    coin = coin.upper()
    for k in ("cross_effects", "catalysts", "sources", "top_traders"):
        if k in fields and not isinstance(fields[k], str):
            fields[k] = json.dumps(fields[k])
    fields["coin"] = coin
    fields["updated_ms"] = int(time.time() * 1000)
    cols = list(fields.keys())
    conn = _store()
    with conn:
        conn.execute(f"INSERT OR REPLACE INTO reports ({','.join(cols)}) "
                     f"VALUES ({','.join('?' for _ in cols)})", [fields[c] for c in cols])
    conn.close()


def get(coin: str) -> Optional[Dict[str, Any]]:
    if not DB.exists():
        return None
    conn = _ro()
    r = conn.execute("SELECT * FROM reports WHERE coin=?", (coin.upper(),)).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    for k in ("cross_effects", "catalysts", "sources", "top_traders"):
        try:
            d[k] = json.loads(d.get(k) or "[]")
        except Exception:
            d[k] = []
    d["age_hours"] = round((time.time() * 1000 - d["updated_ms"]) / 3_600_000, 1)
    # attach live measured pieces
    d["measured_corr"] = price_correlations(coin)
    d["measured_social"] = social_sentiment(coin)
    return d


def all_coins() -> List[str]:
    if not DB.exists():
        return []
    conn = _ro()
    rows = [r[0] for r in conn.execute("SELECT coin FROM reports ORDER BY updated_ms DESC")]
    conn.close()
    return rows
