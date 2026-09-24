"""Agents: something that looks at an as-of observation plus its memory and returns
orders. One interface, so the runner does not care which it is running.

  TrendRule / ReversalRule / RandomRule   fixed rules; the control arms.
  LearningTrendRule   the trend rule + the v2 learning engine (docs/LEARNING_ENGINE_V2.md):
                      Thompson sampling over (side x regime) with decayed evidence, a
                      probation floor so no setup is ever closed, insights with an
                      out-of-sample lifecycle. `hard_close=True` reproduces the v1
                      mistake (close a setup after N losses, forever) as an ablation.
  LLMAgent            a language model decides. It is shown, per coin, what happened in
                      the most similar past situations; the decayed evidence per setup
                      and regime; its active insights; its own calibration; and a few
                      of its most instructive lessons. It states a confidence with
                      every thesis and is scored on it. Observation is MASKED (coins as
                      letters, dates hidden) so a model cannot recall history.

Nothing in an observation is later than t.
"""
from __future__ import annotations

import json
import os
import random
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .data import AsOf, DAY_MS
from .engine import Order, Trade
from .memory import Memory

SIDES = ("long", "short")
REGIMES = ("UPTREND", "DOWNTREND", "CHOP")


def regime_label(data: AsOf, t: int) -> str:
    try:
        c = data.closes(t, 31, ["BTC"])["BTC"].dropna()
        r30 = float(c.iloc[-1] / c.iloc[0] - 1.0) if len(c) > 20 else 0.0
    except Exception:
        return "CHOP"
    return "UPTREND" if r30 > 0.03 else "DOWNTREND" if r30 < -0.03 else "CHOP"


@dataclass
class Observation:
    t: int
    regime: str
    table: pd.DataFrame          # index = coin; the numbers the agent asked for (+ sim_* columns)
    open_positions: List[str]


class Agent:
    name = "base"
    features: List[str] = []
    rebalance_days = 1
    setup = "base"               # tag used for evidence / insights

    def __init__(self, memory: Optional[Memory] = None, seed: int = 0):
        self.memory = memory
        self.rng = random.Random(seed)

    def observe(self, data: AsOf, t: int, open_positions: List[str]) -> Observation:
        coins = data.tradable(t)
        tab = pd.DataFrame(index=coins)
        tab["price"] = [data.price(t, c) for c in coins]
        for f in self.features:
            tab[f] = data.feature(t, f).reindex(coins).values
        tab["long_frac"] = data.positioning(t, "long_frac").reindex(coins).values
        tab["funding_day"] = data.funding_day(t).reindex(coins).values
        obs = Observation(t, regime_label(data, t), tab, open_positions)
        if self.memory is not None and self.features:
            # what happened in the most similar past situations (as a LONG's excess)
            n, mean = [], []
            for c in coins:
                fv = {f: tab.at[c, f] for f in self.features}
                s = self.memory.similar(fv, t, k=20, regime=obs.regime)
                n.append(s["n"]); mean.append(s["mean"])
            tab["sim_n"] = n
            tab["sim_long_excess_bps"] = mean
        return obs

    def decide(self, obs: Observation) -> List[Order]:
        raise NotImplementedError

    def confidence(self, order: Order) -> Optional[float]:
        return None

    def lesson(self, obs_at_open: Observation, tr: Trade) -> str:
        """Plain-words lesson written at close: plan vs outcome vs the best alternative
        plan on the same path. No model call needed."""
        cf = json.loads(tr.counterfactuals or "{}")
        best = max(cf.items(), key=lambda kv: kv[1]) if cf else None
        s = (f"{tr.side} {tr.coin} in {obs_at_open.regime} ({tr.tags}): {tr.exit_reason} after {tr.days_held}d, "
             f"net {tr.net_pnl / tr.notional * 1e4:+.0f} bps, {tr.excess_bps:+.0f} vs market; "
             f"reached {tr.mfe_bps:+.0f} for / {tr.mae_bps:+.0f} against.")
        if best and best[1] > tr.net_pnl / tr.notional * 1e4 + 100:
            s += f" Best plan on this path: {best[0]} -> {best[1]:+.0f} bps."
        return s


# ------------------------------------------------------------------ rule agents

