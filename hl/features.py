"""Every derived variable, computed from the raw payloads.

Nothing here calls the network - pass in what info.py returned. That split
keeps the maths testable offline and makes it obvious which numbers are the
exchange's and which are ours.

Horizon note: this bot trades 1-7 day holds, so the defaults are daily candles
and funding carry is summed over the whole hold, not quoted per hour.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from .constants import FUNDING_INTERVAL_HOURS, HOURS_PER_YEAR

# ---------------------------------------------------------------- candles ---


def candles_to_frame(candles: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    """Raw candleSnapshot rows -> tidy DataFrame indexed by open time (UTC)."""
    if not candles:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume",
                                     "trades", "close_time"])
    df = pd.DataFrame(candles)
    out = pd.DataFrame({
        "open": df["o"].astype(float),
        "high": df["h"].astype(float),
        "low": df["l"].astype(float),
        "close": df["c"].astype(float),
        "volume": df["v"].astype(float),
        "trades": df["n"].astype(int),
        "close_time": pd.to_datetime(df["T"], unit="ms", utc=True),
    })
    out.index = pd.to_datetime(df["t"], unit="ms", utc=True)
    out.index.name = "open_time"
    return out.sort_index()


def _safe(x: Any) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else f


def pct_return(df: pd.DataFrame, bars: int) -> Optional[float]:
    if len(df) <= bars:
        return None
    c = df["close"]
    return _safe(c.iloc[-1] / c.iloc[-1 - bars] - 1.0)


def realized_vol(df: pd.DataFrame, bars: int, bars_per_year: float = 365.0) -> Optional[float]:
    """Annualised close-to-close volatility over the last `bars` bars."""
    if len(df) < bars + 1:
        return None
    r = np.log(df["close"]).diff().dropna().iloc[-bars:]
    if len(r) < 2:
        return None
    return _safe(r.std(ddof=1) * math.sqrt(bars_per_year))


def parkinson_vol(df: pd.DataFrame, bars: int, bars_per_year: float = 365.0) -> Optional[float]:
    """High-low range volatility - about 5x more efficient than close-to-close."""
    if len(df) < bars:
        return None
    w = df.iloc[-bars:]
    hl = np.log(w["high"] / w["low"]) ** 2
    var = hl.mean() / (4.0 * math.log(2.0))
    return _safe(math.sqrt(var) * math.sqrt(bars_per_year))


def atr(df: pd.DataFrame, bars: int = 14) -> Optional[float]:
    if len(df) < bars + 1:
        return None
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return _safe(tr.iloc[-bars:].mean())


def rsi(df: pd.DataFrame, bars: int = 14) -> Optional[float]:
    if len(df) < bars + 1:
        return None
    d = df["close"].diff().dropna()
    gain = d.clip(lower=0).ewm(alpha=1 / bars, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1 / bars, adjust=False).mean()
    last_loss = loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    rs = gain.iloc[-1] / last_loss
    return _safe(100 - 100 / (1 + rs))


def zscore(df: pd.DataFrame, bars: int = 30) -> Optional[float]:
    if len(df) < bars:
        return None
    w = df["close"].iloc[-bars:]
    sd = w.std(ddof=1)
    if not sd:
        return None
    return _safe((w.iloc[-1] - w.mean()) / sd)


def dist_from_extreme(df: pd.DataFrame, bars: int, high: bool = True) -> Optional[float]:
    if len(df) < bars:
        return None
    w = df.iloc[-bars:]
    last = df["close"].iloc[-1]
    ref = w["high"].max() if high else w["low"].min()
    if not ref:
        return None
    return _safe(last / ref - 1.0)


def max_drawdown(df: pd.DataFrame, bars: int) -> Optional[float]:
    if len(df) < 2:
        return None
    c = df["close"].iloc[-bars:]
    peak = c.cummax()
    return _safe((c / peak - 1.0).min())


def ma_distance(df: pd.DataFrame, bars: int, exponential: bool = False) -> Optional[float]:
    if len(df) < bars:
        return None
    ma = (df["close"].ewm(span=bars, adjust=False).mean() if exponential
          else df["close"].rolling(bars).mean())
    v = ma.iloc[-1]
    if not v:
        return None
    return _safe(df["close"].iloc[-1] / v - 1.0)


def volume_zscore(df: pd.DataFrame, bars: int = 30) -> Optional[float]:
    if len(df) < bars:
        return None
    w = df["volume"].iloc[-bars:]
    sd = w.std(ddof=1)
    if not sd:
        return None
    return _safe((w.iloc[-1] - w.mean()) / sd)


def daily_features(df: pd.DataFrame) -> Dict[str, Any]:
    """The full daily-candle variable set for a 1-7 day horizon."""
    if df.empty:
        return {}
    return {
        "bars": len(df),
        "last_close": _safe(df["close"].iloc[-1]),
        "ret_1d": pct_return(df, 1),
        "ret_2d": pct_return(df, 2),
        "ret_3d": pct_return(df, 3),
        "ret_7d": pct_return(df, 7),
        "ret_14d": pct_return(df, 14),
        "ret_30d": pct_return(df, 30),
        "vol_7d_ann": realized_vol(df, 7),
        "vol_30d_ann": realized_vol(df, 30),
        "parkinson_7d_ann": parkinson_vol(df, 7),
        "parkinson_30d_ann": parkinson_vol(df, 30),
        "vol_ratio_7_30": (
            realized_vol(df, 7) / realized_vol(df, 30)
            if realized_vol(df, 7) and realized_vol(df, 30) else None),
        "atr_14": atr(df, 14),
        "atr_14_pct": (atr(df, 14) / df["close"].iloc[-1]
                       if atr(df, 14) and df["close"].iloc[-1] else None),
        "rsi_14": rsi(df, 14),
        "z_30d": zscore(df, 30),
        "dist_high_30d": dist_from_extreme(df, 30, True),
        "dist_low_30d": dist_from_extreme(df, 30, False),
        "dist_sma_7": ma_distance(df, 7),
        "dist_sma_30": ma_distance(df, 30),
        "dist_ema_50": ma_distance(df, 50, exponential=True),
        "max_dd_30d": max_drawdown(df, 30),
        "up_day_ratio_14d": _safe((df["close"].diff().iloc[-14:] > 0).mean()),
        "volume_z_30d": volume_zscore(df, 30),
        "avg_trades_per_day_7d": _safe(df["trades"].iloc[-7:].mean()),
    }


# ---------------------------------------------------------------- funding ---


def funding_stats(history: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Realised funding. Rates from the API are per HOUR (funding is charged
    hourly on Hyperliquid), so annualising means x 24 x 365."""
    if not history:
        return {}
    rates = np.array([float(h["fundingRate"]) for h in history])
    prem = np.array([float(h.get("premium", "nan")) for h in history])

    def window(n: int) -> Dict[str, Any]:
        w = rates[-n:] if len(rates) >= 1 else rates
        if len(w) == 0:
            return {}
        return {
            f"funding_sum_{n}h": _safe(w.sum()),
            f"funding_mean_{n}h": _safe(w.mean()),
            f"funding_apr_{n}h": _safe(w.mean() * HOURS_PER_YEAR),
            f"funding_pos_frac_{n}h": _safe((w > 0).mean()),
        }

    out: Dict[str, Any] = {
        "funding_samples": len(rates),
        "funding_last": _safe(rates[-1]),
        "funding_last_apr": _safe(rates[-1] * HOURS_PER_YEAR),
        "premium_mean": _safe(np.nanmean(prem)) if len(prem) else None,
        "funding_std": _safe(rates.std(ddof=1)) if len(rates) > 1 else None,
    }
    for n in (24, 72, 168):          # 1d, 3d, 7d of hourly funding
        if len(rates) >= n:
            out.update(window(n))
    return out


