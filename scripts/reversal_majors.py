"""The 1-day reversal, re-tested on the MAJORS only, net of measured costs.

    python scripts/reversal_majors.py
    python scripts/reversal_majors.py --top 20,40,80

WHY. validate_reversal.py killed the 1-day reversal on one year of Hyperliquid
daily data: net -20 bps/day, "lives entirely in illiquid coins where the spread
is wider than the edge". The 2026-09-13 kill-test (docs/KILL_TEST_2026-09-13.md)
found the same statistic (IC +0.0336) on the 16 MOST liquid coins over 6.7
years - so the "illiquid only" part was wrong, and the cost question has to be
asked again where the spread is ~1 bp, not 8.

WHAT IS REUSED, ON PURPOSE. The book, the cost model and the report come from
validate_reversal.py unchanged: a long/short book rebalanced daily, each unit
traded charged Hyperliquid's taker fee plus half that coin's MEASURED spread,
on entry and again on exit. Same numbers as before, so the two runs compare.

WHAT IS DIFFERENT.
  * 6.7 years of daily closes (the 00:00 UTC hourly bar) from store.db for all
    172 coins, instead of 1 year of HL daily candles.
  * "Majors" = the N coins with the TIGHTEST measured Hyperliquid spread, for
    N in --top. Not volume: credible_vol_usd is ~100x too high for the 1000x
    contracts (PEPE shows $2T/day), a defect noted in the handoff, not fixed here.
  * Year-by-year split instead of halves, because six years allow it.
  * One extra line per set: maker fees (1.5 bps/side) instead of taker (4.5).
    That is an ASSUMPTION - a resting order is not guaranteed a fill on the
    day a reversal is expected - and it is labelled as such.

WHAT WOULD MAKE THIS WRONG (written before the numbers):
  net bps/day <= 0 on taker fees for every N = the trade is dead on majors too.
  net > 0 only on maker fees = it depends on fills we cannot promise.
  net > 0 only in some years = a story about those years.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_reversal as vr  # noqa: E402  (book, costs, report - reused as is)
from hl.ic import rank_ic, summarise  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "store.db"
DAY_MS = 86_400_000
MAKER_BPS = 1.5


def daily_closes() -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{STORE}?mode=ro", uri=True, timeout=30)
    df = pd.read_sql_query(
        "SELECT o.ts_ms, a.symbol, o.c FROM ohlcv o JOIN asset a ON a.id=o.asset_id "
        f"WHERE o.interval='1h' AND o.ts_ms % {DAY_MS} = 0", conn)
    conn.close()
    px = df.pivot(index="ts_ms", columns="symbol", values="c").sort_index()
    px.index = pd.to_datetime(px.index, unit="ms", utc=True)
    return px


def run_set(label: str, px: pd.DataFrame, spread: pd.Series, min_names: int) -> list:
    rets = px.pct_change()
    fwd1 = px.shift(-1) / px - 1.0
    signal = -rets
    vol30 = rets.rolling(30, min_periods=15).std().shift(1)
    inv_vol = (1.0 / vol30).replace([np.inf, -np.inf], np.nan)

    rows = []
    variants = [
        ("daily rebalance, equal wt", signal, None, None),
        ("vol-scaled", signal, inv_vol, None),
        ("vol-scaled + exit band .45", signal, inv_vol, 0.45),
    ]
    for name, sig, iv, band in variants:
        g, t, w = vr.build_book(sig, fwd1, min_names=min_names, inv_vol=iv, exit_band=band)
        taker = vr.cost_of(w, spread)
        r = vr.report(g, taker, t, f"{label} | {name}")
        # maker-fee line: same book, fee 1.5 instead of 4.5 bps a side (assumption)
        vr.FEE_BPS_PER_SIDE, keep = MAKER_BPS, vr.FEE_BPS_PER_SIDE
        maker = vr.cost_of(w, spread)
        vr.FEE_BPS_PER_SIDE = keep
        r["net_bps_day_maker"] = float((g - maker).mean() * 1e4)
        rows.append(r)
        if band is not None:      # the cheapest variant gets the year split
            for yr, idx in signal.groupby(signal.index.year).groups.items():
                gy, cy = g.reindex(idx), taker.reindex(idx)
                if gy.notna().sum() < 60:
                    continue
                ry = vr.report(gy, cy, t.reindex(idx), f"{label} | {name} | {yr}")
                ry["net_bps_day_maker"] = float((gy - maker.reindex(idx)).mean() * 1e4)
                rows.append(ry)
    ic = rank_ic(signal, fwd1, min_names)
    s = summarise(ic, 1, label)
    print(f"  {label}: {px.shape[1]} coins, {px.shape[0]} days, raw IC {s['mean_ic']:+.4f} "
          f"t {s['t_indep']:+.2f} on {s['n']} days")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", default="20,40,80", help="sizes of the tightest-spread sets")
    args = ap.parse_args()
    tops = [int(x) for x in args.top.split(",")]

    px = daily_closes()
    spread, _vol = vr.load_costs(ROOT / "data" / "venues.db")
    spread = spread.reindex(px.columns)
    print(f"{px.shape[1]} coins with daily closes {px.index[0].date()} -> {px.index[-1].date()}; "
          f"measured HL spread for {int(spread.notna().sum())} of them, median {spread.median():.2f} bps")
    ranked = spread.dropna().sort_values()

    rows = []
    for n in tops:
        cols = list(ranked.index[:n])
        print(f"\ntightest {n}: spread <= {ranked.iloc[:n].max():.2f} bps  "
              f"({', '.join(cols[:8])}{', ...' if n > 8 else ''})")
        rows += run_set(f"top{n}", px[cols], spread, min_names=min(10, max(5, n // 3)))
    rows += run_set("all coins", px, spread, min_names=20)

    res = pd.DataFrame(rows)
    print(f"\n{'book':<48}{'days':>6}{'gross':>8}{'cost':>7}{'net':>8}{'netMkr':>8}"
          f"{'turn':>6}{'netSR':>7}{'hit':>6}")
    print("-" * 104)
    for _, r in res.iterrows():
        print(f"{r['label']:<48}{r['days']:>6}{r['gross_bps_day']:>+8.2f}{r['cost_bps_day']:>7.2f}"
              f"{r['net_bps_day']:>+8.2f}{r['net_bps_day_maker']:>+8.2f}{r['turnover']:>6.2f}"
              f"{r['net_sharpe']:>+7.2f}{r['hit']*100:>5.0f}%")
    print("\nbps/day: gross = before costs; cost = taker fee 4.5 + half measured spread, on every unit "
          "traded, both ways; net = gross - cost; netMkr = the same book on MAKER fees (1.5/side) - "
          "an assumption, fills are not promised.")
    print(f"configurations in this table: {len(res)}. The best cell is where a false positive lives.")
    out = ROOT / "data" / "reversal_majors.csv"
    res.to_csv(out, index=False)
    print(f"written to {out}")


if __name__ == "__main__":
    main()
