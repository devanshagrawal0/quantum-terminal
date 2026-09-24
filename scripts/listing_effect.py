"""Does shorting a new Hyperliquid listing make money? Full universe, incl delisted.

Every coin's candle history starts at its listing, so the listing effect is the
one event type testable on history we already have. Research says listings dump
(89% of 2024 CEX listings, avg -52%). This measures it on OUR venue, our coins,
including the delisted ones so it is not survivor-biased toward listings that
worked.
"""
import sys; sys.path.insert(0, '.')
from pathlib import Path
import numpy as np, pandas as pd
from hl.info import Info, now_ms

DAY = 86_400_000
CACHE = Path('data/carry_cache/listings.parquet')


def fetch():
    info = Info()
    perps = [(a['name'], a.get('isDelisted', False)) for a in info.meta()['universe']]
    rows = []
    for i, (coin, delisted) in enumerate(perps, 1):
        try:
            c = info.candles(coin, '1d', now_ms() - 1400 * DAY, now_ms())
        except Exception:
            continue
        if not c or len(c) < 8:
            continue
        s = pd.Series({int(x['t']): float(x['c']) for x in c}).sort_index()
        s.index = pd.to_datetime(s.index, unit='ms', utc=True)
        p0 = s.iloc[0]
        f = lambda n: float(s.iloc[n] / p0 - 1) if len(s) > n else np.nan
        rows.append(dict(coin=coin, delisted=bool(delisted), listed=str(s.index[0].date()),
                         days=len(s), r1=f(1), r3=f(3), r7=f(7), r14=f(14), r30=f(30),
                         hi7=float(s.iloc[:8].max() / p0 - 1) if len(s) >= 8 else np.nan))
        if i % 40 == 0:
            print(f"  {i}/{len(perps)} ({len(rows)} with data)", flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(CACHE)
    print(f"saved {len(df)} rows to {CACHE}", flush=True)
    return df


if __name__ == '__main__':
    fetch()
