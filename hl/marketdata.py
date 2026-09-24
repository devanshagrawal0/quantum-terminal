"""One object that hands you every variable for a coin, or for the whole
universe, with the raw payloads still attached so nothing is a black box.

    md = MarketData()
    snap = md.snapshot("BTC")          # ~5 requests, everything about one coin
    table = md.scan()                  # 3 requests, every perp, one row each
"""
from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from . import features as F
from .book import Book
from .info import Info, now_ms
from .meta import Universe


class MarketData:
    def __init__(self, testnet: bool = False, ctx_ttl: float = 2.0):
        self.info = Info(testnet=testnet)
        self.universe = Universe(self.info)
        self.ctx_ttl = ctx_ttl
        self._ctx_at = 0.0
        self._meta_ctx: Optional[List[Any]] = None
        self._spot_at = 0.0
        self._spot_ctx: Optional[List[Any]] = None

    # ---- cached raw pulls --------------------------------------------------
    def meta_and_ctxs(self, force: bool = False) -> List[Any]:
        if force or self._meta_ctx is None or time.time() - self._ctx_at > self.ctx_ttl:
            self._meta_ctx = self.info.meta_and_asset_ctxs()
            self._ctx_at = time.time()
        return self._meta_ctx

    def spot_meta_and_ctxs(self, force: bool = False) -> List[Any]:
        if force or self._spot_ctx is None or time.time() - self._spot_at > 30.0:
            self._spot_ctx = self.info.spot_meta_and_asset_ctxs()
            self._spot_at = time.time()
        return self._spot_ctx

    def ctx(self, coin: str) -> Dict[str, Any]:
        meta, ctxs = self.meta_and_ctxs()
        idx = {a["name"]: i for i, a in enumerate(meta["universe"])}
        if coin not in idx:
            raise KeyError(f"{coin} is not a Hyperliquid perp")
        return ctxs[idx[coin]]

    def spot_mid(self, coin: str) -> Optional[float]:
        """Mid of the canonical spot market for this token, if it has one.

        The spot ctx array is NOT positionally aligned with the spot universe
        (717 ctxs vs 326 pairs, and pair "@142" sits at list position 140), so
        contexts are matched on their own "coin" field. Indexing by position
        here silently returns another token's price.
        """
        pair = self.universe.spot_pair(coin)
        if not pair:
            return None
        _meta, ctxs = self.spot_meta_and_ctxs()
        for ctx in ctxs:
            if ctx.get("coin") == pair:
                px = ctx.get("midPx") or ctx.get("markPx")
                return float(px) if px else None
        return None

    # ---- the full picture for one coin ------------------------------------
    def snapshot(self, coin: str, *, sweep_usd: float = 25_000.0,
                 interval: str = "1d", bars: int = 120,
                 funding_hours: int = 24 * 14, depth_bps: float = 10.0,
                 with_book: bool = True, with_trades: bool = True,
                 with_funding: bool = True, with_candles: bool = True,
                 keep_raw: bool = True) -> Dict[str, Any]:
        self.universe.refresh()
        ctx = self.ctx(coin)
        asset = self.universe.perp(coin)

        row: Dict[str, Any] = {
            "coin": coin,
            "ts_ms": now_ms(),
            "sz_decimals": int(asset["szDecimals"]),
            "max_leverage": int(asset["maxLeverage"]),
            "asset_id": self.universe.asset_id(coin),
        }
        row.update(F.asset_ctx_features(ctx))

        raw: Dict[str, Any] = {"ctx": ctx}

        if with_book:
            book = Book.from_payload(self.info.l2_book(coin))
            row.update(F.flatten("book", book.summary(sweep_usd, depth_bps)))
            row["book_age_ms"] = row["ts_ms"] - book.time_ms
            raw["book"] = book

        if with_trades:
            trades = self.info.recent_trades(coin)
            row.update(F.trade_flow(trades))
            raw["trades"] = trades

        if with_funding:
            hist = self.info.funding_history(coin, now_ms() - funding_hours * 3_600_000)
            row.update(F.funding_stats(hist))
            raw["funding_history"] = hist
            hourly = row.get("funding_hourly")
            if hourly is not None:
                for d in (1, 2, 3, 7):
                    row[f"carry_long_{d}d"] = F.carry_cost(hourly, d, True)
                    row[f"carry_short_{d}d"] = F.carry_cost(hourly, d, False)

        if with_candles:
            df = F.candles_to_frame(self.info.candles_lookback(coin, interval, bars))
            row.update(F.daily_features(df))
            raw["candles"] = df

        sp = self.spot_mid(coin)
        if sp:
            row["spot_mid"] = sp
            mark = row.get("mark_px")
            if mark:
                row["perp_spot_basis_bps"] = (mark - sp) / sp * 1e4
            row["spot_pair"] = self.universe.spot_pair(coin)
            row["spot_pair_label"] = self.universe.spot_pair_label(coin)

        if keep_raw:
            row["_raw"] = raw
        return row

    # ---- whole universe, cheaply ------------------------------------------
    def scan(self, coins: Optional[Iterable[str]] = None,
             min_day_volume_usd: float = 0.0) -> pd.DataFrame:
        """One row per perp from 3 requests: metaAndAssetCtxs, predictedFundings,
        perpsAtOpenInterestCap. Use this to pick candidates, then snapshot()."""
        self.universe.refresh()
        meta, ctxs = self.meta_and_ctxs(force=True)
        predicted = F.predicted_funding_map(self.info.predicted_fundings())
        at_cap = set(self.info.perps_at_open_interest_cap())
        wanted = set(coins) if coins else None

        rows: List[Dict[str, Any]] = []
        for asset, ctx in zip(meta["universe"], ctxs):
            name = asset["name"]
            if wanted and name not in wanted:
                continue
            row: Dict[str, Any] = {
                "coin": name,
                "sz_decimals": int(asset["szDecimals"]),
                "max_leverage": int(asset["maxLeverage"]),
                "at_oi_cap": name in at_cap,
                "delisted": bool(asset.get("isDelisted", False)),
            }
            row.update(F.asset_ctx_features(ctx))
            p = predicted.get(name, {})
            row["funding_hl_pred"] = p.get("HlPerp")
            row["funding_binance"] = p.get("BinPerp")
            row["funding_bybit"] = p.get("BybitPerp")
            row["funding_hl_minus_cex_apr"] = p.get("hl_minus_cex_apr")
            rows.append(row)

        df = pd.DataFrame(rows)
        if not df.empty and min_day_volume_usd:
            df = df[df["day_notional_volume"].fillna(0) >= min_day_volume_usd]
        if not df.empty:
            df = df.sort_values("day_notional_volume", ascending=False,
                                na_position="last").reset_index(drop=True)
        return df

    # ---- history helpers ---------------------------------------------------
    def candles(self, coin: str, interval: str = "1d", bars: int = 365) -> pd.DataFrame:
        return F.candles_to_frame(self.info.candles_lookback(coin, interval, bars))

    def funding_frame(self, coin: str, days: int = 30) -> pd.DataFrame:
        hist = self.info.funding_history(coin, now_ms() - days * 86_400_000)
        if not hist:
            return pd.DataFrame(columns=["fundingRate", "premium"])
        df = pd.DataFrame(hist)
        df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
        df["fundingRate"] = df["fundingRate"].astype(float)
        df["premium"] = df["premium"].astype(float)
        return df.set_index("time").sort_index()

    def book(self, coin: str, n_sig_figs: Optional[int] = None) -> Book:
        return Book.from_payload(self.info.l2_book(coin, n_sig_figs))
