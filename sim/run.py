"""Run an agent through history, day by day, at real costs, with memory.

    python -m sim.run --agent trend --start 2024-01-01 --end 2024-12-31
    python -m sim.run --agent learning_trend --start 2021-01-01 --end 2026-08-31 --universe 60
    python -m sim.run --batch trend,random,learning_trend --years 2021-2026 --universe 60
    python -m sim.run --agent llm --start 2025-01-01 --end 2025-03-31      # needs SIM_LLM

Each day t (a UTC day, in order):
  1. the book settles yesterday's positions at today's range/close (stops, targets,
     time), charges funding, marks equity. Closed trades become LESSONS in memory,
     stamped with today - so they are recallable from tomorrow, never earlier.
  2. every `rebalance_days` the agent observes (as-of t only) and decides; orders open
     at today's close, fee + half-spread charged now.
Outputs under data/sim/runs/<run_id>/: trades.csv, equity.csv, summary.json, and the
memory database data/sim/memory_<agent>.db (shared across runs of the same agent so
it keeps learning; pass --fresh-memory to start it empty).
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd

from .agents import AGENTS, Agent, Observation
from . import investigator  # noqa: F401  (registers the 'investigator' agent)
from .data import AsOf, DAY_MS, spreads_bps
from .engine import Book
from .memory import Memory

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "sim" / "runs"


def day_ms(s: str) -> int:
    return int(datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def pick_universe(n: int) -> List[str]:
    """The n coins with the tightest measured Hyperliquid spread (not volume - the
    1000x contracts' volume is ~100x too high, HANDOFF §14)."""
    s = spreads_bps().dropna().sort_values()
    return list(s.index[:n])


def wake_reason(data: AsOf, t: int, last_regime: str, last_decide: int, rebalance_days: int) -> str:
    """Event-driven cadence (Dev, 2026-09-16): decide on the weekly baseline OR when the
    data itself says something happened. Reasons are computed from as-of data only.
    Cooldown: never two wake-ups within 2 days."""
    if last_decide is None or (t - last_decide) >= rebalance_days * DAY_MS:
        return "weekly"
    if (t - last_decide) < 2 * DAY_MS:
        return ""
    from .agents import regime_label
    reg = regime_label(data, t)
    if last_regime and reg != last_regime:
        return f"regime {last_regime}->{reg}"
    try:
        c = data.closes(t, 31)
        r1 = (c.iloc[-1] / c.iloc[-2] - 1.0).dropna()
        if len(r1) >= 20:
            green = float((r1 > 0).mean())
            if green >= 0.9 or green <= 0.1:
                return f"breadth {green*100:.0f}% green"
        if "BTC" in c.columns:
            b = c["BTC"].pct_change().dropna()
            if len(b) > 20 and abs(b.iloc[-1]) > 2.5 * b.iloc[:-1].std():
                return f"BTC {b.iloc[-1]*100:+.1f}% day"
    except Exception:
        pass
    cal = getattr(data, "calendar", None)
    if cal is not None:
        nm = cal.next_macro_hours(t)
        if nm and nm["hours"] <= 24:
            return f"event: {nm['event']} in {nm['hours']:.0f}h"
    if t in data.funding.index:
        f = data.funding.loc[t].dropna()
        f = f[f.index.isin(data.universe)]
        if len(f) >= 20 and (f.abs() > 0.003).sum() >= 3:
            return f"funding extreme on {(f.abs() > 0.003).sum()} coins"
    return ""


def run_episode(agent: Agent, data: AsOf, start: int, end: int, trade_size: float,
                run_id: str, verbose: bool = True, event_driven: bool = True) -> Dict:
    book = Book(data, trade_size=trade_size)
    if hasattr(agent, "risk"):                       # Hat 4 for the LLM agents: code-only risk desk
        from .risk import RiskHat
        agent.risk = RiskHat(data, agent.memory, book, getattr(data, "xsec", None))
    days = [d for d in data.days if start <= d <= end]
    if not days:
        raise SystemExit("no simulation days in that window")
    open_obs: Dict[int, tuple] = {}       # position id -> (observation, confidence, probation)
    last_decide = None
    last_regime = ""
    out = RUNS / run_id
    out.mkdir(parents=True, exist_ok=True)
    decisions = open(out / "decisions.jsonl", "w", encoding="utf-8")
    t0 = time.time()
    for i, t in enumerate(days):
        # 1. settle; every closed trade becomes an EXPERIENCE (time-stamped now)
        for tr in book.settle(t):
            rec = open_obs.pop(tr.id, None)
            if agent.memory is not None and rec is not None:
                obs, conf, probation = rec
                feats = {f: (float(obs.table.at[tr.coin, f]) if tr.coin in obs.table.index else None)
                         for f in agent.features}
                agent.memory.learn(
                    closed_ts=t, opened_ts=tr.entry_ts, coin=tr.coin, side=tr.side,
                    setup=f"{agent.setup}:{tr.side}", regime=obs.regime, features=feats,
                    thesis=tr.thesis, confidence=conf, net_bps=tr.net_pnl / tr.notional * 1e4,
                    excess_bps=tr.excess_bps, mfe_bps=tr.mfe_bps, mae_bps=tr.mae_bps,
                    exit_reason=tr.exit_reason, days_held=tr.days_held,
                    counterfactuals=tr.counterfactuals, lesson=agent.lesson(obs, tr),
                    probation=probation)
        # 2. decide - weekly baseline or an event wake-up
        reason = (wake_reason(data, t, last_regime, last_decide, agent.rebalance_days) if event_driven
                  else ("weekly" if last_decide is None or (t - last_decide) >= agent.rebalance_days * DAY_MS else ""))
        if reason:
            obs = agent.observe(data, t, list(book.positions))
            last_regime = obs.regime
            td = time.time()
            try:
                orders = agent.decide(obs)
                err = None
            except Exception as e:                   # noqa: BLE001 - recorded in the decision log, batch continues
                orders, err = [], f"{type(e).__name__}: {str(e)[:300]}"
                print(f"  DECISION ERROR {datetime.fromtimestamp(t/1000, timezone.utc).date()}: {err}", flush=True)
            opened = []
            for o in orders:
                p = book.open(t, o)
                if p is not None:
                    open_obs[p.id] = (obs, agent.confidence(o), "[probation]" in (o.thesis or ""))
                    opened.append({"coin": o.coin, "side": o.side, "stop": o.stop_pct, "target": o.target_pct,
                                   "hold": o.hold_days, "size_mult": o.size_mult, "notional": p.notional,
                                   "confidence": agent.confidence(o), "thesis": o.thesis})
            decisions.write(json.dumps({"t": t, "date": str(datetime.fromtimestamp(t/1000, timezone.utc).date()),
                                        "reason": reason, "regime": obs.regime, "seconds": round(time.time() - td, 1),
                                        "orders": opened, "evidence_log": getattr(agent, "last_log", None),
                                        "cards": getattr(agent, "last_cards", None), "market_view": getattr(agent, "last_view", None),
                                        "strategist_raw": getattr(agent, "last_strategist_raw", None),
                                        "skeptic": getattr(agent, "last_skeptic", None),
                                        "label_fixes": getattr(agent, "last_label_fixes", None),
                                        "risk": getattr(agent, "last_risk", None), "error": err,
                                        "events": getattr(agent, "last_events", None),
                                        "links_shown": getattr(agent, "last_links_shown", None),
                                        "checklist_gate": getattr(agent, "last_checklist_gate", None),
                                        "checklist_missing": getattr(agent, "last_checklist_missing", None),
                                        "auto_cover": getattr(agent, "last_auto_cover", None),
                                        "portfolio": getattr(agent, "last_portfolio", None),
                                        "portfolio_after": getattr(agent, "last_portfolio_after", None),
                                        "outside_view": True},
                                       default=str) + chr(10))
            decisions.flush()
            if verbose and hasattr(agent, "last_log"):
                print(f"  {datetime.fromtimestamp(t/1000, timezone.utc).date()} [{reason}] {len(getattr(agent,'last_log',[]))} tool calls, "
                      f"{len(opened)} orders, {time.time()-td:.0f}s", flush=True)
            last_decide = t
        if verbose and (i % 200 == 0 or i == len(days) - 1):
            print(f"  {datetime.fromtimestamp(t/1000, timezone.utc).date()}  equity {book.equity(t):,.0f}  "
                  f"open {len(book.positions)}  trades {len(book.trades)}  ({time.time()-t0:.0f}s)", flush=True)
    book.close_all(days[-1])
    decisions.close()
    pd.DataFrame([asdict(x) for x in book.trades]).to_csv(out / "trades.csv", index=False)
    pd.DataFrame(book.equity_curve, columns=["ts_ms", "equity"]).to_csv(out / "equity.csv", index=False)
    summary = book.summary()
    tr_df = pd.DataFrame([asdict(x) for x in book.trades])
    summary["avg_excess_bps"] = float(tr_df["excess_bps"].mean()) if len(tr_df) else float("nan")
    summary.update({"agent": agent.name, "start": days[0], "end": days[-1],
                    "memory": agent.memory.stats() if agent.memory else None,
                    "calibration": agent.memory.calibration(days[-1]) if agent.memory else None})
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    if agent.memory is not None:
        import shutil
        try:
            src = ROOT / "data" / "sim" / f"memory_{agent.name}.db"
            agent.memory.conn.commit()
            shutil.copy2(src, out / "memory.db")                 # the run's memory travels with the run
        except Exception as e:                                    # noqa: BLE001
            print(f"  memory copy failed: {e}")
    return summary


def build_agent(kind: str, memory: bool, fresh: bool, run_id: str, seed: int) -> Agent:
    cls = AGENTS[kind]
    agent = cls(None, seed)
    if memory:
        path = ROOT / "data" / "sim" / f"memory_{agent.name}.db"
        if fresh and path.exists():
            path.unlink()
        agent.memory = Memory(path, agent.name, run_id, seed=seed)
    return agent


def print_row(s: Dict) -> None:
    d = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).date()
    ex = json.loads(s["exits"]) if isinstance(s["exits"], str) else s["exits"]
    mem = s.get("memory") or {}
    print(f"{s['agent']:<20}{str(d(s['start'])):>11} {str(d(s['end'])):>11}{s['trades']:>7}"
          f"{s['net_return_pct']:>+8.1f}%{s['avg_net_per_trade_bps']:>+8.0f}{s.get('avg_excess_bps', float('nan')):>+8.0f}"
          f"{s['hit_rate']*100:>6.0f}%{s['fees']:>7.0f}{s['sharpe']:>+7.2f}{s['max_drawdown_pct']:>+7.1f}%"
          f"  s/t/t {ex.get('stop',0)}/{ex.get('target',0)}/{ex.get('time',0)}"
          + (f"  exp {mem.get('experiences',0)} prob {mem.get('probation_trades',0)} ins {mem.get('insights_active',0)}a/{mem.get('insights_retired',0)}r" if mem else ""))


