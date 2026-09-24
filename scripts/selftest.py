"""Self-test for the simulator: every automatable checklist item in
docs/AGENT_V2_BUILD_SPEC_2026-09-16.md that can run without the model.

    python scripts/selftest.py            # all
    python scripts/selftest.py X R        # only groups X and R

Each test is a function returning (ok: bool, detail: str). The table at the end is the
proof; exit code 1 if anything fails. Tests use small synthetic data where the real
data would make the test slow or non-deterministic, and the real cross-sectional cache
where the item is about real numbers.
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sim.engine import Book, Order, Trade, FEE_BPS          # noqa: E402
from sim.memory import Memory                                # noqa: E402
from sim.agents import regime_label                          # noqa: E402
from sim.investigator import InvestigatorAgent, chain_point  # noqa: E402
from sim.risk import RiskHat, STOP_MIN, STOP_MAX             # noqa: E402
from sim.tools import crowd_label                            # noqa: E402

DAY = 86_400_000
TESTS = []


def test(id_, group):
    def deco(fn):
        TESTS.append((id_, group, fn.__doc__ or fn.__name__, fn))
        return fn
    return deco


# ---------------------------------------------------------------- synthetic market
class FakeData:
    """A tiny AsOf look-alike: 3 coins, N days, deterministic prices, optional funding."""
    def __init__(self, n=12, funding=None):
        days = [1_700_000_000_000 + i * DAY for i in range(n)]
        base = {"AAA": 100.0, "BBB": 50.0, "BTC": 1000.0}
        rows = {c: [base[c] * (1 + 0.01 * i) for i in range(n)] for c in base}
        self.close = pd.DataFrame(rows, index=days)
        self.high = self.close * 1.02
        self.low = self.close * 0.98
        self.days = days
        self.universe = list(base)
        self.spread = pd.Series({c: 10.0 for c in base})
        self.funding = pd.DataFrame(funding if funding is not None else 0.0, index=days, columns=list(base))
        self.pos = {}

    def price(self, t, coin):
        return float(self.close.at[t, coin]) if t in self.close.index else None

    def day_range(self, t, coin):
        return float(self.high.at[t, coin]), float(self.low.at[t, coin])

    def funding_day(self, t):
        return self.funding.loc[t] if t in self.funding.index else None

    def closes(self, t, n, coins):
        c = self.close[self.close.index <= t].tail(n)
        return c[coins]

    def tradable(self, t):
        return self.universe

    def set_path(self, coin, highs, lows, closes):
        """Overwrite a coin's path from day 1 onward (day 0 = entry)."""
        for i, (h, l, c) in enumerate(zip(highs, lows, closes), start=1):
            self.high.iloc[i, self.high.columns.get_loc(coin)] = h
            self.low.iloc[i, self.low.columns.get_loc(coin)] = l
            self.close.iloc[i, self.close.columns.get_loc(coin)] = c


def run_book(data, order, days_to_settle=8):
    b = Book(data, trade_size=100.0)
    t0 = data.days[0]
    b.settle(t0)
    p = b.open(t0, order)
    closed = []
    for t in data.days[1:1 + days_to_settle]:
        closed += b.settle(t)
    return b, p, closed


# ---------------------------------------------------------------- X: engine
@test("X3", "X")
def x3():
    """fee = notional * (4.5 bps + half spread) / 1e4"""
    d = FakeData(); b = Book(d, trade_size=100.0)
    want = 100.0 * (FEE_BPS + 10.0 / 2) / 1e4
    return abs(b._fee("AAA", 100.0) - want) < 1e-9, f"fee {b._fee('AAA', 100.0):.4f} want {want:.4f}"


@test("X4", "X")
def x4():
    """stop checked on the low before target on the high on the same day (long)"""
    d = FakeData(); d.set_path("AAA", highs=[120] * 8, lows=[90] * 8, closes=[100] * 8)
    b, p, closed = run_book(d, Order("AAA", "long", 0.05, 0.10, 7))
    return bool(closed) and closed[0].exit_reason == "stop", f"exit {closed[0].exit_reason if closed else None}"


@test("X5", "X")
def x5():
    """the entry day does not settle the new position"""
    d = FakeData(); d.set_path("AAA", highs=[100] * 8, lows=[100] * 8, closes=[100] * 8)
    b = Book(d, trade_size=100.0); t0 = d.days[0]
    b.open(t0, Order("AAA", "long", 0.05, 0.10, 7)); b.settle(t0)
    return len(b.positions["AAA"].path) == 0 and "AAA" in b.positions, "path empty on entry day"


@test("X6", "X")
def x6():
    """funding sign: a long pays positive funding, a short receives it"""
    d = FakeData(funding=0.001); d.set_path("AAA", highs=[100] * 8, lows=[100] * 8, closes=[100] * 8)
    bl, pl, _ = run_book(d, Order("AAA", "long", 0.5, 0.5, 30), 3)
    bs, ps, _ = run_book(d, Order("AAA", "short", 0.5, 0.5, 30), 3)
    return pl.funding_paid > 0 and ps.funding_paid < 0 and abs(pl.funding_paid + ps.funding_paid) < 1e-9, f"long {pl.funding_paid:.3f} short {ps.funding_paid:.3f}"


@test("X8", "X")
def x8():
    """MFE/MAE per side from the daily highs/lows"""
    d = FakeData(); d.set_path("AAA", highs=[110, 115, 105] + [100] * 5, lows=[97, 98, 96] + [100] * 5, closes=[100] * 8)
    b, p, closed = run_book(d, Order("AAA", "short", 0.5, 0.5, 3), 3)
    tr = closed[0]
    return abs(tr.mfe_bps - 400) < 1 and abs(tr.mae_bps + 1500) < 1, f"short mfe {tr.mfe_bps:.0f} mae {tr.mae_bps:.0f}"


@test("X9", "X")
def x9():
    """counterfactual grid: first touch wins; cost subtracted once"""
    d = FakeData(); d.set_path("AAA", highs=[103, 113, 120] + [100] * 5, lows=[96, 95, 90] + [100] * 5, closes=[100, 110, 100] + [100] * 5)
    b, p, closed = run_book(d, Order("AAA", "long", 0.5, 0.5, 3), 3)
    cf = json.loads(closed[0].counterfactuals)
    cost = (b._fee("AAA", 100) * 2) / 100 * 1e4
    return abs(cf["long:s3:t6"] - (-300 - cost)) < 1 and abs(cf["long:s9:t12"] - (1200 - cost)) < 1, f"{cf['long:s3:t6']:.0f} / {cf['long:s9:t12']:.0f} (cost {cost:.0f})"


