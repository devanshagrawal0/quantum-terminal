"""What can we actually reach for crowd data, keyless, from this machine?

    python scripts/probe_sentiment.py

Two very different families here, and they are not equally useful:

  WHAT PEOPLE SAY   forums, Reddit, Telegram, social counts. Cheap, loud, and
                    the documented failure case - sentiment scores mostly track
                    price rather than lead it.

  WHAT PEOPLE DO    positioning ratios, prediction-market odds, open interest,
                    real wallet positions. Money is already committed, so it is
                    a claim someone paid to make.

Both are collected. They are labelled so we never quietly treat one as the other.
"""
from __future__ import annotations

import concurrent.futures
import json
import time
import urllib.request
from typing import Any, Callable, List, Optional, Tuple

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}


def count(d: Any, *path) -> Optional[int]:
    cur = d
    try:
        for p in path:
            cur = cur[p]
        return len(cur)
    except Exception:
        return None


# family, name, url, counter (None = just report status/size), post body
TARGETS: List[Tuple[str, str, str, Optional[Callable], Optional[dict]]] = [
    # ---------- what people DO with money ----------
    ("money", "binance long/short accounts",
     "https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=1h&limit=3", len, None),
    ("money", "binance top trader positions",
     "https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol=BTCUSDT&period=1h&limit=3", len, None),
    ("money", "binance taker buy/sell",
     "https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=1h&limit=3", len, None),
    ("money", "binance open interest history",
     "https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1h&limit=3", len, None),
    ("money", "bybit account ratio",
     "https://api.bybit.com/v5/market/account-ratio?category=linear&symbol=BTCUSDT&period=1h&limit=3",
     lambda d: count(d, "result", "list"), None),
    ("money", "polymarket markets",
     "https://gamma-api.polymarket.com/markets?limit=5&closed=false", len, None),
    ("money", "polymarket clob",
     "https://clob.polymarket.com/markets", lambda d: count(d, "data"), None),
    ("money", "kalshi markets",
     "https://api.elections.kalshi.com/trade-api/v2/markets?limit=5",
     lambda d: count(d, "markets"), None),
    ("money", "deribit BTC option book",
     "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option",
     lambda d: count(d, "result"), None),
    ("money", "deribit DVOL index",
     "https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&start_timestamp=1&end_timestamp=99999999999999&resolution=3600",
     lambda d: count(d, "result", "data"), None),
    ("money", "hyperliquid leaderboard",
     "https://api.hyperliquid.xyz/info", lambda d: count(d, "leaderboardRows"),
     {"type": "leaderboard"}),
    ("money", "hyperliquid wallet position (read any address)",
     "https://api.hyperliquid.xyz/info", lambda d: count(d, "assetPositions"),
     {"type": "clearinghouseState", "user": "0x0000000000000000000000000000000000000001"}),

    # ---------- what people SAY ----------
    ("say", "reddit json (unauth)",
     "https://www.reddit.com/r/CryptoCurrency/new.json?limit=5",
     lambda d: count(d, "data", "children"), None),
    ("say", "reddit RSS (unauth)",
     "https://www.reddit.com/r/CryptoCurrency/new/.rss", None, None),
    ("say", "old.reddit RSS",
     "https://old.reddit.com/r/CryptoCurrency/new/.rss", None, None),
    ("say", "reddit r/SatoshiStreetBets RSS",
     "https://www.reddit.com/r/SatoshiStreetBets/new/.rss", None, None),
    ("say", "telegram public channel web",
     "https://t.me/s/whale_alert_io", None, None),
    ("say", "telegram channel 2",
     "https://t.me/s/binance_announcements", None, None),
    ("say", "4chan /biz/ catalog",
     "https://a.4cdn.org/biz/catalog.json", len, None),
    ("say", "bitcointalk RSS",
     "https://bitcointalk.org/index.php?type=rss;action=.xml;board=1", None, None),
    ("say", "stocktwits BTC stream",
     "https://api.stocktwits.com/api/2/streams/symbol/BTC.X.json",
     lambda d: count(d, "messages"), None),
    ("say", "coingecko trending searches",
     "https://api.coingecko.com/api/v3/search/trending", lambda d: count(d, "coins"), None),
    ("say", "fear and greed",
     "https://api.alternative.me/fng/?limit=3", lambda d: count(d, "data"), None),
    ("say", "cryptopanic free posts",
     "https://cryptopanic.com/api/v1/posts/?public=true", lambda d: count(d, "results"), None),
    ("say", "farcaster warpcast trending",
     "https://client.warpcast.com/v2/recent-casts?limit=5", None, None),
    ("say", "lunarcrush public",
     "https://lunarcrush.com/api4/public/topic/bitcoin/v1", None, None),
]


def probe(family: str, name: str, url: str, counter, post) -> dict:
    t0 = time.time()
    try:
        data = json.dumps(post).encode() if post else None
        hdr = dict(UA)
        if post:
            hdr["Content-Type"] = "application/json"
        with urllib.request.urlopen(
                urllib.request.Request(url, data=data, headers=hdr), timeout=20) as r:
            raw, code = r.read(), r.status
    except urllib.error.HTTPError as e:
        return {"family": family, "name": name, "status": f"HTTP {e.code}",
                "ms": int((time.time() - t0) * 1000), "n": None}
    except Exception as e:
        return {"family": family, "name": name, "status": type(e).__name__,
                "ms": int((time.time() - t0) * 1000), "n": None}
    ms = int((time.time() - t0) * 1000)
    n = None
    if counter:
        try:
            n = counter(json.loads(raw))
        except Exception:
            n = None
    return {"family": family, "name": name, "status": str(code), "ms": ms,
            "n": n, "kb": len(raw) // 1024}


def main() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        res = list(pool.map(lambda t: probe(*t), TARGETS))

    for fam, title in (("money", "WHAT PEOPLE DO WITH MONEY"),
                       ("say", "WHAT PEOPLE SAY")):
        print(f"\n{title}")
        print(f"  {'source':<45}{'status':<12}{'ms':>7}{'items':>8}{'KB':>6}")
        print("  " + "-" * 76)
        for r in [x for x in res if x["family"] == fam]:
            n = "-" if r["n"] is None else str(r["n"])
            kb = r.get("kb", "")
            print(f"  {r['name']:<45}{r['status']:<12}{r['ms']:>7}{n:>8}{kb:>6}")

    ok = [r for r in res if r["status"] == "200"]
    print(f"\n{len(ok)} of {len(res)} reachable keyless from this machine")


if __name__ == "__main__":
    main()
