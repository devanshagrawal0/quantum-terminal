"""Backtest the calendar overlays as ACTUAL trades, net of fees.

Two rules from the movement sheet:
  FOMC-long  : buy the day before an FOMC decision, sell at the FOMC-day close (1-day
               hold that spans the ~2pm ET announcement). ~46 trades since 2020.
  Thu-short  : short from Wed close to Thu close (fade the weak day). ~470 trades.

Honesty gauntlet: net of a real round-trip fee (0.09% taker AND 0.20% with slippage),
per-trade t-stat, hit rate, BOTH-HALVES, and — critically for FOMC — WITH and WITHOUT
the 2020 COVID emergency cuts, so a couple of outliers can't manufacture the edge.
Also a combined equity curve vs buy-and-hold.

    python scripts/backtest_overlay.py
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from scripts.seasonality import fetch, FOMC, COINS

FEE_T = 0.0009    # taker round-trip
FEE_S = 0.0020    # with slippage
EMERGENCY_2020 = {"2020-03-03", "2020-03-15"}


def series(sym):
    px = fetch(sym).sort_index()
    return np.log(px).diff().dropna()   # daily log returns, indexed by day


def report(name, rets: pd.Series):
    """rets = per-trade NET return series (already fee-adjusted, signed for the trade)."""
    r = rets.dropna()
    n = len(r)
    if n < 5:
        print(f"  {name:<34} (n={n} too few)"); return
    m = r.mean()
    t = m / (r.std(ddof=1) / np.sqrt(n)) if r.std(ddof=1) else 0
    tot = (1 + r).prod() - 1
    h1, h2 = r.iloc[:n // 2], r.iloc[n // 2:]
    print(f"  {name:<34} n={n:>4}  avg {m*100:>+5.2f}%  t{t:>+5.1f}  hit {(r>0).mean()*100:>3.0f}%  "
          f"total {tot*100:>+7.1f}%  |  half-avg {h1.mean()*100:>+.2f}% / {h2.mean()*100:>+.2f}%")


def fomc_trades(ret: pd.Series, fee, drop_emergency=False):
    """Return the NET per-trade return for longing each FOMC day (close-to-close)."""
    out = {}
    fdates = [d for d in FOMC if not (drop_emergency and d in EMERGENCY_2020)]
    for d in fdates:
        ts = pd.Timestamp(d, tz="UTC").normalize()
        hit = ret.index[ret.index.normalize() == ts]
        if len(hit):
            out[hit[0]] = ret.loc[hit[0]] - fee     # long, pay round-trip fee
    return pd.Series(out).sort_index()


def thu_trades(ret: pd.Series, fee):
    """NET per-trade return for SHORTING each Thursday (fade)."""
    thu = ret[ret.index.weekday == 3]
    return (-thu - fee).sort_index()               # short => +(-ret), minus fee


def run():
    btc = series("BTCUSDT")
    print("=" * 96)
    print("FOMC-LONG overlay (buy into the decision, 1-day hold, close-to-close)")
    print("=" * 96)
    print("BTC:")
    report("  FOMC-long  @0.09% fee", fomc_trades(btc, FEE_T))
    report("  FOMC-long  @0.20% fee (slippage)", fomc_trades(btc, FEE_S))
    report("  FOMC-long  @0.20%, EX-2020-emergency", fomc_trades(btc, FEE_S, drop_emergency=True))

    # basket: equal-weight the 12 coins on each FOMC day (robustness across coins)
    per = {}
    for c in COINS:
        r = series(c + "USDT")
        s = fomc_trades(r, FEE_S)
        for dt, v in s.items():
            per.setdefault(dt, []).append(v)
    basket = pd.Series({dt: np.mean(v) for dt, v in per.items()}).sort_index()
    print("12-COIN BASKET (equal-weight each FOMC day):")
    report("  FOMC-long basket @0.20%", basket)
    report("  FOMC-long basket EX-emergency @0.20%",
           basket[[d for d in basket.index if d.strftime('%Y-%m-%d') not in EMERGENCY_2020]])

    print("\n" + "=" * 96)
    print("THURSDAY-SHORT overlay (fade the weak day, Wed->Thu close)")
    print("=" * 96)
    for c in ("BTC", "ETH", "LTC", "ADA"):
        report(f"  Thu-short {c} @0.20%", thu_trades(series(c + "USDT"), FEE_S))
    report("  Thu-short BTC @0.09%", thu_trades(btc, FEE_T))

    # ---- combined equity: hold BTC always, but flat on Thursdays, + a FOMC-day extra long ----
    print("\n" + "=" * 96)
    print("EQUITY CURVES on BTC (does the overlay beat buy-and-hold, net of fees?)")
    print("=" * 96)
    fomc_set = set(pd.Timestamp(d, tz="UTC").normalize() for d in FOMC)
    daily = btc.copy()
    # strategy A: buy & hold
    bh = (1 + daily).prod() - 1
    # strategy B: skip Thursdays (go flat Thu; assume you exit Wed close, re-enter Fri -> 1 fee each skip)
    skip = daily.copy()
    is_thu = skip.index.weekday == 3
    skip[is_thu] = 0.0
    # cost: two fees per skipped week (out Wed, in Fri) -> approximate 2*FEE_S per Thursday
    skip_cost = is_thu.sum() * 2 * FEE_S
    skipB = (1 + skip).prod() - 1 - skip_cost
    # strategy C: skip Thu + double-size the FOMC day (2x on FOMC days), fee on the extra
    boosted = skip.copy()
    for dt in fomc_set:
        if dt in boosted.index:
            boosted.loc[dt] = daily.loc[dt] * 2 - FEE_S   # 2x long on FOMC day (extra fee)
    boostC = (1 + boosted).prod() - 1 - skip_cost
    print(f"  A  buy & hold BTC:                 {bh*100:>+9.1f}%")
    print(f"  B  skip Thursdays (net fees):      {skipB*100:>+9.1f}%")
    print(f"  C  skip Thu + 2x FOMC day:         {boostC*100:>+9.1f}%")
    print("\n  (equity = cumulative product of daily returns over the full sample; "
          "B/C charged real fees for every Thursday exit/re-entry.)")
    print("\nread: an overlay 'works' only if avg net > 0 with t>~2 AND positive in BOTH halves,")
    print("      AND the FOMC edge must SURVIVE dropping the 2020 emergency cuts (else it's 2 outliers).")


if __name__ == "__main__":
    run()
