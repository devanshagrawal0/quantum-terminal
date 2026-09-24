"""Features computed ACROSS venues, which is the part nobody else has.

Anyone can compute momentum on a price series. The panel this reads is
different: the same coin, priced on up to 26 venues, every 5 minutes, including
Korean and Indian exchanges quoting in their own currency. The features here are
the ones that only exist because you are looking at all of them at once.

Three ideas do most of the work:

  CONSENSUS      the median mid across dollar-quoted venues. Median, not mean,
                 because one stale or collided venue should not move it.

  DEVIATION      each venue's distance from consensus, in bps. Hyperliquid's own
                 deviation is the tradeable one - it is the gap between where we
                 trade and where the world says the price is.

  DISPERSION     how far apart the venues are. Wide dispersion means the market
                 disagrees, and disagreement is usually the thing that resolves.

FX is derived, never assumed. The Korean and Indian premia are computed against
an exchange rate IMPLIED BY BITCOIN on those same venues, so the number means
"this coin is expensive in Korea relative to how expensive Bitcoin is in Korea",
not "this coin looks odd because I plugged in yesterday's KRW rate".
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

USD_FAMILY = {"USD", "USDT", "USDC", "USDD", "TUSD", "FDUSD", "BUSD", "DAI"}
PERP_VENUES = {"hyperliquid", "binance", "bybit", "gate", "mexc", "bitget",
               "bingx", "kucoin", "htx", "kraken-fut", "dydx", "paradex",
               "backpack", "woo", "phemex"}
LOCAL_QUOTES = {"KRW": ("upbit-kr", "bithumb-kr"), "INR": ("coindcx-in", "wazirx-in")}
REFERENCE_COIN = "BTC"          # what the implied FX rate is derived from


def load_panel(db: Path, since_ms: Optional[int] = None) -> pd.DataFrame:
    """The raw price panel with venue and coin names joined back on."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = ("SELECT p.ts_ms, v.name AS venue, c.name AS coin, p.bid, p.ask, p.mid, "
         "p.vol, p.suspect, pa.quote "
         "FROM prices p "
         "JOIN venues v ON v.id = p.venue_id "
         "JOIN coins  c ON c.id = p.coin_id "
         "LEFT JOIN pairs pa ON pa.venue_id = p.venue_id AND pa.coin_id = p.coin_id")
    if since_ms:
        q += f" WHERE p.ts_ms >= {int(since_ms)}"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


def implied_fx(snap: pd.DataFrame, quote: str, venues) -> Optional[float]:
    """Local currency per dollar, implied by Bitcoin on those same venues.

    Deriving it instead of hardcoding a rate is the difference between measuring
    a premium and measuring your own stale FX assumption.
    """
    usd = snap[(snap.coin == REFERENCE_COIN) & snap.quote.isin(USD_FAMILY)]["mid"]
    loc = snap[(snap.coin == REFERENCE_COIN) & (snap.quote == quote)
               & snap.venue.isin(venues)]["mid"]
    if usd.empty or loc.empty:
        return None
    return float(loc.median() / usd.median())


def stale_scores(panel: pd.DataFrame, lookback: int = 8,
                 moved_bps: float = 5.0) -> pd.Series:
    """How often each venue's quote sat still while the market moved.

    This is the failure that made "dispersion" meaningless: HTX quoted VIRTUAL
    at 0.6602 while seventeen venues sat at 0.718, and Backpack quoted STRK 800
    bps away. Neither was disagreeing - the coin barely trades there and the
    quote had not updated. A snapshot cannot tell a stale quote from a real
    dislocation. Time can: a venue whose price is unchanged across intervals
    where the consensus clearly moved is asleep.

    Returns a Series indexed by (venue, coin), 0 = always moves, 1 = never does.
    """
    usd = panel[panel.quote.isin(USD_FAMILY) & panel.mid.notna()]
    if usd.ts_ms.nunique() < 3:
        return pd.Series(dtype=float)
    recent = sorted(usd.ts_ms.unique())[-lookback:]
    usd = usd[usd.ts_ms.isin(recent)]

    wide = usd.pivot_table(index="ts_ms", columns=["coin", "venue"], values="mid")
    consensus = wide.T.groupby(level=0).median().T          # per coin, per ts

    unchanged = wide.diff().abs().le(1e-12)
    ref = consensus.pct_change().abs() * 1e4
    market_moved = ref.gt(moved_bps)
    # align the per-coin "did the market move" flag onto every venue column
    moved_wide = pd.DataFrame(
        {col: market_moved[col[0]] for col in wide.columns}, index=wide.index)

    asleep = (unchanged & moved_wide).sum()
    chances = moved_wide.sum()
    score = (asleep / chances.replace(0, np.nan))
    score.index = pd.MultiIndex.from_tuples(
        [(v, c) for c, v in score.index], names=["venue", "coin"])
    return score.dropna()


