"""Event detectors: notice when something NEW happens, store it raw.

The hard line this module holds, and the reason it holds it: detecting that
something is NEW is structural - a perp that was not in the list last time, a
notice id we have not seen. That needs no language understanding and cannot be
fooled by wording.

Deciding what an event MEANS - is this Korean notice a listing or a delisting or
a caution, is it bullish or bearish - is the opposite. Doing that with a keyword
list ("if the title contains 유의 it is bearish") is the banned pattern: brittle,
gameable, and a hardcoded rule masquerading as judgement. So nothing here
classifies. Every event is stored with its full, untranslated title and a link,
and what it means is decided later by something that can actually read it.

Each detector returns events with a stable `event_id`, so polling the same
source every minute never creates a duplicate. first_seen is stamped by the
collector, not taken from the source, because the source's own timestamp is
often wrong and is never what we could actually have known.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}


def _get(url: str, post: Optional[dict] = None, timeout: float = 20.0,
         tries: int = 4) -> Any:
    """Retries on 429 and transient errors. Multiple collectors and the carry
    backfill share one IP against Hyperliquid's 1200-weight/min limit, so a
    cheap call like the universe diff can still be refused when the others are
    busy. Backing off and retrying is correct here; giving up would drop a
    listing detection on a temporary collision."""
    data = json.dumps(post).encode() if post is not None else None
    headers = dict(UA)
    if post is not None:
        headers["Content-Type"] = "application/json"
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, data=data, headers=headers),
                    timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429:
                ra = exc.headers.get("Retry-After")
                time.sleep(float(ra) if (ra or "").isdigit() else 3.0 * (attempt + 1))
                continue
            raise
        except Exception as exc:
            last = exc
            time.sleep(2.0 * (attempt + 1))
    raise last


def _ev(source: str, event_id: str, kind: str, title: str,
        url: str = "", publish_ts: str = "", extra: Optional[dict] = None) -> Dict[str, Any]:
    return {"source": source, "event_id": f"{source}:{event_id}", "kind": kind,
            "title": title, "url": url, "publish_ts": publish_ts,
            "extra": extra or {}}


# ------------------------------------------------------ Hyperliquid universe

def hl_universe() -> List[Dict[str, Any]]:
    """The current perp list as pseudo-events, one per coin. The collector
    diffs these against last time; a coin that appears is a new listing, one
    that vanishes is a delisting, a changed maxLeverage is its own signal.

    This is the highest-value detector we have: it is our OWN venue, it is
    mechanical, and news traders ignore a new perp because it is not news.
    """
    meta = _get("https://api.hyperliquid.xyz/info", {"type": "meta"})
    out = []
    for a in meta["universe"]:
        out.append(_ev("hl_universe", a["name"], "perp_listed", a["name"],
                       url="https://app.hyperliquid.xyz/trade/" + a["name"],
                       extra={"maxLeverage": a.get("maxLeverage"),
                              "szDecimals": a.get("szDecimals"),
                              "isDelisted": a.get("isDelisted", False)}))
    return out


# ------------------------------------------------------------ announcements

def upbit() -> List[Dict[str, Any]]:
    """Korean listings and caution notices. Titles are Korean on purpose - that
    is the moat, and translating/classifying them here would throw it away."""
    d = _get("https://api-manager.upbit.com/api/v1/announcements"
             "?os=web&page=1&per_page=20&category=trade")
    out = []
    for n in d["data"]["notices"]:
        out.append(_ev("upbit", str(n["id"]), "announcement", n["title"],
                       url=f"https://upbit.com/service_center/notice?id={n['id']}",
                       publish_ts=n.get("listed_at", "")))
    return out


def bithumb() -> List[Dict[str, Any]]:
    d = _get("https://api.bithumb.com/v1/notices?count=20")
    out = []
    for n in d if isinstance(d, list) else []:
        nid = n.get("pc_url", "").rstrip("/").split("/")[-1] or n.get("title", "")[:24]
        out.append(_ev("bithumb", str(nid), "announcement", n.get("title", ""),
                       url=n.get("pc_url", ""), publish_ts=str(n.get("published_at", "")),
                       extra={"categories": n.get("categories")}))
    return out


def binance() -> List[Dict[str, Any]]:
    d = _get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
             "?type=1&catalogId=48&pageNo=1&pageSize=20")
    out = []
    for cat in d.get("data", {}).get("catalogs", []):
        for a in cat.get("articles", []):
            out.append(_ev("binance", str(a["id"]), "announcement", a["title"],
                           url=f"https://www.binance.com/en/support/announcement/{a.get('code','')}",
                           publish_ts=str(a.get("releaseDate", ""))))
    return out


def bybit() -> List[Dict[str, Any]]:
    d = _get("https://api.bybit.com/v5/announcements/index?locale=en-US&limit=20")
    out = []
    for a in d.get("result", {}).get("list", []):
        out.append(_ev("bybit", str(a.get("url", a.get("title", ""))[-40:]),
                       "announcement", a.get("title", ""),
                       url=a.get("url", ""), publish_ts=str(a.get("dateTimestamp", ""))))
    return out


DETECTORS: Dict[str, Callable[[], List[Dict[str, Any]]]] = {
    "hl_universe": hl_universe,
    "upbit": upbit,
    "bithumb": bithumb,
    "binance": binance,
    "bybit": bybit,
}
