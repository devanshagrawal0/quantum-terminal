"""The simulated book: holds and settles what an agent decides, at real costs.

Same rules as the live paper engine (hl/paper.py), so a simulated track record and
the live paper track record mean the same thing:
  * every trade the same fixed notional (default $100) - one big win cannot dominate
  * Hyperliquid taker fee 4.5 bps + half of that coin's MEASURED spread, charged on
    entry and again on exit
  * a trade carries a plan at open: stop, target, max hold. Exits fire on the day's
    high/low crossing stop/target (checked against the hourly-built range, so an
    intraday hit counts), or on the hold expiring - whichever first. Stop and target
    are filled AT the level (no gap modelling: optimistic on gaps, stated here)
  * funding is charged/credited daily where funding data exists; None otherwise
  * marks are the daily close
Nothing here decides what to trade.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .data import AsOf, DAY_MS

FEE_BPS = 4.5


@dataclass
class Order:
    coin: str
    side: str                      # "long" | "short"
    stop_pct: float = 0.05         # distance from entry, fraction
    target_pct: float = 0.10
    hold_days: int = 7
    thesis: str = ""
    tags: str = ""                 # comma list, e.g. "trend,rule"
    notional: Optional[float] = None
    size_mult: float = 1.0         # the skeptic/risk hat may shrink a trade (never grow it)
    falsifier_day: int = 0         # the agent's own "I am wrong if": on day N after entry ...
    falsifier_pct: Optional[float] = None   # ... the close has moved this much in PRICE (long: <= pct<0; short: >= pct>0)


@dataclass
class Position:
    id: int
    coin: str
    side: str
    entry_ts: int
    entry_px: float
    notional: float
    stop_px: float
    target_px: float
    expire_ts: int
    thesis: str
    tags: str
    entry_fee: float
    funding_paid: float = 0.0
    stop_pct: float = 0.0
    target_pct: float = 0.0
    falsifier_day: int = 0
    falsifier_pct: Optional[float] = None
    path: list = field(default_factory=list)      # [(ts, close, high, low)] since entry, filled by settle()


@dataclass
class Trade:
    id: int
    coin: str
    side: str
    entry_ts: int
    exit_ts: int
    entry_px: float
    exit_px: float
    notional: float
    gross_pnl: float
    fees: float
    funding: float
    net_pnl: float
    exit_reason: str
    thesis: str
    tags: str
    days_held: int
    excess_bps: float = 0.0        # net result minus the universe's average move over the same window
    mfe_bps: float = 0.0           # best point reached (gross, in the trade's favour)
    mae_bps: float = 0.0           # worst point reached (gross, against the trade)
    counterfactuals: str = "{}"    # JSON: what the same trade returned under other stop/target plans + the opposite side
    path_pct: str = "[]"           # JSON: daily close moves in the trade's favour, % (day 1, day 2, ...)


class Book:
    def __init__(self, data: AsOf, start_cash: float = 10_000.0, trade_size: float = 100.0,
                 max_positions: int = 20, charge_funding: bool = True):
        self.data = data
        self.cash = start_cash
        self.start_cash = start_cash
        self.trade_size = trade_size
        self.max_positions = max_positions
        self.charge_funding = charge_funding
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[tuple] = []
        self._next_id = 1
        med = float(np.nanmedian(data.spread.values)) if len(data.spread) else 10.0
        self.spread = data.spread.reindex(data.universe).fillna(med)

    # ---- costs ---------------------------------------------------------------
    def _fee(self, coin: str, notional: float) -> float:
        return notional * (FEE_BPS + float(self.spread.get(coin, 10.0)) / 2.0) / 1e4

    # ---- open ----------------------------------------------------------------
    def open(self, t: int, o: Order) -> Optional[Position]:
        if o.coin in self.positions or len(self.positions) >= self.max_positions:
            return None
        px = self.data.price(t, o.coin)
        if px is None or px <= 0:
            return None
        notional = (o.notional or self.trade_size) * min(max(float(o.size_mult), 0.0), 1.0)
        if notional <= 0:
            return None
        if o.side == "long":
            stop, target = px * (1 - o.stop_pct), px * (1 + o.target_pct)
        else:
            stop, target = px * (1 + o.stop_pct), px * (1 - o.target_pct)
        fee = self._fee(o.coin, notional)
        p = Position(self._next_id, o.coin, o.side, t, px, notional, stop, target,
                     t + o.hold_days * DAY_MS, o.thesis, o.tags, fee,
                     stop_pct=o.stop_pct, target_pct=o.target_pct)
        # a falsifier only counts if it points the wrong way for the trade (long: price down, short: price up)
        if o.falsifier_day > 0 and o.falsifier_pct is not None and (
                (o.side == "long" and o.falsifier_pct < 0) or (o.side == "short" and o.falsifier_pct > 0)):
            p.falsifier_day, p.falsifier_pct = int(o.falsifier_day), float(o.falsifier_pct)
        self._next_id += 1
        self.positions[o.coin] = p
        self.cash -= fee
        return p

    # ---- close ---------------------------------------------------------------
    def close(self, t: int, coin: str, px: float, reason: str) -> Trade:
        p = self.positions.pop(coin)
        sign = 1.0 if p.side == "long" else -1.0
        gross = sign * (px / p.entry_px - 1.0) * p.notional
        exit_fee = self._fee(coin, p.notional)
        fees = p.entry_fee + exit_fee
        net = gross - fees - p.funding_paid
        self.cash += gross - exit_fee - p.funding_paid
        tr = Trade(p.id, coin, p.side, p.entry_ts, t, p.entry_px, px, p.notional, gross,
                   fees, p.funding_paid, net, reason, p.thesis, p.tags,
                   int((t - p.entry_ts) // DAY_MS))
        self._grade(tr, p, t)
        self.trades.append(tr)
        return tr

    # ---- the richer grade: everything knowable at close ----------------------
    def _grade(self, tr: Trade, p: Position, t: int) -> None:
        sign = 1.0 if p.side == "long" else -1.0
        # excess over the universe: average close-to-close move of every tradable coin
        try:
            c0 = self.data.close.loc[p.entry_ts].reindex(self.data.universe)
            c1 = self.data.close.loc[t].reindex(self.data.universe)
            mkt = float(((c1 / c0) - 1.0).dropna().mean())
        except Exception:
            mkt = 0.0
        tr.excess_bps = (tr.net_pnl / tr.notional - sign * mkt) * 1e4
        path = p.path or []
        if path:
            highs = [h for _, _, h, _ in path]; lows = [l for _, _, _, l in path]
            if p.side == "long":
                tr.mfe_bps = (max(highs) / p.entry_px - 1.0) * 1e4
                tr.mae_bps = (min(lows) / p.entry_px - 1.0) * 1e4
            else:
                tr.mfe_bps = (1.0 - min(lows) / p.entry_px) * 1e4
                tr.mae_bps = (1.0 - max(highs) / p.entry_px) * 1e4
        # counterfactual plans on the observed path (stop/target grid + opposite side)
        cf: Dict[str, float] = {}
        cost = (self._fee(tr.coin, p.notional) * 2 + p.funding_paid) / p.notional * 1e4
        for side, sg in ((p.side, sign), ("short" if p.side == "long" else "long", -sign)):
            for sp in (0.03, 0.06, 0.09):
                for tp in (0.06, 0.12, 0.18):
                    res = None
                    for ts_, close_, hi_, lo_ in path:
                        if sg > 0:
                            if lo_ <= p.entry_px * (1 - sp): res = -sp; break
                            if hi_ >= p.entry_px * (1 + tp): res = tp; break
                        else:
                            if hi_ >= p.entry_px * (1 + sp): res = -sp; break
                            if lo_ <= p.entry_px * (1 - tp): res = tp; break
                    if res is None and path:
                        res = sg * (path[-1][1] / p.entry_px - 1.0)
                    if res is not None:
                        cf[f"{side}:s{int(sp*100)}:t{int(tp*100)}"] = round(res * 1e4 - cost, 1)
        tr.counterfactuals = json.dumps(cf)
        tr.path_pct = json.dumps([round(sign * (c / p.entry_px - 1.0) * 100, 2) for _, c, _, _ in path])

    # ---- daily settle: called once per simulated day AFTER the agent acted ------
    def settle(self, t: int) -> List[Trade]:
        closed: List[Trade] = []
        fund = self.data.funding_day(t) if self.charge_funding else None
        for coin in list(self.positions):
            p = self.positions[coin]
            if t <= p.entry_ts:
                continue                       # opened today: settles from tomorrow
            px = self.data.price(t, coin)
            if px is None:
                continue
            try:
                hi, lo = self.data.day_range(t, coin)
            except Exception:
                hi, lo = px, px
            p.path.append((t, px, hi, lo))
            # funding: longs pay when positive, shorts receive (fraction per day)
            if fund is not None:
                f = fund.get(coin)
                if f is not None and not pd.isna(f):
                    p.funding_paid += (1.0 if p.side == "long" else -1.0) * float(f) * p.notional
            if p.side == "long":
                if lo <= p.stop_px:
                    closed.append(self.close(t, coin, p.stop_px, "stop")); continue
                if hi >= p.target_px:
                    closed.append(self.close(t, coin, p.target_px, "target")); continue
            else:
                if hi >= p.stop_px:
                    closed.append(self.close(t, coin, p.stop_px, "stop")); continue
                if lo <= p.target_px:
                    closed.append(self.close(t, coin, p.target_px, "target")); continue
            # the agent's own falsifier: checked at the close of that day, after stop/target
            if p.falsifier_day and len(p.path) == p.falsifier_day:
                move = (px / p.entry_px - 1.0) * 100.0
                if (p.side == "long" and move <= p.falsifier_pct) or (p.side == "short" and move >= p.falsifier_pct):
                    closed.append(self.close(t, coin, px, "falsifier")); continue
            if t >= p.expire_ts:
                closed.append(self.close(t, coin, px, "time"))
        self.equity_curve.append((t, self.equity(t)))
        return closed

    def equity(self, t: int) -> float:
        eq = self.cash
        for coin, p in self.positions.items():
            px = self.data.price(t, coin)
            if px is None:
                continue
            sign = 1.0 if p.side == "long" else -1.0
            eq += sign * (px / p.entry_px - 1.0) * p.notional - p.funding_paid
        return eq

    def close_all(self, t: int, reason: str = "end") -> None:
        for coin in list(self.positions):
            px = self.data.price(t, coin)
            if px is not None:
                self.close(t, coin, px, reason)

    # ---- reporting -----------------------------------------------------------
    def summary(self) -> Dict[str, float]:
        tr = pd.DataFrame([asdict(x) for x in self.trades]) if self.trades else pd.DataFrame()
        eq = pd.Series({t: e for t, e in self.equity_curve}).sort_index()
        daily = eq.pct_change().dropna()
        n = len(tr)
        out = {
            "trades": n,
            "net_pnl": float(tr["net_pnl"].sum()) if n else 0.0,
            "gross_pnl": float(tr["gross_pnl"].sum()) if n else 0.0,
            "fees": float(tr["fees"].sum()) if n else 0.0,
            "funding": float(tr["funding"].sum()) if n else 0.0,
            "hit_rate": float((tr["net_pnl"] > 0).mean()) if n else float("nan"),
            "avg_net_per_trade_bps": float((tr["net_pnl"] / tr["notional"]).mean() * 1e4) if n else float("nan"),
            "net_return_pct": float((eq.iloc[-1] / self.start_cash - 1) * 100) if len(eq) else 0.0,
            "sharpe": float(daily.mean() / daily.std() * math.sqrt(365)) if len(daily) > 2 and daily.std() > 0 else float("nan"),
            "max_drawdown_pct": float(((eq / eq.cummax()) - 1).min() * 100) if len(eq) else 0.0,
            "days": int(len(eq)),
            "exits": json.dumps(tr["exit_reason"].value_counts().to_dict()) if n else "{}",
        }
        return out
