"""Which exchanges can this machine actually reach, keyless, in bulk?

    python scripts/probe_exchanges.py

Bulk means one request returns every symbol. Per-symbol endpoints are useless
for a recorder that wants 200 coins across 20 venues every minute.

Prints status, round trip, and how many symbols came back. A venue that is slow
or partial here is a venue that will be slow or partial at 3am unattended, so
this is the list the recorder gets built against - not a wishlist.
"""
from __future__ import annotations

import concurrent.futures
import json
import sys
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}


def n(d: Any, *path: Any) -> Optional[int]:
    """Walk a path into the payload and count the list at the end."""
    cur = d
    try:
        for p in path:
            cur = cur[p]
        return len(cur)
    except (KeyError, IndexError, TypeError):
        return None


# name, kind, url, counter
VENUES: List[Tuple[str, str, str, Callable[[Any], Optional[int]]]] = [
    ("hyperliquid",   "perp", "https://api.hyperliquid.xyz/info", lambda d: n(d, 0, "universe")),
    ("binance",       "perp", "https://fapi.binance.com/fapi/v1/ticker/bookTicker", len),
    ("binance-spot",  "spot", "https://api.binance.com/api/v3/ticker/bookTicker", len),
    ("bybit",         "perp", "https://api.bybit.com/v5/market/tickers?category=linear", lambda d: n(d, "result", "list")),
    ("bybit-spot",    "spot", "https://api.bybit.com/v5/market/tickers?category=spot", lambda d: n(d, "result", "list")),
    ("okx",           "perp", "https://www.okx.com/api/v5/market/tickers?instType=SWAP", lambda d: n(d, "data")),
    ("okx-aws",       "perp", "https://aws.okx.com/api/v5/market/tickers?instType=SWAP", lambda d: n(d, "data")),
    ("gate",          "perp", "https://api.gateio.ws/api/v4/futures/usdt/tickers", len),
    ("gate-spot",     "spot", "https://api.gateio.ws/api/v4/spot/tickers", len),
    ("kucoin",        "perp", "https://api-futures.kucoin.com/api/v1/contracts/active", lambda d: n(d, "data")),
    ("kucoin-spot",   "spot", "https://api.kucoin.com/api/v1/market/allTickers", lambda d: n(d, "data", "ticker")),
    ("mexc",          "perp", "https://contract.mexc.com/api/v1/contract/ticker", lambda d: n(d, "data")),
    ("bitget",        "perp", "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES", lambda d: n(d, "data")),
    ("htx",           "perp", "https://api.hbdm.com/linear-swap-ex/market/detail/batch_merged?business_type=swap", lambda d: n(d, "ticks")),
    ("kraken-fut",    "perp", "https://futures.kraken.com/derivatives/api/v3/tickers", lambda d: n(d, "tickers")),
    ("kraken-spot",   "spot", "https://api.kraken.com/0/public/AssetPairs", lambda d: n(d, "result")),
    ("deribit",       "perp", "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=future", lambda d: n(d, "result")),
    ("bingx",         "perp", "https://open-api.bingx.com/openApi/swap/v2/quote/ticker", lambda d: n(d, "data")),
    ("phemex",        "perp", "https://api.phemex.com/md/v2/ticker/24hr/all", lambda d: n(d, "result")),
    ("woo",           "perp", "https://api.woo.org/v1/public/futures", lambda d: n(d, "rows")),
    ("dydx",          "perp", "https://indexer.dydx.trade/v4/perpetualMarkets", lambda d: n(d, "markets")),
    ("backpack",      "perp", "https://api.backpack.exchange/api/v1/tickers", len),
    ("paradex",       "perp", "https://api.prod.paradex.trade/v1/markets/summary?market=ALL", lambda d: n(d, "results")),
    ("aevo",          "perp", "https://api.aevo.xyz/statistics", lambda d: len(d) if isinstance(d, list) else None),
    ("bitfinex",      "spot", "https://api-pub.bitfinex.com/v2/tickers?symbols=ALL", len),
    ("cryptocom",     "spot", "https://api.crypto.com/exchange/v1/public/get-tickers", lambda d: n(d, "result", "data")),
    ("bitmart",       "spot", "https://api-cloud.bitmart.com/spot/quotation/v3/tickers", lambda d: n(d, "data")),
    ("coinbase",      "spot", "https://api.exchange.coinbase.com/products", len),
    ("upbit-kr",      "spot", "https://api.upbit.com/v1/market/all", len),
    ("bithumb-kr",    "spot", "https://api.bithumb.com/public/ticker/ALL_KRW", lambda d: n(d, "data")),
    ("coindcx-in",    "spot", "https://api.coindcx.com/exchange/ticker", len),
    ("wazirx-in",     "spot", "https://api.wazirx.com/api/v2/tickers", len),
    ("bitbns-in",     "spot", "https://api.bitbns.com/api/trade/v1/ticker", len),
]


def probe(name: str, kind: str, url: str, counter) -> Dict[str, Any]:
    t0 = time.time()
    try:
        if "hyperliquid" in name:
            req = urllib.request.Request(
                url, data=json.dumps({"type": "metaAndAssetCtxs"}).encode(),
                headers={**UA, "Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        return {"name": name, "kind": kind, "status": f"HTTP {e.code}",
                "ms": int((time.time() - t0) * 1000), "symbols": None}
    except Exception as e:
        return {"name": name, "kind": kind, "status": type(e).__name__,
                "ms": int((time.time() - t0) * 1000), "symbols": None}
    ms = int((time.time() - t0) * 1000)
    try:
        data = json.loads(raw)
    except ValueError:
        return {"name": name, "kind": kind, "status": f"{code} not-json", "ms": ms,
                "symbols": None}
    try:
        cnt = counter(data)
    except Exception:
        cnt = None
    return {"name": name, "kind": kind, "status": str(code), "ms": ms,
            "symbols": cnt, "bytes": len(raw)}


def main() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda v: probe(*v), VENUES))

    ok = [r for r in results if r["status"] == "200" and (r["symbols"] or 0) > 0]
    bad = [r for r in results if r not in ok]

    print(f"\n{'venue':<15}{'type':<7}{'status':<14}{'ms':>7}{'symbols':>10}")
    print("-" * 55)
    for r in sorted(ok, key=lambda x: (x["kind"], -(x["symbols"] or 0))):
        print(f"{r['name']:<15}{r['kind']:<7}{r['status']:<14}{r['ms']:>7}{r['symbols']:>10}")
    if bad:
        print("\nnot usable from this machine:")
        for r in sorted(bad, key=lambda x: x["name"]):
            print(f"  {r['name']:<15}{r['status']:<20}{r['ms']:>6}ms  symbols={r['symbols']}")

    print(f"\n{len(ok)} of {len(results)} venues reachable, keyless, in one bulk call")
    print(f"  perp venues: {sum(1 for r in ok if r['kind'] == 'perp')}")
    print(f"  spot venues: {sum(1 for r in ok if r['kind'] == 'spot')}")
    print(f"  total symbols visible: {sum(r['symbols'] or 0 for r in ok):,}")


if __name__ == "__main__":
    main()
