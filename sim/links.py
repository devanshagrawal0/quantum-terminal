"""The links engine (spec 4.3 C19-C31, C48-C49; dossier C(iii)): measured responses of returns to
shocks, stored with n, t, sample and status, re-estimated as-of any date so the agent only
ever sees links that could have been measured by then.

Estimator: lag-augmented local projection (Montiel Olea & Plagborg-Moller 2021) - for each
horizon h, pooled OLS across coins and days of
    y[t+1..t+h] (cumulative forward return, residual for coin links)  on  shock[t],
    controls: 2 lags of the shock and 2 lags of the 1-day return, day fixed effect removed
    by demeaning within each day (cross-sectional), White standard errors clustered by day.
Admission: |t| >= 3 AND sign agreement in >= 3 of 4 non-overlapping sub-periods AND n_days >= 60.
Otherwise status 'unmeasured' (kept, weight NULL) or 'rejected' (|t| >= 3 but unstable sign).

Shocks implemented (all cross-sectional, coin-level, time-locked):
    funding_z      today's funding z-scored within the day's cross-section
    resid_mom_7d   7-day residual momentum (skip last day)
    long_share_z   Binance account long share z-scored within the day (from 2026-08-02 only)
Targets: residual forward return at h in {1,3,7,14} days (bps), raw return also stored.

`links` table lives in store.db:
    link(id, shock, target, horizon_days, beta_bps_per_1sd, se, tstat, n_obs, n_days,
         sign_agree_k_of_4, sample_start, sample_end, as_of, status, estimator)
"""
from __future__ import annotations

import math
import sqlite3
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .data import STORE, daily_funding, daily_positioning

DAY_MS = 86_400_000
HORIZONS = (1, 3, 7, 14)
T_ADMIT = 3.0
MIN_DAYS = 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS link (
  id INTEGER PRIMARY KEY, shock TEXT NOT NULL, target TEXT NOT NULL, horizon_days INTEGER NOT NULL,
  beta_bps_per_1sd REAL, se REAL, tstat REAL, n_obs INTEGER, n_days INTEGER, sign_agree_k_of_4 INTEGER,
  sample_start INTEGER, sample_end INTEGER, as_of INTEGER NOT NULL, status TEXT NOT NULL, estimator TEXT NOT NULL,
  UNIQUE(shock, target, horizon_days, as_of)
);
"""


def _zscore_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1).replace(0, np.nan), axis=0)


def _rank_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Within-day rank mapped to a standard normal (robust to extreme funding prints)."""
    from scipy.stats import norm
    u = df.rank(axis=1, pct=True)
    n = df.notna().sum(axis=1)
    u = u.mul(n, axis=0).sub(0.5).div(n, axis=0)          # (rank - 0.5) / n  in (0, 1)
    return pd.DataFrame(norm.ppf(u.values), index=df.index, columns=df.columns)


def _clustered_ols(y: np.ndarray, X: np.ndarray, groups: np.ndarray):
    """OLS beta for the first column of X with day-clustered (White) standard errors."""
    XtX = X.T @ X
    XtX_inv = np.linalg.pinv(XtX)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    G = pd.DataFrame(X * e[:, None]).groupby(groups).sum().values     # per-day score sums (vectorised)
    meat = G.T @ G
    V = XtX_inv @ meat @ XtX_inv
    return float(beta[0]), float(math.sqrt(max(V[0, 0], 1e-18)))


def local_projection(shock: pd.DataFrame, fwd: pd.DataFrame, r1: pd.DataFrame, h: int, transform: str = "z") -> Dict:
    """Pooled lag-augmented LP of the h-day forward return on the shock (both day-demeaned).
    transform: 'z' (cross-sectional z-score) or 'rank' (within-day rank -> normal scores)."""
    s0 = _rank_rows(shock) if transform == "rank" else _zscore_rows(shock)
    s1, s2 = s0.shift(1), s0.shift(2)
    y = fwd.sub(fwd.mean(axis=1), axis=0)
    rl1, rl2 = r1.shift(1), r1.shift(2)
    rl1 = rl1.sub(rl1.mean(axis=1), axis=0); rl2 = rl2.sub(rl2.mean(axis=1), axis=0)
    frames = {"y": y, "s": s0, "s1": s1, "s2": s2, "r1": rl1, "r2": rl2}
    st = pd.concat({k: v.stack() for k, v in frames.items()}, axis=1).dropna()
    st = st[st["y"].abs() < 2.0]
    if len(st) < 500:
        return {"n_obs": int(len(st)), "n_days": 0, "beta": None, "se": None, "t": None, "k": 0}
    days = st.index.get_level_values(0).values
    X = np.column_stack([st["s"].values, st["s1"].values, st["s2"].values, st["r1"].values, st["r2"].values, np.ones(len(st))])
    b, se = _clustered_ols(st["y"].values * 1e4, X, days)
    # sign stability over 4 non-overlapping sub-periods
    uniq = np.unique(days); parts = np.array_split(uniq, 4); k = 0
    for part in parts:
        m = np.isin(days, part)
        if m.sum() < 200:
            continue
        bp, _ = _clustered_ols(st["y"].values[m] * 1e4, X[m], days[m])
        k += int(np.sign(bp) == np.sign(b))
    return {"n_obs": int(len(st)), "n_days": int(len(uniq)), "beta": b, "se": se, "t": b / se if se else None, "k": k,
            "sample_start": int(uniq.min()), "sample_end": int(uniq.max())}


