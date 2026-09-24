"""Desk packet v2 - everything the desk can know at this minute, from free public endpoints.

Board        all live Hyperliquid perps: mark, 1d return, funding %/day + crowd label, OI $,
             OI change since our last snapshot (we snapshot every build), volume, premium.
Candidates   ~30 coins in full: 1h/4h/24h/7d/30d returns, 7d/30d realised vol, own daily move
             and the stop band, beta / R2 / crash beta / cluster (our store, vintage stated),
             order book (spread bps, depth within 0.5% each side, in $), OKX funding for the
             same coin (cross-venue), Korean premium where Upbit lists it.
Market       BTC 1h/4h/24h/7d/30d, breadth, BTC dominance (CoinGecko), Fear & Greed (7 days),
             session + hours to next funding print + NY time + weekday, the calendar 7 days out,
             the measured calendar tilts for today, our measured links, cross-venue funding on
             the majors (OKX), Korean premium on the majors.
Own record   the last desk runs: calls, outcomes, lessons (so it reads its own history first).
Unavailable  is stated in the packet, never silently missing: Binance/Bybit (US geo-block),
             liquidations (no free feed), whale positions (no free feed).
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402

INFO = "https://api.hyperliquid.xyz/info"
SNAP = ROOT / "data" / "desk_calls" / "oi_snapshots.jsonl"
RUNS = ROOT / "data" / "desk_calls"
NY = ZoneInfo("America/New_York")
MAJORS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "AVAX", "LINK", "HYPE"]


def hl(body: dict, timeout: int = 30, tries: int = 5):
    """Hyperliquid info call with backoff on 429 (the raw gather makes ~300 calls in a row)."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(INFO, json.dumps(body).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 429:
                raise
            time.sleep(1.5 * (i + 1))
    raise last


def get(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (desk)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def candles(coin: str, interval: str, span_ms: int) -> pd.DataFrame:
    now = int(time.time() * 1000)
    c = hl({"type": "candleSnapshot", "req": {"coin": coin, "interval": interval, "startTime": now - span_ms, "endTime": now}})
    if not c:
        return pd.DataFrame()
    df = pd.DataFrame([{"t": int(x["t"]), "o": float(x["o"]), "h": float(x["h"]), "l": float(x["l"]), "c": float(x["c"]), "v": float(x["v"])} for x in c])
    return df.sort_values("t").reset_index(drop=True)


def ret(df: pd.DataFrame, bars: int):
    if df.empty or len(df) <= bars:
        return None
    return round(float(df["c"].iloc[-1] / df["c"].iloc[-1 - bars] - 1), 4)


def book(coin: str) -> dict:
    try:
        b = hl({"type": "l2Book", "coin": coin})
        bids, asks = b["levels"][0], b["levels"][1]
        bb, ba = float(bids[0]["px"]), float(asks[0]["px"])
        mid = (bb + ba) / 2
        spread_bps = (ba - bb) / mid * 1e4
        d_bid = sum(float(x["px"]) * float(x["sz"]) for x in bids if float(x["px"]) >= mid * 0.995)
        d_ask = sum(float(x["px"]) * float(x["sz"]) for x in asks if float(x["px"]) <= mid * 1.005)
        return {"spread_bps": round(spread_bps, 1), "depth_bid_0p5pct_usd": round(d_bid), "depth_ask_0p5pct_usd": round(d_ask),
                "imbalance": round((d_bid - d_ask) / (d_bid + d_ask), 2) if (d_bid + d_ask) else None}
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__}


def okx_funding(coin: str):
    try:
        d = get(f"https://www.okx.com/api/v5/public/funding-rate?instId={coin}-USDT-SWAP")["data"]
        if not d:
            return None
        r = float(d[0]["fundingRate"])
        return {"okx_funding_pct_per_8h": round(r * 100, 4), "okx_funding_pct_per_day": round(r * 3 * 100, 4)}
    except Exception:  # noqa: BLE001
        return None


def korean_premium(coins: list[str], usd_prices: dict) -> dict:
    out = {}
    try:
        krw = float(get("https://open.er-api.com/v6/latest/USD")["rates"]["KRW"])
        listed = {m["market"] for m in get("https://api.upbit.com/v1/market/all")}      # a market Upbit does not list 404s the whole call
        markets = ",".join(f"KRW-{c}" for c in coins if f"KRW-{c}" in listed)
        for row in get(f"https://api.upbit.com/v1/ticker?markets={markets}"):
            c = row["market"].split("-")[1]
            usd = usd_prices.get(c)
            if usd:
                out[c] = round((float(row["trade_price"]) / krw / usd - 1) * 100, 2)
        out["_usdkrw"] = round(krw, 1)
    except Exception as e:  # noqa: BLE001
        out["_error"] = type(e).__name__
    return out