@test("X10", "X")
def x10():
    """path_pct is in the trade's favour: a short on a falling coin shows positive numbers"""
    d = FakeData(); d.set_path("AAA", highs=[100] * 8, lows=[90] * 8, closes=[98, 96, 95] + [95] * 5)
    b, p, closed = run_book(d, Order("AAA", "short", 0.5, 0.5, 3), 3)
    path = json.loads(closed[0].path_pct)
    return path[:3] == [2.0, 4.0, 5.0], f"path {path[:3]}"


@test("X11", "X")
def x11():
    """a falsifier on the wrong side is ignored at open"""
    d = FakeData(); b = Book(d, trade_size=100.0)
    p = b.open(d.days[0], Order("AAA", "long", 0.05, 0.1, 7, falsifier_day=2, falsifier_pct=+3.0))
    q = b.open(d.days[0], Order("BBB", "short", 0.05, 0.1, 7, falsifier_day=2, falsifier_pct=+3.0))
    return p.falsifier_day == 0 and q.falsifier_day == 2, f"long {p.falsifier_day} short {q.falsifier_day}"


@test("X12", "X")
def x12():
    """falsifier closes the trade at that day's close when crossed (before the stop would)"""
    d = FakeData(); d.set_path("AAA", highs=[101, 105] + [100] * 6, lows=[99, 100] + [100] * 6, closes=[100, 104] + [100] * 6)
    b, p, closed = run_book(d, Order("AAA", "short", 0.06, 0.12, 7, falsifier_day=2, falsifier_pct=3.0), 3)
    return bool(closed) and closed[0].exit_reason == "falsifier" and closed[0].days_held == 2, f"{closed[0].exit_reason if closed else None}"


@test("X13", "X")
def x13():
    """size_mult shrinks notional and is capped at 1"""
    d = FakeData(); b = Book(d, trade_size=100.0)
    p = b.open(d.days[0], Order("AAA", "long", 0.05, 0.1, 7, size_mult=0.5))
    q = b.open(d.days[0], Order("BBB", "long", 0.05, 0.1, 7, size_mult=1.5))
    return p.notional == 50.0 and q.notional == 100.0, f"{p.notional} / {q.notional}"


@test("X14", "X")
def x14():
    """close_all closes at the close with reason 'end'"""
    d = FakeData(); b = Book(d, trade_size=100.0)
    b.open(d.days[0], Order("AAA", "long", 0.5, 0.5, 30)); b.settle(d.days[1]); b.close_all(d.days[1])
    return not b.positions and b.trades[0].exit_reason == "end" and b.trades[0].exit_px == d.price(d.days[1], "AAA"), "ok"


@test("X15", "X")
def x15():
    """summary Sharpe equals the recomputation from the equity curve"""
    d = FakeData(); b = Book(d, trade_size=100.0)
    b.open(d.days[0], Order("AAA", "long", 0.5, 0.5, 30))
    for t in d.days[1:]:
        b.settle(t)
    s = b.summary()
    eq = pd.Series({t: e for t, e in b.equity_curve}); dr = eq.pct_change().dropna()
    want = dr.mean() / dr.std() * math.sqrt(365) if dr.std() > 0 else float("nan")
    return (math.isnan(want) and math.isnan(s["sharpe"])) or abs(s["sharpe"] - want) < 1e-9, f"{s['sharpe']:.3f} vs {want:.3f}"


# ---------------------------------------------------------------- X: memory
def _mem():
    p = Path(tempfile.mkdtemp()) / "m.db"
    return Memory(p, "t", "run", seed=1)


def _learn(m, closed_ts, side="long", excess=100.0, conf=0.6):
    m.learn(closed_ts=closed_ts, opened_ts=closed_ts - 3 * DAY, coin="AAA", side=side, setup=f"s:{side}", regime="CHOP",
            features={"f1": 1.0, "f2": 2.0}, thesis="{}", confidence=conf, net_bps=excess, excess_bps=excess,
            mfe_bps=150, mae_bps=-50, exit_reason="target", days_held=3, counterfactuals="{}", lesson="lesson word xyzzy")


@test("X17", "X")
def x17():
    """evidence is time-locked: a close after t is not counted at t"""
    m = _mem(); t = 1_700_000_000_000
    _learn(m, t); _learn(m, t + 5 * DAY)
    e0, e1 = m.evidence("s:long", None, t), m.evidence("s:long", None, t + 5 * DAY)
    return e0["n"] == 1 and e1["n"] == 2, f"n at t {e0['n']}, later {e1['n']}"


@test("X18", "X")
def x18():
    """similar() excludes experiences closed after t"""
    m = _mem(); t = 1_700_000_000_000
    for i in range(6):
        _learn(m, t + (5 + i) * DAY)
    s0 = m.similar({"f1": 1.0, "f2": 2.0}, t, k=5)
    s1 = m.similar({"f1": 1.0, "f2": 2.0}, t + 12 * DAY, k=5)
    return s0["n"] == 0 and s1["n"] == 5, f"{s0['n']} then {s1['n']}"


@test("X19", "X")
def x19():
    """Thompson sampling: one loss does not close a setup (still drawn positive 25-60% of the time); six consistent losses nearly do"""
    m = _mem(); t = 1_700_000_000_000
    _learn(m, t, side="long", excess=-200.0)
    one = sum(m.sample("s:long", None, t + 2 * DAY) > 0 for _ in range(500))
    for i in range(1, 6):
        _learn(m, t + i * DAY, side="long", excess=-200.0)
    six = sum(m.sample("s:long", None, t + 10 * DAY) > 0 for _ in range(500))
    return 125 <= one <= 300 and six < one, f"after 1 loss positive {one}/500; after 6 losses {six}/500 (probation trades keep it alive)"


@test("X21", "X")
def x21():
    """calibration buckets count wins per stated-confidence bucket"""
    m = _mem(); t = 1_700_000_000_000
    for i, (c, ex) in enumerate([(0.6, 100), (0.6, -100), (0.6, 100), (0.9, -50)]):
        _learn(m, t + i * DAY, conf=c, excess=ex)
    cal = {b["bucket"]: b for b in m.calibration(t + 10 * DAY)}
    return cal["0.55-0.70"]["n"] == 3 and abs(cal["0.55-0.70"]["win"] - 2 / 3) < 1e-9 and cal["0.85-1.00"]["win"] == 0.0, str(cal)


