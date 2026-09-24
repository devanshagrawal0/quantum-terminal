"""Beta-hedged funding carry: keep the carry, cancel the market direction.

    python scripts/funding_hedged.py

The last test proved the "+119%" short book was a directional short in a
down-year - it made money because crypto fell, and lost in the half crypto rose.
The carry LEG, though, was positive in both halves (+10%, +15%). The question
here: if we hedge out the market beta so the book is direction-neutral, does the
carry survive in BOTH halves net of costs?

THE HEDGE
  Each rebalance, estimate every coin's beta to the equal-weight market
  (trailing 60d regression, shrunk 0.65*raw + 0.35*1 because raw betas on thin
  alts are noisy at the extremes). The book's net beta = sum(w_i * beta_i). Add
  a market-basket hedge of -net_beta, and pay fee+spread to trade that hedge too.

THE CHECK THAT CAN FAIL, pre-registered
  Regress the hedged book's daily returns on the market's. If the hedge worked,
  the residual beta is ~0. A book that still has beta 0.5 is not hedged, however
  good the returns look. This is reported first, before any P&L.

  Then: net Sharpe positive in BOTH halves. That is the bar the unhedged book
  failed. If the hedged book also fails it, funding carry is not a standalone
  strategy and we say so.
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


def load():
    px = pd.read_parquet(CACHE / "daily_365.parquet")
    px.index = pd.to_datetime(px.index.astype("int64"), unit="ms", utc=True)
    fd = pd.read_parquet(CACHE / "funding_daily_365.parquet")
    fd.index = pd.to_datetime(fd.index.astype("int64"), unit="ms", utc=True)
    common = sorted(set(px.columns) & set(fd.columns))
    px, fd = px[common].sort_index(), fd[common].reindex(px.index).sort_index()
    conn = sqlite3.connect(f"file:{ROOT/'data'/'venues.db'}?mode=ro", uri=True)
    sp = pd.read_sql_query("SELECT coin, AVG(hl_spread_bps) s FROM cv_features GROUP BY coin", conn)
    conn.close()
    return px, fd, sp.set_index("coin")["s"]


def run(px, fd, spread, n_short=8, rebal_days=3, stop_pct=0.25,
        hedge=True, shrink=0.65, beta_win=60):
    cols = list(px.columns)
    rets = px.pct_change(fill_method=None)
    mkt = rets.mean(axis=1)                       # equal-weight market = the hedge instrument
    # trailing shrunk betas, known before each day (shift 1)
    cov = rets.rolling(beta_win, min_periods=30).cov(mkt)
    var = mkt.rolling(beta_win, min_periods=30).var()
    beta = (shrink * cov.div(var, axis=0) + (1 - shrink) * 1.0).shift(1)

    med = float(spread.reindex(cols).median()) if spread.notna().any() else 10.0
    cost_side = (FEE_BPS + spread.reindex(cols).fillna(med) / 2.0) / 1e4
    hedge_cost_side = (FEE_BPS + med / 2.0) / 1e4     # hedge basket cost

    dates = px.index
    daily = pd.Series(0.0, index=dates)
    legs = {"carry": 0.0, "price": 0.0, "cost": 0.0, "hedge_pnl": 0.0, "stops": 0}
    i, n_rebals = beta_win, 0
    while i < len(dates) - rebal_days:
        sig = fd.iloc[i - 3:i].mean().dropna()
        elig = sig[px.iloc[i].notna() & (sig.abs() > 0)]
        if len(elig) < 2 * n_short:
            i += rebal_days
            continue
        ranked = elig.sort_values()
        shorts = list(ranked.index[-n_short:])
        longs = list(ranked.index[:n_short])
        book = {c: -1.0 / n_short for c in shorts}
        book.update({c: 1.0 / n_short for c in longs})
        n_rebals += 1

        # net beta of the book, and the hedge that cancels it
        b_now = beta.iloc[i]
        net_beta = sum(w * (b_now.get(c) if pd.notna(b_now.get(c)) else 1.0)
                       for c, w in book.items())
        hedge_w = -net_beta if hedge else 0.0

        entry = sum(abs(w) * cost_side[c] for c, w in book.items()) \
            + abs(hedge_w) * hedge_cost_side
        daily.iloc[i] -= entry
        legs["cost"] += entry
        active = dict(book)

        for d in range(1, rebal_days + 1):
            day = i + d
            if day >= len(dates):
                break
            m = mkt.iloc[day]
            if hedge_w and pd.notna(m):
                hp = hedge_w * m
                daily.iloc[day] += hp
                legs["hedge_pnl"] += hp
            for c in list(active):
                w = active[c]
                r = rets.iloc[day].get(c)
                f = fd.iloc[day].get(c)
                if pd.isna(r):
                    continue
                carry = -w * (f if pd.notna(f) else 0.0)
                stopped = w < 0 and r > stop_pct
                price = w * (stop_pct if stopped else r)
                daily.iloc[day] += carry + price
                legs["carry"] += carry
                legs["price"] += price
                if stopped:
                    legs["stops"] += 1
                    ec = abs(w) * cost_side[c]
                    daily.iloc[day] -= ec
                    legs["cost"] += ec
                    del active[c]
        end = min(i + rebal_days, len(dates) - 1)
        ex = sum(abs(w) * cost_side[c] for c, w in active.items()) \
            + abs(hedge_w) * hedge_cost_side
        daily.iloc[end] -= ex
        legs["cost"] += ex
        i += rebal_days

    pnl = daily[daily != 0]
    ann = np.sqrt(365)
    return {"daily": daily, "n_rebals": n_rebals,
            "total_pct": daily.sum() * 100,
            "sharpe": float(pnl.mean() / pnl.std() * ann) if pnl.std() else np.nan,
            "mkt": mkt, **{k: (v * 100 if k != "stops" else v) for k, v in legs.items()}}


def residual_beta(daily, mkt) -> Tuple[float, float]:
    """Regress the book's daily return on the market. Near-zero beta = hedged."""
    df = pd.concat([daily.rename("b"), mkt.rename("m")], axis=1).dropna()
    df = df[df["b"] != 0]
    if len(df) < 20:
        return np.nan, np.nan
    x = df["m"].values
    y = df["b"].values
    beta = np.cov(x, y)[0, 1] / np.var(x)
    corr = np.corrcoef(x, y)[0, 1]
    return float(beta), float(corr)


