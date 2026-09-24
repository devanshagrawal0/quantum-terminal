"""Three ways to kill the 1-day reversal result before believing it.

    python scripts/validate_reversal.py

An information coefficient is not money. These checks ask whether the thing
survives contact with costs, with the specific coins it lives in, and with a
different year.

  1 COST      Build the actual long/short book, measure its turnover, charge
              every rebalance the real fee plus that coin's own spread, and
              report net. A 1-day signal rebalances daily, which is the most
              expensive schedule there is.

  2 LIQUIDITY Split the universe into cost terciles. If the edge lives in the
              names that cost 7.7bps a side, it is not an edge, it is a
              measurement of the spread.

  3 PERIOD    First half of the sample against the second. A signal that only
              worked in one stretch is a story about that stretch.

Costs come from measured Hyperliquid spreads in the cross-venue panel, not from
an assumption. Where a coin has no measured spread it gets the universe median,
which is stated rather than hidden.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl.ic import rank_ic, summarise  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "carry_cache"
FEE_BPS_PER_SIDE = 4.5          # hyperliquid taker


def load_costs(db: Path) -> Tuple[pd.Series, pd.Series]:
    """Measured Hyperliquid spread and credible volume, per coin, from the panel."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    df = pd.read_sql_query(
        "SELECT coin, AVG(hl_spread_bps) AS spread, AVG(credible_vol_usd) AS vol "
        "FROM cv_features GROUP BY coin", conn)
    conn.close()
    return (df.set_index("coin")["spread"], df.set_index("coin")["vol"])


def build_book(signal: pd.DataFrame, fwd1: pd.DataFrame, decile: float = 0.2,
               min_names: int = 20, inv_vol: Optional[pd.DataFrame] = None,
               exit_band: Optional[float] = None) -> Tuple[pd.Series, pd.Series, pd.DataFrame]:
    """Long/short book rebalanced daily.

    inv_vol   size each position by 1/volatility instead of equally. Equal
              weighting lets the highest-volatility coins dominate the book's
              risk, which is why the gross return was 1bp/day while the rank IC
              said 0.034 - the signal was there and the noise was louder.

    exit_band hysteresis. Enter at the top/bottom `decile`, but do not exit
              until the name leaves the wider `exit_band`. Turnover of 149% a
              day at 14bps a unit is what actually killed this book, and a name
              that is still in the top third does not need to be sold because it
              slipped out of the top fifth.
    """
    weights = pd.DataFrame(0.0, index=signal.index, columns=signal.columns)
    prev = pd.Series(0.0, index=signal.columns)
    for ts, row in signal.iterrows():
        s = row.dropna()
        if len(s) < min_names:
            weights.loc[ts] = prev
            continue
        k = max(int(len(s) * decile), 3)
        ranked = s.sort_values()
        shorts, longs = set(ranked.index[:k]), set(ranked.index[-k:])

        if exit_band is not None:
            ke = max(int(len(s) * exit_band), k)
            keep_long = set(ranked.index[-ke:])
            keep_short = set(ranked.index[:ke])
            longs |= {c for c in s.index if prev.get(c, 0) > 0 and c in keep_long}
            shorts |= {c for c in s.index if prev.get(c, 0) < 0 and c in keep_short}
            longs -= shorts

        w = pd.Series(0.0, index=signal.columns)
        size = (inv_vol.loc[ts] if inv_vol is not None and ts in inv_vol.index
                else pd.Series(1.0, index=signal.columns))
        for side, names in ((1.0, longs), (-1.0, shorts)):
            sz = size.reindex(list(names)).replace([np.inf, -np.inf], np.nan)
            sz = sz.fillna(sz.median() if sz.notna().any() else 1.0)
            if sz.sum() <= 0:
                continue
            w.loc[list(names)] = side * sz / sz.sum()
        weights.loc[ts] = w
        prev = w

    gross = (weights * fwd1.reindex_like(weights)).sum(axis=1)
    # Turnover is how much of the book changes between consecutive days - the
    # thing that gets charged. Sum of absolute weight changes, halved so a full
    # replacement of a long-only book reads as 1.0.
    turnover = weights.diff().abs().sum(axis=1) / 2.0
    return gross, turnover, weights


def cost_of(weights: pd.DataFrame, spread: pd.Series) -> pd.Series:
    """Per-day cost in return units, charged on the weight actually traded.

    Each unit traded pays the fee plus half the spread on entry and again on
    exit - crossing the book both ways, which is what a taker does.
    """
    med = float(spread.median()) if spread.notna().any() else 10.0
    per_coin_bps = (FEE_BPS_PER_SIDE + spread.reindex(weights.columns).fillna(med) / 2.0)
    traded = weights.diff().abs()
    return (traded * per_coin_bps / 1e4).sum(axis=1)


def report(gross: pd.Series, cost: pd.Series, turnover: pd.Series,
           label: str) -> Dict[str, float]:
    net = gross - cost
    n = int(gross.notna().sum())
    ann = np.sqrt(365)
    out = {
        "label": label, "days": n,
        "gross_bps_day": float(gross.mean() * 1e4),
        "cost_bps_day": float(cost.mean() * 1e4),
        "net_bps_day": float(net.mean() * 1e4),
        "turnover": float(turnover.mean()),
        "gross_sharpe": float(gross.mean() / gross.std() * ann) if gross.std() else np.nan,
        "net_sharpe": float(net.mean() / net.std() * ann) if net.std() else np.nan,
        "hit": float((net > 0).mean()),
    }
    return out


