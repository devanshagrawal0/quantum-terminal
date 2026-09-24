"""Re-label sources after verification, per Dev's decisions.

  geo_blocked  -> the local ISP blocks it. PROVEN by comparing local DNS
                  against Cloudflare's. Expected to work from another region.
  needs_key    -> the endpoint is alive, it just wants a free signup.
                  Flagged for Dev to add the key later.
  removed      -> the URL the research agent gave was wrong or the service is
                  genuinely dead. Replacement recorded where one was found.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "store"))
import store  # noqa: E402

# name -> (new_status, reason)
# 2026-09-13, retried from the US (new PC): kalshi and polymarket_gamma came back
# 200 with real payloads and are now 'verified' (verify_sources.py set that).
# The other two were NOT geo after all - see REMOVED below. Nothing is
# geo-blocked from the US as of that date.
GEO_BLOCKED = {}

NEEDS_KEY = {
    "fred": "free registration at fred.stlouisfed.org — 32-char key. HIGH PRIORITY: decades of macro history.",
    "eia_energy": "free key at api.eia.gov — oil/energy/inventories.",
    "finnhub": "free tier 60 calls/min — EARNINGS CALENDAR.",
    "fmp_calendar": "free tier — earnings/IPO/dividend/split calendars.",
    "trade_gov_csl": "free developer.trade.gov key — 11 US sanctions lists, hourly.",
    "cloudflare_radar": "free key, CC BY-NC — national internet outages.",
    "nasa_firms": "free MAP_KEY — active fires near facilities.",
    "lunarcrush_public": "was free, now 401 — needs an account. Social volume/sentiment.",
    "farcaster_warpcast": "now 401 — needs auth. Crypto-native social.",
    "korea_law_go_kr": "free OC key (email id) for the DRF open API.",
}

# name -> (reason, replacement_name_or_None)
REMOVED = {
    "restcountries": ("v3.1 returns 'This API version has been deprecated'. v5 needs a key "
                      "and gives only 500 req/MONTH.", "world_bank_countries"),
    "sanctions_network": ("Not an API — returns the same HTML page for every path.",
                          "ofac_sdn_direct"),
    "futuresbench_cot": ("All JSON paths 404. Site is HTML only.", "cftc_cot_official"),
    "bis_cbank_list": ("bis.org/cbanks.htm is 404 (dead URL from the research agent).",
                       "bis_cbank_members"),
    "dbnomics": ("Wrong path — /series/BIS/CBPOL 404s. The API itself is alive.",
                 "dbnomics_providers"),
    "uspto_patents": ("search.patentsview.org has NO DNS record anywhere (not a block — "
                      "the hostname does not exist).", "patentsview_api"),
    "acled": ("api.acleddata.com has NO DNS record anywhere. Real host is acleddata.com, "
              "and the API needs a Research-tier account.", None),
    "cryptocurrency_cv_news": ("403 — bot-blocked.", None),
    "eurlex": ("HTTP 202 challenge page — needs browser-like headers.", None),
    "legislation_gov_uk": ("HTTP 202 challenge page — needs browser-like headers.", None),
    # were labelled geo_blocked on one network; retried from another region 2026-09-13
    "fcc_equipment_auth": ("HTTP 403 from the US too — bot-blocked HTML search UI, and it "
                           "never had a JSON API. Not a geo issue.", None),
    "india_rbi_dbie": ("SSL certificate is not valid for dbie.rbi.org.in from the US as well "
                       "— their certificate, not a geo block. HTML portal, no API.", None),
}

# Replacements that were live-tested and returned real data.
REPLACEMENTS = [
    dict(name="world_bank_countries", cat="reference",
         url="https://api.worldbank.org/v2/country?format=json&per_page=300",
         covers="ISO2/ISO3 codes, region, income group, capital, lat/lon for 295 countries",
         doc="No key. Replaces the deprecated restcountries. Returns [meta, rows].",
         evidence="http=200, 295 countries, first=Aruba/ABW/AW"),
    dict(name="ofac_sdn_direct", cat="reference",
         url="https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML",
         covers="OFAC SDN sanctions designations (the authoritative source)",
         doc="No key. 29 MB XML. Replaces sanctions.network which is not an API.",
         evidence="http=200, 28,969,226 bytes of sdnList XML"),
    dict(name="opensanctions_index", cat="reference",
         url="https://data.opensanctions.org/datasets/latest/index.json",
         covers="consolidated OFAC + EU + UN + UK + PEP lists in one schema",
         doc="Free for non-commercial; a licence is required for business use.",
         evidence="http=200, 2 MB dataset index"),
    dict(name="dbnomics_providers", cat="macro",
         url="https://api.db.nomics.world/v22/providers",
         covers="47,062 datasets / 1.7bn series across 90+ official providers (IMF, OECD, Eurostat, ECB, WB, BIS, Fed, BLS)",
         doc="No key. My earlier /series path was wrong, not the API.",
         evidence="http=200, nb_datasets=47062, nb_series=1725529719"),
]


def main():
    conn = store.init()
    print("RECLASSIFYING\n" + "=" * 92)

    for n, why in GEO_BLOCKED.items():
        conn.execute("UPDATE source SET status='geo_blocked', notes=notes||' || GEO: '||? WHERE name=?",
                     (why, n))
        print(f"  geo_blocked  {n:<32} {why[:52]}")

    for n, why in NEEDS_KEY.items():
        conn.execute("UPDATE source SET status='needs_key', notes=notes||' || KEY: '||? WHERE name=?",
                     (why, n))
        print(f"  needs_key    {n:<32} {why[:52]}")

    for n, (why, rep) in REMOVED.items():
        conn.execute("UPDATE source SET status='removed', notes=notes||' || REMOVED: '||? WHERE name=?",
                     (why + (f" REPLACED BY: {rep}" if rep else " NO REPLACEMENT YET"), n))
        print(f"  removed      {n:<32} -> {rep or 'NO REPLACEMENT'}")

    for r in REPLACEMENTS:
        store.record_source(conn, r["name"], r["cat"], r["url"], "none", True, "verified",
                            200, None, None,
                            f"DOC: {r['doc']} | COVERS: {r['covers']} | EVIDENCE: {r['evidence']}",
                            None, "2026-09-02")
        print(f"  ADDED        {r['name']:<32} {r['covers'][:52]}")

    conn.commit()
    print("=" * 92)
    for s, c in conn.execute(
        "SELECT status, COUNT(*) FROM source GROUP BY status ORDER BY COUNT(*) DESC"
    ):
        print(f"  {s:<14} {c}")
    conn.close()


if __name__ == "__main__":
    main()