def carry_cost(hourly_rate: float, days: float, is_long: bool = True) -> float:
    """Funding paid (negative) or received (positive) as a fraction of notional
    if the current hourly rate held for `days`. Longs pay a positive rate."""
    hours = days * 24.0 / FUNDING_INTERVAL_HOURS
    signed = -hourly_rate if is_long else hourly_rate
    return signed * hours


def predicted_funding_map(predicted, default_cex_interval_hours: float = 8.0):
    """predictedFundings -> {coin: {venue: hourly_rate, ...}} plus the HL-vs-CEX
    spread, which is the tradable cross-venue funding edge.

    Two real quirks of this payload, both seen live:
      * a venue can be present with a null body (that CEX does not list the
        coin) - those are skipped, not treated as zero,
      * fundingIntervalHours is sometimes missing on the CEX venues; Hyperliquid
        charges hourly, the CEXes quote 8h by default, so that is the fallback.
    """
    out = {}
    for entry in predicted:
        if not (isinstance(entry, list) and len(entry) == 2):
            continue
        coin, venues = entry
        row = {}
        for venue in venues or []:
            if not (isinstance(venue, list) and len(venue) == 2):
                continue
            name, v = venue
            if not isinstance(v, dict):
                continue                                   # venue does not list it
            rate = _safe(v.get("fundingRate"))
            if rate is None:
                continue
            hours = _safe(v.get("fundingIntervalHours"))
            if not hours:
                hours = 1.0 if name == "HlPerp" else default_cex_interval_hours
            row[name] = rate / hours                       # normalise to per hour
            row[f"{name}_next_ms"] = v.get("nextFundingTime")
        hl = row.get("HlPerp")
        cex = [row[k] for k in ("BinPerp", "BybitPerp") if k in row]
        if hl is not None and cex:
            row["cex_mean"] = float(np.mean(cex))
            row["hl_minus_cex"] = hl - row["cex_mean"]
            row["hl_minus_cex_apr"] = (hl - row["cex_mean"]) * HOURS_PER_YEAR
        out[coin] = row
    return out


