"""L2 order book model and the liquidity variables derived from it.

Works on both the REST l2Book payload and the websocket l2Book/WsBook payload -
they have the same shape: {"coin", "time", "levels": [bids, asks]} where each
level is {"px", "sz", "n"} and bids are descending, asks ascending.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Level:
    px: float
    sz: float
    n: int

    @property
    def notional(self) -> float:
        return self.px * self.sz


@dataclass
class Book:
    coin: str
    time_ms: int
    bids: List[Level] = field(default_factory=list)
    asks: List[Level] = field(default_factory=list)

    # ---- construction ------------------------------------------------------
    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "Book":
        levels = payload.get("levels") or [[], []]
        def parse(side: List[Dict[str, Any]]) -> List[Level]:
            return [Level(float(l["px"]), float(l["sz"]), int(l.get("n", 0)))
                    for l in side]
        return cls(coin=payload.get("coin", ""), time_ms=int(payload.get("time", 0)),
                   bids=parse(levels[0]), asks=parse(levels[1]))

    # ---- top of book -------------------------------------------------------
    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].px if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].px if self.asks else None

    @property
    def mid(self) -> Optional[float]:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2.0

    @property
    def spread(self) -> Optional[float]:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    @property
    def spread_bps(self) -> Optional[float]:
        m, s = self.mid, self.spread
        if m is None or s is None or m == 0:
            return None
        return s / m * 1e4

    @property
    def microprice(self) -> Optional[float]:
        """Size-weighted top-of-book price: leans toward the thinner side, which
        is the side price is more likely to move to."""
        if not self.bids or not self.asks:
            return None
        bq, aq = self.bids[0].sz, self.asks[0].sz
        if bq + aq == 0:
            return self.mid
        return (self.best_bid * aq + self.best_ask * bq) / (bq + aq)

    # ---- depth / imbalance -------------------------------------------------
    def depth_notional(self, bps: float = 10.0) -> Tuple[float, float]:
        """USD resting within `bps` of mid, (bid_side, ask_side)."""
        m = self.mid
        if m is None:
            return (0.0, 0.0)
        lo, hi = m * (1 - bps / 1e4), m * (1 + bps / 1e4)
        bid = sum(l.notional for l in self.bids if l.px >= lo)
        ask = sum(l.notional for l in self.asks if l.px <= hi)
        return (bid, ask)

    def imbalance(self, bps: float = 10.0) -> Optional[float]:
        """(bid - ask) / (bid + ask) notional within bps. +1 all bids, -1 all asks."""
        b, a = self.depth_notional(bps)
        if b + a == 0:
            return None
        return (b - a) / (b + a)

    def top_imbalance(self, levels: int = 5) -> Optional[float]:
        b = sum(l.notional for l in self.bids[:levels])
        a = sum(l.notional for l in self.asks[:levels])
        if b + a == 0:
            return None
        return (b - a) / (b + a)

    def total_notional(self) -> Tuple[float, float]:
        return (sum(l.notional for l in self.bids),
                sum(l.notional for l in self.asks))

    # ---- execution cost ----------------------------------------------------
    def sweep(self, usd_notional: float, is_buy: bool) -> Dict[str, Any]:
        """Walk the book for a market order of `usd_notional`.

        Returns average fill price, slippage vs mid in bps, how much of the
        order the visible book can absorb, and how many levels it eats.
        Visible depth only - Hyperliquid returns 20 levels per side, so treat
        a `filled_pct` below 1 as "this size is bigger than the visible book".
        """
        side = self.asks if is_buy else self.bids
        mid = self.mid
        remaining = float(usd_notional)
        cost = 0.0
        base = 0.0
        used = 0
        for lvl in side:
            if remaining <= 0:
                break
            take = min(remaining, lvl.notional)
            cost += take
            base += take / lvl.px
            remaining -= take
            used += 1
        if base == 0:
            return {"avg_px": None, "slippage_bps": None, "filled_pct": 0.0,
                    "levels_used": 0, "worst_px": None}
        avg = cost / base
        slip = None
        if mid:
            slip = (avg - mid) / mid * 1e4 * (1 if is_buy else -1)
        return {
            "avg_px": avg,
            "slippage_bps": slip,
            "filled_pct": (usd_notional - max(remaining, 0.0)) / usd_notional,
            "levels_used": used,
            "worst_px": side[used - 1].px if used else None,
        }

    def summary(self, sweep_usd: float = 25_000.0, bps: float = 10.0) -> Dict[str, Any]:
        b10, a10 = self.depth_notional(bps)
        tb, ta = self.total_notional()
        return {
            "coin": self.coin,
            "time_ms": self.time_ms,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "mid": self.mid,
            "microprice": self.microprice,
            "spread": self.spread,
            "spread_bps": self.spread_bps,
            "bid_levels": len(self.bids),
            "ask_levels": len(self.asks),
            "bid_orders": sum(l.n for l in self.bids),
            "ask_orders": sum(l.n for l in self.asks),
            f"depth_bid_usd_{int(bps)}bps": b10,
            f"depth_ask_usd_{int(bps)}bps": a10,
            f"imbalance_{int(bps)}bps": self.imbalance(bps),
            "imbalance_top5": self.top_imbalance(5),
            "book_bid_usd": tb,
            "book_ask_usd": ta,
            "buy_slippage_bps": self.sweep(sweep_usd, True)["slippage_bps"],
            "sell_slippage_bps": self.sweep(sweep_usd, False)["slippage_bps"],
            "sweep_usd": sweep_usd,
        }