@test("X22", "X")
def x22():
    """notes are time-locked"""
    m = _mem(); t = 1_700_000_000_000
    m.write_note(t + DAY, "market_view", "future view", "t")
    return len(m.notes(t, kind="market_view", k=5)) == 0 and len(m.notes(t + 2 * DAY, kind="market_view", k=5)) == 1, "ok"


@test("X23", "X")
def x23():
    """regime label thresholds at +-3% over 30 days"""
    d = FakeData(n=40)
    d.close["BTC"] = [1000.0] * 10 + [1000.0 * (1 + 0.04 * i / 29) for i in range(30)]
    up = regime_label(d, d.days[-1])
    d.close["BTC"] = [1000.0] * 40
    flat = regime_label(d, d.days[-1])
    return up == "UPTREND" and flat == "CHOP", f"{up} / {flat}"


@test("X31", "X")
def x31():
    """falsifier/checkpoint units: move fraction -> pct percent; legacy pct passes; junk -> None"""
    a = chain_point({"day": 2, "move": -0.05}); b = chain_point({"day": 4, "pct": 3}); c = chain_point("x"); d = chain_point({"day": "z"})
    return a == {"day": 2, "pct": -5.0} and b == {"day": 4, "pct": 3.0} and c is None and d is None, f"{a} {b} {c} {d}"


@test("X35", "X")
def x35():
    """lesson verdicts: TRIGGERED / not triggered / closed before judged"""
    ag = InvestigatorAgent.__new__(InvestigatorAgent)
    obs = type("O", (), {"regime": "CHOP"})()
    def tr(side, path, chain):
        return Trade(1, "AAA", side, 0, 3 * DAY, 100, 100, 100, 0, 0, 0, -1.0, "stop", json.dumps(chain), "x", len(path),
                     0, 0, 0, "{}", json.dumps(path))
    s1 = ag.lesson(obs, tr("short", [-1.46, -4.29], {"falsifier": {"day": 2, "pct": 3}}))
    s2 = ag.lesson(obs, tr("short", [5.41, 12.92], {"falsifier": {"day": 2, "pct": 4}}))
    s3 = ag.lesson(obs, tr("long", [-4.85], {"falsifier": {"day": 2, "pct": -3}}))
    ok = "TRIGGERED" in s1 and "not triggered" in s2 and "closed on day 1 before" in s3
    return ok, f"{s1[-60:]} | {s2[-40:]} | {s3[-50:]}"


@test("X42", "X")
def x42():
    """crowd label text follows the sign, both extremes and mild cases"""
    a, b, c, d, e = crowd_label(0.003), crowd_label(-0.003), crowd_label(0.0005), crowd_label(-0.0005), crowd_label(0.0)
    ok = "LONGS CROWDED" in a and "DOWN" in a and "SHORTS CROWDED" in b and "UP" in b and "mild" in c and "mild" in d and "flat" in e
    return ok, f"{a[:30]} | {b[:30]}"


# ---------------------------------------------------------------- D: cross-sectional layer (real cache)
def _x():
    from sim.xsec import xsec
    return xsec()


@test("D1", "D")
def d1():
    """beta_btc_raw equals numpy OLS on the last 60 days for BTC-like coins"""
    from sim.data import daily_ohlc
    x = _x(); close = daily_ohlc()["close"]; r = np.log(close).diff().where(lambda v: v.abs() < 1.5)
    bad = []
    for coin in ("ETH", "SOL", "DOGE"):
        pair = pd.concat([r[coin], r["BTC"]], axis=1).dropna().tail(60)
        want = np.polyfit(pair.iloc[:, 1], pair.iloc[:, 0], 1)[0]
        got = float(x["frames"]["beta_btc_raw"][coin].dropna().iloc[-1])
        if abs(got - want) > 0.02:
            bad.append(f"{coin} got {got:.3f} want {want:.3f}")
    return not bad, "; ".join(bad) or "ETH/SOL/DOGE within 0.02"


@test("D2", "D")
def d2():
    """Vasicek: coins with larger standard error are pulled closer to the cross-sectional median"""
    x = _x(); f = x["frames"]
    raw, se, shr = f["beta_btc_raw"].iloc[-1], f["beta_btc_se"].iloc[-1], f["beta_btc"].iloc[-1]
    ok = raw.notna() & se.notna() & shr.notna()
    med = raw[ok].median()
    pull = ((raw - shr).abs() / (raw - med).abs().replace(0, np.nan))[ok].dropna()
    hi_se = se[ok] > se[ok].median()
    return pull[hi_se].median() > pull[~hi_se].median(), f"pull high-SE {pull[hi_se].median():.2f} vs low-SE {pull[~hi_se].median():.2f}"


@test("D6", "D")
def d6():
    """resid_r_1d uses yesterday's beta (no look-ahead)"""
    from sim.data import daily_ohlc
    x = _x(); f = x["frames"]; close = daily_ohlc()["close"]; r = np.log(close).diff()
    coin = "ETH"; d = f["resid_r_1d"].index[-1]; i = f["resid_r_1d"].index.get_loc(d)
    want = r.at[d, coin] - f["beta_btc"][coin].iloc[i - 1] * r.at[d, "BTC"]
    got = f["resid_r_1d"].at[d, coin]
    return abs(float(got) - float(want)) < 1e-5, f"got {got:.6f} want {want:.6f}"


@test("D10", "D")
def d10():
    """corr_btc_30d equals numpy on the last 30 days"""
    from sim.data import daily_ohlc
    x = _x(); close = daily_ohlc()["close"]; r = np.log(close).diff().where(lambda v: v.abs() < 1.5)
    pair = pd.concat([r["ETH"], r["BTC"]], axis=1).dropna().tail(30)
    want = float(np.corrcoef(pair.iloc[:, 0], pair.iloc[:, 1])[0, 1])
    got = float(x["frames"]["corr_btc_30d"]["ETH"].dropna().iloc[-1])
    return abs(got - want) < 0.02, f"got {got:.3f} want {want:.3f}"