def shocks_and_targets(x: Dict, close: pd.DataFrame, as_of: int):
    """Shock frames and forward-return frames using only rows with day <= as_of and
    forward windows that END by as_of (no outcome leaks)."""
    resid = x["frames"]["resid_r_1d"].astype(float)
    r1 = np.log(close).diff().where(lambda v: v.abs() < 1.5)
    fund = daily_funding().reindex(columns=[c for c in resid.columns if c in daily_funding().columns])
    fund = fund.reindex(resid.index)
    shocks = {"funding_z": fund, "resid_mom_7d": x["frames"]["resid_mom_7d_skip1"].astype(float)}
    try:
        pos = daily_positioning()["long_frac"].reindex(resid.index)
        pos = pos.reindex(columns=resid.columns)
        shocks["long_share_z"] = pos
    except Exception:
        pass
    out = {}
    for h in HORIZONS:
        fwd = resid.rolling(h).sum().shift(-h)                   # sum of resid returns t+1..t+h
        fwd = fwd[fwd.index + h * DAY_MS <= as_of]               # window fully inside the as-of past
        out[h] = fwd
    return {k: v[v.index <= as_of] for k, v in shocks.items()}, out, r1[r1.index <= as_of]


def estimate(x: Dict, close: pd.DataFrame, as_of: int, conn: Optional[sqlite3.Connection] = None) -> List[Dict]:
    own = conn is None
    conn = conn or sqlite3.connect(STORE)
    conn.executescript(SCHEMA)
    shocks, fwds, r1 = shocks_and_targets(x, close, as_of)
    rows = []
    variants = [(name, sh, tr) for name, sh in shocks.items() for tr in ("z", "rank")]
    for base, sh, tr in variants:
        name = base if tr == "z" else base.replace("_z", "") + "_rank"
        for h, fwd in fwds.items():
            res = local_projection(sh, fwd, r1, h, transform=tr)
            t = res.get("t")
            if res["n_days"] < MIN_DAYS or t is None:
                status = "unmeasured"
            elif abs(t) >= T_ADMIT and res["k"] >= 3:
                status = "admitted"
            elif abs(t) >= T_ADMIT:
                status = "rejected"
            else:
                status = "unmeasured"
            row = {"shock": name, "target": "resid_return", "horizon_days": h, "beta_bps_per_1sd": None if res["beta"] is None else round(res["beta"], 2),
                   "se": None if res["se"] is None else round(res["se"], 2), "tstat": None if t is None else round(t, 2),
                   "n_obs": res["n_obs"], "n_days": res["n_days"], "sign_agree_k_of_4": res["k"],
                   "sample_start": res.get("sample_start"), "sample_end": res.get("sample_end"), "as_of": as_of,
                   "status": status, "estimator": "LP_lagaug_dayFE_clusterSE"}
            rows.append(row)
            conn.execute("INSERT OR REPLACE INTO link(shock,target,horizon_days,beta_bps_per_1sd,se,tstat,n_obs,n_days,sign_agree_k_of_4,"
                         "sample_start,sample_end,as_of,status,estimator) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         tuple(row[k] for k in ("shock", "target", "horizon_days", "beta_bps_per_1sd", "se", "tstat", "n_obs", "n_days",
                                                 "sign_agree_k_of_4", "sample_start", "sample_end", "as_of", "status", "estimator")))
    conn.commit()
    if own:
        conn.close()
    return rows


def links_as_of(as_of: int, conn: Optional[sqlite3.Connection] = None) -> List[Dict]:
    """The latest vintage of every link measured at or before as_of."""
    own = conn is None
    conn = conn or sqlite3.connect(f"file:{STORE}?mode=ro", uri=True)
    try:
        conn.execute("SELECT 1 FROM link LIMIT 1")
    except sqlite3.OperationalError:
        return []
    rows = conn.execute(
        "SELECT shock, target, horizon_days, beta_bps_per_1sd, se, tstat, n_obs, n_days, sign_agree_k_of_4, status, as_of "
        "FROM link WHERE as_of <= ? ORDER BY as_of DESC", (as_of,)).fetchall()
    seen = set(); out = []
    for r in rows:
        key = (r[0], r[1], r[2])
        if key in seen:
            continue
        seen.add(key)
        out.append({"shock": r[0], "target": r[1], "horizon_days": r[2], "beta_bps_per_1sd": r[3], "se": r[4], "tstat": r[5],
                    "n_obs": r[6], "n_days": r[7], "sign_agree_k_of_4": r[8], "status": r[9], "measured_as_of": r[10]})
    if own:
        conn.close()
    return sorted(out, key=lambda d: (d["shock"], d["horizon_days"]))


if __name__ == "__main__":
    import sys
    from .xsec import xsec
    from .data import daily_ohlc
    from .run import day_ms
    as_of = day_ms(sys.argv[1]) if len(sys.argv) > 1 else int(daily_ohlc()["close"].index[-1])
    rows = estimate(xsec(), daily_ohlc()["close"], as_of)
    print(f"{'shock':14} {'h':>3} {'beta bps/1sd':>13} {'t':>7} {'n_days':>7} {'k/4':>4} status")
    for r in rows:
        print(f"{r['shock']:14} {r['horizon_days']:>3} {str(r['beta_bps_per_1sd']):>13} {str(r['tstat']):>7} {r['n_days']:>7} {r['sign_agree_k_of_4']:>4} {r['status']}")
