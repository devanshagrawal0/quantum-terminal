"""Protocol scorer - docs/BENCHMARK_PROTOCOL.md applied mechanically to one or more runs.

    python scripts/benchmark.py RUN_DIR [RUN_DIR ...] [--memory DB_FOR_RUN1 DB_FOR_RUN2 ...] [--label NAME ...]

For each run: per category, the rung reached (20/40/60/80/100), the score
(rung + 10 x share of next-rung conditions met), and the first unmet condition of the next
rung. Every condition reads an artefact; none reads the model's words as evidence.
`judged.json` in the run folder supplies the single human input (C6 view consistency).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sim.data import daily_funding, STORE          # noqa: E402
from sim.xsec import xsec                           # noqa: E402

CHECK_TOOLS = {1: {"regime"}, 2: {"funding_extremes", "positioning", "funding"}, 3: {"scheduled_events"},
               5: {"evidence", "stops_report", "insights"}, 6: {"similar"}, 7: {"funding", "cross_venue", "fear_greed"}}


# ------------------------------------------------------------------ artefacts
class Run:
    def __init__(self, path, mem):
        self.path = Path(path); self.id = self.path.name
        self.dec = [json.loads(l) for l in open(self.path / "decisions.jsonl", encoding="utf-8")]
        self.trades = pd.read_csv(self.path / "trades.csv") if (self.path / "trades.csv").exists() else pd.DataFrame()
        self.summary = json.loads((self.path / "summary.json").read_text()) if (self.path / "summary.json").exists() else {}
        self.judged = json.loads((self.path / "judged.json").read_text()) if (self.path / "judged.json").exists() else {}
        local = self.path / "memory.db"
        mem = str(local) if local.exists() else mem                # a run's own copy beats any global db
        self.mem = sqlite3.connect(mem) if mem and Path(mem).exists() else None
        self.orders = [(d["t"], o) for d in self.dec for o in d["orders"]]
        self.x = xsec(); self.fund = daily_funding()

    # helpers ------------------------------------------------------------
    def file(self, name):
        p = self.path / name
        return json.loads(p.read_text()) if p.exists() else None

    def table_exists(self, conn, name):
        if conn is None:
            return False
        return conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

    def store(self):
        return sqlite3.connect(f"file:{STORE}?mode=ro", uri=True)

    def lessons(self):
        if self.mem is None:
            return []
        return [r[0] or "" for r in self.mem.execute("SELECT lesson FROM experience WHERE run_id=?", (self.id,))]

    def own_move(self, t, coin):
        f = self.x["frames"]["idio_daily_move_pct"]
        if coin not in f.columns:
            return None
        s = f[coin]; s = s[s.index <= t].dropna()
        return None if s.empty else float(s.iloc[-1])

    def risk_verdicts(self, rounds=("round1", "round2", "round3_desk_fixed")):
        out = []
        for d in self.dec:
            rk = d.get("risk") or {}
            for r in rounds:
                out += rk.get(r, [])
        return out

    def skeptic_verdicts(self):
        return [v for d in self.dec for v in ((d.get("skeptic") or {}).get("verdicts") or [])]

    def dossiers(self):
        return [dd for d in self.dec for dd in ((d.get("skeptic") or {}).get("dossier") or [])]

    def chains(self):
        out = []
        for _, o in self.orders:
            try:
                out.append(json.loads(o.get("thesis") or "{}"))
            except Exception:
                out.append({})
        return out

    def calls(self, d):
        return [e for e in (d.get("evidence_log") or []) if isinstance(e, dict)]

    def coverage(self, d):
        """Checklist items covered = 8 minus what the runner's own definition says is missing
        (sim.investigator.checklist_missing) - one definition for the gate and the scorer."""
        from sim.investigator import checklist_missing
        return 8 - len(checklist_missing(self.calls(d)))

    @staticmethod
    def _fals(o):
        try:
            return (json.loads(o.get("thesis") or "{}").get("falsifier") or {}).get("pct")
        except Exception:
            return None


def share(xs):
    xs = list(xs)
    return sum(1 for v in xs if v) / len(xs) if xs else 0.0


def nums_in(text):
    return {round(float(m), 2) for m in re.findall(r"-?\d+(?:\.\d+)?", text or "")}


# ------------------------------------------------------------------ rung conditions
def conditions(r: Run):
    n_dec = max(1, len(r.dec)); n_ord = len(r.orders); n_tr = len(r.trades)
    chains = r.chains(); rv = r.risk_verdicts(); sv = r.skeptic_verdicts(); dos = r.dossiers(); les = r.lessons()
    st = r.store()
    cov = [r.coverage(d) for d in r.dec]
    tw = r.file("twins.json"); junk = r.file("junk_report.json"); stress = r.file("stress_report.json")
    abl = r.file("ablations.json"); seeds = r.file("seeds.json"); replay = r.file("replay_hash.json"); backbone = r.file("backbone.json")
    selft = r.file("selftest_result.json") or (json.loads((ROOT / "data" / "sim" / "selftest_result.json").read_text()) if (ROOT / "data" / "sim" / "selftest_result.json").exists() else None)
    C = {}

    # C1
    rounds_ok = share(len({e.get("round") for e in r.calls(d) if e.get("round") is not None}) >= 2 for d in r.dec)
    cond_q = 0
    for d in r.dec:
        seen = set(); hit = False
        for e in r.calls(d):
            a = (e.get("args") or {}).get("coin")
            if a and a in seen:
                hit = True
            seen |= set(re.findall(r"\bC\d+\b", e.get("result") or ""))
        cond_q += hit
    compute_per_dec = sum(1 for d in r.dec for e in r.calls(d) if e.get("tool") == "compute") / n_dec
    xcheck = share(len({e.get("tool") for e in r.calls(d) if (e.get("args") or {}).get("coin") == lab}) >= 2
                   for d in r.dec for o in d["orders"] for lab in [next((v["label"] for v in (d.get("risk") or {}).get("round1", []) if v["coin"] == o["coin"]), None)] if lab)
    C[1] = {20: [("mean checklist items >= 6", sum(cov) / n_dec >= 6)],
            40: [("8/8 items in every decision", all(c >= 8 for c in cov))],
            60: [(">=2 investigator rounds logged in >=80% decisions", rounds_ok >= 0.8), ("conditional question in >=50% decisions", cond_q / n_dec >= 0.5)],
            80: [("compute() >=1 per decision", compute_per_dec >= 1), ("every order coin queried by >=2 tools", xcheck >= 0.999 and n_ord > 0)],
            100: [(">=30 decisions", len(r.dec) >= 30), ("8/8 in >=95%", share(c >= 8 for c in cov) >= 0.95)]}

    # C2
    full_chain = share(bool(c.get("mechanism")) and bool(c.get("falsifier")) and bool(c.get("checkpoint")) for c in chains)
    verd = share(("falsifier day" in l or "checkpoint day" in l) for l in les)
    fals_used = (n_tr and (r.trades["exit_reason"] == "falsifier").any()) or any("TRIGGERED" in l or "not triggered" in l for l in les)
    ev_families = 0; ev_nonunlock = False
    if r.table_exists(st, "event_instance"):
        ev_families = st.execute("SELECT COUNT(DISTINCT event_type) FROM event_instance").fetchone()[0]
        t0, t1 = r.dec[0]["t"], r.dec[-1]["t"]
        ev_nonunlock = st.execute("SELECT COUNT(*) FROM event_instance WHERE event_type!='unlock' AND scheduled_ts BETWEEN ? AND ?", (t0, t1 + 7 * 86_400_000)).fetchone()[0] > 0
    links_ok = r.table_exists(r.mem, "link") and r.mem.execute("SELECT COUNT(*) FROM link WHERE status='admitted'").fetchone()[0] > 0
    chain_link = share("link" in c for c in chains)
    t1 = r.file("acceptance/T1.json")
    C[2] = {20: [(">=90% orders have mechanism+falsifier+checkpoint", full_chain >= 0.9 and n_ord > 0)],
            40: [(">=80% lessons carry verdicts", verd >= 0.8 and bool(les)), ("a falsifier fired or was judged", bool(fals_used))],
            60: [("event_instance has >=3 families", ev_families >= 3), ("non-unlock event inside window", ev_nonunlock), ("decisions log events section", all("events" in d for d in r.dec))],
            80: [("admitted link exists", bool(links_ok)), (">=80% chains carry link field", chain_link >= 0.8), ("link_cap in verdict checks", any("link_cap" in v.get("checks", {}) for v in rv))],
            100: [("acceptance T1 passed", bool(t1 and t1.get("pass"))), (">=30 chains graded", len(les) >= 30)]}

    # C3
    fc_rows = st.execute("SELECT COUNT(*) FROM feat_cross WHERE ts_ms BETWEEN ? AND ?", (r.dec[0]["t"], r.dec[-1]["t"] + 86_400_000)).fetchone()[0] if r.table_exists(st, "feat_cross") else 0
    keys3 = ("beta_btc", "beta_stress", "stress_loss_3sigma", "vol_scale", "cluster")
    v3 = share(all(k in v.get("checks", {}) for k in keys3) for v in rv)
    stab = pd.Series(r.x.get("cluster_stability", {})); stab_med = float(stab.median()) if len(stab) else 0.0
    attr = n_tr > 0 and "attribution" in r.trades.columns
    hedge = any("hedge" in c for c in chains)
    C[3] = {20: [("feat_cross rows in window", fc_rows > 0), ("dossiers carry btc_relationship", share("btc_relationship" in d_ for d_ in dos) >= 0.9 and bool(dos))],
            40: [(">=90% verdicts carry beta/stress/vol/cluster", v3 >= 0.9 and bool(rv))],
            60: [("trades carry attribution", bool(attr)), ("cluster stability median >= 0.5", stab_med >= 0.5)],
            80: [("viewer endpoints exist", (ROOT / "scripts" / "dashboard.py").read_text(encoding="utf-8", errors="ignore").find("/api/xsec_corr") >= 0), ("hedged/residual-sized order", hedge)],
            100: [(">=60 trades with attribution", bool(attr) and n_tr >= 60)]}

    # C4
    crowd_calls = sum(1 for d in r.dec for e in r.calls(d) if e.get("tool") in ("funding", "positioning")) / n_dec
    labels_ok = any('"crowd"' in (e.get("result") or "") for d in r.dec for e in r.calls(d) if e.get("tool") in ("funding", "positioning"))
    fq = share("funding_quintile" in v.get("checks", {}) for v in rv)
    oi = share(any(e.get("tool") == "open_interest" for e in r.calls(d)) or any("oi_change_7d_usd" in json.dumps(dd) for dd in ((d.get("skeptic") or {}).get("dossier") or [])) for d in r.dec)
    links_shown = share("links_shown" in d for d in r.dec)
    liq = share(any(k in json.dumps(dd) for k in ("liquidation", "cross_venue")) for dd in dos)
    C[4] = {20: [("funding/positioning >=1 per decision", crowd_calls >= 1), ("engine crowd labels in results", labels_ok)],
            40: [(">=90% verdicts carry funding_quintile", fq >= 0.9 and bool(rv)), ("OI used in >=50% decisions", oi >= 0.5)],
            60: [("links_shown logged", links_shown >= 0.9)],
            80: [("liquidation/cross-venue in >=50% dossiers", liq >= 0.5)],
            100: [("carry sleeve live >=60 trades", False)]}

    # C5
    cited = []; num_ok = []
    for d in r.dec:
        called = {e.get("tool"): e for e in r.calls(d)}
        SHEET = {"morning_sheet", "sheet", "morning sheet"}          # the sheet is tool output (regime/market_table/calendar/links)
        for c in (d.get("cards") or []):
            if not isinstance(c, dict):
                continue
            srcs = [x.split("(")[0].strip().split(" ")[0] for x in str(c.get("source", "")).split(",") if x.strip()]   # "funding C104" -> funding
            srcs = [("market_table" if x in SHEET else x) for x in srcs]
            ok = bool(srcs) and all(x in called for x in srcs)
            cited.append(ok)
            if ok:
                nums = nums_in(c.get("fact", "")); have = set()
                for x in srcs:
                    have |= nums_in(called[x].get("result", ""))
                num_ok.append(all(any(abs(n - h) <= 0.01 * max(1, abs(n)) for h in have) for n in nums) if nums else True)
    rejected = all("cards_rejected" in d for d in r.dec)
    quotes = share(all(k in c for k in ("quote", "url", "fetched_at")) for d in r.dec for c in (d.get("cards") or []) if isinstance(c, dict) and c.get("url"))
    C[5] = {20: [(">=80% cards cite a called tool", share(cited) >= 0.8 and bool(cited))],
            40: [("100% cited and rejects logged", share(cited) >= 0.999 and rejected), (">=90% card numbers match tool output", share(num_ok) >= 0.9 and bool(num_ok))],
            60: [("text cards carry quote+url+fetched_at", bool(quotes) and quotes >= 0.99), ("citation P/R logged", all("citation_precision" in d for d in r.dec))],
            80: [("junk_report.json exists", junk is not None)],
            100: [("junk report passes J11", bool(junk and junk.get("pass")))]}

    # C6
    vc = r.judged.get("view_consistency")
    vc_mean = sum(vc) / len(vc) if vc else None
    beliefs = r.table_exists(r.mem, "belief") and r.mem.execute("SELECT COUNT(*) FROM belief WHERE run_id=?", (r.id,)).fetchone()[0] >= len(r.dec)
    C[6] = {20: [("market view in every decision", all(d.get("market_view") for d in r.dec)), ("judged view_consistency >= 0.67", vc_mean is not None and vc_mean >= 0.67)],
            40: [("belief rows >= decisions", bool(beliefs))],
            60: [(">=90% orders cite belief_ids", share(bool(c.get("belief_ids")) for c in chains) >= 0.9 and n_ord > 0), ("contradiction check logged", all("contradiction_blocked" in d for d in r.dec))],
            80: [("belief_revision rows", r.table_exists(r.mem, "belief_revision") and r.mem.execute("SELECT COUNT(*) FROM belief_revision").fetchone()[0] > 0), ("belief_score rows", r.table_exists(r.mem, "belief_score") and r.mem.execute("SELECT COUNT(*) FROM belief_score").fetchone()[0] > 0)],
            100: [(">=100 resolved beliefs with slope in range", False)]}

    # C7
    exp_rows = r.mem.execute("SELECT COUNT(*) FROM experience WHERE run_id=?", (r.id,)).fetchone()[0] if r.mem is not None else 0
    closed_real = int((r.trades["exit_reason"] != "end").sum()) if n_tr else 0
    mem_used = share(any(e.get("tool") in ("evidence", "similar") for e in r.calls(d)) or "outside_view" in d for d in r.dec)
    graph = r.table_exists(r.mem, "node") and r.table_exists(r.mem, "edge")
    walk = share(any(e.get("tool") in ("graph_walk", "analogues") for e in r.calls(d)) for d in r.dec)
    refl = r.table_exists(r.mem, "insight") and r.mem is not None and r.mem.execute("SELECT COUNT(*) FROM insight WHERE run_id=? AND source LIKE 'reflection%'", (r.id,)).fetchone()[0] > 0
    active = r.mem is not None and r.mem.execute("SELECT COUNT(*) FROM insight WHERE status='active'").fetchone()[0] > 0
    skills = r.table_exists(r.mem, "skill") and r.mem.execute("SELECT COUNT(*) FROM skill").fetchone()[0] > 0
    C[7] = {20: [(">=80% closed trades have an experience row", closed_real > 0 and exp_rows / closed_real >= 0.8)],
            40: [("memory consulted in >=90% decisions", mem_used >= 0.9), (">=80% lessons carry verdicts", verd >= 0.8 and bool(les))],
            60: [("node/edge tables", bool(graph)), ("graph_walk/analogues in >=50% decisions", walk >= 0.5), ("reflection insight with node ids", bool(refl))],
            80: [(">=1 active insight", bool(active)), (">=1 skill", bool(skills))],
            100: [("memory-off ablation shows >=25 bps loss", bool(abl and abl.get("memory_off_excess_delta", 0) <= -25))]}

    # C8
    sk_cov = share(any(v.get("coin") == o["coin"] for v in sv) for _, o in r.orders) if n_ord else 0
    reasons = share(bool(v.get("reason")) for v in sv); mism = sum(1 for v in sv if v.get("words_vs_json"))
    basis = share(isinstance(v.get("basis"), list) and bool(v.get("basis")) for v in sv)
    breaks = share(v.get("breaks_if_false") is not None for v in sv)
    contra = any(v.get("action") == "veto" and "contradiction" in str(v.get("reason", "")).lower() or v.get("contradiction") for v in sv)
    C[8] = {20: [("verdicts for >=90% orders with reasons", sk_cov >= 0.9 and reasons >= 0.999 and bool(sv)), ("0 words/JSON mismatches", mism == 0 and bool(sv))],
            40: [(">=50% verdicts carry basis", basis >= 0.5), ("prompt v2 (no arithmetic)", any((d.get("skeptic") or {}).get("prompt_version", 0) >= 2 for d in r.dec))],
            60: [(">=80% carry breaks_if_false", breaks >= 0.8), (">=1 contradiction verdict", bool(contra))],
            80: [("skeptic-off ablation shows >=25 bps loss", bool(abl and abl.get("skeptic_off_excess_delta", 0) <= -25))],
            100: [("across >=3 regimes", False)]}

    # C9
    kinds = set()
    for v in rv:
        for s in v.get("violations", []):
            kinds.add(s.split(" ")[0])
    keys9 = ("funding_quintile", "cluster", "beta_btc", "stress_loss_3sigma")
    v9 = share(all(k in v.get("checks", {}) for k in keys9) for v in rv)
    keys9b = ("stamped_facts", "dossier_fresh", "ledger_ok", "preflight")
    level = r.file("level.json")
    rule_checks = {"stop_in_moves", "target_in_moves", "funding_quintile", "cluster", "beta_btc", "stress_loss_3sigma", "event_blackout", "link_cap", "recent_loss_same_side"}
    evaluated = share(len(rule_checks & set(v.get("checks", {}))) >= 6 for v in rv)
    C[9] = {20: [("risk verdicts on 100% orders", share(any(v.get("coin") == o["coin"] for v in rv) for _, o in r.orders) >= 0.999 and n_ord > 0), (">=6 rule checks evaluated on >=90% verdicts", evaluated >= 0.9 and bool(rv))],
            40: [(">=90% verdicts carry funding/cluster/beta/stress", v9 >= 0.9 and bool(rv)), ("event_blackout in checks", any("event_blackout" in v.get("checks", {}) for v in rv))],
            60: [("stamped/fresh/ledger/preflight checks", any(all(k in v.get("checks", {}) for k in keys9b) for v in rv)), ("rejection rate in summary", "risk_rejection_rate" in r.summary)],
            80: [("stress_report passes", bool(stress and stress.get("pass")))],
            100: [("level >= 2", bool(level and level.get("level", 0) >= 2))]}

    # C10
    nots = {round(o.get("notional", 100.0), 1) for _, o in r.orders}
    kv = share("kelly_scale" in v.get("checks", {}) and "vol_scale" in v.get("checks", {}) for v in rv)
    calib = share("calibration_bucket" in v.get("checks", {}) for v in rv)
    C[10] = {20: [(">=2 distinct notionals", len(nots) >= 2), ("kelly/vol scale in checks", kv >= 0.9 and bool(rv))],
             40: [("calibration bucket applied on >=50%", calib >= 0.5)],
             60: [("twins.json with equal-weight and inverse-vol", bool(tw and "equal_weight" in tw and "inverse_vol" in tw))],
             80: [(">=100 trades and agent >= twins", bool(tw) and n_tr >= 100 and tw.get("agent_beats_both", False))],
             100: [("capacity on every order", share("capacity" in c for c in chains) >= 0.999 and n_ord > 0)]}

    # C11
    inband = []
    for t, o in r.orders:
        dm = r.own_move(t, o["coin"])
        if dm:
            sm, tm = o["stop"] * 100 / dm, o["target"] * 100 / dm
            inband.append(1.49 <= sm <= 3.01 and tm >= 1.99)
    r1 = [v for d in r.dec for v in (d.get("risk") or {}).get("round1", [])]
    first_time = share(not any(s.split(" ")[0] in ("stop", "target") for s in v.get("violations", [])) for v in r1)   # hold is engine-derived
    bounce_rate = share(v.get("action") == "bounce" for v in r1)
    stops_called = share(any(e.get("tool") == "stops_report" for e in r.calls(d)) for d in r.dec)
    noise = None
    if n_tr >= 60:
        st_ = r.trades[r.trades["exit_reason"] == "stop"]
        noise = share(st_["mfe_bps"] >= (r.trades.loc[st_.index, "target"] if "target" in r.trades.columns else 1e9))
    C[11] = {20: [("100% opened orders in band", share(inband) >= 0.999 and bool(inband))],
             40: [(">=80% first-time-right on stop/target", first_time >= 0.8 and bool(r1))],
             60: [("bounce rate <= 20%", bounce_rate <= 0.2 and bool(r1)), ("stops_report in >=50% decisions", stops_called >= 0.5)],
             80: [("event_note on orders with events in hold", share("event_note" in c for c in chains) >= 0.999 and n_ord > 0)],
             100: [("noise-stop rate < 20% over >=60 trades", noise is not None and noise < 0.2)]}

    # C12
    C[12] = {20: [("100% lessons carry excess and counterfactuals", share("vs market" in l for l in les) >= 0.999 and bool(les))],
             40: [(">=80% lessons carry verdicts", verd >= 0.8 and bool(les))],
             60: [("loss_class on losses", r.mem is not None and r.mem.execute("SELECT COUNT(*) FROM experience WHERE run_id=? AND lesson LIKE '%loss_class%'", (r.id,)).fetchone()[0] > 0)],
             80: [("belief_score rows", r.table_exists(r.mem, "belief_score")), ("attribution_bps in decisions", all("attribution_bps" in d for d in r.dec))],
             100: [("states.json over a year", r.file("states.json") is not None)]}

    # C13
    ex = r.trades["excess_bps"] if n_tr else pd.Series(dtype=float)
    ci_ok = False
    if n_tr >= 60:
        import numpy as np
        rng = np.random.default_rng(0); means = [ex.sample(n_tr, replace=True, random_state=int(rng.integers(1e9))).mean() for _ in range(2000)]
        ci_ok = pd.Series(means).quantile(0.05) > 0
    C[13] = {20: [("n >= 20", n_tr >= 20), ("twins.json", tw is not None)],
             40: [("n >= 60", n_tr >= 60), ("bootstrap 90% CI excludes 0", bool(ci_ok))],
             60: [("PSR >= 0.95", r.summary.get("psr", 0) >= 0.95), ("DSR reported", "dsr" in r.summary)],
             80: [("walk-forward sign stability >= 5/8", bool(r.file("walkforward.json") and r.file("walkforward.json").get("sign_stable", 0) >= 5)), (">=2 ablations show loss", bool(abl and abl.get("n_losses", 0) >= 2))],
             100: [("held-out and prospective pass", False)]}

    # C14
    errs = sum(1 for d in r.dec if d.get("error"))
    schema = share(bool((d.get("call_meta") or {}).get("json_schema")) for d in r.dec)
    paths = any(d.get("error") or (d.get("risk") or {}).get("unanswered_desk_fixed") or ((d.get("call_meta") or {}).get("attempt", 1) > 1) for d in r.dec)
    C[14] = {20: [("selftest all pass", bool(selft and selft.get("fails", 1) == 0)), ("0 decision errors", errs == 0)],
             40: [("json_schema on 100% calls", schema >= 0.999), ("a garbage/empty/server path exercised live", bool(paths))],
             60: [("junk_report.json", junk is not None)],
             80: [("seeds.json", seeds is not None), ("replay_hash equal", bool(replay and replay.get("equal"))), ("backbone.json", backbone is not None)],
             100: [("stress_report all pass", bool(stress and stress.get("pass")))]}

    # C15
    confs = share(o.get("confidence") is not None for _, o in r.orders)
    med3 = share((d.get("strategist_meta") or {}).get("samples") == 3 for d in r.dec)
    no_trade = any("no_trade_reason" in d for d in r.dec)
    C[15] = {20: [("confidence on 100% orders", confs >= 0.999 and n_ord > 0)],
             40: [("calibration bucket used on >=50% verdicts", calib >= 0.5)],
             60: [("median-of-3 logged", med3 >= 0.9), ("a no_trade_reason logged", no_trade)],
             80: [("slope in [0.7,1.3] over >=50", False)],
             100: [(">=100 across regimes", False)]}
    return C


def score(C):
    out = {}
    for k, rungs in C.items():
        reached = 0
        for rung in (20, 40, 60, 80, 100):
            if all(ok for _, ok in rungs[rung]):
                reached = rung
            else:
                break
        nxt = reached + 20 if reached < 100 else None
        met = share(ok for _, ok in rungs[nxt]) if nxt else 1.0
        first_unmet = next((name for name, ok in rungs[nxt] if not ok), None) if nxt else None
        out[k] = {"rung": reached, "score": int(round(reached + 10 * met)), "next_unmet": first_unmet}
    return out


NAMES = {1: "Information gathering", 2: "Event & chain reasoning", 3: "Cross-sectional awareness", 4: "Crowd reading",
         5: "Provenance & anti-hallucination", 6: "Consistency of beliefs", 7: "Memory & learning", 8: "Skeptic",
         9: "Risk desk", 10: "Sizing", 11: "Plan quality", 12: "Accountability & grading", 13: "Outcome vs twins",
         14: "Robustness", 15: "Calibration & abstention"}


def main():
    args = sys.argv[1:]
    mems = []
    if "--memory" in args:
        i = args.index("--memory"); mems = [a for a in args[i + 1:] if not a.startswith("--")]
    default_mem = str(ROOT / "data" / "sim" / "memory_investigator.db")
    labels = []
    if "--label" in args:
        i = args.index("--label"); labels = [a for a in args[i + 1:] if not a.startswith("--")]
    runs = [a for a in args if not a.startswith("--") and Path(a).exists() and (Path(a) / "decisions.jsonl").exists()]
    results = {}
    for i, rd in enumerate(runs):
        r = Run(rd, mems[i] if i < len(mems) else default_mem)     # one memory db per run, in order
        results[labels[i] if i < len(labels) else r.id] = score(conditions(r))
    names = list(results)
    print("| # | category | " + " | ".join(names) + " |")
    print("|---|---|" + "---|" * len(names))
    for k in range(1, 16):
        print(f"| {k} | {NAMES[k]} | " + " | ".join(f"{results[n][k]['score']} (rung {results[n][k]['rung']})" for n in names) + " |")
    print("| | **mean** | " + " | ".join(f"**{sum(results[n][k]['score'] for k in range(1, 16)) / 15:.1f}**" for n in names) + " |")
    print("\n## First unmet condition of the next rung")
    for n in names:
        print(f"\n### {n}")
        for k in range(1, 16):
            print(f"- {k}. {NAMES[k]}: {results[n][k]['next_unmet']}")


if __name__ == "__main__":
    main()