def header() -> None:
    print(f"{'agent':<20}{'start':>11} {'end':>11}{'trades':>7}{'net ret':>9}{'bps/trd':>8}{'xs/trd':>8}{'hit':>7}"
          f"{'fees':>7}{'sharpe':>7}{'maxDD':>8}")
    print("-" * 120)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="trend")
    ap.add_argument("--batch", default="", help="comma list of agents to run over --years")
    ap.add_argument("--years", default="", help="e.g. 2021-2026: one episode per calendar year")
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--universe", type=int, default=60, help="n tightest-spread coins")
    ap.add_argument("--size", type=float, default=100.0)
    ap.add_argument("--no-memory", action="store_true")
    ap.add_argument("--fresh-memory", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    universe = pick_universe(args.universe)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if args.batch:
        y0, y1 = [int(x) for x in args.years.split("-")]
        agents = args.batch.split(",")
        feats = sorted({f for a in agents for f in AGENTS[a](None, 0).features})
        print(f"universe: {len(universe)} coins (tightest spread) · features loaded: {len(feats)} · loading data...", flush=True)
        data = AsOf(feats, universe)
        from .xsec import xsec
        data.xsec = xsec()
        rows = []
        for a in agents:
            agent = build_agent(a, not args.no_memory, args.fresh_memory, f"{stamp}_{a}", args.seed)
            for y in range(y0, y1 + 1):
                s0, s1 = day_ms(f"{y}-01-01"), min(day_ms(f"{y}-12-31"), data.days[-1])
                if s0 > data.days[-1]:
                    break
                rows.append(run_episode(agent, data, s0, s1, args.size, f"{stamp}_{a}_{y}", verbose=False))
        print()
        header()
        for r in rows:
            print_row(r)
        pd.DataFrame(rows).to_csv(RUNS / f"{stamp}_batch.csv", index=False)
        print(f"\nwritten to {RUNS / (stamp + '_batch.csv')}")
        return

    feats = AGENTS[args.agent](None, 0).features
    print(f"universe: {len(universe)} coins · loading data...", flush=True)
    data = AsOf(feats, universe)
    from .xsec import xsec
    data.xsec = xsec()                               # cross-sectional layer (cached per data vintage)
    agent = build_agent(args.agent, not args.no_memory, args.fresh_memory, f"{stamp}_{args.agent}", args.seed)
    s = run_episode(agent, data, day_ms(args.start), day_ms(args.end), args.size, f"{stamp}_{args.agent}")
    print()
    header()
    print_row(s)
    print(f"\nrun folder: {RUNS / (stamp + '_' + args.agent)}")


if __name__ == "__main__":
    main()