def snapshot_features(snap: pd.DataFrame,
                      stale: Optional[pd.Series] = None,
                      stale_cut: float = 0.6) -> pd.DataFrame:
    """One timestamp of the panel -> one row per coin.

    Rows flagged `suspect` are excluded from every consensus: they are the
    ticker collisions, and one of them would drag a mean badly and can still
    reach a median when a coin trades on few venues.
    """
    snap = snap[(snap["suspect"].isna()) | (snap["suspect"] == 0)]
    usd = snap[snap.quote.isin(USD_FAMILY) & snap.mid.notna()]
    if usd.empty:
        return pd.DataFrame()

    n_dropped = 0
    if stale is not None and len(stale):
        keys = list(zip(usd["venue"], usd["coin"]))
        keep = np.array([stale.get(k, 0.0) < stale_cut for k in keys])
        n_dropped = int((~keep).sum())
        usd = usd[keep]

    fx = {q: implied_fx(snap, q, v) for q, v in LOCAL_QUOTES.items()}

    rows = []
    for coin, g in usd.groupby("coin"):
        if len(g) < 3:                       # a consensus of two is not one
            continue
        consensus = float(g["mid"].median())
        if consensus <= 0:
            continue
        dev = (g["mid"] / consensus - 1.0) * 1e4          # bps per venue
        spread = ((g["ask"] - g["bid"]) / g["mid"] * 1e4).replace(
            [np.inf, -np.inf], np.nan)
        vols = g["vol"].fillna(0.0)
        share = vols / vols.sum() if vols.sum() > 0 else vols

        perp = g[g.venue.isin(PERP_VENUES)]
        spot = g[~g.venue.isin(PERP_VENUES)]
        hl = g[g.venue == "hyperliquid"]["mid"]

        row: Dict[str, object] = {
            "coin": coin,
            "n_venues": len(g),
            "consensus": consensus,
            # how much the venues disagree - the headline cross-venue number
            # Robust dispersion: median absolute deviation, scaled to be
            # comparable with a standard deviation. A plain std is dominated by
            # whichever venue is most asleep, which is the opposite of what this
            # feature is supposed to measure.
            "dispersion_bps": float(1.4826 * (dev - dev.median()).abs().median()),
            "dispersion_raw_bps": float(dev.std(ddof=1)) if len(dev) > 2 else np.nan,
            "range_p10_p90_bps": float(dev.quantile(0.9) - dev.quantile(0.1)),
            "range_bps": float(dev.max() - dev.min()),
            "n_stale_dropped": n_dropped,
            # where WE sit versus the world. the tradeable deviation
            "hl_dev_bps": float((hl.iloc[0] / consensus - 1) * 1e4) if len(hl) else np.nan,
            "richest_venue": g.loc[g["mid"].idxmax(), "venue"],
            "cheapest_venue": g.loc[g["mid"].idxmin(), "venue"],
            # liquidity, per venue and best-of
            "best_spread_bps": float(spread.min()) if spread.notna().any() else np.nan,
            "median_spread_bps": float(spread.median()) if spread.notna().any() else np.nan,
            "hl_spread_bps": float(
                ((g[g.venue == "hyperliquid"]["ask"] - g[g.venue == "hyperliquid"]["bid"])
                 / g[g.venue == "hyperliquid"]["mid"] * 1e4).iloc[0]) if len(hl) else np.nan,
            # is trading concentrated on one venue or spread across many
            "venue_herfindahl": float((share ** 2).sum()) if vols.sum() > 0 else np.nan,
            "total_vol_usd": float(vols.sum()),
            # perp vs spot: the basis, computed across venues rather than one pair
            "perp_spot_bps": (float((perp["mid"].median() / spot["mid"].median() - 1) * 1e4)
                              if len(perp) >= 2 and len(spot) >= 2 else np.nan),
        }

        # Regional premia, each against its own BTC-implied exchange rate.
        for quote, venues in LOCAL_QUOTES.items():
            rate = fx.get(quote)
            local = snap[(snap.coin == coin) & (snap.quote == quote)
                         & snap.venue.isin(venues)]["mid"]
            if rate and len(local):
                row[f"premium_{quote.lower()}_bps"] = float(
                    (local.median() / rate / consensus - 1) * 1e4)
            else:
                row[f"premium_{quote.lower()}_bps"] = np.nan
        rows.append(row)

    return pd.DataFrame(rows).set_index("coin")


def venue_detail(snap: pd.DataFrame, coin: str) -> pd.DataFrame:
    """Every venue's own view of one coin, for looking at by hand."""
    snap = snap[(snap.coin == coin)]
    usd = snap[snap.quote.isin(USD_FAMILY) & snap.mid.notna()
               & ((snap["suspect"].isna()) | (snap["suspect"] == 0))]
    if usd.empty:
        return pd.DataFrame()
    consensus = usd["mid"].median()
    out = usd[["venue", "quote", "bid", "ask", "mid", "vol", "suspect"]].copy()
    out["dev_bps"] = (out["mid"] / consensus - 1) * 1e4
    out["spread_bps"] = (out["ask"] - out["bid"]) / out["mid"] * 1e4
    tot = out["vol"].fillna(0).sum()
    out["vol_share"] = out["vol"].fillna(0) / tot if tot else np.nan
    return out.sort_values("dev_bps", ascending=False).set_index("venue")


def history_features(panel: pd.DataFrame, coin: str) -> pd.DataFrame:
    """Per-venue time series for one coin: each venue's own price path.

    This is where per-venue momentum and volatility come from once enough
    snapshots exist. With only a few hours recorded most columns are still
    empty, and they are left empty rather than computed off three points.
    """
    g = panel[(panel.coin == coin) & panel.quote.isin(USD_FAMILY)]
    if g.empty:
        return pd.DataFrame()
    wide = g.pivot_table(index="ts_ms", columns="venue", values="mid")
    wide.index = pd.to_datetime(wide.index, unit="ms", utc=True)
    return wide.sort_index()
