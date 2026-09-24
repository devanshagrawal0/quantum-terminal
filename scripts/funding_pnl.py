"""Does shorting the highest-funding coins actually make money, net of everything?

    python scripts/funding_pnl.py

The IC test said high-funding coins underperform, but showed most of that was
carry you collect rather than price you predict. That is not a yes. The question
a book answers and an IC cannot: after you pay the price move, the fees, the
spread, and eat the occasional squeeze, is the carry you keep positive?

WHAT THIS MODELS
  * Every `rebal_days`, short the top `n_short` coins by funding, long the bottom
    `n_short` (or cash-neutral short-only, both reported). Equal weight.
  * Hold for `rebal_days`. Each day: collect funding on the short (pay it on the
    long), take the price move, on exit pay fees + half-spread each side.
  * A STOP: if a short rallies more than `stop_pct` intraday-proxy (we only have
    daily bars, so this is a daily-close stop, stated as such), close it that day
    at the stop level and pay the exit cost. Squeeze risk is the whole point, so
    a book without a stop is not a real test.
  * Costs are the MEASURED per-coin Hyperliquid spread from our panel, not a flat
    assumption; coins with no measured spread get the universe median.

WHAT WOULD MAKE IT A REAL STRATEGY
  net Sharpe clearly positive AFTER costs, in BOTH halves of the year, and the
  short-only leg not dominated by one or two coins. Pre-registered before the run.

HONEST LIMITS
  * daily bars only, so the stop is a daily-close stop and UNDERSTATES squeeze
    cost - a real intraday squeeze can blow through it. The result is therefore
    an OPTIMISTIC bound on the stop's protection.
  * one year, one regime. Split-half is the minimum check, not sufficiency.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "carry_cache"
FEE_BPS = 4.5


def load() -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    px = pd.read_parquet(CACHE / "daily_365.parquet")
    px.index = pd.to_datetime(px.index.astype("int64"), unit="ms", utc=True)
    fd = pd.read_parquet(CACHE / "funding_daily_365.parquet")
    fd.index = pd.to_datetime(fd.index.astype("int64"), unit="ms", utc=True)
    common = sorted(set(px.columns) & set(fd.columns))
    px, fd = px[common].sort_index(), fd[common].reindex(px.index).sort_index()

    conn = sqlite3.connect(f"file:{ROOT/'data'/'venues.db'}?mode=ro", uri=True)
    sp = pd.read_sql_query(
        "SELECT coin, AVG(hl_spread_bps) s FROM cv_features GROUP BY coin", conn)
    conn.close()
    spread = sp.set_index("coin")["s"]
    return px, fd, spread


def run_book(px, fd, spread, n_short=8, rebal_days=3, stop_pct=0.25,
             short_only=True, sub=None) -> Dict[str, object]:
    """Walk the year, rebalancing every `rebal_days`, and return the daily P&L
    of the book in return units (fraction of gross exposure)."""
    cols = list(sub) if sub is not None else list(px.columns)
    px, fd = px[cols], fd[cols]
    rets = px.pct_change()
    med_spread = float(spread.reindex(cols).median()) if spread.notna().any() else 10.0
    per_side_cost = (FEE_BPS + spread.reindex(cols).fillna(med_spread) / 2.0) / 1e4

    dates = px.index
    daily_pnl = pd.Series(0.0, index=dates)
    n_rebals = 0
    leg_pnl = {"carry": 0.0, "price": 0.0, "cost": 0.0, "stops": 0}
    contributors: Dict[str, float] = {c: 0.0 for c in cols}

    i = 30                                    # warmup for a funding average
    while i < len(dates) - rebal_days:
        # Signal known at the OPEN of the holding window: trailing 3d funding.
        sig = fd.iloc[i - 3:i].mean().dropna()
        eligible = sig[px.iloc[i].notna() & (sig.abs() > 0)]
        if len(eligible) < 2 * n_short:
            i += rebal_days
            continue
        ranked = eligible.sort_values()
        shorts = list(ranked.index[-n_short:])       # highest funding
        longs = [] if short_only else list(ranked.index[:n_short])
        n_rebals += 1

        book = {c: -1.0 / n_short for c in shorts}
        book.update({c: 1.0 / n_short for c in longs})
        active = dict(book)

        # entry cost
        entry_cost = sum(abs(w) * per_side_cost[c] for c, w in book.items())
        daily_pnl.iloc[i] -= entry_cost
        leg_pnl["cost"] += entry_cost

        for d in range(1, rebal_days + 1):
            day = i + d
            if day >= len(dates):
                break
            for c in list(active):
                w = active[c]
                r = rets.iloc[day].get(c)
                f = fd.iloc[day].get(c)
                if pd.isna(r):
                    continue
                # short (w<0) collects +funding; price move hurts if it rises.
                carry = -w * (f if pd.notna(f) else 0.0)     # you pay funding on a long, collect on a short... sign: short w<0, -w>0, collect +f
                price = w * r
                # daily-close stop on a short that rallied hard against us
                stopped = w < 0 and r > stop_pct
                if stopped:
                    price = w * stop_pct
                    leg_pnl["stops"] += 1
                daily_pnl.iloc[day] += carry + price
                leg_pnl["carry"] += carry
                leg_pnl["price"] += price
                contributors[c] += carry + price
                if stopped:
                    exit_c = abs(w) * per_side_cost[c]
                    daily_pnl.iloc[day] -= exit_c
                    leg_pnl["cost"] += exit_c
                    del active[c]
        # exit cost on whatever is still open
        exit_cost = sum(abs(w) * per_side_cost[c] for c, w in active.items())
        end = min(i + rebal_days, len(dates) - 1)
        daily_pnl.iloc[end] -= exit_cost
        leg_pnl["cost"] += exit_cost
        i += rebal_days

    pnl = daily_pnl[daily_pnl != 0.0]
    ann = np.sqrt(365)
    sharpe = float(pnl.mean() / pnl.std() * ann) if pnl.std() else float("nan")
    total = float(daily_pnl.sum())
    return {"n_rebals": n_rebals, "days_active": int((daily_pnl != 0).sum()),
            "total_return_pct": total * 100, "sharpe": sharpe,
            "mean_bps_day": float(daily_pnl.mean() * 1e4),
            "carry_pct": leg_pnl["carry"] * 100, "price_pct": leg_pnl["price"] * 100,
            "cost_pct": leg_pnl["cost"] * 100, "stops": leg_pnl["stops"],
            "daily": daily_pnl,
            "top_contributors": sorted(contributors.items(), key=lambda x: -abs(x[1]))[:6]}


def show(label, r):
    print(f"\n{label}")
    print(f"  {r['n_rebals']} rebalances, active {r['days_active']} days, {r['stops']} stops hit")
    print(f"  TOTAL {r['total_return_pct']:+.1f}%   Sharpe {r['sharpe']:+.2f}   "
          f"{r['mean_bps_day']:+.2f} bps/day")
    print(f"  decomposition:  carry {r['carry_pct']:+.1f}%   price {r['price_pct']:+.1f}%   "
          f"cost {r['cost_pct']:.1f}%")


def main() -> None:
    px, fd, spread = load()
    print(f"{px.shape[1]} coins, {px.shape[0]} days, measured spread for "
          f"{int(spread.notna().sum())} (median {spread.median():.1f} bps)")
    print("\nPRE-REGISTERED: net Sharpe > 0 after costs in BOTH halves, and the")
    print("short leg not dominated by 1-2 coins. Otherwise it is carry theatre.")

    base = run_book(px, fd, spread)
    show("A. short-only top-8 funding, 3d hold, 25% daily-close stop", base)
    print("  biggest contributors (coin: total pnl%):")
    for c, v in base["top_contributors"]:
        print(f"    {c:<10}{v*100:+.2f}%")

    ls = run_book(px, fd, spread, short_only=False)
    show("B. long/short (short high funding, long low)", ls)

    nostop = run_book(px, fd, spread, stop_pct=99)
    show("C. short-only, NO stop (how much does the stop cost/save?)", nostop)

    # split-half on the base book
    half = px.index[len(px) // 2]
    for name, sl in (("first half", px.index < half), ("second half", px.index >= half)):
        r = run_book(px.loc[sl], fd.loc[sl], spread)
        show(f"D. base book, {name}", r)

    # liquid-only: does it survive in tradeable names?
    liquid = spread.dropna().sort_values().index[:50]
    liq = run_book(px, fd, spread, sub=[c for c in liquid if c in px.columns])
    show("E. base book, liquid-50 only (the names we can actually trade)", liq)

    print("\nread: A/B are the headline. C shows the stop's effect. D is the")
    print("regime check - if one half is negative it is not robust. E is whether")
    print("it survives in liquid names. Daily-close stop UNDERSTATES squeeze cost.")


if __name__ == "__main__":
    main()
