"""The cross-sectional layer: beta, residual returns, idiosyncratic vol, correlation
matrices (normal and stressed), clusters, breadth - computed from the daily closes we
already have, as-of every day (nothing uses a later row), and written both to the sim
cache and to store.db feat_cross so the live terminal sees the same numbers.

Definitions (docs/AGENT_V2_RESEARCH_2026-09-16.md D(iii)):
  beta_btc_raw  OLS slope of the coin's daily log return on BTC's, 60-day window
  beta_btc      Vasicek shrinkage of the raw beta toward the day's cross-sectional
                median, weighted by each coin's standard error (noisy betas shrink more)
  r2_btc        share of the coin's variance BTC explains over the window
  resid_r_1d    today's return minus beta(yesterday) * BTC return  (no look-ahead)
  resid_mom_*   sum of residual returns over t-8..t-2 / t-31..t-2 (skip the last day)
  idio_vol_30d  std of residual returns, annualised;  idio_daily_move_pct = its daily size
  beta_stress   OLS on the worst-decile |BTC| days of the trailing 365 (refreshed monthly)
  corr_btc_30d / 90d
  universe series: breadth_1d, mean_corr_60d, common_share (PC1 share), neff
  clusters      hierarchical (Ward linkage, d = sqrt(0.5 (1 - rho))) on the 90-day
                residual correlation, cut into 8 groups (average linkage put 157 of 172
                coins in one blob; Ward gives balanced, recognisable groups), refreshed monthly; Jaccard
                stability vs the previous month
  corr matrices weekly: Ledoit-Wolf (constant-correlation target) shrunk residual
                correlation over 60 days, and the same on the shock days of the last year
"""
from __future__ import annotations

import math
import sqlite3
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from .data import DECIDE_OFF, STORE, _cached, _names, daily_ohlc

WIN = 60          # beta / corr window (days)
IDIO_WIN = 30
CLUSTER_WIN = 90
N_CLUSTERS = 8
MIN_OBS = 40


def _log_returns(close: pd.DataFrame = None) -> pd.DataFrame:
    close = daily_ohlc()["close"] if close is None else close
    r = np.log(close).diff()
    return r.where(r.abs() < 1.5)          # drop listing/glitch bars (>350% moves)


