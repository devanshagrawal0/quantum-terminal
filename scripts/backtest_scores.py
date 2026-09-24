"""Unbiased test: does our composite score actually predict forward returns?

The whole point of a score is that a HIGH score should mean HIGHER return next.
This checks that honestly, with the discipline that separates real edge from a
story we tell ourselves:

  * POINT-IN-TIME — every feature at day t uses ONLY data up to t (shift()ed),
    so nothing peeks at the future. The future return is the LABEL only.
  * CROSS-SECTIONAL — the score is ranked across all coins each day (a +8% week
    only matters relative to the field), exactly like the live engine.
  * BOTH-HALVES — the edge must show in the first half AND the second half of
    history, not just ride one lucky melt-up (this is what killed funding-carry, L10).
  * NET OF FEES — long top-quintile / short bottom-quintile, charged the real
    Hyperliquid round-trip at each rebalance. An edge below the fee floor is dead.
  * BTC-NEUTRAL — forward return is measured vs BTC (residual), so we are testing
    stock-picking skill, not a levered market bet (the trap L9/L11 fell into).

It prints the Information Coefficient (rank-correlation of score->forward return),
its t-stat, and the long-short quintile performance per horizon. If the numbers are
flat, it SAYS flat — that is the unbiased result, not a failure to hide.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FEE_RT = 0.0009          # 0.045% x2 taker round-trip
FEE_RT_SLIP = 0.0020     # with slippage on a small perp


def load():
    px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
    fp = ROOT / "data" / "carry_cache" / "funding_daily_365.parquet"
    fund = pd.read_parquet(fp) if fp.exists() else None
    # keep coins with enough history
    good = [c for c in px.columns if px[c].notna().sum() > 150]
    return px[good], (fund[[c for c in good if c in fund.columns]] if fund is not None else None)


def zscore_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score: each ROW (a day) standardized across coins."""
    mu = df.mean(axis=1)
    sd = df.std(axis=1).replace(0, np.nan)
    return df.sub(mu, axis=0).div(sd, axis=0)


def build_composite(px: pd.DataFrame, fund):
    """The SAME factors + weights as the live engine, computed point-in-time."""
    ret = px.pct_change(fill_method=None)
    btc = px["BTC"] if "BTC" in px.columns else px.iloc[:, 0]
    btc_ret = btc.pct_change()

    # --- factors, all shift()ed so day t sees only <= t ---
    mom = px.shift(2) / px.shift(30) - 1.0            # 7-28d momentum, skip last 2d
    past = px.shift(31) / px.shift(90) - 1.0          # 30-90d (long reversal -> negative weight)
    ret3 = px / px.shift(3) - 1.0                     # 1-3d (reversal -> negative weight)
    fund_apr = (fund.reindex_like(px) * 365.0) if fund is not None else px * np.nan

    # residual 7d vs BTC: coin 7d move minus beta*BTC 7d move, beta on trailing 60d
    ret7 = px / px.shift(7) - 1.0
    btc7 = btc / btc.shift(7) - 1.0
    beta = ret.rolling(60).cov(btc_ret).div(btc_ret.rolling(60).var(), axis=0)
    resid7 = ret7.sub(beta.mul(btc7, axis=0))

    # realized vol (30d) for the vol-scale
    rv30 = ret.rolling(30).std() * np.sqrt(365)

    # cross-sectional z each factor, combine with the live weights
    zmom, zfund, zresid, zpast, zret3 = map(zscore_rows, (mom, fund_apr, resid7, past, ret3))
    raw = (1.0 * zmom - 0.8 * zfund.fillna(0) + 0.8 * zresid.fillna(0)
           - 0.5 * zpast - 0.3 * zret3) / 5.0
    scale = (0.6 / rv30).clip(upper=1.5)
    comp = raw * scale
    # each factor on its own, in the direction the live engine bets it, for the
    # per-factor honesty check (is the blend hiding one live factor?)
    factors = {"momentum": zmom, "funding(-)": -zfund, "resid7": zresid,
               "longrev(-)": -zpast, "rev3d(-)": -zret3}
    return comp, btc_ret, beta, factors


