"""Reference / physical / on-chain collectors.

RATE LIMITS (from docs / observed):
  SEC EDGAR    <=10 requests/second, declared User-Agent MANDATORY.
               We stay far under: a handful of calls per cycle.
  GLEIF        no key, no published cap. page[size] max 200.
  OFAC         static 29 MB XML. Poll daily, never faster.
  CFTC Socrata $limit/$offset. Unauthenticated is throttled — poll weekly
               (COT publishes Fri 15:30 ET anyway).
  PortWatch    ArcGIS FeatureServer, resultOffset paging. Weekly refresh.
  USGS         no key. Poll hourly.
  Greenhouse   public board JSON, no key. Poll daily.
  crt.sh       free but SLOW (3-30s). Poll daily.
  DefiLlama    no key, generous. Poll 15 min.
  openFDA      240 req/min per IP without a key.

Run:  python data_layer/collectors/reference_sources.py
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

UA = {"User-Agent": store.user_agent()}


def http(url, timeout=90):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def _ts(s):
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d",
              "%Y-%m-%dT%H:%M:%S"):
        try:
            d = datetime.strptime(s, f)
            return int((d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp() * 1000)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------- SEC (tier 1)

# CIKs we care about. Expand freely — this is config, not code.
WATCH_CIK = {
    "0000320193": "Apple", "0001045810": "NVIDIA", "0000789019": "Microsoft",
    "0001318605": "Tesla", "0001730168": "Broadcom", "0001067983": "Berkshire",
    "0001764925": "Coinbase", "0001512673": "MicroStrategy",
}


def sec_filings(conn):
    now = int(time.time() * 1000)
    rows, crefs = [], []
    for cik, name in WATCH_CIK.items():
        try:
            d = json.loads(http(f"https://data.sec.gov/submissions/CIK{cik}.json", 60))
        except Exception:
            continue
        crefs.append((cik, d.get("name") or name, d.get("stateOfIncorporation"),
                      d.get("sic"), ",".join(d.get("tickers") or []), now))
        rec = d.get("filings", {}).get("recent", {})
        forms = rec.get("form", [])
        for i in range(len(forms)):
            rows.append((rec["accessionNumber"][i], cik, d.get("name"), forms[i],
                         rec["filingDate"][i], _ts(rec.get("acceptanceDateTime", [None]*len(forms))[i]),
                         (rec.get("items") or [""] * len(forms))[i],
                         rec.get("primaryDocument", [""] * len(forms))[i], now))
        time.sleep(0.15)   # stay well under 10 req/s
    store.insert_many(conn, "company_ref",
        ["cik", "name", "state_of_incorporation", "sic", "tickers", "observed_at"],
        crefs, replace=True)
    n = store.insert_many(conn, "filing",
        ["accession", "cik", "company", "form", "filing_date", "acceptance_ts",
         "items", "primary_doc", "observed_at"], rows)
    conn.commit()
    return n


def gleif(conn, names=("Apple Inc.", "NVIDIA Corporation", "Coinbase Global, Inc.",
                       "MicroStrategy Incorporated", "Tesla, Inc.")):
    now = int(time.time() * 1000)
    rows = []
    for nm in names:
        try:
            d = json.loads(http("https://api.gleif.org/api/v1/lei-records?filter[entity.legalName]="
                                + urllib.parse.quote(nm) + "&page[size]=5", 60))
        except Exception:
            continue
        for rec in d.get("data", []):
            a = rec.get("attributes", {})
            e = a.get("entity", {})
            rows.append((a.get("lei"), (e.get("legalName") or {}).get("name"),
                         e.get("jurisdiction"), (e.get("legalForm") or {}).get("id"),
                         e.get("status"), now))
        time.sleep(0.3)
    n = store.insert_many(conn, "company_ref",
        ["lei", "name", "jurisdiction", "legal_form", "status", "observed_at"],
        rows, replace=True)
    conn.commit()
    return n


def ofac_sdn(conn):
    """29 MB XML. Daily at most."""
    try:
        x = http("https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML",
                 240).decode("utf-8", "replace")
    except Exception:
        return 0
    now = int(time.time() * 1000)
    rows = []
    for m in re.finditer(r"<sdnEntry>(.*?)</sdnEntry>", x, re.S):
        b = m.group(1)
        g = lambda t: (re.search(rf"<{t}>(.*?)</{t}>", b, re.S) or [None, None])[1]
        uid = g("uid")
        if not uid:
            continue
        nm = g("lastName") or ""
        first = g("firstName")
        if first:
            nm = f"{first} {nm}".strip()
        progs = re.findall(r"<program>(.*?)</program>", b)
        rows.append(("OFAC_SDN", uid, nm, g("sdnType"), ",".join(progs), None, now))
    n = store.insert_many(conn, "sanction_entity",
        ["list_name", "uid", "name", "entity_type", "program", "country", "observed_at"],
        rows, replace=True)
    conn.commit()
    return n


def cftc_cot(conn):
    try:
        d = json.loads(http("https://publicreporting.cftc.gov/resource/6dca-aqww.json"
                            "?$limit=5000&$order=report_date_as_yyyy_mm_dd%20DESC", 120))
    except Exception:
        return 0
    rows = []
    for r in d:
        rows.append((r.get("report_date_as_yyyy_mm_dd", "")[:10],
                     r.get("market_and_exchange_names"),
                     _ts(r.get("report_date_as_yyyy_mm_dd")),
                     _f(r.get("open_interest_all")),
                     _f(r.get("noncomm_positions_long_all")),
                     _f(r.get("noncomm_positions_short_all")),
                     _f(r.get("comm_positions_long_all")),
                     _f(r.get("comm_positions_short_all")),
                     _f(r.get("nonrept_positions_long_all")),
                     _f(r.get("nonrept_positions_short_all"))))
    n = store.insert_many(conn, "cot_position",
        ["report_date", "market", "ts_ms", "open_interest", "noncomm_long",
         "noncomm_short", "comm_long", "comm_short", "nonrept_long", "nonrept_short"],
        rows, replace=True)
    conn.commit()
    return n


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def portwatch(conn):
    """Daily transits for all 28 chokepoints."""
    base = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/"
            "Daily_Chokepoints_Data/FeatureServer/0/query")
    total = 0
    for i in range(1, 29):
        try:
            d = json.loads(http(
                f"{base}?where=portid%3D%27chokepoint{i}%27&outFields=*&f=json"
                f"&resultRecordCount=2000&orderByFields=date%20DESC", 90))
        except Exception:
            continue
        rows = []
        for f in d.get("features", []):
            a = f.get("attributes", {})
            ts = a.get("date")
            if isinstance(ts, (int, float)) and ts > 1e11:
                dt = datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m-%d")
            else:
                dt = str(a.get("date"))[:10]
            rows.append((a.get("portid"), dt, int(ts) if isinstance(ts, (int, float)) else None,
                         a.get("portname"), _f(a.get("n_total")), _f(a.get("n_cargo")),
                         _f(a.get("n_tanker")), _f(a.get("n_container")),
                         _f(a.get("n_dry_bulk")), _f(a.get("capacity"))))
        total += store.insert_many(conn, "chokepoint_transit",
            ["portid", "date", "ts_ms", "portname", "n_total", "n_cargo", "n_tanker",
             "n_container", "n_drybulk", "capacity"], rows, replace=True)
        conn.commit()
        time.sleep(0.3)
    return total


def usgs_quakes(conn):
    try:
        d = json.loads(http("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
                            "&starttime=2020-01-01&minmagnitude=5.5&limit=5000", 120))
    except Exception:
        return 0
    rows = []
    for f in d.get("features", []):
        p, g = f.get("properties", {}), (f.get("geometry") or {}).get("coordinates") or [None]*3
        rows.append(("usgs", f.get("id"), p.get("time"), "earthquake", p.get("mag"),
                     g[1], g[0], p.get("place"), json.dumps({"depth": g[2]})))
    n = store.insert_many(conn, "geo_event",
        ["source", "event_id", "ts_ms", "kind", "magnitude", "lat", "lon", "place", "detail"],
        rows, replace=True)
    conn.commit()
    return n


def greenhouse(conn, companies=("anthropic", "openai", "coinbase", "databricks", "stripe")):
    now = int(time.time() * 1000)
    total = 0
    for co in companies:
        try:
            d = json.loads(http(f"https://boards-api.greenhouse.io/v1/boards/{co}/jobs", 60))
        except Exception:
            continue
        rows = [(co, str(j.get("id")), j.get("title"),
                 (j.get("location") or {}).get("name"), _ts(j.get("updated_at")),
                 now, j.get("absolute_url")) for j in d.get("jobs", [])]
        total += store.insert_many(conn, "job_posting",
            ["company", "job_id", "title", "location", "posted_ts", "first_seen_ms", "url"], rows)
        conn.commit()
        time.sleep(0.3)
    return total


def crtsh(conn, domains=("anthropic.com", "openai.com", "coinbase.com")):
    now = int(time.time() * 1000)
    total = 0
    for dom in domains:
        try:
            d = json.loads(http(f"https://crt.sh/?q=%25.{dom}&output=json", 120))
        except Exception:
            continue
        rows = [(dom, str(c.get("id")), c.get("name_value"), _ts(c.get("entry_timestamp")), now)
                for c in d[:3000]]
        total += store.insert_many(conn, "cert_log",
            ["domain", "cert_id", "name_value", "issued_ts", "first_seen_ms"], rows)
        conn.commit()
        time.sleep(1.0)
    return total


def defillama(conn):
    now = int(time.time() * 1000)
    total = 0
    try:
        d = json.loads(http("https://api.llama.fi/protocols", 90))
        rows = [("defillama", "tvl", p.get("slug") or p.get("name"), now,
                 _f(p.get("tvl")), p.get("chain")) for p in d if p.get("tvl")]
        total += store.insert_many(conn, "onchain_metric",
            ["source", "metric", "entity", "ts_ms", "value", "chain"], rows, replace=True)
        conn.commit()
    except Exception:
        pass
    try:
        d = json.loads(http("https://stablecoins.llama.fi/stablecoins?includePrices=true", 90))
        rows = []
        for s in d.get("peggedAssets", []):
            circ = (s.get("circulating") or {}).get("peggedUSD")
            if circ:
                rows.append(("defillama", "stablecoin_supply", s.get("symbol") or s.get("name"),
                             now, _f(circ), None))
        total += store.insert_many(conn, "onchain_metric",
            ["source", "metric", "entity", "ts_ms", "value", "chain"], rows, replace=True)
        conn.commit()
    except Exception:
        pass
    return total


def fear_greed(conn):
    try:
        d = json.loads(http("https://api.alternative.me/fng/?limit=2000", 60))
    except Exception:
        return 0
    rows = [("alternative.me", "FEAR_GREED", int(x["timestamp"]) * 1000,
             float(x["value"]), "index", None, int(time.time() * 1000))
            for x in d.get("data", []) if x.get("value")]
    n = store.insert_many(conn, "macro_series",
        ["source", "series_id", "ts_ms", "value", "unit", "geo", "observed_at"],
        rows, replace=True)
    conn.commit()
    return n


COLLECTORS = [
    ("sec_filings", sec_filings),
    ("gleif", gleif),
    ("cftc_cot", cftc_cot),
    ("portwatch", portwatch),
    ("usgs_quakes", usgs_quakes),
    ("greenhouse", greenhouse),
    ("defillama", defillama),
    ("fear_greed", fear_greed),
    ("crtsh", crtsh),
    ("ofac_sdn", ofac_sdn),
]


def run_once(conn, only=None, verbose=True):
    total = 0
    for name, fn in COLLECTORS:
        if only and name not in only:
            continue
        t0 = time.time()
        try:
            n = fn(conn)
            store.log_run(conn, f"ref:{name}", True, n, int((time.time() - t0) * 1000))
            total += n
            if verbose:
                print(f"  {name:<18} +{n:<8} rows  ({time.time()-t0:.1f}s)")
        except Exception as e:  # noqa: BLE001
            store.log_run(conn, f"ref:{name}", False, 0,
                          int((time.time() - t0) * 1000), str(e)[:180])
            print(f"  {name:<18} ERROR {str(e)[:70]}")
        conn.commit()
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=0)
    ap.add_argument("--only", help="comma list of collector names")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    conn = store.init()
    if a.interval <= 0:
        print(f"reference sources: one pass")
        print(f"total +{run_once(conn, only)} rows")
        conn.close()
        return
    while True:
        t0 = time.time()
        n = run_once(conn, only, verbose=False)
        print(f"[{time.strftime('%H:%M:%S')}] +{n} rows", flush=True)
        time.sleep(max(60.0, a.interval - (time.time() - t0)))


if __name__ == "__main__":
    main()
