"""Walk every recorded snapshot and write Tier 0 plus the basis feature.

    python scripts/build_features.py            # process new snapshots
    python scripts/build_features.py --rebuild  # start over
    python scripts/build_features.py --show     # look at what is there

Runs forward through time, one snapshot at a time, and for each one uses ONLY
the snapshots before it. That is slower than computing everything at once with a
rolling window, and it is the only way the numbers mean what they say: a feature
stamped 14:05 must not contain anything that happened at 14:05 or later.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl.crossvenue import LOCAL_QUOTES, implied_fx, load_panel  # noqa: E402
from hl.tier0 import (USD_FAMILY, build_symbol_map, consolidated,  # noqa: E402
                      ensure_tables, staleness_causal, universe_at)

ROOT = Path(__file__).resolve().parents[1]


def _f(v):
    """None for anything sqlite cannot store as a number, including NaN and
    numpy scalars, which sqlite writes as opaque blobs rather than refusing."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def process(db: Path, rebuild: bool) -> None:
    ensure_tables(db)
    conn = sqlite3.connect(db)
    if rebuild:
        with conn:
            conn.execute("DELETE FROM cv_features")
            conn.execute("DELETE FROM universe_pit")
        print("cleared previous features")

    done = {r[0] for r in conn.execute("SELECT DISTINCT ts_ms FROM cv_features")}
    panel = load_panel(db)
    stamps = sorted(panel.ts_ms.unique())
    todo = [t for t in stamps if t not in done]
    print(f"{len(stamps)} snapshots recorded, {len(todo)} still to process")
    if not todo:
        conn.close()
        return

    smap, _ = build_symbol_map(panel)
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO symbol_map(venue,coin,first_seen_ms,"
            "last_seen_ms,snapshots,quote) VALUES (?,?,?,?,?,?)",
            [(str(r.venue), str(r.coin), int(r.first_seen_ms), int(r.last_seen_ms),
              int(r.snapshots), (str(r.quote) if pd.notna(r.quote) else None))
             for r in smap.itertuples(index=False)])
    print(f"symbol map: {len(smap)} venue/coin pairs")

    written = 0
    t0 = time.time()
    for i, ts in enumerate(todo, 1):
        # int(), not numpy.int64: sqlite stores an unadapted numpy integer as a
        # BLOB, so ts_ms came back as bytes and every later join on it would
        # have silently matched nothing.
        ts = int(ts)
        # Only the past. This is the causality rule and it is why the loop
        # exists at all instead of one vectorised rolling computation.
        stale = staleness_causal(panel, ts)
        snap = panel[panel.ts_ms == ts]
        snap = snap[(snap["suspect"].isna()) | (snap["suspect"] == 0)]
        fx = {q: implied_fx(snap, q, v) for q, v in LOCAL_QUOTES.items()}

        rows = []
        for coin, g in snap.groupby("coin"):
            usd = g[g.quote.isin(USD_FAMILY)]
            if len(usd) < 3:
                continue
            f = consolidated(g, stale)
            if not f:
                continue
            for quote, venues in LOCAL_QUOTES.items():
                rate = fx.get(quote)
                loc = g[(g.quote == quote) & g.venue.isin(venues)]["mid"]
                key = f"premium_{quote.lower()}_bps"
                f[key] = (float((loc.median() / rate / f["cp"] - 1) * 1e4)
                          if rate and len(loc) and f["cp"] else np.nan)
            rows.append((ts, str(coin), float(f["cp"]), int(f["n_venues"]),
                         int(f["n_stale"]),
                         _f(f["hl_dev_bps"]), _f(f["disp_iqr_bps"]),
                         _f(f["cp_perp"]), _f(f["cp_spot"]), _f(f["sp_basis_bps"]),
                         _f(f["best_spread_bps"]), _f(f["hl_spread_bps"]),
                         _f(f["hhi"]), _f(f["hl_vol_share"]),
                         _f(f["credible_vol_usd"]), _f(f["premium_krw_bps"]),
                         _f(f["premium_inr_bps"])))
        uni = universe_at(panel, ts)
        with conn:
            conn.executemany("INSERT OR REPLACE INTO cv_features VALUES "
                             "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            if not uni.empty:
                conn.executemany(
                    "INSERT OR REPLACE INTO universe_pit VALUES (?,?,?,?,?)",
                    [(int(r.ts_ms), str(r.coin), int(r.on_hl), int(r.n_venues),
                      _f(r.hl_vol_usd)) for r in uni.itertuples(index=False)])
        written += len(rows)
        if i % 5 == 0 or i == len(todo):
            print(f"  [{i}/{len(todo)}] {written:,} feature rows, {time.time()-t0:.0f}s")
    conn.close()


def show(db: Path) -> None:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    n, ts_n = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT ts_ms) FROM cv_features").fetchone()
    if not n:
        print("no features yet")
        return
    print(f"\n{n:,} feature rows over {ts_n} snapshots")
    last = conn.execute("SELECT MAX(ts_ms) FROM cv_features").fetchone()[0]
    df = pd.read_sql_query(
        "SELECT * FROM cv_features WHERE ts_ms = ?", conn, params=(last,))
    conn.close()

    liq = df[df.credible_vol_usd > 2e7].copy()
    print(f"latest snapshot {time.strftime('%H:%M:%S', time.localtime(last/1000))}, "
          f"{len(df)} coins, {len(liq)} with >$20m credible volume")

    print("\nFEATURE #1 - CONSOLIDATED PERP vs CONSOLIDATED SPOT (basis, bps)")
    print("positive = perps rich vs spot = longs paying up\n")
    b = liq.dropna(subset=["sp_basis_bps"]).sort_values("sp_basis_bps")
    cols = ["coin", "cp", "sp_basis_bps", "hl_dev_bps", "disp_iqr_bps",
            "n_venues", "n_stale", "credible_vol_usd"]
    print("  most negative (spot rich / perps cheap):")
    print(b[cols].head(6).to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    print("\n  most positive (perps rich / longs crowded):")
    print(b[cols].tail(6).to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    print(f"\n  basis across {len(b)} liquid coins: median "
          f"{b.sp_basis_bps.median():+.1f} bps, "
          f"10th {b.sp_basis_bps.quantile(0.1):+.1f}, "
          f"90th {b.sp_basis_bps.quantile(0.9):+.1f}")

    print("\nTIER 0 HEALTH")
    print(f"  stale quotes excluded, this snapshot: {int(df.n_stale.sum())}")
    print(f"  coins with a spot side at all: {int(df.cp_spot.notna().sum())} of {len(df)}")
    print(f"  coins priced on 10+ venues: {int((df.n_venues >= 10).sum())}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/venues.db")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()
    db = ROOT / args.db if not Path(args.db).is_absolute() else Path(args.db)
    if args.show:
        show(db)
        return
    process(db, args.rebuild)
    show(db)


if __name__ == "__main__":
    main()