def fwd_resid_return(px, btc_ret, beta, H):
    """Forward H-day return, BTC-neutralized (the honest label)."""
    fwd = px.shift(-H) / px - 1.0
    btc_fwd = (btc_ret.add(1).rolling(H).apply(np.prod, raw=True).shift(-H) - 1.0)
    return fwd.sub(beta.mul(btc_fwd, axis=0))


def ic_stats(comp, label):
    """Daily cross-sectional Spearman IC of score vs forward return."""
    ics = []
    for t in comp.index:
        s, y = comp.loc[t], label.loc[t]
        m = s.notna() & y.notna()
        if m.sum() >= 12:
            ics.append(s[m].rank().corr(y[m].rank()))
    ics = pd.Series(ics).dropna()
    if len(ics) < 20:
        return None
    t_stat = ics.mean() / (ics.std() / np.sqrt(len(ics)))
    return {"ic": ics.mean(), "ic_t": t_stat, "n_days": len(ics), "hit": (ics > 0).mean()}


def quintile_ls(comp, label, H, fee):
    """Long top-quintile, short bottom-quintile, rebalanced every H days
    (non-overlapping so returns don't double-count). Net of fee per rebalance."""
    days = comp.index[::H]
    rows = []
    for t in days:
        s, y = comp.loc[t], label.loc[t]
        m = s.notna() & y.notna()
        if m.sum() < 15:
            continue
        s, y = s[m], y[m]
        k = max(2, int(len(s) * 0.2))
        top = y[s.nlargest(k).index].mean()
        bot = y[s.nsmallest(k).index].mean()
        rows.append(top - bot - 2 * fee)     # both legs turn over -> 2x round-trip
    r = pd.Series(rows).dropna()
    if len(r) < 8:
        return None
    ann = (1 + r.mean()) ** (365.0 / H) - 1
    sharpe = r.mean() / r.std() * np.sqrt(365.0 / H) if r.std() else 0.0
    return {"per_reb": r.mean(), "ann": ann, "sharpe": sharpe, "hit": (r > 0).mean(), "n": len(r)}


