"""Features #2 and #3: residual momentum and residual reversal, on daily bars.

    python scripts/measure_momentum.py

These are the only two features in the research list with published evidence at
exactly a 1-7 day horizon, and unlike everything cross-venue they are testable
today - Hyperliquid serves years of daily candles, and the carry run has already
cached them.

WHAT "RESIDUAL" MEANS AND WHY IT IS THE WHOLE POINT
Crypto's cross-section is dominated by one thing: how hard each coin moves with
the market. Rank coins by raw 7-day return and you have mostly ranked them by
beta, so the "momentum" signal is really "which coins are high beta in a rising
market". Both a raw and a residual version of every feature are measured below,
side by side, so the difference is visible rather than asserted.

TWO PRE-REGISTERED HYPOTHESES, written before the numbers exist:
  #2  residual 7-day momentum, SKIPPING the most recent day, is POSITIVE.
      The skip matters: the last day carries reversal, which contaminates it.
  #3  residual 1-day reversal (minus yesterday's residual return) is POSITIVE,
      i.e. yesterday's losers outperform.
They have opposite signs on the same underlying returns, which is the useful
part - if both come back positive they are measuring different things.

WHAT WOULD MAKE THIS WRONG:
  |t| on non-overlapping windows inside 2.5 = nothing found.
  IC below 0.015 = not tradeable at our costs even if real.
  Raw and residual agreeing closely = the residualisation is not doing anything
  and one of them is redundant.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl.ic import print_table, rank_ic, self_tests, summarise  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "carry_cache"


def residualise(rets: pd.DataFrame, window: int = 120,
                shrink: float = 0.65) -> pd.DataFrame:
    """Strip each coin's market component out of its return.

    The market is the equal-weight cross-sectional mean - a basket, not a
    principal component, because PCs rotate and flip sign between windows.

    Betas are shrunk toward 1: raw betas on thin alts are noisy and the noise is
    biased toward the extremes, so unshrunk betas over-hedge exactly the names
    you least want to over-hedge.
    """
    mkt = rets.mean(axis=1)
    cov = rets.rolling(window, min_periods=window // 2).cov(mkt)
    var = mkt.rolling(window, min_periods=window // 2).var()
    beta_raw = cov.div(var, axis=0)
    beta = shrink * beta_raw + (1.0 - shrink) * 1.0
    # Yesterday's beta applied to today's move: using today's beta would be
    # fitting the hedge on the return being hedged.
    return rets - beta.shift(1).mul(mkt, axis=0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--min-names", type=int, default=20)
    args = ap.parse_args()

    f = CACHE / f"daily_{args.days}.parquet"
    if not f.exists():
        print(f"no cached candles at {f} - run measure_carry.py first")
        return
    px = pd.read_parquet(f)
    px.index = pd.to_datetime(px.index.astype("int64"), unit="ms", utc=True)
    px = px.sort_index()
    print(f"{px.shape[0]} daily bars x {px.shape[1]} coins "
          f"({px.index[0].date()} to {px.index[-1].date()})")

    rets = px.pct_change()
    resid = residualise(rets)

    # How much of a coin's move is market? If residualising changes nothing,
    # the whole exercise is pointless and this number says so.
    shared = float(np.nanmean([rets[c].corr(rets.mean(axis=1)) for c in rets.columns]))
    print(f"average correlation of a coin with the equal-weight market: {shared:.3f}")

    feats: Dict[str, pd.DataFrame] = {
        # #2 - momentum, skipping the most recent day
        "mom_7d_skip1_resid": resid.shift(1).rolling(6, min_periods=4).sum(),
        "mom_7d_skip1_raw": rets.shift(1).rolling(6, min_periods=4).sum(),
        "mom_30d_skip1_resid": resid.shift(1).rolling(29, min_periods=20).sum(),
        # #3 - reversal. Negated, so a POSITIVE score means "expected to rise".
        "rev_1d_resid": -resid,
        "rev_1d_raw": -rets,
        "rev_3d_resid": -resid.rolling(3, min_periods=2).sum(),
    }

    fwds: Dict[int, pd.DataFrame] = {}
    for h in (1, 3, 7):
        fwds[h] = px.shift(-h) / px - 1.0

    print("\nSELF TESTS")
    print_table(self_tests(feats["mom_7d_skip1_resid"], fwds[1], 1, args.min_names),
                "must behave or nothing below is readable")

    rows = []
    for name, fdf in feats.items():
        for h, fwd in fwds.items():
            rows.append(summarise(rank_ic(fdf, fwd, args.min_names), h, name))
    res = pd.DataFrame(rows)
    print_table(res, "RESULT - price-only forward returns (see note below)")

    out = ROOT / "data" / "momentum_ic.csv"
    res.to_csv(out, index=False)
    print(f"\nwritten to {out}")
    print("\nREADING THIS HONESTLY:")
    print("  Returns here are PRICE ONLY - the funding cache is still being")
    print("  fetched by the carry run. Funding is a real cost at 7 days and")
    print("  these numbers will move when it is subtracted. Not final.")
    print("  Pre-registered: #2 positive, #3 positive, |t indep| > 2.5 to count,")
    print("  IC > 0.015 to be tradeable. 6 features x 3 horizons = 18 tests.")


if __name__ == "__main__":
    main()