@test("D12", "D")
def d12():
    """stress-day correlation is higher than normal-day correlation"""
    u = _x()["universe"].dropna(subset=["stress_mean_corr", "mean_corr_60d"]).tail(1)
    return float(u["stress_mean_corr"].iloc[0]) > float(u["mean_corr_60d"].iloc[0]), f"stress {u['stress_mean_corr'].iloc[0]:.2f} vs normal {u['mean_corr_60d'].iloc[0]:.2f}"


@test("D14", "D")
def d14():
    """effective number of independent assets is small (2-10) on the latest week"""
    u = _x()["universe"].dropna(subset=["neff"]).tail(1)
    v = float(u["neff"].iloc[0])
    return 1.5 <= v <= 10, f"neff {v:.2f}"


@test("D15", "D")
def d15():
    """clusters exist for most coins, no cluster holds half the universe, stability is reported"""
    x = _x(); cl = x["frames"]["cluster_id"].iloc[-1].dropna()
    st = x["cluster_stability"]
    return len(cl) > 100 and 4 <= cl.nunique() <= 8 and max(cl.value_counts()) < 0.5 * len(cl) and len(st) > 5, f"{len(cl)} coins in {cl.nunique()} clusters; {len(st)} stability points, last {list(st.values())[-1]:.2f}"


@test("D46", "D")
def d46():
    """computed_with_data_through equals the last day in the closes"""
    from sim.data import daily_ohlc
    x = _x(); last = int(daily_ohlc()["close"].index[-1])
    return x["computed_with_data_through"] == last, f"{x['computed_with_data_through']} vs {last}"


@test("A27x", "D")
def a27x():
    """shuffle test: the layer at day d is identical whether or not the 30 days after d exist"""
    from sim.data import daily_ohlc
    from sim.xsec import build_xsec
    close = daily_ohlc()["close"]
    full = _x(); cut = build_xsec(close.iloc[:-30])
    d = cut["frames"]["beta_btc"].index[-1]
    bad = []
    for k in ("beta_btc_raw", "beta_btc", "resid_r_1d", "idio_daily_move_pct", "corr_btc_30d"):
        a = full["frames"][k].loc[d].dropna(); b = cut["frames"][k].loc[d].dropna()
        common = a.index.intersection(b.index)
        diff = float((a[common] - b[common]).abs().max()) if len(common) else 0.0
        if diff > 1e-4:
            bad.append(f"{k} max diff {diff:.2e}")
    return not bad, "; ".join(bad) or "identical on all five frames"


# ---------------------------------------------------------------- R: risk hat
def _risk(idio=5.0, cluster=None, funding=None, beta=1.0, beta_stress=1.4, r2=0.3):
    d = FakeData(n=80, funding=funding)
    days = d.days
    frames = {k: pd.DataFrame(v, index=days, columns=d.universe) for k, v in {
        "idio_daily_move_pct": idio, "beta_btc": beta, "beta_stress": beta_stress, "r2_btc": r2, "idio_vol_30d": idio / 100 * math.sqrt(365)}.items()}
    frames["cluster_id"] = pd.DataFrame(cluster if cluster is not None else np.nan, index=days, columns=d.universe)
    x = {"frames": frames, "universe": pd.DataFrame({"common_share": 0.4}, index=days)}
    b = Book(d, trade_size=100.0)
    for t in days[:5]:
        b.settle(t)
    return d, b, RiskHat(d, None, b, x)


def _review(rh, orders, conf=None, t=None, pending=None):
    t = t or rh.data.days[4]
    conf = conf or {o.coin: 0.65 for o in orders}
    tab = pd.DataFrame(index=[f"C{i}" for i in range(3)])
    labels = {"AAA": "C0", "BBB": "C1", "BTC": "C2"}
    return rh.review(orders, t, conf, tab, labels, "s", rh.book.equity(t), pending=pending)


@test("R2", "R")
def r2():
    """a stop of 0.5 daily moves is bounced with the allowed band; 2.0 moves passes"""
    d, b, rh = _risk(idio=5.0)
    kept, v, bounces = _review(rh, [Order("AAA", "long", 0.025, 0.15, 10)])
    kept2, v2, b2 = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)])
    ok = not kept and bounces and abs(bounces[0]["suggested"]["stop_pct"] - 0.0765) < 1e-9 and kept2 and not b2
    return ok, f"bounced: {bounces[0]['violations'][0] if bounces else None}; second accepted={bool(kept2)}"


@test("R3", "R")
def r3():
    """falsifier on the wrong side or outside the stop is bounced with a fix"""
    d, b, rh = _risk(idio=5.0)
    kept, v, bounces = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10, falsifier_day=2, falsifier_pct=+4.0)])
    kept2, v2, b2 = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10, falsifier_day=2, falsifier_pct=-12.0)])
    ok = not kept and bounces[0]["suggested"]["falsifier_pct"] < 0 and not kept2 and abs(b2[0]["suggested"]["falsifier_pct"]) < 10
    return ok, f"{bounces[0]['violations']} | {b2[0]['violations']}"


@test("R4", "R")
def r4():
    """target below 2 daily moves or below 1.5x stop is bounced"""
    d, b, rh = _risk(idio=5.0)
    kept, v, bounces = _review(rh, [Order("AAA", "long", 0.10, 0.08, 10)])
    return not kept and abs(bounces[0]["suggested"]["target_pct"] - 0.153) < 1e-9, str(bounces[0]["violations"])


@test("R5", "R")
def r5():
    """hold too short for the target at that vol is SET by the desk (arithmetic), not bounced"""
    d, b, rh = _risk(idio=5.0)
    kept, v, bounces = _review(rh, [Order("AAA", "long", 0.10, 0.15, 2)])
    return bool(kept) and kept[0].hold_days == 9 and "hold_set_by_desk" in v[0]["checks"], str(v[0]["checks"].get("hold_set_by_desk"))


