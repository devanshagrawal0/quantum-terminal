"""The agent's eyes: time-locked tools over everything in the store, plus its own memory.

Every tool takes the simulation clock `t` from the Toolbox and returns a small JSON-able
dict with a `source` stamp. Nothing after t is reachable. When a table simply has no
data for that date (positioning before 2026-08, cross-venue outside 2026-08-23/24,
unlocks before now, prediction markets outside 2026-09-09) the tool says so - it does
not invent. Every call is appended to `self.log` (tool, args, summary, t): the evidence
log the survey calls provenance.
"""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .data import AsOf, DAY_MS, STORE, VENUES, _ro, _cached
from .memory import Memory

ROOT = Path(__file__).resolve().parents[1]
UNLOCKS_DB = ROOT / "data" / "unlocks.db"


# ------------------------------------------------------------- extra loaders
def macro_series() -> Dict[str, pd.Series]:
    def build():
        conn = _ro(STORE)
        df = pd.read_sql_query(
            "SELECT series_id, ts_ms, value FROM macro_series WHERE series_id IN "
            "('US_FEDFUNDS','US_10Y','FEAR_GREED','EURUSD','EA_10Y_YIELD','ECB_MRO_RATE','USDBRL')", conn)
        conn.close()
        out = {}
        for sid, g in df.groupby("series_id"):
            s = g.set_index("ts_ms")["value"].sort_index()
            s = s[s.index > 0]
            out[sid] = s
        return out
    return _cached("macro", build)


