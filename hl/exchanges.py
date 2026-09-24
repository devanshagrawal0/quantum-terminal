"""Every reachable exchange, reduced to one shape: {base coin: quote}.

Table-driven on purpose. 29 venues as 29 hand-written classes is 29 places for
a bug to hide; here each venue is one row saying where the list lives and which
fields hold the symbol and the prices, plus the handful of genuine oddities as
explicit overrides.

SYMBOLOGY WARNING, and this is the part that quietly ruins cross-venue data:
every venue writes the same asset differently - BTCUSDT, BTC-USDT-SWAP,
BTC_USDT, PF_XBTUSD, tBTCUSD, XBTUSDTM, BTC-PERPETUAL, KRW-BTC. Getting one
wrong does not throw; it silently compares two different assets. So the parser
is deliberately conservative: it only accepts a symbol it can fully explain,
and everything else is reported as unmapped rather than guessed at.

Prices are quoted in the venue's own quote currency. KRW and INR venues are NOT
converted to dollars here - conversion is a decision for the caller, and doing
it silently would hide the FX assumption inside the data.
"""
from __future__ import annotations

import concurrent.futures
import json
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

# Quote currencies, longest first so USDT is tried before USD.
QUOTES = ("USDT", "USDC", "USDD", "TUSD", "FDUSD", "BUSD", "USD", "KRW", "INR",
          "EUR", "JPY", "BTC", "ETH", "DAI")

# Suffixes and prefixes that mean "this is a perp", not part of the asset name.
# The rank matters: a venue can list the same coin as both a linear (USD
# margined) and an inverse (coin margined) perp, and they are different
# instruments with different funding and a different basis. Kraken ships
# PF_XBTUSD (linear) and PI_XBTUSD (inverse) side by side; without a preference
# we kept whichever arrived first, which was the inverse one. Lower rank wins.
PERP_MARKERS = ("-SWAP", "-PERP", "-PERPETUAL", "PERP_", "_PERP", "PF_", "PI_")
CONTRACT_RANK = {"PF_": 0, "PI_": 2}      # anything unmarked ranks 1

# Venue-specific asset aliases. XBT is Kraken/KuCoin's name for BTC; the k and
# 1000 forms are contract multipliers handled in venues.py.
ALIASES = {"XBT": "BTC", "WBTC": "BTC", "WETH": "ETH"}


def _strip_multiplier(base: str) -> tuple:
    """1000PEPE / kPEPE -> (PEPE, 1000). Kept identical to venues.normalise()."""
    from .venues import normalise
    return normalise(base)


def contract_rank(sym: str) -> int:
    """0 best. Used to pick between two symbols that mean the same coin."""
    up = sym.upper()
    for marker, rank in CONTRACT_RANK.items():
        if up.startswith(marker):
            return rank
    return 1


