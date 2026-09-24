"""Other venues, for comparing Hyperliquid's price against the rest of the market.

All three are keyless public endpoints. Each venue is asked for its OWN contract
metadata first, so a symbol is never guessed from a string: we take the base
asset the exchange itself declares, then strip any size multiplier.

The multiplier matters and is the classic silent bug here. Hyperliquid lists
1000x contracts as kPEPE; Binance and Bybit list the same thing as 1000PEPE;
OKX quotes the coin itself. Comparing kPEPE to PEPE without dividing gives a
1000x "gap" that looks like the trade of the century. Everything below is
normalised to price per one unit of the base coin before anything is compared.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

# A leading number on a contract name CAN be a size multiplier (1000PEPE,
# 1MBABYDOGE) but is very often just part of the coin's name (1INCH, 0G, 2Z).
# Only a power of ten of at least 1000 is treated as a multiplier; everything
# else is left alone. Getting this wrong is not a rounding error - it divides a
# price by zero or by one thousand and invents a gap that is not there.
_NUM_PREFIX = re.compile(r"^(\d+)(?=[A-Z])")
_M_PREFIX = re.compile(r"^1M(?=[A-Z])")
_VALID_MULTS = (1000.0, 10_000.0, 100_000.0, 1_000_000.0)


def normalise(sym: str):
    """Contract name -> (base coin, how many coins one contract unit represents)."""
    s = sym.upper()
    if _M_PREFIX.match(s) and len(s) > 2:
        return s[2:], 1_000_000.0
    m = _NUM_PREFIX.match(s)
    if m:
        mult = float(m.group(1))
        rest = s[m.end():]
        if mult in _VALID_MULTS and rest:
            return rest, mult
        return s, 1.0                              # 1INCH, 0G, 2Z: part of the name
    if len(sym) > 1 and sym[0] == "k" and sym[1:].upper() == sym[1:]:
        return s[1:], 1000.0                       # Hyperliquid's kPEPE
    return s, 1.0


def _get(url: str, timeout: float = 30.0) -> Any:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


class Venue:
    """One exchange's perp quotes, keyed by base coin, priced per single coin."""

    name = "?"
    meta_ttl = 3600.0

    def __init__(self) -> None:
        self._meta: Dict[str, Tuple[str, float]] = {}     # symbol -> (base, mult)
        self._meta_at = 0.0
        self.last_error: Optional[str] = None

    def _load_meta(self) -> None:
        raise NotImplementedError

    def meta(self, force: bool = False) -> Dict[str, Tuple[str, float]]:
        if force or not self._meta or time.time() - self._meta_at > self.meta_ttl:
            self._load_meta()
            self._meta_at = time.time()
        return self._meta

    def quotes(self) -> Dict[str, Dict[str, float]]:
        """{base coin: {bid, ask, mid, mult, symbol}} — prices per one coin."""
        raise NotImplementedError

    @staticmethod
    def _row(bid: float, ask: float, mult: float, symbol: str) -> Optional[Dict[str, float]]:
        if bid <= 0 or ask <= 0 or ask < bid:
            return None
        return {"bid": bid / mult, "ask": ask / mult,
                "mid": (bid + ask) / 2 / mult, "mult": mult, "symbol": symbol}


class Binance(Venue):
    name = "binance"

    def _load_meta(self) -> None:
        info = _get("https://fapi.binance.com/fapi/v1/exchangeInfo")
        out = {}
        for s in info["symbols"]:
            if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT" \
                    and s.get("status") == "TRADING":
                base, mult = normalise(s["baseAsset"])
                out[s["symbol"]] = (base, mult)
        self._meta = out

    def quotes(self) -> Dict[str, Dict[str, float]]:
        meta = self.meta()
        out: Dict[str, Dict[str, float]] = {}
        for b in _get("https://fapi.binance.com/fapi/v1/ticker/bookTicker"):
            hit = meta.get(b["symbol"])
            if not hit:
                continue
            base, mult = hit
            row = self._row(float(b["bidPrice"]), float(b["askPrice"]), mult, b["symbol"])
            if row:
                out[base] = row
        return out


class Bybit(Venue):
    name = "bybit"

    def _load_meta(self) -> None:
        out, cursor = {}, ""
        for _ in range(10):
            url = ("https://api.bybit.com/v5/market/instruments-info"
                   "?category=linear&limit=1000")
            if cursor:
                url += "&cursor=" + urllib.parse.quote(cursor)
            d = _get(url)["result"]
            for s in d.get("list", []):
                # LinearPerpetual only. Bybit lists dated futures (BTCUSDT-25JUN27)
                # under the same baseCoin; they trade in contango and overwrote the
                # perp, which read as a 64 bps BTC gap that does not exist.
                if (s.get("quoteCoin") == "USDT" and s.get("status") == "Trading"
                        and s.get("contractType") == "LinearPerpetual"):
                    base, mult = normalise(s["baseCoin"])
                    out[s["symbol"]] = (base, mult)
            cursor = d.get("nextPageCursor") or ""
            if not cursor:
                break
        self._meta = out

    def quotes(self) -> Dict[str, Dict[str, float]]:
        meta = self.meta()
        out: Dict[str, Dict[str, float]] = {}
        for t in _get("https://api.bybit.com/v5/market/tickers?category=linear")["result"]["list"]:
            hit = meta.get(t["symbol"])
            if not hit:
                continue
            base, mult = hit
            try:
                row = self._row(float(t.get("bid1Price") or 0),
                                float(t.get("ask1Price") or 0), mult, t["symbol"])
            except ValueError:
                continue
            if row:
                out[base] = row
        return out


class OKX(Venue):
    name = "okx"

    def _load_meta(self) -> None:
        d = _get("https://www.okx.com/api/v5/public/instruments?instType=SWAP")
        out = {}
        for s in d.get("data", []):
            if s.get("settleCcy") == "USDT" and s.get("state") == "live":
                base, mult = normalise(s["ctValCcy"] if s.get("ctValCcy") not in (None, "USD", "USDT")
                                       else s["instId"].split("-")[0])
                out[s["instId"]] = (base, mult)
        self._meta = out

    def quotes(self) -> Dict[str, Dict[str, float]]:
        meta = self.meta()
        out: Dict[str, Dict[str, float]] = {}
        for t in _get("https://www.okx.com/api/v5/market/tickers?instType=SWAP").get("data", []):
            hit = meta.get(t["instId"])
            if not hit:
                continue
            base, mult = hit
            try:
                row = self._row(float(t.get("bidPx") or 0), float(t.get("askPx") or 0),
                                mult, t["instId"])
            except ValueError:
                continue
            if row:
                out[base] = row
        return out


ALL_VENUES = (Binance, Bybit, OKX)


def all_quotes(venues=ALL_VENUES) -> Dict[str, Dict[str, Dict[str, float]]]:
    """{venue name: quotes}. A venue that fails is omitted, never faked as empty
    prices — a missing venue and a venue quoting zero are different facts."""
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    errors: Dict[str, str] = {}
    for cls in venues:
        v = cls()
        try:
            q = v.quotes()
            if q:
                out[v.name] = q
        except Exception as exc:
            errors[v.name] = f"{type(exc).__name__}: {exc}"
    all_quotes.errors = errors          # type: ignore[attr-defined]
    return out