@test("R6", "R")
def r6():
    """size: p=0.5 rejected (no edge); p=0.65 gives kelly x vol scale, never > 1"""
    d, b, rh = _risk(idio=5.0)
    kept, v, _ = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)], conf={"AAA": 0.5})
    kept2, v2, _ = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)], conf={"AAA": 0.65})
    k = v2[0]["checks"]["kelly_scale"]; vs = v2[0]["checks"]["vol_scale"]
    want_k = min(max((2 * 0.65 - 1) * (0.10 / 0.15) * 4, 0), 1)
    want_vs = min(max(12.0 / (5.0 * math.sqrt(365)), 0.25), 1.0)
    ok = not kept and v[0]["action"] == "reject" and kept2 and abs(k - want_k) < 1e-6 and abs(vs - want_vs) < 1e-6 and 0 < kept2[0].size_mult <= 1
    return ok, f"p=0.5 -> {v[0]['action']}; p=0.65 -> kelly {k} vol {vs} size_mult {kept2[0].size_mult if kept2 else None}"


@test("R7", "R")
def r7():
    """cluster cap: a third order in the same cluster is rejected"""
    d, b, rh = _risk(idio=5.0, cluster=2.0)
    o1, o2, o3 = (Order(c, "long", 0.10, 0.15, 10) for c in ("AAA", "BBB", "BTC"))
    kept, v, _ = _review(rh, [o1, o2, o3])
    return len(kept) == 2 and v[2]["action"] == "reject" and "cluster" in v[2]["violations"][0], f"{[x['action'] for x in v]}"


@test("R8", "R")
def r8():
    """stress-margin: a huge order that would lose >10% of equity in a 3-sigma BTC move is rejected"""
    d, b, rh = _risk(idio=5.0, beta_stress=1.4)
    d.close["BTC"] = d.close["BTC"] * (1 + 0.05 * np.sin(np.arange(len(d.days))))     # give BTC a real sigma
    b.trade_size = 60_000.0
    kept, v, _ = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)], t=d.days[70])    # 70 days of BTC history
    return not kept and any("3-sigma" in s for s in v[0]["violations"]), str(v[0]["violations"])


@test("R9", "R")
def r9():
    """funding rule: a long paying top-quintile funding needs p_final >= 0.60"""
    n = 80; days = [1_700_000_000_000 + i * DAY for i in range(n)]
    d, b, rh = _risk(idio=5.0)
    cols = [f"Z{i}" for i in range(24)] + ["AAA", "BBB", "BTC"]
    f = pd.DataFrame({c: 0.0001 * i for i, c in enumerate(cols)}, index=days)
    f["AAA"] = 0.01                                # top of the cross-section
    rh.data.funding = f
    kept, v, _ = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)], conf={"AAA": 0.55})
    kept2, v2, _ = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)], conf={"AAA": 0.70})
    return not kept and kept2 and v[0]["checks"]["funding_quintile"] == 4, f"{v[0]['violations']} | second accepted={bool(kept2)}"


@test("R12", "R")
def r12():
    """circuit breakers: drawdown > 15% or day loss > 3% blocks all new trades"""
    d, b, rh = _risk(idio=5.0)
    b.equity_curve = [(d.days[i], 10_000 - 200 * i) for i in range(10)]
    kept, v, _ = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)], t=d.days[9])
    return not kept and v[0]["action"] == "reject" and "drawdown" in v[0]["violations"][0], str(v[0]["violations"])


@test("R11", "R")
def r11():
    """CVaR brake: a worst-1% day halves sizes for 5 days"""
    d, b, rh = _risk(idio=5.0)
    curve = [10_000 * (1 + 0.001 * math.sin(i)) for i in range(120)]
    curve[-1] = curve[-2] * 0.90
    b.equity_curve = [(1_700_000_000_000 + i * DAY, e) for i, e in enumerate(curve)]
    t = 1_700_000_000_000 + 119 * DAY
    _review(rh, [], t=t)                                       # arms the brake (the day loss itself blocks today)
    b.equity_curve += [(t + DAY, curve[-1]), (t + 2 * DAY, curve[-1])]   # two flat days later: brake still on
    kept, v, _ = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)], conf={"AAA": 0.9}, t=t + 2 * DAY)
    return bool(kept) and v[0]["checks"]["cvar_brake"] is True and kept[0].size_mult <= 0.5, f"brake_until set={rh.brake_until is not None}, size_mult {kept[0].size_mult if kept else None}"


@test("R18", "R")
def r18():
    """pending orders count toward cluster caps in the second review round"""
    d, b, rh = _risk(idio=5.0, cluster=1.0)
    o1, o2 = Order("AAA", "long", 0.10, 0.15, 10), Order("BBB", "long", 0.10, 0.15, 10)
    kept, v, _ = _review(rh, [o1, o2])
    kept2, v2, _ = _review(rh, [Order("BTC", "long", 0.10, 0.15, 10)], pending=kept)
    return len(kept) == 2 and not kept2 and v2[0]["action"] == "reject", f"{v2[0]['violations'] if v2 else None}"


@test("R18b", "R")
def r18b():
    """bounce loop end to end (model stubbed): a bad replan is desk-fixed and accepted, not dropped"""
    d, b, rh = _risk(idio=10.0)
    ag = InvestigatorAgent.__new__(InvestigatorAgent)
    ag.risk = rh; ag.setup = "s"; ag._conf = {"AAA": 0.65}; ag.last_risk = {}
    ag._chat = lambda msgs, thinking=False, max_tokens=0: (
        '{"orders":[{"label":"C0","action":"replan","stop_pct":0.12,"target_pct":0.24,"hold_days":6,"falsifier":{"day":2,"move":-0.05}}]}')
    o = Order("AAA", "long", 0.15, 0.30, 10, "{}", "x", falsifier_day=2, falsifier_pct=+5.0)   # only the falsifier is wrong
    obs = type("O", (), {"t": d.days[4]})()
    tab = pd.DataFrame(index=["C0", "C1", "C2"])
    kept = ag._risk_pass([o], obs, tab, {"AAA": "C0", "BBB": "C1", "BTC": "C2"})
    log = ag.last_risk
    ok = (len(kept) == 1 and log["round1"][0]["action"] == "bounce" and log["round2"][0]["action"] == "bounce"
          and log.get("round3_desk_fixed") and log["round3_desk_fixed"][0]["action"] == "accept"
          and kept[0].falsifier_pct < 0 and 0.15 <= kept[0].stop_pct <= 0.30 and not log["dropped_after_replan"])
    return ok, f"r1 {log['round1'][0]['action']} r2 {log['round2'][0]['action']} r3 {log.get('round3_desk_fixed', [{}])[0].get('action')} stop {kept[0].stop_pct if kept else None} fals {kept[0].falsifier_pct if kept else None}"


