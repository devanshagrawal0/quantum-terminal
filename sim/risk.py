"""The Risk hat - code only, no model call, cannot be overridden (spec 4.7).

Runs after the skeptic. For every surviving order it computes the numbers the model is
not allowed to do in its head, checks the desk rules, sizes the trade, and either
accepts it, bounces it once to the strategist with the numbers, or rejects it.
Every check is logged with the value that decided it.

Rules (R2-R12, R16-R19):
  stop        1.5 .. 3.0 idiosyncratic daily moves
  falsifier   on the wrong side for the trade (long: down, short: up) and inside the stop
  target      >= 2 daily moves and >= 1.5 x stop
  hold        >= days the target needs at that vol: ceil((target / daily move)^2), <= 14
  cluster     <= 2 positions per residual-correlation cluster (open positions count)
  risk capital = max_positions x trade_size (the most the book can ever deploy); every book-level
              cap below is a share of THAT, not of idle cash (2026-09-16: against $10k cash the
              caps could never fire with $100 units, and the August book went 10 of 10 long)
  beta band   |sum side * beta * notional| <= 50% of risk capital
  net/gross   with 4+ positions, |net beta dollars| <= 60% of gross beta dollars: the book can
              lean, it cannot be one bet; low-beta coins barely count, so "its own story" longs
              still fit a long book and a short (or a hedge) reopens room
  stress      projected loss under a 3-sigma BTC move with stressed betas <= 10% of risk capital
  funding     a long that PAYS top-quintile funding needs p_final >= 0.60; a short that pays
              bottom-quintile (crowded-short) funding needs p_final >= 0.65 (measured: the
              crowd-short quintile is paid ~48 bps/week, MEASURED_LINKS section 4b)
  size        size_mult = kelly_scale x vol_scale, kelly_scale = clip((2p-1) * stop/target * 4, 0, 1)
              (quarter-Kelly for a stop/target bet), vol_scale = clip(12% / idio vol, 0.25, 1)
  p_final     stated confidence shrunk toward 0.5 by k = n/(n+10) with n = the agent's own
              closed trades on that side, then mapped through its calibration table
  brakes      CVaR: a day in the worst 1% of history -> sizes x0.5 for 5 days; drawdown > 15%
              from peak -> no new trades; day loss > 3% -> no new trades
"""
from __future__ import annotations

import json
import math
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .engine import Book, Order

STOP_MIN, STOP_MAX = 1.5, 3.0
TARGET_MIN_MOVES, TARGET_MIN_RATIO = 2.0, 1.5
MAX_HOLD = 14
CLUSTER_CAP = 2
BETA_BAND = 0.50
NET_GROSS_MAX = 0.60           # |net beta $| / gross beta $ once the book has NET_RULE_FROM positions
NET_RULE_FROM = 4
STRESS_LOSS_CAP = 0.10
DD_CAP, DAY_LOSS_CAP = 0.15, 0.03
VOL_TARGET_PCT = 12.0
TOL = 0.01
RECENT_LOSS_P = 0.65           # a repeat of a trade that just lost needs this much conviction (spec B46, outside view first)
LINK_CAP = 0.65                # spec B6/C26: a chain with no admitted measured link cannot claim more than this                     # band checks tolerate 1% so a number the desk itself suggested never fails its own rule


