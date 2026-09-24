"""Does crowd positioning predict a 1-7 day move? Measured, not asserted.

    python scripts/measure_positioning.py            # fetch + measure
    python scripts/measure_positioning.py --cached   # reuse fetched prices

METHOD, and every choice here exists because the alternative has already fooled
this project or one like it:

  * Per timestamp, rank every eligible coin by the feature, rank them by what
    happened next, correlate the two ranks. One number per hour. The average is
    the strength, the spread of the series is the error bar.
    Pooling every coin and every hour into one regression instead measures "the
    market went up" and reports it as signal - that is exactly how the 1-day
    flip in the cryptobot plan appeared, and it reversed sign when measured
    this way.

  * Ranking cross-sectionally is automatically market neutral. A feature that
    only means "the whole market rose" scores zero here by construction.

  * Forward returns are FUNDING ADJUSTED. Over 7 days a long pays 168 funding
    charges, which on a hot coin exceeds the entire move being predicted.

  * The headline t-stat uses NON-OVERLAPPING windows. Consecutive hourly
    observations of a 24h forward return share 23 of 24 hours, so the naive
    t-stat over every hour is inflated several-fold. Both are printed.

  * Three self-tests run every time. A feature fed its own future must score
    hugely (this is the dead-pipeline detector: a tool that silently returns
    zero from a typo looks identical to "no signal found"). A shuffled feature
    and a random column must both score zero.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl.info import Info, now_ms  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "measure_cache"
HOUR_MS = 3_600_000


# ----------------------------------------------------------------- fetching


def fetch_prices(coins: List[str], hours: int, use_cache: bool) -> pd.DataFrame:
    """Hourly close per coin from Hyperliquid's own candles."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"px_{hours}.parquet"
    if use_cache and f.exists():
        return pd.read_parquet(f)
    info = Info()
    end = now_ms()
    start = end - hours * HOUR_MS
    frames = {}
    for i, c in enumerate(coins, 1):
        try:
            rows = info.candles(c, "1h", start, end)
        except Exception:
            continue
        if not rows:
            continue
        s = pd.Series({int(r["t"]): float(r["c"]) for r in rows})
        frames[c] = s
        if i % 40 == 0:
            print(f"    prices {i}/{len(coins)}")
    px = pd.DataFrame(frames).sort_index()
    px.to_parquet(f)
    return px


