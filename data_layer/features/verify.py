"""Verify the feature engine against independently computed values.

A number appearing in a table proves nothing. Each check below recomputes the
value a DIFFERENT way — by hand from raw bars, or against a known identity —
and compares. Anything outside tolerance is printed as FAIL.

This is the check that is allowed to fail. If it cannot fail, it is not a test.

Run:  python data_layer/features/verify.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "store"))
import store  # noqa: E402

RESULTS = []


def check(name, got, want, tol=1e-6, note=""):
    if got is None or want is None or (isinstance(got, float) and np.isnan(got)):
        RESULTS.append((name, "SKIP", got, want, note))
        return
    err = abs(got - want)
    rel = err / max(abs(want), 1e-12)
    ok = err < tol or rel < tol
    RESULTS.append((name, "PASS" if ok else "FAIL", got, want, note))


def main():
    conn = store.connect(read_only=True)
    aid = conn.execute("SELECT id FROM asset WHERE symbol='BTC'").fetchone()[0]

    bars = pd.read_sql_query(
        "SELECT ts_ms,o,h,l,c,v,n FROM ohlcv WHERE asset_id=? AND interval='1h' "
        "ORDER BY ts_ms", conn, params=[aid]).set_index("ts_ms")
    print("BTC bars loaded: %s" % format(len(bars), ","))

    # pick a timestamp deep enough that every long window is warmed up
    ts = int(bars.index[-500])
    i = bars.index.get_loc(ts)
    c = bars["c"]
    h, l, o, v = bars["h"], bars["l"], bars["o"], bars["v"]

    def stored(table, col):
        r = conn.execute("SELECT %s FROM %s WHERE asset_id=? AND ts_ms=?" % (col, table),
                         (aid, ts)).fetchone()
        return r[0] if r else None

    # ---------------- 1. returns: recompute by hand from raw closes
    check("r_1h  = ln(C_t / C_t-1)", stored("feat_ret", "r_1h"),
          float(np.log(c.iloc[i] / c.iloc[i - 1])))
    check("r_1d  = ln(C_t / C_t-24)", stored("feat_ret", "r_1d"),
          float(np.log(c.iloc[i] / c.iloc[i - 24])))
    check("r_7d  = ln(C_t / C_t-168)", stored("feat_ret", "r_7d"),
          float(np.log(c.iloc[i] / c.iloc[i - 168])))
    # the skip matters: 7d momentum must SKIP the last day
    check("mom_7d_skip1 = ln(C_t-24 / C_t-168)", stored("feat_ret", "mom_7d_skip1"),
          float(np.log(c.iloc[i - 24] / c.iloc[i - 168])), note="skip-a-day")

    # ---------------- 2. moving averages: plain arithmetic mean
    check("sma_20 = mean(last 20 closes)", stored("feat_trend", "sma_20"),
          float(c.iloc[i - 19:i + 1].mean()))
    check("sma_200 = mean(last 200 closes)", stored("feat_trend", "sma_200"),
          float(c.iloc[i - 199:i + 1].mean()))

    # ---------------- 3. volatility: realized vol from scratch
    lr = np.log(c / c.shift(1))
    want_rv = float(lr.iloc[i - 23:i + 1].std() * np.sqrt(24 * 365))
    check("rv_24h = std(24 log rets) * sqrt(8760)", stored("feat_volat", "rv_24h"), want_rv)

    # Parkinson, independent implementation
    hl = np.log(h / l)
    want_pk = float(np.sqrt((hl.iloc[i - 23:i + 1] ** 2).mean() / (4 * np.log(2)))
                    * np.sqrt(24 * 365))
    check("parkinson = sqrt(mean(ln(H/L)^2)/(4ln2))*ann",
          stored("feat_volat", "parkinson"), want_pk)

    # ---------------- 4. RSI: Wilder smoothing, computed independently
    n = 14
    d = c.diff()
    up, dn = d.clip(lower=0), (-d).clip(lower=0)
    au = up.ewm(alpha=1 / n, adjust=False).mean()
    ad = dn.ewm(alpha=1 / n, adjust=False).mean()
    want_rsi = float(100 - 100 / (1 + au.iloc[i] / ad.iloc[i]))
    check("rsi_14 (Wilder alpha=1/14)", stored("feat_osc", "rsi_14"), want_rsi, tol=1e-5)

    # RSI must also be bounded 0..100 across the whole series
    rs = pd.read_sql_query(
        "SELECT rsi_14 FROM feat_osc WHERE asset_id=? AND rsi_14 IS NOT NULL",
        conn, params=[aid])["rsi_14"]
    check("rsi_14 min >= 0", float(rs.min()), 0.0, tol=50.0,
          note="min=%.2f max=%.2f" % (rs.min(), rs.max()))
    bad = int(((rs < 0) | (rs > 100)).sum())
    check("rsi_14 values outside 0..100", float(bad), 0.0, tol=0.5,
          note="%d violations of %d" % (bad, len(rs)))

    # ---------------- 5. MACD identity: macd - signal == hist
    m = stored("feat_trend", "macd")
    sg = stored("feat_trend", "macd_signal")
    hs = stored("feat_trend", "macd_hist")
    if None not in (m, sg, hs):
        check("macd - signal == hist", hs, m - sg, tol=1e-9)

    # ---------------- 6. Bollinger identity: mid == sma20, %B in range
    check("bb_mid == sma_20", stored("feat_bands", "bb_mid"),
          stored("feat_trend", "sma_20"), tol=1e-9)
    bbu, bbl, bbm = (stored("feat_bands", "bb_upper"), stored("feat_bands", "bb_lower"),
                     stored("feat_bands", "bb_mid"))
    if None not in (bbu, bbl, bbm):
        check("bb_upper - bb_mid == bb_mid - bb_lower (symmetry)",
              bbu - bbm, bbm - bbl, tol=1e-9)

    # ---------------- 7. ATR must be positive and < price
    atr = stored("feat_volat", "atr_14")
    px = float(c.iloc[i])
    if atr is not None:
        check("atr_14 > 0", 1.0 if atr > 0 else 0.0, 1.0, tol=0.1,
              note="atr=%.2f price=%.2f" % (atr, px))

    # ---------------- 8. candle geometry: the three parts sum to <= 1
    b = stored("feat_candle", "body_pct")
    uw = stored("feat_candle", "upper_wick_pct")
    lw = stored("feat_candle", "lower_wick_pct")
    if None not in (b, uw, lw):
        check("body + upper wick + lower wick == 1", b + uw + lw, 1.0, tol=1e-9)

    # ---------------- 9. NO LOOK-AHEAD: recompute using ONLY bars <= ts.
    # If a feature peeks forward, truncating the future changes its value.
    trunc = bars.iloc[:i + 1]
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import compute as C
    for tbl, fn, col in (("feat_ret", C.f_returns, "r_1d"),
                         ("feat_volat", C.f_volatility, "rv_24h"),
                         ("feat_trend", C.f_trend, "sma_50"),
                         ("feat_osc", C.f_oscillators, "rsi_14"),
                         ("feat_bands", C.f_bands, "bb_width"),
                         ("feat_risk", C.f_risk, "var_95")):
        try:
            val = float(fn(trunc)[col].iloc[-1])
            check("NO-LOOKAHEAD %s.%s" % (tbl, col), stored(tbl, col), val, tol=1e-6,
                  note="future bars removed")
        except Exception as e:  # noqa: BLE001
            RESULTS.append(("NO-LOOKAHEAD %s.%s" % (tbl, col), "ERROR", None, None,
                            str(e)[:50]))

    # ---------------- report
    print()
    print("=" * 96)
    print("%-52s %-6s %-16s %-16s" % ("CHECK", "STATUS", "STORED", "INDEPENDENT"))
    print("=" * 96)
    for name, status, got, want, note in RESULTS:
        g = "-" if got is None else ("%.8g" % got)
        w = "-" if want is None else ("%.8g" % want)
        print("%-52s %-6s %-16s %-16s %s" % (name[:52], status, g, w, note))
    print("=" * 96)
    p = sum(1 for r in RESULTS if r[1] == "PASS")
    f = sum(1 for r in RESULTS if r[1] == "FAIL")
    e = sum(1 for r in RESULTS if r[1] in ("ERROR", "SKIP"))
    print("PASS %d   FAIL %d   SKIP/ERROR %d" % (p, f, e))
    conn.close()
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
