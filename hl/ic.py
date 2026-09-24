"""How we decide whether a feature predicts anything. One implementation.

Both measurements import this. Two copies of a statistics routine drift, and
when they drift the older one keeps printing numbers that look fine.

The method, and every part of it is a correction for a way this goes wrong:

  per-timestamp ranking   Rank coins against each other WITHIN each timestamp,
                          rank what happened next, correlate. Pooling every coin
                          and every bar into one number instead measures "the
                          market went up" - that is precisely how a 1-day signal
                          appeared in the cryptobot work and then reversed sign
                          when measured this way.

  automatic neutrality    Ranking within a timestamp removes the common move by
                          construction. A feature that only means "everything
                          rose" scores zero.

  non-overlapping t       Consecutive hourly readings of a 24h forward return
                          share 23 of 24 hours. The naive t-stat over every bar
                          counts the same fortnight hundreds of times. The
                          headline number samples one observation per horizon.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


def rank_ic(feature: pd.DataFrame, fwd: pd.DataFrame,
            min_names: int = 20) -> pd.Series:
    """Spearman rank correlation, computed within each timestamp separately.

    feature and fwd are both timestamp x coin. Returns one number per timestamp.
    """
    out: Dict[int, float] = {}
    for ts in feature.index.intersection(fwd.index):
        both = pd.concat([feature.loc[ts], fwd.loc[ts]], axis=1).dropna()
        if len(both) < min_names:
            continue
        both.columns = ["f", "r"]
        if both["f"].nunique() < 5:
            continue
        out[ts] = both["f"].rank().corr(both["r"].rank())
    return pd.Series(out).sort_index()


def summarise(ic: pd.Series, horizon_bars: int, label: str,
              bars_per_day: float = 1.0) -> Dict[str, object]:
    """Naive stats over every bar, and honest stats over non-overlapping ones.

    horizon_bars is how many bars forward the return looks, which is exactly how
    far apart two observations must be to not overlap.
    """
    blank = {"feature": label, "horizon_bars": horizon_bars,
             "horizon_d": horizon_bars / bars_per_day, "n": len(ic),
             "mean_ic": np.nan, "t_naive": np.nan, "n_indep": 0,
             "t_indep": np.nan, "hit": np.nan}
    if len(ic) < 3:
        return blank

    sd = ic.std(ddof=1)
    mean = ic.mean()
    t_naive = mean / (sd / np.sqrt(len(ic))) if sd else np.nan

    indep = ic.iloc[::max(horizon_bars, 1)]
    sd_i = indep.std(ddof=1) if len(indep) > 2 else np.nan
    t_indep = (indep.mean() / (sd_i / np.sqrt(len(indep)))
               if len(indep) > 2 and sd_i else np.nan)

    return {"feature": label, "horizon_bars": horizon_bars,
            "horizon_d": horizon_bars / bars_per_day, "n": len(ic),
            "mean_ic": mean, "t_naive": t_naive, "n_indep": len(indep),
            "t_indep": t_indep, "hit": float((ic > 0).mean())}


def self_tests(feature: pd.DataFrame, fwd: pd.DataFrame, horizon_bars: int,
               min_names: int = 20, seed: int = 7) -> pd.DataFrame:
    """Three checks that must behave or no result below them means anything.

    The first is the important one. A pipeline broken by a typo returns zeros,
    which looks exactly like "no signal found" - the only way to tell them apart
    is to feed a feature its own future and confirm the tool can still see it.
    """
    rng = np.random.default_rng(seed)
    cases = {
        "own future (must be ~+1)": fwd.reindex_like(feature),
        "shuffled (must be ~0)": pd.DataFrame(
            rng.permuted(feature.values, axis=1),
            index=feature.index, columns=feature.columns),
        "random (must be ~0)": pd.DataFrame(
            rng.standard_normal(feature.shape),
            index=feature.index, columns=feature.columns),
    }
    rows = []
    for name, f in cases.items():
        rows.append(summarise(rank_ic(f, fwd, min_names), horizon_bars, name))
    return pd.DataFrame(rows)


def print_table(res: pd.DataFrame, title: str) -> None:
    print(f"\n{title}")
    print(f"{'feature':<24}{'horizon':>8}{'obs':>7}{'mean IC':>10}"
          f"{'t naive':>10}{'indep':>7}{'t indep':>9}{'hit%':>7}")
    print("-" * 82)
    for _, r in res.sort_values(["feature", "horizon_bars"]).iterrows():
        hz = f"{r['horizon_d']:.0f}d"
        t_i = "n/a" if pd.isna(r["t_indep"]) else f"{r['t_indep']:+.2f}"
        hit = "" if pd.isna(r["hit"]) else f"{r['hit']*100:.0f}%"
        print(f"{r['feature']:<24}{hz:>8}{r['n']:>7}{r['mean_ic']:>+10.4f}"
              f"{r['t_naive']:>+10.2f}{r['n_indep']:>7}{t_i:>9}{hit:>7}")
