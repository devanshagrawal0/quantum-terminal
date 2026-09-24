"""The signal engine — a coin's numbers, ranked against the whole market.

The edge is not in a raw number, it is in the RANKING: a +8% week means nothing until
you know it is the 3rd-best of 80 coins. So this computes a feature vector for EVERY
tradable coin, z-scores each feature across the universe, and turns the ranks into named,
directional, fee-aware signals — the exact factor set the research points to:

  momentum (7-28d, skipping the last 2d so the short-term reversal doesn't poison it),
  long-horizon reversal (moves past a month tend to reverse), 1-3d reversal (real but
  mostly lives inside the spread — flagged), funding level/trend/squeeze, open-interest-
  vs-price regime (deleveraging vs leverage-build), realized-vol regime + downside vol,
  perp basis + cross-venue dispersion, beta & BTC-residual return (so an alt call isn't
  just a levered BTC bet), drawdown, Amihud illiquidity (a TRADABILITY filter, not alpha),
  and attention INFLECTION (z-score, not raw level).

Every signal states its direction, how strong it ranks, and whether the expected move
clears the Hyperliquid fee floor (~0.09% taker round-trip, ~0.20% with slippage on a
small perp). A signal that can't beat fees is labeled dead, not dressed up.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]

# fee floor — the one number that governs everything (research §0)
TAKER_RT = 0.0009          # 0.045% x2, round-trip, taker
SLIP_RT = 0.0020           # realistic all-in with slippage on a small perp
MAKER_RT = 0.0003          # if you truly use limit entries

# Empirical edge per unit of score, from the forward-tracker backfill (avg +0.45%
# BTC-neutral per pick; kept conservative so the fee gate never oversells).
EDGE_PER_SCORE = 0.007

# The composite's measured, unbiased edge (scripts/backtest_scores.py, 2026-08-25,
# point-in-time, net of 0.20%/side, BTC-neutral). These are the H=10 LONG-ONLY-HEDGED
# quintile numbers — the robust book. The long-SHORT version is NOT used: its Sharpe
# is unstable (flipped +1.41 -> -0.09 on a data refresh) because the short leg has no
# edge; long-only-hedged is +1.34 and positive in both halves. (L13.)
BACKTEST = {
    "hold_days": 10, "ic": 0.031, "ic_t": 3.99, "sharpe": 1.34, "hit": 0.55,
    "half1_sharpe": 1.20, "half2_sharpe": 1.92, "net_fee_pct": 0.20, "book": "long-only hedged",
    "caveat": "in-sample; H searched; needs out-of-sample (the live tracker is the real judge); survivorship (delisted coins excluded)",
}

_cache: Dict[str, Any] = {"t": 0.0, "univ": None}


def _universe() -> Optional[Dict[str, Any]]:
    """Compute the cross-section once (heavy: pandas over 80 coins), cache 5 min."""
    if time.time() - _cache["t"] < 300 and _cache["univ"] is not None:
        return _cache["univ"]
    try:
        import numpy as np
        import pandas as pd
    except Exception:
        return None
    px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
    fp = ROOT / "data" / "carry_cache" / "funding_daily_365.parquet"
    fund = pd.read_parquet(fp) if fp.exists() else None
    rows: Dict[str, Dict[str, float]] = {}
    btc = px["BTC"].dropna() if "BTC" in px.columns else None
    btc_ret = btc.pct_change() if btc is not None else None

    for coin in px.columns:
        s = px[coin].dropna()
        if len(s) < 40:
            continue
        last = float(s.iloc[-1])
        r: Dict[str, float] = {"last": last}
        # momentum 7-28d skipping last 2 (research: skip the reversal window)
        if len(s) > 30:
            r["mom_7_28"] = float(s.iloc[-3] / s.iloc[-30] - 1)
        if len(s) > 8:
            r["mom_7"] = float(s.iloc[-1] / s.iloc[-8] - 1)
        # long reversal: 30-90d winners tend to reverse -> we store the past move
        if len(s) > 90:
            r["past_30_90"] = float(s.iloc[-31] / s.iloc[-90] - 1)
        # 1-3d reversal (fade the last 3d)
        if len(s) > 4:
            r["ret_3d"] = float(last / s.iloc[-4] - 1)
        # realized vol + regime + downside semivariance
        ret = s.pct_change().dropna()
        if len(ret) > 35:
            rv7 = float(ret.tail(7).std() * np.sqrt(365))
            rv30 = float(ret.tail(30).std() * np.sqrt(365))
            r["rv_30"] = rv30
            r["vol_ratio"] = rv7 / rv30 if rv30 else float("nan")
            dn = ret.tail(30).clip(upper=0)
            r["downside_vol"] = float(dn.std() * np.sqrt(365))
        # drawdown / distance from 90d high
        if len(s) > 90:
            r["dist_high_90"] = float(last / s.tail(90).max() - 1)
        # amihud illiquidity (tradability filter): |ret| / (proxy $vol). No volume in
        # this frame, so use |ret| scaled by 1 as a relative illiquidity rank proxy.
        if len(ret) > 20:
            r["amihud"] = float(ret.tail(20).abs().mean())
        # beta / corr / residual return vs BTC
        if btc_ret is not None and coin != "BTC":
            m = pd.concat([ret, btc_ret], axis=1, keys=["c", "b"]).dropna().tail(60)
            if len(m) > 30 and m["b"].var():
                beta = float(np.cov(m["c"], m["b"])[0, 1] / m["b"].var())
                r["beta_btc"] = beta
                r["corr_btc"] = float(m["c"].corr(m["b"]))
                # BTC-neutral 7d residual: coin's 7d move minus beta*BTC's 7d move
                if "mom_7" in r and len(btc) > 8:
                    btc_7 = float(btc.iloc[-1] / btc.iloc[-8] - 1)
                    r["resid_7"] = r["mom_7"] - beta * btc_7
        # funding level + trend + z
        if fund is not None and coin in fund.columns:
            fh = fund[coin].dropna()
            if len(fh) > 30:
                # NOTE: this parquet stores DAILY-summed funding, so annualize x365
                # (NOT x24x365 — that would 24x-overcount; BTC would read +293%/yr).
                r["funding_apr"] = float(fh.iloc[-1] * 365)
                r["funding_z"] = float((fh.iloc[-1] - fh.tail(90).mean()) / (fh.tail(90).std() + 1e-9))
                r["funding_trend"] = float((fh.tail(3).mean() - fh.tail(10).mean()) * 365)
        rows[coin] = r

    df = pd.DataFrame(rows).T
    # cross-sectional z-scores (the ranking is the edge)
    zc = {}
    for col in ("mom_7_28", "ret_3d", "past_30_90", "funding_apr", "funding_z",
                "resid_7", "vol_ratio", "amihud", "downside_vol", "dist_high_90"):
        if col in df.columns:
            v = df[col].astype(float)
            sd = v.std()
            zc[col] = (v - v.mean()) / sd if sd else v * 0
    zdf = pd.DataFrame(zc)
    # percentile ranks (0-100) for display
    pct = {c: df[c].rank(pct=True) * 100 for c in df.columns if df[c].dtype != object}
    _cache["univ"] = {"raw": df, "z": zdf, "pct": pd.DataFrame(pct), "n": len(df)}
    _cache["t"] = time.time()
    return _cache["univ"]


def _live_oi(coin: str):
    """24h OI change + price change from venues.db, for the OI-vs-price regime."""
    try:
        c = sqlite3.connect(f"file:{ROOT/'data'/'venues.db'}?mode=ro", uri=True)
        now = time.time() * 1000
        cur = c.execute("SELECT mid,oi_base FROM hl_state WHERE coin=? ORDER BY ts_ms DESC LIMIT 1", (coin,)).fetchone()
        old = c.execute("SELECT mid,oi_base FROM hl_state WHERE coin=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1",
                        (coin, now - 24 * 3600000)).fetchone()
        basis = c.execute("SELECT sp_basis_bps,disp_iqr_bps,credible_vol_usd FROM cv_features WHERE coin=? ORDER BY ts_ms DESC LIMIT 1", (coin,)).fetchone()
        c.close()
        d = {}
        if cur and old and old[0] and old[1]:
            d["price_24h"] = cur[0] / old[0] - 1
            d["oi_24h"] = cur[1] / old[1] - 1
        if basis:
            d["basis_bps"], d["disp_bps"], d["vol_usd"] = basis
        return d
    except Exception:
        return {}


def coin_signals(coin: str) -> Dict[str, Any]:
    """The full ranked signal dossier for one coin: raw value, universe percentile,
    direction, strength, and a fee-aware read for each factor + a composite."""
    coin = coin.upper()
    u = _universe()
    if not u or coin not in u["raw"].index:
        return {"coin": coin, "signals": [], "composite": None, "n_universe": u["n"] if u else 0}
    raw = u["raw"].loc[coin]
    z = u["z"].loc[coin] if coin in u["z"].index else None
    pct = u["pct"].loc[coin] if coin in u["pct"].index else None
    oi = _live_oi(coin)
    sig: List[Dict[str, Any]] = []

    def g(col):
        try:
            v = raw.get(col)
            return None if v is None or (isinstance(v, float) and v != v) else float(v)
        except Exception:
            return None

    def zof(col):
        try:
            v = z.get(col) if z is not None else None
            return None if v is None or (isinstance(v, float) and v != v) else float(v)
        except Exception:
            return None

    def pof(col):
        try:
            v = pct.get(col) if pct is not None else None
            return None if v is None or (isinstance(v, float) and v != v) else float(v)
        except Exception:
            return None

    def add(name, value, disp, direction, strength, read, note=""):
        sig.append({"name": name, "value": value, "disp": disp, "dir": direction,
                    "strength": round(strength, 2), "read": read, "note": note})

    # --- momentum 7-28d (buy top rank / short bottom) ---
    m = g("mom_7_28"); zm = zof("mom_7_28"); pm = pof("mom_7_28")
    if m is not None and pm is not None:
        d = "long" if pm > 66 else "short" if pm < 34 else "neutral"
        add("Momentum 7-28d", m, f"{m*100:+.1f}% ({pm:.0f}%ile)", d, min(abs(zm or 0) / 2, 1),
            ("top-rank momentum — trend-continuation long" if d == "long"
             else "bottom-rank — laggard, momentum short" if d == "short" else "mid-pack, no momentum edge"),
            "skips last 2d so reversal doesn't poison it")

    # --- long-horizon reversal (30-90d winners reverse) ---
    lr = g("past_30_90"); plr = pof("past_30_90")
    if lr is not None and plr is not None:
        d = "short" if plr > 75 else "long" if plr < 25 else "neutral"
        add("Long reversal 30-90d", lr, f"{lr*100:+.1f}% past ({plr:.0f}%ile)", d, min(abs((plr-50)/50), 1),
            ("extended winner — mean-reversion SHORT candidate" if d == "short"
             else "beaten-down — reversion LONG candidate" if d == "long" else "no reversion signal"),
            "crypto momentum flips to reversal after ~1 month")

    # --- 1-3d reversal (flagged: mostly inside the spread) ---
    r3 = g("ret_3d")
    if r3 is not None:
        d = "short" if r3 > 0.06 else "long" if r3 < -0.06 else "neutral"
        add("Reversal 1-3d", -r3, f"{r3*100:+.1f}% last 3d", d, min(abs(r3) / 0.1, 1),
            "fade the 3d move" if d != "neutral" else "no 3d extreme",
            "WEAK: real but usually dies inside the bid-ask spread + fees")

    # --- funding level (crowding) ---
    fa = g("funding_apr")
    if fa is not None:
        d = "short" if fa > 0.30 else "long" if fa < -0.15 else "neutral"
        add("Funding (crowding)", fa, f"{fa*100:+.0f}%/yr", d, min(abs(fa) / 0.6, 1),
            ("crowded LONGS paying — squeeze/deleverage short" if d == "short"
             else "shorts paying — squeeze-up long" if d == "long" else "funding balanced"),
            "extreme funding is the highest edge-per-effort derivatives signal")

    # --- funding trend ---
    ft = g("funding_trend")
    if ft is not None and abs(ft) > 0.05:
        add("Funding trend", ft, f"{ft*100:+.0f}%/yr Δ", "info", min(abs(ft) / 0.4, 1),
            "funding rising — crowd piling in (fragile)" if ft > 0 else "funding falling — crowd unwinding", "")

    # --- OI vs price regime (deleveraging detection) ---
    if "oi_24h" in oi and "price_24h" in oi:
        o, p = oi["oi_24h"], oi["price_24h"]
        if p > 0.01 and o < -0.02:
            add("OI×Price regime", o, f"OI {o*100:+.1f}% / px {p*100:+.1f}%", "short", 0.6,
                "rally on FALLING OI = short-covering, weak — fades", "price↑ OI↓")
        elif p < -0.01 and o < -0.02:
            add("OI×Price regime", o, f"OI {o*100:+.1f}% / px {p*100:+.1f}%", "long", 0.55,
                "long liquidation flushing out — capitulation-bounce long", "price↓ OI↓ = deleveraging")
        elif o > 0.05 and abs(p) < 0.01:
            add("OI×Price regime", o, f"OI {o*100:+.1f}% / px {p*100:+.1f}%", "info", 0.5,
                "leverage building, price stalling — squeeze primed (either way)", "OI↑ px flat")
        elif p > 0.01 and o > 0.03:
            add("OI×Price regime", o, f"OI {o*100:+.1f}% / px {p*100:+.1f}%", "long", 0.45,
                "new longs confirming trend (check funding for fragility)", "price↑ OI↑")

    # --- vol regime (gate/scaler, not alpha) ---
    vr = g("vol_ratio")
    if vr is not None:
        add("Vol regime 7/30", vr, f"{vr:.2f}x", "info", min(abs(vr - 1), 1),
            "vol expanding — trends break, size DOWN" if vr > 1.3 else
            "vol compressed — breakout pending, coil" if vr < 0.7 else "vol normal",
            "use to SIZE, not to pick; weight ∝ 1/vol")

    # --- basis / dispersion ---
    if "basis_bps" in oi and oi["basis_bps"] is not None:
        b = float(oi["basis_bps"])
        add("Perp basis", b, f"{b:+.0f}bps", "short" if b > 30 else "long" if b < -30 else "neutral",
            min(abs(b) / 80, 1), "perp rich vs spot — crowded long" if b > 30 else
            "perp cheap vs spot — crowded short" if b < -30 else "basis flat", "")

    # --- beta / BTC-residual (is this an independent bet?) ---
    bt = g("beta_btc"); cb = g("corr_btc"); rs = g("resid_7")
    if bt is not None:
        add("Beta to BTC", bt, f"{bt:.2f}x  (corr {cb:.2f})" if cb is not None else f"{bt:.2f}x", "info",
            min(abs(bt - 1), 1), ("amplifies BTC — a levered BTC bet, not independent" if (cb or 0) > 0.7
             else "semi-independent of BTC" if (cb or 0) < 0.4 else "moves with BTC"),
            "residualize signals vs BTC or you're just betting beta")
    if rs is not None:
        prs = pof("resid_7")
        d = "long" if (prs or 50) > 66 else "short" if (prs or 50) < 34 else "neutral"
        add("BTC-neutral 7d", rs, f"{rs*100:+.1f}% vs BTC" + (f" ({prs:.0f}%ile)" if prs else ""), d,
            min(abs(rs) / 0.1, 1), "outperforming BTC — real relative strength" if d == "long"
            else "underperforming BTC — relative weakness" if d == "short" else "tracking BTC", "")

    # --- drawdown ---
    dh = g("dist_high_90")
    if dh is not None:
        add("Drawdown from 90d high", dh, f"{dh*100:+.1f}%", "info", min(abs(dh) / 0.5, 1),
            "at the highs — crowded, reversal risk" if dh > -0.03 else
            "deep drawdown — reversion fuel if OI/funding align" if dh < -0.35 else "mid-range", "")

    # --- amihud tradability filter ---
    am = g("amihud"); pam = pof("amihud"); vol = oi.get("vol_usd")
    if pam is not None:
        tradable = pam < 80 and (vol is None or vol > 2e6)
        add("Liquidity (Amihud)", am, (f"${vol/1e6:.0f}M vol · " if vol else "") + f"illiq {pam:.0f}%ile",
            "info", 0.3, "liquid enough for $100 clips" if tradable else
            "ILLIQUID — fills will bleed, treat signals with caution", "filter, not alpha")

    # --- attention inflection (from intel's social) ---
    try:
        from hl import intel
        soc = intel.social_sentiment(coin)
        cur, prev = soc.get("mentions_24h", 0), soc.get("mentions_prev", 0)
        if cur or prev:
            inflect = cur > prev * 1.3 and prev < 40
            add("Attention inflection", cur, f"{prev}→{cur} mentions", "info", min(cur / 40, 1),
                "attention INFLECTING up — narrative arriving" if inflect else
                "loud already — late, fade material" if cur > 40 else "quiet", "inflection, not level")
    except Exception:
        pass

    # --- COMPOSITE = the ONLY score that passed the unbiased backtest ------------
    # The fast 1-7d blend of all factors was tested (scripts/backtest_scores.py) and
    # is DEAD: IC t -1.3, loses net of fees, fails both-halves. What survived was
    # NARROW and SLOW: short-crowded-funding + relative-strength-vs-BTC, held ~10
    # days -> IC t +3.99, Sharpe +1.41 net of fees, POSITIVE in both halves. So the
    # composite IS that tested score, not a hopeful blend. Momentum/reversal are shown
    # as signals above but deliberately NOT in the score (they backtested to noise).
    comp = None
    zf, zr = zof("funding_apr"), zof("resid_7")
    parts = [(-1.0, zf), (1.0, zr)]
    used = [w * z for w, z in parts if z is not None]
    if used:
        raw_c = sum(used) / len(used)
        rv = g("rv_30")
        scale = min(0.6 / rv, 1.5) if rv else 1.0   # vol-scale: weight ~ 1/vol
        # clip the score so one extreme-funding coin (e.g. -600%/yr) can't run away
        # and dominate the book / oversell a giant number.
        comp_v = max(-1.5, min(1.5, raw_c * scale))
        raw_dir = "LONG" if comp_v > 0.25 else "SHORT" if comp_v < -0.25 else "FLAT"
        # LONG-ONLY POLICY (backtested call, L13): the short leg has no edge and makes
        # the book UNSTABLE (long-short Sharpe flips +1.41 -> -0.09 on days of new data;
        # long-only-hedged is +1.34 both halves +, matches the tracker's long +0.87% vs
        # short +0.16%). So a negative score is a "do not go long / avoid", NOT a short.
        traded = raw_dir == "LONG"
        dir_ = "LONG" if traded else ("AVOID" if raw_dir == "SHORT" else "FLAT")
        # expected EDGE grounded in the backfill (avg +0.45% BTC-neutral per pick at
        # avg |score|), NOT raw volatility — so the fee gate is meaningful and honest.
        exp_edge = min(abs(comp_v), 1.5) * EDGE_PER_SCORE      # gross edge, longs only
        net_edge = exp_edge - SLIP_RT
        beats = traded and net_edge > 0
        if traded:
            read = (f"LONG on a ~10-day hold: low funding + relative-strength, the long-only book that "
                    f"backtested (Sharpe {BACKTEST['sharpe']} net, both halves +). Est edge ~{exp_edge*100:.2f}% "
                    f"vs BTC, ~{net_edge*100:+.2f}% after the {SLIP_RT*100:.2f}% fee — "
                    + ("clears it" if net_edge > 0 else "does NOT clear it") + ". Small, slow; hedge with BTC.")
        elif raw_dir == "SHORT":
            read = ("AVOID (not a short). Score is negative — crowded-long funding + relative weakness — but "
                    "the SHORT side has NO measured edge (drags the book negative), so we do not trade it. "
                    "Long-only policy: this is a 'don't own it', not a short.")
        else:
            read = "FLAT — score is mid-pack; no long-only edge either way."
        comp = {"score": round(comp_v, 2), "dir": dir_, "raw_dir": raw_dir, "traded": traded,
                "long_only": True, "vol_scale": round(scale, 2),
                "hold_days": 10, "exp_move_pct": round(exp_edge * 100, 2),
                "net_edge_pct": round(net_edge * 100, 2),
                "fee_floor_pct": round(SLIP_RT * 100, 2), "beats_fees": beats,
                "backtest": dict(BACKTEST), "read": read}
    sig.sort(key=lambda x: (x["dir"] == "neutral" or x["dir"] == "info", -x["strength"]))
    # F&G as live CONTEXT only — it was tested (scripts/backtest_scores.py fng_overlay)
    # and did NOT improve the score in our data, so it is shown, not scored.
    mood = None
    try:
        from hl import fng
        mood = fng.live()
    except Exception:
        pass
    return {"coin": coin, "signals": sig, "composite": comp, "n_universe": u["n"], "mood": mood}
