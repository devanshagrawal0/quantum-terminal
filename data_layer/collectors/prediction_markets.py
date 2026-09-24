"""Kalshi + Polymarket -> prediction_market table.

WHY THIS MATTERS: these are the only direct read on what the market EXPECTS.
Every "is this already priced in?" question needs a prior, and a prediction
market IS that prior, quoted in probability. Without it, "surprise" can only
be guessed at from price drift.

GEO NOTE: both were unreachable from one network whose ISP DNS-hijacked them
to a block page. Confirmed working from another region on 2026-09-09.

FIELD NAMES VERIFIED LIVE (2026-09-09), not assumed:
  Kalshi     yes_bid_dollars / yes_ask_dollars / last_price_dollars,
             volume_fp / open_interest_fp, close_time, status, ticker, title
             (the old yes_bid / volume / open_interest names are GONE)
  Polymarket question, outcomes, outcomePrices (JSON string array),
             bestBid/bestAsk, volume, liquidity, endDate, conditionId

RATE LIMITS: neither publishes a hard public cap. Kalshi pages at 1000/req,
Polymarket at 500. We poll every 15 min and page politely.

Run:  python data_layer/collectors/prediction_markets.py
      python data_layer/collectors/prediction_markets.py --interval 900
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

UA = {"User-Agent": "quant-research-bot" + ((" contact:" + __import__("os").environ["CONTACT_EMAIL"]) if __import__("os").environ.get("CONTACT_EMAIL") else "")}


def http(url, timeout=45):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def _ts(s):
    if not s:
        return None
    try:
        return int(datetime.strptime(str(s).replace("Z", "+0000"),
                                     "%Y-%m-%dT%H:%M:%S%z").timestamp() * 1000)
    except ValueError:
        pass
    for f in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(str(s), f).replace(tzinfo=timezone.utc)
                       .timestamp() * 1000)
        except ValueError:
            continue
    return None


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def kalshi(conn, max_pages=8):
    """Page through open Kalshi markets."""
    now = int(time.time() * 1000)
    rows, cursor, pages = [], None, 0
    while pages < max_pages:
        url = "https://api.elections.kalshi.com/trade-api/v2/markets?limit=1000&status=open"
        if cursor:
            url += f"&cursor={cursor}"
        try:
            d = json.loads(http(url, 60))
        except Exception:
            break
        mk = d.get("markets", [])
        if not mk:
            break
        for m in mk:
            yes = _f(m.get("last_price_dollars"))
            rows.append(("kalshi", m.get("ticker"), now, m.get("title"),
                         m.get("event_ticker"), yes,
                         (1 - yes) if yes is not None else None,
                         _f(m.get("yes_bid_dollars")), _f(m.get("yes_ask_dollars")),
                         _f(m.get("volume_fp")), _f(m.get("liquidity_dollars")),
                         _f(m.get("open_interest_fp")), _ts(m.get("close_time")),
                         m.get("status")))
        cursor = d.get("cursor")
        pages += 1
        if not cursor:
            break
        time.sleep(0.4)
    return store.insert_many(conn, "prediction_market",
        ["venue", "market_id", "ts_ms", "question", "category", "yes_price", "no_price",
         "yes_bid", "yes_ask", "volume", "liquidity", "open_interest", "close_ts", "status"],
        rows, replace=True)


def polymarket(conn, max_pages=10):
    now = int(time.time() * 1000)
    rows, offset, pages = [], 0, 0
    while pages < max_pages:
        try:
            d = json.loads(http(
                f"https://gamma-api.polymarket.com/markets?limit=500&offset={offset}"
                f"&closed=false&order=volume&ascending=false", 60))
        except Exception:
            break
        if not d:
            break
        for m in d:
            yes = no = None
            try:
                prices = json.loads(m.get("outcomePrices") or "[]")
                outs = json.loads(m.get("outcomes") or "[]")
                if len(prices) == 2 and len(outs) == 2:
                    idx = 0 if str(outs[0]).lower() == "yes" else 1
                    yes, no = _f(prices[idx]), _f(prices[1 - idx])
            except (json.JSONDecodeError, TypeError):
                pass
            rows.append(("polymarket", m.get("conditionId") or str(m.get("id")), now,
                         m.get("question"), m.get("category"), yes, no,
                         _f(m.get("bestBid")), _f(m.get("bestAsk")),
                         _f(m.get("volume")), _f(m.get("liquidity")), None,
                         _ts(m.get("endDate")),
                         "open" if m.get("active") else "closed"))
        offset += 500
        pages += 1
        time.sleep(0.4)
    return store.insert_many(conn, "prediction_market",
        ["venue", "market_id", "ts_ms", "question", "category", "yes_price", "no_price",
         "yes_bid", "yes_ask", "volume", "liquidity", "open_interest", "close_ts", "status"],
        rows, replace=True)


def run_once(conn, verbose=True):
    total = 0
    for name, fn in (("kalshi", kalshi), ("polymarket", polymarket)):
        t0 = time.time()
        try:
            n = fn(conn)
            conn.commit()
            store.log_run(conn, f"pred:{name}", True, n, int((time.time() - t0) * 1000))
            total += n
            if verbose:
                print(f"  {name:<12} +{n:<7} markets  ({time.time()-t0:.1f}s)")
        except Exception as e:  # noqa: BLE001
            conn.commit()
            store.log_run(conn, f"pred:{name}", False, 0,
                          int((time.time() - t0) * 1000), str(e)[:180])
            print(f"  {name:<12} ERROR {str(e)[:70]}")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=0)
    a = ap.parse_args()
    conn = store.init()
    if a.interval <= 0:
        print("prediction markets: one pass")
        print(f"total +{run_once(conn)} markets")
        conn.close()
        return
    while True:
        t0 = time.time()
        n = run_once(conn, verbose=False)
        print(f"[{time.strftime('%H:%M:%S')}] +{n} markets", flush=True)
        time.sleep(max(60.0, a.interval - (time.time() - t0)))


if __name__ == "__main__":
    main()