# ------------------------------------------------------------------- tape ---


def trade_flow(trades):
    """Aggressor flow from recentTrades. side "B" means the buyer was the taker.

    recentTrades comes back newest-first, so the tape window is measured from
    min/max time rather than first/last row.
    """
    if not trades:
        return {}
    buy = sell = 0.0
    notional = 0.0
    base = 0.0
    sizes = []
    times = []
    for t in trades:
        px, sz = float(t["px"]), float(t["sz"])
        n = px * sz
        notional += n
        base += sz
        sizes.append(n)
        times.append(int(t["time"]))
        if t.get("side") == "B":
            buy += n
        else:
            sell += n
    span_s = (max(times) - min(times)) / 1000.0
    return {
        "trades_n": len(trades),
        "trade_vwap": _safe(notional / base) if base else None,
        "trade_notional_usd": _safe(notional),
        "taker_buy_usd": _safe(buy),
        "taker_sell_usd": _safe(sell),
        "taker_imbalance": _safe((buy - sell) / (buy + sell)) if buy + sell else None,
        "avg_trade_usd": _safe(notional / len(trades)),
        "max_trade_usd": _safe(max(sizes)) if sizes else None,
        "tape_newest_ms": max(times),
        "tape_span_seconds": span_s,
        "trades_per_second": _safe(len(trades) / span_s) if span_s > 0 else None,
    }


# ------------------------------------------------------------- asset ctx  ---


def asset_ctx_features(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Everything the exchange publishes per perp, plus the obvious ratios."""
    mark = _safe(ctx.get("markPx"))
    oracle = _safe(ctx.get("oraclePx"))
    mid = _safe(ctx.get("midPx"))
    prev = _safe(ctx.get("prevDayPx"))
    oi = _safe(ctx.get("openInterest"))
    day_ntl = _safe(ctx.get("dayNtlVlm"))
    funding = _safe(ctx.get("funding"))
    impact = ctx.get("impactPxs") or [None, None]

    oi_usd = oi * mark if (oi is not None and mark) else None
    out: Dict[str, Any] = {
        "mark_px": mark,
        "oracle_px": oracle,
        "mid_px": mid,
        "prev_day_px": prev,
        "day_change_pct": (mark / prev - 1.0) if (mark and prev) else None,
        "open_interest_base": oi,
        "open_interest_usd": oi_usd,
        "day_notional_volume": day_ntl,
        "day_base_volume": _safe(ctx.get("dayBaseVlm")),
        "turnover_vol_over_oi": (day_ntl / oi_usd) if (day_ntl and oi_usd) else None,
        "funding_hourly": funding,
        "funding_apr": funding * HOURS_PER_YEAR if funding is not None else None,
        "premium": _safe(ctx.get("premium")),
        "impact_bid": _safe(impact[0]) if len(impact) > 0 else None,
        "impact_ask": _safe(impact[1]) if len(impact) > 1 else None,
    }
    if mark and oracle:
        out["mark_oracle_bps"] = (mark - oracle) / oracle * 1e4
    if out["impact_bid"] and out["impact_ask"]:
        ip_mid = (out["impact_bid"] + out["impact_ask"]) / 2
        out["impact_spread_bps"] = (out["impact_ask"] - out["impact_bid"]) / ip_mid * 1e4
    return out


def flatten(prefix: str, d: Dict[str, Any]) -> Dict[str, Any]:
    return {f"{prefix}_{k}": v for k, v in d.items()}


def merge(*dicts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for d in dicts:
        if d:
            out.update(d)
    return out
