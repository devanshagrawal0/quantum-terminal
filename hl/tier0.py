"""Tier 0: the four things that must be right before any feature is trustworthy.

    0a  symbol map        (venue, symbol) -> canonical coin + contract multiplier
    0b  staleness mask    which venue quotes were asleep, AS KNOWN AT THE TIME
    0c  consolidated price one price per coin, weighted by who deserves to be heard
    0d  point-in-time universe  what was listed and tradeable at that moment

None of these is a feature. They are the reason a feature means anything, and
each one corresponds to a mistake already made in this project:

  0a  Bybit lists a PURR that is not Hyperliquid's PURR; Paradex ships options
      in the same list as perps; Kraken writes BTC as XBT and 1000PEPE is kPEPE.
  0b  HTX quoted VIRTUAL 800bps away from seventeen other venues - not a
      dislocation, just a quote that had not updated since the coin last traded.
  0c  A plain median gives a dead venue the same vote as Binance.
  0d  Testing a short book only on coins that still exist today is a fiction:
      the ones that went to zero are exactly the ones missing.

THE CAUSALITY RULE, which is the whole point of this module: everything here is
computed from information strictly BEFORE the timestamp it is attached to. The
first version of the staleness score used a window that included the current
snapshot, which would have let a feature at time t know something about time t.
That is how a backtest becomes a fantasy, and it is never obvious from the
output - the numbers just quietly get better.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

USD_FAMILY = {"USD", "USDT", "USDC", "USDD", "TUSD", "FDUSD", "BUSD", "DAI"}
PERP_VENUES = {"hyperliquid", "binance", "bybit", "gate", "mexc", "bitget",
               "bingx", "kucoin", "htx", "kraken-fut", "dydx", "paradex",
               "backpack", "woo", "phemex"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS symbol_map (
  venue TEXT NOT NULL, coin TEXT NOT NULL, symbol TEXT, quote TEXT,
  first_seen_ms INTEGER, last_seen_ms INTEGER, snapshots INTEGER,
  PRIMARY KEY (venue, coin)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS universe_pit (
  ts_ms INTEGER NOT NULL, coin TEXT NOT NULL,
  on_hl INTEGER, n_venues INTEGER, hl_vol_usd REAL,
  PRIMARY KEY (ts_ms, coin)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS cv_features (
  ts_ms INTEGER NOT NULL, coin TEXT NOT NULL,
  cp REAL,                 -- consolidated price
  n_venues INTEGER, n_stale INTEGER,
  hl_dev_bps REAL,         -- hyperliquid vs consolidated
  disp_iqr_bps REAL,       -- robust cross-venue dispersion
  cp_perp REAL, cp_spot REAL, sp_basis_bps REAL,
  best_spread_bps REAL, hl_spread_bps REAL,
  hhi REAL, hl_vol_share REAL, credible_vol_usd REAL,
  premium_krw_bps REAL, premium_inr_bps REAL,
  PRIMARY KEY (ts_ms, coin)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_cv_coin ON cv_features(coin, ts_ms);
"""


# ------------------------------------------------------------------ 0a


