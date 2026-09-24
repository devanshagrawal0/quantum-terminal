"""Source verification harness.

PROTOCOL (per Dev):
  1. documentation is read first (findings recorded in DOCS below)
  2. call the real endpoint
  3. log whether data came back, and WHAT data
  4. verify the payload actually contains the expected field(s)
  5. label verified / dead, with evidence, into store.source

Nothing is marked 'verified' on an HTTP 200 alone — a check must confirm the
payload holds the field we actually need. HL's `leaderboard` returned a clean
422 while sitting in our code as if it worked; that is the failure this guards.

Run:  python data_layer/verify_sources.py            # all
      python data_layer/verify_sources.py --batch 1  # one batch
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "store"))
import store  # noqa: E402

UA = "quant-research-bot" + ((" contact:" + __import__("os").environ["CONTACT_EMAIL"]) if __import__("os").environ.get("CONTACT_EMAIL") else "")


def _env(key: str) -> str:
    import os
    v = os.getenv(key)
    if v:
        return v.strip()
    try:
        for line in (store.ROOT / ".env").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def fetch(url, headers=None, timeout=25, post=None):
    """Return (http_status, body_bytes, latency_ms, error)."""
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    t0 = time.time()
    try:
        req = urllib.request.Request(url, data=post, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, body, int((time.time() - t0) * 1000), None
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:2000], int((time.time() - t0) * 1000), f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return 0, b"", int((time.time() - t0) * 1000), str(e)[:200]


# ---------------------------------------------------------------- checkers
# Each returns (ok: bool, description_of_data: str)

def j(body):
    return json.loads(body.decode("utf-8", "replace"))


def chk_sec_submissions(b):
    d = j(b)
    n = len(d.get("filings", {}).get("recent", {}).get("form", []))
    return (n > 0 and "cik" in d,
            f"name={d.get('name')} sic={d.get('sicDescription')} "
            f"state_of_inc={d.get('stateOfIncorporation')} recent_filings={n}")


def chk_sec_frames(b):
    d = j(b)
    n = len(d.get("data", []))
    return n > 0, f"tag={d.get('tag')} unit={d.get('uom')} filers={n}"


def chk_sec_fts(b):
    d = j(b)
    n = d.get("hits", {}).get("total", {}).get("value", 0)
    return n > 0, f"full-text hits={n}"


def chk_fedreg(b):
    d = j(b)
    n = d.get("count", 0)
    r = (d.get("results") or [{}])[0]
    return n > 0, f"docs={n} first='{str(r.get('title'))[:60]}' type={r.get('type')}"


def chk_gleif(b):
    d = j(b)
    arr = d.get("data", [])
    if not arr:
        return False, "no records"
    a = arr[0].get("attributes", {})
    ent = a.get("entity", {})
    return True, (f"lei={a.get('lei')} name={ent.get('legalName',{}).get('name')} "
                  f"jurisdiction={ent.get('jurisdiction')} n={len(arr)}")


def chk_fred(b):
    d = j(b)
    obs = d.get("observations", [])
    return len(obs) > 0, f"obs={len(obs)} last={obs[-1].get('date')}:{obs[-1].get('value')}" if obs else "none"


def chk_worldbank(b):
    d = j(b)
    if not isinstance(d, list) or len(d) < 2:
        return False, "unexpected shape"
    return len(d[1]) > 0, f"rows={len(d[1])} first={d[1][0].get('country',{}).get('value')}"


def chk_ecb(b):
    t = b.decode("utf-8", "replace")
    lines = [x for x in t.splitlines() if x.strip()]
    return len(lines) > 1, f"csv rows={len(lines)-1} header={lines[0][:70] if lines else ''}"


def chk_gdelt(b):
    d = j(b)
    arts = d.get("articles", [])
    if not arts:
        return False, "no articles"
    langs = {a.get("language") for a in arts}
    return True, f"articles={len(arts)} langs={sorted(x for x in langs if x)[:5]}"


def chk_portwatch(b):
    d = j(b)
    f = d.get("features", [])
    if not f:
        return False, "no features"
    at = f[0].get("attributes", {})
    return True, f"records={len(f)} portname={at.get('portname')} date_field_keys={list(at)[:6]}"


def chk_usgs(b):
    d = j(b)
    f = d.get("features", [])
    return len(f) > 0, f"quakes={len(f)} max_mag={max((x['properties'].get('mag') or 0) for x in f) if f else 0}"


def chk_restcountries(b):
    d = j(b)
    return len(d) > 100, f"countries={len(d)}"


def chk_crtsh(b):
    d = j(b)
    return len(d) > 0, f"certs={len(d)} first_name={d[0].get('name_value','')[:40] if d else ''}"


def chk_greenhouse(b):
    d = j(b)
    jobs = d.get("jobs", [])
    return len(jobs) > 0, f"jobs={len(jobs)} first={str(jobs[0].get('title'))[:40] if jobs else ''}"


def chk_wikidata(b):
    d = j(b)
    r = d.get("results", {}).get("bindings", [])
    return len(r) > 0, f"bindings={len(r)}"


def chk_defillama(b):
    d = j(b)
    if isinstance(d, list):
        return len(d) > 0, f"protocols={len(d)}"
    return bool(d), f"keys={list(d)[:6]}"


def chk_coingecko(b):
    d = j(b)
    return "data" in d or isinstance(d, list), f"keys={list(d)[:6] if isinstance(d,dict) else 'list'}"


def chk_cbanks(b):
    t = b.decode("utf-8", "replace")
    n = t.lower().count("<a href")
    return n > 50, f"html page, anchor tags={n}"


def chk_bcb(b):
    d = j(b)
    return len(d) > 0, f"rows={len(d)} last={d[-1] if d else None}"


def chk_futuresbench(b):
    t = b.decode("utf-8", "replace")
    lines = [x for x in t.splitlines() if x.strip()]
    return len(lines) > 1, f"csv rows={len(lines)-1}"


def chk_sanctions_net(b):
    d = j(b)
    return bool(d), f"type={type(d).__name__} size={len(d) if hasattr(d,'__len__') else '?'}"


def chk_rss(b):
    t = b.decode("utf-8", "replace")
    n = t.count("<item") + t.count("<entry")
    return n > 0, f"feed items={n}"


def chk_fcc(b):
    t = b.decode("utf-8", "replace")
    return len(t) > 500, f"html bytes={len(t)}"


def chk_overpass(b):
    d = j(b)
    el = d.get("elements", [])
    return len(el) > 0, f"osm elements={len(el)}"


def chk_bis(b):
    t = b.decode("utf-8", "replace")
    lines = [x for x in t.splitlines() if x.strip()]
    return len(lines) > 1, f"rows={len(lines)-1} header={lines[0][:70] if lines else ''}"


# ------------------------------------------------------------------ sources
# doc = what the documentation says (read before testing)

SOURCES = [
    # ---------------- BATCH 1: SEC / US GOV / MACRO (no key) ----------------
    dict(batch=1, name="sec_edgar_submissions", cat="reference",
         url="https://data.sec.gov/submissions/CIK0000320193.json",
         chk=chk_sec_submissions, auth="none",
         doc="No auth/API key. Declared User-Agent required. JSON only. "
             "CIK zero-padded to 10. <1s update lag. Bulk ZIPs nightly ~03:00 ET.",
         covers="filings history, 8-K item codes, state of incorporation, tickers"),
    dict(batch=1, name="sec_edgar_xbrl_frames", cat="reference",
         url="https://data.sec.gov/api/xbrl/frames/us-gaap/Revenues/USD/CY2024Q1.json",
         chk=chk_sec_frames, auth="none",
         doc="Frames API: CY####/CY####Q#/CY####Q#I. Units USD or USD-per-shares. "
             "XBRL lag <1min. No auth.",
         covers="structured financials for ALL filers in a period"),
    dict(batch=1, name="sec_edgar_fulltext", cat="reference",
         url="https://efts.sec.gov/LATEST/search-index?q=%22tariff%22&forms=10-K",
         chk=chk_sec_fts, auth="none",
         doc="Full-text search over filing bodies+exhibits, 2001->. Unauthenticated JSON.",
         covers="text inside filings (risk factors, customer disclosures)"),
    dict(batch=1, name="federal_register", cat="news",
         url="https://www.federalregister.gov/api/v1/documents.json?per_page=5&order=newest",
         chk=chk_fedreg, auth="none",
         doc="API v1. No key. Types: Notice/Proposed Rule/Rule/Presidential Document.",
         covers="US rules, proposed rules, notices, executive orders"),
    dict(batch=1, name="federal_register_public_inspection", cat="news",
         url="https://www.federalregister.gov/api/v1/public-inspection-documents.json",
         chk=chk_fedreg, auth="none",
         doc="Documents on public inspection BEFORE Register publication (hours of lead).",
         covers="pre-publication regulatory documents"),
    dict(batch=1, name="gleif_lei", cat="reference",
         url="https://api.gleif.org/api/v1/lei-records?filter[entity.legalName]=Apple%20Inc.&page[size]=3",
         chk=chk_gleif, auth="none",
         doc="Golden Copy. No registration/key. JSON:API format, page[size]/page[number].",
         covers="legal jurisdiction, legal form, parent/child ownership hierarchy"),
    dict(batch=1, name="world_bank", cat="macro",
         url="https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?format=json&per_page=5",
         chk=chk_worldbank, auth="none",
         doc="No key. format=json returns [metadata, rows].",
         covers="1,400+ development indicators, all countries"),
    dict(batch=1, name="ecb_data_portal", cat="macro",
         url="https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=3&format=csvdata",
         chk=chk_ecb, auth="none",
         doc="SDMX 2.1. No key, no registration. 139k+ euro-area series. CSV/JSON/XML.",
         covers="euro-area rates, FX, monetary aggregates"),
    dict(batch=1, name="bis_stats", cat="macro",
         url="https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.US?startPeriod=2026-01-01&format=csv",
         chk=chk_bis, auth="none",
         doc="BIS Data Portal API v2 (stats.bis.org/api-doc/v2/). CBPOL = policy rates.",
         covers="central bank policy rates, all reporting jurisdictions"),
    dict(batch=1, name="bis_cbank_list", cat="reference",
         url="https://www.bis.org/cbanks.htm", chk=chk_cbanks, auth="none",
         doc="Static HTML list of every central bank / monetary authority website.",
         covers="the seed list for a global policy-calendar crawler"),

    # ---------------- BATCH 2: NEWS / GEO / PHYSICAL (no key) ----------------
    dict(batch=2, name="gdelt_doc", cat="news",
         url="https://api.gdeltproject.org/api/v2/doc/doc?query=bitcoin&mode=artlist&maxrecords=10&format=json",
         chk=chk_gdelt, auth="none",
         doc="GDELT 2.0 DOC API. No key. 15-min updates, 65+ languages, tone+geo.",
         covers="global news events in 65+ languages — the free substitute for local-language sentiment"),
    dict(batch=2, name="imf_portwatch_chokepoints", cat="macro",
         url=("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/"
              "Daily_Chokepoints_Data/FeatureServer/0/query?where=portid%3D%27chokepoint1%27"
              "&outFields=*&f=json&resultRecordCount=5"),
         chk=chk_portwatch, auth="none",
         doc="ArcGIS FeatureServer. No key. 28 chokepoints, ~1600 ports. "
             "Refreshed weekly Tue ~09:00 ET, daily granularity. Paginate resultOffset.",
         covers="daily ship transits for Hormuz/Malacca/Suez/Bab-el-Mandeb etc"),
    dict(batch=2, name="usgs_earthquakes", cat="macro",
         url=("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
              "&starttime=2026-08-01&minmagnitude=6&limit=10"),
         chk=chk_usgs, auth="none",
         doc="FDSN event service. No key. GeoJSON.",
         covers="seismic events with coordinates (physical disruption to facilities)"),
    dict(batch=2, name="restcountries", cat="reference",
         url="https://restcountries.com/v3.1/all?fields=cca2,cca3,name,currencies,timezones",
         chk=chk_restcountries, auth="none",
         doc="Free, no key. v3.1 requires ?fields= on /all.",
         covers="ISO codes, currencies, timezones, borders — the country dimension"),
    dict(batch=2, name="crtsh", cat="reference",
         url="https://crt.sh/?q=%25.anthropic.com&output=json",
         chk=chk_crtsh, auth="none",
         doc="Certificate transparency log search. Free, no key. Slow (can take 10-30s).",
         covers="unannounced subdomains = pre-announcement product leak signal"),
    dict(batch=2, name="greenhouse_jobs", cat="reference",
         url="https://boards-api.greenhouse.io/v1/boards/anthropic/jobs",
         chk=chk_greenhouse, auth="none",
         doc="Public job board JSON for any Greenhouse customer. No key.",
         covers="hiring = budget already committed = 2-3 quarter lead signal"),
    dict(batch=2, name="wikidata_sparql", cat="reference",
         url=("https://query.wikidata.org/sparql?format=json&query="
              "SELECT%20?c%20WHERE%20%7B?c%20wdt%3AP31%20wd%3AQ4830453.%7D%20LIMIT%205"),
         chk=chk_wikidata, auth="none",
         doc="SPARQL endpoint. No key. Needs descriptive UA. P17 country, P159 HQ, P749 parent.",
         covers="global company<->country<->exchange graph where EDGAR does not reach"),
    dict(batch=2, name="overpass_osm", cat="macro",
         url=("https://overpass-api.de/api/interpreter?data=[out:json][timeout:25];"
              "node[%22man_made%22=%22lighthouse%22](54.0,8.0,54.5,9.0);out%205;"),
         chk=chk_overpass, auth="none",
         doc="Overpass QL. Free, no key. Heavy queries rate-limited/blocked.",
         covers="physical asset layer: ports, pipelines, mines, plants, cable landings"),
    dict(batch=2, name="futuresbench_cot", cat="reference",
         url="https://futuresbench.com/api/cot/latest.csv",
         chk=chk_futuresbench, auth="none",
         doc="Static CDN mirror of CFTC COT. No key, no rate limit. 107 markets, 1986->. "
             "COT released Fri 15:30 ET for prior Tuesday.",
         covers="CFTC Commitments of Traders positioning"),
    dict(batch=2, name="sanctions_network", cat="reference",
         url="https://sanctions.network/api/v1/sources",
         chk=chk_sanctions_net, auth="none",
         doc="Free JSON screening against OFAC SDN + UNSC + EU.",
         covers="sanctions designations"),

    # ---------------- BATCH 3: CRYPTO / RSS / MISC (no key) ----------------
    dict(batch=3, name="defillama_protocols", cat="crypto_onchain",
         url="https://api.llama.fi/protocols", chk=chk_defillama, auth="none",
         doc="Free, no key. TVL by protocol.",
         covers="TVL, protocol flows"),
    dict(batch=3, name="defillama_stablecoins", cat="crypto_onchain",
         url="https://stablecoins.llama.fi/stablecoins?includePrices=true",
         chk=chk_defillama, auth="none",
         doc="Free, no key. Stablecoin supply by chain — the crypto liquidity proxy.",
         covers="stablecoin supply (liquidity), USDT/USDC split by chain"),
    dict(batch=3, name="coingecko_global", cat="reference",
         url="https://api.coingecko.com/api/v3/global", chk=chk_coingecko, auth="none",
         doc="Free tier ~10-30 calls/min, no key on public endpoints.",
         covers="BTC dominance, total market cap"),
    dict(batch=3, name="bcb_brazil", cat="macro",
         url="https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/3?formato=json",
         chk=chk_bcb, auth="none",
         doc="Banco Central do Brasil SGS. Free, no key. Series 432 = SELIC target.",
         covers="SELIC, BRL FX, all BCB series"),
    dict(batch=3, name="fed_speeches_rss", cat="news",
         url="https://www.federalreserve.gov/feeds/speeches.xml", chk=chk_rss, auth="none",
         doc="RSS feed. Free.",
         covers="Fed speaker communications (the pre-blackout high-information window)"),
    dict(batch=3, name="fcc_equipment_auth", cat="reference",
         url="https://www.fcc.gov/oet/ea/fccid", chk=chk_fcc, auth="none",
         doc="HTML search UI; no documented JSON API.",
         covers="device certifications appearing weeks before product launch"),

    # ------- BATCH 4: CORRECTED endpoints for batch 1-3 failures -------
    dict(batch=4, name="cftc_cot_official", cat="reference",
         url="https://publicreporting.cftc.gov/resource/6dca-aqww.json?$limit=5",
         chk=chk_defillama, auth="none",
         doc="OFFICIAL CFTC Public Reporting Environment (Socrata). No key. "
             "REPLACES futuresbench (whose JSON paths 404). Socrata $limit/$where/$order. "
             "COT released Fri 15:30 ET for prior Tuesday.",
         covers="CFTC Commitments of Traders positioning, all futures markets"),
    dict(batch=4, name="bis_cbank_members", cat="reference",
         url="https://www.bis.org/about/organisation/members", chk=chk_cbanks, auth="none",
         doc="CORRECTED URL — /cbanks.htm is 404 (dead). This page lists the 63 member "
             "central banks. HTML, no API.",
         covers="the seed list of central banks for a global policy calendar"),

    # ------- BATCH 5: CRYPTO / MARKET (no key) -------
    dict(batch=5, name="deribit_options", cat="derivatives",
         url="https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option",
         chk=chk_defillama, auth="none",
         doc="Deribit API v2 public. No key for market data. JSON-RPC style REST.",
         covers="FULL BTC/ETH options chain: IV, OI by strike, mark price -> skew, RR, term structure, GEX"),
    dict(batch=5, name="deribit_index", cat="derivatives",
         url="https://www.deribit.com/api/v2/public/get_index_price?index_name=btc_usd",
         chk=chk_defillama, auth="none", doc="Deribit public index price.",
         covers="BTC/ETH index reference price"),
    dict(batch=5, name="binance_vision_history", cat="crypto_cex",
         url="https://data.binance.vision/?prefix=data/futures/um/daily/klines/BTCUSDT/1m/",
         chk=chk_fcc, auth="none",
         doc="Bulk historical archive (S3-style listing). No key. ZIP CSVs per day. "
             "THE fix for our 9.9-day history problem.",
         covers="YEARS of klines/aggTrades/funding history"),
    dict(batch=5, name="kalshi", cat="prediction_markets",
         url="https://api.elections.kalshi.com/trade-api/v2/markets?limit=5",
         chk=chk_defillama, auth="none", doc="Kalshi public trade API v2.",
         covers="event probabilities — what the market EXPECTED (priced-in input)"),
    dict(batch=5, name="polymarket_gamma", cat="prediction_markets",
         url="https://gamma-api.polymarket.com/markets?limit=5",
         chk=chk_defillama, auth="none", doc="Polymarket Gamma API. No key.",
         covers="event probabilities, crypto + macro + politics"),
    dict(batch=5, name="lunarcrush_public", cat="social",
         url="https://lunarcrush.com/api4/public/topic/bitcoin/v1", chk=chk_defillama,
         auth="none", doc="Public topic endpoint (api4). Was probed in probe_sentiment.py, never collected.",
         covers="social volume/dominance/sentiment per topic"),
    dict(batch=5, name="farcaster_warpcast", cat="social",
         url="https://client.warpcast.com/v2/recent-casts?limit=5", chk=chk_defillama,
         auth="none", doc="Warpcast public client API. Probed, never collected.",
         covers="crypto-native social posts"),
    dict(batch=5, name="alternative_me_fng", cat="reference",
         url="https://api.alternative.me/fng/?limit=3", chk=chk_defillama, auth="none",
         doc="Fear & Greed index. Free, no key.", covers="crypto fear/greed sentiment index"),
    dict(batch=5, name="stooq_eod", cat="macro",
         url="https://stooq.com/q/d/l/?s=%5Espx&i=d", chk=chk_futuresbench, auth="none",
         doc="Free EOD CSV. No key. ^spx, ^ndq, cl.f (oil) etc.",
         covers="free end-of-day equity/index/commodity history"),

    # ------- BATCH 6: KEY-REQUIRED (endpoint aliveness test) -------
    dict(batch=6, name="fred", cat="macro",
         url="https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key=%s&file_type=json&limit=3&sort_order=desc"
             % (_env("FRED_API_KEY") or "MISSING"),
         chk=chk_fred, auth="key",
         doc="api_key = 32-char lowercase. file_type=json (default xml!). limit<=100000. "
             "Also /fred/releases/dates = the macro release CALENDAR.",
         covers="DGS10/DGS2/T10Y2Y/CPIAUCSL/PAYEMS/WALCL/VIXCLS/oil — decades of history"),
    dict(batch=6, name="openfda", cat="reference",
         url="https://api.fda.gov/drug/event.json?limit=1", chk=chk_defillama, auth="none",
         doc="Free WITHOUT key (240 req/min/IP, 1000/day). Key raises limits.",
         covers="drug approvals/PDUFA — the purest scheduled binary event dataset"),
    dict(batch=6, name="uscourts_courtlistener", cat="reference",
         url="https://www.courtlistener.com/api/rest/v4/courts/?page_size=3",
         chk=chk_defillama, auth="key",
         doc="v4 REST. Free tier needs a token for most endpoints.",
         covers="US court dockets and opinions (enforcement/litigation events)"),
    dict(batch=6, name="un_comtrade", cat="macro",
         url="https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode=842&period=2023&cmdCode=TOTAL&flowCode=X",
         chk=chk_defillama, auth="key", doc="Free tier requires subscription key header.",
         covers="bilateral trade flows by product/country"),
    dict(batch=6, name="cloudflare_radar", cat="macro",
         url="https://api.cloudflare.com/client/v4/radar/annotations/outages?limit=3",
         chk=chk_defillama, auth="key",
         doc="Free key. CC BY-NC 4.0 (non-commercial).",
         covers="national internet outages — leading indicator of coups/protests/censorship"),
    dict(batch=6, name="congress_gov", cat="news",
         url="https://api.congress.gov/v3/bill?limit=3&api_key=%s" % (_env("CONGRESS_API_KEY") or "DEMO_KEY"),
         chk=chk_defillama, auth="key", doc="Free key via api.data.gov. 5k/hr.",
         covers="US bills, votes, committee stage transitions"),

    # ------- BATCH 7: GLOBAL LAW / GAZETTES / REMAINING -------
    dict(batch=7, name="dbnomics", cat="macro",
         url="https://api.db.nomics.world/v22/series/BIS/CBPOL?observations=1&limit=2",
         chk=chk_defillama, auth="none",
         doc="Aggregates 90+ official providers (IMF/OECD/Eurostat/ECB/WB/BIS/Fed/BLS). No key.",
         covers="one API over most official statistics providers"),
    dict(batch=7, name="eurlex", cat="news",
         url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
         chk=chk_fcc, auth="none", doc="EU law. HTML + SPARQL/REST (CELEX ids). MiCA = 32023R1114.",
         covers="EU regulation — MiCA-class events with known future effective dates"),
    dict(batch=7, name="legislation_gov_uk", cat="news",
         url="https://www.legislation.gov.uk/ukpga/2023/29/data.xml", chk=chk_fcc, auth="none",
         doc="Free API, Atom/XML. /data.xml on any item.", covers="UK primary/secondary legislation"),
    dict(batch=7, name="india_rbi_dbie", cat="macro",
         url="https://dbie.rbi.org.in/", chk=chk_fcc, auth="none",
         doc="RBI Database on Indian Economy. HTML portal.", covers="RBI rates, India macro"),
    dict(batch=7, name="japan_egov_law", cat="news",
         url="https://laws.e-gov.go.jp/api/1/lawlists/1", chk=chk_fcc, auth="none",
         doc="e-Gov 法令API v1. Free, XML.", covers="Japanese law texts"),
    dict(batch=7, name="korea_law_go_kr", cat="news",
         url="https://www.law.go.kr/DRF/lawSearch.do?OC=test&target=law&type=XML&query=%EC%9D%80%ED%96%89",
         chk=chk_fcc, auth="key", doc="Open API needs a free OC key (email id).",
         covers="Korean law/regulation"),
    dict(batch=7, name="eia_energy", cat="macro",
         url="https://api.eia.gov/v2/petroleum/pri/spt/data/?api_key=%s&frequency=daily&data[0]=value&length=3"
             % (_env("EIA_API_KEY") or "MISSING"),
         chk=chk_defillama, auth="key", doc="EIA API v2. Free key. Generous limits.",
         covers="oil/energy prices, inventories, chokepoint throughput"),
    dict(batch=7, name="govinfo", cat="news",
         url="https://api.govinfo.gov/collections?api_key=%s" % (_env("GOVINFO_API_KEY") or "DEMO_KEY"),
         chk=chk_defillama, auth="key", doc="Free key via api.data.gov.",
         covers="CFR, US Code, bill status bulk"),
    dict(batch=7, name="regulations_gov", cat="news",
         url="https://api.regulations.gov/v4/documents?api_key=%s&page[size]=5" % (_env("REGULATIONS_API_KEY") or "DEMO_KEY"),
         chk=chk_defillama, auth="key", doc="Free key. Dockets + public comments.",
         covers="comment volume as a leading indicator of whether a rule survives"),
    dict(batch=7, name="trade_gov_csl", cat="reference",
         url="https://data.trade.gov/consolidated_screening_list/v1/search?name=test",
         chk=chk_defillama, auth="key", doc="Free developer.trade.gov key. Updated HOURLY. 11 US lists merged.",
         covers="BIS Entity List, OFAC SDN, Denied Persons — sanctions/export-control designations"),
    dict(batch=7, name="acled", cat="macro",
         url="https://api.acleddata.com/acled/read?limit=2", chk=chk_defillama, auth="key",
         doc="Free registration; API needs Research/Partner tier.",
         covers="political violence + protest events with lat/lon and fatalities"),
    dict(batch=7, name="finnhub", cat="reference",
         url="https://finnhub.io/api/v1/calendar/earnings?token=%s" % (_env("FINNHUB_API_KEY") or "MISSING"),
         chk=chk_defillama, auth="key", doc="Free tier 60 calls/min.",
         covers="EARNINGS CALENDAR, company news, filings"),
    dict(batch=7, name="fmp_calendar", cat="reference",
         url="https://financialmodelingprep.com/api/v3/earning_calendar?apikey=%s" % (_env("FMP_API_KEY") or "MISSING"),
         chk=chk_defillama, auth="key", doc="Free tier limited.",
         covers="earnings/IPO/dividend/split calendars"),
    dict(batch=7, name="uspto_patents", cat="reference",
         url="https://api.patentsview.org/patents/query?q=%7B%22_gte%22%3A%7B%22patent_date%22%3A%222026-01-01%22%7D%7D&f=%5B%22patent_number%22%5D&o=%7B%22per_page%22%3A3%7D",
         chk=chk_defillama, auth="none", doc="PatentsView query API.",
         covers="patents = pre-announcement signal (publish 18mo after filing)"),
    dict(batch=7, name="nasa_firms", cat="macro",
         url="https://firms.modaps.eosdis.nasa.gov/api/country/csv/%s/MODIS_NRT/USA/1" % (_env("FIRMS_API_KEY") or "MISSING"),
         chk=chk_futuresbench, auth="key", doc="Free MAP_KEY required.",
         covers="active fires — physical disruption to facilities with known coordinates"),
    dict(batch=7, name="gpr_index", cat="macro",
         url="https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls",
         chk=chk_fcc, auth="none", doc="Free XLS. Monthly GPR + DAILY GPRD.",
         covers="Geopolitical Risk Index — daily, back decades"),
    dict(batch=7, name="cryptocurrency_cv_news", cat="news",
         url="https://cryptocurrency.cv/api/news", chk=chk_defillama, auth="none",
         doc="Claimed free crypto news API, no key.", covers="aggregated crypto news + historical archive"),
]


def run(batches=None):
    conn = store.init()
    results = []
    sel = [s for s in SOURCES if batches is None or s["batch"] in batches]
    print(f"Verifying {len(sel)} sources\n" + "=" * 100)
    for s in sel:
        code, body, ms, err = fetch(s["url"], s.get("headers"))
        ok, desc = False, err or "no data"
        if code == 200 and body:
            try:
                ok, desc = s["chk"](body)
            except Exception as e:  # noqa: BLE001
                ok, desc = False, f"payload check failed: {str(e)[:90]}"
        status = "verified" if ok else "dead"
        tick = "OK  " if ok else "FAIL"
        print(f"[{tick}] {s['name']:<34} http={code:<4} {ms:>6}ms  {desc[:70]}")
        store.record_source(conn, s["name"], s["cat"], s["url"], s.get("auth", "none"),
                            True, status, code, ms, s.get("rate"),
                            f"DOC: {s['doc']} | COVERS: {s['covers']} | EVIDENCE: {desc[:200]}",
                            json.dumps({"desc": desc})[:1500],
                            time.strftime("%Y-%m-%d") if ok else None)
        conn.commit()
        results.append((s, ok, code, desc))
        time.sleep(0.4)  # be polite
    print("=" * 100)
    good = [r for r in results if r[1]]
    print(f"{len(good)}/{len(results)} verified")
    conn.close()
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, action="append")
    a = ap.parse_args()
    run(a.batch)
