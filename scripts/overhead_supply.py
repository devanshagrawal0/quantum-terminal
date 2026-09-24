"""Test the 'trapped longs / overhead supply' idea.

Mechanism: when a wave of buyers is underwater (bought ABOVE current price), they sell
into rallies back to breakeven -> overhead resistance. When price finally BREAKS THROUGH
that heavy-volume zone, the sellers are cleared and it can accelerate.

Proxy from daily OHLCV: overhead_ratio(t) = fraction of the last 90d of VOLUME that
traded at a price ABOVE today's price. High = heavy trapped supply overhead.

Two hypotheses, tested pooled across coins, both-halves, and — the honesty check —
whether overhead_ratio is just momentum/range-position in disguise (it might be: heavy
overhead = price is low in its range = a laggard, which we already trade).
"""
from __future__ import annotations
import json, sys, time, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "carry_cache"
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC"]
LOOK = 90


def ohlcv(sym):
    f = CACHE / f"ohlcv_{sym}.parquet"
    if f.exists() and time.time() - f.stat().st_mtime < 86400:
        return pd.read_parquet(f)
    out = {}
    start = 1502928000000
    while True:
        url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d&startTime={start}&limit=1000"
        try:
            rows = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
        except Exception:
            break
        if not rows:
            break
        for r in rows:
            out[int(r[0])] = (float(r[4]), float(r[5]))   # close, volume
        if len(rows) < 1000:
            break
        start = rows[-1][0] + 86400000
    df = pd.DataFrame(out, index=["close", "volume"]).T
    df.index = pd.to_datetime(df.index, unit="ms", utc=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(f)
    return df


def overhead_ratio(close, volume):
    """Fraction of trailing-LOOK volume that traded ABOVE the current close."""
    c = close.values; v = volume.values
    out = np.full(len(c), np.nan)
    for t in range(LOOK, len(c)):
        w_c = c[t - LOOK:t]; w_v = v[t - LOOK:t]
        above = w_v[w_c > c[t]].sum()
        tot = w_v.sum()
        if tot > 0:
            out[t] = above / tot
    return pd.Series(out, index=close.index)


def run():
    recs = []
    for sym in COINS:
        d = ohlcv(sym + "USDT")
        if len(d) < 200:
            continue
        c = d["close"]
        oh = overhead_ratio(c, d["volume"])
        rng = (c - c.rolling(30).min()) / (c.rolling(30).max() - c.rolling(30).min())  # range-position
        fwd10 = c.shift(-10) / c - 1.0
        oh_prev = oh.shift(3)   # was it high 3 days ago (for the 'break through' event)
        df = pd.DataFrame({"oh": oh, "rng": rng, "fwd": fwd10, "oh_prev": oh_prev, "coin": sym}).dropna()
        recs.append(df)
    A = pd.concat(recs)
    print(f"pooled {A['coin'].nunique()} coins, {len(A)} obs\n")

    # honesty check: is overhead just inverse range-position (momentum)?
    print(f"corr(overhead_ratio, range-position) = {A['oh'].corr(A['rng']):+.2f}  "
          f"(-1 would mean it's exactly inverse momentum)\n")

    print("HYP A — forward-10d return by OVERHEAD bucket (high = heavy trapped supply above):")
    for lab, a, b in [("light  (0-0.2)", 0, 0.2), ("some  (0.2-0.5)", 0.2, 0.5),
                      ("heavy (0.5-0.8)", 0.5, 0.8), ("buried (0.8-1)", 0.8, 1.01)]:
        m = A[(A.oh >= a) & (A.oh < b)]
        if len(m) < 30:
            continue
        t = m.fwd.mean() / (m.fwd.std() / np.sqrt(len(m)))
        print(f"   {lab:<16} n={len(m):>5}  fwd10 {m.fwd.mean()*100:>+5.2f}%  win {(m.fwd>0).mean()*100:>3.0f}%  t{t:>+5.1f}")

    print("\nHYP B — BREAK-THROUGH-SUPPLY: overhead was heavy (>0.5) 3d ago, now cleared (<0.25):")
    ev = A[(A.oh_prev > 0.5) & (A.oh < 0.25)]
    base = A
    if len(ev) > 20:
        te = ev.fwd.mean() / (ev.fwd.std() / np.sqrt(len(ev)))
        h = ev.sort_index()
        h1, h2 = h.iloc[:len(h) // 2], h.iloc[len(h) // 2:]
        print(f"   break-through  n={len(ev):>5}  fwd10 {ev.fwd.mean()*100:>+5.2f}%  win {(ev.fwd>0).mean()*100:>3.0f}%  t{te:>+5.1f}"
              f"   (halves {h1.fwd.mean()*100:+.1f}% / {h2.fwd.mean()*100:+.1f}%)")
        print(f"   baseline (all) n={len(base):>5}  fwd10 {base.fwd.mean()*100:>+5.2f}%")
        print(f"   edge vs baseline: {(ev.fwd.mean()-base.fwd.mean())*100:+.2f}%")
    else:
        print(f"   too few break-through events (n={len(ev)})")

    print("\nread: for a REAL new edge, HYP B (break-through) must beat baseline by a lot with t>~2,")
    print("      survive both halves, AND overhead must NOT just be inverse momentum (corr near -1 = same thing).")


if __name__ == "__main__":
    run()