def dominance():
    try:
        d = get("https://api.coingecko.com/api/v3/global")["data"]
        return {"btc_dominance_pct": round(d["market_cap_percentage"]["btc"], 2), "eth_dominance_pct": round(d["market_cap_percentage"]["eth"], 2),
                "total_mcap_usd": round(d["total_market_cap"]["usd"]), "mcap_change_24h_pct": round(d["market_cap_change_percentage_24h_usd"], 2)}
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__}


def fear_greed():
    try:
        f = get("https://api.alternative.me/fng/?limit=7")["data"]
        return {"now": int(f[0]["value"]), "label": f[0]["value_classification"], "last_7": [int(x["value"]) for x in f]}
    except Exception:  # noqa: BLE001
        return None


def oi_change(tab: pd.DataFrame) -> dict:
    """Snapshot OI now; return change vs the last snapshot and vs the last one >= 24h old."""
    now = int(time.time() * 1000)
    prev, prev24 = None, None
    if SNAP.exists():
        rows = [json.loads(l) for l in SNAP.read_text(encoding="utf-8").splitlines() if l.strip()]
        if rows:
            prev = rows[-1]
            old = [r for r in rows if now - r["t"] >= 24 * 3_600_000]
            prev24 = old[-1] if old else None
    snap = {"t": now, "oi": {c: float(v) for c, v in tab["oi_usd"].items()}}
    SNAP.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAP, "a", encoding="utf-8") as f:
        f.write(json.dumps(snap) + "\n")
    out = {}
    for c, v in snap["oi"].items():
        e = {}
        if prev and c in prev["oi"] and prev["oi"][c]:
            e["oi_chg_since_last_pct"] = round((v / prev["oi"][c] - 1) * 100, 1)
            e["hours_since_last"] = round((now - prev["t"]) / 3_600_000, 1)
        if prev24 and c in prev24["oi"] and prev24["oi"][c]:
            e["oi_chg_24h_pct"] = round((v / prev24["oi"][c] - 1) * 100, 1)
        out[c] = e
    return out


def live_xsec(coins: list, days: int = 90) -> dict:
    """Beta / R2 / own daily move / crash-day beta computed NOW from Hyperliquid daily candles, so the
    numbers are as of today, not the store's last vintage. Returns {coin: {...}} plus '_meta'."""
    closes = {}
    for c in ["BTC"] + [c for c in coins if c != "BTC"]:
        d = candles(c, "1d", (days + 5) * 86_400_000)
        if not d.empty and len(d) >= 30:
            closes[c] = d.set_index("t")["c"]
    if "BTC" not in closes:
        return {"_meta": {"error": "no BTC candles"}}
    px = pd.DataFrame(closes).sort_index()
    rets = px.pct_change().dropna(how="all")
    b = rets["BTC"].dropna()
    sig = float(b.std())
    crash_days = b.index[b.abs() > 2.5 * sig]
    out = {"_meta": {"as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "window_days": int(len(b)),
                     "btc_daily_sigma_pct": round(sig * 100, 2), "n_crash_days": int(len(crash_days))}}
    for c in rets.columns:
        r = rets[c].dropna()
        j = r.index.intersection(b.index)
        if len(j) < 25:
            continue
        x, y = b.loc[j].values, r.loc[j].values
        vx = float(((x - x.mean()) ** 2).mean())
        beta = float(((x - x.mean()) * (y - y.mean())).mean() / vx) if vx > 0 else 1.0
        beta_s = 0.8 * beta + 0.2 * 1.0                                   # light shrink toward 1 (Vasicek-style)
        resid = y - beta_s * x
        vy = float(y.var()) or 1e-12
        r2 = max(0.0, 1.0 - float(resid.var()) / vy)
        cj = [t for t in crash_days if t in j]
        if len(cj) >= 3:
            xc, yc = b.loc[cj].values, r.loc[cj].values
            vxc = float(((xc - xc.mean()) ** 2).mean())
            beta_c = float(((xc - xc.mean()) * (yc - yc.mean())).mean() / vxc) if vxc > 0 else None
        else:
            beta_c = None
        out[c] = {"beta": round(beta_s, 3), "r2": round(r2, 3), "own_daily_move_pct": round(float(resid.std()) * 100, 2),
                  "total_daily_move_pct": round(float(y.std()) * 100, 2),
                  "beta_crash_days": (round(beta_c, 3) if beta_c is not None else None), "n_days": int(len(j))}
    return out