@test("R2b", "R")
def r2b():
    """boundary: a stop the desk itself suggested passes the desk's own rule (rounding must never bounce it)"""
    bad = []
    for dm in (2.4224, 2.45, 3.3333, 7.777, 10.13, 0.9):
        d, b, rh = _risk(idio=dm)
        kept, v, bounces = _review(rh, [Order("AAA", "long", 0.5, 0.9, 14)])          # far too wide -> bounce
        fix = bounces[0]["suggested"]
        o2 = Order("AAA", "long", fix["stop_pct"], fix.get("target_pct", 0.9), fix.get("hold_days", 14))
        kept2, v2, b2 = _review(rh, [o2])
        if not kept2:
            bad.append(f"dm {dm}: {v2[0]['violations']}")
    return not bad, "; ".join(bad) or "desk-suggested stops accepted at 6 volatilities"


@test("R3b", "R")
def r3b():
    """a coin with no volatility data is rejected, never sized off a default"""
    d, b, rh = _risk(idio=5.0)
    rh.x["frames"]["idio_daily_move_pct"]["AAA"] = np.nan
    kept, v, _ = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)])
    return not kept and v[0]["action"] == "reject" and "no volatility" in v[0]["violations"][0], str(v[0]["violations"])


def _agent_with(rh, chat_answer):
    ag = InvestigatorAgent.__new__(InvestigatorAgent)
    ag.risk = rh; ag.setup = "s"; ag._conf = {"AAA": 0.65, "BBB": 0.6}; ag.last_risk = {}
    ag._chat = lambda msgs, thinking=False, max_tokens=0: chat_answer
    return ag


@test("R18c", "R")
def r18c():
    """empty replan answer: the desk's numbers are applied and the order still opens"""
    d, b, rh = _risk(idio=10.0)
    ag = _agent_with(rh, "")
    o = Order("AAA", "long", 0.05, 0.30, 10, "{}", "x")                       # stop too tight
    kept = ag._risk_pass([o], type("O", (), {"t": d.days[4]})(), pd.DataFrame(index=["C0", "C1", "C2"]), {"AAA": "C0", "BBB": "C1", "BTC": "C2"})
    log = ag.last_risk
    return len(kept) == 1 and log.get("unanswered_desk_fixed") == ["C0"] and 0.15 <= kept[0].stop_pct <= 0.30, f"stop {kept[0].stop_pct if kept else None} log {log.get('unanswered_desk_fixed')}"


@test("R18d", "R")
def r18d():
    """garbage replan answer (not JSON, wrong labels): desk numbers applied, nothing crashes"""
    d, b, rh = _risk(idio=10.0)
    ag = _agent_with(rh, 'sure! here is my plan: {"orders":[{"label":"C99","action":"replan","stop_pct":"abc"}]} and more text')
    o = Order("AAA", "long", 0.05, 0.30, 10, "{}", "x")
    kept = ag._risk_pass([o], type("O", (), {"t": d.days[4]})(), pd.DataFrame(index=["C0", "C1", "C2"]), {"AAA": "C0", "BBB": "C1", "BTC": "C2"})
    return len(kept) == 1 and ag.last_risk.get("unanswered_desk_fixed") == ["C0"], f"kept {len(kept)}"


@test("R18e", "R")
def r18e():
    """replan that changes an unflagged field to a bad value is desk-fixed, and the flagged fix is kept"""
    d, b, rh = _risk(idio=10.0)
    ag = _agent_with(rh, '{"orders":[{"label":"C0","action":"replan","stop_pct":0.02,"hold_days":10}]}')
    o = Order("AAA", "long", 0.20, 0.45, 2, "{}", "x")                        # only hold is wrong
    kept = ag._risk_pass([o], type("O", (), {"t": d.days[4]})(), pd.DataFrame(index=["C0", "C1", "C2"]), {"AAA": "C0", "BBB": "C1", "BTC": "C2"})
    return len(kept) == 1 and kept[0].hold_days >= 10 and 0.15 <= kept[0].stop_pct <= 0.30, f"stop {kept[0].stop_pct if kept else None} hold {kept[0].hold_days if kept else None}"


@test("P1b", "X")
def p1b():
    """positioning label follows the long share and its 7-day change"""
    from sim.tools import positioning_label
    a, b, c, d = positioning_label(0.70, 0.08), positioning_label(0.35, -0.06), positioning_label(0.52, 0.01), positioning_label(0.66, None)
    ok = "LONGS CROWDED" in a and "piling" in a and "SHORTS CROWDED" in b and "leaving" in b and "balanced" in c and d.endswith("LONGS CROWDED")
    return ok, f"{a} | {b}"


# ---------------------------------------------------------------- audit fixes A-K
@test("A-eng", "X")
def a_eng():
    """per-trade bps uses each trade's own notional (size_mult), not the fixed trade size"""
    d = FakeData(); b = Book(d, trade_size=100.0)
    b.open(d.days[0], Order("AAA", "long", 0.5, 0.5, 30, size_mult=0.5)); b.settle(d.days[1]); b.close_all(d.days[1])
    s = b.summary(); tr = b.trades[0]
    return abs(s["avg_net_per_trade_bps"] - tr.net_pnl / tr.notional * 1e4) < 1e-9 and tr.notional == 50.0, f"{s['avg_net_per_trade_bps']:.1f} bps on ${tr.notional}"


@test("B-mem", "X")
def b_mem():
    """recall() survives punctuation and FTS keywords in the query"""
    m = _mem(); t = 1_700_000_000_000; _learn(m, t)
    try:
        r1 = m.recall(t + DAY, 'short-squeeze OR "xyzzy" NOT (crash)')
        r2 = m.recall(t + DAY, "xyzzy")
    except Exception as e:
        return False, f"EXC {e}"
    return len(r2) == 1, f"punctuated query ok ({len(r1)} rows), plain word found {len(r2)}"


@test("C-mem", "X")
def c_mem():
    """feature rows are parsed once per (as_of, count): repeated similar() calls hit the cache"""
    m = _mem(); t = 1_700_000_000_000
    for i in range(6):
        _learn(m, t + i * DAY)
    m.similar({"f1": 1.0, "f2": 2.0}, t + 10 * DAY); key1 = m._feat_cache[0]
    m.similar({"f1": 1.5, "f2": 2.0}, t + 10 * DAY); key2 = m._feat_cache[0]
    _learn(m, t + 11 * DAY); m.similar({"f1": 1.0, "f2": 2.0}, t + 12 * DAY); key3 = m._feat_cache[0]
    return key1 == key2 == (t + 10 * DAY, 6) and key3 == (t + 12 * DAY, 7), f"{key1} {key2} {key3}"


