"""Macro / economic series -> macro_series table.

RATE LIMITS (from docs / observed):
  ECB Data Portal  no key, no published cap. SDMX. Poll daily.
  BIS stats v2     no key. SDMX. Poll daily (policy rates change rarely).
  World Bank       no key, no published cap. Annual data — poll weekly.
  DBnomics         no key. Aggregates 90+ providers.
  BCB Brazil       no key, generous.
  Stooq            free EOD CSV, no key. Be gentle: 1 req/s.
  GPR index        static XLS, updated monthly (daily series inside).

Everything lands in one table: (source, series_id, ts_ms, value).
One shape for every provider so downstream code does not care who supplied it.

Run:  python data_layer/collectors/macro_sources.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "store"))
import store  # noqa: E402

UA = {"User-Agent": store.user_agent()}


def http(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def _ts(s):
    s = str(s).strip()
    for f in ("%Y-%m-%d", "%Y-%m", "%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return int(datetime.strptime(s, f).replace(tzinfo=timezone.utc).timestamp() * 1000)
        except ValueError:
            continue
    return None


def _write(conn, source, rows):
    """rows = (series_id, ts_ms, value, unit, geo)"""
    now = int(time.time() * 1000)
    return store.insert_many(conn, "macro_series",
        ["source", "series_id", "ts_ms", "value", "unit", "geo", "observed_at"],
        [(source, r[0], r[1], r[2], r[3], r[4], now) for r in rows if r[1] is not None],
        replace=True)


def _csv_rows(text):
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return [], []
    hdr = [h.strip().strip('"') for h in lines[0].split(",")]
    return hdr, [[c.strip().strip('"') for c in l.split(",")] for l in lines[1:]]


# ------------------------------------------------------------- collectors

ECB_SERIES = {
    "EXR/D.USD.EUR.SP00.A": "EURUSD",
    "FM/D.U2.EUR.4F.KR.MRR_FR.LEV": "ECB_MRO_RATE",
    "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y": "EA_10Y_YIELD",
}


def ecb(conn):
    n = 0
    for key, sid in ECB_SERIES.items():
        try:
            t = http(f"https://data-api.ecb.europa.eu/service/data/{key}"
                     f"?lastNObservations=500&format=csvdata", 60).decode("utf-8", "replace")
        except Exception:
            continue
        hdr, rows = _csv_rows(t)
        if "TIME_PERIOD" not in hdr or "OBS_VALUE" not in hdr:
            continue
        ti, vi = hdr.index("TIME_PERIOD"), hdr.index("OBS_VALUE")
        out = []
        for r in rows:
            if len(r) <= max(ti, vi):
                continue
            try:
                out.append((sid, _ts(r[ti]), float(r[vi]), None, "EA"))
            except ValueError:
                continue
        n += _write(conn, "ecb", out)
        conn.commit()
    return n


def bis_policy_rates(conn):
    """Central bank policy rates for every reporting jurisdiction."""
    n = 0
    for geo in ("US", "XM", "GB", "JP", "CN", "IN", "BR", "AU", "CA", "CH", "KR"):
        try:
            t = http(f"https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.{geo}"
                     f"?startPeriod=2015-01-01&format=csv", 60).decode("utf-8", "replace")
        except Exception:
            continue
        hdr, rows = _csv_rows(t)
        if "TIME_PERIOD" not in hdr or "OBS_VALUE" not in hdr:
            continue
        ti, vi = hdr.index("TIME_PERIOD"), hdr.index("OBS_VALUE")
        out = []
        for r in rows:
            if len(r) <= max(ti, vi):
                continue
            try:
                out.append((f"POLICY_RATE_{geo}", _ts(r[ti]), float(r[vi]), "pct", geo))
            except ValueError:
                continue
        n += _write(conn, "bis", out)
        conn.commit()
        time.sleep(0.3)
    return n


def bcb_brazil(conn):
    n = 0
    for code, sid in ((432, "SELIC_TARGET"), (1, "USDBRL"), (433, "IPCA_MoM")):
        try:
            d = json.loads(http(
                f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
                f"?formato=json&dataInicial=01/01/2018", 60))
        except Exception:
            continue
        out = []
        for r in d:
            try:
                out.append((sid, _ts(r["data"]), float(r["valor"]), None, "BR"))
            except (ValueError, KeyError):
                continue
        n += _write(conn, "bcb", out)
        conn.commit()
    return n


WB_INDICATORS = {"NY.GDP.MKTP.KD.ZG": "GDP_GROWTH", "FP.CPI.TOTL.ZG": "CPI_INFLATION"}


def world_bank(conn):
    n = 0
    for ind, sid in WB_INDICATORS.items():
        try:
            d = json.loads(http(
                f"https://api.worldbank.org/v2/country/all/indicator/{ind}"
                f"?format=json&per_page=2000&date=2015:2026", 90))
        except Exception:
            continue
        if not isinstance(d, list) or len(d) < 2 or not d[1]:
            continue
        out = []
        for r in d[1]:
            if r.get("value") is None:
                continue
            out.append((f"{sid}_{r['country']['id']}", _ts(r.get("date")),
                        float(r["value"]), "pct", r["country"]["id"]))
        n += _write(conn, "worldbank", out)
        conn.commit()
    return n


def stooq(conn):
    """Free EOD for indices and commodities — our only non-crypto price history."""
    n = 0
    for sym, sid in (("^spx", "SPX"), ("^ndq", "NASDAQ"), ("^vix", "VIX"),
                     ("cl.f", "WTI_OIL"), ("gc.f", "GOLD"), ("dx.f", "DOLLAR_INDEX")):
        try:
            t = http(f"https://stooq.com/q/d/l/?s={sym}&i=d", 60).decode("utf-8", "replace")
        except Exception:
            continue
        hdr, rows = _csv_rows(t)
        if "Date" not in hdr or "Close" not in hdr:
            continue
        di, ci = hdr.index("Date"), hdr.index("Close")
        out = []
        for r in rows:
            if len(r) <= max(di, ci):
                continue
            try:
                out.append((sid, _ts(r[di]), float(r[ci]), None, None))
            except ValueError:
                continue
        n += _write(conn, "stooq", out)
        conn.commit()
        time.sleep(1.0)   # be gentle, free service
    return n


def dbnomics(conn):
    """One API over 90+ official providers. Pull a few high-value series."""
    n = 0
    for sid, path in (("US_10Y", "FED/H15/RIFLGFCY10_N.B"),
                      ("US_FEDFUNDS", "FED/H15/RIFSPFF_N.D")):
        try:
            d = json.loads(http(
                f"https://api.db.nomics.world/v22/series/{path}?observations=1", 60))
        except Exception:
            continue
        for s in d.get("series", {}).get("docs", []):
            per, val = s.get("period", []), s.get("value", [])
            out = []
            for p, v in zip(per, val):
                if v in (None, "NA"):
                    continue
                try:
                    out.append((sid, _ts(p), float(v), None, "US"))
                except ValueError:
                    continue
            n += _write(conn, "dbnomics", out)
        conn.commit()
    return n


COLLECTORS = [
    ("ecb", ecb),
    ("bis_policy_rates", bis_policy_rates),
    ("bcb_brazil", bcb_brazil),
    ("world_bank", world_bank),
    ("stooq", stooq),
    ("dbnomics", dbnomics),
]


def run_once(conn, verbose=True):
    total = 0
    for name, fn in COLLECTORS:
        t0 = time.time()
        try:
            n = fn(conn)
            store.log_run(conn, f"macro:{name}", True, n, int((time.time() - t0) * 1000))
            total += n
            if verbose:
                print(f"  {name:<20} +{n:<8} points  ({time.time()-t0:.1f}s)")
        except Exception as e:  # noqa: BLE001
            store.log_run(conn, f"macro:{name}", False, 0,
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
        print(f"macro sources: one pass ({len(COLLECTORS)} collectors)")
        print(f"total +{run_once(conn)} data points")
        conn.close()
        return
    while True:
        t0 = time.time()
        n = run_once(conn, verbose=False)
        print(f"[{time.strftime('%H:%M:%S')}] +{n} points", flush=True)
        time.sleep(max(60.0, a.interval - (time.time() - t0)))


if __name__ == "__main__":
    main()