def calendar_tilts(now_ny: datetime) -> dict:
    """Today's measured calendar tilts (docs/CALENDAR_SEASONALITY.md, BTC/ETH 2017-2026)."""
    wd = now_ny.strftime("%A")
    tilt = {"Thursday": "weak day for both majors (BTC -0.34%/d, ETH -0.54%/d vs base; t -2.1/-2.4): do not open fresh risk, trim day",
            "Wednesday": "BTC mid-week bid (+0.35%/d, t 2.1)", "Saturday": "ETH weekend retail bid (+0.30%/d, t 2.0)"}.get(wd)
    month = {10: "October: BTC's strongest month (+0.50%/d, t 3.1) - skew long", 6: "June: soft month, ETH -0.47%/d (t -2.1) - size down"}.get(now_ny.month)
    dom = now_ny.day
    tom = "turn of month: mild long tilt (ETH +0.36%/d t 2.3; BTC +0.23%)" if (dom <= 3 or dom >= 28) else None
    return {"weekday": wd, "weekday_tilt": tilt, "month_tilt": month, "turn_of_month": tom,
            "rule": "tilts of 0.3-0.5%/day on size and timing; never a trade on their own"}


def measured_links() -> list:
    try:
        from sim.links import links_as_of
        rows = links_as_of(int(time.time() * 1000))
        return [{k: r.get(k) for k in ("shock", "horizon", "beta_bps_per_sd", "t", "n", "status")} for r in rows][:12]
    except Exception as e:  # noqa: BLE001
        return [{"error": type(e).__name__}]


def own_record(max_runs: int = 6) -> list:
    out = []
    for f in sorted(RUNS.glob("*.json"), reverse=True)[:max_runs]:
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        calls = ((r.get("calls") or {}).get("data") or {}).get("trades") or []
        last = (r.get("settlements") or [None])[-1]
        rv = (r.get("reviews") or [None])[-1]
        item = {"when_utc": (r.get("packet") or {}).get("now_utc"), "market_read": ((r.get("calls") or {}).get("data") or {}).get("market_read"),
                "trades": []}
        for c in calls:
            s = next((t for t in (last or {}).get("trades", []) if t.get("coin") == c["coin"]), {})
            item["trades"].append({"coin": c["coin"], "side": c["side"], "lev": c["leverage"], "thesis": c["thesis"],
                                   "status": s.get("reason"), "price_move_pct": s.get("price_move_pct"), "pnl_usd": s.get("pnl_usd_on_100_margin")})
        if last:
            item["book_pnl_usd"] = last.get("total_pnl_usd")
        if rv and (rv.get("result") or {}).get("ok"):
            d = rv["result"]["data"]
            item["lessons"] = [x.get("lesson_one_line") for x in d.get("reviews", [])]
            item["book_lesson"] = d.get("book_lesson")
        out.append(item)
    return out