@test("E-inv", "X")
def e_inv():
    """garbage model answers never crash order parsing: list JSON, string orders, junk numbers, duplicate coins"""
    ok1 = InvestigatorAgent._json("[1,2,3]") is None and InvestigatorAgent._json("no json here") is None
    n = InvestigatorAgent._num
    ok2 = n("abc", 0.06, 0.005, 0.6) == 0.06 and n("nan", 0.06, 0.005, 0.6) == 0.06 and n(-5, 0.06, 0.005, 0.6) == 0.005 and n("0.2", 0.06, 0.005, 0.6) == 0.2
    return ok1 and ok2, f"json-guard {ok1} num-guard {ok2}"


@test("H-srv", "X")
def h_srv():
    """ensure_server refuses to launch anything for a non-local endpoint and reports the local server state"""
    from sim.investigator import ensure_server
    remote = ensure_server("http://example.com/v1", wait_s=1)
    return remote is False, f"remote -> {remote}"


@test("D-stamp", "D")
def d_stamp():
    """the cache stamp covers newest candle, candle count, funding and positioning (four parts)"""
    from sim.data import _store_stamp
    st = _store_stamp()
    parts = st.split("|")
    return len(parts) == 4 and all(p.isdigit() for p in parts) and int(parts[0]) > 0 and int(parts[1]) > 0, st


@test("J-feat", "D")
def j_feat():
    """feat_cross columns are reachable through daily_features (beta_btc, r2_btc, idio_vol)"""
    from sim.data import daily_features
    f = daily_features(["beta_btc", "r2_btc", "idio_vol"])
    last = f["beta_btc"].dropna(how="all").index[-1]
    return set(f) == {"beta_btc", "r2_btc", "idio_vol"} and f["beta_btc"].loc[last].notna().sum() > 100, f"{f['beta_btc'].loc[last].notna().sum()} coins on last day"


@test("K-risk", "R")
def k_risk():
    """the stress check is never silently skipped: with too little BTC history the verdict says so"""
    d, b, rh = _risk(idio=5.0)
    kept, v, _ = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)], t=d.days[4])   # only 5 days of history
    return "stress_note" in v[0]["checks"] and "skipped" in v[0]["checks"]["stress_note"], str(v[0]["checks"].get("stress_note"))


@test("S-move", "R")
def s_move():
    """the skeptic dossier's daily move is the desk's own-move number, not raw 7-day vol"""
    d, b, rh = _risk(idio=23.07)
    ag = InvestigatorAgent.__new__(InvestigatorAgent)
    ag.risk = rh; ag._data = d; ag._conf = {"AAA": 0.7}; ag.last_chains = {}; ag.setup = "s"; ag.memory = None
    ag.last_call_meta = {}; ag.last_skeptic_meta = {}
    ag._chat = lambda msgs, thinking=False, max_tokens=0: '{"weakest":"C0","why_weakest":"x","verdicts":[{"label":"C0","action":"stand","reason":"ok 1"}]}'
    from sim.tools import Toolbox
    tab = pd.DataFrame({"rv_7d": [0.55]}, index=["C0"])                 # raw vol says 2.9%/day; own move is 23.07%/day
    box = Toolbox(d, None, d.days[4], "CHOP", tab, [], "s", coin_map={"C0": "AAA"})
    obs = type("O", (), {"t": d.days[4], "regime": "CHOP"})()
    ag._skeptic([Order("AAA", "long", 0.0432, 0.0864, 2, "{}", "x")], obs, box, {"AAA": "C0"}, [], "")
    dd = ag.last_skeptic["dossier"][0]
    return dd["typical_daily_move_pct"] == 23.07 and abs(dd["stop_in_daily_moves"] - 0.19) < 0.01 and dd["daily_move_source"] == "idio_daily_move_pct", f"{dd['typical_daily_move_pct']} moves {dd['stop_in_daily_moves']} src {dd['daily_move_source']}"


# ---------------------------------------------------------------- V: events / calendar
@test("C2s", "V")
def c2s():
    """FOMC times convert through New York DST: Jan (EST) -> 19:00 UTC, Sep (EDT) -> 18:00 UTC; CPI 08:30 ET"""
    from sim.events import ny_to_utc_ms
    from datetime import datetime, timezone
    h = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%H:%M")
    return h(ny_to_utc_ms(2021, "01-27", 14, 0)) == "19:00" and h(ny_to_utc_ms(2025, "09-17", 14, 0)) == "18:00" and h(ny_to_utc_ms(2025, "01-15", 8, 30)) == "13:30", "ok"


@test("C9s", "V")
def c9s():
    """sessions: asia/europe/us/late by UTC hour, weekend by weekday"""
    from sim.events import session_of
    base = 1_757_980_800_000            # 2025-09-16 00:00 UTC (Tuesday)
    got = [session_of(base + h * 3_600_000) for h in (1, 9, 14, 22)] + [session_of(base + 4 * DAY)]
    return got == ["asia", "europe", "us", "late", "weekend"], str(got)


@test("C1s", "V")
def c1s():
    """calendar reads are time-locked: an event with observed_at after t is invisible at t; past() needs the horizon to have passed"""
    from sim.events import Calendar
    c = Calendar()
    t = 1_757_980_800_000               # 2025-09-16
    up = c.upcoming(t, 3)
    fomc_visible = (up.event_type == "fomc").any()
    early = c.upcoming(1_600_000_000_000, 3)           # 2020-09: schedules not yet observed
    past7 = c.past(t, "fomc", horizon_days=7)
    return fomc_visible and early.empty and (past7.scheduled_ts + 7 * DAY <= t).all() and len(past7) > 30, f"fomc visible {fomc_visible}, 2020 rows {len(early)}, past n {len(past7)}"