def parse_symbol(sym: str, quotes, quote_first: bool = False,
                 implicit_quote: Optional[str] = None) -> Optional[tuple]:
    """Venue symbol -> (base, quote, multiplier), or None when it cannot be
    fully explained.

    Parsing uses THAT VENUE'S quote currencies, never a global list. With a
    global list "PF_XBTUSD" split into base XB + quote TUSD, because TrueUSD is
    longer than USD and matched first. Kraken futures only ever quote in USD, so
    telling the parser that removes the ambiguity instead of guessing at it.

    None is the honest answer. A guess here silently compares two different
    assets and every number downstream inherits the error.
    """
    if not sym:
        return None
    s = sym.upper().strip()

    if implicit_quote:                       # Bithumb keys rows by bare coin
        base, mult = _strip_multiplier(s)
        base = ALIASES.get(base, base)
        return (base, implicit_quote, mult) if base.isalnum() else None

    if len(sym) > 1 and sym[0] == "t" and s[1:].isalnum():
        s = s[1:]                            # Bitfinex trading prefix

    for marker in PERP_MARKERS:
        s = s.replace(marker, "-" if marker.startswith("-") else "")

    if s.endswith("M") and any(s[:-1].endswith(q) for q in quotes):
        s = s[:-1]                           # KuCoin futures XBTUSDTM

    parts = [p for p in s.replace("_", "-").replace("/", "-").split("-") if p]

    # Three or more parts means a dated future or an option, not a perp:
    # Paradex ships BTC-USD-25JUN27-86000-C in the same list as BTC-USD-PERP,
    # and taking the first two parts read an option's mark price as BTC.
    if len(parts) > 2:
        return None

    if len(parts) == 2:
        a, b = parts
        if quote_first or (a in quotes and b not in quotes):
            base, quote = b, a               # Upbit writes KRW-BTC
        else:
            base, quote = a, b
        if quote not in quotes:
            return None
    else:
        joined = parts[0] if parts else ""
        quote = None
        for q in sorted(quotes, key=len, reverse=True):
            if joined.endswith(q) and len(joined) > len(q):
                quote = q
                break
        if not quote:
            return None
        base = joined[: -len(quote)]

    base, mult = _strip_multiplier(base)
    base = ALIASES.get(base, base)
    if not base or not base.isalnum():
        return None
    return base, quote, mult


class Spec:
    """One venue's bulk ticker endpoint, described rather than coded."""

    def __init__(self, name: str, kind: str, url: str, path: Any = None,
                 sym: str = "symbol", bid: Optional[str] = None,
                 ask: Optional[str] = None, last: Optional[str] = None,
                 vol: Optional[str] = None, quotes: tuple = ("USDT", "USDC", "USD"),
                 custom: Optional[Callable] = None, post: Optional[dict] = None,
                 quote_first: bool = False, implicit_quote: Optional[str] = None,
                 array_rows: Optional[dict] = None,
                 row_filter: Optional[Callable] = None,
                 mid_field: Optional[str] = None,
                 vol_is_base: bool = False):
        self.name, self.kind, self.url = name, kind, url
        self.path = path if isinstance(path, (list, tuple)) else ([path] if path else [])
        self.sym, self.bid, self.ask, self.last, self.vol = sym, bid, ask, last, vol
        self.quotes, self.custom, self.post = quotes, custom, post
        self.quote_first, self.implicit_quote = quote_first, implicit_quote
        self.array_rows = array_rows
        self.row_filter = row_filter
        self.mid_field = mid_field
        # Most venues report 24h volume in the QUOTE currency (dollars); a few
        # report it in the base coin. Comparing 4,193 (Coinbase, in BTC) with
        # 5.2e9 (MEXC, in USDT) as if they were the same unit made the volume
        # concentration feature meaningless.
        self.vol_is_base = vol_is_base

    # ---- fetching ----------------------------------------------------------
    def fetch(self, timeout: float = 15.0) -> Any:
        headers = dict(UA)
        data = None
        if self.post is not None:
            data = json.dumps(self.post).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def rows(self, payload: Any) -> List[dict]:
        cur = payload
        for p in self.path:
            cur = cur[p]
        if isinstance(cur, dict):                       # keyed by symbol
            return [{**v, "__key__": k} for k, v in cur.items()
                    if isinstance(v, dict)]
        if self.array_rows:                             # positional columns
            out = []
            for r in cur:
                if isinstance(r, (list, tuple)):
                    out.append({k: r[i] for k, i in self.array_rows.items()
                                if i < len(r)})
            return out
        return [r for r in cur if isinstance(r, dict)]

    @staticmethod
    def _f(row: dict, key: Optional[str]) -> Optional[float]:
        if not key:
            return None
        v = row.get(key)
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if f > 0 else None

    def quotes_by_coin(self, timeout: float = 15.0) -> Dict[str, dict]:
        payload = self.fetch(timeout)
        if self.custom:
            return self.custom(payload)
        out: Dict[str, dict] = {}
        for row in self.rows(payload):
            if self.row_filter and not self.row_filter(row):
                continue
            raw = str(row.get(self.sym) or row.get("__key__") or "")
            parsed = parse_symbol(raw, self.quotes, self.quote_first,
                                  self.implicit_quote)
            if not parsed:
                continue
            base, quote, mult = parsed
            if quote not in self.quotes:
                continue
            bid = self._f(row, self.bid)
            ask = self._f(row, self.ask)
            last = self._f(row, self.last)
            # A midpoint is only a price when there is a book behind it. On a
            # dead market the midpoint is halfway between two hopeful quotes:
            # Paradex WLFI had zero 24h volume and an ask 27% over the bid, and
            # its midpoint read 13% away from every other venue. Where a venue
            # publishes its own mark, that is the more honest number, and bid
            # and ask are still stored so the spread stays visible.
            mark = self._f(row, self.mid_field) if self.mid_field else None
            mid = mark or ((bid + ask) / 2 if (bid and ask and ask >= bid) else last)
            if not mid:
                continue
            vol = self._f(row, self.vol)
            if vol is not None and self.vol_is_base:
                vol = vol * mid                      # base units -> notional
            rec = {"symbol": raw, "quote": quote,
                   "bid": bid / mult if bid else None,
                   "ask": ask / mult if ask else None,
                   "mid": mid / mult, "last": (last / mult) if last else None,
                   "vol": vol}
            # One venue can list the same coin several times: against different
            # quote currencies, and as both a linear and an inverse contract.
            # Rank both, lowest wins, so the choice is deterministic instead of
            # being whichever row happened to arrive last.
            rec["rank"] = (self.quotes.index(quote), contract_rank(raw))
            old = out.get(base)
            if old is None or rec["rank"] < old.get("rank", (99, 99)):
                out[base] = rec
        return out


