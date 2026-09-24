"""Token-unlock calendar — the scheduled-catalyst feed, restored on a FREE source.

The old feed (api.llama.fi/emissions) moved behind DefiLlama's $300/mo Pro tier (402).
The free path is their frontend dataset host, no key, no 402:
    https://defillama-datasets.llama.fi/emissionsProtocolsList   -> 370 protocol slugs
    https://defillama-datasets.llama.fi/emissions/<slug>         -> that token's schedule

Unlock cliffs are ~88% negative in the 72h around them (research), so a near unlock is
a BEARISH overlay on any long we are considering. This module scans the protocols,
caches the next upcoming unlock per token, and maps our HL tickers to it.
"""
from __future__ import annotations

import json
import sqlite3
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "unlocks.db"
DS = "https://defillama-datasets.llama.fi"
_HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://defillama.com/"}
_cg = {"t": 0.0, "map": None}

SCHEMA = """
CREATE TABLE IF NOT EXISTS unlocks (
  gecko_id TEXT PRIMARY KEY, slug TEXT, next_ts INTEGER, next_days REAL,
  next_desc TEXT, updated_ms INTEGER
);
"""

# Added 2026-09-13 (HANDOFF §8e: "dates but no sizes"). The payload always had
# the size - every event carries noOfTokens - it was just never stored.
#   next_tokens   tokens unlocking that day, SUMMED over that day's events
#                 (Arbitrum's cliff is 'insiders' + 'privateSale' on the same date)
#   next_pct_max  next_tokens / supplyMetrics.maxSupply (56 of 60 protocols have it);
#                 NULL when the max supply is unknown. Max supply, not circulating -
#                 circulating is not in the payload and would have to be derived.
#   next_events   how many events make up that day
#   next_cats     their categories, comma-joined (insiders, privateSale, ...)
SIZE_COLS = (("next_tokens", "REAL"), ("next_pct_max", "REAL"),
             ("next_events", "INTEGER"), ("next_cats", "TEXT"))


def _get(url, timeout=15):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=_HDR), timeout=timeout).read())


def _store():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB); c.executescript(SCHEMA)
    have = {r[1] for r in c.execute("PRAGMA table_info(unlocks)")}
    for col, typ in SIZE_COLS:          # migrate an older file in place
        if col not in have:
            c.execute(f"ALTER TABLE unlocks ADD COLUMN {col} {typ}")
    c.commit()
    return c


def _cg_symbol_map() -> Dict[str, List[str]]:
    """symbol -> [coingecko ids], cached 24h (one call, ~16k coins)."""
    if time.time() - _cg["t"] < 86400 and _cg["map"]:
        return _cg["map"]
    m: Dict[str, List[str]] = {}
    try:
        for row in _get("https://api.coingecko.com/api/v3/coins/list", timeout=25):
            m.setdefault((row.get("symbol") or "").lower(), []).append(row.get("id"))
    except Exception:
        pass
    _cg["map"] = m; _cg["t"] = time.time()
    return m


def refresh_cache(limit: Optional[int] = None, sleep: float = 0.05) -> int:
    """Scan the emissions protocols and cache each token's NEXT upcoming unlock.
    Slow (one request per protocol) — run periodically, not per page load."""
    now = time.time()
    try:
        protos = _get(f"{DS}/emissionsProtocolsList")
    except Exception:
        return 0
    if limit:
        protos = protos[:limit]
    conn = _store()
    n = 0
    for slug in protos:
        try:
            d = _get(f"{DS}/emissions/{slug}", timeout=12)
            gid = d.get("gecko_id")
            evs = (d.get("metadata") or {}).get("events") or []
            up = [e for e in evs if e.get("timestamp", 0) > now]
            if not gid or not up:
                continue
            nxt = min(up, key=lambda e: e["timestamp"])
            days = (nxt["timestamp"] - now) / 86400
            desc = (nxt.get("description") or nxt.get("category") or "unlock")[:120]
            # size of the cliff = every event on that same UTC day
            day = int(nxt["timestamp"] // 86400)
            same = [e for e in up if int(e.get("timestamp", 0) // 86400) == day]
            tokens = 0.0
            for e in same:
                for t in (e.get("noOfTokens") or []):
                    try:
                        tokens += float(t)
                    except (TypeError, ValueError):
                        pass
            max_supply = (d.get("supplyMetrics") or {}).get("maxSupply")
            try:
                pct = tokens / float(max_supply) if max_supply and tokens else None
            except (TypeError, ValueError, ZeroDivisionError):
                pct = None
            cats = ",".join(sorted({str(e.get("category")) for e in same if e.get("category")})) or None
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO unlocks (gecko_id,slug,next_ts,next_days,next_desc,"
                    "updated_ms,next_tokens,next_pct_max,next_events,next_cats) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (gid, slug, int(nxt["timestamp"]), round(days, 1), desc, int(now * 1000),
                     tokens or None, pct, len(same), cats))
            n += 1
        except Exception:
            pass
        if sleep:
            time.sleep(sleep)
    conn.close()
    return n


def for_coin(ticker: str) -> Optional[Dict[str, Any]]:
    """Next upcoming unlock for an HL ticker, or None. Resolves symbol->gecko via
    CoinGecko, preferring the gecko id we actually have unlock data for."""
    if not DB.exists():
        return None
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    ids = _cg_symbol_map().get(ticker.lower(), [])
    # also try the ticker itself as a gecko id (common for majors)
    cand = [ticker.lower()] + ids
    cols = {r[1] for r in conn.execute("PRAGMA table_info(unlocks)")}
    sized = all(c in cols for c, _ in SIZE_COLS)   # an old file may predate the size columns
    extra = ",next_tokens,next_pct_max,next_events,next_cats" if sized else ""
    for gid in cand:
        r = conn.execute(f"SELECT gecko_id,next_ts,next_days,next_desc{extra} FROM unlocks "
                         "WHERE gecko_id=?", (gid,)).fetchone()
        if r:
            conn.close()
            out = {"gecko_id": r[0], "next_ts": r[1], "days": r[2], "desc": r[3]}
            if sized:
                out.update({"tokens": r[4], "pct_max": r[5], "events": r[6], "cats": r[7]})
            return out
    conn.close()
    return None


def upcoming(within_days: float = 14) -> List[Dict[str, Any]]:
    if not DB.exists():
        return []
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    now = time.time()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(unlocks)")}
    sized = all(c in cols for c, _ in SIZE_COLS)
    extra = ",next_tokens,next_pct_max,next_events,next_cats" if sized else ""
    rows = conn.execute(f"SELECT gecko_id,slug,next_ts,next_days,next_desc{extra} FROM unlocks "
                        "WHERE next_ts>? ORDER BY next_ts", (now,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        if r[3] is None or r[3] > within_days:
            continue
        d = {"gecko_id": r[0], "slug": r[1], "days": r[3], "desc": r[4]}
        if sized:
            d.update({"tokens": r[5], "pct_max": r[6], "events": r[7], "cats": r[8]})
        out.append(d)
    return out
