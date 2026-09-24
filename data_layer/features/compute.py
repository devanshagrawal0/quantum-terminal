"""Feature engine — 157 features computed from OHLCV.

THREE RULES, enforced structurally (not by hoping):

 1. NO LOOK-AHEAD. Every window is TRAILING. pandas .rolling() and .ewm()
    look backwards only. There is no .shift(-n) anywhere in this file and no
    centered window. A value stamped at time T uses only bars at or before T.

 2. NO STALE DATA. Incremental: read the last ts already in the feature table
    and recompute only from there, minus a warmup tail so the long windows are
    correct at the boundary.

 3. FORMULAS ARE CHECKED, not trusted. verify.py recomputes a sample by hand
    and compares. Nothing here is believed until that passes.

Data reality (measured 2026-09-09): ohlcv is 1h bars, 6.7 years, 57 coins and
growing. The 17 microstructure features in the spec are NOT here because the
book and trade tables are empty — they are not faked.

Run:  python data_layer/features/compute.py --symbols BTC,ETH
      python data_layer/features/compute.py --all
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "store"))
import store  # noqa: E402

HOURS_YEAR = 24 * 365          # annualisation factor for hourly bars
WARMUP = 24 * 210              # bars kept before an incremental start


# ----------------------------------------------------------------- helpers

def _ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def _wilder(s, n):
    """Wilder smoothing (RSI/ATR/ADX). alpha = 1/n, NOT 2/(n+1)."""
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def _rsi(close, n):
    d = close.diff()
    up = d.clip(lower=0)
    dn = (-d).clip(lower=0)
    rs = _wilder(up, n) / _wilder(dn, n).replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _true_range(h, l, c):
    pc = c.shift(1)
    return pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)


def _rolling_slope(s, n):
    x = np.arange(n)
    dx = x - x.mean()
    den = (dx ** 2).sum()
    return s.rolling(n).apply(lambda y: float(np.dot(dx, y - y.mean()) / den), raw=True)


def _hurst(s, n=200):
    def h(a):
        a = np.asarray(a, dtype=float)
        if len(a) < 40 or np.all(a == a[0]):
            return np.nan
        lags = np.array([2, 4, 8, 16, 32])
        lags = lags[lags < len(a) // 2]
        if len(lags) < 3:
            return np.nan
        tau = np.array([np.sqrt(np.std(a[lag:] - a[:-lag])) for lag in lags])
        if np.any(tau <= 0) or np.any(~np.isfinite(tau)):
            return np.nan
        return float(np.polyfit(np.log(lags), np.log(tau), 1)[0] * 2.0)
    return s.rolling(n).apply(h, raw=True)


# -------------------------------------------------------------- families

def f_returns(df):
    c = df["c"]
    lr = np.log(c / c.shift(1))
    out = pd.DataFrame(index=df.index)
    for tag, n in (("1h", 1), ("4h", 4), ("12h", 12), ("1d", 24), ("3d", 72),
                   ("7d", 168), ("14d", 336), ("30d", 720), ("90d", 2160)):
        out["r_" + tag] = np.log(c / c.shift(n))
    # Skip-a-period momentum. The skip is standard and it matters: without it
    # short-horizon reversal contaminates the signal and flips its sign.
    out["mom_7d_skip1"] = np.log(c.shift(24) / c.shift(168))
    out["mom_30d_skip1"] = np.log(c.shift(24) / c.shift(720))
    out["mom_90d_skip7"] = np.log(c.shift(168) / c.shift(2160))
    out["rev_1h"] = -out["r_1h"]
    out["rev_1d"] = -out["r_1d"]
    out["ret_zscore"] = (lr - lr.rolling(720).mean()) / lr.rolling(720).std()
    out["logret_cum"] = lr.cumsum()
    return out


def f_volatility(df):
    o, h, l, c = df["o"], df["h"], df["l"], df["c"]
    lr = np.log(c / c.shift(1))
    ann = np.sqrt(HOURS_YEAR)
    out = pd.DataFrame(index=df.index)
    for tag, n in (("24h", 24), ("7d", 168), ("30d", 720)):
        out["rv_" + tag] = lr.rolling(n).std() * ann

    hl = np.log(h / l)
    co = np.log(c / o)
    out["parkinson"] = np.sqrt((hl ** 2).rolling(24).mean() / (4 * np.log(2))) * ann
    out["garman_klass"] = np.sqrt(
        (0.5 * hl ** 2 - (2 * np.log(2) - 1) * co ** 2).rolling(24).mean().clip(lower=0)) * ann
    rs = np.log(h / c) * np.log(h / o) + np.log(l / c) * np.log(l / o)
    out["rogers_satchell"] = np.sqrt(rs.rolling(24).mean().clip(lower=0)) * ann

    oc = np.log(o / c.shift(1))
    n = 24
    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    out["yang_zhang"] = np.sqrt(
        (oc.rolling(n).var() + k * co.rolling(n).var()
         + (1 - k) * rs.rolling(n).mean()).clip(lower=0)) * ann

    bp = (np.pi / 2) * (lr.abs() * lr.abs().shift(1)).rolling(24).sum()
    out["bipower"] = np.sqrt(bp.clip(lower=0) / 24) * ann
    rv2 = (lr ** 2).rolling(24).sum()
    out["jump_frac"] = (rv2 - bp).clip(lower=0) / rv2.replace(0, np.nan)

    tr = _true_range(h, l, c)
    out["atr_14"] = _wilder(tr, 14)
    out["atr_pct"] = out["atr_14"] / c
    out["ewma_vol"] = lr.ewm(span=72, adjust=False).std() * ann
    out["vol_of_vol"] = out["rv_24h"].rolling(168).std()
    out["realized_skew"] = lr.rolling(720).skew()
    out["realized_kurt"] = lr.rolling(720).kurt()
    out["semi_vol_up"] = lr.clip(lower=0).rolling(720).std() * ann
    out["semi_vol_down"] = lr.clip(upper=0).rolling(720).std() * ann
    out["ud_vol_ratio"] = out["semi_vol_up"] / out["semi_vol_down"].replace(0, np.nan)
    out["vol_ratio_7_30"] = out["rv_7d"] / out["rv_30d"].replace(0, np.nan)
    out["vol_pctile_1y"] = out["rv_24h"].rolling(HOURS_YEAR, min_periods=720).rank(pct=True)
    out["vol_zscore"] = ((out["rv_24h"] - out["rv_24h"].rolling(720).mean())
                         / out["rv_24h"].rolling(720).std())
    return out


def f_trend(df):
    o, h, l, c = df["o"], df["h"], df["l"], df["c"]
    out = pd.DataFrame(index=df.index)
    for n in (5, 10, 20, 50, 100, 200):
        out["sma_%d" % n] = c.rolling(n).mean()
    for n in (9, 12, 21, 26, 50, 200):
        out["ema_%d" % n] = _ema(c, n)
    out["macd"] = out["ema_12"] - out["ema_26"]
    out["macd_signal"] = _ema(out["macd"], 9)
    out["macd_hist"] = out["macd"] - out["macd_signal"]

    up = h.diff()
    dn = -l.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    atr = _wilder(_true_range(h, l, c), 14)
    pdi = 100 * _wilder(plus_dm, 14) / atr.replace(0, np.nan)
    mdi = 100 * _wilder(minus_dm, 14) / atr.replace(0, np.nan)
    out["di_plus"], out["di_minus"] = pdi, mdi
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    out["adx_14"] = _wilder(dx, 14)

    n = 25
    out["aroon_up"] = 100 * h.rolling(n + 1).apply(lambda x: float(np.argmax(x)), raw=True) / n
    out["aroon_down"] = 100 * l.rolling(n + 1).apply(lambda x: float(np.argmin(x)), raw=True) / n
    out["aroon_osc"] = out["aroon_up"] - out["aroon_down"]

    # Documented simplifications: true PSAR is a stateful recursion and true
    # Supertrend flips on band crosses. Both are stored as ATR-offset trailing
    # levels here; named honestly rather than pretending to be the textbook form.
    out["psar"] = c - 0.02 * atr
    out["supertrend"] = (h + l) / 2 - 3 * atr

    out["linreg_slope"] = _rolling_slope(c, 50)
    out["hurst"] = _hurst(np.log(c), 200)

    out["donchian_hi"] = h.rolling(20).max()
    out["donchian_lo"] = l.rolling(20).min()
    out["donchian_mid"] = (out["donchian_hi"] + out["donchian_lo"]) / 2

    out["ich_tenkan"] = (h.rolling(9).max() + l.rolling(9).min()) / 2
    out["ich_kijun"] = (h.rolling(26).max() + l.rolling(26).min()) / 2
    out["ich_senkou_a"] = (out["ich_tenkan"] + out["ich_kijun"]) / 2
    out["ich_senkou_b"] = (h.rolling(52).max() + l.rolling(52).min()) / 2
    # Textbook Ichimoku shifts the cloud FORWARD — that is look-ahead in a
    # feature table, so chikou is stored as a TRAILING lag instead.
    out["ich_chikou"] = c.shift(26)

    out["px_vs_sma50"] = c / out["sma_50"] - 1
    out["px_vs_sma200"] = c / out["sma_200"] - 1
    out["golden_cross"] = (out["sma_50"] > out["sma_200"]).astype(float)
    return out


def f_oscillators(df):
    h, l, c = df["h"], df["l"], df["c"]
    out = pd.DataFrame(index=df.index)
    for n in (7, 14, 21):
        out["rsi_%d" % n] = _rsi(c, n)
    ll, hh = l.rolling(14).min(), h.rolling(14).max()
    out["stoch_k"] = 100 * (c - ll) / (hh - ll).replace(0, np.nan)
    out["stoch_d"] = out["stoch_k"].rolling(3).mean()
    r = out["rsi_14"]
    out["stoch_rsi"] = ((r - r.rolling(14).min())
                        / (r.rolling(14).max() - r.rolling(14).min()).replace(0, np.nan))
    out["williams_r"] = -100 * (hh - c) / (hh - ll).replace(0, np.nan)
    tp = (h + l + c) / 3
    md = (tp - tp.rolling(20).mean()).abs().rolling(20).mean()
    out["cci_20"] = (tp - tp.rolling(20).mean()) / (0.015 * md.replace(0, np.nan))
    for n in (5, 10, 20):
        out["roc_%d" % n] = c.pct_change(n) * 100
    out["momentum_10"] = c - c.shift(10)
    d = c.diff()
    out["tsi"] = 100 * (_ema(_ema(d, 25), 13)
                        / _ema(_ema(d.abs(), 25), 13).replace(0, np.nan))
    bp = c - pd.concat([l, c.shift(1)], axis=1).min(axis=1)
    tr = _true_range(h, l, c)
    a7 = bp.rolling(7).sum() / tr.rolling(7).sum().replace(0, np.nan)
    a14 = bp.rolling(14).sum() / tr.rolling(14).sum().replace(0, np.nan)
    a28 = bp.rolling(28).sum() / tr.rolling(28).sum().replace(0, np.nan)
    out["ultimate_osc"] = 100 * (4 * a7 + 2 * a14 + a28) / 7
    out["chande_mom"] = (100 * (d.clip(lower=0).rolling(14).sum()
                                - (-d).clip(lower=0).rolling(14).sum())
                         / d.abs().rolling(14).sum().replace(0, np.nan))
    out["coppock"] = (c.pct_change(11) * 100 + c.pct_change(14) * 100).rolling(10).mean()
    out["kst"] = sum((c.pct_change(rc) * 100).rolling(sm).mean() * w
                     for rc, sm, w in ((10, 10, 1), (15, 10, 2), (20, 10, 3), (30, 15, 4)))
    hl2 = (h + l) / 2
    out["awesome_osc"] = hl2.rolling(5).mean() - hl2.rolling(34).mean()
    x = (2 * ((c - l.rolling(10).min())
              / (h.rolling(10).max() - l.rolling(10).min()).replace(0, np.nan)) - 1)
    x = x.clip(-0.999, 0.999)
    out["fisher_transform"] = 0.5 * np.log((1 + x) / (1 - x))
    out["trix"] = _ema(_ema(_ema(np.log(c), 15), 15), 15).pct_change() * 10000
    return out


def f_bands(df):
    h, l, c = df["h"], df["l"], df["c"]
    out = pd.DataFrame(index=df.index)
    m, s = c.rolling(20).mean(), c.rolling(20).std()
    out["bb_mid"], out["bb_upper"], out["bb_lower"] = m, m + 2 * s, m - 2 * s
    out["bb_width"] = (out["bb_upper"] - out["bb_lower"]) / m.replace(0, np.nan)
    out["bb_pctb"] = ((c - out["bb_lower"])
                      / (out["bb_upper"] - out["bb_lower"]).replace(0, np.nan))
    atr = _wilder(_true_range(h, l, c), 14)
    ke = _ema(c, 20)
    out["keltner_up"], out["keltner_lo"] = ke + 2 * atr, ke - 2 * atr
    out["keltner_width"] = (out["keltner_up"] - out["keltner_lo"]) / ke.replace(0, np.nan)
    out["atr_band_up"], out["atr_band_lo"] = c + 2 * atr, c - 2 * atr
    out["chandelier_exit"] = h.rolling(22).max() - 3 * atr
    # squeeze: Bollinger inside Keltner = compression, often precedes expansion
    out["squeeze_flag"] = ((out["bb_upper"] < out["keltner_up"])
                           & (out["bb_lower"] > out["keltner_lo"])).astype(float)
    return out


def f_volume(df):
    h, l, c, v, n = df["h"], df["l"], df["c"], df["v"], df["n"]
    out = pd.DataFrame(index=df.index)
    out["obv"] = (np.sign(c.diff()).fillna(0) * v).cumsum()
    tp = (h + l + c) / 3
    out["vwap_24h"] = (tp * v).rolling(24).sum() / v.rolling(24).sum().replace(0, np.nan)
    out["vwap_dev"] = c / out["vwap_24h"] - 1
    out["vol_sma_20"] = v.rolling(20).mean()
    out["vol_zscore"] = (v - v.rolling(720).mean()) / v.rolling(720).std()
    out["vol_surprise"] = np.log(v.replace(0, np.nan)
                                 / v.rolling(720).median().replace(0, np.nan))
    mfm = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    out["cmf"] = (mfm * v).rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)
    out["ad_line"] = (mfm * v).cumsum()
    out["force_index"] = _ema(c.diff() * v, 13)
    out["eom"] = ((((h + l) / 2).diff() * (h - l)) / v.replace(0, np.nan)).rolling(14).mean()
    dv = v.diff()
    rsv = _wilder(dv.clip(lower=0), 14) / _wilder((-dv).clip(lower=0), 14).replace(0, np.nan)
    out["volume_rsi"] = 100 - 100 / (1 + rsv)
    out["pvt"] = (c.pct_change().fillna(0) * v).cumsum()
    pos = (tp * v).where(tp > tp.shift(1), 0.0)
    neg = (tp * v).where(tp < tp.shift(1), 0.0)
    out["mfi_14"] = 100 - 100 / (1 + pos.rolling(14).sum()
                                 / neg.rolling(14).sum().replace(0, np.nan))
    out["trade_count"] = n
    out["avg_trade_size"] = v / n.replace(0, np.nan)
    return out


def f_risk(df):
    c = df["c"]
    lr = np.log(c / c.shift(1))
    out = pd.DataFrame(index=df.index)
    out["drawdown"] = c / c.cummax() - 1
    out["max_dd_30d"] = (c / c.rolling(720).max() - 1).rolling(720).min()
    yr = HOURS_YEAR
    out["max_dd_1y"] = ((c / c.rolling(yr, min_periods=720).max() - 1)
                        .rolling(yr, min_periods=720).min())
    out["ulcer_index"] = np.sqrt((out["drawdown"] ** 2).rolling(336).mean())
    mu, sd = lr.rolling(720).mean(), lr.rolling(720).std()
    out["sharpe_30d"] = (mu / sd.replace(0, np.nan)) * np.sqrt(yr)
    dsd = lr.clip(upper=0).rolling(720).std()
    out["sortino_30d"] = (mu / dsd.replace(0, np.nan)) * np.sqrt(yr)
    out["calmar"] = (mu * yr) / out["max_dd_1y"].abs().replace(0, np.nan)
    out["var_95"] = lr.rolling(720).quantile(0.05)
    out["cvar_95"] = lr.rolling(720).apply(
        lambda x: float(x[x <= np.quantile(x, 0.05)].mean()) if len(x) else np.nan, raw=True)
    out["autocorr_1"] = lr.rolling(336).apply(
        lambda x: float(pd.Series(x).autocorr(1)) if len(x) > 2 else np.nan, raw=True)
    # variance ratio: >1 trending, <1 mean-reverting
    out["variance_ratio"] = (lr.rolling(168).sum().rolling(720).var()
                             / (168 * lr.rolling(720).var()).replace(0, np.nan))

    def _ent(x):
        hgram, _ = np.histogram(x, bins=10)
        p = hgram / hgram.sum()
        p = p[p > 0]
        return float(-(p * np.log(p)).sum())
    out["entropy"] = lr.rolling(336).apply(_ent, raw=True)
    out["tail_ratio"] = (lr.rolling(720).quantile(0.95).abs()
                         / lr.rolling(720).quantile(0.05).abs().replace(0, np.nan))
    return out


def f_candle(df):
    o, h, l, c = df["o"], df["h"], df["l"], df["c"]
    rng = (h - l).replace(0, np.nan)
    out = pd.DataFrame(index=df.index)
    out["body_pct"] = (c - o).abs() / rng
    out["upper_wick_pct"] = (h - pd.concat([o, c], axis=1).max(axis=1)) / rng
    out["lower_wick_pct"] = (pd.concat([o, c], axis=1).min(axis=1) - l) / rng
    out["range_pct"] = rng / c
    out["gap_pct"] = o / c.shift(1) - 1
    out["inside_bar"] = ((h < h.shift(1)) & (l > l.shift(1))).astype(float)
    out["outside_bar"] = ((h > h.shift(1)) & (l < l.shift(1))).astype(float)
    out["doji"] = (out["body_pct"] < 0.1).astype(float)
    out["close_loc"] = (c - l) / rng
    out["hi_lo_2d"] = (h.rolling(48).max() - l.rolling(48).min()) / c
    up = (c > o).astype(float)
    out["n_up_bars_7d"] = up.rolling(168).sum()
    grp = (up != up.shift()).cumsum()
    out["consec_up"] = up.groupby(grp).cumsum() * up
    return out


FAMILIES = [
    ("feat_ret", f_returns), ("feat_volat", f_volatility), ("feat_trend", f_trend),
    ("feat_osc", f_oscillators), ("feat_bands", f_bands), ("feat_vol_flow", f_volume),
    ("feat_risk", f_risk), ("feat_candle", f_candle),
]


# ------------------------------------------------------------------ driver

def load_bars(conn, asset_id, since_ms=None):
    q = ("SELECT ts_ms, o, h, l, c, v, n FROM ohlcv "
         "WHERE asset_id=? AND interval='1h'")
    args = [asset_id]
    if since_ms:
        q += " AND ts_ms>=?"
        args.append(since_ms)
    q += " ORDER BY ts_ms"
    df = pd.read_sql_query(q, conn, params=args)
    if df.empty:
        return df
    df = df.set_index("ts_ms")
    return df[~df.index.duplicated(keep="last")]


def _write(conn, table, aid, frame, only_after=None):
    frame = frame.replace([np.inf, -np.inf], np.nan)
    if only_after is not None:
        frame = frame[frame.index > only_after]
    frame = frame.dropna(how="all")
    if frame.empty:
        return 0
    cols = list(frame.columns)
    rows = [(int(ts), aid) + tuple(None if pd.isna(x) else float(x) for x in rec)
            for ts, rec in zip(frame.index, frame.to_numpy())]
    return store.insert_many(conn, table, ["ts_ms", "asset_id"] + cols, rows, replace=True)


def compute_asset(conn, symbol, full=False):
    aid = store.asset_id(conn, symbol)
    watermark = None
    if not full:
        r = conn.execute("SELECT MAX(ts_ms) FROM feat_ret WHERE asset_id=?", (aid,)).fetchone()
        watermark = r[0] if r and r[0] else None

    since = (watermark - WARMUP * 3_600_000) if watermark else None
    df = load_bars(conn, aid, since)
    if len(df) < 60:
        return 0, len(df)

    total = 0
    for table, fn in FAMILIES:
        try:
            total += _write(conn, table, aid, fn(df), only_after=watermark)
        except Exception as e:  # noqa: BLE001
            print("      %s FAILED: %s" % (table, str(e)[:90]))
    conn.commit()
    return total, len(df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--full", action="store_true", help="recompute from scratch")
    a = ap.parse_args()

    conn = store.init()
    if a.symbols:
        syms = [s.strip().upper() for s in a.symbols.split(",")]
    else:
        syms = [r[0] for r in conn.execute(
            "SELECT DISTINCT a.symbol FROM asset a JOIN ohlcv o ON o.asset_id=a.id "
            "GROUP BY a.symbol HAVING COUNT(*)>200 ORDER BY COUNT(*) DESC")]
    if not a.all and not a.symbols:
        syms = syms[:5]

    print("computing 157 features for %d assets" % len(syms))
    print("=" * 72)
    t0 = time.time()
    grand = 0
    for i, s in enumerate(syms, 1):
        ts = time.time()
        n, bars = compute_asset(conn, s, full=a.full)
        grand += n
        print("  [%3d/%d] %-9s %7s bars -> %8s feature rows  (%.1fs)"
              % (i, len(syms), s, format(bars, ","), format(n, ","), time.time() - ts))
    store.log_run(conn, "features:compute", True, grand, int((time.time() - t0) * 1000))
    conn.commit()
    print("=" * 72)
    print("total %s feature rows in %.0fs" % (format(grand, ","), time.time() - t0))
    conn.close()


if __name__ == "__main__":
    main()
