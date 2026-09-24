"""Validate the breakout / position-in-range factor — the honest way.

The raw finding (near-highs -> continuation, t+6.6) rides the bull market. So this
does NOT trust the time-series number. It asks the harder questions:

  1. CROSS-SECTIONAL, BTC-NEUTRAL: does a coin near ITS OWN 30d high beat OTHER coins
     over the next 5-10d after removing beta*BTC? (a factor, not just market beta)
  2. BOTH-HALVES + net fees.
  3. Is it just momentum? IC of breakout vs the residual-momentum we already have, and
     their correlation — does breakout add anything on top?
  4. REGIME CONTROL (time-series BTC 9yr): does 'near highs -> up' hold when BTC is
     BELOW its 200d (i.e. not a raging bull), or only in bull regimes?
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FEE = 0.0020
L = 30   # range lookback


def zrows(df):
    return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1).replace(0, np.nan), axis=0)


def ic(sig, fwd):
    out = []
    for t in sig.index:
        s, y = sig.loc[t], fwd.loc[t]
        m = s.notna() & y.notna()
        if m.sum() >= 12:
            out.append(s[m].rank().corr(y[m].rank()))
    s = pd.Series(out).dropna()
    return (s.mean(), s.mean() / (s.std() / np.sqrt(len(s)))) if len(s) > 20 else (None, None)


def quintile(sig, fwd, H, sl=None):
    idx = sig.index[sl] if sl else sig.index
    rows = []
    for t in idx[::H]:
        s, y = sig.loc[t], fwd.loc[t]
        m = s.notna() & y.notna()
        if m.sum() < 15:
            continue
        s, y = s[m], y[m]
        k = max(2, int(len(s) * 0.2))
        rows.append(y[s.nlargest(k).index].mean() - y[s.nsmallest(k).index].mean() - 2 * FEE)
    r = pd.Series(rows).dropna()
    if len(r) < 6:
        return None
    return {"per": r.mean(), "sharpe": r.mean() / r.std() * np.sqrt(365.0 / H) if r.std() else 0,
            "hit": (r > 0).mean(), "n": len(r)}


def run():
    px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
    good = [c for c in px.columns if px[c].notna().sum() > 150]
    px = px[good]
    ret = px.pct_change(fill_method=None)
    btc = px["BTC"]; btc_ret = btc.pct_change()
    beta = ret.rolling(60).cov(btc_ret).div(btc_ret.rolling(60).var(), axis=0)

    rpos = (px - px.rolling(L).min()) / (px.rolling(L).max() - px.rolling(L).min())
    zbrk = zrows(rpos)
    # residual momentum we already trade (7d resid vs BTC), for the "does it add?" test
    ret7 = px / px.shift(7) - 1.0
    btc7 = btc / btc.shift(7) - 1.0
    resid7 = ret7.sub(beta.mul(btc7, axis=0))
    zmom = zrows(resid7)

    print(f"CROSS-SECTIONAL, BTC-NEUTRAL  ({px.shape[1]} coins x {px.shape[0]}d)")
    print(f"{'factor':<16}{'H':>3}{'IC':>8}{'IC t':>7}{'LS/reb':>9}{'Sharpe':>8}{'1stSh':>7}{'2ndSh':>7}")
    n = len(px)
    for name, sig in (("breakout(range)", zbrk), ("resid-momentum", zmom)):
        for H in (5, 10):
            fwd = px.shift(-H) / px - 1.0
            btcf = (btc.shift(-H) / btc - 1.0)
            fwd_resid = fwd.sub(beta.mul(btcf, axis=0))
            icv, ict = ic(sig, fwd_resid)
            full = quintile(sig, fwd_resid, H)
            h1 = quintile(sig, fwd_resid, H, slice(0, n // 2))
            h2 = quintile(sig, fwd_resid, H, slice(n // 2, n))
            if not full:
                continue
            print(f"{name:<16}{H:>3}{icv:>+8.3f}{ict:>+7.1f}{full['per']*100:>+8.2f}%{full['sharpe']:>+8.2f}"
                  f"{(h1['sharpe'] if h1 else float('nan')):>+7.2f}{(h2['sharpe'] if h2 else float('nan')):>+7.2f}")

    # does breakout add BEYOND momentum? correlation + combined
    corr = zbrk.corrwith(zmom, axis=1).mean()
    combo = (zbrk.fillna(0) + zmom.fillna(0)) / 2
    fwd = px.shift(-10) / px - 1.0
    fwd_resid = fwd.sub(beta.mul((btc.shift(-10) / btc - 1.0), axis=0))
    icc, ictc = ic(combo, fwd_resid)
    print(f"\nbreakout vs momentum cross-sectional corr: {corr:+.2f}  (high = same thing)")
    print(f"combined (breakout+momentum) H=10 IC t: {ictc:+.1f}")

    # REGIME CONTROL on BTC 9yr: near-highs effect below vs above the 200d
    from scripts.seasonality import fetch
    b = fetch("BTCUSDT").sort_index()
    pos = (b - b.rolling(L).min()) / (b.rolling(L).max() - b.rolling(L).min())
    fwd5 = b.shift(-5) / b - 1.0
    ma200 = b.rolling(200).mean()
    df = pd.DataFrame({"pos": pos, "fwd": fwd5, "bull": b > ma200}).dropna()
    print("\nREGIME CONTROL (BTC 9yr): forward-5d by range-position, split by 200d trend")
    for reg, sub in (("BULL (>200d)", df[df.bull]), ("BEAR (<200d)", df[~df.bull])):
        hi = sub[sub.pos >= 0.85]; loo = sub[sub.pos <= 0.15]
        def tt(x): return x.fwd.mean() / (x.fwd.std() / np.sqrt(len(x))) if len(x) > 5 else 0
        print(f"  {reg:<14} near-HIGH n={len(hi):>4} fwd {hi.fwd.mean()*100:>+5.2f}% t{tt(hi):>+4.1f}  |  "
              f"near-LOW n={len(loo):>4} fwd {loo.fwd.mean()*100:>+5.2f}% t{tt(loo):>+4.1f}")
    print("\nread: for breakout to be a REAL factor it must (a) have IC t>~2 BTC-neutral cross-sectionally,")
    print("      (b) survive both-halves, (c) add beyond momentum (low corr / combined IC up), and")
    print("      (d) work in BEAR regimes too — else it's just bull-market beta.")


if __name__ == "__main__":
    run()