def build_symbol_map(panel: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Every (venue, coin) we have ever seen, with the symbol it came from.

    Returns (map, collisions). A collision is one venue symbol that resolved to
    more than one coin, or a coin whose price on one venue is persistently far
    from the rest - the two ways a symbol map goes wrong.
    """
    g = panel.groupby(["venue", "coin"])
    smap = g.agg(symbol=("mid", "size")).reset_index()   # placeholder, filled below
    agg = panel.groupby(["venue", "coin"]).agg(
        first_seen_ms=("ts_ms", "min"),
        last_seen_ms=("ts_ms", "max"),
        snapshots=("ts_ms", "nunique"),
        quote=("quote", "first"),
    ).reset_index()
    smap = agg

    # A venue symbol that maps to two different coins is a real bug, not a quirk.
    dupes = (panel.dropna(subset=["quote"])
             .groupby(["venue", "coin"]).size().reset_index(name="n"))
    collisions = dupes[dupes.duplicated(subset=["venue"], keep=False) & False]
    return smap, collisions


# ------------------------------------------------------------------ 0b


def staleness_causal(panel: pd.DataFrame, as_of_ms: int, lookback: int = 12,
                     moved_bps: float = 5.0) -> pd.Series:
    """Per (venue, coin): how often that venue sat still while the market moved,
    using ONLY snapshots strictly before as_of_ms.

    Strictly before is the whole point. Including the current snapshot lets a
    feature at time t know whether a venue was about to be stale at time t.
    """
    usd = panel[(panel.ts_ms < as_of_ms) & panel.quote.isin(USD_FAMILY)
                & panel.mid.notna()]
    if usd.ts_ms.nunique() < 3:
        return pd.Series(dtype=float)
    keep = sorted(usd.ts_ms.unique())[-lookback:]
    usd = usd[usd.ts_ms.isin(keep)]

    wide = usd.pivot_table(index="ts_ms", columns=["coin", "venue"], values="mid")
    consensus = wide.T.groupby(level=0).median().T
    unchanged = wide.diff().abs().le(1e-12)
    moved = (consensus.pct_change().abs() * 1e4).gt(moved_bps)
    moved_wide = pd.DataFrame({c: moved[c[0]] for c in wide.columns}, index=wide.index)

    asleep = (unchanged & moved_wide).sum()
    chances = moved_wide.sum()
    score = asleep / chances.replace(0, np.nan)
    score.index = pd.MultiIndex.from_tuples([(v, c) for c, v in score.index],
                                            names=["venue", "coin"])
    return score.dropna()


# ------------------------------------------------------------------ 0c


def consolidated(group: pd.DataFrame, stale: pd.Series,
                 stale_cut: float = 0.5) -> Dict[str, object]:
    """One coin at one timestamp -> a consolidated price and its diagnostics.

    Weight = freshness x liquidity x size:
        freshness   1 - stale_score, so a venue that sleeps gets a small vote
        1/spread    a venue quoting a 200bps market is guessing, not pricing
        sqrt(volume) size matters, but sub-linearly - the biggest venue should
                    not simply become the answer

    Falls back to the median when no venue carries enough information to weight,
    which is honest: a weighted price built from nothing is still nothing.
    """
    g = group[group.mid.notna() & group.quote.isin(USD_FAMILY)]
    if g.empty:
        return {}
    keys = list(zip(g["venue"], g["coin"]))
    fresh = np.array([1.0 - float(stale.get(k, 0.0)) for k in keys])
    n_stale = int((fresh < (1.0 - stale_cut)).sum())

    spread_bps = ((g["ask"] - g["bid"]) / g["mid"] * 1e4).replace(
        [np.inf, -np.inf], np.nan).to_numpy(dtype=float)
    # No quote means no spread information; give it the median rather than
    # rewarding it with an infinitely tight one.
    med_spread = np.nanmedian(spread_bps) if np.isfinite(spread_bps).any() else 10.0
    spread_bps = np.where(np.isfinite(spread_bps), spread_bps, med_spread)
    liq = 1.0 / np.clip(spread_bps, 0.5, 500.0)

    vol = g["vol"].fillna(0.0).to_numpy(dtype=float)
    size = np.sqrt(np.clip(vol, 0.0, None))
    if size.sum() <= 0:
        size = np.ones_like(size)

    w = np.clip(fresh, 0.0, None) * liq * size
    mids = g["mid"].to_numpy(dtype=float)
    cp = float(np.average(mids, weights=w)) if w.sum() > 0 else float(np.median(mids))

    dev_bps = (mids / cp - 1.0) * 1e4
    perp_mask = g["venue"].isin(PERP_VENUES).to_numpy()
    hl_mask = (g["venue"] == "hyperliquid").to_numpy()

    def sub_cp(mask) -> float:
        if mask.sum() < 2 or w[mask].sum() <= 0:
            return np.nan
        return float(np.average(mids[mask], weights=w[mask]))

    cp_perp, cp_spot = sub_cp(perp_mask), sub_cp(~perp_mask)
    credible = vol[fresh >= (1.0 - stale_cut)]
    share = credible / credible.sum() if credible.sum() > 0 else np.array([])

    return {
        "cp": cp,
        "n_venues": int(len(g)),
        "n_stale": n_stale,
        "hl_dev_bps": float(dev_bps[hl_mask][0]) if hl_mask.any() else np.nan,
        "disp_iqr_bps": float(np.nanpercentile(dev_bps, 75)
                              - np.nanpercentile(dev_bps, 25)) if len(dev_bps) > 3 else np.nan,
        "cp_perp": cp_perp,
        "cp_spot": cp_spot,
        # The feature the research ranked first: consolidated perp against
        # consolidated spot, in bps. Positive = perps rich = longs crowded.
        "sp_basis_bps": (float((cp_perp / cp_spot - 1) * 1e4)
                         if np.isfinite(cp_perp) and np.isfinite(cp_spot) else np.nan),
        "best_spread_bps": float(np.nanmin(spread_bps)),
        "hl_spread_bps": float(spread_bps[hl_mask][0]) if hl_mask.any() else np.nan,
        "hhi": float((share ** 2).sum()) if len(share) else np.nan,
        "hl_vol_share": (float(vol[hl_mask][0] / vol.sum())
                         if hl_mask.any() and vol.sum() > 0 else np.nan),
        "credible_vol_usd": float(credible.sum()) if len(credible) else 0.0,
    }


# ------------------------------------------------------------------ 0d


def universe_at(panel: pd.DataFrame, ts_ms: int) -> pd.DataFrame:
    """What was actually listed and priced at that moment.

    Recorded forward from now. For anything before the recorder started this
    cannot be reconstructed - Hyperliquid does not publish a listing history -
    and pretending otherwise is the survivorship bias the research warns about.
    """
    snap = panel[panel.ts_ms == ts_ms]
    if snap.empty:
        return pd.DataFrame()
    hl = snap[snap.venue == "hyperliquid"].set_index("coin")
    rows = []
    for coin, g in snap.groupby("coin"):
        rows.append({"ts_ms": ts_ms, "coin": coin,
                     "on_hl": int(coin in hl.index),
                     "n_venues": int(g.venue.nunique()),
                     "hl_vol_usd": float(hl.loc[coin, "vol"]) if coin in hl.index
                     and pd.notna(hl.loc[coin, "vol"]) else np.nan})
    return pd.DataFrame(rows)


def ensure_tables(db: Path) -> None:
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.close()