def fetch_funding(coins: List[str], hours: int, use_cache: bool) -> pd.DataFrame:
    """Hourly funding rate per coin. A long pays this; a short receives it."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"fund_{hours}.parquet"
    if use_cache and f.exists():
        return pd.read_parquet(f)
    info = Info()
    start = now_ms() - hours * HOUR_MS
    frames = {}
    for i, c in enumerate(coins, 1):
        try:
            rows = info.funding_history(c, start)
        except Exception:
            continue
        if not rows:
            continue
        frames[c] = pd.Series({int(r["time"]) // HOUR_MS * HOUR_MS: float(r["fundingRate"])
                               for r in rows})
        if i % 40 == 0:
            print(f"    funding {i}/{len(coins)}")
    fd = pd.DataFrame(frames).sort_index()
    fd.to_parquet(f)
    return fd


def load_positioning(db: Path) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    df = pd.read_sql_query(
        "SELECT ts_ms, coin, oi_usd, long_frac, ls_ratio, top_long_frac, "
        "top_ls_ratio, taker_ratio FROM positioning WHERE period='1h'", conn)
    conn.close()
    return df


# ------------------------------------------------------------------ measuring


def rank_ic(feature: pd.DataFrame, fwd: pd.DataFrame, min_names: int = 20) -> pd.Series:
    """Spearman rank correlation between feature and forward return, computed
    WITHIN each timestamp. One number per timestamp."""
    common_ts = feature.index.intersection(fwd.index)
    out = {}
    for ts in common_ts:
        a = feature.loc[ts]
        b = fwd.loc[ts]
        both = pd.concat([a, b], axis=1).dropna()
        if len(both) < min_names:
            continue
        both.columns = ["f", "r"]
        if both["f"].nunique() < 5:
            continue
        out[ts] = both["f"].rank().corr(both["r"].rank())
    return pd.Series(out).sort_index()


def summarise(ic: pd.Series, horizon_h: int, label: str) -> Dict[str, object]:
    """Naive stats over every hour, and honest stats over non-overlapping ones."""
    if len(ic) < 3:
        return {"feature": label, "horizon_h": horizon_h, "n": len(ic),
                "mean_ic": np.nan, "t_naive": np.nan, "n_indep": 0,
                "t_indep": np.nan, "hit": np.nan}
    mean = ic.mean()
    t_naive = mean / (ic.std(ddof=1) / np.sqrt(len(ic))) if ic.std(ddof=1) else np.nan

    # Sample one observation per horizon so windows do not overlap.
    step = max(horizon_h, 1)
    indep = ic.iloc[::step]
    t_indep = (indep.mean() / (indep.std(ddof=1) / np.sqrt(len(indep)))
               if len(indep) > 2 and indep.std(ddof=1) else np.nan)
    return {"feature": label, "horizon_h": horizon_h, "n": len(ic),
            "mean_ic": mean, "t_naive": t_naive,
            "n_indep": len(indep), "t_indep": t_indep,
            "hit": float((ic > 0).mean())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/venues.db")
    ap.add_argument("--hours", type=int, default=520)
    ap.add_argument("--cached", action="store_true")
    ap.add_argument("--min-names", type=int, default=20)
    args = ap.parse_args()

    db = ROOT / args.db if not Path(args.db).is_absolute() else Path(args.db)
    pos = load_positioning(db)
    coins = sorted(pos["coin"].unique())
    print(f"positioning: {len(pos):,} rows, {len(coins)} coins, "
          f"{(pos.ts_ms.max()-pos.ts_ms.min())/86_400_000:.1f} days")

    print("fetching hourly prices and funding from Hyperliquid...")
    px = fetch_prices(coins, args.hours, args.cached)
    fd = fetch_funding(coins, args.hours, args.cached)
    print(f"prices {px.shape[0]} hours x {px.shape[1]} coins, "
          f"funding {fd.shape[0]} x {fd.shape[1]}")

    # ---- features, pivoted to timestamp x coin --------------------------
    pos["ts_ms"] = (pos["ts_ms"] // HOUR_MS) * HOUR_MS
    feats: Dict[str, pd.DataFrame] = {}
    for col in ("top_long_frac", "long_frac", "taker_ratio", "oi_usd"):
        feats[col] = pos.pivot_table(index="ts_ms", columns="coin", values=col)

    # The divergence Dev spotted: big positions versus retail headcount.
    feats["top_minus_retail"] = feats["top_long_frac"] - feats["long_frac"]
    # Open interest CHANGE, not level - a level is mostly "how big is this coin".
    feats["oi_change_24h"] = feats["oi_usd"].pct_change(24)
    feats["oi_change_6h"] = feats["oi_usd"].pct_change(6)
    del feats["oi_usd"]

    # ---- forward returns, funding adjusted -------------------------------
    fwds: Dict[int, pd.DataFrame] = {}
    for h in (24, 72, 168):
        price_ret = px.shift(-h) / px - 1.0
        # A long pays funding every hour it is held.
        cost = fd.rolling(h, min_periods=max(1, h // 2)).sum().shift(-h)
        fwds[h] = (price_ret - cost.reindex_like(price_ret)).dropna(how="all")

    # ---- self tests, run before believing any result ---------------------
    print("\nSELF TESTS (these must behave or nothing below means anything)")
    rng = np.random.default_rng(7)
    base = feats["top_long_frac"]
    fwd24 = fwds[24]
    tests = {
        "feature fed its own future (must be strongly positive)":
            fwd24.reindex_like(base),
        "shuffled feature (must be ~0)":
            pd.DataFrame(rng.permuted(base.values, axis=1),
                         index=base.index, columns=base.columns),
        "pure random column (must be ~0)":
            pd.DataFrame(rng.standard_normal(base.shape),
                         index=base.index, columns=base.columns),
    }
    for name, f in tests.items():
        ic = rank_ic(f, fwd24, args.min_names)
        s = summarise(ic, 24, name)
        print(f"  {name:<52} IC {s['mean_ic']:+.4f}  t_indep {s['t_indep']:+.2f}")

    # ---- the real measurement --------------------------------------------
    rows = []
    for fname, fdf in feats.items():
        for h, fwd in fwds.items():
            ic = rank_ic(fdf, fwd, args.min_names)
            rows.append(summarise(ic, h, fname))
    res = pd.DataFrame(rows)

    print("\nRESULT - rank correlation between feature and funding-adjusted "
          "forward return")
    print("t_indep is the honest one: non-overlapping windows only\n")
    print(f"{'feature':<20}{'horizon':>8}{'obs':>7}{'mean IC':>10}"
          f"{'t naive':>10}{'indep':>7}{'t indep':>9}{'hit%':>7}")
    print("-" * 78)
    for _, r in res.sort_values(["feature", "horizon_h"]).iterrows():
        hz = f"{r['horizon_h']//24}d"
        print(f"{r['feature']:<20}{hz:>8}{r['n']:>7}{r['mean_ic']:>+10.4f}"
              f"{r['t_naive']:>+10.2f}{r['n_indep']:>7}{r['t_indep']:>+9.2f}"
              f"{r['hit']*100:>6.0f}%")

    out = ROOT / "data" / "positioning_ic.csv"
    res.to_csv(out, index=False)
    print(f"\nwritten to {out}")
    print("\nREAD THIS BEFORE BELIEVING ANY ROW ABOVE:")
    print(f"  21 days of history means {res['n_indep'].max()} independent 1-day")
    print("  windows and about 3 independent 7-day windows. A |t| under roughly")
    print("  2.5 here is noise, and even above that the sample is too short to")
    print("  conclude anything - this tells us where to look, not what is true.")


if __name__ == "__main__":
    main()