def perp_state_daily() -> Dict[str, pd.DataFrame]:
    """oi_usd and funding_hourly per coin per day from perp_state (2026-08-23 ->)."""
    def build():
        conn = _ro(STORE)
        names = {i: s for i, s in conn.execute("SELECT id, symbol FROM asset")}
        df = pd.read_sql_query("SELECT ts_ms, asset_id, oi_usd, funding_hourly FROM perp_state", conn)
        conn.close()
        df["coin"] = df["asset_id"].map(names)
        df["day"] = (df["ts_ms"] // DAY_MS) * DAY_MS
        return {"oi_usd": df.groupby(["day", "coin"])["oi_usd"].last().unstack().sort_index(),
                "funding_hourly": df.groupby(["day", "coin"])["funding_hourly"].mean().unstack().sort_index()}
    return _cached("perp_state_daily", build)


# ------------------------------------------------------------------ toolbox
def crowd_label(f: float) -> str:
    """The sign convention written by code so the model never has to infer it."""
    if f is None or (isinstance(f, float) and math.isnan(f)):
        return "no funding data"
    if f > 0.0015:
        return "longs pay shorts - LONGS CROWDED - squeeze risk is DOWN (long liquidations)"
    if f > 0:
        return "longs pay shorts (mild) - slightly crowded long"
    if f < -0.0015:
        return "shorts pay longs - SHORTS CROWDED - squeeze risk is UP (short covering)"
    if f < 0:
        return "shorts pay longs (mild) - slightly crowded short"
    return "funding flat - no crowd either way"


def positioning_label(long_share: float, chg7: Optional[float]) -> str:
    """Engine-written reading of the account long-share and its 7-day change."""
    if long_share >= 0.65:
        base = f"{long_share:.0%} of accounts long - LONGS CROWDED"
    elif long_share <= 0.40:
        base = f"{long_share:.0%} of accounts long - SHORTS CROWDED"
    else:
        base = f"{long_share:.0%} of accounts long - balanced"
    if chg7 is None:
        return base
    if chg7 >= 0.05:
        return base + f"; long share UP {chg7:+.0%} in 7d (crowd piling into longs)"
    if chg7 <= -0.05:
        return base + f"; long share DOWN {chg7:+.0%} in 7d (crowd leaving longs)"
    return base + f"; little change in 7d ({chg7:+.1%})"


class Toolbox:
    def __init__(self, data: AsOf, memory: Optional[Memory], t: int, regime: str, table: pd.DataFrame,
                 open_positions: List[str], agent_setup: str = "llm", coin_map: Optional[Dict[str, str]] = None):
        # `table` may be MASKED (index = C1..Cn); coin_map translates a label to the real coin
        # for data lookups. Results echo whatever name the caller used.
        self.data, self.memory, self.t, self.regime_lbl = data, memory, t, regime
        self.table, self.open_positions, self.setup = table, open_positions, agent_setup
        self.coin_map = coin_map or {}
        self.macro = macro_series()
        self.perp = perp_state_daily()
        self.log: List[Dict[str, Any]] = []
        self.round = 0                                   # investigator round, stamped on every call
        self.labels_of = {v: k for k, v in self.coin_map.items()}   # real coin -> label

    # ---- helpers ----
    def _asof(self, s: pd.Series, days: int = 1) -> pd.Series:
        s = s[(s.index <= self.t + DAY_MS - 1) & (s.index > self.t - days * DAY_MS)]
        return s

    def _coin(self, x: str) -> str:
        return self.coin_map.get(x, x)

    def _stamp(self, name: str, args: Dict, result: Dict) -> Dict:
        """Append to the evidence log: what was asked, what came back (truncated)."""
        summary = json.dumps(result, default=str)
        self.log.append({"tool": name, "args": args, "t": self.t, "round": self.round,
                         "result": summary if len(summary) <= 800 else summary[:800] + "...(truncated)"})
        return result

    # ---- tools ----
    def market_table(self, sort_by: str = "mom_7d_skip1", top_n: int = 15, ascending: bool = False,
                     columns: Optional[List[str]] = None) -> Dict:
        """The masked coin table, sorted; ask for slices, the whole universe is 172 rows."""
        tab = self.table.drop(columns=[c for c in ("price",) if c in self.table.columns])
        if sort_by in tab.columns:
            tab = tab.sort_values(sort_by, ascending=ascending)
        if columns:
            tab = tab[[c for c in columns if c in tab.columns]]
        return {"rows": tab.head(int(top_n)).round(4).to_dict(orient="index"), "n_universe": len(self.table),
                "source": "feat_* at the decision bar"}

    def regime(self) -> Dict:
        c = self.data.closes(self.t, 31)
        rets1 = c.iloc[-1] / c.iloc[-2] - 1.0
        rets7 = c.iloc[-1] / c.iloc[-8] - 1.0 if len(c) >= 8 else rets1 * np.nan
        btc = c["BTC"].dropna() if "BTC" in c.columns else None
        r30 = float(btc.iloc[-1] / btc.iloc[0] - 1.0) if btc is not None and len(btc) > 20 else float("nan")
        return {"label": self.regime_lbl, "btc_30d": round(r30, 4),
                "breadth_1d_pct_green": round(float((rets1 > 0).mean()) * 100, 1),
                "breadth_7d_pct_green": round(float((rets7 > 0).mean()) * 100, 1),
                "coins_priced": int(rets1.notna().sum()), "source": "daily closes"}

    def correlations(self, coins: List[str], days: int = 30) -> Dict:
        labels = list(coins); coins = [self._coin(x) for x in coins]
        c = self.data.closes(self.t, days + 1, [x for x in coins if x in self.data.close.columns] + (["BTC"] if "BTC" not in coins else []))
        r = c.pct_change().dropna(how="all")
        if len(r) < 10:
            return {"note": "not enough history", "source": "daily closes"}
        corr = r.corr()
        back = dict(zip(coins, labels))
        out = {back[x]: round(float(corr.at[x, "BTC"]), 2) for x in coins if x in corr.index and "BTC" in corr.columns}
        pair = {f"{back[a]}-{back[b]}": round(float(corr.at[a, b]), 2) for i, a in enumerate(coins) for b in coins[i+1:] if a in corr.index and b in corr.columns}
        return {"corr_to_btc": out, "pairwise": pair, "days": days, "source": "daily closes"}

    def positioning(self, coin: str) -> Dict:
        label, coin = coin, self._coin(coin)
        lf = self.data.pos["long_frac"]; tl = self.data.pos["top_long_frac"]; oi = self.data.pos["oi_usd"]
        if coin not in lf.columns or self.t not in lf.index or pd.isna(lf.at[self.t, coin]):
            return {"coin": label, "note": "no positioning data at this date (Binance crowd data starts 2026-08-02)",
                    "source": "positioning"}
        def chg(df, k=7):
            idx = df.index.get_indexer([self.t])[0]
            if idx >= k and coin in df.columns:
                a, b = df.iloc[idx][coin], df.iloc[idx - k][coin]
                return None if pd.isna(a) or pd.isna(b) else round(float(a - b), 4)
            return None
        return {"coin": label, "long_share_of_accounts": round(float(lf.at[self.t, coin]), 4),
                "top_trader_long_share": None if pd.isna(tl.at[self.t, coin]) else round(float(tl.at[self.t, coin]), 4),
                "open_interest_usd": None if pd.isna(oi.at[self.t, coin]) else float(oi.at[self.t, coin]),
                "long_share_change_7d": chg(lf), "oi_change_7d_usd": chg(oi),
                "crowd": positioning_label(float(lf.at[self.t, coin]), chg(lf)), "source": "positioning (Binance archive)"}

    def funding(self, coin: str) -> Dict:
        label, coin = coin, self._coin(coin)
        f = self.data.funding
        if coin not in f.columns:
            return {"coin": label, "note": "no funding series", "source": "funding"}
        s = f[coin]; s = s[(s.index <= self.t)].dropna().tail(30)
        if s.empty:
            return {"coin": label, "note": "no funding data at this date (history starts 2025-08-13)", "source": "funding"}
        last = float(s.iloc[-1])
        return {"coin": label, "funding_last_day_pct": round(last * 100, 4), "funding_7d_avg_pct": round(float(s.tail(7).mean()) * 100, 4),
                "funding_30d_avg_pct": round(float(s.mean()) * 100, 4), "annualised_pct": round(last * 365 * 100, 1),
                "who_pays": "longs pay shorts" if last > 0 else "shorts pay longs",
                "crowd": crowd_label(last), "source": "funding daily"}

    def funding_extremes(self, top_n: int = 8) -> Dict:
        f = self.data.funding
        if self.t not in f.index:
            return {"note": "no funding data at this date", "source": "funding daily"}
        row = f.loc[self.t].dropna()
        coins = {self._coin(x): x for x in self.table.index}          # real coin -> label shown to the model
        row = row[row.index.isin(list(coins))]
        if row.empty:
            return {"note": "no funding data at this date", "source": "funding daily"}
        top = row.sort_values(ascending=False).head(top_n); bot = row.sort_values().head(top_n)
        return {"convention": "positive = longs pay shorts = LONGS crowded (squeeze DOWN); negative = shorts pay longs = SHORTS crowded (squeeze UP)",
                "most_positive_pct_per_day": {coins[c]: round(v * 100, 4) for c, v in top.items()},
                "most_negative_pct_per_day": {coins[c]: round(v * 100, 4) for c, v in bot.items()},
                "median_pct_per_day": round(float(row.median()) * 100, 4), "n_coins": int(len(row)), "source": "funding daily"}

    def open_interest(self, coin: str) -> Dict:
        label, coin = coin, self._coin(coin)
        oi = self.perp["oi_usd"]
        if coin not in oi.columns or self.t not in oi.index or pd.isna(oi.at[self.t, coin]):
            return {"coin": label, "note": "no open-interest data at this date (perp_state starts 2026-08-23)", "source": "perp_state"}
        s = oi[coin].dropna(); s = s[s.index <= self.t].tail(8)
        return {"coin": label, "oi_usd": float(s.iloc[-1]), "oi_change_7d_pct": None if len(s) < 8 else round(float(s.iloc[-1] / s.iloc[0] - 1) * 100, 1),
                "source": "perp_state"}

    def fear_greed(self, days: int = 30) -> Dict:
        s = self._asof(self.macro.get("FEAR_GREED", pd.Series(dtype=float)), days)
        if s.empty:
            return {"note": "no Fear&Greed at this date", "source": "alternative.me"}
        return {"now": float(s.iloc[-1]), "min_30d": float(s.min()), "max_30d": float(s.max()),
                "mean_30d": round(float(s.mean()), 1), "source": "alternative.me via macro_series"}

    def macro_rates(self, days: int = 90) -> Dict:
        out = {}
        for sid, label in (("US_FEDFUNDS", "fed_funds_pct"), ("US_10Y", "us_10y_pct"), ("EURUSD", "eurusd"), ("EA_10Y_YIELD", "euro_10y_pct")):
            s = self._asof(self.macro.get(sid, pd.Series(dtype=float)), days)
            if not s.empty:
                out[label] = {"now": round(float(s.iloc[-1]), 3), "change_over_window": round(float(s.iloc[-1] - s.iloc[0]), 3)}
        out["source"] = "macro_series (dbnomics/ecb)"; out["note"] = "oil, dollar index, breakevens, VIX not in store yet (FRED key pending)"
        return out

    def scheduled_events(self, days: int = 7) -> Dict:
        if not UNLOCKS_DB.exists():
            return {"note": "no calendar", "source": "unlocks.db"}
        conn = sqlite3.connect(f"file:{UNLOCKS_DB}?mode=ro", uri=True)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(unlocks)")}
        lo, hi = self.t // 1000, (self.t + days * DAY_MS) // 1000
        rows = conn.execute("SELECT gecko_id, slug, next_ts" + (", next_tokens, next_pct_max, next_cats" if "next_pct_max" in cols else "") +
                            " FROM unlocks WHERE next_ts BETWEEN ? AND ? ORDER BY next_ts", (lo, hi)).fetchall()
        conn.close()
        if not rows:
            return {"events": [], "note": "no unlock in window (calendar only knows FUTURE unlocks from today; empty in historical sims)", "source": "unlocks.db"}
        return {"events": [{"token": r[1], "in_days": round((r[2] - lo) / 86400, 1),
                            **({"tokens": r[3], "pct_of_max_supply": None if r[4] is None else round(r[4] * 100, 2), "categories": r[5]} if len(r) > 3 else {})}
                           for r in rows[:25]], "source": "unlocks.db (DefiLlama)"}

    def cross_venue(self, coin: str) -> Dict:
        label, coin = coin, self._coin(coin)
        conn = _ro(VENUES)
        row = conn.execute("SELECT ts_ms, hl_spread_bps, sp_basis_bps, disp_iqr_bps, n_venues, credible_vol_usd FROM cv_features "
                           "WHERE coin=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1", (coin, self.t + DAY_MS)).fetchone()
        conn.close()
        if not row or (self.t - row[0]) > 3 * DAY_MS:
            return {"coin": label, "note": "no cross-venue snapshot within 3 days of this date (panel covers 2026-08-23/24 only)", "source": "cv_features"}
        return {"coin": label, "hl_spread_bps": row[1], "perp_spot_basis_bps": row[2], "venue_dispersion_bps": row[3],
                "n_venues": row[4], "credible_vol_usd": row[5], "source": "cv_features"}

    # ---- calendar and event history ----
    def calendar(self, days: int = 7) -> Dict:
        """Everything scheduled in the next `days` days that was known today: macro releases
        with UTC time and hours from now, expiries, unlocks/listings for coins in the universe
        (labelled), plus the session we are in now."""
        from .events import session_of
        cal = getattr(self.data, "calendar", None)
        if cal is None:
            return {"note": "no calendar loaded", "source": "event_instance"}
        coins = [self._coin(x) for x in self.table.index]
        up = cal.upcoming(self.t, int(days), coins)
        rows = []
        for _, r in up.iterrows():
            lab = self.labels_of.get(r.coin) if isinstance(r.coin, str) else None
            rows.append({"event": r.event_type, "what": (r.entity if lab is None else f"{lab}: {r.entity.split(' ', 1)[1] if ' ' in r.entity else r.entity}"),
                         "utc": pd.Timestamp(int(r.scheduled_ts), unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M"),
                         "hours_from_now": round((int(r.scheduled_ts) - self.t) / 3.6e6, 1),
                         "consensus": r.consensus, "realised": r.realised})
        return {"now_session": session_of(self.t), "next_macro": cal.next_macro_hours(self.t), "events": rows[:40],
                "n": int(len(up)), "source": "event_instance (FOMC/CPI/NFP/opex/unlocks/listings)"}

    def event_history(self, event_type: str, coin: Optional[str] = None, target: str = "BTC") -> Dict:
        """What happened after past events of this type (only events whose horizon has passed):
        for coin events (unlock, listing) the coin's own residual move; for macro events BTC/ETH."""
        from .events import outcomes
        cal = getattr(self.data, "calendar", None); x = getattr(self.data, "xsec", None)
        if cal is None or x is None:
            return {"note": "no calendar/xsec loaded", "source": "event_instance"}
        real = self._coin(coin) if coin else None
        res = outcomes(cal, x["frames"]["resid_r_1d"].astype(float), self.data.close, self.t, str(event_type), target=str(target), coin=real)
        res["source"] = "event_instance + residual returns (time-locked)"
        if coin:
            res["coin"] = coin
        return res

    def links(self) -> Dict:
        """Measured responses (local projections) of forward residual returns to shocks, as of today:
        beta in bps per 1 standard deviation of the shock, t-stat, days, sign stability, status.
        'admitted' = |t|>=3 and sign stable; 'unmeasured' = not strong enough to be used as a fact."""
        from .links import links_as_of
        rows = links_as_of(self.t)
        admitted = [r for r in rows if r["status"] == "admitted"]
        return {"admitted": admitted, "unmeasured": [r for r in rows if r["status"] != "admitted"][:12], "n": len(rows),
                "reading": ("no shock->return link is admitted at |t|>=3 today: any chain built on funding, momentum or "
                            "positioning alone is UNMEASURED and its confidence is capped by the risk desk" if not admitted else
                            f"{len(admitted)} admitted links"),
                "source": "link table (LP, day fixed effects, clustered SE)"}

    # ---- its own mind ----
    def similar(self, coin: str, k: int = 20) -> Dict:
        if self.memory is None or coin not in self.table.index:
            return {"coin": coin, "note": "no memory or unknown label"}
        fv = {f: self.table.at[coin, f] for f in self.table.columns if f not in ("price", "sim_n", "sim_long_excess_bps", "long_frac", "funding_day")}
        s = self.memory.similar(fv, self.t, k=k, regime=self.regime_lbl)
        return {"coin": coin, "n": s["n"], "long_excess_bps_mean": None if math.isnan(s["mean"]) else round(s["mean"], 0),
                "long_win_rate": None if math.isnan(s["win"]) else round(s["win"], 2), "source": "own experiences (feature k-NN)"}

    def evidence(self, side: str) -> Dict:
        if self.memory is None:
            return {"note": "no memory"}
        ev = self.memory.evidence(f"{self.setup}:{side}", self.regime_lbl, self.t)
        ev_all = self.memory.evidence(f"{self.setup}:{side}", None, self.t)
        return {"side": side, "regime": self.regime_lbl, "in_regime": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in ev.items()},
                "all_regimes": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in ev_all.items()}, "source": "own experiences, decayed"}

    def stops_report(self, side: str) -> Dict:
        """From counterfactuals: which stop/target plan paid best for this side, and how
        often the stop fired before the target would have hit."""
        if self.memory is None:
            return {"note": "no memory"}
        rows = self.memory.conn.execute(
            "SELECT counterfactuals, exit_reason FROM experience WHERE agent=? AND side=? AND closed_ts<=? ORDER BY closed_ts DESC LIMIT 200",
            (self.memory.agent, side, self.t)).fetchall()
        if not rows:
            return {"side": side, "note": "no closed trades yet"}
        agg: Dict[str, List[float]] = {}
        stopped = 0
        for cf, reason in rows:
            d = json.loads(cf or "{}")
            for k, v in d.items():
                if k.startswith(side + ":"):
                    agg.setdefault(k, []).append(v)
            stopped += reason == "stop"
        best = sorted(((k, float(np.mean(v)), len(v)) for k, v in agg.items()), key=lambda x: -x[1])[:4]
        return {"side": side, "n": len(rows), "stop_rate": round(stopped / len(rows), 2),
                "best_plans_mean_bps": [{"plan": k, "mean_bps": round(m, 0), "n": n} for k, m, n in best], "source": "own counterfactuals"}

    def insights(self) -> Dict:
        if self.memory is None:
            return {"active": []}
        return {"active": [{"text": i["text"], "importance": i["importance"], "oos_n": i["oos_n"]} for i in self.memory.insights(self.t, "active")],
                "proposed": len(self.memory.insights(self.t, "proposed")), "source": "own insights"}

    def calibration(self) -> Dict:
        if self.memory is None:
            return {"buckets": []}
        return {"buckets": self.memory.calibration(self.t), "source": "own record"}

    def market_view(self, n: int = 3) -> Dict:
        if self.memory is None:
            return {"views": []}
        return {"views": self.memory.notes(self.t, kind="market_view", k=n), "source": "own notes"}

    def recall(self, query: str, k: int = 5) -> Dict:
        if self.memory is None:
            return {"lessons": []}
        return {"lessons": [l["lesson"] for l in self.memory.recall(self.t, query, k=k)], "source": "own lessons (FTS)"}

    def write_note(self, text: str, tags: str = "") -> Dict:
        if self.memory is None:
            return {"note": "no memory"}
        nid = self.memory.write_note(self.t, "note", text, tags)
        return {"stored": nid}

    # ---- dispatch ----
    SPEC = {
        "market_table": "sort_by (a column), top_n, ascending, columns[] -> a slice of the coin table (172 coins; ask for slices). "
                        "Columns include beta_btc, r2_btc (share of moves explained by BTC), idio_vol (own annualised vol), "
                        "resid_mom_7d_skip1 (7d momentum after removing BTC's part)",
        "regime": "-> regime label, BTC 30d, breadth (% coins green 1d/7d)",
        "correlations": "coins[] , days -> correlation to BTC and pairwise (concentration risk)",
        "positioning": "coin -> Binance crowd long share, top-trader share, OI, 7d changes (from 2026-08-02)",
        "funding": "coin -> funding last day / 7d / 30d, who pays whom",
        "funding_extremes": "top_n -> most positive and most negative funding coins today",
        "open_interest": "coin -> OI and 7d change (from 2026-08-23)",
        "fear_greed": "days -> Fear & Greed index now and its 30d range",
        "macro_rates": "days -> Fed funds, US 10y, EUR/USD, euro 10y and their change",
        "scheduled_events": "days -> upcoming token unlocks with size (future-only calendar)",
        "links": "-> measured shock->return links (funding, momentum, positioning): beta bps per 1 sd, t-stat, status admitted/unmeasured",
        "calendar": "days -> everything scheduled in the window known today: FOMC/CPI/NFP with UTC time and hours from now, expiries, unlocks and listings for labelled coins, and the session we are in",
        "event_history": "event_type (fomc|cpi|nfp|opex|unlock|listing), coin (for unlock/listing), target (BTC|ETH for macro) -> what happened after past events of that type: median/p25/p75/hit rate at 1d/3d/7d, n",
        "cross_venue": "coin -> HL spread, perp-spot basis, venue dispersion (2026-08-23/24 only)",
        "similar": "coin, k -> what happened in your k most similar past situations (as a long)",
        "evidence": "side -> your decayed track record for this side in this regime and overall",
        "stops_report": "side -> which stop/target plans paid best in your closed trades; how often stops fired",
        "insights": "-> your active insights (rules with out-of-sample support)",
        "calibration": "-> your stated confidence vs actual win rate",
        "market_view": "n -> your last n weekly market views",
        "recall": "query, k -> your lessons matching the words",
        "write_note": "text, tags -> store a note for your future self",
    }

    def call(self, name: str, args: Optional[Dict] = None) -> Dict:
        args = dict(args or {})
        fn = getattr(self, name, None)
        if name not in self.SPEC or fn is None:
            return self._stamp(name, args, {"error": f"unknown tool {name}"})
        try:
            res = fn(**args)
        except TypeError as e:
            res = {"error": f"bad arguments for {name}: {e}"}
        except Exception as e:  # noqa: BLE001
            res = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
        return self._stamp(name, args, res)
