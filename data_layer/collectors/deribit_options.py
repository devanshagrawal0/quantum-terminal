"""Deribit options chain -> option_quote + feat_options.

We had ZERO options data (only the DVOL index). This is the whole surface.

DOCUMENTATION READ BEFORE WRITING (2026-09-03):
  endpoint : https://www.deribit.com/api/v2/public/get_book_summary_by_currency
  auth     : none for public market data
  rate     : 20 req/s for non-matching-engine endpoints; public requests are
             limited per-IP. We make 2 calls per cycle (BTC, ETH), so this is
             ~0.003% of the allowance. Not a constraint.
  response : verified live — 976 BTC instruments in ONE call, fields:
             instrument_name, mark_iv, mark_price, bid_price, ask_price,
             open_interest, volume, underlying_price, underlying_index
  naming   : BTC-26MAR27-104000-C  =  CCY-EXPIRY-STRIKE-TYPE

DELTA: not returned by this endpoint, and fetching greeks per instrument would
be 976 calls. We compute Black-Scholes delta ourselves from (mark_iv, strike,
underlying, time-to-expiry, r=0). That is exact, free, and one call.

Derived features written to feat_options:
  atm_iv_7d / 30d / 90d   ATM implied vol by tenor
  rr_25d                  25-delta risk reversal (call IV - put IV)
  skew                    (put IV - call IV) / ATM  at 25 delta
  term_ratio_30_7         30d IV / 7d IV  (inversion = near-term stress)
  put_call_ratio          put OI / call OI
  max_pain                strike where option holders lose the most
  gex                     dealer gamma exposure proxy, sum(gamma * OI * S^2)

Run:  python data_layer/collectors/deribit_options.py            # once
      python data_layer/collectors/deribit_options.py --interval 300
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "store"))
import store  # noqa: E402

UA = {"User-Agent": "quant-research-bot" + ((" contact:" + __import__("os").environ["CONTACT_EMAIL"]) if __import__("os").environ.get("CONTACT_EMAIL") else "")}
API = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={}&kind=option"
MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def _ndist(x):
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _npdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_delta_gamma(S, K, T, sigma, is_call):
    """Black-Scholes delta and gamma, r=0 (crypto options are ~zero-rate)."""
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return None, None
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    delta = _ndist(d1) if is_call else _ndist(d1) - 1.0
    gamma = _npdf(d1) / (S * sigma * math.sqrt(T))
    return delta, gamma


def parse_instrument(name):
    """BTC-26MAR27-104000-C -> (expiry_ms, strike, 'C')"""
    p = name.split("-")
    if len(p) != 4:
        return None, None, None
    ds, strike, typ = p[1], p[2], p[3]
    try:
        day = int(ds[:-5]); mon = MONTHS[ds[-5:-2]]; yr = 2000 + int(ds[-2:])
        exp = int(datetime(yr, mon, day, 8, 0, tzinfo=timezone.utc).timestamp() * 1000)
        return exp, float(strike), typ
    except (ValueError, KeyError):
        return None, None, None


def fetch(ccy):
    raw = urllib.request.urlopen(
        urllib.request.Request(API.format(ccy), headers=UA), timeout=40).read()
    return json.loads(raw).get("result", [])


def _interp_atm(by_tenor, target_days):
    """ATM IV at a target tenor, interpolated between the two nearest expiries."""
    pts = sorted((d, iv) for d, iv in by_tenor.items() if iv)
    if not pts:
        return None
    if len(pts) == 1:
        return pts[0][1]
    below = [p for p in pts if p[0] <= target_days]
    above = [p for p in pts if p[0] > target_days]
    if not below:
        return above[0][1]
    if not above:
        return below[-1][1]
    (d0, v0), (d1, v1) = below[-1], above[0]
    if d1 == d0:
        return v0
    w = (target_days - d0) / (d1 - d0)
    return v0 + w * (v1 - v0)


def compute(rows, now_ms):
    """Turn the raw chain into the option features."""
    opts = []
    for r in rows:
        exp, strike, typ = parse_instrument(r.get("instrument_name", ""))
        if exp is None:
            continue
        S = r.get("underlying_price") or 0
        iv = (r.get("mark_iv") or 0) / 100.0          # Deribit gives percent
        T = max((exp - now_ms) / 86_400_000.0, 0) / 365.0
        d, g = bs_delta_gamma(S, strike, T, iv, typ == "C")
        opts.append(dict(inst=r["instrument_name"], exp=exp, K=strike, typ=typ,
                         S=S, iv=iv, oi=r.get("open_interest") or 0,
                         vol=r.get("volume") or 0, mark=r.get("mark_price"),
                         bid=r.get("bid_price"), ask=r.get("ask_price"),
                         delta=d, gamma=g, tte=T * 365.0))
    if not opts:
        return opts, {}

    S = max((o["S"] for o in opts), default=0)
    feats = {}

    # ATM IV per expiry -> interpolate to standard tenors
    atm_by_tenor = {}
    for exp in {o["exp"] for o in opts}:
        grp = [o for o in opts if o["exp"] == exp and o["iv"] > 0]
        if not grp:
            continue
        days = grp[0]["tte"]
        nearest = min(grp, key=lambda o: abs(o["K"] - S))
        same_k = [o for o in grp if abs(o["K"] - nearest["K"]) < 1e-9]
        atm_by_tenor[days] = sum(o["iv"] for o in same_k) / len(same_k)
    for tag, d in (("atm_iv_7d", 7), ("atm_iv_30d", 30), ("atm_iv_90d", 90)):
        v = _interp_atm(atm_by_tenor, d)
        if v:
            feats[tag] = round(v * 100, 4)
    if feats.get("atm_iv_30d") and feats.get("atm_iv_7d"):
        feats["term_ratio_30_7"] = round(feats["atm_iv_30d"] / feats["atm_iv_7d"], 4)

    # 25-delta risk reversal + skew, on the expiry nearest 30 days
    cand = [o for o in opts if o["delta"] is not None and o["iv"] > 0 and 5 < o["tte"] < 75]
    if cand:
        target = min({o["exp"] for o in cand},
                     key=lambda e: abs(next(o["tte"] for o in cand if o["exp"] == e) - 30))
        grp = [o for o in cand if o["exp"] == target]
        calls = [o for o in grp if o["typ"] == "C"]
        puts = [o for o in grp if o["typ"] == "P"]
        if calls and puts:
            c25 = min(calls, key=lambda o: abs(o["delta"] - 0.25))
            p25 = min(puts, key=lambda o: abs(o["delta"] + 0.25))
            feats["rr_25d"] = round((c25["iv"] - p25["iv"]) * 100, 4)
            atm = feats.get("atm_iv_30d")
            if atm:
                feats["skew"] = round((p25["iv"] - c25["iv"]) * 100 / atm, 4)
            feats["bf_25d"] = round(((c25["iv"] + p25["iv"]) / 2 * 100) - (atm or 0), 4)

    # put/call open interest ratio
    coi = sum(o["oi"] for o in opts if o["typ"] == "C")
    poi = sum(o["oi"] for o in opts if o["typ"] == "P")
    if coi > 0:
        feats["put_call_ratio"] = round(poi / coi, 4)

    # max pain: strike minimising total in-the-money value to holders
    strikes = sorted({o["K"] for o in opts})
    if strikes and S:
        near = [k for k in strikes if 0.5 * S < k < 1.8 * S] or strikes
        pain = {}
        for k in near:
            tot = 0.0
            for o in opts:
                if o["typ"] == "C" and k > o["K"]:
                    tot += (k - o["K"]) * o["oi"]
                elif o["typ"] == "P" and k < o["K"]:
                    tot += (o["K"] - k) * o["oi"]
            pain[k] = tot
        feats["max_pain"] = min(pain, key=pain.get)

    # dealer gamma exposure proxy: sum(gamma * OI * S^2), calls +, puts -
    gex = 0.0
    for o in opts:
        if o["gamma"] and o["oi"]:
            gex += o["gamma"] * o["oi"] * S * S * (1 if o["typ"] == "C" else -1)
    feats["gex"] = round(gex, 2)
    return opts, feats


def run_once(conn, currencies=("BTC", "ETH")):
    vid = store.venue_id(conn, "deribit", kind="options")
    now = int(time.time() * 1000)
    total = 0
    for ccy in currencies:
        t0 = time.time()
        try:
            rows = fetch(ccy)
        except Exception as e:  # noqa: BLE001
            store.log_run(conn, f"deribit:{ccy}", False, 0, 0, str(e)[:150])
            print(f"  {ccy}: FETCH FAILED {str(e)[:70]}")
            continue
        aid = store.asset_id(conn, ccy)
        opts, feats = compute(rows, now)

        store.insert_many(conn, "option_quote",
            ["ts_ms", "venue_id", "asset_id", "instrument", "expiry_ms", "strike",
             "opt_type", "bid", "ask", "mark", "mark_iv", "open_interest", "volume",
             "underlying", "delta", "tte_days"],
            [(now, vid, aid, o["inst"], o["exp"], o["K"], o["typ"], o["bid"], o["ask"],
              o["mark"], o["iv"] * 100, o["oi"], o["vol"], o["S"], o["delta"], o["tte"])
             for o in opts], replace=True)

        if feats:
            cols = ["ts_ms", "asset_id"] + list(feats)
            store.insert_many(conn, "feat_options", cols,
                              [tuple([now, aid] + list(feats.values()))], replace=True)
        conn.commit()
        store.log_run(conn, f"deribit:{ccy}", True, len(opts), int((time.time() - t0) * 1000))
        total += len(opts)
        print(f"  {ccy}: {len(opts)} instruments | " +
              " ".join(f"{k}={v}" for k, v in list(feats.items())[:8]))
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=0)
    a = ap.parse_args()
    conn = store.init()
    if a.interval <= 0:
        run_once(conn)
        conn.close()
        return
    print(f"deribit options: every {a.interval:.0f}s")
    while True:
        t0 = time.time()
        try:
            run_once(conn)
        except Exception as e:  # noqa: BLE001
            print("cycle error:", str(e)[:150])
        time.sleep(max(5.0, a.interval - (time.time() - t0)))


if __name__ == "__main__":
    main()