class RiskHat:
    def __init__(self, data, memory, book: Book, xsec: Optional[Dict] = None):
        self.data, self.memory, self.book = data, memory, book
        self.x = xsec
        self.risk_capital = float(book.max_positions * book.trade_size)
        self.brake_until: Optional[int] = None
        self.last: List[Dict] = []

    # ---- numbers ---------------------------------------------------------------
    def _xs(self, key: str, t: int, coin: str) -> Optional[float]:
        if not self.x:
            return None
        f = self.x["frames"].get(key)
        if f is None or coin not in f.columns:
            return None
        s = f[coin]
        s = s[s.index <= t].dropna()
        return None if s.empty else float(s.iloc[-1])

    def daily_move(self, t: int, coin: str, table: Optional[pd.DataFrame] = None, label: Optional[str] = None) -> Tuple[Optional[float], str]:
        """The coin's own daily move in %: residual vol first, raw 7-day vol second, else None
        (an order with no volatility data is rejected - never sized off an invented number)."""
        v = self._xs("idio_daily_move_pct", t, coin)
        if v is not None and v > 0:
            return v, "idio_daily_move_pct"
        if table is not None and label in table.index and "rv_7d" in table.columns and pd.notna(table.at[label, "rv_7d"]):
            rv = float(table.at[label, "rv_7d"])
            if rv > 0:
                return rv / math.sqrt(365) * 100.0, "rv_7d (no residual vol yet)"
        return None, "no volatility data"

    def funding_quintile(self, t: int, coin: str) -> Optional[int]:
        f = self.data.funding
        if coin not in f.columns or t not in f.index:
            return None
        row = f.loc[t].dropna()
        if len(row) < 20 or pd.isna(row.get(coin)):
            return None
        return int(min(4, (row.rank(pct=True)[coin]) * 5 // 1))

    def p_final(self, coin: str, side: str, p_model: float, t: int, setup: str) -> Tuple[float, Dict]:
        """Outside view first: shrink the stated probability toward the agent's own realised win
        rate on this side (p_engine) by k = n/(n+10), then map through the calibration table."""
        info = {"p_model": round(p_model, 3)}
        n, p_engine = 0, None
        if self.memory is not None:
            ev = self.memory.evidence(f"{setup}:{side}", None, t)
            n = int(ev.get("n", 0) or 0)
            w = ev.get("win")
            p_engine = None if w is None or (isinstance(w, float) and math.isnan(w)) else float(w)
        k = n / (n + 10.0) if p_engine is not None else 0.0
        p = (1 - k) * p_model + k * (p_engine if p_engine is not None else 0.5)
        info.update({"n_side": n, "p_engine": None if p_engine is None else round(p_engine, 3), "k": round(k, 3),
                     "p_after_shrink": round(p, 3)})
        if self.memory is not None:
            try:
                for b in self.memory.calibration(t):                     # {"bucket": "0.55-0.70", "n", "win", ...}
                    lo, hi = (float(x) for x in b["bucket"].split("-"))
                    if b.get("n", 0) >= 10 and lo <= p < (hi if hi < 1.0 else 1.01):
                        info["calibration_bucket"] = b; p = float(b["win"]); break
            except Exception:
                pass
        p = min(max(p, 0.01), 0.99)
        info["p_final"] = round(p, 3)
        return p, info

    def recent_loss(self, coin: str, side: str, t: int, days: int = 7) -> Optional[Dict]:
        """The most recent losing experience on this coin and side closed within `days` (the
        agent's own record, applied by the desk rather than hoped for from the model)."""
        if self.memory is None:
            return None
        row = self.memory.conn.execute(
            "SELECT closed_ts, net_bps, exit_reason FROM experience WHERE agent=? AND coin=? AND side=? AND closed_ts<=? "
            "AND closed_ts>? AND net_bps<0 ORDER BY closed_ts DESC LIMIT 1",
            (self.memory.agent, coin, side, t, t - days * 86_400_000)).fetchone()
        if not row:
            return None
        return {"days_ago": round((t - row[0]) / 86_400_000, 1), "net_bps": round(row[1], 0), "exit_reason": row[2]}

    # ---- brakes ----------------------------------------------------------------
    def brakes(self, t: int) -> List[str]:
        eq = pd.Series({ts: e for ts, e in self.book.equity_curve}).sort_index()
        out = []
        if len(eq) >= 2:
            peak = eq.cummax().iloc[-1]
            dd = peak - eq.iloc[-1]
            if dd > DD_CAP * self.risk_capital:
                out.append(f"drawdown ${dd:,.0f} > {DD_CAP * 100:.0f}% of risk capital ${self.risk_capital:,.0f}: no new trades")
            day = eq.diff().dropna()
            if len(day) and day.iloc[-1] < -DAY_LOSS_CAP * self.risk_capital:
                out.append(f"day loss ${-day.iloc[-1]:,.0f} > {DAY_LOSS_CAP * 100:.0f}% of risk capital ${self.risk_capital:,.0f}: no new trades")
            day = eq.pct_change().dropna()
            if len(day) >= 100 and day.iloc[-1] <= day.quantile(0.01):
                self.brake_until = t + 5 * 86_400_000
        return out

    # ---- the book --------------------------------------------------------------
    def _net_ok(self, net: float, gross: float, count: int) -> bool:
        return count < NET_RULE_FROM or abs(net) <= NET_GROSS_MAX * gross + 1e-9

    def portfolio(self, t: int, pending: Optional[List[Order]] = None, labels: Optional[Dict[str, str]] = None) -> Dict:
        """What the book holds now (plus `pending`, orders accepted earlier in this decision) and
        how much room the net/gross, beta-band and cluster rules leave, computed by code and
        written in words the model can copy. Rows carry coin and label (the label is what the
        model sees)."""
        labels = labels or {}
        rows, net, gross, clusters = [], 0.0, 0.0, {}
        for c, p in self.book.positions.items():
            b = self._xs("beta_btc", t, c); b = 1.0 if b is None else b
            k = self._xs("cluster_id", t, c)
            px = self.data.price(t, c)
            pnl = None if px is None else round(((1 if p.side == "long" else -1) * (px / p.entry_px - 1) * 1e4), 0)
            sg = 1 if p.side == "long" else -1
            rows.append({"coin": c, "label": labels.get(c, c), "side": p.side, "beta_btc": round(b, 2),
                         "cluster": None if k is None else int(k), "notional": round(p.notional, 1),
                         "days_held": round((t - p.entry_ts) / 86_400_000, 1), "pnl_bps_so_far": pnl})
            net += sg * b * p.notional; gross += abs(b) * p.notional
            if k is not None:
                clusters[int(k)] = clusters.get(int(k), 0) + 1
        for o in (pending or []):
            b = self._xs("beta_btc", t, o.coin); b = 1.0 if b is None else b
            k = self._xs("cluster_id", t, o.coin)
            n = self.book.trade_size * o.size_mult
            rows.append({"coin": o.coin, "label": labels.get(o.coin, o.coin), "side": o.side, "beta_btc": round(b, 2),
                         "cluster": None if k is None else int(k), "notional": round(n, 1), "days_held": 0, "pnl_bps_so_far": None,
                         "pending": True})
            net += (1 if o.side == "long" else -1) * b * n; gross += abs(b) * n
            if k is not None:
                clusters[int(k)] = clusters.get(int(k), 0) + 1
        count = len(rows)
        longs = sum(1 for r in rows if r["side"] == "long"); shorts = count - longs
        unit = self.book.trade_size
        free_slots = max(0, self.book.max_positions - count)

        def fits(side: str, beta: float, net_=None, gross_=None, count_=None) -> bool:
            sg = 1 if side == "long" else -1
            n2 = (net if net_ is None else net_) + sg * beta * unit
            g2 = (gross if gross_ is None else gross_) + abs(beta) * unit
            c2 = (count if count_ is None else count_) + 1
            return self._net_ok(n2, g2, c2) and abs(n2) <= BETA_BAND * self.risk_capital

        def how_many(side: str) -> int:
            n_, g_, c_, k = net, gross, count, 0
            sg = 1 if side == "long" else -1
            while k < free_slots and fits(side, 1.0, n_, g_, c_):
                n_ += sg * unit; g_ += unit; c_ += 1; k += 1
            return k

        def max_beta(side: str) -> Optional[float]:
            if free_slots == 0:
                return None
            lo, hi = 0.0, 3.0
            if not fits(side, lo):
                return 0.0
            for _ in range(30):
                mid = (lo + hi) / 2
                if fits(side, mid):
                    lo = mid
                else:
                    hi = mid
            return round(lo, 2)

        more_l, more_s = how_many("long"), how_many("short")
        mb_l, mb_s = max_beta("long"), max_beta("short")
        full = sorted(k for k, n in clusters.items() if n >= CLUSTER_CAP)
        lean = None if gross == 0 else round(net / gross, 2)
        if count == 0:
            words = "Book is empty: anything fits."
        else:
            side_word = "long" if net > 0 else "short" if net < 0 else "flat"
            words = (f"Book: {longs} long, {shorts} short; net beta ${net:,.0f} of gross ${gross:,.0f} "
                     f"({abs(lean or 0) * 100:.0f}% one way, {side_word}). Rule: from {NET_RULE_FROM} positions net must be <= "
                     f"{NET_GROSS_MAX * 100:.0f}% of gross. Room now: {more_l} more beta-1 long(s), {more_s} more beta-1 short(s)"
                     + (f"; a long fits only with beta_btc <= {mb_l}" if mb_l is not None and mb_l < 3.0 else "")
                     + (f"; a short fits only with beta_btc <= {mb_s}" if mb_s is not None and mb_s < 3.0 else "")
                     + (f". Clusters full (cap {CLUSTER_CAP}): {full}" if full else "")
                     + f". Free slots: {free_slots} of {self.book.max_positions}.")
        return {"positions": rows, "count": count, "longs": longs, "shorts": shorts,
                "net_beta_usd": round(net, 1), "gross_beta_usd": round(gross, 1), "net_over_gross": lean,
                "risk_capital": self.risk_capital, "beta_band_usd": round(BETA_BAND * self.risk_capital, 1),
                "clusters": clusters, "clusters_full": full, "free_slots": free_slots,
                "room": {"more_longs_beta1": more_l, "more_shorts_beta1": more_s, "max_beta_long": mb_l, "max_beta_short": mb_s},
                "words": words}

    # ---- the review ------------------------------------------------------------
    def review(self, orders: List[Order], t: int, conf: Dict[str, float], table: pd.DataFrame,
               labels: Dict[str, str], setup: str, equity: float,
               pending: Optional[List[Order]] = None) -> Tuple[List[Order], List[Dict], List[Dict]]:
        """Returns (accepted orders, verdicts, bounces). A bounce is a violation list the
        strategist may fix once; the caller re-submits and the second review is final.
        `pending` = orders already accepted in this decision (count like open positions)."""
        kept, verdicts, bounces = [], [], []
        hard = self.brakes(t)
        halve = self.brake_until is not None and t <= self.brake_until
        pending = pending or []
        open_pos = list(self.book.positions) + [o.coin for o in pending]
        cluster_of = {c: self._xs("cluster_id", t, c) for c in open_pos + [o.coin for o in orders]}
        cluster_count: Dict[float, int] = {}
        for c in open_pos:
            k = cluster_of.get(c)
            if k is not None:
                cluster_count[k] = cluster_count.get(k, 0) + 1
        beta_exp = sum((1 if p.side == "long" else -1) * (self._xs("beta_btc", t, c) or 1.0) * p.notional
                       for c, p in self.book.positions.items())
        beta_exp += sum((1 if o.side == "long" else -1) * (self._xs("beta_btc", t, o.coin) or 1.0) * self.book.trade_size * o.size_mult
                        for o in pending)
        gross_exp = sum(abs(self._xs("beta_btc", t, c) or 1.0) * p.notional for c, p in self.book.positions.items())
        gross_exp += sum(abs(self._xs("beta_btc", t, o.coin) or 1.0) * self.book.trade_size * o.size_mult for o in pending)
        n_open = len(open_pos)
        cap = self.risk_capital
        btc_sigma, sigma_note = 0.0, ""
        try:
            b = self.data.closes(t, 61, ["BTC"])["BTC"].pct_change().dropna()
            btc_sigma = float(b.std()) if len(b) >= 20 else 0.0
            if not btc_sigma:
                sigma_note = f"stress check skipped: only {len(b)} BTC days"
        except (KeyError, IndexError) as e:
            sigma_note = f"stress check skipped: {type(e).__name__}"
        stress_loss = sum((1 if p.side == "long" else -1) * (self._xs("beta_stress", t, c) or 1.4) * 3 * btc_sigma * p.notional
                          for c, p in self.book.positions.items())
        stress_loss += sum((1 if o.side == "long" else -1) * (self._xs("beta_stress", t, o.coin) or 1.4) * 3 * btc_sigma * self.book.trade_size * o.size_mult
                           for o in pending)
        for o in orders:
            lab = labels.get(o.coin, o.coin)
            v: Dict = {"label": lab, "coin": o.coin, "side": o.side, "checks": {}, "violations": [], "action": "accept"}
            if hard:
                v["action"] = "reject"; v["violations"] = list(hard); verdicts.append(v); continue
            dm, dm_src = self.daily_move(t, o.coin, table, lab)
            if dm is None:
                v["action"] = "reject"; v["violations"] = ["no volatility data for this coin - cannot size or place a stop"]
                v["checks"]["daily_move_source"] = dm_src; verdicts.append(v); continue
            stop_moves = o.stop_pct * 100 / dm; tgt_moves = o.target_pct * 100 / dm
            v["checks"].update({"daily_move_pct": round(dm, 2), "daily_move_source": dm_src,
                                "stop_in_moves": round(stop_moves, 2), "target_in_moves": round(tgt_moves, 2),
                                "target_over_stop": round(o.target_pct / o.stop_pct, 2) if o.stop_pct else None,
                                "r2_btc": self._xs("r2_btc", t, o.coin), "beta_btc": self._xs("beta_btc", t, o.coin),
                                "beta_stress": self._xs("beta_stress", t, o.coin), "cluster": cluster_of.get(o.coin)})
            fix: Dict = {}
            if not (STOP_MIN - TOL <= stop_moves <= STOP_MAX + TOL):
                lo, hi = STOP_MIN * dm / 100, STOP_MAX * dm / 100
                # the suggested stop lands strictly inside the band after 4-decimal rounding
                fix["stop_pct"] = round(min(max(o.stop_pct, lo * 1.02), hi * 0.98), 4)
                v["violations"].append(f"stop {o.stop_pct * 100:.1f}% = {stop_moves:.2f} daily moves ({dm:.2f}%/day); allowed {lo * 100:.1f}%..{hi * 100:.1f}%")
            need_t = max(TARGET_MIN_MOVES * dm / 100, TARGET_MIN_RATIO * fix.get("stop_pct", o.stop_pct))
            if o.target_pct < need_t * (1 - TOL):
                fix["target_pct"] = round(need_t * 1.02, 4)
                v["violations"].append(f"target {o.target_pct * 100:.1f}% below minimum {need_t * 100:.1f}% (2 daily moves and 1.5x stop)")
            tgt_use = fix.get("target_pct", o.target_pct)
            need_h = int(min(MAX_HOLD, max(1, math.ceil((tgt_use * 100 / dm) ** 2))))
            if o.hold_days < need_h:
                # hold is arithmetic on the target and the coin's move: the desk sets it and says so (no bounce)
                v["checks"]["hold_set_by_desk"] = f"{o.hold_days}d -> {need_h}d for a {tgt_use * 100:.1f}% target at {dm:.2f}%/day"
                o.hold_days = need_h
            if o.falsifier_pct is not None:
                stop_now = fix.get("stop_pct", o.stop_pct)
                default_f = (-1 if o.side == "long" else 1) * round(0.6 * stop_now * 100, 2)   # 60% of the stop, correct side
                wrong_side = (o.side == "long" and o.falsifier_pct >= 0) or (o.side == "short" and o.falsifier_pct <= 0)
                if abs(o.falsifier_pct) < 0.05:
                    v["violations"].append("falsifier of 0% is not a falsifier; needs a real price level")
                    fix["falsifier_pct"] = default_f
                elif wrong_side:
                    v["violations"].append(f"falsifier {o.falsifier_pct:+.1f}% is on the wrong side for a {o.side}")
                    fix["falsifier_pct"] = -abs(o.falsifier_pct) if o.side == "long" else abs(o.falsifier_pct)
                if abs(o.falsifier_pct) >= stop_now * 100 * (1 - TOL):
                    v["violations"].append(f"falsifier {abs(o.falsifier_pct):.1f}% not inside the stop {fix.get('stop_pct', o.stop_pct) * 100:.1f}%")
                    fix["falsifier_pct"] = default_f
            k = cluster_of.get(o.coin)
            if k is not None and cluster_count.get(k, 0) >= CLUSTER_CAP:
                v["violations"].append(f"cluster {int(k)} already has {cluster_count[k]} positions (cap {CLUSTER_CAP})")
                v["action"] = "reject"
            sign = 1 if o.side == "long" else -1
            beta = self._xs("beta_btc", t, o.coin) or 1.0
            notional = self.book.trade_size * o.size_mult
            net2, gross2 = beta_exp + sign * beta * notional, gross_exp + abs(beta) * notional
            v["checks"]["net_gross"] = {"net_usd": round(net2, 0), "gross_usd": round(gross2, 0),
                                        "positions_after": n_open + 1, "rule_from": NET_RULE_FROM, "max": NET_GROSS_MAX}
            if abs(net2) > BETA_BAND * cap:
                v["violations"].append(f"book beta exposure would be ${abs(net2):,.0f} > {BETA_BAND * 100:.0f}% of risk capital ${cap:,.0f}")
                v["action"] = "reject"
            if not self._net_ok(net2, gross2, n_open + 1):
                v["violations"].append(f"book would be {abs(net2) / gross2 * 100:.0f}% one way (net ${net2:,.0f} of gross ${gross2:,.0f}) "
                                       f"with {n_open + 1} positions; from {NET_RULE_FROM} positions net must be <= {NET_GROSS_MAX * 100:.0f}% of gross - "
                                       f"add the other side or a low-beta coin instead")
                v["action"] = "reject"
            bs = self._xs("beta_stress", t, o.coin) or 1.4
            sl = stress_loss + sign * bs * 3 * btc_sigma * notional
            v["checks"]["stress_loss_3sigma"] = round(abs(sl), 1)
            if sigma_note:
                v["checks"]["stress_note"] = sigma_note
            if btc_sigma and abs(sl) > STRESS_LOSS_CAP * cap:
                v["violations"].append(f"3-sigma BTC move would cost ${abs(sl):,.0f} > {STRESS_LOSS_CAP * 100:.0f}% of risk capital ${cap:,.0f}")
                v["action"] = "reject"
            cal = getattr(self.data, "calendar", None)
            nm = cal.next_macro_hours(t) if cal is not None else None
            v["checks"]["event_blackout"] = None if not nm else f"{nm['event']} in {nm['hours']}h"
            if nm and nm["hours"] <= 24:
                try:
                    chain = json.loads(o.thesis or "{}")
                except Exception:
                    chain = {}
                if not chain.get("event_note"):
                    v["violations"].append(f"{nm['event'].upper()} at {nm['utc']} is {nm['hours']}h away: the chain must say how it affects this trade (event_note) or wait")
                    fix["event_note"] = f"needs your note on {nm['event']} at {nm['utc']}"
            p_model = float(conf.get(o.coin, 0.5))
            p, pinfo = self.p_final(o.coin, o.side, p_model, t, setup)
            v["checks"].update(pinfo)
            # confidence cap by measured links (spec C26/B6): with no admitted link the chain is a hypothesis
            try:
                from .links import links_as_of
                admitted = [r for r in links_as_of(t) if r["status"] == "admitted"]
            except Exception:
                admitted = []
            if not admitted and p > LINK_CAP:
                v["checks"]["link_cap"] = f"no admitted link: p_final {p:.2f} -> {LINK_CAP}"
                p = LINK_CAP
            else:
                v["checks"]["link_cap"] = None if admitted else "p already <= cap"
            recent = self.recent_loss(o.coin, o.side, t)
            v["checks"]["recent_loss_same_side"] = recent
            if recent and p < RECENT_LOSS_P:
                v["violations"].append(f"{o.side} {o.coin} lost {recent['net_bps']:+.0f} bps {recent['days_ago']}d ago ({recent['exit_reason']}): "
                                       f"the same trade again needs p_final >= {RECENT_LOSS_P}, has {p:.2f}")
                v["action"] = "reject"
            fq = self.funding_quintile(t, o.coin)
            v["checks"]["funding_quintile"] = fq
            if fq == 4 and o.side == "long" and p < 0.60:
                v["violations"].append(f"long pays top-quintile funding (~22 bps/week measured); needs p_final >= 0.60, has {p:.2f}")
                v["action"] = "reject"
            if fq == 0 and o.side == "short" and p < 0.65:
                v["violations"].append(f"short pays bottom-quintile funding (crowd-short coins are paid ~48 bps/week); needs p_final >= 0.65, has {p:.2f}")
                v["action"] = "reject"
            stop_use = fix.get("stop_pct", o.stop_pct)
            kelly = min(max((2 * p - 1) * (stop_use / tgt_use) * 4, 0.0), 1.0)
            idio_ann = self._xs("idio_vol_30d", t, o.coin)
            vol_scale = min(max(VOL_TARGET_PCT / (idio_ann * 100), 0.25), 1.0) if idio_ann else 1.0
            size = kelly * vol_scale * (0.5 if halve else 1.0)
            v["checks"].update({"kelly_scale": round(kelly, 3), "vol_scale": round(vol_scale, 3), "cvar_brake": halve, "size_mult": round(size, 3)})
            if kelly <= 0:
                v["violations"].append(f"no edge at p_final {p:.2f} (needs > 0.5 after shrink and calibration)")
                v["action"] = "reject"
            if v["action"] == "reject":
                verdicts.append(v); continue
            if fix:
                v["action"] = "bounce"; v["fix"] = fix
                bounces.append({"label": lab, "coin": o.coin, "violations": v["violations"], "suggested": fix})
                verdicts.append(v); continue
            o.size_mult = min(o.size_mult, size) if o.size_mult < 1 else size
            v["checks"]["notional"] = round(self.book.trade_size * o.size_mult, 1)
            kept.append(o); verdicts.append(v)
            if k is not None:
                cluster_count[k] = cluster_count.get(k, 0) + 1
            beta_exp += sign * beta * self.book.trade_size * o.size_mult
            gross_exp += abs(beta) * self.book.trade_size * o.size_mult
            n_open += 1
            stress_loss += sign * bs * 3 * btc_sigma * self.book.trade_size * o.size_mult    # the sized order, same as beta_exp
        self.last = verdicts
        return kept, verdicts, bounces

    @staticmethod
    def apply_fix(o: Order, fix: Dict) -> Order:
        """Apply the risk hat's suggested numbers when the strategist accepts them verbatim.
        An event_note cannot be 'accepted' - it must be written by the strategist (replan)."""
        for k_, val in fix.items():
            if k_ == "event_note":
                continue
            setattr(o, k_, val)
        if "falsifier_pct" in fix and not o.falsifier_day:
            o.falsifier_day = 2
        return o
