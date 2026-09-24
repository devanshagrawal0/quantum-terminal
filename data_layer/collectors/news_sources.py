"""News / law / regulation collectors -> document table.

Every source records BOTH published_ts (when it happened) and first_seen_ms
(when WE saw it). Backtests filter on first_seen_ms. Without that split every
news backtest silently look-aheads.

RATE LIMITS (read from each provider's docs / observed):
  GDELT        no documented hard cap; heavy queries are slow (~20s observed).
               We poll every 15 min because that is GDELT's own update cadence.
  Fed Register no key, no published limit. Poll 30 min; it updates daily.
  Congress.gov 5,000 requests/hour on the free api.data.gov key.
  GovInfo      api.data.gov key, generous. Poll hourly.
  Regulations  api.data.gov key, moderate. Poll hourly.
  Fed RSS      static file. Poll 30 min.

source_tier: 1 = official/primary, 2 = wire, 3 = media, 4 = social.
Tiering matters because a tier-3 headline alone must never fire a trade.

Run:  python data_layer/collectors/news_sources.py
      python data_layer/collectors/news_sources.py --interval 900
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "store"))
import store  # noqa: E402

UA = {"User-Agent": "quant-research-bot" + ((" contact:" + __import__("os").environ["CONTACT_EMAIL"]) if __import__("os").environ.get("CONTACT_EMAIL") else "")}


def http(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def _env(k):
    import os
    v = os.getenv(k)
    if v:
        return v.strip()
    try:
        for line in (store.ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(k + "="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def _ts(s):
    """Parse assorted date formats to epoch ms."""
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d",
              "%Y%m%dT%H%M%SZ", "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            d = datetime.strptime(s, f)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return int(d.timestamp() * 1000)
        except ValueError:
            continue
    try:  # GDELT 20260903T101500Z
        return int(datetime.strptime(s[:15], "%Y%m%dT%H%M%S")
                   .replace(tzinfo=timezone.utc).timestamp() * 1000)
    except ValueError:
        return None


def _write(conn, rows):
    """rows = (source_name, url, published_ts, title, lang, tier, extra)"""
    now = int(time.time() * 1000)
    return store.insert_many(conn, "document",
        ["source_name", "url", "published_ts", "first_seen_ms", "title", "lang",
         "source_tier", "extra"],
        [(r[0], r[1], r[2], now, r[3], r[4], r[5], r[6]) for r in rows if r[1]])


# ------------------------------------------------------------- collectors

def gdelt(conn, queries=("bitcoin", "ethereum", "crypto regulation",
                         "federal reserve", "sanctions", "export controls")):
    n = 0
    for q in queries:
        url = ("https://api.gdeltproject.org/api/v2/doc/doc?query="
               + urllib.parse.quote(q) + "&mode=artlist&maxrecords=75&format=json"
               "&sort=datedesc")
        try:
            d = json.loads(http(url, 90))
        except Exception:
            continue
        rows = [("gdelt:" + q, a.get("url"), _ts(a.get("seendate")),
                 a.get("title"), a.get("language"), 3,
                 json.dumps({"domain": a.get("domain"), "country": a.get("sourcecountry")}))
                for a in d.get("articles", [])]
        n += _write(conn, rows)
        conn.commit()
        time.sleep(1.5)   # GDELT is slow; be gentle
    return n


def federal_register(conn):
    n = 0
    for path, tier in (("documents.json?per_page=100&order=newest", 1),
                       ("public-inspection-documents.json", 1)):
        try:
            d = json.loads(http("https://www.federalregister.gov/api/v1/" + path, 60))
        except Exception:
            continue
        rows = [("federal_register", r.get("html_url"),
                 _ts(r.get("publication_date") or r.get("filed_at")),
                 r.get("title"), "en", tier,
                 json.dumps({"type": r.get("type"), "agencies":
                             [a.get("name") for a in (r.get("agencies") or [])][:3]}))
                for r in d.get("results", [])]
        n += _write(conn, rows)
        conn.commit()
    return n


def fed_speeches(conn):
    try:
        x = http("https://www.federalreserve.gov/feeds/speeches.xml", 40).decode("utf-8", "replace")
    except Exception:
        return 0
    rows = []
    for m in re.finditer(r"<item>(.*?)</item>", x, re.S):
        b = m.group(1)
        g = lambda t: (re.search(rf"<{t}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{t}>", b, re.S) or [None, None])[1]
        rows.append(("fed_speeches", g("link"), _ts(g("pubDate")), g("title"), "en", 1, None))
    n = _write(conn, rows)
    conn.commit()
    return n


def congress(conn):
    k = _env("CONGRESS_API_KEY") or "DEMO_KEY"
    try:
        d = json.loads(http(f"https://api.congress.gov/v3/bill?limit=100&api_key={k}", 60))
    except Exception:
        return 0
    rows = [("congress_gov", b.get("url"), _ts(b.get("updateDate")),
             f"{b.get('type','')}{b.get('number','')}: {b.get('title','')}", "en", 1,
             json.dumps({"latestAction": (b.get("latestAction") or {}).get("text")}))
            for b in d.get("bills", [])]
    n = _write(conn, rows)
    conn.commit()
    return n


def regulations_gov(conn):
    k = _env("REGULATIONS_API_KEY") or "DEMO_KEY"
    try:
        d = json.loads(http(
            f"https://api.regulations.gov/v4/documents?api_key={k}&page[size]=100"
            "&sort=-postedDate", 60))
    except Exception:
        return 0
    rows = []
    for r in d.get("data", []):
        a = r.get("attributes", {})
        rows.append(("regulations_gov",
                     f"https://www.regulations.gov/document/{r.get('id')}",
                     _ts(a.get("postedDate")), a.get("title"), "en", 1,
                     json.dumps({"agency": a.get("agencyId"),
                                 "docType": a.get("documentType")})))
    n = _write(conn, rows)
    conn.commit()
    return n


def govinfo(conn):
    k = _env("GOVINFO_API_KEY") or "DEMO_KEY"
    try:
        d = json.loads(http(f"https://api.govinfo.gov/collections?api_key={k}", 60))
    except Exception:
        return 0
    rows = [("govinfo", f"https://www.govinfo.gov/app/collection/{c.get('collectionCode')}",
             None, f"{c.get('collectionCode')}: {c.get('collectionName')}", "en", 1,
             json.dumps({"packageCount": c.get("packageCount")}))
            for c in d.get("collections", [])]
    n = _write(conn, rows)
    conn.commit()
    return n


COLLECTORS = [
    ("gdelt", gdelt),
    ("federal_register", federal_register),
    ("fed_speeches", fed_speeches),
    ("congress_gov", congress),
    ("regulations_gov", regulations_gov),
    ("govinfo", govinfo),
]


def run_once(conn, verbose=True):
    total = 0
    for name, fn in COLLECTORS:
        t0 = time.time()
        try:
            n = fn(conn)
            store.log_run(conn, f"news:{name}", True, n, int((time.time() - t0) * 1000))
            total += n
            if verbose:
                print(f"  {name:<20} +{n:<6} docs  ({time.time()-t0:.1f}s)")
        except Exception as e:  # noqa: BLE001
            store.log_run(conn, f"news:{name}", False, 0,
                          int((time.time() - t0) * 1000), str(e)[:180])
            print(f"  {name:<20} ERROR {str(e)[:70]}")
        conn.commit()
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=0)
    a = ap.parse_args()
    conn = store.init()
    if a.interval <= 0:
        print(f"news sources: one pass ({len(COLLECTORS)} collectors)")
        print(f"total +{run_once(conn)} documents")
        conn.close()
        return
    print(f"news sources: every {a.interval:.0f}s")
    while True:
        t0 = time.time()
        n = run_once(conn, verbose=False)
        print(f"[{time.strftime('%H:%M:%S')}] +{n} docs ({time.time()-t0:.0f}s)", flush=True)
        time.sleep(max(30.0, a.interval - (time.time() - t0)))


if __name__ == "__main__":
    main()