class TrendRule(Agent):
    """Weekly: long the k strongest 7-day movers (skipping the last day) above their
    50-day average, short the k weakest below it. Hold 7 days, 6% stop, 12% target."""
    name = "trend_rule"
    setup = "trend"
    features = ["mom_7d_skip1", "px_vs_sma50", "rv_7d"]
    rebalance_days = 7

    def __init__(self, memory=None, seed=0, k=5):
        super().__init__(memory, seed)
        self.k = k

    def candidates(self, obs: Observation) -> Dict[str, List[str]]:
        t = obs.table.dropna(subset=["mom_7d_skip1", "px_vs_sma50"])
        t = t[~t.index.isin(obs.open_positions)]
        return {"long": list(t[t["px_vs_sma50"] > 0].sort_values("mom_7d_skip1", ascending=False).head(self.k).index),
                "short": list(t[t["px_vs_sma50"] < 0].sort_values("mom_7d_skip1").head(self.k).index)}

    def decide(self, obs: Observation) -> List[Order]:
        c = self.candidates(obs)
        return ([Order(x, "long", 0.06, 0.12, 7, f"7d momentum {obs.table.at[x,'mom_7d_skip1']:+.3f} above SMA50", "trend,long") for x in c["long"]] +
                [Order(x, "short", 0.06, 0.12, 7, f"7d momentum {obs.table.at[x,'mom_7d_skip1']:+.3f} below SMA50", "trend,short") for x in c["short"]])


class ReversalRule(Agent):
    name = "reversal_rule"
    setup = "reversal"
    features = ["r_1d"]
    rebalance_days = 1

    def __init__(self, memory=None, seed=0, k=5):
        super().__init__(memory, seed)
        self.k = k

    def decide(self, obs: Observation) -> List[Order]:
        t = obs.table.dropna(subset=["r_1d"])
        t = t[~t.index.isin(obs.open_positions)]
        return ([Order(c, "long", 0.05, 0.05, 1, f"1d loser {t.at[c,'r_1d']:+.3f}", "reversal,long") for c in t.sort_values("r_1d").head(self.k).index] +
                [Order(c, "short", 0.05, 0.05, 1, f"1d gainer {t.at[c,'r_1d']:+.3f}", "reversal,short") for c in t.sort_values("r_1d", ascending=False).head(self.k).index])


class RandomRule(Agent):
    name = "random_rule"
    setup = "random"
    features = []
    rebalance_days = 7

    def __init__(self, memory=None, seed=0, k=5):
        super().__init__(memory, seed)
        self.k = k

    def decide(self, obs: Observation) -> List[Order]:
        coins = [c for c in obs.table.index if c not in obs.open_positions]
        self.rng.shuffle(coins)
        return ([Order(c, "long", 0.06, 0.12, 7, "random", "random,long") for c in coins[: self.k]] +
                [Order(c, "short", 0.06, 0.12, 7, "random", "random,short") for c in coins[self.k: 2 * self.k]])


# ------------------------------------------------------------- learning agent

class LearningTrendRule(TrendRule):
    """TrendRule + the v2 engine. For each side in the current regime it draws a
    Thompson sample of that setup's decayed excess. Positive draw -> take the side at
    full size. Negative draw -> still take it with probability `explore` at half size
    (a PROBATION trade), so the evidence never dies. Evidence with n_eff >= 20 and a
    negative decayed mean proposes a 'skip' insight; the insight only becomes active
    with out-of-sample support, and later disagreeing outcomes retire it.
    hard_close=True: v1 behaviour - a proposed skip is obeyed absolutely and forever."""
    name = "learning_trend"

    def __init__(self, memory=None, seed=0, k=5, explore=0.10, hard_close=False):
        super().__init__(memory, seed, k)
        self.explore, self.hard_close = explore, hard_close
        self._probation: Dict[str, bool] = {}
        if hard_close:
            self.name = "learning_trend_hard"

    def _side_setup(self, side: str) -> str:
        return f"{self.setup}:{side}"

    def _maybe_propose(self, t: int, regime: str) -> None:
        if self.memory is None:
            return
        existing = {(i["setup"], i["regime"]) for st in ("proposed", "active")
                    for i in self.memory.insights(t, st)}
        for side in SIDES:
            su = self._side_setup(side)
            ev = self.memory.evidence(su, regime, t)
            if ev["n_eff"] >= 20 and ev["mean"] < 0 and (su, regime) not in existing:
                self.memory.propose_insight(t, su, regime,
                    f"Skip {side}s in {regime}: decayed mean {ev['mean']:+.0f} bps vs market over "
                    f"{ev['n']} trades (win {ev['win']*100:.0f}%).", "evidence", ev["n"])

    def decide(self, obs: Observation) -> List[Order]:
        cands = self.candidates(obs)
        if self.memory is None:
            return super().decide(obs)
        self._maybe_propose(obs.t, obs.regime)
        active = {(i["setup"], i["regime"]) for i in self.memory.insights(obs.t, "active")}
        if self.hard_close:
            active |= {(i["setup"], i["regime"]) for i in self.memory.insights(obs.t, "proposed")}
        out = []
        for side in SIDES:
            su = self._side_setup(side)
            skip_rule = (su, obs.regime) in active
            if self.hard_close and skip_rule:
                continue                                       # v1: door closed, forever
            draw = self.memory.sample(su, obs.regime, obs.t)
            take_full = draw > 0 and not skip_rule
            probation = not take_full and self.rng.random() < self.explore
            if not (take_full or probation):
                continue
            for x in cands[side]:
                o = Order(x, side, 0.06, 0.12, 7,
                          f"7d momentum {obs.table.at[x,'mom_7d_skip1']:+.3f} {'above' if side=='long' else 'below'} SMA50"
                          + (" [probation]" if probation else ""), f"trend,{side}",
                          notional=50.0 if probation else None)
                self._probation[x] = probation
                out.append(o)
        return out