def _hyperliquid(payload: Any) -> Dict[str, dict]:
    meta, ctxs = payload
    out = {}
    for a, c in zip(meta["universe"], ctxs):
        if a.get("isDelisted") or not (c.get("midPx") or c.get("markPx")):
            continue
        base, mult = _strip_multiplier(a["name"])
        mid = float(c.get("midPx") or c["markPx"])
        out[base] = {"symbol": a["name"], "quote": "USDC", "bid": None, "ask": None,
                     "mid": mid / mult, "last": mid / mult,
                     "vol": float(c["dayNtlVlm"]) if c.get("dayNtlVlm") else None,
                     "mark": float(c["markPx"]) / mult if c.get("markPx") else None,
                     "oracle": float(c["oraclePx"]) / mult if c.get("oraclePx") else None,
                     "funding": float(c["funding"]) if c.get("funding") is not None else None,
                     "oi": float(c["openInterest"]) * mult if c.get("openInterest") else None}
    return out


def _upbit(_payload: Any) -> Dict[str, dict]:
    """Upbit needs two calls: the market list, then tickers for those markets.
    Prices come back in KRW and are left in KRW on purpose - converting here
    would bury an FX assumption inside the data."""
    req = urllib.request.Request("https://api.upbit.com/v1/market/all", headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        markets = [m["market"] for m in json.loads(r.read())
                   if m.get("market", "").startswith("KRW-")]
    out = {}
    for i in range(0, len(markets), 100):
        chunk = ",".join(markets[i:i + 100])
        url = "https://api.upbit.com/v1/ticker?markets=" + chunk
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                    timeout=15) as r:
            for t in json.loads(r.read()):
                parsed = parse_symbol(t["market"], ("KRW",), quote_first=True)
                if not parsed:
                    continue
                base, quote, mult = parsed
                px = float(t["trade_price"]) / mult
                out[base] = {"symbol": t["market"], "quote": "KRW", "bid": None,
                             "ask": None, "mid": px, "last": px,
                             "vol": t.get("acc_trade_price_24h")}
    return out


