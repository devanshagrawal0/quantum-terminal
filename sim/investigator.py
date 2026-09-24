"""The investigator agent - docs/AGENT_COGNITION_SPEC.md section 3.

One decision = Investigator rounds (asks follow-up questions, each answered by a tool
call; gathers evidence cards; writes a market view; thinking OFF for speed) -> Strategist
(chains with mechanism, falsifier, checkpoint, confidence; thinking ON). Every tool call
is logged as evidence and saved by the runner next to the decision.
"""
from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from typing import Dict, List

from .agents import AGENTS, LLMAgent, Observation, SIDES
from .data import AsOf
from .engine import Order, Trade
from .tools import Toolbox

NL = chr(10)


def ensure_server(base: str, wait_s: int = 120) -> bool:
    """If the local llama-server is down, start it (C:/llm/run-qwen.ps1) and wait for /health.
    Returns True when the server answers. Only for the local endpoint; remote bases just fail."""
    import subprocess
    import time as _t
    root = base.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    if "127.0.0.1" not in root and "localhost" not in root:
        return False
    def up():
        try:
            with urllib.request.urlopen(root + "/health", timeout=3) as r:
                return b"ok" in r.read()
        except Exception:
            return False
    if up():
        return True
    script = r"C:\llm\run-qwen.ps1"
    if not os.path.exists(script):
        return False
    subprocess.Popen(["powershell", "-ExecutionPolicy", "Bypass", "-File", script],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(wait_s // 3):
        _t.sleep(3)
        if up():
            return True
    return False

CHECK_TOOLS = {1: {"regime"}, 2: {"funding_extremes", "positioning", "funding"}, 3: {"scheduled_events", "calendar"},
               4: {"market_table"}, 5: {"evidence", "stops_report", "insights"}, 6: {"similar"},
               7: {"funding", "cross_venue", "fear_greed", "calendar"}, 8: {"event_history", "similar", "evidence"}}


def checklist_missing(log) -> List[str]:
    """Checklist items (1-8) with no tool call behind them yet. One definition, shared with the
    benchmark scorer, so 'covered' means the same thing everywhere."""
    tools = {e.get("tool") for e in log if isinstance(e, dict)}
    out = []
    for i, need in CHECK_TOOLS.items():
        if not (tools & need):
            out.append(f"{i}. {CHECKLIST[i - 1]}")
    return out


CHECKLIST = [
    "What is the regime, and did it change since my last market view?",
    "What is crowded? (positioning extremes, funding extremes)",
    "What is scheduled in the next 7 days that could move my candidates?",
    "What moved unusually this week, and why might it have?",
    "What does my own record say about the setups I am about to take, in this regime?",
    "What happened in the situations most similar to each candidate?",
    "What is the market already pricing? (funding, basis, breadth)",
    "What would make me wrong, and by when? (check event_history / similar / evidence for how this kind of trade failed before)",
]


def chain_point(cp):
    """{day, move: fraction} -> {day, pct: percent}; a legacy {day, pct} passes through; junk -> None."""
    if not isinstance(cp, dict):
        return None
    try:
        day = int(cp.get("day"))
        if "move" in cp:
            return {"day": day, "pct": round(float(cp["move"]) * 100.0, 2)}
        return {"day": day, "pct": float(cp.get("pct"))}
    except (TypeError, ValueError):
        return None


class InvestigatorAgent(LLMAgent):
    name = "investigator"
    setup = "investigator"
    features = ["mom_7d_skip1", "r_1d", "r_7d", "r_30d", "px_vs_sma50", "px_vs_sma200", "rv_7d",
                "rsi_14", "vol_zscore", "atr_pct", "drawdown",
                "beta_btc", "r2_btc", "idio_vol", "resid_mom_7d_skip1"]      # cross-sectional layer (feat_cross)

    def __init__(self, memory=None, seed=0, max_orders=6, spec=None, max_rounds=3, max_calls_per_round=6):
        super().__init__(memory, seed, max_orders, spec)
        self.max_rounds, self.max_calls = max_rounds, max_calls_per_round
        self.last_log: List[Dict] = []
        self.last_cards: List[Dict] = []
        self.last_view = ""
        self.last_chains: Dict[str, Dict] = {}
        self.last_strategist_raw = ""
        self.last_call_meta: Dict = {}
        self.last_strategist_meta: Dict = {}
        self.last_skeptic: Dict = {}
        self.last_label_fixes: List[Dict] = []
        self.last_events: Dict = {}
        self.last_auto_cover: Dict = {}
        self.last_portfolio: Dict = {}
        self.last_portfolio_after: Dict = {}
        self.last_links_shown: Dict = {}
        self.last_checklist_gate: List[str] = []
        self.last_checklist_missing: List[str] = []
        self.risk = None                      # set by the runner: RiskHat(data, memory, book, xsec)
        self.last_risk: Dict = {}
        self.last_skeptic_meta: Dict = {}
        self._data = None

    # ---- one model call; thinking toggled per request (llama.cpp chat_template_kwargs) ----
    def _chat(self, messages: List[Dict], thinking: bool = False, max_tokens: int = 1800) -> str:
        kind, _, model = self.spec.partition(":")
        if kind != "openai":
            return self._ask("\n\n".join(m["content"] for m in messages))
        model, _, base = model.partition("@")
        base = base or "http://localhost:8080/v1"
        body = {"model": model, "temperature": 0.3 if thinking else 0.2, "max_tokens": max_tokens,
                "messages": messages, "chat_template_kwargs": {"enable_thinking": bool(thinking)}}
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        resp = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=3600) as r:
                    resp = json.loads(r.read())
                break
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
                self.last_call_meta = {"error": f"{type(e).__name__}: {str(e)[:120]}", "attempt": attempt + 1}
                if attempt == 2 or not ensure_server(base):
                    raise
        if resp is None:
            raise RuntimeError("model server gave no response")
        ch = resp["choices"][0]
        msg = ch["message"]
        self.last_call_meta = {"finish": ch.get("finish_reason"), "usage": resp.get("usage"),
                               "reasoning_chars": len(msg.get("reasoning_content") or ""), "thinking": thinking}
        return msg.get("content") or ""

    @staticmethod
    def _json(raw: str):
        """The first {...} object in the answer, or None. Anything that is not a dict is None."""
        s, e = raw.find("{"), raw.rfind("}")
        try:
            v = json.loads(raw[s:e + 1])
        except Exception:
            return None
        return v if isinstance(v, dict) else None

    @staticmethod
    def _num(v, default: float, lo: float, hi: float) -> float:
        """A model-written number, clamped; garbage becomes the default (never a crash)."""
        try:
            x = float(v)
        except (TypeError, ValueError):
            return default
        if x != x:                      # NaN
            return default
        return min(max(x, lo), hi)

    def observe(self, data: AsOf, t: int, open_positions: List[str]) -> Observation:
        self._data = data
        return super().observe(data, t, open_positions)

    def decide(self, obs: Observation) -> List[Order]:
        self.last_risk, self.last_skeptic, self.last_label_fixes = {}, {}, []       # never carry a hat's log into the next decision
        self.last_checklist_gate, self.last_strategist_raw = [], ""
        tab, labels = self._mask(obs)              # masked table; coin -> label
        unmask = self._labels[obs.t]                # label -> coin
        held = [labels[c] for c in obs.open_positions if c in labels]
        # the book as the desk sees it, before anything is proposed (labels only reach the model)
        self.last_portfolio = self.risk.portfolio(obs.t, labels=labels) if self.risk is not None else {}
        self.last_portfolio_after = {}
        book_words = self.last_portfolio.get("words", "")
        book_rows = [{k: v for k, v in r.items() if k != "coin"} for r in self.last_portfolio.get("positions", [])]
        box = Toolbox(self._data, self.memory, obs.t, obs.regime, tab, held, self.setup, coin_map=unmask)

        # ---------------- Hat 1: Investigator ----------------
        spec_lines = "\n".join(f"- {k}: {v}" for k, v in Toolbox.SPEC.items())
        sys_msg = (
            "You are the investigator on a crypto perpetuals desk, inside a simulation. Coins are anonymised C1..Cn, "
            "the date is hidden, nothing after 'now' exists. You cannot see the market table until you ask for it. "
            "Work through the checklist by asking follow-up questions and answering each with a TOOL CALL. "
            "A morning sheet (regime, unusual movers, momentum extremes) is given; call market_table for any other slice. "
            "Tools that take `coin` take ONE label like C12; there is no ALL. "
            "Funding sign convention: positive funding = longs pay shorts = crowded longs; negative funding = shorts pay "
            "longs = crowded shorts (squeeze risk is UP). "
            f"Positions already open: {held or 'none'}. {book_words}\n\nTOOLS (name: arguments -> result):\n{spec_lines}\n\n"
            "CHECKLIST:\n" + "\n".join(f"{i + 1}. {q}" for i, q in enumerate(CHECKLIST)) +
            "\n\nEach round answer ONLY with JSON: {\"followups\":[{\"question\":\"...\",\"tool\":\"name\",\"args\":{...}}]} "
            f"(max {self.max_calls} per round). When you have enough, answer "
            "{\"done\":true,\"market_view\":\"3 lines\",\"cards\":[{\"fact\":\"one evidence fact with a number\","
            "\"source\":\"tool\"}],\"candidates\":[\"C3\",\"C7\"]}. Facts on cards must come from tool results, never from assumption.")
        sheet = {
            "regime": box.call("regime", {}),
            "most_unusual_volume_10": box.call("market_table", {"sort_by": "vol_zscore", "top_n": 10,
                                                                 "columns": ["vol_zscore", "r_1d", "r_7d", "rsi_14", "px_vs_sma50"]}),
            "strongest_7d_momentum_8": box.call("market_table", {"sort_by": "mom_7d_skip1", "top_n": 8,
                                                                  "columns": ["mom_7d_skip1", "r_30d", "px_vs_sma50", "rv_7d", "rsi_14"]}),
            "weakest_7d_momentum_8": box.call("market_table", {"sort_by": "mom_7d_skip1", "top_n": 8, "ascending": True,
                                                                "columns": ["mom_7d_skip1", "r_30d", "px_vs_sma50", "rv_7d", "rsi_14"]}),
            "events_next_7d": box.call("calendar", {"days": 7}),
            "measured_links": box.call("links", {}),
        }
        self.last_events = sheet["events_next_7d"]
        self.last_links_shown = sheet["measured_links"]
        msgs = [{"role": "system", "content": sys_msg},
                {"role": "user", "content": "MORNING SHEET (already fetched for you; the full table has "
                 f"{len(tab)} coins - ask market_table for other slices):" + chr(10) + json.dumps(sheet, default=str)[:7000] +
                 chr(10) + chr(10) + "Begin. Round 1: ask your first follow-up questions."}]
        cards, view, cands = [], "", []
        done = False
        extra_round = 0                                  # one extra round is granted when the checklist is incomplete
        rnd = 0
        while rnd < self.max_rounds + extra_round:
            box.round = rnd + 1
            raw = self._chat(msgs, thinking=False, max_tokens=1200)
            parsed = self._json(raw) or {}
            msgs.append({"role": "assistant", "content": raw[:4000]})
            if parsed.get("done"):
                missing = checklist_missing(box.log)
                if missing and extra_round < 2:
                    # the engine, not the model, decides when the checklist is covered (spec P3); two extra rounds max
                    extra_round += 1
                    msgs.append({"role": "user", "content": "NOT DONE. The checklist still has unanswered items: " + "; ".join(missing) +
                                 ". Ask them now as follow-ups (JSON), then answer done=true."})
                    self.last_checklist_gate = missing
                    rnd += 1
                    continue
                cards = parsed.get("cards") or []
                view = str(parsed.get("market_view", ""))[:600]
                cands = [str(x) for x in (parsed.get("candidates") or [])]
                done = True
                break
            results = []
            for fu in (parsed.get("followups") or [])[: self.max_calls]:
                if not isinstance(fu, dict):
                    continue
                res = box.call(str(fu.get("tool", "")), fu.get("args") if isinstance(fu.get("args"), dict) else {})
                results.append({"question": fu.get("question", ""), "tool": fu.get("tool"), "result": res})
            payload = json.dumps(results, default=str)
            if len(payload) > 9000:
                payload = payload[:9000] + "...(truncated: ask for smaller slices)"
            last = rnd == self.max_rounds + extra_round - 2
            msgs.append({"role": "user", "content": "RESULTS:\n" + payload + (
                "\n\nThis is your LAST round: answer now with done=true, market_view, cards, candidates."
                if last else "\n\nNext round: more follow-ups, or done=true with market_view, cards, candidates.")})
            rnd += 1
        if not done:
            raw = self._chat(msgs + [{"role": "user", "content": "Answer now with done=true, market_view, cards, candidates."}],
                             False, 900)
            parsed = self._json(raw) or {}
            cards = parsed.get("cards") or []
            view = str(parsed.get("market_view", ""))[:600]
            cands = [str(x) for x in (parsed.get("candidates") or [])]
        cards = [c if isinstance(c, dict) else {"fact": str(c), "source": "unknown"} for c in (cards if isinstance(cards, list) else [])]
        # outside view first (spec B46): whatever the model did not ask, the engine asks for it
        auto = {}
        if checklist_missing(box.log):
            box.round = 99                                       # marks engine-made calls in the log
            tools_now = {e.get("tool") for e in box.log}
            if not tools_now & CHECK_TOOLS[5]:
                auto["own_record"] = {"long": box.call("evidence", {"side": "long"}), "short": box.call("evidence", {"side": "short"})}
            if not tools_now & CHECK_TOOLS[6]:
                auto["similar"] = {c: box.call("similar", {"coin": c}) for c in cands[:6] if c in tab.index}
            if not tools_now & CHECK_TOOLS[8]:
                auto["how_this_failed_before"] = {c: box.call("event_history", {"event_type": "funding", "coin": c}) for c in cands[:3] if c in tab.index}
            if not tools_now & CHECK_TOOLS[3]:
                auto["calendar"] = box.call("calendar", {"days": 7})
        self.last_auto_cover = auto
        self.last_log, self.last_cards, self.last_view = list(box.log), cards, view
        self.last_checklist_missing = checklist_missing(box.log)
        if self.memory is not None and view:
            self.memory.write_note(obs.t, "market_view", view, "investigator")

        # ---------------- Hat 2: Strategist (thinking on) ----------------
        cand_tab = tab.loc[[c for c in cands if c in tab.index]].copy() if cands else tab.iloc[0:0]
        if "rv_7d" in cand_tab.columns:
            cand_tab.insert(0, "typical_daily_move_pct", (cand_tab["rv_7d"] / math.sqrt(365) * 100).round(2))
        if len(cand_tab) and getattr(self._data, "xsec", None):
            # the engine's cross-sectional facts per candidate: own (residual) daily move, BTC share, crash beta, cluster
            xf = {lab: self._xsec_facts(obs.t, unmask[lab]) for lab in cand_tab.index if lab in unmask}
            cand_tab.insert(0, "own_daily_move_pct", [xf[l].get("own_daily_move_pct") for l in cand_tab.index])
            cand_tab.insert(1, "btc_share_r2", [xf[l].get("share_of_moves_explained_by_btc") for l in cand_tab.index])
            cand_tab.insert(2, "beta_crash_days", [xf[l].get("beta_to_btc_on_crash_days") for l in cand_tab.index])
            cand_tab.insert(3, "cluster", [xf[l].get("cluster") for l in cand_tab.index])
            # the plan numbers the desk will enforce, computed here so the model copies instead of calculates
            dm = cand_tab["own_daily_move_pct"].astype(float)
            cand_tab.insert(4, "stop_pct_allowed", [f"{a / 100:.4f}-{b / 100:.4f}" if a == a else None for a, b in zip(1.5 * dm, 3.0 * dm)])
            cand_tab.insert(5, "target_pct_min", [round(2.0 * v / 100, 4) if v == v else None for v in dm])
            cand_tab.insert(6, "hold_days_for_2x_3x_4x_moves", ["4/9/14"] * len(cand_tab))
        cand_rows = cand_tab.round(4).to_csv() if len(cand_tab) else ""
        strat = (
            "You are the strategist. Using ONLY the evidence cards and market view below (from your investigator), "
            "write trades as CHAINS: observation -> mechanism -> expected move -> falsifier -> checkpoint -> order. "
            "Funding sign convention: positive funding = longs pay shorts = crowded longs; negative = shorts pay longs = "
            "crowded shorts (squeeze risk is UP). Check each chain's direction against this before writing it. "
            f"Regime: {obs.regime}. Positions already open: {held or 'none'}. Costs: 4.5 bps taker + half spread each side, "
            "$100 per trade. Each candidate row shows own_daily_move_pct (the coin's own one-day move after removing "
            "BTC's part; use this for stops), btc_share_r2 (how much of it is just BTC), beta_crash_days (how hard it "
            "falls on BTC crash days) and cluster (coins in one cluster are one bet). Set stop_pct at 1.5 to 3 own "
            "daily moves (a stop inside one daily move is stopped by noise, not by being wrong) and target_pct at "
            "2 to 4 own daily moves and at least 1.5x the stop. Each row gives stop_pct_allowed (copy a value inside it), "
            "target_pct_min, and hold_days_for_2x_3x_4x_moves = 4/9/14: a target of 2 own moves needs hold_days 4, "
            "3 moves needs 9, 4 moves needs 14 (copy these; do not compute your own). The risk desk (code) bounces "
            "orders outside these numbers. "
            "The falsifier must be smaller than the stop, so it can fire first."
            f"\n\nTHE BOOK NOW (engine; the desk enforces the room stated here - a trade outside it is rejected, not bounced):\n"
            f"{book_words}\n{json.dumps(book_rows, default=str)[:1500]}"
            f"\n\nSIMILAR PAST SITUATIONS for the candidates (engine, k-NN over your own trades):\n"
            f"{json.dumps({c: box.call('similar', {'coin': c}) for c in cands[:6] if c in tab.index}, default=str)[:1200]}"
            f"\n\nYOUR OWN RECORD (read this BEFORE writing the chains - the outside view comes first):\n"
            f"{json.dumps({'longs': box.call('evidence', {'side': 'long'}), 'shorts': box.call('evidence', {'side': 'short'}), 'stops_long': box.call('stops_report', {'side': 'long'}), 'stops_short': box.call('stops_report', {'side': 'short'})}, default=str)[:1800]}"
            f"\n\nMEASURED LINKS (what the data says about shock -> forward return; a chain whose links are all "
            f"'unmeasured' is a hypothesis and will be confidence-capped by the risk desk):\n{json.dumps(self.last_links_shown, default=str)[:1500]}"
            f"\n\nMARKET VIEW:\n{view}\n\nEVIDENCE CARDS:\n" +
            "\n".join(f"- {c.get('fact')} [{c.get('source')}]" for c in cards) +
            (f"\n\nCANDIDATE ROWS:\n{cand_rows}" if cand_rows else "") +
            f"\n\nDecide up to {self.max_orders} trades (or none). Answer ONLY with JSON: "
            "{\"orders\":[{\"label\":\"C3\",\"side\":\"long|short\",\"stop_pct\":0.06,\"target_pct\":0.12,\"hold_days\":7,"
            "\"confidence\":0.6,\"mechanism\":\"why this moves\",\"falsifier\":{\"day\":2,\"move\":-0.03},"
            "\"checkpoint\":{\"day\":4,\"move\":0.04},\"thesis\":\"one sentence\"}],\"notes\":\"...\"}. "
            "`label` is the coin's label exactly as it appears in the table (C3, C57), nothing added. "
            "ALL sizes are FRACTIONS of price: stop_pct 0.06 = 6%, and falsifier/checkpoint `move` is the PRICE move "
            "as a fraction by that day (for a short: falsifier {day:2, move:+0.03} = price up 3% proves me wrong; "
            "checkpoint {day:4, move:-0.04} = price should be down 4% by day 4). "
            "confidence = your honest probability the trade ends positive after costs.")
        budget = int(os.environ.get("SIM_THINK_TOKENS", "7000"))
        raw = self._chat([{"role": "user", "content": strat}], thinking=True, max_tokens=budget)
        self.last_strategist_meta = dict(self.last_call_meta)
        if not raw.strip():
            # thinking used the whole budget: answer once more without thinking (fast) rather than trade nothing
            raw = self._chat([{"role": "user", "content": strat}], thinking=False, max_tokens=1500)
            self.last_strategist_meta["fallback_no_thinking"] = True
        self.last_strategist_raw = raw[:3000]
        parsed = self._json(raw) or {}
        out: List[Order] = []
        self.last_chains = {}
        self.last_label_fixes = []
        for o in (parsed.get("orders") or [])[: self.max_orders]:
            if not isinstance(o, dict):
                continue
            label = str(o.get("label", "")).strip()
            coin = unmask.get(label)
            if not coin:
                # tolerate a decorated label ("C162_Squeeze"): keep the leading C<number> token
                i = 1
                while label[:1] == "C" and i < len(label) and label[i].isdigit():
                    i += 1
                head = label[:i] if i > 1 else ""
                coin = unmask.get(head)
                if coin:
                    self.last_label_fixes.append({"given": label, "used": head})
            side = o.get("side")
            if not coin or side not in SIDES or coin in obs.open_positions or any(x.coin == coin for x in out):
                continue
            self._conf[coin] = self._num(o.get("confidence", 0.5), 0.5, 0.01, 0.99)
            chain = {"mechanism": str(o.get("mechanism", ""))[:300], "falsifier": chain_point(o.get("falsifier")),
                     "checkpoint": chain_point(o.get("checkpoint")), "thesis": str(o.get("thesis", ""))[:300]}
            self.last_chains[coin] = chain
            f_day, f_pct = 0, None
            try:
                f_day, f_pct = int((chain["falsifier"] or {}).get("day")), float((chain["falsifier"] or {}).get("pct"))
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            out.append(Order(coin, side, self._num(o.get("stop_pct", 0.06), 0.06, 0.005, 0.60),
                             self._num(o.get("target_pct", 0.12), 0.12, 0.005, 1.50),
                             int(self._num(o.get("hold_days", 7), 7, 1, 30)), json.dumps(chain), f"investigator,{side}",
                             falsifier_day=f_day, falsifier_pct=f_pct))
        if out and os.environ.get("SIM_SKEPTIC", "1") != "0":
            out = self._skeptic(out, obs, box, labels, cards, view)
        if out and self.risk is not None:
            out = self._risk_pass(out, obs, tab, labels)
        return out

    def _xsec_facts(self, t: int, coin: str) -> Dict:
        """Engine-written facts from the cross-sectional layer: how much of this coin is BTC,
        its own daily move, its crash-day beta, its cluster."""
        x = getattr(self._data, "xsec", None)
        if not x:
            return {"note": "cross-sectional layer not loaded"}
        def at(key):
            f = x["frames"].get(key)
            if f is None or coin not in f.columns:
                return None
            s = f[coin]; s = s[s.index <= t].dropna()
            return None if s.empty else round(float(s.iloc[-1]), 3)
        r2, b, bs, idio, cl = at("r2_btc"), at("beta_btc"), at("beta_stress"), at("idio_daily_move_pct"), at("cluster_id")
        u = x["universe"]; u = u[u.index <= t].dropna(subset=["common_share"]) if "common_share" in u.columns else None
        regime = None
        if u is not None and len(u):
            cs = float(u["common_share"].iloc[-1])
            regime = f"market one-trade share {cs:.0%}: " + ("STRESS (>55%)" if cs > 0.55 else "speculative (<30%)" if cs < 0.30 else "mixed")
        return {"share_of_moves_explained_by_btc": r2, "beta_to_btc_normal_days": b, "beta_to_btc_on_crash_days": bs,
                "own_daily_move_pct": idio, "cluster": None if cl is None else int(cl),
                "reading": (None if r2 is None else ("mostly its own story" if r2 < 0.3 else "mostly a BTC trade" if r2 > 0.6 else "half BTC, half its own")),
                "market_regime": regime}

    # ---------------- Hat 4: Risk (code; one replan round with the strategist) ----------------
    def _risk_pass(self, orders: List[Order], obs: Observation, tab, labels: Dict[str, str]) -> List[Order]:
        equity = self.risk.book.equity(obs.t)
        kept, verdicts, bounces = self.risk.review(orders, obs.t, self._conf, tab, labels, self.setup, equity)
        log: Dict = {"round1": verdicts, "bounces": bounces}
        if bounces:
            by_label = {labels.get(o.coin, o.coin): o for o in orders}
            shown = []                                   # the same numbers in the strategist's own units
            for b in bounces:
                sg = dict(b["suggested"])
                if "falsifier_pct" in sg:
                    sg["falsifier"] = {"day": 2, "move": round(sg.pop("falsifier_pct") / 100.0, 4)}
                shown.append({"label": b["label"], "violations": b["violations"], "suggested": sg})
            prompt = (
                "You are the strategist. The risk desk (code, not a person) bounced these orders with the numbers "
                "that decided it. For each label either accept the suggested numbers (action accept - the usual "
                "answer), or change ONLY the flagged fields (action replan; keep every other number exactly as it "
                "was; fractions of price; falsifier `move` signed), or drop the order. Answer ONLY with JSON: "
                '{"orders":[{"label":"C3","action":"accept|replan|drop","stop_pct":0.12,"target_pct":0.24,'
                '"hold_days":6,"falsifier":{"day":2,"move":-0.05},"event_note":"how the scheduled event affects this trade"}]}.'
                + NL + NL + json.dumps(shown, default=str))
            raw = self._chat([{"role": "user", "content": prompt}], thinking=False, max_tokens=700)
            log["replan_raw"] = raw[:2000]
            parsed = self._json(raw) or {}
            resubmit: List[Order] = []
            answered = set()
            for d in (parsed.get("orders") or []):
                lab = str(d.get("label", "")).strip(); o = by_label.get(lab)
                b = next((x for x in bounces if x["label"] == lab), None)
                if o is None or b is None:
                    continue
                answered.add(lab)
                act = str(d.get("action", "drop")).lower()
                if act == "accept":
                    self.risk.apply_fix(o, b["suggested"]); resubmit.append(o)
                elif act == "replan":
                    if d.get("event_note"):
                        try:
                            ch_ = json.loads(o.thesis or "{}")
                        except Exception:
                            ch_ = {}
                        ch_["event_note"] = str(d.get("event_note"))[:300]; o.thesis = json.dumps(ch_)
                    o.stop_pct = self._num(d.get("stop_pct", o.stop_pct), o.stop_pct, 0.005, 0.60)
                    o.target_pct = self._num(d.get("target_pct", o.target_pct), o.target_pct, 0.005, 1.50)
                    o.hold_days = int(self._num(d.get("hold_days", o.hold_days), o.hold_days, 1, 30))
                    f = d.get("falsifier") if isinstance(d.get("falsifier"), dict) else {}
                    if "move" in f and "day" in f:
                        o.falsifier_day = int(self._num(f["day"], 2, 1, 14))
                        o.falsifier_pct = round(self._num(f["move"], 0.0, -0.5, 0.5) * 100.0, 2)
                    resubmit.append(o)
            # no usable answer for a bounced order (empty / garbage JSON / label missing): the desk's numbers apply
            for b in bounces:
                if b["label"] not in answered:
                    o = by_label.get(b["label"])
                    if o is not None:
                        self.risk.apply_fix(o, b["suggested"]); resubmit.append(o)
                        log.setdefault("unanswered_desk_fixed", []).append(b["label"])
            kept2, verdicts2, bounces2 = self.risk.review(resubmit, obs.t, self._conf, tab, labels, self.setup, equity, pending=kept)
            log["round2"] = verdicts2
            # still bounced with a full fix available: the desk owns the numbers - apply them and review once more
            if bounces2:
                fixed = []
                for b in bounces2:
                    o = by_label.get(b["label"])
                    if o is not None:
                        self.risk.apply_fix(o, b["suggested"]); fixed.append(o)
                kept3, verdicts3, bounces3 = self.risk.review(fixed, obs.t, self._conf, tab, labels, self.setup, equity, pending=kept + kept2)
                for v in verdicts3:
                    v["desk_fixed"] = True
                log["round3_desk_fixed"] = verdicts3
                kept2 = kept2 + kept3
                bounces2 = bounces3
            log["dropped_after_replan"] = sorted(set(
                [b["label"] for b in bounces2] + [v["label"] for v in verdicts2 if v.get("action") == "reject"] +
                [labels.get(o.coin, o.coin) for o in orders if o not in kept and o not in kept2 and o not in resubmit]))
            kept = kept + kept2
        for o in kept:
            try:
                chain = json.loads(o.thesis)
            except Exception:
                chain = {}
            rv = next((v for v in (log.get("round2", []) + log["round1"]) if v.get("coin") == o.coin and v.get("action") == "accept"), None)
            chain["risk"] = {"size_mult": o.size_mult, "stop_pct": o.stop_pct, "target_pct": o.target_pct,
                             "checks": (rv or {}).get("checks")}
            o.thesis = json.dumps(chain)
        self.last_risk = log
        self.last_portfolio_after = self.risk.portfolio(obs.t, pending=kept, labels=labels)
        return kept

    # ---------------- Hat 3: Skeptic (thinking off) ----------------
    def _skeptic(self, orders: List[Order], obs: Observation, box: Toolbox, labels: Dict[str, str],
                 cards: List[Dict], view: str) -> List[Order]:
        """Attack the weakest order. The ENGINE gathers the counter-evidence (own record, similar
        situations, crowd, funding, volatility vs the stop, correlation between the orders); the
        model must veto, resize or let each stand, with a reason. Never grows a trade."""
        tab = box.table
        dossier = []
        for o in orders:
            lab = labels.get(o.coin, o.coin)
            row = tab.loc[lab] if lab in tab.index else None
            # the SAME daily move the risk desk uses (own/residual move first, raw 7-day vol as fallback),
            # so the skeptic and the desk never disagree about what "1.5 daily moves" means
            daily_sigma, sigma_src = None, None
            if self.risk is not None:
                daily_sigma, sigma_src = self.risk.daily_move(obs.t, o.coin, tab, lab)
            elif row is not None and "rv_7d" in row.index and row["rv_7d"] == row["rv_7d"]:
                daily_sigma, sigma_src = float(row["rv_7d"]) / math.sqrt(365) * 100, "rv_7d"
            daily_sigma = None if daily_sigma is None else round(daily_sigma, 2)
            d = {"label": lab, "side": o.side, "stop_pct": o.stop_pct, "target_pct": o.target_pct, "hold_days": o.hold_days,
                 "confidence": self._conf.get(o.coin), "chain": self.last_chains.get(o.coin, {}),
                 "typical_daily_move_pct": daily_sigma, "daily_move_source": sigma_src,
                 "stop_in_daily_moves": None if not daily_sigma else round(o.stop_pct * 100 / daily_sigma, 2),
                 "features": {k: round(float(row[k]), 4) for k in ("r_1d", "r_7d", "r_30d", "px_vs_sma50", "rsi_14", "vol_zscore", "drawdown")
                              if row is not None and k in row.index and row[k] == row[k]},
                 "btc_relationship": self._xsec_facts(obs.t, o.coin),
                 "funding": box.call("funding", {"coin": lab}),
                 "positioning": box.call("positioning", {"coin": lab}),
                 "similar_situations": box.call("similar", {"coin": lab}),
                 "own_record_this_side": box.call("evidence", {"side": o.side}),
                 "stops_report_this_side": box.call("stops_report", {"side": o.side})}
            dossier.append(d)
        extra = {"active_insights": box.call("insights", {}), "calibration": box.call("calibration", {}),
                 "book": {"words": self.last_portfolio.get("words"), "positions": [{k: v for k, v in r.items() if k != "coin"} for r in self.last_portfolio.get("positions", [])]}}
        labs = [labels.get(o.coin, o.coin) for o in orders] + list(box.open_positions)
        if len(labs) >= 2:
            extra["correlations"] = box.call("correlations", {"coins": labs})
        prompt = (
            "You are the skeptic on a crypto perpetuals desk, inside a simulation. The strategist has proposed the orders "
            "below. Your only job is to find what is wrong with them before money is risked. For EACH order check: "
            "(1) does the mechanism contradict the evidence cards or the funding sign convention (positive funding = longs "
            "pay = crowded longs; negative = crowded shorts, squeeze risk is UP)? (2) is the stop tighter than the coin's "
            "typical daily move (stop_in_daily_moves < 1.5 means noise alone will likely stop it)? (3) does the own record, "
            "similar situations or an active insight argue against it? (4) are the orders (and open positions) so correlated "
            "that they are one bet? (5) is the falsifier on the wrong side of the trade or unreachable before the stop? "
            "(6) is the stated confidence honest given the calibration record? "
            "If the idea holds but the stop or target is wrong for the coin's volatility, REPLAN it (give new stop_pct "
            "and target_pct as fractions, stop at 1.5-3 typical daily moves) rather than veto; veto is for a broken thesis. "
            f"Regime: {obs.regime}." + NL + NL + "MARKET VIEW:" + NL + view + NL + NL + "EVIDENCE CARDS:" + NL +
            NL.join(f"- {c.get('fact')} [{c.get('source')}]" for c in cards) +
            NL + NL + "PROPOSED ORDERS WITH COUNTER-EVIDENCE (gathered by the engine, not by the strategist):" + NL +
            json.dumps(dossier, default=str)[:9000] + NL + NL + "CONTEXT:" + NL + json.dumps(extra, default=str)[:3000] +
            NL + NL + "Answer ONLY with JSON: {\"weakest\":\"C3\",\"why_weakest\":\"one sentence\","
            "\"verdicts\":[{\"label\":\"C3\",\"action\":\"veto|resize|replan|stand\",\"size_mult\":0.5,"
            "\"stop_pct\":0.12,\"target_pct\":0.2,\"reason\":\"one sentence naming the broken link\"}]}. "
            "size_mult is only used for resize and must be between 0.25 and 0.9; stop_pct/target_pct only for replan. "
            "Let an order stand only if you found nothing that breaks it.")
        raw = self._chat([{"role": "user", "content": prompt}], thinking=False, max_tokens=1200)
        self.last_skeptic_meta = dict(self.last_call_meta)
        parsed = self._json(raw) or {}
        verdicts = {str(v.get("label")): v for v in (parsed.get("verdicts") or []) if isinstance(v, dict)}
        kept: List[Order] = []
        applied = []
        for o in orders:
            lab = labels.get(o.coin, o.coin)
            v = verdicts.get(lab, {})
            action = str(v.get("action", "stand")).lower()
            reason = str(v.get("reason", ""))[:300]
            said = [w for w in ("veto", "resize", "replan", "stand") if w in reason.lower()]
            if said and action not in said:
                v["words_vs_json"] = f"reason mentions {said}, action is {action}"      # the JSON is what counts; logged
            if action == "veto":
                applied.append({"label": lab, "coin": o.coin, "action": "veto", "reason": reason})
                self._conf.pop(o.coin, None)
                continue
            replanned = None
            if action == "resize":
                try:
                    o.size_mult = min(max(float(v.get("size_mult", 0.5)), 0.25), 0.9)
                except (TypeError, ValueError):
                    o.size_mult = 0.5
            elif action == "replan":
                try:
                    new_stop = min(max(float(v.get("stop_pct", o.stop_pct)), 0.02), 0.40)
                    new_target = min(max(float(v.get("target_pct", o.target_pct)), new_stop), 0.80)
                except (TypeError, ValueError):
                    new_stop, new_target = o.stop_pct, o.target_pct
                replanned = {"from": [o.stop_pct, o.target_pct], "to": [new_stop, new_target]}
                o.stop_pct, o.target_pct = new_stop, new_target
                # the falsifier must still be able to fire before the new stop
                if o.falsifier_pct is not None and abs(o.falsifier_pct) >= new_stop * 100:
                    o.falsifier_pct = None; o.falsifier_day = 0
            else:
                action = "stand"
            chain = self.last_chains.get(o.coin, {})
            chain["skeptic"] = {"action": action, "size_mult": o.size_mult, "replan": replanned, "reason": reason}
            o.thesis = json.dumps(chain)
            applied.append({"label": lab, "coin": o.coin, "action": action, "size_mult": o.size_mult,
                            "stop_pct": o.stop_pct, "target_pct": o.target_pct, "replan": replanned, "reason": reason,
                            "words_vs_json": v.get("words_vs_json")})
            kept.append(o)
        self.last_skeptic = {"weakest": parsed.get("weakest"), "why_weakest": parsed.get("why_weakest"),
                             "verdicts": applied, "dossier": dossier, "raw": raw[:3000]}
        return kept

    def lesson(self, obs_at_open: Observation, tr: Trade) -> str:
        base = super().lesson(obs_at_open, tr)
        try:
            chain = json.loads(tr.thesis)
        except Exception:
            return base
        path = json.loads(getattr(tr, "path_pct", "[]") or "[]")     # daily moves IN THE TRADE'S FAVOUR, %
        sgn = 1.0 if tr.side == "long" else -1.0
        verdict = []
        for key in ("checkpoint", "falsifier"):
            cp = chain.get(key) or {}
            try:
                day, pct = int(cp.get("day")), float(cp.get("pct"))
            except (TypeError, ValueError, AttributeError):
                continue
            if day > len(path) > 0:
                verdict.append(f"{key} day {day}: closed on day {len(path)} before it could be judged")
                continue
            if 0 < day <= len(path):
                actual_favor = path[day - 1]                 # already in the trade's favour
                target_favor = sgn * pct                     # price move -> favour move
                if key == "checkpoint":
                    verdict.append(f"checkpoint day {day}: expected price {pct:+.0f}%, got {sgn*actual_favor:+.1f}% -> "
                                   f"{'HIT' if actual_favor >= target_favor else 'MISSED'}")
                else:
                    verdict.append(f"falsifier day {day}: limit price {pct:+.0f}%, got {sgn*actual_favor:+.1f}% -> "
                                   f"{'TRIGGERED' if actual_favor <= target_favor else 'not triggered'}")
        mech = chain.get("mechanism", "")
        return base + (f" Mechanism: {mech}." if mech else "") + (" " + "; ".join(verdict) if verdict else "")


AGENTS["investigator"] = InvestigatorAgent