# ------------------------------------------------------------------ LLM agent

class LLMAgent(Agent):
    """A language model decides. Endpoint from env SIM_LLM:
         "ollama:<model>"            -> http://localhost:11434/api/chat
         "openai:<model>@<base_url>" -> any OpenAI-compatible server (llama.cpp llama-server, vLLM, ...)
         "anthropic:<model>"         -> Anthropic Messages API (ANTHROPIC_API_KEY)
    Must answer JSON: {"orders":[{"label":"C3","side":"long","stop_pct":0.06,"target_pct":0.12,
    "hold_days":7,"confidence":0.65,"thesis":"..."}], "notes":"..."}"""
    name = "llm"
    setup = "llm"
    features = ["mom_7d_skip1", "r_1d", "r_30d", "px_vs_sma50", "rv_7d", "rsi_14", "vol_zscore"]
    rebalance_days = 7

    def __init__(self, memory=None, seed=0, max_orders=6, spec: Optional[str] = None):
        super().__init__(memory, seed)
        self.max_orders = max_orders
        self.spec = spec or os.environ.get("SIM_LLM", "")
        self._labels: Dict[int, Dict[str, str]] = {}
        self._conf: Dict[str, float] = {}

    def _mask(self, obs: Observation):
        coins = list(obs.table.index)
        self.rng.shuffle(coins)
        labels = {c: f"C{i+1}" for i, c in enumerate(coins)}
        self._labels[obs.t] = {v: k for k, v in labels.items()}
        tab = obs.table.copy()
        tab.index = [labels[c] for c in tab.index]
        tab = tab.drop(columns=["price"])
        return tab.round(4), labels

    def _prompt(self, obs: Observation) -> str:
        tab, labels = self._mask(obs)
        held = [labels[c] for c in obs.open_positions if c in labels]
        lines = [
            "You are a crypto perpetuals trader in a simulation. Coins are anonymised as C1..Cn and the date is hidden.",
            f"Market regime (BTC 30-day move): {obs.regime}. Positions already open: {held or 'none'}.",
            "Columns: mom_7d_skip1 (7d return skipping last day), r_1d, r_30d, px_vs_sma50, rv_7d (vol), rsi_14, vol_zscore, "
            "long_frac (share of Binance accounts long, may be NaN), funding_day (fraction/day, may be NaN), "
            "sim_n / sim_long_excess_bps (how many of YOUR OWN past trades looked like this coin now, and the average result "
            "a LONG made in them, vs market, after costs - negative means longs lost / shorts won).",
            "Costs: 4.5 bps taker + half spread each side. Fixed $100 per trade. Fills at the stop/target level.",
            "", "DATA (as of now, nothing from the future):", tab.to_csv(),
        ]
        if self.memory is not None:
            ev = self.memory.evidence_table([f"llm:{s}" for s in SIDES], REGIMES, obs.t)
            if ev:
                lines += ["", "YOUR TRACK RECORD by setup and regime (decayed, vs market, after costs):"]
                lines += [f"- {e['setup'].split(':')[1]}s in {e['regime']}: n={e['n']} eff={e['n_eff']:.0f} mean {e['mean']:+.0f} bps win {e['win']*100:.0f}%" for e in ev]
            cal = self.memory.calibration(obs.t)
            if cal:
                lines += ["", "YOUR CALIBRATION (stated confidence -> actual win rate):"]
                lines += [f"- confidence {c['bucket']}: n={c['n']} win {c['win']*100:.0f}% mean {c['mean_excess']:+.0f} bps" for c in cal]
            ins = self.memory.insights(obs.t, "active")
            if ins:
                lines += ["", "YOUR ACTIVE INSIGHTS (rules that earned out-of-sample support):"]
                lines += [f"- {i['text']} [importance {i['importance']}, oos n={i['oos_n']}]" for i in ins]
            les = self.memory.recall(obs.t, obs.regime, k=5)
            if les:
                lines += ["", "YOUR MOST INSTRUCTIVE LESSONS in this regime:"]
                lines += [f"- {l['lesson']}" for l in les]
        lines += ["", f"Decide up to {self.max_orders} new trades. Every order needs a confidence in (0,1) = your honest probability it "
                  "ends positive after costs. Answer ONLY with JSON: "
                  '{"orders":[{"label":"C3","side":"long|short","stop_pct":0.06,"target_pct":0.12,"hold_days":7,'
                  '"confidence":0.6,"thesis":"one sentence"}],"notes":"what you are watching"}']
        return "\n".join(lines)

    def _ask(self, prompt: str) -> str:
        kind, _, model = self.spec.partition(":")
        if kind == "ollama":
            body = json.dumps({"model": model, "stream": False, "format": "json",
                               "messages": [{"role": "user", "content": prompt}]}).encode()
            req = urllib.request.Request("http://localhost:11434/api/chat", body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=1800) as r:
                return json.loads(r.read())["message"]["content"]
        if kind == "openai":
            model, _, base = model.partition("@")
            base = base or "http://localhost:8080/v1"
            body = json.dumps({"model": model, "temperature": 0.2, "max_tokens": 1500,
                               "messages": [{"role": "user", "content": prompt}]}).encode()
            hdr = {"Content-Type": "application/json"}
            if os.environ.get("OPENAI_API_KEY"):
                hdr["Authorization"] = "Bearer " + os.environ["OPENAI_API_KEY"]
            req = urllib.request.Request(base.rstrip("/") + "/chat/completions", body, hdr)
            with urllib.request.urlopen(req, timeout=1800) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"]
        if kind == "anthropic":
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            body = json.dumps({"model": model, "max_tokens": 1500,
                               "messages": [{"role": "user", "content": prompt}]}).encode()
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", body,
                                         {"Content-Type": "application/json", "x-api-key": key,
                                          "anthropic-version": "2023-06-01"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return "".join(b.get("text", "") for b in json.loads(r.read())["content"])
        raise RuntimeError(f"SIM_LLM not set or unknown: {self.spec!r}")

    def decide(self, obs: Observation) -> List[Order]:
        raw = self._ask(self._prompt(obs))
        try:
            s, e = raw.find("{"), raw.rfind("}")
            parsed = json.loads(raw[s:e + 1])
        except Exception:
            return []
        unmask = self._labels.get(obs.t, {})
        out = []
        for o in (parsed.get("orders") or [])[: self.max_orders]:
            coin = unmask.get(str(o.get("label", "")))
            side = o.get("side")
            if not coin or side not in SIDES or coin in obs.open_positions:
                continue
            try:
                conf = float(o.get("confidence", 0.5))
            except (TypeError, ValueError):
                conf = 0.5
            self._conf[coin] = min(max(conf, 0.01), 0.99)
            out.append(Order(coin, side, float(o.get("stop_pct", 0.06)), float(o.get("target_pct", 0.12)),
                             int(o.get("hold_days", 7)), str(o.get("thesis", ""))[:300], f"llm,{side}"))
        return out

    def confidence(self, order: Order) -> Optional[float]:
        return self._conf.get(order.coin)


AGENTS = {
    "trend": TrendRule,
    "reversal": ReversalRule,
    "random": RandomRule,
    "learning_trend": LearningTrendRule,
    "learning_trend_hard": lambda memory=None, seed=0: LearningTrendRule(memory, seed, hard_close=True),
    "llm": LLMAgent,
}