def _rolling_beta(r: pd.DataFrame, b: pd.Series, win: int) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Slope, its standard error and R^2 of r on b over a rolling window (vectorised)."""
    bb = b.reindex(r.index)
    both = r.notna() & bb.notna().values[:, None]
    n = both.rolling(win).sum()
    rr = r.where(both); bm = pd.DataFrame(np.repeat(bb.values[:, None], r.shape[1], axis=1), index=r.index, columns=r.columns).where(both)
    sx = bm.rolling(win, min_periods=MIN_OBS).sum(); sy = rr.rolling(win, min_periods=MIN_OBS).sum()
    sxx = (bm ** 2).rolling(win, min_periods=MIN_OBS).sum(); syy = (rr ** 2).rolling(win, min_periods=MIN_OBS).sum()
    sxy = (bm * rr).rolling(win, min_periods=MIN_OBS).sum()
    varx = sxx / n - (sx / n) ** 2; vary = syy / n - (sy / n) ** 2; cov = sxy / n - (sx / n) * (sy / n)
    beta = cov / varx
    r2 = (cov ** 2 / (varx * vary)).clip(0, 1)
    resid_var = (vary * (1 - r2)) * n / (n - 2)
    se = np.sqrt(resid_var / (n * varx))
    return beta, se, r2


def _vasicek(beta: pd.DataFrame, se: pd.DataFrame) -> pd.DataFrame:
    """Shrink each coin's beta toward the day's cross-sectional median; a coin with a large
    standard error is pulled harder. beta_shr = (b/se^2 + m/tau^2) / (1/se^2 + 1/tau^2)."""
    m = beta.median(axis=1)
    mad = (beta.sub(m, axis=0)).abs().median(axis=1)                 # robust spread: outlier betas must not widen the prior
    tau2 = ((1.4826 * mad) ** 2).clip(lower=1e-4)
    w = 1.0 / (se ** 2).clip(lower=1e-6)
    wm = (1.0 / tau2).values[:, None]
    return (beta * w + m.values[:, None] * wm) / (w + wm)


def _ledoit_wolf_corr(x: np.ndarray) -> np.ndarray:
    """Ledoit & Wolf (2004) shrinkage of a sample correlation matrix toward the constant-
    correlation target (all off-diagonals = their average). x: T x N standardised returns."""
    T, N = x.shape
    s = np.corrcoef(x, rowvar=False)
    rbar = (s.sum() - N) / (N * (N - 1))
    f = np.full((N, N), rbar); np.fill_diagonal(f, 1.0)
    # pi: sum of asymptotic variances of the sample correlations
    x2 = x ** 2
    pi_mat = (x2.T @ x2) / T - s ** 2
    pi = pi_mat.sum()
    # rho: covariance between sample correlations and the target (constant-corr version)
    theta = ((x ** 3).T @ x) / T - (np.diag(s)[:, None] * s)     # asymptotic cov of s_ii, s_ij (s_ii = 1)
    off = theta.copy(); np.fill_diagonal(off, 0.0)                    # the i != j terms only
    rho = np.trace(pi_mat) + rbar * off.sum()
    gamma = ((f - s) ** 2).sum()
    kappa = (pi - rho) / gamma if gamma > 0 else 0.0
    delta = float(min(max(kappa / T, 0.0), 1.0))
    out = delta * f + (1 - delta) * s
    np.fill_diagonal(out, 1.0)
    return out


def build_xsec(close: pd.DataFrame = None) -> Dict[str, object]:
    r = _log_returns(close)
    if "BTC" not in r.columns:
        raise RuntimeError("BTC missing from daily closes")
    btc = r["BTC"]
    beta_raw, beta_se, r2 = _rolling_beta(r, btc, WIN)
    beta = _vasicek(beta_raw, beta_se)
    beta_lag = beta.shift(1)                                            # yesterday's beta -> no look-ahead
    resid = r - beta_lag.mul(btc, axis=0)
    resid_mom7 = resid.shift(2).rolling(7, min_periods=5).sum()          # t-8 .. t-2
    resid_mom30 = resid.shift(2).rolling(30, min_periods=20).sum()      # t-31 .. t-2
    idio_vol = resid.rolling(IDIO_WIN, min_periods=20).std() * math.sqrt(365)
    idio_ewma = np.sqrt((resid ** 2).ewm(alpha=0.06, min_periods=20).mean()) * math.sqrt(365)
    idio_daily = idio_vol / math.sqrt(365) * 100.0
    corr30 = r.rolling(30, min_periods=20).corr(btc)
    corr90 = r.rolling(90, min_periods=50).corr(btc)
    # cross-sectional ranks (0..1) of 1d / 7d returns and of idio vol
    rank_ret_1d = r.rank(axis=1, pct=True); rank_ret_7d = r.rolling(7).sum().rank(axis=1, pct=True)
    rank_vol = idio_vol.rank(axis=1, pct=True)

    # ---- universe series ------------------------------------------------------
    breadth_1d = (r > 0).sum(axis=1) / r.notna().sum(axis=1)
    mean_corr, mean_corr_raw, common_share, neff, stress_corr = {}, {}, {}, {}, {}
    raw_mats: Dict[int, pd.DataFrame] = {}
    beta_stress = pd.DataFrame(index=r.index, columns=r.columns, dtype="float64")
    corr_mats: Dict[int, pd.DataFrame] = {}; stress_mats: Dict[int, pd.DataFrame] = {}
    cluster_id = pd.DataFrame(index=r.index, columns=r.columns, dtype="float64")
    stability: Dict[int, float] = {}
    prev_clusters = None
    days = list(r.index)
    for i, d in enumerate(days):
        if i < WIN:
            continue
        weekly = (i % 7 == 0); monthly = (i % 30 == 0)
        if not (weekly or monthly):
            continue
        win = resid.iloc[i - WIN + 1: i + 1]
        ok = win.columns[win.notna().sum() >= MIN_OBS]
        if len(ok) < 10:
            continue
        w = win[ok].fillna(0.0)
        z = (w - w.mean()) / w.std().replace(0, np.nan)
        z = z.dropna(axis=1, how="any")
        if z.shape[1] < 10:
            continue
        if weekly:
            # residual-return matrix (for clusters / hedged risk)
            c = _ledoit_wolf_corr(z.values)
            cm = pd.DataFrame(c, index=z.columns, columns=z.columns)
            corr_mats[int(d)] = cm
            iu = np.triu_indices(len(cm), 1)
            mean_corr[d] = float(np.mean(c[iu]))
            # raw-return matrix (the "is the market one trade" read): mean corr, PC1 share, effective N
            rw = r.iloc[i - WIN + 1: i + 1][ok].fillna(0.0)
            rz = (rw - rw.mean()) / rw.std().replace(0, np.nan); rz = rz.dropna(axis=1, how="any")
            if rz.shape[1] >= 10:
                cr = _ledoit_wolf_corr(rz.values)
                raw_mats[int(d)] = pd.DataFrame(cr, index=rz.columns, columns=rz.columns)
                iu2 = np.triu_indices(len(cr), 1)
                mc = float(np.mean(cr[iu2])); mean_corr_raw[d] = mc
                ev = np.linalg.eigvalsh(cr)[::-1]; common_share[d] = float(ev[0] / ev.sum())
                n_ = len(cr); neff[d] = float(n_ / (1 + (n_ - 1) * mc))
        if monthly:
            # stress matrix and stressed beta: worst-decile |BTC| days of the trailing 365
            lo = max(0, i - 365)
            bwin = btc.iloc[lo: i + 1].dropna()
            thr = bwin.abs().quantile(0.9)
            shock_days = bwin.index[bwin.abs() > thr]
            sw = r.loc[shock_days]
            okc = sw.columns[sw.notna().sum() >= 8]
            if len(okc) >= 10 and len(shock_days) >= 8:
                zs = sw[okc].fillna(0.0); zs = (zs - zs.mean()) / zs.std().replace(0, np.nan); zs = zs.dropna(axis=1, how="any")
                if zs.shape[1] >= 10:
                    cs = np.corrcoef(zs.values, rowvar=False)
                    stress_mats[int(d)] = pd.DataFrame(cs, index=zs.columns, columns=zs.columns)
                    stress_corr[d] = float(np.mean(cs[np.triu_indices(len(cs), 1)]))
                bs = sw.loc[:, okc]; bb = btc.loc[shock_days]
                valid = bs.notna()
                ybar = valid.mul(bb, axis=0).sum() / valid.sum()             # BTC mean over each coin's valid days
                yc = pd.DataFrame(np.repeat(bb.values[:, None], len(okc), axis=1), index=bb.index, columns=okc) - ybar
                num = (bs - bs.mean()).mul(yc).sum()
                den = (yc ** 2).where(valid).sum()
                cov = num / den.replace(0, np.nan)
                beta_stress.loc[d, cov.index] = cov.values
            # clusters on the 90-day residual correlation
            cw = resid.iloc[max(0, i - CLUSTER_WIN + 1): i + 1]
            okk = cw.columns[cw.notna().sum() >= 60]
            if len(okk) >= N_CLUSTERS + 4:
                cz = cw[okk].fillna(0.0); cz = (cz - cz.mean()) / cz.std().replace(0, np.nan); cz = cz.dropna(axis=1, how="any")
                cc = np.corrcoef(cz.values, rowvar=False)
                dist = np.sqrt(0.5 * (1 - np.clip(cc, -1, 1))); np.fill_diagonal(dist, 0.0)
                labels = fcluster(linkage(squareform(dist, checks=False), method="ward"), N_CLUSTERS, criterion="maxclust")
                cur = dict(zip(cz.columns, labels))
                cluster_id.loc[d, list(cur)] = list(cur.values())
                if prev_clusters:
                    # Jaccard stability: share of coin pairs that stay together / were together in either month
                    common = [c_ for c_ in cur if c_ in prev_clusters]
                    same_now = {(a, b) for a in common for b in common if a < b and cur[a] == cur[b]}
                    same_prev = {(a, b) for a in common for b in common if a < b and prev_clusters[a] == prev_clusters[b]}
                    union = same_now | same_prev
                    stability[int(d)] = float(len(same_now & same_prev) / len(union)) if union else float("nan")
                prev_clusters = cur
    beta_stress = beta_stress.ffill(limit=35)
    cluster_id = cluster_id.ffill(limit=35)
    uni = pd.DataFrame({"breadth_1d": breadth_1d,
                        "mean_resid_corr_60d": pd.Series(mean_corr), "mean_corr_60d": pd.Series(mean_corr_raw),
                        "common_share": pd.Series(common_share), "neff": pd.Series(neff),
                        "stress_mean_corr": pd.Series(stress_corr)}).sort_index()
    ff = ["mean_resid_corr_60d", "mean_corr_60d", "common_share", "neff", "stress_mean_corr"]
    uni[ff] = uni[ff].ffill(limit=35)
    frames = {"beta_btc_raw": beta_raw, "beta_btc_se": beta_se, "beta_btc": beta, "r2_btc": r2,
              "resid_r_1d": resid, "resid_mom_7d_skip1": resid_mom7, "resid_mom_30d_skip1": resid_mom30,
              "idio_vol_30d": idio_vol, "idio_vol_ewma": idio_ewma, "idio_daily_move_pct": idio_daily,
              "beta_stress": beta_stress, "corr_btc_30d": corr30, "corr_btc_90d": corr90,
              "rank_ret_1d": rank_ret_1d, "rank_ret_7d": rank_ret_7d, "rank_vol": rank_vol, "cluster_id": cluster_id}
    return {"frames": {k: v.astype("float32") for k, v in frames.items()}, "universe": uni,
            "corr_mats": corr_mats, "raw_corr_mats": raw_mats, "stress_mats": stress_mats, "cluster_stability": stability,
            "computed_with_data_through": int(days[-1])}


def xsec() -> Dict[str, object]:
    return _cached("xsec_v3", build_xsec)


def write_store(x: Dict[str, object]) -> int:
    """Fill feat_cross in store.db (ts = the day's 23:00 bar, like every other feature)."""
    conn = sqlite3.connect(STORE)
    ids = {s: i for i, s in _names(conn).items()}
    f = x["frames"]
    cols = ["beta_btc", "beta_eth", "corr_btc_30d", "corr_btc_90d", "resid_r_1d", "resid_r_7d",
            "resid_mom_7d_skip1", "rank_ret_1d", "rank_ret_7d", "rank_vol", "idio_vol", "r2_btc"]
    resid7 = f["resid_r_1d"].rolling(7, min_periods=5).sum()
    src = {"beta_btc": f["beta_btc"], "beta_eth": None, "corr_btc_30d": f["corr_btc_30d"], "corr_btc_90d": f["corr_btc_90d"],
           "resid_r_1d": f["resid_r_1d"], "resid_r_7d": resid7, "resid_mom_7d_skip1": f["resid_mom_7d_skip1"],
           "rank_ret_1d": f["rank_ret_1d"], "rank_ret_7d": f["rank_ret_7d"], "rank_vol": f["rank_vol"],
           "idio_vol": f["idio_vol_30d"], "r2_btc": f["r2_btc"]}
    rows = []
    days = f["beta_btc"].index
    for coin in f["beta_btc"].columns:
        if coin not in ids:
            continue
        stack = pd.DataFrame({c: (src[c][coin] if src[c] is not None else pd.Series(np.nan, index=days)) for c in cols})
        stack = stack.dropna(subset=["beta_btc"])
        for day, rec in stack.iterrows():
            rows.append((int(day) + DECIDE_OFF, ids[coin], *[None if pd.isna(v) else float(v) for v in rec.values]))
    conn.execute("BEGIN")
    conn.executemany(f"INSERT OR REPLACE INTO feat_cross (ts_ms, asset_id, {', '.join(cols)}) VALUES (?, ?, {', '.join('?' * len(cols))})", rows)
    conn.commit(); conn.close()
    return len(rows)


if __name__ == "__main__":
    x = build_xsec()
    n = write_store(x)
    u = x["universe"].dropna().tail(1)
    print(f"feat_cross rows written: {n}; last day {pd.to_datetime(x['computed_with_data_through'], unit='ms').date()}")
    print(u.round(3).to_string())