def long_only_vs_ls(px, factors, btc_ret, beta, H=10, fee=FEE_RT_SLIP):
    """The call: is dropping the short leg better? Compares, on the LIVE score
    (funding + relative-strength), three books rebalanced every H days:
      LONG-SHORT   : long top quintile, short bottom quintile (BTC-neutral, 2 fee legs)
      LONG hedged  : long top quintile only, BTC-neutral (short BTC as hedge, 1 fee leg)
      LONG unhedged: long top quintile, take the market beta too (1 fee leg)
    Reports net annualized return, Sharpe, hit, and BOTH-HALVES Sharpe for each."""
    import numpy as np
    comp7 = (factors["funding(-)"].fillna(0) + factors["resid7"].fillna(0)) / 2.0
    resid = fwd_resid_return(px, btc_ret, beta, H)          # BTC-neutral label
    raw = px.shift(-H) / px - 1.0                           # unhedged label
    n = len(comp7)

    def series(idx, kind, decile=False):
        out = []
        for t in idx[::H]:
            s = comp7.loc[t]
            yb = resid.loc[t]
            yr = raw.loc[t]
            m = s.notna() & yb.notna() & yr.notna()
            if m.sum() < 15:
                continue
            s = s[m]
            k = max(2, int(len(s) * (0.1 if decile else 0.2)))
            top = s.nlargest(k).index
            bot = s.nsmallest(k).index
            if kind == "ls":
                out.append(yb[top].mean() - yb[bot].mean() - 2 * fee)
            elif kind == "long_hedged":
                out.append(yb[top].mean() - fee)
            elif kind == "long_unhedged":
                out.append(yr[top].mean() - fee)
        return np.array(out)

    def stat(arr):
        if len(arr) < 8:
            return None
        ann = (1 + arr.mean()) ** (365.0 / H) - 1
        sharpe = arr.mean() / arr.std() * np.sqrt(365.0 / H) if arr.std() else 0.0
        return {"ann": ann, "sharpe": sharpe, "hit": (arr > 0).mean(), "n": len(arr),
                "per": arr.mean()}

    variants = [("LONG-SHORT (quintile)", "ls", False),
                ("LONG-only hedged (quintile)", "long_hedged", False),
                ("LONG-only hedged (decile)", "long_hedged", True),
                ("LONG-only UNhedged (quintile)", "long_unhedged", False)]
    print(f"\nLONG-ONLY vs LONG-SHORT  (H={H}d, net {fee*100:.2f}%/leg, on the live funding+strength score)")
    print(f"{'book':>32} {'per-reb':>8} {'annual':>8} {'Sharpe':>7} {'hit':>5} {'1stSh':>6} {'2ndSh':>6} {'n':>4}")
    print("-" * 88)
    results = {}
    for name, kind, dec in variants:
        full = stat(series(comp7.index, kind, dec))
        h1 = stat(series(comp7.index[:n // 2], kind, dec))
        h2 = stat(series(comp7.index[n // 2:], kind, dec))
        if not full:
            print(f"{name:>32}  (insufficient)"); continue
        results[name] = (full, h1, h2)
        print(f"{name:>32} {full['per']*100:>+7.2f}% {full['ann']*100:>+7.1f}% {full['sharpe']:>+7.2f} "
              f"{full['hit']*100:>4.0f}% {(h1['sharpe'] if h1 else float('nan')):>+6.2f} "
              f"{(h2['sharpe'] if h2 else float('nan')):>+6.2f} {full['n']:>4}")
    return results


def fng_overlay(px, comp, btc_ret, beta, H=10, thresh=0.25):
    """Does the market's mood change the score's edge? Split every directional pick's
    BTC-neutral outcome by the Fear&Greed reading at entry. If the long edge dies in
    extreme greed (or shorts die in extreme fear), a mood gate helps; if flat across
    buckets, F&G adds nothing."""
    try:
        from hl import fng
        fseries = fng.series()
    except Exception as e:
        print(f"\nF&G OVERLAY: unavailable ({e})"); return
    label = fwd_resid_return(px, btc_ret, beta, H)
    # F&G value per price-index day (as-of, no lookahead)
    fvals = {}
    fidx = fseries.index.values
    import numpy as np
    for ts in px.index:
        prior = fseries[fseries.index <= ts]
        fvals[ts] = int(prior.iloc[-1]) if len(prior) else np.nan

    def bucket(v):
        if v != v:
            return None
        return "fear<40" if v < 40 else "greed>65" if v > 65 else "neutral"

    stats = {}   # (side, bucket) -> [edges]
    for t in comp.index:
        b = bucket(fvals.get(t, np.nan))
        if not b:
            continue
        s, y = comp.loc[t], label.loc[t]
        m = s.notna() & y.notna()
        for coin in s[m].index:
            sc = s[coin]
            if abs(sc) < thresh:
                continue
            side = "LONG" if sc > 0 else "SHORT"
            edge = y[coin] if sc > 0 else -y[coin]
            stats.setdefault((side, b), []).append(edge)

    print(f"\nF&G OVERLAY (H={H}): avg BTC-neutral edge per pick, gross, split by mood at entry")
    print(f"{'side':>6} {'mood':>10} {'n':>6} {'avg edge':>9} {'hit':>6}")
    print("-" * 44)
    for side in ("LONG", "SHORT"):
        for b in ("fear<40", "neutral", "greed>65"):
            e = stats.get((side, b), [])
            if not e:
                continue
            arr = np.array(e)
            print(f"{side:>6} {b:>10} {len(arr):>6} {arr.mean()*100:>+8.2f}% {(arr>0).mean()*100:>5.0f}%")
    print("read: if LONG edge collapses in greed>65 or SHORT edge in fear<40, gate that side by mood.")


def run():
    px, fund = load()
    comp, btc_ret, beta, factors = build_composite(px, fund)
    n = len(comp)
    first, second = comp.iloc[:n // 2], comp.iloc[n // 2:]
    print(f"universe: {px.shape[1]} coins x {px.shape[0]} days   (split at day {n//2})\n")
    print(f"{'H':>3} {'IC':>7} {'IC t':>6} {'hitday':>6} | {'LS/reb':>8} {'annual':>8} {'Sharpe':>7} {'hit':>5} "
          f"| {'1st-half Sh':>11} {'2nd-half Sh':>11}  (net {FEE_RT_SLIP*100:.2f}%/side)")
    print("-" * 104)
    for H in (1, 2, 3, 5, 7):
        label = fwd_resid_return(px, btc_ret, beta, H)
        ic = ic_stats(comp, label)
        ls = quintile_ls(comp, label, H, FEE_RT_SLIP)
        h1 = quintile_ls(first, label.loc[first.index], H, FEE_RT_SLIP)
        h2 = quintile_ls(second, label.loc[second.index], H, FEE_RT_SLIP)
        if not (ic and ls):
            print(f"{H:>3}  (insufficient data)")
            continue
        print(f"{H:>3} {ic['ic']:>+7.3f} {ic['ic_t']:>+6.2f} {ic['hit']*100:>5.0f}% | "
              f"{ls['per_reb']*100:>+7.2f}% {ls['ann']*100:>+7.1f}% {ls['sharpe']:>+7.2f} {ls['hit']*100:>4.0f}% | "
              f"{(h1['sharpe'] if h1 else float('nan')):>+11.2f} {(h2['sharpe'] if h2 else float('nan')):>+11.2f}")
    # ---- candidate: the horizon-honest 7-day score (only the factors that survived
    #      at H=7: funding + relative-strength), tested both-halves before we trust it ----
    comp7 = (factors["funding(-)"].fillna(0) + factors["resid7"].fillna(0)) / 2.0
    c1, c2 = comp7.iloc[:n // 2], comp7.iloc[n // 2:]
    print("\nCANDIDATE 7-day score = z(funding short) + z(rel-strength vs BTC):")
    print(f"{'H':>3} {'IC':>7} {'IC t':>6} | {'LS/reb':>8} {'Sharpe':>7} {'hit':>5} | {'1st Sh':>7} {'2nd Sh':>7}")
    print("-" * 66)
    for H in (5, 7, 10):
        label = fwd_resid_return(px, btc_ret, beta, H)
        ic = ic_stats(comp7, label)
        ls = quintile_ls(comp7, label, H, FEE_RT_SLIP)
        h1 = quintile_ls(c1, label.loc[c1.index], H, FEE_RT_SLIP)
        h2 = quintile_ls(c2, label.loc[c2.index], H, FEE_RT_SLIP)
        if not (ic and ls):
            print(f"{H:>3}  (insufficient)"); continue
        print(f"{H:>3} {ic['ic']:>+7.3f} {ic['ic_t']:>+6.2f} | {ls['per_reb']*100:>+7.2f}% {ls['sharpe']:>+7.2f} "
              f"{ls['hit']*100:>4.0f}% | {(h1['sharpe'] if h1 else float('nan')):>+7.2f} {(h2['sharpe'] if h2 else float('nan')):>+7.2f}")

    # ---- per-factor honesty check: is the blend burying one live factor? ----
    print("\nPER-FACTOR IC (each factor alone, signed the way we bet it):")
    print(f"{'factor':>12} | " + "  ".join(f"H={H} IC(t)".rjust(13) for H in (1, 3, 7)))
    print("-" * 60)
    for name, f in factors.items():
        cells = []
        for H in (1, 3, 7):
            lab = fwd_resid_return(px, btc_ret, beta, H)
            st = ic_stats(f, lab)
            cells.append(f"{st['ic']:>+6.3f}({st['ic_t']:>+4.1f})" if st else "     n/a     ")
        print(f"{name:>12} | " + "  ".join(c.rjust(13) for c in cells))

    long_only_vs_ls(px, factors, btc_ret, beta, H=10)
    fng_overlay(px, comp, btc_ret, beta, H=10)

    print("\nread: IC t > ~2 means the score's ranking predicts forward return beyond noise.")
    print("      Sharpe must be POSITIVE in BOTH halves to be believed (else it's one lucky regime).")
    print("      LS/reb is the top-minus-bottom quintile return per rebalance, already net of fees.")


if __name__ == "__main__":
    run()