def build_packet(n_candidates: int = 30, liquid_floor: float = 2_000_000) -> dict:
    t0 = time.time()
    now = datetime.now(timezone.utc)
    now_ny = now.astimezone(NY)
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
        fh = float(c["funding"])
        rows.append({"coin": u["name"], "max_leverage": u.get("maxLeverage"), "mark": mark, "r_1d": round(mark / prev - 1, 4),
                     "funding_hourly": fh, "funding_pct_per_day": round(fh * 24 * 100, 4),
                     "crowd": ("crowded LONG (longs pay; squeeze DOWN)" if fh > 0.0000125 * 2 else
                               "crowded SHORT (shorts pay; squeeze UP)" if fh < 0 else "baseline"),
                     "oi_usd": round(float(c["openInterest"]) * mark), "day_volume_usd": round(float(c["dayNtlVlm"])),
                     "premium_vs_oracle_bps": round(float(c["premium"] or 0.0) * 1e4, 1)})
    tab = pd.DataFrame(rows).set_index("coin")
    oi = oi_change(tab)
    liquid = tab[tab["day_volume_usd"] >= liquid_floor]
    # candidates: funding extremes, 1-day movers both ways, OI jumpers, biggest volume, always the majors that are liquid
    cands = []
    oi_jump = sorted([(oi[c].get("oi_chg_since_last_pct") or 0, c) for c in liquid.index], reverse=True)
    for s in (liquid["funding_pct_per_day"].nlargest(6).index, liquid["funding_pct_per_day"].nsmallest(6).index,
              liquid["r_1d"].nlargest(6).index, liquid["r_1d"].nsmallest(6).index,
              [c for _, c in oi_jump[:5]], liquid["day_volume_usd"].nlargest(8).index):
        for coin in s:
            if coin not in cands:
                cands.append(coin)
    for m in MAJORS:
        if m in liquid.index and m not in cands:
            cands.append(m)
    cands = cands[:n_candidates]
    try:
        from sim.xsec import xsec
        x = xsec()

        def xs(key, coin):
            f = x["frames"].get(key)
            if f is None or coin not in f.columns:
                return None
            s = f[coin].dropna()
            return None if s.empty else round(float(s.iloc[-1]), 3)
        vintage = str(pd.to_datetime(x["frames"]["beta_btc"].index[-1], unit="ms").date())
    except Exception:  # noqa: BLE001
        xs, vintage = (lambda k, c: None), "unavailable"
    lx = live_xsec(cands)                                   # today's betas, not the store's vintage
    cand = {}
    for coin in cands:
        d1 = candles(coin, "1d", 35 * 86_400_000)
        h1 = candles(coin, "1h", 30 * 3_600_000)
        if d1.empty or len(d1) < 8:
            continue
        r = d1["c"].pct_change().dropna()
        rv7 = float(r.tail(7).std() * math.sqrt(365)) if len(r) >= 7 else None
        rv30 = float(r.tail(30).std() * math.sqrt(365)) if len(r) >= 20 else None
        L = lx.get(coin) or {}
        if coin == "BTC":
            dm = rv7 / math.sqrt(365) * 100 if rv7 else None       # BTC's own move = its total move
        else:
            dm = L.get("own_daily_move_pct") or xs("idio_daily_move_pct", coin)
            if not dm or dm < 0.3:
                dm = rv7 / math.sqrt(365) * 100 if rv7 else None
        hi30, lo30 = float(d1["h"].max()), float(d1["l"].min())
        cand[coin] = {
            "mark": tab.at[coin, "mark"],
            "returns": {"1h": ret(h1, 1), "4h": ret(h1, 4), "24h": tab.at[coin, "r_1d"], "7d": ret(d1, 7), "30d": ret(d1, 30)},
            "range_30d": {"pct_from_high": round((tab.at[coin, "mark"] / hi30 - 1) * 100, 1), "pct_from_low": round((tab.at[coin, "mark"] / lo30 - 1) * 100, 1)},
            "vol": {"rv_7d_ann": round(rv7, 3) if rv7 else None, "rv_30d_ann": round(rv30, 3) if rv30 else None,
                    "own_daily_move_pct": round(dm, 2) if dm else None,
                    "stop_band_1p5_to_3_own_moves": (f"{1.5 * dm / 100:.4f}-{3 * dm / 100:.4f}" if dm else None)},
            "btc_link": {"beta": L.get("beta", xs("beta_btc", coin)), "r2": L.get("r2", xs("r2_btc", coin)),
                         "beta_crash_days": L.get("beta_crash_days", xs("beta_stress", coin)), "cluster": xs("cluster_id", coin),
                         "as_of": lx.get("_meta", {}).get("as_of") if L else vintage, "n_days": L.get("n_days")},
            "crowd": {"funding_pct_per_day": tab.at[coin, "funding_pct_per_day"], "label": tab.at[coin, "crowd"],
                      "oi_usd": tab.at[coin, "oi_usd"], **oi.get(coin, {}),
                      "premium_vs_oracle_bps": tab.at[coin, "premium_vs_oracle_bps"], "okx": okx_funding(coin)},
            "liquidity": {"day_volume_usd": tab.at[coin, "day_volume_usd"], **book(coin), "max_leverage": int(tab.at[coin, "max_leverage"] or 0)},
        }
    btc_h = candles("BTC", "1h", 30 * 3_600_000); btc_d = candles("BTC", "1d", 40 * 86_400_000)
    usd = {c: tab.at[c, "mark"] for c in MAJORS if c in tab.index}
    kp = korean_premium([c for c in MAJORS if c in tab.index], usd)
    for c, v in kp.items():
        if c in cand:
            cand[c]["crowd"]["korean_premium_pct"] = v
    board = tab.sort_values("day_volume_usd", ascending=False)[["mark", "r_1d", "funding_pct_per_day", "oi_usd", "day_volume_usd", "premium_vs_oracle_bps"]].round(4)
    board["oi_chg_pct"] = [oi.get(c, {}).get("oi_chg_since_last_pct") for c in board.index]
    next_funding_min = 60 - now.minute
    session = "asia" if now.hour < 8 else "europe" if now.hour < 13 else "us" if now.hour < 21 else "late"
    try:
        from sim.events import Calendar
        ev = Calendar().upcoming(int(time.time() * 1000), days=7)
        events = ev.head(20).to_dict(orient="records") if hasattr(ev, "to_dict") else ev
    except Exception as e:  # noqa: BLE001
        events = f"calendar unavailable: {type(e).__name__}"
    packet = {
        "now_utc": now.strftime("%Y-%m-%d %H:%M"), "now_new_york": now_ny.strftime("%Y-%m-%d %H:%M %Z"),
        "time": {"session": session, "minutes_to_next_hourly_funding": next_funding_min, "weekday": now_ny.strftime("%A"),
                 "us_equity_cash_open": 9 <= now_ny.hour < 16 and now_ny.weekday() < 5},
        "market": {"btc": {"mark": tab.at["BTC", "mark"], "1h": ret(btc_h, 1), "4h": ret(btc_h, 4), "24h": tab.at["BTC", "r_1d"],
                           "7d": ret(btc_d, 7), "30d": ret(btc_d, 30)},
                   "breadth_1d_pct_green": round(float((tab["r_1d"] > 0).mean() * 100), 1),
                   "breadth_liquid_pct_green": round(float((liquid["r_1d"] > 0).mean() * 100), 1),
                   "n_perps": int(len(tab)), "n_liquid": int(len(liquid)), "dominance": dominance(), "fear_greed": fear_greed(),
                   "korean_premium_pct": kp, "cross_venue_funding_majors": {c: okx_funding(c) for c in ("BTC", "ETH", "SOL")},
                   "funding_extremes_pct_per_day": {"most_positive": liquid["funding_pct_per_day"].nlargest(8).round(4).to_dict(),
                                                    "most_negative": liquid["funding_pct_per_day"].nsmallest(8).round(4).to_dict()},
                   "movers_1d": {"up": liquid["r_1d"].nlargest(8).to_dict(), "down": liquid["r_1d"].nsmallest(8).to_dict()},
                   "oi_jumpers_since_last_snapshot": [{"coin": c, "oi_chg_pct": v} for v, c in oi_jump[:8] if v]},
        "calendar_next_7d": events, "calendar_tilts_today": calendar_tilts(now_ny), "measured_links": measured_links(),
        "own_record_last_runs": own_record(),
        "data_notes": {"beta_r2_own_move": f"live, {lx.get('_meta', {}).get('window_days')} daily Hyperliquid candles to {lx.get('_meta', {}).get('as_of')}; "
                                          f"BTC daily sigma {lx.get('_meta', {}).get('btc_daily_sigma_pct')}%, {lx.get('_meta', {}).get('n_crash_days')} crash days in window",
                       "clusters_vintage": vintage, "prices_funding_oi_volume_book": "live Hyperliquid", "okx_funding": "live",
                       "korean_premium": "live Upbit vs USD/KRW", "unavailable": ["Binance/Bybit (geo-blocked from this PC)",
                                                                                 "liquidation feed", "whale/large-holder positions",
                                                                                 "long/short account ratios (collector not running)"]},
        "board": board.to_dict(orient="index"),
        "candidates": cand,
        "build_seconds": round(time.time() - t0, 1),
    }
    return packet


if __name__ == "__main__":
    p = build_packet()
    print(f"built in {p['build_seconds']}s: {len(p['board'])} on the board, {len(p['candidates'])} candidates, {len(json.dumps(p, default=str))} chars")
    print(json.dumps({k: p[k] for k in ("now_utc", "time", "calendar_tilts_today", "data_notes")}, indent=1, default=str))
    print(json.dumps(p["market"], indent=1, default=str)[:2500])
    c = next(iter(p["candidates"]))
    print(c, json.dumps(p["candidates"][c], indent=1, default=str))
