"""Generate the TRADING DOSSIER — the well-made, always-current training document.

Everything we must not forget, pulled from the real data into one report:
  * the live scoreboard (current book + closed-trade performance),
  * the rulebook and every dated lesson,
  * a per-bet report for EVERY closed trade (thesis -> outcome -> lesson),
  * the mistake catalogue (losing patterns named, with the fix),
  * the open contradiction watchlist,
  * the decision framework distilled from all of it.

Generated FROM the databases (journal / research / watchlist / paper) and the rules
file, so it can never go stale — regenerate any time:

    python scripts/report.py            # writes docs/trading/TRADING_DOSSIER.md

This is the thing we read to remember what works, what burned us, and why.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _ro(db):
    p = ROOT / "data" / db
    if not p.exists():
        return None
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def _money(x):
    if x is None:
        return "—"
    return ("-$" if x < 0 else "+$") + f"{abs(x):.2f}"


def build():
    from hl import journal
    from hl.paper import Paper

    out = []
    W = out.append

    W("# TRADING DOSSIER — HYPERDESK Paper Book")
    W("")
    W("*The training record: every bet, every win, every mistake, every rule. "
      "Auto-generated from the live databases so it never goes stale.*  ")
    W("*Regenerate: `python scripts/report.py`*")
    W("")

    # 1 · scoreboard
    bk = Paper()
    a = bk.account()
    opens = bk.open_positions()
    bk.close()
    rev = journal.review()
    W("---")
    W("## 1 · Scoreboard")
    W("")
    W(f"**Live book:** {a['n_open']} open · exposure ${a['open_notional']:.0f} · "
      f"unrealized {_money(a['unrealized_pnl'])} · realized {_money(a['realized_pnl'])} · "
      f"**total {_money(a['total_pnl'])}**")
    if rev.get("n"):
        o = rev["overall"]
        W(f"**Closed record:** {o['n']} trades · win {o['win_rate']*100:.0f}% · "
          f"net {_money(o['total_pnl'])} · avg hold {o['avg_hold_h']}h")
        W("")
        W("**By setup — what actually works:**")
        W("")
        W("| Setup | Trades | Win % | Net P&L |")
        W("|---|---|---|---|")
        for k, v in sorted(rev.get("by_setup", {}).items(), key=lambda x: -x[1]["total_pnl"]):
            W(f"| `{k}` | {v['n']} | {v['win_rate']*100:.0f}% | {_money(v['total_pnl'])} |")
        W("")
        W("**By side:**")
        W("")
        W("| Side | Trades | Win % | Net P&L |")
        W("|---|---|---|---|")
        for k, v in rev.get("by_side", {}).items():
            W(f"| {k} | {v['n']} | {v['win_rate']*100:.0f}% | {_money(v['total_pnl'])} |")
        if rev.get("by_regime"):
            W("")
            W("**By regime — decisions graded by the market state they were opened in:**")
            W("")
            W("| Regime | Trades | Win % | Net P&L |")
            W("|---|---|---|---|")
            for k, v in rev["by_regime"].items():
                W(f"| {k} | {v['n']} | {v['win_rate']*100:.0f}% | {_money(v['total_pnl'])} |")
    W("")
    if opens:
        W("**Currently open:**")
        W("")
        W("| Coin | Side | Entry | Mark | P&L $ | P&L % |")
        W("|---|---|---|---|---|---|")
        for p in sorted(opens, key=lambda x: (x['unrealized_pnl'] or 0)):
            W(f"| {p['coin']} | {p['side']} | {p['entry_px']:.6g} | "
              f"{(p.get('mark_now') or 0):.6g} | {_money(p.get('unrealized_pnl'))} | "
              f"{(p.get('unrealized_pct') or 0):+.1f}% |")
    W("")

    # 2 · rulebook + lessons
    W("---")
    W("## 2 · Rulebook & Lessons")
    W("")
    lf = ROOT / "docs" / "trading" / "LEARNINGS_AND_RULES.md"
    if lf.exists():
        txt = lf.read_text(encoding="utf-8")
        body = txt.split("\n", 1)[1] if "\n" in txt else txt
        W(body.strip())
    W("")

    # 3 · per-bet reports
    W("---")
    W("## 3 · Per-Bet Reports — every closed trade")
    W("")
    jc = _ro("journal.db")
    if jc:
        rows = [dict(r) for r in jc.execute("SELECT * FROM reviews ORDER BY recorded_ms DESC")]
        jc.close()
        for r in rows:
            try:
                sig = json.loads(r.get("entry_signals") or "{}")
            except Exception:
                sig = {}
            try:
                oc = json.loads(r.get("outcome") or "{}")
            except Exception:
                oc = {}
            verdict = "WIN" if r.get("worked") else "LOSS"
            W(f"### {r['coin']} · {r['side'].upper()} · {verdict} {_money(r['pnl_usd'])}"
              f"  `[{r.get('setup_tag') or 'untagged'}]`")
            W("")
            mv = oc.get('price_move_our_way_pct')
            W(f"- **Result:** {_money(r['pnl_usd'])} · exit *{r['exit_reason']}* · "
              f"held {r.get('hold_hours','?')}h" + (f" · moved {round(mv,1)}% our way" if mv is not None else ""))
            entry = r.get('entry_px'); exit_ = r.get('exit_px')
            if entry and exit_:
                W(f"- **Trade:** entry {entry:.6g} → exit {exit_:.6g}")
            if sig:
                bits = []
                for k, lbl in (("ret_1d", "1d"), ("ret_7d", "7d"), ("ret_30d", "30d")):
                    if sig.get(k) is not None:
                        bits.append(f"{lbl} {sig[k]*100:+.0f}%")
                if sig.get("funding_apr") is not None:
                    bits.append(f"funding {sig['funding_apr']*100:+.0f}%APR")
                for k, lbl in (("regime_BTC_7d", "BTC7d"), ("regime_ETH_7d", "ETH7d")):
                    if sig.get(k) is not None:
                        bits.append(f"{lbl} {sig[k]*100:+.0f}%")
                if bits:
                    W(f"- **Signals at entry:** {' · '.join(bits)}")
            if r.get("lesson"):
                W(f"- **Lesson:** {r['lesson']}")
            W("")

    # 4 · mistake catalogue
    W("---")
    W("## 4 · Mistake Catalogue — losing patterns, named")
    W("")
    if rev.get("n"):
        losers = {k: v for k, v in rev.get("by_setup", {}).items() if v["total_pnl"] < 0}
        if losers:
            for k, v in sorted(losers.items(), key=lambda x: x[1]["total_pnl"]):
                W(f"- **`{k}`** — {v['n']} trades, {v['win_rate']*100:.0f}% win, "
                  f"cost **{_money(v['total_pnl'])}**. See per-bet lessons for the fix.")
        else:
            W("*No losing setups on record.*")
    W("")

    # 5 · watchlist
    W("---")
    W("## 5 · Open Contradictions (Watchlist)")
    W("")
    try:
        from hl import watchlist as wl
        wls = [w for w in wl.list_all() if w["status"] == "watching"]
        if wls:
            for w in wls:
                mv = w.get("move_pct")
                winning = "—" if mv is None else ("momentum ▲" if mv >= 0 else "news ▼")
                W(f"- **{w['coin']}** — bull: {w['bull_side']}  ")
                W(f"  bear: {w['bear_side']}  ")
                W(f"  since flagged: {mv is not None and f'{mv:+.1f}%'} ({winning} winning) · lean: *{w['lean']}*")
        else:
            W("*No open contradictions.*")
    except Exception:
        W("*Watchlist unavailable.*")
    W("")

    # 6 · decision framework
    W("---")
    W("## 6 · Decision Framework (the distilled playbook)")
    W("")
    W("1. **Regime first.** Melt-up (breadth >80% green, majors trending) → momentum-"
      "continuation LONGS on fresh breakouts. Do NOT short on 'overbought' or carry — "
      "proven 0/3, −$10.78 (L7).")
    W("2. **News is the trigger to think, not the entry.** Verify the catalyst is real "
      "(deep web research). A momentum-up / news-down coin is a TRAP → Watchlist, don't trade (EIGEN).")
    W("3. **Fresh breakout, not extended.** A long after +100%/30d round-trips "
      "(ETHFI −$5.15). Enter on the push, not the exhaustion.")
    W("4. **Correlation cap (L8).** Max 3 per sector; count clusters not tickers; an all-"
      "one-side book is one leveraged bet. 9 correlated longs cost us the session.")
    W("5. **Realistic take-profit.** Bank ~+10-12% on the money (HYPE +10% cashed clean); "
      "don't hold for greedy targets and watch them reverse (L1).")
    W("6. **Every trade: stop + target + time, hashed at open.** First to hit closes it. "
      "Enter on a LIVE price, band wider than spread noise (L2).")
    W("")
    W(f"*Generated {time.strftime('%Y-%m-%d %H:%M')} · {rev.get('n',0)} closed trades on record.*")

    txt = "\n".join(out) + "\n"
    (ROOT / "docs" / "trading" / "TRADING_DOSSIER.md").write_text(txt, encoding="utf-8")
    return len(txt), rev.get("n", 0)


if __name__ == "__main__":
    n, trades = build()
    print(f"TRADING_DOSSIER.md generated: {n} chars, {trades} closed trades documented")