@test("C24s", "V")
def c24s():
    """event_history returns n, median/p25/p75/hit at 1/3/7d for FOMC->BTC from real data"""
    from sim.events import Calendar, outcomes
    from sim.xsec import xsec
    from sim.data import daily_ohlc
    c = Calendar(); x = xsec(); close = daily_ohlc()["close"]
    r = outcomes(c, x["frames"]["resid_r_1d"].astype(float), close, 1_757_980_800_000, "fomc", target="BTC")
    ok = r["n"] >= 30 and all(k in r["horizons"] for k in ("1d", "3d", "7d")) and all(set(v) >= {"median_pct", "p25", "p75", "hit_up", "n"} for v in r["horizons"].values())
    return ok, f"n {r['n']} 3d {r['horizons'].get('3d')}"


@test("P3s", "V")
def p3s():
    """checklist gate: coverage is decided by the tool log, not the model"""
    from sim.investigator import checklist_missing
    log = [{"tool": t} for t in ("regime", "funding_extremes", "calendar", "market_table", "evidence", "similar", "fear_greed", "event_history")]
    return checklist_missing(log) == [] and len(checklist_missing(log[:3])) == 4, str(checklist_missing(log[:3]))   # calendar covers items 3 and 7


@test("R13s", "R")
def r13s():
    """event rule: a macro release inside 24h bounces an order without an event_note; with one it passes"""
    d, b, rh = _risk(idio=5.0)
    class Cal:
        def next_macro_hours(self, t): return {"event": "fomc", "entity": "FOMC statement", "hours": 6.0, "utc": "x"}
    d.calendar = Cal()
    kept, v, bounces = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10, "{}", "x")])
    o2 = Order("AAA", "long", 0.10, 0.15, 10, json.dumps({"event_note": "hawkish risk; sized down"}), "x")
    kept2, v2, _ = _review(rh, [o2])
    return not kept and "event_note" in bounces[0]["suggested"] and kept2 and v2[0]["checks"]["event_blackout"] == "fomc in 6.0h", f"{bounces[0]['violations'] if bounces else None} | second kept={bool(kept2)}"


@test("C12s", "V")
def c12s():
    """listing and unlock instances carry the asset id (symbol->id map direction)"""
    import sqlite3
    from sim.data import STORE
    c = sqlite3.connect(f"file:{STORE}?mode=ro", uri=True)
    l = c.execute("SELECT COUNT(*), COUNT(asset_id) FROM event_instance WHERE event_type='listing'").fetchone()
    u = c.execute("SELECT COUNT(*), COUNT(asset_id) FROM event_instance WHERE event_type='unlock'").fetchone()
    return l[0] == l[1] and l[0] >= 172 and u[1] >= 100, f"listings {l} unlocks {u}"


@test("R3c", "R")
def r3c():
    """a zero falsifier (model wrote move 0) is replaced by 60% of the stop on the correct side, and passes on resubmit"""
    d, b, rh = _risk(idio=5.0)
    kept, v, bounces = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10, falsifier_day=1, falsifier_pct=0.0)])
    fixd = bounces[0]["suggested"]
    o2 = Order("AAA", "long", 0.10, 0.15, 10, falsifier_day=1, falsifier_pct=fixd["falsifier_pct"])
    kept2, v2, _ = _review(rh, [o2])
    return not kept and fixd["falsifier_pct"] == -6.0 and kept2, f"fix {fixd} second kept={bool(kept2)}"


@test("C26s", "R")
def c26s():
    """confidence cap: with no admitted link, p_final is capped at 0.65 and the cap is logged"""
    d, b, rh = _risk(idio=5.0)
    kept, v, _ = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)], conf={"AAA": 0.9})
    c = v[0]["checks"]
    return bool(kept) and c["link_cap"].startswith("no admitted link") and abs(c["kelly_scale"] - min(max((2 * 0.65 - 1) * (0.10 / 0.15) * 4, 0), 1)) < 1e-6, f"{c['link_cap']} kelly {c['kelly_scale']}"


@test("C48s", "V")
def c48s():
    """links_as_of is time-locked and returns the latest vintage per (shock, horizon)"""
    from sim.links import links_as_of
    rows = links_as_of(1_788_134_400_000 + DAY)          # 2026-09-01: after the 08-31 vintage
    early = links_as_of(1_700_000_000_000)
    keys = {(r["shock"], r["horizon_days"]) for r in rows}
    return len(rows) == len(keys) and len(rows) >= 12 and early == [], f"{len(rows)} links; before vintage {len(early)}"


@test("B46s", "R")
def b46s():
    """outside view enforced: a repeat of a same-coin same-side trade that lost within 7 days needs p_final >= 0.65"""
    d, b, rh = _risk(idio=5.0)
    m = _mem(); rh.memory = m; t = d.days[4]
    m.learn(closed_ts=t - 2 * DAY, opened_ts=t - 4 * DAY, coin="AAA", side="long", setup="s:long", regime="CHOP", features={"f1": 1.0},
            thesis="{}", confidence=0.6, net_bps=-300, excess_bps=-250, mfe_bps=50, mae_bps=-400, exit_reason="stop", days_held=2,
            counterfactuals="{}", lesson="lost")
    kept, v, _ = _review(rh, [Order("AAA", "long", 0.10, 0.15, 10)], conf={"AAA": 0.6}, t=t)
    kept2, v2, _ = _review(rh, [Order("AAA", "short", 0.10, 0.15, 10)], conf={"AAA": 0.6}, t=t)     # other side: allowed
    ok = not kept and v[0]["action"] == "reject" and v[0]["checks"]["recent_loss_same_side"]["days_ago"] == 2.0 and bool(kept2)
    return ok, f"{v[0]['violations']} | short allowed={bool(kept2)}"


# ---------------------------------------------------------------- runner
def main():
    groups = set(sys.argv[1:]) or None
    rows, fails = [], 0
    for id_, group, doc, fn in TESTS:
        if groups and group not in groups:
            continue
        t0 = time.time()
        try:
            ok, detail = fn()
        except Exception as e:                                  # a crash is a failure with the traceback line
            ok, detail = False, f"EXC {type(e).__name__}: {e}"
        fails += not ok
        rows.append((id_, "PASS" if ok else "FAIL", f"{time.time() - t0:.1f}s", doc, str(detail)[:110]))
    w = max(len(r[3]) for r in rows) if rows else 10
    print(f"{'id':6} {'res':4} {'time':6} {'test':{w}}  detail")
    for r in rows:
        print(f"{r[0]:6} {r[1]:4} {r[2]:6} {r[3]:{w}}  {r[4]}")
    print(f"\n{len(rows) - fails}/{len(rows)} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