def main() -> None:
    px = pd.read_parquet(CACHE / "daily_365.parquet")
    px.index = pd.to_datetime(px.index.astype("int64"), unit="ms", utc=True)
    px = px.sort_index()
    rets = px.pct_change()
    fwd1 = px.shift(-1) / px - 1.0
    signal = -rets                      # yesterday's loser scores highest

    # 1/volatility sizing, from trailing realised vol known before the trade.
    vol30 = rets.rolling(30, min_periods=15).std().shift(1)
    inv_vol = (1.0 / vol30).replace([np.inf, -np.inf], np.nan)

    spread, vol = load_costs(ROOT / "data" / "venues.db")
    print(f"{px.shape[1]} coins, {px.shape[0]} days. Measured HL spread for "
          f"{int(spread.notna().sum())} of them; "
          f"median {spread.median():.2f} bps, worst {spread.max():.1f} bps")

    # ---------- 1. cost ----------
    gross, turnover, w = build_book(signal, fwd1)
    cost = cost_of(w, spread)
    rows = [report(gross, cost, turnover, "all coins, daily rebalance")]

    # A no-trade band: only move a position if the signal says so strongly.
    # This is the standard turnover control and it is worth testing because
    # turnover is what is killing the book.
    for band in (0.3, 0.5):
        s2 = signal.copy()
        rank = s2.rank(axis=1, pct=True)
        held = ((rank > 1 - band / 2) | (rank < band / 2))
        g2, t2, w2 = build_book(s2.where(held), fwd1)
        rows.append(report(g2, cost_of(w2, spread), t2, f"top/bottom {band:.0%} only"))

    # ---------- 2. liquidity tiers ----------
    cheap = spread.dropna().sort_values()
    if len(cheap) >= 30:
        tiers = {
            "cheapest third": cheap.index[: len(cheap) // 3],
            "middle third": cheap.index[len(cheap) // 3: 2 * len(cheap) // 3],
            "priciest third": cheap.index[2 * len(cheap) // 3:],
        }
        for name, coins in tiers.items():
            cols = [c for c in coins if c in signal.columns]
            if len(cols) < 12:
                continue
            g, t, ww = build_book(signal[cols], fwd1[cols], min_names=10)
            rows.append(report(g, cost_of(ww, spread), t, f"tier: {name}"))

    # ---------- 4. the two fixes, separately and together ----------
    liquid = [c for c in spread.dropna().sort_values().index[:40] if c in signal.columns]
    print(f"liquidity screen keeps {len(liquid)} coins "
          f"(spread <= {spread.dropna().sort_values().iloc[:40].max():.2f} bps)")

    variants = [
        ("vol-scaled, all coins", signal, inv_vol, None, 20),
        ("liquid 40 only, equal wt", signal[liquid], None, None, 10),
        ("liquid 40 + vol-scaled", signal[liquid], inv_vol[liquid], None, 10),
        ("liquid 40 + vol + band", signal[liquid], inv_vol[liquid], 0.45, 10),
        ("vol + band, all coins", signal, inv_vol, 0.45, 20),
    ]
    for name, sig, iv, band, mn in variants:
        cols = list(sig.columns)
        g, t, ww = build_book(sig, fwd1[cols], min_names=mn, inv_vol=iv,
                              exit_band=band)
        rows.append(report(g, cost_of(ww, spread), t, name))

    # ---------- 3. period split ----------
    half = len(px) // 2
    for name, sl in (("first half", slice(0, half)), ("second half", slice(half, None))):
        g, t, ww = build_book(signal.iloc[sl], fwd1.iloc[sl])
        rows.append(report(g, cost_of(ww, spread), t, f"period: {name}"))

    res = pd.DataFrame(rows)
    print(f"\n{'book':<28}{'days':>6}{'gross':>9}{'cost':>8}{'net':>9}"
          f"{'turn':>7}{'grossSR':>9}{'netSR':>8}{'hit':>7}")
    print("-" * 92)
    for _, r in res.iterrows():
        print(f"{r['label']:<28}{r['days']:>6}{r['gross_bps_day']:>+9.2f}"
              f"{r['cost_bps_day']:>8.2f}{r['net_bps_day']:>+9.2f}{r['turnover']:>7.2f}"
              f"{r['gross_sharpe']:>+9.2f}{r['net_sharpe']:>+8.2f}{r['hit']*100:>6.0f}%")

    # IC by period as well, since the book adds construction choices on top
    print("\nIC of the raw signal, by period (no portfolio construction):")
    for name, sl in (("first half", slice(0, half)), ("second half", slice(half, None))):
        ic = rank_ic(signal.iloc[sl], fwd1.iloc[sl], 20)
        s = summarise(ic, 1, name)
        print(f"  {name:<14}IC {s['mean_ic']:+.4f}  t {s['t_indep']:+.2f}  "
              f"n {s['n']}  hit {s['hit']*100:.0f}%")

    # Every configuration above is a test. The best cell in a table of this
    # size is where a false positive lives, so the count is printed rather than
    # left for the reader to work out.
    print(f"configurations tried in this table: {len(res)}. "
          "The best one needs a much higher bar than a single pre-registered test.")

    res.to_csv(ROOT / "data" / "reversal_validation.csv", index=False)
    print(f"\nwritten to {ROOT / 'data' / 'reversal_validation.csv'}")


if __name__ == "__main__":
    main()
