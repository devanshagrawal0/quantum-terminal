"""Validate the FADE-THE-BLOWOFF short — the edge we missed.

Dev's point, made concrete: a coin that has already shot up hard tends to reach a
breaking point and reverse. Our long-only momentum book had NO cap for this and
happily bought STX at +109% in 7d, which is exactly the zone that reverses. The
earlier decile test (scripts, in-session) showed forward-10d BTC-neutral:
    +70-120% 7d gain -> -6.76% (both halves negative, t -2.2)
    >+120%           -> -9.93%
So the *long* was wrong; the question here is whether the *short* is a real,
tradable edge or just hindsight — because shorting a hot coin can get squeezed.

This tests, unbiased:
  1. Short coins up > THRESH% in 7d, hold H days. Net-of-fees P&L (short = -fwd).
  2. Both halves of history (an edge that only works in one half is not an edge).
  3. Squeeze risk: the WORST adverse excursion (how hard it rips up before it works)
     and the win rate — shorting is only tradable if the tail doesn't kill you.
  4. Does a FUNDING filter help? Only short when funding is POSITIVE (crowded longs
     paying) — the flow read. Crowded-long blow-offs should reverse harder.
  5. BTC-neutral (hedge the short with a small BTC long) vs raw.

No hardcoded coin lists. Pooled across the whole liquid universe.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FEE_RT = 0.004      # ~0.20%/side all-in with slippage, round trip, on a small perp

def load():
    px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet").sort_index()
    cols = [c for c in px.columns if px[c].notna().sum() > 120]
    px = px[cols]
    fp = ROOT / "data" / "carry_cache" / "funding_daily_365.parquet"
    fund = pd.read_parquet(fp).sort_index() if fp.exists() else None
    return px, fund

def build(px, fund, look=7, fwd=10):
    idx = px.index
    btc = px["BTC"]
    recs = []
    for i in range(look, len(idx) - fwd):
        b0, bm, bf = btc.iloc[i], btc.iloc[i - look], btc.iloc[i + fwd]
        if not (b0 > 0 and bm > 0 and bf > 0):
            continue
        btc_fwd = bf / b0 - 1
        for c in px.columns:
            if c == "BTC":
                continue
            p0, pm = px[c].iloc[i], px[c].iloc[i - look]
            pf = px[c].iloc[i + fwd]
            if not (p0 > 0 and pm > 0 and pf > 0):
                continue
            mom = p0 / pm - 1
            fwd_ret = pf / p0 - 1
            # worst adverse excursion for a SHORT = biggest UP move within the hold
            path = px[c].iloc[i:i + fwd + 1] / p0 - 1
            max_up = float(path.max())          # how far it rips against a short
            f = np.nan
            if fund is not None and c in fund.columns:
                fh = fund[c]
                if i < len(fh):
                    val = fh.iloc[i]
                    f = float(val * 365) if val == val else np.nan
            recs.append((idx[i], c, mom, fwd_ret, fwd_ret - btc_fwd, max_up, f))
    return pd.DataFrame(recs, columns=["date", "coin", "mom", "fwd", "fwdn", "max_up", "fund"])

def report(A):
    print(f"pooled: {len(A)} obs, {A.coin.nunique()} coins, {A.date.nunique()} days\n")
    print("FADE-THE-BLOWOFF: short coins up >THRESH in 7d, hold 10d.")
    print("short P&L = -(forward return) - fees. BTC-neutral hedges the short with BTC long.\n")
    hdr = f"{'threshold':<12}{'n':>5}{'short raw':>11}{'short neutral':>14}{'net(fee)':>10}{'win%':>7}{'halves(neut)':>16}{'worst rip':>11}"
    print(hdr)
    for lab, thr in [("+50%", 0.50), ("+70%", 0.70), ("+90%", 0.90), ("+120%", 1.20)]:
        m = A[A.mom >= thr]
        if len(m) < 20:
            print(f"  {lab:<10} n={len(m)} (too few)")
            continue
        short_raw = -m.fwd.mean()
        short_neu = -m.fwdn.mean()
        net = short_neu - FEE_RT
        win = (m.fwdn < 0).mean() * 100       # short wins when coin underperforms
        h = m.sort_values("date")
        h1, h2 = h.iloc[:len(h)//2], h.iloc[len(h)//2:]
        s1, s2 = -h1.fwdn.mean(), -h2.fwdn.mean()
        worst = m.max_up.mean()               # avg worst up-move against the short
        print(f"  {lab:<10}{len(m):>5}{short_raw*100:>+10.2f}%{short_neu*100:>+13.2f}%{net*100:>+9.2f}%{win:>6.0f}%{s1*100:>+7.1f}/{s2*100:>+6.1f}{worst*100:>+10.1f}%")

    print("\nWITH FLOW FILTER — only short blow-offs where funding is POSITIVE (crowded longs paying):")
    print(hdr)
    for lab, thr in [("+50%", 0.50), ("+70%", 0.70), ("+90%", 0.90)]:
        m = A[(A.mom >= thr) & (A.fund > 0)]
        if len(m) < 20:
            print(f"  {lab:<10} n={len(m)} (too few crowded)")
            continue
        short_neu = -m.fwdn.mean()
        net = short_neu - FEE_RT
        win = (m.fwdn < 0).mean() * 100
        h = m.sort_values("date")
        h1, h2 = h.iloc[:len(h)//2], h.iloc[len(h)//2:]
        s1, s2 = -h1.fwdn.mean(), -h2.fwdn.mean()
        worst = m.max_up.mean()
        print(f"  {lab:<10}{len(m):>5}{'':>11}{short_neu*100:>+13.2f}%{net*100:>+9.2f}%{win:>6.0f}%{s1*100:>+7.1f}/{s2*100:>+6.1f}{worst*100:>+10.1f}%")

    print("\nREAD: a tradable short needs net(fee) clearly >0, POSITIVE in BOTH halves, win>50%,")
    print("      and a 'worst rip' small enough to survive (a +40% squeeze blows a 2x short).")

if __name__ == "__main__":
    px, fund = load()
    A = build(px, fund)
    report(A)
