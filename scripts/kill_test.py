"""THE KILL-TEST: does any of the computed features predict forward returns?

    python scripts/kill_test.py                 # every feature, every table, 1/3/7 day horizons
    python scripts/kill_test.py --tables feat_osc,feat_ret
    python scripts/kill_test.py --min-names 8

HANDOFF §8a. 145 features in 8 tables pass all 22 correctness checks. Correct and
useless are compatible; nobody had measured whether one of them predicts anything.
This does, with hl/ic.py - the one statistics routine - so the numbers are
comparable with measure_momentum.py / measure_positioning.py.

METHOD (see hl/ic.py for why each part exists)
  * one observation per coin per day: the 00:00 UTC bar of every feature table,
    forward return = close h days later / close now - 1, h in {1, 3, 7}
  * rank coins against each other WITHIN each day, rank what happened next,
    Spearman-correlate -> one IC per day; the market's common move cancels
  * t-stat on NON-overlapping days (every h-th day) is the honest one

HONEST LIMITS, read before the table:
  * only 16 coins have features, so each day's ranking is 16 names wide (min 10
    after NaNs). Cross-sections this thin are noisy; hl/ic.py's default of 20
    names would discard every day, so --min-names is 10 here and it is said so.
  * 145 features x 3 horizons = 435 tests. At |t| > 2.5 about 5 pass by pure
    chance. A feature has to clear |t indep| > 3.3 (roughly Bonferroni at 435)
    AND |IC| > 0.015 (the tradeable floor used in measure_momentum.py) to be
    called a survivor. Anything between 2.5 and 3.3 is "look again", not "real".
  * price-LEVEL features (sma_20, bb_upper, obv, ...) rank BTC first every day
    by construction. They are measured anyway because Dev asked for all of them,
    but flagged LEVEL in the output - a result there is not a signal.
  * returns are price only; funding is not subtracted.

Memory: one table at a time, daily rows only (~37k rows x <=38 cols). Nothing
close to the 893k-row hourly tables is ever loaded.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl.ic import print_table, rank_ic, self_tests, summarise  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "store.db"
DAY_MS = 86_400_000

TABLES = ["feat_ret", "feat_volat", "feat_trend", "feat_osc", "feat_bands",
          "feat_vol_flow", "feat_risk", "feat_candle"]

# Scale-dependent: a price level, a price difference, or a raw volume/count.
# Ranking these across coins ranks the coins' price scale, not information.
LEVEL = {
    "sma_5", "sma_10", "sma_20", "sma_50", "sma_100", "sma_200",
    "ema_9", "ema_12", "ema_21", "ema_26", "ema_50", "ema_200",
    "macd", "macd_signal", "macd_hist", "psar", "supertrend", "linreg_slope",
    "donchian_hi", "donchian_lo", "donchian_mid",
    "ich_tenkan", "ich_kijun", "ich_senkou_a", "ich_senkou_b", "ich_chikou",
    "bb_upper", "bb_mid", "bb_lower", "keltner_up", "keltner_lo",
    "atr_band_up", "atr_band_lo", "chandelier_exit", "atr_14",
    "obv", "vwap_24h", "vol_sma_20", "ad_line", "force_index", "eom", "pvt",
    "trade_count", "avg_trade_size", "momentum_10", "awesome_osc", "logret_cum",
}

SURVIVE_T, LOOK_T, TRADE_IC = 3.3, 2.5, 0.015


def ro() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{STORE}?mode=ro", uri=True, timeout=30)


def daily_closes(conn: sqlite3.Connection, asset_ids: List[int]) -> pd.DataFrame:
    """00:00 UTC close per coin, from the 1h bars."""
    q = ("SELECT o.ts_ms, a.symbol, o.c FROM ohlcv o JOIN asset a ON a.id=o.asset_id "
         f"WHERE o.interval='1h' AND o.ts_ms % {DAY_MS} = 0 "
         f"AND o.asset_id IN ({','.join('?' * len(asset_ids))})")
    df = pd.read_sql_query(q, conn, params=asset_ids)
    return df.pivot(index="ts_ms", columns="symbol", values="c").sort_index()


def daily_features(conn: sqlite3.Connection, table: str, names: Dict[int, str]) -> pd.DataFrame:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")
            if r[1] not in ("ts_ms", "asset_id")]
    df = pd.read_sql_query(
        f"SELECT ts_ms, asset_id, {', '.join(cols)} FROM {table} WHERE ts_ms % {DAY_MS} = 0",
        conn)
    df["coin"] = df["asset_id"].map(names)
    return df.drop(columns="asset_id"), cols


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default=",".join(TABLES))
    ap.add_argument("--horizons", default="1,3,7")
    ap.add_argument("--min-names", type=int, default=10,
                    help="coins needed in a day's ranking (hl/ic.py default 20 > the 16 we have)")
    args = ap.parse_args()
    tables = [t.strip() for t in args.tables.split(",") if t.strip()]
    horizons = [int(h) for h in args.horizons.split(",")]

    conn = ro()
    ids = [r[0] for r in conn.execute("SELECT DISTINCT asset_id FROM feat_ret")]
    names = {i: s for i, s in conn.execute(
        f"SELECT id, symbol FROM asset WHERE id IN ({','.join('?' * len(ids))})", ids)}
    px = daily_closes(conn, ids)
    print(f"{len(ids)} coins with features: {' '.join(sorted(names.values()))}")
    print(f"{len(px)} daily closes, {pd.to_datetime(px.index[0], unit='ms').date()} -> "
          f"{pd.to_datetime(px.index[-1], unit='ms').date()}")
    fwds = {h: px.shift(-h) / px - 1.0 for h in horizons}

    rows, t0, n_feat = [], time.time(), 0
    for ti, table in enumerate(tables, 1):
        df, cols = daily_features(conn, table, names)
        print(f"\n[{ti}/{len(tables)}] {table}: {len(cols)} features, {len(df):,} daily rows")
        for col in cols:
            feat = df.pivot(index="ts_ms", columns="coin", values=col).sort_index()
            feat = feat.reindex(columns=px.columns)
            if ti == 1 and col == cols[0]:
                print_table(self_tests(feat, fwds[horizons[0]], horizons[0], args.min_names),
                            "SELF TESTS - must behave or nothing below is readable")
            for h in horizons:
                r = summarise(rank_ic(feat, fwds[h], args.min_names), h, col)
                r["table"] = table
                r["kind"] = "LEVEL" if col in LEVEL else "ok"
                rows.append(r)
            n_feat += 1
        print(f"    done, {time.time()-t0:.0f}s elapsed")
    conn.close()

    res = pd.DataFrame(rows)
    res["abs_t"] = res["t_indep"].abs()

    # COIN-PICKING CONTROL. With 16 coins, a feature that ranks them the same
    # way every day (DOGE is always the most volatile) cannot be told apart
    # from "which coins did well over these six years". So for every candidate
    # the test is re-run with each coin's feature FROZEN at its all-time mean
    # rank. If the frozen version scores about the same, the feature picks
    # coins, it does not time them. (The frozen rank uses the whole sample, so
    # it is a diagnostic ceiling, not a tradeable signal.)
    cand = res[(res["kind"] == "ok") & (res["abs_t"] > LOOK_T)]
    static_ic: Dict[tuple, float] = {}
    if len(cand):
        conn = ro()
        print(f"\ncoin-picking control on {cand['feature'].nunique()} candidate features...")
        for table, grp in cand.groupby("table"):
            df, _ = daily_features(conn, table, names)
            for col in grp["feature"].unique():
                feat = df.pivot(index="ts_ms", columns="coin", values=col).sort_index()
                feat = feat.reindex(columns=px.columns)
                mean_rank = feat.rank(axis=1).mean(axis=0)
                frozen = pd.DataFrame(np.tile(mean_rank.values, (len(feat), 1)),
                                      index=feat.index, columns=feat.columns).where(feat.notna())
                for h in grp.loc[grp["feature"] == col, "horizon_bars"].unique():
                    s = summarise(rank_ic(frozen, fwds[int(h)], args.min_names), int(h), col)
                    static_ic[(col, int(h))] = s["mean_ic"]
        conn.close()
    res["ic_frozen"] = [static_ic.get((f, int(h)), np.nan)
                        for f, h in zip(res["feature"], res["horizon_bars"])]
    # share of the IC that survives once coin identity is removed
    res["ic_timing"] = res["mean_ic"] - res["ic_frozen"]

    out = ROOT / "data" / "kill_test_ic.csv"
    res.drop(columns="abs_t").to_csv(out, index=False)

    n_tests = len(res)
    print(f"\n{'=' * 82}\nKILL-TEST RESULT: {n_feat} features x {len(horizons)} horizons = {n_tests} tests, "
          f"{len(ids)} coins, min {args.min_names} names/day")
    print(f"expected passes at |t|>{LOOK_T} by chance alone: ~{n_tests * 0.0124:.0f}")

    ok = res[res["kind"] == "ok"]
    surv = ok[(ok["abs_t"] > SURVIVE_T) & (ok["mean_ic"].abs() > TRADE_IC)]
    look = ok[(ok["abs_t"] > LOOK_T) & ~ok.index.isin(surv.index)]
    print_table(surv.sort_values("abs_t", ascending=False),
                f"SURVIVORS: |t indep| > {SURVIVE_T} AND |IC| > {TRADE_IC}  ({len(surv)})")
    print_table(look.sort_values("abs_t", ascending=False).head(25),
                f"LOOK AGAIN: |t indep| > {LOOK_T} but not a survivor  ({len(look)}, top 25 shown)")
    both = pd.concat([surv, look]).sort_values("abs_t", ascending=False)
    if len(both):
        print("\nCOIN-PICKING CONTROL for every candidate above")
        print("  'frozen' = same test with each coin's feature held at its all-time mean rank.")
        print("  'timing' = full IC minus frozen IC = what is left once coin identity is removed.")
        print(f"{'feature':<24}{'horizon':>8}{'full IC':>10}{'frozen IC':>11}{'timing IC':>11}  verdict")
        print("-" * 82)
        for _, r in both.iterrows():
            fz, tm = r["ic_frozen"], r["ic_timing"]
            if pd.isna(fz):
                verdict = "n/a"
            elif abs(tm) < TRADE_IC:
                verdict = "coin-picking (timing part below tradeable floor)"
            elif abs(tm) < abs(r["mean_ic"]) * 0.5:
                verdict = "mostly coin-picking"
            else:
                verdict = "timing information present"
            print(f"{r['feature']:<24}{r['horizon_d']:>7.0f}d{r['mean_ic']:>+10.4f}"
                  f"{fz:>+11.4f}{tm:>+11.4f}  {verdict}")

    lvl = res[(res["kind"] == "LEVEL") & (res["abs_t"] > LOOK_T)]
    print_table(lvl.sort_values("abs_t", ascending=False).head(10),
                f"LEVEL features over {LOOK_T} - price scale, NOT a signal  ({len(lvl)}, top 10)")
    print(f"\nfull table ({n_tests} rows) written to {out}")
    print("\nREADING THIS HONESTLY:")
    print("  16 coins is a thin cross-section. A survivor here earns a re-test on more")
    print("  coins (HANDOFF §8b), not a trade. Returns are price only, no funding.")
    print("  A pipeline that returns zeros looks exactly like 'no signal' - check the")
    print("  SELF TESTS block above says own-future ~ +1 before believing any zero.")


if __name__ == "__main__":
    main()
