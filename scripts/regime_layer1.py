"""Validate Layer 1 — does the risk-on/off read actually predict the tide?

Point-in-time: for every historical day, take the regime label computed from ONLY
that day's trailing data, then look at what BTC did over the NEXT 30 days. If the read
is real, RISK-ON precedes higher forward returns and smaller drawdowns than RISK-OFF —
in both halves of history, not just one. Also runs a 'step aside in RISK-OFF' timing
strategy vs buy-and-hold, net of fees, on Sharpe and max-drawdown (the honest test of
whether the tide read is worth acting on).
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from hl.macro_regime import score_series, _load_btc

FEE = 0.0020


def fwd_ret(px, H):
    return px.shift(-H) / px - 1.0


def maxdd(equity):
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1.0).min())


def run():
    px = _load_btc()
    s = score_series(px).dropna()
    px = px.loc[s.index]
    ret = np.log(px).diff().fillna(0)
    print(f"BTC {s.index[0].date()} -> {s.index[-1].date()}, {len(s)} days\n")

    print("== FORWARD 30-DAY BTC RETURN BY REGIME (point-in-time) ==")
    for H in (7, 30):
        f = fwd_ret(px, H)
        print(f"  horizon {H}d:")
        for lab in ("RISK-ON", "NEUTRAL", "RISK-OFF"):
            m = s["label"] == lab
            r = f[m].dropna()
            if len(r) < 20:
                print(f"    {lab:<9} (n={len(r)} too few)"); continue
            print(f"    {lab:<9} n={len(r):>4}  avg fwd {r.mean()*100:>+6.1f}%  win {(r>0).mean()*100:>3.0f}%  "
                  f"median {r.median()*100:>+6.1f}%")

    print("\n== BOTH-HALVES (30d fwd avg by regime) ==")
    f30 = fwd_ret(px, 30)
    n = len(s)
    for half, sl in (("1st", slice(0, n // 2)), ("2nd", slice(n // 2, n))):
        ss, ff = s.iloc[sl], f30.iloc[sl]
        row = []
        for lab in ("RISK-ON", "NEUTRAL", "RISK-OFF"):
            r = ff[ss["label"] == lab].dropna()
            row.append(f"{lab} {r.mean()*100:+.1f}%(n{len(r)})" if len(r) > 10 else f"{lab} n/a")
        print(f"  {half}-half: " + "   ".join(row))

    print("\n== TIMING STRATEGY: hold BTC unless RISK-OFF (step aside), net fees ==")
    invested = (s["label"] != "RISK-OFF").astype(float)   # 1 in on/neutral, 0 in risk-off
    pos = invested.shift(1).fillna(1.0)                    # act on yesterday's signal (no lookahead)
    strat_ret = pos * ret
    switches = pos.diff().abs().fillna(0)
    strat_ret = strat_ret - switches * FEE                 # fee on every entry/exit
    def eq(r): return (1 + (np.exp(r) - 1)).cumprod() if False else np.exp(r.cumsum())
    bh_eq = np.exp(ret.cumsum())
    st_eq = np.exp(strat_ret.cumsum())
    def sharpe(r): return r.mean() / r.std() * np.sqrt(365) if r.std() else 0
    print(f"  {'':<16}{'total':>10}{'Sharpe':>9}{'maxDD':>9}{'time in mkt':>12}")
    print(f"  {'buy & hold':<16}{(bh_eq.iloc[-1]-1)*100:>+9.0f}%{sharpe(ret):>9.2f}{maxdd(bh_eq)*100:>+8.0f}%{'100%':>12}")
    print(f"  {'step-aside':<16}{(st_eq.iloc[-1]-1)*100:>+9.0f}%{sharpe(strat_ret):>9.2f}{maxdd(st_eq)*100:>+8.0f}%"
          f"{pos.mean()*100:>11.0f}%")
    print(f"  switches (fee events): {int(switches.sum())}")

    print("\n== CURRENT READ ==")
    from hl.macro_regime import read
    r = read()
    print(f"  {r['as_of']}  BTC ${r['btc']:,.0f}  ->  {r['label']} (score {r['score']})")
    print(f"  {r['read']}")
    print("\nread: the tide read WORKS if RISK-ON fwd-return > RISK-OFF in BOTH halves, and step-aside")
    print("      cuts max-drawdown meaningfully without killing return (higher Sharpe).")


if __name__ == "__main__":
    run()
