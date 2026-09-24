"""Grade the 2026-08-25 prediction test + print the whole portfolio.

Run any time (tomorrow / day-after). For each pred_test bet it reports: predicted
side, entry, mark/exit, the realized move IN the predicted direction (net of the
0.20% fee), and win/lose (closed = hit target/stop/time; open = leading/trailing).
Then the portfolio ledger and the fused-vs-quant-only veto edge.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hl.paper import Paper, live_all_mids

FEE = 0.0020

def run():
    p = Paper(); mids = live_all_mids()
    rows = p.conn.execute("SELECT coin,side,entry_px,exit_px,status,exit_reason,mark_px,pnl_usd,thesis "
                          "FROM positions WHERE tag='pred_test' ORDER BY opened_ms").fetchall()
    print("="*72); print("PREDICTION TEST 2026-08-25 — grade"); print("="*72)
    wins=live_win=0; n_closed=0; moves=[]
    for r in rows:
        px = r["exit_px"] if r["status"]=="closed" else mids.get(r["coin"], r["mark_px"])
        move = (px/r["entry_px"]-1.0)
        dirmove = move if r["side"]=="long" else -move   # move in predicted direction
        net = dirmove - FEE
        moves.append(net)
        if r["status"]=="closed":
            n_closed+=1
            w = (r["exit_reason"]=="target") or (net>0 and r["exit_reason"]!="stop")
            wins += 1 if net>0 else 0
            tag = f"CLOSED {r['exit_reason']} {'WIN' if net>0 else 'LOSS'} pnl ${r['pnl_usd']:+.2f}"
        else:
            live_win += 1 if net>0 else 0
            tag = f"open, {'leading' if net>0 else 'trailing'}"
        print(f"  {r['coin']:<6} {r['side']:<5} entry {r['entry_px']:.5g} -> {px:.5g}  "
              f"move-in-dir {dirmove*100:+.1f}% (net {net*100:+.1f}%)  [{tag}]")
    n=len(moves)
    avg = sum(moves)/n if n else 0
    print(f"\n  {n} bets | avg net move-in-predicted-dir {avg*100:+.2f}% | "
          f"leading/won {sum(1 for m in moves if m>0)}/{n} | closed {n_closed} (won {wins})")
    a = p.account()
    print("\n"+"="*72); print("PORTFOLIO"); print("="*72)
    print(f"  total P&L ${a['total_pnl']:+.2f} | realized ${a['balance']:+.2f} | "
          f"unrealized ${a['unrealized_pnl']:+.2f} | fees ${a['fees_paid']:.2f} | win {round((a['win_rate'] or 0)*100)}%")
    h=a.get('hedge') or {}
    print(f"  hedge: short ${h.get('notional')} BTC, P&L ${h.get('pnl')}")
    bc = p.book_compare()
    for t in ('fused','quant_only'):
        d=bc[t]; print(f"  {t:<11} n={d['n']} avg BTC-neutral {d['avg_resid_pct']}% win {d['win_rate']}")
    print(f"  veto edge (fused - quant_only): {bc.get('veto_edge_pct')}%  -> "
          f"{'news veto SMART' if bc.get('veto_was_smart') else 'news veto NOT paying (skipped winners)'}")
    p.close()

if __name__=="__main__":
    run()