def show(label, r, mkt):
    b, c = residual_beta(r["daily"], mkt)
    print(f"\n{label}")
    print(f"  residual beta to market {b:+.3f}  (corr {c:+.2f})  <- near 0 = actually hedged")
    print(f"  TOTAL {r['total_pct']:+.1f}%   Sharpe {r['sharpe']:+.2f}   {r['stops']} stops")
    print(f"  legs:  carry {r['carry']:+.1f}%   price {r['price']:+.1f}%   "
          f"hedge {r['hedge_pnl']:+.1f}%   cost {r['cost']:.1f}%")


def main():
    px, fd, spread = load()
    mkt_full = px.pct_change(fill_method=None).mean(axis=1)
    half = px.index[len(px) // 2]
    print(f"{px.shape[1]} coins, {px.shape[0]} days, split {half.date()}")
    print("PRE-REGISTERED: residual beta ~0 AND net Sharpe > 0 in BOTH halves.\n")

    unhedged = run(px, fd, spread, hedge=False)
    show("UNHEDGED long/short (baseline)", unhedged, mkt_full)

    hedged = run(px, fd, spread, hedge=True)
    show("BETA-HEDGED, full year", hedged, mkt_full)

    for name, sl in (("first half", px.index < half), ("second half", px.index >= half)):
        r = run(px.loc[sl], fd.loc[sl], spread, hedge=True)
        show(f"BETA-HEDGED, {name}", r, mkt_full[sl])

    # liquid-only hedged
    liquid = [c for c in spread.dropna().sort_values().index[:50] if c in px.columns]
    liq = run(px[liquid], fd[liquid], spread, hedge=True)
    show("BETA-HEDGED, liquid-50 only", liq, mkt_full)

    print("\nread: if residual beta is near 0 in the full-year hedged book, the")
    print("hedge works. Then the split-half is the verdict: carry surviving BOTH")
    print("halves direction-neutral is the thing the unhedged book could not do.")


if __name__ == "__main__":
    main()
