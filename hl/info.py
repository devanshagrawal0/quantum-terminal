"""Read-only REST client for the Hyperliquid /info endpoint.

Every method is a thin, honest wrapper: one method == one documented request
type, no reshaping of the payload beyond parsing JSON. Higher level maths lives
in features.py so the raw layer stays auditable.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

from .constants import INTERVAL_MS, MAINNET_API, MAX_CANDLES, TESTNET_API
from .errors import HttpError, RateLimited
from .ratelimit import WeightLimiter, base_weight, extra_weight


def now_ms() -> int:
    return int(time.time() * 1000)


class Info:
    def __init__(self, testnet: bool = False, timeout: float = 20.0,
                 limiter: Optional[WeightLimiter] = None, max_retries: int = 4):
        self.base = (TESTNET_API if testnet else MAINNET_API) + "/info"
        self.timeout = timeout
        self.limiter = limiter or WeightLimiter()
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ---- transport ---------------------------------------------------------
    def post(self, body: Dict[str, Any]) -> Any:
        req_type = body.get("type", "")
        self.limiter.acquire(base_weight(req_type))
        last: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                r = self.session.post(self.base, json=body, timeout=self.timeout)
            except requests.RequestException as exc:        # network blip
                last = exc
                time.sleep(min(2 ** attempt, 8))
                continue
            if r.status_code == 429:
                last = RateLimited(429, r.text, body)
                time.sleep(min(2 ** attempt, 8) + 1)
                continue
            if r.status_code >= 500:
                last = HttpError(r.status_code, r.text, body)
                time.sleep(min(2 ** attempt, 8))
                continue
            if r.status_code != 200:
                raise HttpError(r.status_code, r.text, body)
            data = r.json()
            if isinstance(data, list):
                self.limiter.charge(extra_weight(req_type, len(data)))
            return data
        raise last if last else HttpError(0, "unreachable", body)

    # ---- market metadata ---------------------------------------------------
    def meta(self, dex: str = "") -> Dict[str, Any]:
        """Perp universe: name, szDecimals, maxLeverage, marginTableId."""
        return self.post({"type": "meta", "dex": dex})

    def meta_and_asset_ctxs(self, dex: str = "") -> List[Any]:
        """[meta, ctxs] where ctxs[i] lines up with meta["universe"][i].

        ctx fields: funding (rate charged per HOUR), openInterest (base units),
        prevDayPx, dayNtlVlm, premium, oraclePx, markPx, midPx,
        impactPxs [bid, ask], dayBaseVlm.
        """
        return self.post({"type": "metaAndAssetCtxs", "dex": dex})

    def spot_meta(self) -> Dict[str, Any]:
        return self.post({"type": "spotMeta"})

    def spot_meta_and_asset_ctxs(self) -> List[Any]:
        return self.post({"type": "spotMetaAndAssetCtxs"})

    def perp_dexs(self) -> Any:
        return self.post({"type": "perpDexs"})

    def perps_at_open_interest_cap(self, dex: str = "") -> List[str]:
        return self.post({"type": "perpsAtOpenInterestCap", "dex": dex})

    def exchange_status(self) -> Dict[str, Any]:
        return self.post({"type": "exchangeStatus"})

    # ---- prices, book, tape ------------------------------------------------
    def all_mids(self, dex: str = "") -> Dict[str, str]:
        return self.post({"type": "allMids", "dex": dex})

    def l2_book(self, coin: str, n_sig_figs: Optional[int] = None,
                mantissa: Optional[int] = None) -> Dict[str, Any]:
        """Full L2 depth (20 levels per side). n_sig_figs buckets the prices."""
        body: Dict[str, Any] = {"type": "l2Book", "coin": coin}
        if n_sig_figs is not None:
            body["nSigFigs"] = n_sig_figs
        if mantissa is not None:
            body["mantissa"] = mantissa
        return self.post(body)

    def recent_trades(self, coin: str) -> List[Dict[str, Any]]:
        return self.post({"type": "recentTrades", "coin": coin})

    def candles(self, coin: str, interval: str, start_ms: int,
                end_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """Raw candles. t=open ms, T=close ms, o/h/l/c, v=base volume, n=trades."""
        req: Dict[str, Any] = {"coin": coin, "interval": interval,
                               "startTime": int(start_ms)}
        if end_ms is not None:
            req["endTime"] = int(end_ms)
        return self.post({"type": "candleSnapshot", "req": req})

    def candles_lookback(self, coin: str, interval: str,
                         bars: int) -> List[Dict[str, Any]]:
        """Most recent `bars` candles, capped by the 5000 server retention."""
        bars = min(bars, MAX_CANDLES)
        span = INTERVAL_MS[interval] * (bars + 2)
        end = now_ms()
        return self.candles(coin, interval, end - span, end)

    # ---- funding -----------------------------------------------------------
    def funding_history(self, coin: str, start_ms: int,
                        end_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """Realised hourly funding: fundingRate (per hour), premium, time."""
        body: Dict[str, Any] = {"type": "fundingHistory", "coin": coin,
                                "startTime": int(start_ms)}
        if end_ms is not None:
            body["endTime"] = int(end_ms)
        return self.post(body)

    def predicted_fundings(self) -> List[Any]:
        """Next funding per coin across HlPerp / BinPerp / BybitPerp."""
        return self.post({"type": "predictedFundings"})

    # ---- account (read only) ----------------------------------------------
    def clearinghouse_state(self, user: str, dex: str = "") -> Dict[str, Any]:
        return self.post({"type": "clearinghouseState", "user": user, "dex": dex})

    def spot_clearinghouse_state(self, user: str) -> Dict[str, Any]:
        return self.post({"type": "spotClearinghouseState", "user": user})

    def open_orders(self, user: str, dex: str = "") -> List[Dict[str, Any]]:
        return self.post({"type": "openOrders", "user": user, "dex": dex})

    def frontend_open_orders(self, user: str, dex: str = "") -> List[Dict[str, Any]]:
        return self.post({"type": "frontendOpenOrders", "user": user, "dex": dex})

    def user_fills(self, user: str,
                   aggregate_by_time: bool = False) -> List[Dict[str, Any]]:
        return self.post({"type": "userFills", "user": user,
                          "aggregateByTime": aggregate_by_time})

    def user_fills_by_time(self, user: str, start_ms: int,
                           end_ms: Optional[int] = None,
                           aggregate_by_time: bool = False) -> List[Dict[str, Any]]:
        body: Dict[str, Any] = {"type": "userFillsByTime", "user": user,
                                "startTime": int(start_ms),
                                "aggregateByTime": aggregate_by_time}
        if end_ms is not None:
            body["endTime"] = int(end_ms)
        return self.post(body)

    def user_funding(self, user: str, start_ms: int,
                     end_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        body: Dict[str, Any] = {"type": "userFunding", "user": user,
                                "startTime": int(start_ms)}
        if end_ms is not None:
            body["endTime"] = int(end_ms)
        return self.post(body)

    def user_non_funding_ledger_updates(self, user: str, start_ms: int,
                                        end_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        body: Dict[str, Any] = {"type": "userNonFundingLedgerUpdates",
                                "user": user, "startTime": int(start_ms)}
        if end_ms is not None:
            body["endTime"] = int(end_ms)
        return self.post(body)

    def historical_orders(self, user: str) -> List[Dict[str, Any]]:
        return self.post({"type": "historicalOrders", "user": user})

    def order_status(self, user: str, oid: int) -> Dict[str, Any]:
        return self.post({"type": "orderStatus", "user": user, "oid": oid})

    def active_asset_data(self, user: str, coin: str) -> Dict[str, Any]:
        """Per-asset leverage, availableToTrade and maxTradeSzs for this user."""
        return self.post({"type": "activeAssetData", "user": user, "coin": coin})

    def user_rate_limit(self, user: str) -> Dict[str, Any]:
        return self.post({"type": "userRateLimit", "user": user})

    def sub_accounts(self, user: str) -> Any:
        return self.post({"type": "subAccounts", "user": user})

    def portfolio(self, user: str) -> Any:
        return self.post({"type": "portfolio", "user": user})
