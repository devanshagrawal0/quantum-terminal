"""Live desk call through ChatGPT: research + trade calls on today's market.

Step 1  packet   - live Hyperliquid data (metaAndAssetCtxs + 30d daily candles for the
                   candidates), our betas/clusters (xsec, last vintage), the calendar, Fear & Greed.
Step 2  research - ONE batched ChatGPT call with web access: per candidate the newest news,
                   scheduled unlock/listing/delisting/hack risk; plus the week's macro. Every
                   fact must carry a URL (codex_backend drops the rest).
Step 3  calls    - ONE ChatGPT call, no web, manual chapters attached, forced JSON: exactly
                   N trades with side / leverage / tp / sl / hold_hours / falsifier / thesis /
                   which research facts it used.
Step 4  settle   - later: `--settle <file>` fetches the hourly candles since entry from
                   Hyperliquid and settles every call (SL/TP on high/low, SL first; liquidation
                   at lev x adverse >= 100%; time exit; fees 4.5 bps + ~3 bps half spread per
                   side; funding from the hourly prints).

Usage:
  python scripts/desk_call.py                 # packet + research + calls, saved to data/desk_calls/<ts>.json
  python scripts/desk_call.py --no-research   # calls from the packet only (control run)
  python scripts/desk_call.py --settle data/desk_calls/<ts>.json
Nothing here touches an exchange account; read-only public endpoints only.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402

from sim.codex_backend import research, chat, login_status  # noqa: E402

OUT = ROOT / "data" / "desk_calls"
INFO = "https://api.hyperliquid.xyz/info"
MANUAL = ["ch03_btc_is_the_market.md", "ch05_the_crowd.md", "ch07_volatility_stops_sizing.md", "ch11_how_to_be_a_trader.md"]
N_TRADES = 5
N_CANDIDATES = 24


def hl(body: dict, timeout: int = 30):
    req = urllib.request.Request(INFO, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def daily_candles(coin: str, days: int = 35) -> pd.DataFrame:
    now = int(time.time() * 1000)
    c = hl({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1d", "startTime": now - days * 86_400_000, "endTime": now}})
    if not c:
        return pd.DataFrame()
    df = pd.DataFrame([{"t": int(x["t"]), "o": float(x["o"]), "h": float(x["h"]), "l": float(x["l"]), "c": float(x["c"]), "v": float(x["v"])} for x in c])
    return df.sort_values("t")


def hourly_candles(coin: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    c = hl({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1h", "startTime": start_ms, "endTime": end_ms}})
    if not c:
        return pd.DataFrame()
    df = pd.DataFrame([{"t": int(x["t"]), "o": float(x["o"]), "h": float(x["h"]), "l": float(x["l"]), "c": float(x["c"])} for x in c])
    return df.sort_values("t")


def funding_history(coin: str, start_ms: int, end_ms: int) -> float:
    r = hl({"type": "fundingHistory", "coin": coin, "startTime": start_ms, "endTime": end_ms})
    return float(sum(float(x["fundingRate"]) for x in r)) if r else 0.0


# ---------------------------------------------------------------- step 1: the packet
def build_packet() -> dict:
    meta, ctx = hl({"type": "metaAndAssetCtxs"})
    rows = []
    for u, c in zip(meta["universe"], ctx):
        if u.get("isDelisted"):
            continue
        try:
            mark, prev = float(c["markPx"]), float(c["prevDayPx"])
        except (TypeError, ValueError):
            continue
        if mark <= 0 or prev <= 0:
            continue
        rows.append({"coin": u["name"], "max_leverage": u.get("maxLeverage"), "mark": mark,
                     "r_1d": round(mark / prev - 1, 4), "funding_hourly": float(c["funding"]),
                     "funding_pct_per_day": round(float(c["funding"]) * 24 * 100, 4),
                     "oi_usd": round(float(c["openInterest"]) * mark, 0), "day_volume_usd": round(float(c["dayNtlVlm"]), 0),
                     "premium": float(c["premium"] or 0.0)})
    tab = pd.DataFrame(rows).set_index("coin")
    liquid = tab[tab["day_volume_usd"] >= 2_000_000]                       # tradeable at $100-400 notional
    # candidate set: funding extremes + 1-day movers + biggest OI, all from the liquid set
    cands = []
    for s in (liquid["funding_pct_per_day"].nlargest(6), liquid["funding_pct_per_day"].nsmallest(6),
              liquid["r_1d"].nlargest(6), liquid["r_1d"].nsmallest(6), liquid["day_volume_usd"].nlargest(8)):
        for coin in s.index:
            if coin not in cands:
                cands.append(coin)
    cands = cands[:N_CANDIDATES]
    for must in ("BTC", "ETH"):
        if must not in cands:
            cands.insert(0, must)
    # our cross-sectional layer (last vintage: candles in the store stop 2026-08-31 - stated in the packet)
    try:
        from sim.xsec import xsec
        x = xsec()
        def xs(key, coin):
            f = x["frames"].get(key)
            if f is None or coin not in f.columns:
                return None
            s = f[coin].dropna()
            return None if s.empty else float(s.iloc[-1])
        vintage = str(pd.to_datetime(x["frames"]["beta_btc"].index[-1], unit="ms").date())
    except Exception:  # noqa: BLE001
        xs, vintage = (lambda k, c: None), "unavailable"
    cand_rows = {}
    for coin in cands:
        d = daily_candles(coin)
        if d.empty or len(d) < 8:
            continue
        r = d["c"].pct_change().dropna()
        rv7 = float(r.tail(7).std() * math.sqrt(365)) if len(r) >= 7 else None
        rv30 = float(r.tail(30).std() * math.sqrt(365)) if len(r) >= 20 else None
        # own move: residual vol for alts; for BTC (residual of itself = 0) and any coin without a
        # residual estimate, the total 7-day move. Never a zero band.
        dm = xs("idio_daily_move_pct", coin)
        if coin == "BTC" or not dm or dm < 0.3:
            dm = rv7 / math.sqrt(365) * 100 if rv7 else None
        cand_rows[coin] = {
            "mark": tab.at[coin, "mark"], "r_1d": tab.at[coin, "r_1d"],
            "r_7d": round(float(d["c"].iloc[-1] / d["c"].iloc[-8] - 1), 4),
            "r_30d": round(float(d["c"].iloc[-1] / d["c"].iloc[0] - 1), 4) if len(d) >= 30 else None,
            "rv_7d_ann": round(rv7, 3) if rv7 else None, "rv_30d_ann": round(rv30, 3) if rv30 else None,
            "own_daily_move_pct": round(dm, 2) if dm else None,
            "stop_pct_allowed_1p5_to_3_own_moves": (f"{1.5 * dm / 100:.4f}-{3 * dm / 100:.4f}" if dm else None),
            "beta_btc": xs("beta_btc", coin), "share_of_moves_explained_by_btc": xs("r2_btc", coin),
            "beta_crash_days": xs("beta_stress", coin), "cluster": xs("cluster_id", coin),
            "funding_pct_per_day": tab.at[coin, "funding_pct_per_day"],
            "crowd": ("longs pay shorts - crowded LONG (squeeze DOWN)" if tab.at[coin, "funding_hourly"] > 0.0000125 * 2
                      else "shorts pay longs - crowded SHORT (squeeze UP)" if tab.at[coin, "funding_hourly"] < 0
                      else "near the interest baseline - not crowded"),
            "oi_usd": tab.at[coin, "oi_usd"], "day_volume_usd": tab.at[coin, "day_volume_usd"],
            "premium_vs_oracle": tab.at[coin, "premium"], "max_leverage": int(tab.at[coin, "max_leverage"] or 0)}
    btc = daily_candles("BTC", 40)
    regime = {"btc_30d": round(float(btc["c"].iloc[-1] / btc["c"].iloc[-31] - 1), 4) if len(btc) >= 31 else None,
              "btc_7d": round(float(btc["c"].iloc[-1] / btc["c"].iloc[-8] - 1), 4) if len(btc) >= 8 else None,
              "breadth_1d_pct_green": round(float((tab["r_1d"] > 0).mean() * 100), 1),
              "n_perps": int(len(tab)), "n_liquid": int(len(liquid))}
    try:
        fng = json.loads(urllib.request.urlopen("https://api.alternative.me/fng/?limit=7", timeout=10).read())["data"]
        fear_greed = {"now": int(fng[0]["value"]), "label": fng[0]["value_classification"], "last_7": [int(x["value"]) for x in fng]}
    except Exception:  # noqa: BLE001
        fear_greed = None
    try:
        from sim.events import Calendar
        cal = Calendar()
        ev = cal.upcoming(int(time.time() * 1000), days=7)
        events = ev.head(20).to_dict(orient="records") if hasattr(ev, "to_dict") else ev
    except Exception as e:  # noqa: BLE001
        events = f"calendar unavailable: {type(e).__name__}"
    return {"now_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "regime": regime, "fear_greed": fear_greed,
            "calendar_next_7d": events, "xsec_vintage": vintage,
            "note": "betas/clusters/own-move are from our store as of xsec_vintage; prices, funding, OI, volume are live",
            "funding_extremes_pct_per_day": {"most_positive": liquid["funding_pct_per_day"].nlargest(8).round(4).to_dict(),
                                             "most_negative": liquid["funding_pct_per_day"].nsmallest(8).round(4).to_dict()},
            "movers_1d": {"up": liquid["r_1d"].nlargest(8).to_dict(), "down": liquid["r_1d"].nsmallest(8).to_dict()},
            "candidates": cand_rows}


# ---------------------------------------------------------------- step 2a: the desk writes its own questions
ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "shortlist": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
        "why": {"type": "string"}},
    "required": ["shortlist", "questions", "why"], "additionalProperties": False}

ASK_RULES = (
    "You are the strategist on a crypto perpetuals desk (Hyperliquid, US-hours desk, $100-400 per trade). Below is the live "
    "packet: the whole board, ~30 candidates in depth (returns 1h-30d, vol and the stop band, BTC beta/R2, funding + OI change + "
    "OKX funding + Korean premium, order book), market context (BTC, breadth, dominance, fear/greed, session, calendar, measured "
    "calendar tilts, measured links) and your own last runs with their outcomes and lessons. Read your own record FIRST. "
    "Then decide what you need the research desk (web access, Google, primary sources) to find before you trade. Choose at most 6 "
    "coins (the shortlist - the ones with an asymmetric setup: crowded and unrewarded, OI jump, unusual move, catalyst) and write "
    "at most 8 precise questions. Cover what the packet cannot: the coin's newest catalysts (7d) and scheduled events (14d: unlocks, "
    "listings/delistings on Binance/OKX/Upbit/Bithumb/Coinbase, governance, mainnet, hacks); large-holder / whale / treasury moves; "
    "international news that moves crypto now (US, EU, Korea, Japan, China regulation; ETF flows; stablecoin issuance); the macro "
    "calendar for the next 3 days with UTC times; anything that explains an OI jump or a funding extreme. Each question names the "
    "coin or topic and the time window and ends with 'At most 2 searches; primary sources; say not_found if nothing.' "
    "Do not ask for opinions or predictions. Answer ONLY in the required JSON."
)


def ask_questions(packet: dict) -> dict:
    prompt = ASK_RULES + chr(10) + chr(10) + "=== DESK PACKET (live) ===" + chr(10) + json.dumps(packet, default=str)
    return chat(prompt, ASK_SCHEMA, tag="ask", timeout_s=600, web=False, effort="low")


# ---------------------------------------------------------------- step 2b: default questions (fallback if the ask step fails)
def research_questions(packet: dict) -> list[str]:
    qs = []
    for coin in packet["candidates"]:
        qs.append(f"{coin}: the single most important news item about this token in the last 7 days (title, date, URL, one-line quote) - "
                  f"and any scheduled token unlock, exchange listing/delisting, hack, or governance vote in the next 14 days. "
                  f"At most 2 searches; if nothing found say not_found.")
    qs.append("Crypto market this week: the scheduled US macro releases and Fed events in the next 7 days with dates/times (UTC), "
              "and any exchange outage, regulatory action or large hack in the last 3 days. At most 3 searches.")
    qs.append("Spot BTC ETF net flows for the last 5 trading days (daily figures with source URL). At most 2 searches.")
    return qs


# ---------------------------------------------------------------- step 3: the calls
CALL_SCHEMA = {
    "type": "object",
    "properties": {
        "market_read": {"type": "string"},
        "trades": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"}, "side": {"type": "string", "enum": ["long", "short"]},
                "kind": {"type": "string", "enum": ["intraday", "swing"]},
                "leverage": {"type": "integer"}, "tp_pct": {"type": "number"}, "sl_pct": {"type": "number"},
                "hold_hours": {"type": "integer"},
                "falsifier": {"type": "object", "properties": {"hours": {"type": "integer"}, "move": {"type": "number"}},
                              "required": ["hours", "move"], "additionalProperties": False},
                "checkpoint": {"type": "object", "properties": {"hours": {"type": "integer"}, "move": {"type": "number"}},
                               "required": ["hours", "move"], "additionalProperties": False},
                "thesis": {"type": "string"}, "mechanism": {"type": "string"},
                "research_facts_used": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number"}},
            "required": ["coin", "side", "kind", "leverage", "tp_pct", "sl_pct", "hold_hours", "falsifier", "checkpoint",
                         "thesis", "mechanism", "research_facts_used", "confidence"],
            "additionalProperties": False}},
        "book_note": {"type": "string"},
        "what_i_did_not_trade_and_why": {"type": "array", "items": {"type": "string"}}},
    "required": ["market_read", "trades", "book_note", "what_i_did_not_trade_and_why"],
    "additionalProperties": False,
}

N_INTRADAY = 2
LEV_BY_CONF = [(0.65, 4), (0.60, 3), (0.55, 2), (0.0, 1)]     # confidence floor -> leverage (desk-enforced after the call)
MAX_MARGIN_LOSS_AT_STOP = 0.60                               # lev x sl <= 60% of the $100 margin

CALL_RULES = (
    f"You are the strategist on a crypto perpetuals desk (Hyperliquid). Open EXACTLY {N_TRADES} trades now: "
    f"{N_INTRADAY} INTRADAY (kind='intraday', hold_hours 3-12, on coins with a live 1h/4h move, an OI jump, a funding print or a "
    f"catalyst inside the window; stop 0.5-1.0 x the coin's own DAILY move) and {N_TRADES - N_INTRADAY} SWING (kind='swing', "
    "hold_hours 24-72; stop inside stop_band_1p5_to_3_own_moves). Use ONLY the desk packet and the research report below; cite "
    "the research facts you used by their URL in research_facts_used (empty list if none). Read your own record in the packet first. "
    "Units: tp_pct, sl_pct and every `move` are FRACTIONS OF PRICE (0.06 = 6%). tp_pct >= 1.5 x sl_pct. "
    "Leverage is set BY CONVICTION and the desk enforces it: confidence < 0.55 -> 1x, 0.55-0.60 -> 2x, 0.60-0.65 -> 3x, >= 0.65 -> 4x, "
    "never above the coin's max_leverage, and leverage x sl_pct <= 0.60 (you cannot lose more than 60% of margin at the stop). "
    "So state your honest confidence; it decides the size. The falsifier is a price move on the wrong side, smaller than the stop, "
    "with an hour by which it is judged. The checkpoint is what should have happened by that hour if the mechanism works. "
    "thesis = one sentence on WHO has to trade and WHY. Also list the coins you considered and rejected, with the reason. "
    "Answer ONLY in the required JSON."
)


def enforce_desk_rules(trades: list, packet: dict) -> list:
    """Code, not the model, sets leverage from confidence and clamps the stop into the band for the trade kind.
    Every change is written into the trade as desk_fixes so the review can see it."""
    out = []
    for t in trades:
        fixes = []
        row = (packet.get("candidates", {}).get(t["coin"]) or {})
        dm = (row.get("vol") or {}).get("own_daily_move_pct") or row.get("own_daily_move_pct")
        maxlev = int((row.get("liquidity") or {}).get("max_leverage") or row.get("max_leverage") or 4)
        conf = float(t.get("confidence") or 0.5)
        lev_rule = next(l for floor, l in LEV_BY_CONF if conf >= floor)
        lev = min(lev_rule, maxlev, 4)
        sl = abs(float(t["sl_pct"])); tp = abs(float(t["tp_pct"]))
        kind = t.get("kind") or ("intraday" if int(t.get("hold_hours", 72)) <= 12 else "swing")
        if dm:
            lo, hi = ((0.5 * dm / 100, 1.0 * dm / 100) if kind == "intraday" else (1.5 * dm / 100, 3.0 * dm / 100))
            if not (lo * 0.99 <= sl <= hi * 1.01):
                new_sl = min(max(sl, lo), hi)
                fixes.append(f"sl {sl:.4f} -> {new_sl:.4f} ({kind} band {lo:.4f}-{hi:.4f}, own move {dm}%/d)")
                sl = round(new_sl, 4)
        if tp < 1.5 * sl:
            fixes.append(f"tp {tp:.4f} -> {1.5 * sl:.4f} (>= 1.5 x sl)")
            tp = round(1.5 * sl, 4)
        while lev > 1 and lev * sl > MAX_MARGIN_LOSS_AT_STOP:
            lev -= 1
        if lev != int(t.get("leverage", 1)):
            fixes.append(f"leverage {t.get('leverage')} -> {lev} (conviction {conf:.2f}; max {maxlev}; lev x sl <= {MAX_MARGIN_LOSS_AT_STOP})")
        hold = int(t.get("hold_hours", 72))
        lo_h, hi_h = (3, 12) if kind == "intraday" else (24, 72)
        if not (lo_h <= hold <= hi_h):
            fixes.append(f"hold {hold}h -> {min(max(hold, lo_h), hi_h)}h ({kind})")
            hold = min(max(hold, lo_h), hi_h)
        t2 = dict(t); t2.update({"leverage": lev, "sl_pct": sl, "tp_pct": tp, "hold_hours": hold, "kind": kind, "desk_fixes": fixes})
        out.append(t2)
    return out


def make_calls(packet: dict, report: dict | None, with_manual: bool = True) -> dict:
    manual = ""
    if with_manual:
        manual = "\n\n=== DESK MANUAL (reference; apply it) ===\n" + "\n\n".join(
            io.open(ROOT / "docs" / "manual" / f, encoding="utf-8").read() for f in MANUAL)
    prompt = (CALL_RULES + manual + "\n\n=== DESK PACKET (live) ===\n" + json.dumps(packet, default=str) +
              "\n\n=== RESEARCH REPORT (web, URL-stamped) ===\n" + (json.dumps(report, default=str) if report else "none (control run)"))
    return chat(prompt, CALL_SCHEMA, tag="calls", timeout_s=900, web=False)


# ---------------------------------------------------------------- step 4: settle
def settle(run: dict) -> dict:
    t_entry = int(run["entry_ms"])
    now = int(time.time() * 1000)
    out, total = [], 0.0
    for tr in run["calls"]["data"]["trades"]:
        coin = tr["coin"]
        pk = run["packet"]
        entry = (pk.get("candidates", {}).get(coin, {}) or {}).get("mark") or (pk.get("board", {}).get(coin, {}) or {}).get("mark")
        if entry is None:
            out.append({"coin": coin, "error": "no entry mark in packet"}); continue
        hold = min(72, int(tr["hold_hours"]))
        end = min(now, t_entry + hold * 3_600_000)
        path = hourly_candles(coin, t_entry, end)
        if path.empty:
            out.append({"coin": coin, "error": "no candles yet"}); continue
        sg = 1 if tr["side"] == "long" else -1
        lev = max(1, min(4, int(tr["leverage"]))); tp, sl = abs(float(tr["tp_pct"])), abs(float(tr["sl_pct"]))
        exit_px, reason, hrs = None, "open" if end < t_entry + hold * 3_600_000 else "time", len(path)
        # the trade's own falsifier (a wrong-side close by hour h) and any desk action (cut) recorded by the watcher
        fz = tr.get("falsifier") or {}
        try:
            fz_h, fz_mv = int(fz.get("hours")), float(fz.get("move"))
        except Exception:
            fz_h, fz_mv = None, None
        cut_at = min([int(a["at_ms"]) for a in run.get("actions", []) if a.get("coin") == coin and a.get("action") == "cut"] or [None]) \
            if run.get("actions") else None
        for i, r in path.iterrows():
            adverse = (1 - r["l"] / entry) if sg > 0 else (r["h"] / entry - 1)
            favour = (r["h"] / entry - 1) if sg > 0 else (1 - r["l"] / entry)
            if adverse * lev >= 1.0:
                exit_px, reason, hrs = entry * (1 - sg / lev), "liquidated", i + 1; break
            if adverse >= sl:
                exit_px, reason, hrs = entry * (1 - sg * sl), "stop", i + 1; break
            if favour >= tp:
                exit_px, reason, hrs = entry * (1 + sg * tp), "target", i + 1; break
            close_fav = sg * (float(r["c"]) / entry - 1)
            if fz_h is not None and i + 1 <= fz_h and close_fav <= sg * fz_mv and run.get("enforce_falsifier", True):
                exit_px, reason, hrs = float(r["c"]), "falsifier", i + 1; break
            if cut_at is not None and int(r["t"]) + 3_600_000 > cut_at:
                exit_px, reason, hrs = float(r["c"]), "cut", i + 1; break
        if exit_px is None:
            exit_px = float(path["c"].iloc[-1])
        move = sg * (exit_px / entry - 1)
        margin = float(tr.get("margin_usd") or 100.0)
        notional = margin * lev
        fees = notional * 2 * (0.00045 + 0.0003)
        fund = -sg * funding_history(coin, t_entry, t_entry + hrs * 3_600_000) * notional
        pnl = move * notional - fees + fund
        total += pnl
        row = run["packet"].get("candidates", {}).get(coin, {}) or {}
        dm = row.get("own_daily_move_pct") or (row.get("vol") or {}).get("own_daily_move_pct")     # packet v1 / v2
        # the path in the trade's favour, hour by hour, and where the falsifier / checkpoint stand
        path_pct = [round(sg * (float(c) / entry - 1) * 100, 2) for c in path["c"].iloc[:hrs].tolist()]
        inside = path.iloc[:hrs]
        mfe = float(inside["h"].max() / entry - 1) if sg > 0 else float(1 - inside["l"].min() / entry)
        mae = float(inside["l"].min() / entry - 1) if sg > 0 else float(1 - inside["h"].max() / entry)

        def gate(g, kind):
            try:
                h, mv = int(g.get("hours")), float(g.get("move"))
            except Exception:
                return {"status": "none"}
            fav = sg * mv * 100                                   # the gate's move, in the trade's favour
            if kind == "falsifier":                               # a wrong-side move: hit if the path went at least that far against
                hit = any(x <= fav for x in path_pct[:h]) if path_pct else False
                st = "HIT" if hit else ("armed" if hrs < h and reason == "open" else "not triggered")
            else:                                                 # checkpoint: judged at hour h
                if len(path_pct) >= h:
                    st = "HIT" if path_pct[h - 1] >= fav else "MISSED"
                else:
                    st = "due" if reason == "open" else "closed before"
            return {"status": st, "hours": h, "move_pct": round(mv * 100, 2), "at_hour": h}
        out.append({"coin": coin, "side": tr["side"], "kind": tr.get("kind"), "lev": lev, "tp": tp, "sl": sl, "hold_h": hold, "entry": entry,
                    "exit": round(exit_px, 6), "reason": reason, "hours": hrs, "price_move_pct": round(move * 100, 2),
                    "pnl_usd_on_100_margin": round(pnl, 2), "fees_usd": round(fees, 2), "funding_usd": round(fund, 2),
                    "r_multiple": round(pnl / (sl * notional), 2) if sl else None, "margin_usd": margin, "notional_usd": round(notional, 2),
                    "sl_in_own_moves": round(sl * 100 / dm, 2) if dm else None, "own_daily_move_pct": dm,
                    "path_pct": path_pct, "mfe_pct": round(mfe * 100, 2), "mae_pct": round(mae * 100, 2),
                    "dist_to_tp_pct": round((tp - move) * 100, 2) if reason == "open" else None,
                    "dist_to_sl_pct": round((sl + move) * 100, 2) if reason == "open" else None,
                    "falsifier": gate(tr.get("falsifier") or {}, "falsifier"), "checkpoint": gate(tr.get("checkpoint") or {}, "checkpoint"),
                    "confidence": tr.get("confidence"), "desk_fixes": tr.get("desk_fixes", []),
                    "closed_ms": t_entry + hrs * 3_600_000 if reason != "open" else None,
                    "thesis": tr.get("thesis"), "mechanism": tr.get("mechanism"), "research_facts_used": tr.get("research_facts_used", [])})
    return {"settled_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "trades": out, "total_pnl_usd": round(total, 2)}


# ---------------------------------------------------------------- step 5: the review (learning from the trade)
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "reviews": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"},
                "why_entered": {"type": "string"},
                "what_happened": {"type": "string"},
                "what_was_right": {"type": "string"},
                "what_was_wrong": {"type": "string"},
                "how_it_went_the_other_way": {"type": "string"},
                "visible_and_unused": {"type": "string"},
                "loss_class": {"type": "string", "enum": ["thesis", "timing", "risk_plan", "regime", "none_it_won", "unknown"]},
                "exit_quality": {"type": "string", "enum": ["perfect", "left_money", "got_out_in_time", "noise_stop", "too_early", "too_late"]},
                "hold_next_time": {"type": "string", "enum": ["shorter", "same", "longer"]},
                "stop_next_time": {"type": "string", "enum": ["tighter", "same", "wider"]},
                "next_time": {"type": "string"},
                "lesson_one_line": {"type": "string"}},
            "required": ["coin", "why_entered", "what_happened", "what_was_right", "what_was_wrong", "how_it_went_the_other_way",
                         "visible_and_unused", "loss_class", "exit_quality", "hold_next_time", "stop_next_time", "next_time", "lesson_one_line"],
            "additionalProperties": False}},
        "book_lesson": {"type": "string"},
        "what_to_research_next_time": {"type": "array", "items": {"type": "string"}}},
    "required": ["reviews", "book_lesson", "what_to_research_next_time"],
    "additionalProperties": False,
}

REVIEW_RULES = (
    "You are the reviewer on a crypto perpetuals desk. Below are trades the desk opened, with the full chain it wrote at entry "
    "(thesis, mechanism, falsifier, checkpoint, research facts used), the real hourly price path since entry, how each trade "
    "exited, its best and worst point (MFE/MAE), the price after the exit, funding paid or received, and what the research desk "
    "found during the trade. Judge the DECISION, not the outcome: a loss with a correct process is a good decision; a win with a "
    "broken thesis is a bad one. For each trade answer every field plainly, with numbers from the data. 'how_it_went_the_other_way': "
    "if price did the opposite of the thesis, explain what actually moved it. 'visible_and_unused': a fact that was in the packet or "
    "research at entry and should have changed the call (or 'none'). Then one lesson for the book and what to research next time. "
    "Answer ONLY in the required JSON."
)


def _path_stats(path: pd.DataFrame, entry: float, sg: int, exit_hours: int) -> dict:
    """MFE/MAE inside the trade and the price 6h / 24h after the exit (on the same hourly path)."""
    inside = path.iloc[:exit_hours] if exit_hours else path
    if inside.empty:
        return {}
    if sg > 0:
        mfe = float(inside["h"].max() / entry - 1); mae = float(inside["l"].min() / entry - 1)
    else:
        mfe = float(1 - inside["l"].min() / entry); mae = float(1 - inside["h"].max() / entry)
    after = path.iloc[exit_hours:] if exit_hours < len(path) else pd.DataFrame()

    def at(h):
        if after.empty or len(after) < h:
            return None
        return round(sg * (float(after["c"].iloc[h - 1]) / entry - 1) * 100, 2)
    return {"mfe_pct": round(mfe * 100, 2), "mae_pct": round(mae * 100, 2),
            "move_6h_after_exit_pct": at(6), "move_24h_after_exit_pct": at(24),
            "hourly_closes_pct": [round(sg * (float(c) / entry - 1) * 100, 2) for c in path["c"].tolist()]}


def review(run: dict) -> dict:
    """Build the review packet from the last settlement and ask ChatGPT for the lessons."""
    settled = run["settlements"][-1]
    t_entry = int(run["entry_ms"]); now = int(time.time() * 1000)
    trades_at_entry = {t["coin"]: t for t in run["calls"]["data"]["trades"]}
    items = []
    for s in settled["trades"]:
        if "error" in s:
            continue
        coin = s["coin"]; sg = 1 if s["side"] == "long" else -1
        path = hourly_candles(coin, t_entry, min(now, t_entry + (int(s["hold_h"]) + 24) * 3_600_000))
        stats = _path_stats(path, s["entry"], sg, int(s["hours"])) if not path.empty else {}
        items.append({"at_entry": trades_at_entry.get(coin), "settlement": s, "path": stats,
                      "packet_row_at_entry": run["packet"]["candidates"].get(coin)})
    news_now = None
    try:
        qs = [f"{it['settlement']['coin']}: what moved this token between {run['packet']['now_utc']} UTC and now? Newest dated news "
              f"or on-chain/exchange event with URL. At most 2 searches; say not_found if nothing." for it in items[:5]]
        r = research(qs, {"trades": [{k: it["settlement"][k] for k in ("coin", "side", "reason", "price_move_pct")} for it in items]},
                     tag="review_research", timeout_s=900)
        news_now = r.get("data") if r.get("ok") else {"error": r.get("error")}
    except Exception as e:  # noqa: BLE001
        news_now = {"error": f"{type(e).__name__}: {e}"}
    prompt = (REVIEW_RULES + chr(10) + chr(10) + "=== TRADES ===" + chr(10) + json.dumps(items, default=str) +
              chr(10) + chr(10) + "=== MARKET READ AT ENTRY ===" + chr(10) + str(run["calls"]["data"].get("market_read")) +
              chr(10) + chr(10) + "=== WHAT RESEARCH FOUND DURING THE TRADE ===" + chr(10) + json.dumps(news_now, default=str))
    out = chat(prompt, REVIEW_SCHEMA, tag="review", timeout_s=900, web=False)
    return {"reviewed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "news_during": news_now, "result": out}


# ---------------------------------------------------------------- deep mode: one unbounded session, no structure from us
DEEP_SCHEMA = {
    "type": "object",
    "properties": {
        "research_log": {"type": "array", "items": {
            "type": "object",
            "properties": {"topic": {"type": "string"}, "what_i_found": {"type": "string"},
                           "sources": {"type": "array", "items": {"type": "string"}}, "matters_because": {"type": "string"}},
            "required": ["topic", "what_i_found", "sources", "matters_because"], "additionalProperties": False}},
        "market_read": {"type": "string"},
        "theories": {"type": "array", "items": {
            "type": "object",
            "properties": {"claim": {"type": "string"}, "mechanism": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "string"}},
                           "what_would_kill_it": {"type": "string"}, "coins": {"type": "array", "items": {"type": "string"}}},
            "required": ["claim", "mechanism", "evidence", "what_would_kill_it", "coins"], "additionalProperties": False}},
        "trades": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"}, "side": {"type": "string", "enum": ["long", "short"]},
                "kind": {"type": "string", "enum": ["intraday", "swing"]}, "leverage": {"type": "integer"},
                "margin_usd": {"type": "number"}, "tp_pct": {"type": "number"}, "sl_pct": {"type": "number"}, "hold_hours": {"type": "integer"},
                "falsifier": {"type": "object", "properties": {"hours": {"type": "integer"}, "move": {"type": "number"}},
                              "required": ["hours", "move"], "additionalProperties": False},
                "checkpoint": {"type": "object", "properties": {"hours": {"type": "integer"}, "move": {"type": "number"}},
                               "required": ["hours", "move"], "additionalProperties": False},
                "thesis": {"type": "string"}, "mechanism": {"type": "string"}, "why_now": {"type": "string"},
                "what_the_crowd_is_missing": {"type": "string"},
                "research_facts_used": {"type": "array", "items": {"type": "string"}}, "confidence": {"type": "number"}},
            "required": ["coin", "side", "kind", "leverage", "margin_usd", "tp_pct", "sl_pct", "hold_hours", "falsifier", "checkpoint",
                         "thesis", "mechanism", "why_now", "what_the_crowd_is_missing", "research_facts_used", "confidence"],
            "additionalProperties": False}},
        "book_note": {"type": "string"},
        "what_i_did_not_trade_and_why": {"type": "array", "items": {"type": "string"}},
        "what_i_still_do_not_know": {"type": "array", "items": {"type": "string"}}},
    "required": ["research_log", "market_read", "theories", "trades", "book_note", "what_i_did_not_trade_and_why", "what_i_still_do_not_know"],
    "additionalProperties": False,
}

DEEP_MANDATE = (
    "You are the head trader of a crypto perpetuals desk on Hyperliquid, with a budget of ${budget} of margin and leverage up to 4x "
    "(never above a coin's max_leverage). You have web access. Below: the desk manual (read it - it is what this desk has measured and "
    "how it works), the live packet (the whole board, ~30 coins in depth, market context, your own past runs with outcomes and lessons), "
    "and nothing else. Your job: find the best trades available right now, or none.\n\n"
    "Work the way the best discretionary desks work, and do not stop early:\n"
    "1. Read your own record first. What did you get wrong last time and why? Do not repeat it.\n"
    "2. Form a view of the tape: who is forced to trade today, where the crowd is crowded and unrewarded, what the session and calendar imply.\n"
    "3. Research as deep as you need - there is no limit on searches, pages or sources. For anything you might trade, go to primary "
    "sources (project blogs and GitHub, governance forums, exchange announcement pages on Binance/OKX/Coinbase/Upbit/Bithumb, block "
    "explorers and unlock trackers, regulator and central-bank sites, Farside for ETF flows, funding/OI dashboards), read the actual "
    "pages, cross-check every number with a second source, and date every fact. Look for what the crowd is missing: Korean and Asian "
    "flow, international regulation, whale and treasury moves, listings and delistings, unlock cliffs, protocol changes, macro prints "
    "in the next 72 hours. Keep asking the next question until you are certain or have proven there is nothing there.\n"
    "4. Write your theories explicitly: claim, mechanism (who must trade and why), evidence, what would kill it.\n"
    "5. Trade only what you would risk your own money on: 0 to 5 trades, confidence >= 0.55 each, margin per trade of your choosing "
    "within the budget. Every trade: side, kind (intraday 3-12h or swing 24-72h), leverage, margin, tp/sl as fractions of price with the "
    "stop inside the coin's band for its kind (intraday 0.5-1.0 own daily move; swing 1.5-3.0), tp >= 1.5 x sl, a falsifier (wrong-side "
    "price move by an hour that proves you wrong before the stop), a checkpoint, and the URLs you relied on.\n"
    "6. Book: not one bet in five coats - beta-weighted net exposure <= 60% of gross once you hold 4+, no two same-side trades from one "
    "cluster, name the worst-case loss at the stops.\n"
    "7. Say what you did not trade and why, and what you still do not know.\n"
    "Everything you assert must be traceable to the packet or to a URL you actually opened. Answer ONLY in the required JSON."
)


def deep_session(packet: dict, budget: float, with_manual: bool = True, effort: str = "xhigh") -> dict:
    manual = ""
    if with_manual:
        files = sorted((ROOT / "docs" / "manual").glob("ch*.md"))
        manual = "\n\n=== DESK MANUAL ===\n" + "\n\n".join(io.open(f, encoding="utf-8").read() for f in files)
    prompt = (DEEP_MANDATE.replace("${budget}", f"{budget:.0f}") + manual +
              "\n\n=== LIVE PACKET ===\n" + json.dumps(packet, default=str))
    r = chat(prompt, DEEP_SCHEMA, tag="deep", timeout_s=3600, web=True, effort=effort)
    if not r.get("ok") and "reasoning" in str(r.get("error", "")).lower():
        r = chat(prompt, DEEP_SCHEMA, tag="deep", timeout_s=3600, web=True, effort="high")
    return r


def searches_from_events(run_dir: str) -> list:
    """What the session actually searched (from the codex event stream) - the proof of depth."""
    out = []
    try:
        for line in io.open(Path(run_dir) / "events.jsonl", encoding="utf-8"):
            try:
                ev = json.loads(line)
            except Exception:
                continue
            it = ev.get("item") or {}
            if ev.get("type") == "item.completed" and it.get("type") == "web_search":
                q = it.get("query") or ", ".join((it.get("action") or {}).get("queries") or [])
                if q:
                    out.append(q)
    except Exception:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-research", action="store_true")
    ap.add_argument("--mode", choices=["structured", "deep"], default="deep")
    ap.add_argument("--budget", type=float, default=500.0, help="total margin in $ across the trades")
    ap.add_argument("--portfolio", type=str, default="P1")
    ap.add_argument("--no-manual", action="store_true")
    ap.add_argument("--settle", type=str, default=None)
    ap.add_argument("--review", type=str, default=None, help="run file: settle (if needed) then ask ChatGPT for the review")
    a = ap.parse_args()
    if a.review:
        run = json.loads(Path(a.review).read_text(encoding="utf-8"))
        if not run.get("settlements"):
            run["settlements"] = [settle(run)]
        rv = review(run)
        run.setdefault("reviews", []).append(rv)
        Path(a.review).write_text(json.dumps(run, indent=1, default=str), encoding="utf-8")
        res = rv["result"]
        print(f"review: ok={res.get('ok')} {res.get('seconds')}s usage={res.get('usage')} {res.get('error', '')}")
        if res.get("ok"):
            for r in res["data"]["reviews"]:
                print()
                print(f"{r['coin']}: {r['lesson_one_line']}")
                for k in ("why_entered", "what_happened", "what_was_right", "what_was_wrong", "how_it_went_the_other_way", "visible_and_unused", "next_time"):
                    print(f"  {k}: {r[k]}")
                print(f"  loss_class={r['loss_class']} exit={r['exit_quality']} hold_next={r['hold_next_time']} stop_next={r['stop_next_time']}")
            print()
            print("BOOK LESSON:", res["data"]["book_lesson"])
            for q in res["data"]["what_to_research_next_time"]:
                print("  research next time:", q)
        return
    if a.settle:
        run = json.loads(Path(a.settle).read_text(encoding="utf-8"))
        s = settle(run)
        run.setdefault("settlements", []).append(s)
        Path(a.settle).write_text(json.dumps(run, indent=1, default=str), encoding="utf-8")
        print(f"settled at {s['settled_at']}: total ${s['total_pnl_usd']:+.2f}")
        for x in s["trades"]:
            print("  ", x)
        return
    st = login_status()
    print("codex:", st.get("status") or st.get("error"))
    if not st.get("ok"):
        sys.exit(1)
    t0 = time.time()
    from desk_packet import build_packet as build_packet_v2
    packet = build_packet_v2()
    print(f"packet v2: {len(packet['board'])} on the board, {len(packet['candidates'])} candidates, {len(json.dumps(packet, default=str))} chars, {time.time() - t0:.0f}s", flush=True)
    report, asked = None, None
    if a.mode == "deep":
        c = deep_session(packet, a.budget, with_manual=not a.no_manual)
        print(f"deep session: ok={c.get('ok')} {c.get('seconds')}s usage={c.get('usage')} {c.get('error', '')}", flush=True)
        searched = searches_from_events(c.get("dir", "")) if c.get("dir") else []
        print(f"  web searches made: {len(searched)}")
        for q in searched[:60]:
            print("   -", q[:140])
        if c.get("ok"):
            c["data"]["trades_as_proposed"] = [dict(t) for t in c["data"]["trades"]]
            c["data"]["trades"] = enforce_desk_rules(c["data"]["trades"], packet)
            for t in c["data"]["trades"]:                       # margin: the model's choice, capped by the budget
                t["margin_usd"] = float(t.get("margin_usd") or 0)
            tot = sum(t["margin_usd"] for t in c["data"]["trades"])
            if tot > a.budget and tot > 0:
                for t in c["data"]["trades"]:
                    t["margin_usd"] = round(t["margin_usd"] * a.budget / tot, 2)
                    t.setdefault("desk_fixes", []).append(f"margin scaled to fit ${a.budget:.0f} budget")
            report = {"deep": True, "research_log": c["data"].get("research_log"), "theories": c["data"].get("theories"),
                      "searches": searched, "what_i_still_do_not_know": c["data"].get("what_i_still_do_not_know")}
        OUT.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run = {"stamp": stamp, "portfolio": a.portfolio, "budget": a.budget, "mode": "deep", "entry_ms": int(time.time() * 1000),
               "packet": packet, "asked": None, "research": report, "calls": c, "with_manual": not a.no_manual, "with_research": True}
        path = OUT / f"{stamp}.json"
        path.write_text(json.dumps(run, indent=1, default=str), encoding="utf-8")
        if c.get("ok"):
            d = c["data"]
            print("\nMARKET READ:", d["market_read"])
            for th in d.get("theories", []):
                print("  THEORY:", th["claim"], "| kills it:", th["what_would_kill_it"])
            for tr in d["trades"]:
                print(f"  {tr['coin']:6s} {tr['side']:5s} {tr.get('kind', '?'):8s} {tr['leverage']}x ${tr['margin_usd']:.0f} tp {tr['tp_pct']} sl {tr['sl_pct']} hold {tr['hold_hours']}h conf {tr['confidence']} | {tr['thesis']}")
                print("       why now:", tr.get("why_now"))
                print("       crowd misses:", tr.get("what_the_crowd_is_missing"))
                for fx in tr.get("desk_fixes", []):
                    print("       desk:", fx)
            print("BOOK:", d["book_note"])
            for w in d["what_i_did_not_trade_and_why"]:
                print("  rejected:", w)
            for w in d["what_i_still_do_not_know"]:
                print("  unknown:", w)
        print("saved", path)
        return
    if not a.no_research:
        asked = ask_questions(packet)
        print(f"ask: ok={asked.get('ok')} {asked.get('seconds')}s usage={asked.get('usage')} {asked.get('error', '')}", flush=True)
        if asked.get("ok") and asked["data"].get("questions"):
            qs = asked["data"]["questions"][:8]
            print("  shortlist:", asked["data"].get("shortlist"))
            for q in qs:
                print("  Q:", q[:150])
        else:
            qs = research_questions(packet)[-2:] + research_questions(packet)[:8]     # fallback: market + first 8 coins
        qs = [q.replace("At most 2 searches", "At most 4 searches") for q in qs]
        r = research(qs, {"market": packet.get("market", packet.get("regime")), "candidates": list(packet["candidates"])},
                     tag="desk_research", timeout_s=1500, effort="high",
                     depth_note=("DEEP MODE: this is a decision-time report. Go to primary sources (project GitHub/blog/governance forum, "
                                 "exchange announcement pages, block explorers, regulator and central-bank sites, Farside for ETF flows, "
                                 "token-unlock trackers) rather than news aggregators; cross-check any number with a second source when "
                                 "it matters; date every fact."))
        print(f"research: ok={r.get('ok')} {r.get('seconds')}s usage={r.get('usage')} dropped_no_url={r.get('facts_dropped_no_url')} {r.get('error', '')}", flush=True)
        report = r.get("data") if r.get("ok") else {"error": r.get("error")}
    c = make_calls(packet, report, with_manual=not a.no_manual)
    print(f"calls: ok={c.get('ok')} {c.get('seconds')}s usage={c.get('usage')} {c.get('error', '')}", flush=True)
    if c.get("ok"):
        c["data"]["trades_as_proposed"] = [dict(t) for t in c["data"]["trades"]]
        c["data"]["trades"] = enforce_desk_rules(c["data"]["trades"], packet)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run = {"stamp": stamp, "entry_ms": int(time.time() * 1000), "packet": packet, "asked": asked, "research": report, "calls": c,
           "with_manual": not a.no_manual, "with_research": not a.no_research}
    path = OUT / f"{stamp}.json"
    path.write_text(json.dumps(run, indent=1, default=str), encoding="utf-8")
    if c.get("ok"):
        d = c["data"]
        print("\nMARKET READ:", d["market_read"])
        for tr in d["trades"]:
            print(f"  {tr['coin']:6s} {tr['side']:5s} {tr.get('kind', '?'):8s} {tr['leverage']}x tp {tr['tp_pct']} sl {tr['sl_pct']} hold {tr['hold_hours']}h conf {tr['confidence']} | {tr['thesis']}")
            for fx in tr.get("desk_fixes", []):
                print("       desk:", fx)
            for u in tr["research_facts_used"]:
                print("       uses:", u)
        print("BOOK:", d["book_note"])
        for w in d["what_i_did_not_trade_and_why"]:
            print("  rejected:", w)
    print("saved", path)


if __name__ == "__main__":
    main()