SPECS: List[Spec] = [
    Spec("hyperliquid", "perp", "https://api.hyperliquid.xyz/info",
         post={"type": "metaAndAssetCtxs"}, custom=_hyperliquid),

    # ---- perp venues -------------------------------------------------------
    Spec("binance", "perp", "https://fapi.binance.com/fapi/v1/ticker/bookTicker",
         sym="symbol", bid="bidPrice", ask="askPrice"),
    Spec("bybit", "perp", "https://api.bybit.com/v5/market/tickers?category=linear",
         path=["result", "list"], sym="symbol", bid="bid1Price", ask="ask1Price",
         last="lastPrice", vol="turnover24h"),
    Spec("gate", "perp", "https://api.gateio.ws/api/v4/futures/usdt/tickers",
         sym="contract", last="last", vol="volume_24h_settle"),
    Spec("mexc", "perp", "https://contract.mexc.com/api/v1/contract/ticker",
         path="data", sym="symbol", bid="bid1", ask="ask1", last="lastPrice",
         vol="amount24"),
    Spec("bitget", "perp", "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES",
         path="data", sym="symbol", bid="bidPr", ask="askPr", last="lastPr",
         vol="usdtVolume"),
    Spec("bingx", "perp", "https://open-api.bingx.com/openApi/swap/v2/quote/ticker",
         path="data", sym="symbol", bid="bidPrice", ask="askPrice", last="lastPrice",
         vol="quoteVolume"),
    Spec("kucoin", "perp", "https://api-futures.kucoin.com/api/v1/contracts/active",
         path="data", sym="symbol", bid="bestBidPrice", ask="bestAskPrice",
         last="lastTradePrice", vol="volumeOf24h", vol_is_base=True),
    Spec("htx", "perp", "https://api.hbdm.com/linear-swap-ex/market/detail/batch_merged?business_type=swap",
         path="ticks", sym="contract_code", bid="bid", ask="ask", last="close",
         vol="trade_turnover"),
    Spec("kraken-fut", "perp", "https://futures.kraken.com/derivatives/api/v3/tickers",
         path="tickers", sym="symbol", bid="bid", ask="ask", last="last",
         vol="volumeQuote", quotes=("USD",)),   # USD only: stops TUSD matching XBTUSD
    # ACTIVE only. dYdX keeps FINAL_SETTLEMENT markets in the same response and
    # they still carry an oracle price, frozen at settlement - FET read 1.348
    # against Hyperliquid's 0.166, and 40 other coins were wrong the same way.
    Spec("dydx", "perp", "https://indexer.dydx.trade/v4/perpetualMarkets",
         path="markets", sym="ticker", last="oraclePrice", vol="volume24H",
         row_filter=lambda r: r.get("status") == "ACTIVE"),
    Spec("phemex", "perp", "https://api.phemex.com/md/v2/ticker/24hr/all",
         path="result", sym="symbol", last="closeRp", vol="turnoverRv"),
    Spec("woo", "perp", "https://api.woo.org/v1/public/futures", path="rows",
         sym="symbol", last="mark_price", vol="notional_24h"),
    Spec("backpack", "perp", "https://api.backpack.exchange/api/v1/tickers",
         sym="symbol", last="lastPrice", vol="quoteVolume"),
    Spec("paradex", "perp", "https://api.prod.paradex.trade/v1/markets/summary?market=ALL",
         path="results", sym="symbol", bid="bid", ask="ask",
         last="last_traded_price", mid_field="mark_price", vol="volume_24h"),

    # ---- spot venues -------------------------------------------------------
    Spec("binance-spot", "spot", "https://api.binance.com/api/v3/ticker/bookTicker",
         sym="symbol", bid="bidPrice", ask="askPrice"),
    Spec("bybit-spot", "spot", "https://api.bybit.com/v5/market/tickers?category=spot",
         path=["result", "list"], sym="symbol", bid="bid1Price", ask="ask1Price",
         last="lastPrice", vol="turnover24h"),
    Spec("gate-spot", "spot", "https://api.gateio.ws/api/v4/spot/tickers",
         sym="currency_pair", last="last", vol="quote_volume"),
    Spec("kucoin-spot", "spot", "https://api.kucoin.com/api/v1/market/allTickers",
         path=["data", "ticker"], sym="symbol", bid="buy", ask="sell", last="last",
         vol="volValue"),
    # The v2 exchange-rates table was quoting assets Coinbase does not trade -
    # JUP and MNT are not among its 923 products, yet the table returned a rate,
    # off by ~1000x. This is the real market list, with live prices.
    Spec("coinbase", "spot", "https://api.coinbase.com/api/v3/brokerage/market/products",
         path="products", sym="product_id", last="price", vol="volume_24h",
         quotes=("USD", "USDC", "USDT"), vol_is_base=True,
         row_filter=lambda r: r.get("status") == "online" and not r.get("trading_disabled")),
    # Bitmart returns positional arrays, not objects. Columns named from their
    # v3 docs; only bid/ask are used because the "last" column did not agree
    # with the book on inspection and an unverified field is not worth having.
    # Note: this endpoint returns only ~43 markets, not Bitmart's whole book.
    Spec("bitmart", "spot", "https://api-cloud.bitmart.com/spot/quotation/v3/tickers",
         path="data", array_rows={"symbol": 0, "last": 1, "vol": 3, "bid": 8, "ask": 10},
         sym="symbol", bid="bid", ask="ask", last="last", vol="vol"),
    Spec("cryptocom", "spot", "https://api.crypto.com/exchange/v1/public/get-tickers",
         path=["result", "data"], sym="i", bid="b", ask="k", last="a", vol="vv"),

    # ---- regional: the venues that matter for a local-listing thesis -------
    Spec("upbit-kr", "spot", "https://api.upbit.com/v1/market/all",
         custom=_upbit, quotes=("KRW",)),
    Spec("bithumb-kr", "spot", "https://api.bithumb.com/public/ticker/ALL_KRW",
         path="data", last="closing_price", vol="acc_trade_value_24H",
         quotes=("KRW",), implicit_quote="KRW"),
    Spec("coindcx-in", "spot", "https://api.coindcx.com/exchange/ticker",
         sym="market", bid="bid", ask="ask", last="last_price", vol="volume",
         quotes=("INR", "USDT", "BTC")),
    # WazirX keys rows by "btcinr" but each row carries name "BTC/INR", which
    # the parser can read directly. BTC is left out of the quote list here: it
    # would swallow pairs like ETH/BTC and mislabel the quote currency.
    # 266 of WazirX's 498 markets had zero 24h volume and quoted 0.0 across the
    # board; the ones in between quote stale prices that drift far from the
    # market. No volume, no price.
    Spec("wazirx-in", "spot", "https://api.wazirx.com/api/v2/tickers",
         sym="name", bid="buy", ask="sell", last="last", vol="volume",
         quotes=("INR", "USDT"),
         row_filter=lambda r: float(r.get("volume") or 0) > 0),
]

BY_NAME = {s.name: s for s in SPECS}


def snapshot(names: Optional[List[str]] = None, workers: int = 12,
             timeout: float = 15.0) -> Dict[str, Any]:
    """Every venue at once. Returns {"quotes": {venue: {coin: rec}},
    "errors": {venue: str}, "took_ms": int}. A venue that fails is absent from
    quotes and present in errors, never silently empty."""
    specs = [BY_NAME[n] for n in names] if names else SPECS
    out: Dict[str, Dict[str, dict]] = {}
    errors: Dict[str, str] = {}
    t0 = time.time()

    def one(spec: Spec):
        try:
            return spec.name, spec.quotes_by_coin(timeout), None
        except Exception as exc:
            return spec.name, None, f"{type(exc).__name__}: {exc}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for name, q, err in pool.map(one, specs):
            if err:
                errors[name] = err
            elif q:
                out[name] = q
            else:
                errors[name] = "returned no parseable symbols"
    return {"quotes": out, "errors": errors, "took_ms": int((time.time() - t0) * 1000)}
