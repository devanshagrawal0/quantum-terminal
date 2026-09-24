"""Does funding / carry predict a 1-7 day move? A year of history, daily bars.

    python scripts/measure_carry.py --days 365 --top 80
    python scripts/measure_carry.py --cached          # skip refetching

Why this test and not another: of everything in the research, funding and carry
extremes are the one multi-day effect with support that did not come from our
own short sample. And unlike crowd positioning - where Binance serves only 500
points, about 3 weeks - Hyperliquid publishes its own funding back to listing.
A year gives 52 non-overlapping 7-day windows instead of 2.

THE HYPOTHESIS, stated before the run so it cannot be adjusted afterwards:
    coins whose longs are paying heavily (high positive funding) UNDERPERFORM
    over the next 1-7 days, because a crowded, expensive long is both a carry
    drag and a squeeze risk. Expect a NEGATIVE information coefficient.

WHAT WOULD MAKE THIS WRONG, also stated first:
    a t-stat on non-overlapping windows inside +/-2.5 means nothing was found.
    Sign flipping across horizons means nothing was found. Only the funding
    ADJUSTED return counts, because at 7 days funding is 168 charges and on a
    hot coin it exceeds the move being predicted.

SURVIVORSHIP: delisted markets are INCLUDED wherever Hyperliquid still serves
their history. Testing only today's survivors is how a strategy learns that
everything recovers - the coins that did not recover are the ones missing.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl.ic import print_table, rank_ic, self_tests, summarise  # noqa: E402
from hl.info import Info, now_ms  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "carry_cache"
DAY_MS = 86_400_000
HOUR_MS = 3_600_000


def pick_universe(info: Info, top: int) -> List[str]:
    """Liquid perps by 24h volume, plus every delisted market we can still get
    history for - leaving those out is survivorship bias."""
    meta, ctxs = info.meta_and_asset_ctxs()
    live, dead = [], []
    for a, c in zip(meta["universe"], ctxs):
        vol = float(c.get("dayNtlVlm") or 0)
        (dead if a.get("isDelisted") else live).append((a["name"], vol))
    live.sort(key=lambda x: -x[1])
    chosen = [n for n, _ in live[:top]] + [n for n, _ in dead]
    print(f"universe: {min(top, len(live))} live by volume + {len(dead)} delisted "
          f"= {len(chosen)}")
    return chosen


def fetch_daily(info: Info, coins: List[str], days: int, cached: bool) -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"daily_{days}.parquet"
    if cached and f.exists():
        return pd.read_parquet(f)
    end, start = now_ms(), now_ms() - (days + 10) * DAY_MS
    frames = {}
    for i, c in enumerate(coins, 1):
        try:
            rows = info.candles(c, "1d", start, end)
        except Exception:
            continue
        if rows:
            frames[c] = pd.Series({int(r["t"]): float(r["c"]) for r in rows})
        if i % 30 == 0:
            print(f"    candles {i}/{len(coins)}")
    px = pd.DataFrame(frames).sort_index()
    px.to_parquet(f)
    return px


def fetch_funding_daily(info: Info, coins: List[str], days: int,
                        cached: bool) -> pd.DataFrame:
    """Hourly funding, summed to a daily total per coin.

    fundingHistory returns 500 rows per call, which at hourly resolution is
    about 21 days, so a year takes ~18 paged calls per coin. That is the whole
    reason this is slow and it is also why nobody has this history lying around.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"funding_daily_{days}.parquet"
    if cached and f.exists():
        return pd.read_parquet(f)
    start_all = now_ms() - (days + 10) * DAY_MS
    frames = {}
    for i, c in enumerate(coins, 1):
        cursor = start_all
        rows: List[dict] = []
        for _page in range(days // 20 + 3):
            try:
                page = info.funding_history(c, cursor)
            except Exception:
                break
            if not page:
                break
            rows.extend(page)
            last = int(page[-1]["time"])
            if last <= cursor or len(page) < 400:
                break
            cursor = last + 1
        if rows:
            s = pd.Series({int(r["time"]): float(r["fundingRate"]) for r in rows})
            s.index = (s.index // DAY_MS) * DAY_MS
            frames[c] = s.groupby(level=0).sum()
        if i % 10 == 0:
            print(f"    funding {i}/{len(coins)}  ({len(rows)} rows for {c})")
    fd = pd.DataFrame(frames).sort_index()
    fd.to_parquet(f)
    return fd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--top", type=int, default=80)
    ap.add_argument("--cached", action="store_true")
    ap.add_argument("--min-names", type=int, default=20)
    args = ap.parse_args()

    info = Info()
    coins = pick_universe(info, args.top)

    print("fetching daily closes...")
    px = fetch_daily(info, coins, args.days, args.cached)
    print(f"  {px.shape[0]} days x {px.shape[1]} coins")
    print("fetching funding history (this is the slow part)...")
    fd = fetch_funding_daily(info, coins, args.days, args.cached)
    print(f"  {fd.shape[0]} days x {fd.shape[1]} coins")

    common = sorted(set(px.columns) & set(fd.columns))
    px, fd = px[common], fd[common].reindex(px.index)
    print(f"  {len(common)} coins with both price and funding")

    # ---- features, all computed from information available AT time t --------
    feats: Dict[str, pd.DataFrame] = {
        "funding_1d": fd,
        "funding_3d": fd.rolling(3, min_periods=2).mean(),
        "funding_7d": fd.rolling(7, min_periods=4).mean(),
        "funding_30d": fd.rolling(30, min_periods=15).mean(),
    }
    # How extreme is today's funding against this coin's OWN history? A raw
    # level is partly just "which coin is this" - some names always pay more.
    roll_mean = fd.rolling(60, min_periods=30).mean()
    roll_sd = fd.rolling(60, min_periods=30).std()
    feats["funding_z60"] = (fd - roll_mean) / roll_sd
    # Change in funding, not level: is the crowd piling in or backing out.
    feats["funding_chg_3d"] = fd.rolling(3).mean() - fd.rolling(3).mean().shift(3)

    # ---- forward returns, funding adjusted ---------------------------------
    fwds: Dict[int, pd.DataFrame] = {}
    for h in (1, 3, 7):
        price_ret = px.shift(-h) / px - 1.0
        carry = fd.shift(-h).rolling(h, min_periods=1).sum()   # paid by a long
        fwds[h] = price_ret - carry.reindex_like(price_ret)

    print("\nSELF TESTS")
    st = self_tests(feats["funding_7d"], fwds[1], 1, args.min_names)
    print_table(st, "must behave or nothing below is readable")

    rows = []
    for name, fdf in feats.items():
        for h, fwd in fwds.items():
            rows.append(summarise(rank_ic(fdf, fwd, args.min_names), h, name))
    res = pd.DataFrame(rows)
    print_table(res, "RESULT - funding features vs funding-adjusted forward return")

    out = ROOT / "data" / "carry_ic.csv"
    res.to_csv(out, index=False)
    print(f"\nwritten to {out}")
    print("\nPRE-REGISTERED READING:")
    print("  hypothesis was NEGATIVE IC (high funding -> underperform).")
    print("  |t indep| under 2.5 = nothing found. Sign flipping across")
    print("  horizons = nothing found. 6 features x 3 horizons = 18 tests, so")
    print("  about one |t| over 2 is expected from luck alone.")


if __name__ == "__main__":
    main()
