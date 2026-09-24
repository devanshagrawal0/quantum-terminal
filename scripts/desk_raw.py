"""RAW mode: give ChatGPT nothing but raw market data files + a working directory with Python, and one
order: compute every feature yourself (200+: returns, vol family, trend, oscillators, bands, CVD from the
trade tape, funding/OI regimes, betas, correlation matrix, residual vol, book imbalance...), research every
kind of news worldwide, and place EXACTLY 3 trades.

Why raw: Dev's instruction 2026-09-20 - no manual, no packet features from us; it can't reach Hyperliquid /
Lighter itself, so we hand it the raw rows and let it do the work the way it would in a chat.

Files written into the session dir (./data):
  hl_state.csv        every live Hyperliquid perp: mark, oracle, mid, funding_hourly, open_interest, day_volume, premium, prev_day_px, max_leverage
  hl_1h.csv           hourly OHLCV, last 96 bars, liquid coins (>= $2M/day) + majors
  hl_1d.csv           daily OHLCV, last 90 days, same coins
  hl_funding_7d.csv   hourly funding prints, last 7 days, same coins
  hl_trades.csv       the last ~500 trades per coin (side, price, size, time) - CVD is yours to compute
  hl_book.csv         top 20 levels each side, same coins
  lighter_funding.csv Lighter's funding table incl. the rates it shows for other exchanges (binance etc.)
  lighter_stats.csv   Lighter exchange stats per market (last price, daily volume, daily price change)
  okx_funding.csv     OKX funding for the same coins
  upbit_krw.csv       Upbit KRW tickers for coins it lists + USDKRW
  macro.json          CoinGecko global (dominance, mcap), Fear & Greed 7d
  calendar.csv        our scheduled-event table for the next 14 days (FOMC/CPI/NFP/opex/unlocks/listings)
  own_record.json     the desk's previous runs and outcomes
Usage: python scripts/desk_raw.py --budget 100 --portfolio P2
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import pandas as pd  # noqa: E402

import desk_packet as dp  # noqa: E402
import subprocess  # noqa: E402
from sim.codex_backend import login_status, chat, WORK  # noqa: E402
from desk_call import DEEP_SCHEMA, enforce_desk_rules, searches_from_events, OUT  # noqa: E402

LIGHTER = "https://mainnet.zklighter.elliot.ai/api/v1"


def csv_text(rows: list, cols: list) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def gather(liquid_floor: float = 2_000_000) -> tuple[dict, dict]:
    t0 = time.time()
    meta, ctx = dp.hl({"type": "metaAndAssetCtxs"})
    state = []
    for u, c in zip(meta["universe"], ctx):
        if u.get("isDelisted"):
            continue
        try:
            state.append({"coin": u["name"], "mark": float(c["markPx"]), "oracle": float(c["oraclePx"]), "mid": float(c["midPx"] or 0),
                          "funding_hourly": float(c["funding"]), "open_interest_coins": float(c["openInterest"]),
                          "open_interest_usd": round(float(c["openInterest"]) * float(c["markPx"])),
                          "day_volume_usd": round(float(c["dayNtlVlm"])), "premium": float(c["premium"] or 0),
                          "prev_day_px": float(c["prevDayPx"]), "max_leverage": u.get("maxLeverage")})
        except (TypeError, ValueError):
            continue
    st = pd.DataFrame(state).set_index("coin")
    coins = list(st[st["day_volume_usd"] >= liquid_floor].index)
    for m in dp.MAJORS:
        if m in st.index and m not in coins:
            coins.append(m)
    now = int(time.time() * 1000)
    h1, d1, fund, trades, book = [], [], [], [], []
    for c in coins:
        time.sleep(0.25)                                            # stay under the public rate limit
        df = dp.candles(c, "1h", 100 * 3_600_000)
        for _, r in df.tail(96).iterrows():
            h1.append({"coin": c, "ts_utc": datetime.fromtimestamp(r["t"] / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M"), "o": r["o"], "h": r["h"], "l": r["l"], "c": r["c"], "v": r["v"]})
        dd = dp.candles(c, "1d", 95 * 86_400_000)
        for _, r in dd.tail(90).iterrows():
            d1.append({"coin": c, "date": datetime.fromtimestamp(r["t"] / 1000, timezone.utc).strftime("%Y-%m-%d"), "o": r["o"], "h": r["h"], "l": r["l"], "c": r["c"], "v": r["v"]})
        try:
            for x in dp.hl({"type": "fundingHistory", "coin": c, "startTime": now - 7 * 86_400_000, "endTime": now}):
                fund.append({"coin": c, "ts_utc": datetime.fromtimestamp(int(x["time"]) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M"), "funding_rate": float(x["fundingRate"]), "premium": float(x.get("premium") or 0)})
        except Exception:  # noqa: BLE001
            pass
        try:
            for x in dp.hl({"type": "recentTrades", "coin": c}):
                trades.append({"coin": c, "ts_utc": datetime.fromtimestamp(int(x["time"]) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                               "side": "buy" if x["side"] == "B" else "sell", "px": float(x["px"]), "sz": float(x["sz"]), "usd": round(float(x["px"]) * float(x["sz"]), 2)})
        except Exception:  # noqa: BLE001
            pass
        try:
            b = dp.hl({"type": "l2Book", "coin": c})
            for side, lv in (("bid", b["levels"][0][:20]), ("ask", b["levels"][1][:20])):
                for i, x in enumerate(lv):
                    book.append({"coin": c, "side": side, "level": i, "px": float(x["px"]), "sz": float(x["sz"]), "n_orders": x.get("n")})
        except Exception:  # noqa: BLE001
            pass
    # Lighter (public)
    lf, ls = [], []
    try:
        for x in dp.get(f"{LIGHTER}/funding-rates")["funding_rates"]:
            lf.append({"symbol": x.get("symbol"), "exchange": x.get("exchange"), "rate": x.get("rate"), "market_id": x.get("market_id")})
    except Exception as e:  # noqa: BLE001
        lf.append({"symbol": "ERROR", "exchange": type(e).__name__})
    try:
        for x in dp.get(f"{LIGHTER}/exchangeStats")["order_book_stats"]:
            ls.append({"symbol": x.get("symbol"), "last_trade_price": x.get("last_trade_price"), "daily_trades_count": x.get("daily_trades_count"),
                       "daily_base_volume": x.get("daily_base_token_volume"), "daily_quote_volume_usd": x.get("daily_quote_token_volume"),
                       "daily_price_change_pct": x.get("daily_price_change")})
    except Exception as e:  # noqa: BLE001
        ls.append({"symbol": "ERROR", "last_trade_price": type(e).__name__})
    okx = []
    for c in coins:
        f = dp.okx_funding(c)
        if f:
            okx.append({"coin": c, **f})
    upbit = []
    try:
        krw = float(dp.get("https://open.er-api.com/v6/latest/USD")["rates"]["KRW"])
        listed = {m["market"] for m in dp.get("https://api.upbit.com/v1/market/all")}
        mk = [f"KRW-{c}" for c in coins if f"KRW-{c}" in listed]
        for i in range(0, len(mk), 50):
            for row in dp.get("https://api.upbit.com/v1/ticker?markets=" + ",".join(mk[i:i + 50])):
                upbit.append({"coin": row["market"].split("-")[1], "krw_price": row["trade_price"], "usd_equiv": round(float(row["trade_price"]) / krw, 6),
                              "change_24h_pct": round(float(row.get("signed_change_rate", 0)) * 100, 2), "acc_trade_price_24h_krw": row.get("acc_trade_price_24h")})
        upbit.append({"coin": "_USDKRW", "krw_price": krw})
    except Exception as e:  # noqa: BLE001
        upbit.append({"coin": "ERROR", "krw_price": type(e).__name__})
    macro = {"coingecko_global": dp.dominance(), "fear_greed_7d": dp.fear_greed(),
             "now_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "now_new_york": datetime.now(dp.NY).strftime("%Y-%m-%d %H:%M %Z %A")}
    cal = []
    try:
        from sim.events import Calendar
        ev = Calendar().upcoming(now, days=14)
        cal = ev.head(60).to_dict(orient="records") if hasattr(ev, "to_dict") else []
    except Exception:  # noqa: BLE001
        pass
    files = {
        "data/hl_state.csv": csv_text([{"coin": k, **v} for k, v in st.to_dict(orient="index").items()],
                                      ["coin", "mark", "oracle", "mid", "funding_hourly", "open_interest_coins", "open_interest_usd", "day_volume_usd", "premium", "prev_day_px", "max_leverage"]),
        "data/hl_1h.csv": csv_text(h1, ["coin", "ts_utc", "o", "h", "l", "c", "v"]),
        "data/hl_1d.csv": csv_text(d1, ["coin", "date", "o", "h", "l", "c", "v"]),
        "data/hl_funding_7d.csv": csv_text(fund, ["coin", "ts_utc", "funding_rate", "premium"]),
        "data/hl_trades.csv": csv_text(trades, ["coin", "ts_utc", "side", "px", "sz", "usd"]),
        "data/hl_book.csv": csv_text(book, ["coin", "side", "level", "px", "sz", "n_orders"]),
        "data/lighter_funding.csv": csv_text(lf, ["symbol", "exchange", "rate", "market_id"]),
        "data/lighter_stats.csv": csv_text(ls, ["symbol", "last_trade_price", "daily_trades_count", "daily_base_volume", "daily_quote_volume_usd", "daily_price_change_pct"]),
        "data/okx_funding.csv": csv_text(okx, ["coin", "okx_funding_pct_per_8h", "okx_funding_pct_per_day"]),
        "data/upbit_krw.csv": csv_text(upbit, ["coin", "krw_price", "usd_equiv", "change_24h_pct", "acc_trade_price_24h_krw"]),
        "data/macro.json": json.dumps(macro, indent=1, default=str),
        "data/calendar.csv": csv_text(cal, list(cal[0].keys()) if cal else ["none"]),
        "data/own_record.json": json.dumps(dp.own_record(), indent=1, default=str),
    }
    info = {"coins": coins, "n_state": len(state), "n_1h_rows": len(h1), "n_1d_rows": len(d1), "n_funding_rows": len(fund),
            "n_trades": len(trades), "n_book_rows": len(book), "n_lighter_funding": len(lf), "n_lighter_stats": len(ls),
            "n_okx": len(okx), "n_upbit": len(upbit), "n_calendar": len(cal), "bytes": sum(len(v) for v in files.values()),
            "gather_seconds": round(time.time() - t0, 1), "marks": {k: v["mark"] for k, v in st.to_dict(orient="index").items()},
            "max_leverage": {k: v["max_leverage"] for k, v in st.to_dict(orient="index").items()}}
    return files, info


# ---------------------------------------------------------------- compute rounds: ChatGPT writes the Python, we run it (sandboxed here)
CODE_SCHEMA = {
    "type": "object",
    "properties": {"script": {"type": "string"}, "done": {"type": "boolean"}, "notes": {"type": "string"},
                   "features_computed": {"type": "array", "items": {"type": "string"}}},
    "required": ["script", "done", "notes", "features_computed"], "additionalProperties": False}

CODE_RULES = (
    "You are the quant on a crypto perpetuals desk. The raw files listed below sit in ./data (schemas and first rows shown). "
    "You cannot run code yourself; write ONE self-contained Python 3 script (pandas, numpy available; no network; no imports beyond the "
    "standard library, pandas, numpy) and the desk runs it for you in this folder and returns its stdout and the head of any CSV you "
    "write. Your job across rounds: compute 200+ features per coin from the raw data and write them to ./features.csv (one row per "
    "coin, coin as the first column) plus ./corr_raw.csv and ./corr_resid.csv (correlation matrices) and ./summary.txt (the 30 most "
    "striking readings in words with numbers: crowded-and-unrewarded, OI jumps, funding divergences across venues, CVD vs price, "
    "book imbalance, coins trading on their own story, Korean premium). Feature list to cover: returns 1h/4h/12h/24h/3d/7d/30d and "
    "skip-1 momentum; realised vol close-to-close/Parkinson/Garman-Klass 24h/7d/30d annualised sqrt(365), vol-of-vol, vol percentile, "
    "ATR; SMA/EMA 20/50, ADX, Donchian, distance from 30d high/low; RSI 7/14, stochastic, MACD; Bollinger/Keltner width, squeeze; "
    "volume z, VWAP deviation, OBV; CVD and taker imbalance from hl_trades.csv; funding level, funding z vs 7d, cumulative 7d carry, "
    "funding vs OKX and vs the binance rates in lighter_funding.csv; OI $, OI/volume; spread bps, depth within 0.5%, imbalance; beta "
    "to BTC and ETH from hl_1d.csv, R2, residual daily move, crash-day beta; correlation matrices raw and residual, clusters; Korean "
    "premium. Print progress and any data problems. Guard every division. Set done=true only when features.csv has 200+ columns for "
    "all coins and summary.txt exists. Answer ONLY in the required JSON."
)


def _heads(files: dict, n: int = 4) -> str:
    out = []
    for k in sorted(files):
        lines = files[k].splitlines()
        out.append(f"--- {k} ({len(lines)} lines) ---" + chr(10) + chr(10).join(lines[:n]))
    return chr(10).join(out)


def run_script(session_dir: Path, script: str, timeout_s: int = 300) -> dict:
    """Run the model's script in the session folder with no network and a time cap; return what it printed."""
    sp = session_dir / "round.py"
    sp.write_text(script, encoding="utf-8")
    # no network for the model's script: sockets are disabled in-process before it runs (a guard against accidental
    # fetches, not a hostile sandbox), no PATH, isolated interpreter
    env = {"PATH": "", "SYSTEMROOT": "C:/Windows", "PYTHONIOENCODING": "utf-8"}
    wrapper = session_dir / "_run_wrapper.py"
    wrapper.write_text(
        "import socket, runpy, sys" + chr(10) +
        "class _NoNet:" + chr(10) +
        "    def __init__(self, *a, **k): raise OSError('network is disabled in the desk sandbox')" + chr(10) +
        "def _blocked(*a, **k): raise OSError('network is disabled in the desk sandbox')" + chr(10) +
        "socket.socket = _NoNet; socket.create_connection = _blocked; socket.getaddrinfo = _blocked" + chr(10) +
        "sys.argv = [sys.argv[1]]" + chr(10) +
        "runpy.run_path(sys.argv[0], run_name='__main__')" + chr(10), encoding="utf-8")
    try:
        r = subprocess.run([sys.executable, "-I", str(wrapper.resolve()), str(sp.resolve())], cwd=str(session_dir.resolve()), capture_output=True, text=True, timeout=timeout_s,
                           encoding="utf-8", errors="replace", env=env)
        out = (r.stdout or "")[-6000:] + (("\n[stderr]\n" + r.stderr[-3000:]) if r.stderr else "")
        rc = r.returncode
    except subprocess.TimeoutExpired:
        out, rc = f"[timed out after {timeout_s}s]", -1
    heads = {}
    for name in ("features.csv", "corr_raw.csv", "corr_resid.csv", "summary.txt"):
        f = session_dir / name
        if f.exists():
            txt = f.read_text(encoding="utf-8", errors="replace")
            if name.endswith(".csv"):
                lines = txt.splitlines()
                heads[name] = {"rows": max(0, len(lines) - 1), "cols": len(lines[0].split(",")) if lines else 0, "head": chr(10).join(lines[:3])[:1500]}
            else:
                heads[name] = {"text": txt[:4000]}
    return {"returncode": rc, "output": out, "artifacts": heads}


def compute_rounds(files: dict, session_dir: Path, max_rounds: int = 4) -> dict:
    session_dir.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        fp = session_dir / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
    history, result = [], None
    for rnd in range(1, max_rounds + 1):
        prompt = (CODE_RULES + f"\n\nROUND {rnd} of {max_rounds}.\n\n=== FILES (schemas + first rows) ===\n" + _heads(files) +
                  ("\n\n=== PREVIOUS ROUNDS ===\n" + json.dumps(history, default=str)[-14000:] if history else ""))
        r = chat(prompt, CODE_SCHEMA, tag=f"code{rnd}", timeout_s=900, web=False, effort="high")
        if not r.get("ok"):
            history.append({"round": rnd, "error": r.get("error")})
            print(f"  code round {rnd}: FAILED {r.get('error', '')[:160]}", flush=True)
            break
        d = r["data"]
        res = run_script(session_dir, d["script"])
        print(f"  code round {rnd}: {r.get('seconds')}s, script {len(d['script'])} chars, rc={res['returncode']}, "
              f"features.csv={res['artifacts'].get('features.csv', {}).get('cols', 0)} cols x {res['artifacts'].get('features.csv', {}).get('rows', 0)} rows, done={d['done']}", flush=True)
        history.append({"round": rnd, "notes": d["notes"], "features_computed": d["features_computed"][:60], "run": res})
        result = {"round": rnd, "run": res, "notes": d["notes"]}
        if d["done"] and res["artifacts"].get("features.csv", {}).get("cols", 0) >= 150:
            break
    return {"history": history, "final": result}


RAW_MANDATE = (
    "You are the head trader of a crypto perpetuals desk on Hyperliquid with ${budget} of margin, leverage up to 4x (never above a "
    "coin's max_leverage). Below: the FEATURES YOU COMPUTED YOURSELF in the previous step from the raw Hyperliquid/Lighter/OKX/Upbit "
    "data (features.csv: one row per coin; your summary.txt of the most striking readings; the correlation matrices), the raw "
    "state table, the calendar and your own record. You have web access, no limit on searches or sources. Do the rest to the "
    "standard of the best quantitative discretionary desk, and do not stop early:\n\n"
    "1. READ YOUR FEATURES - they cover: returns over 1h/4h/12h/24h/3d/7d/30d and momentum "
    "skipping the last bar; realised vol (close-to-close, Parkinson, Garman-Klass) over 24h/7d/30d, annualised with sqrt(365) and "
    "vol-of-vol, vol percentile; ATR; trend (SMA/EMA 20/50, ADX, Donchian, distance from 30d high/low); oscillators (RSI 7/14, "
    "stochastic, MACD); Bollinger/Keltner width and squeeze; volume z-score, VWAP deviation, OBV; CVD and taker imbalance from "
    "hl_trades.csv; funding level, funding z vs its 7-day history, cumulative 7-day carry, funding vs OKX and vs the rates in "
    "lighter_funding.csv (cross-venue crowding); open interest in $ and OI/volume; price-vs-OI regime; order-book spread, depth "
    "within 0.5%, imbalance; BETA to BTC and to ETH from hl_1d.csv, R2, residual (own) daily move, crash-day beta; the full "
    "CORRELATION MATRIX (raw and residual) and clusters; Korean premium from upbit_krw.csv; distance to liquidation clusters if "
    "you can infer them. Write what you computed to ./features.csv (one row per coin) so the desk can audit it.\n"
    "2. RESEARCH everything that could move these coins in the next 72 hours - there is no limit on searches or sources: US, EU, "
    "UK, Korea, Japan, China, Hong Kong, Singapore, UAE, India regulation and enforcement; Fed/ECB/BoJ/PBoC meetings, speeches, "
    "rate expectations, macro prints and their times (UTC); exchange listings/delistings/suspensions on Binance, OKX, Coinbase, "
    "Upbit, Bithumb, Bybit, Kraken, Gate; token unlocks and vesting cliffs; protocol upgrades, governance votes, fee switches, "
    "buybacks; hacks, exploits, depegs, outages; ETF flows (Farside) and new ETF filings; treasury companies and whale wallets; "
    "stablecoin issuance; geopolitics and government news that moves risk; local-language sources where they matter (Korean, "
    "Japanese, Chinese). Primary sources first, cross-check numbers, date every fact.\n"
    "3. THINK: who is forced to trade, where is the crowd crowded and unrewarded, what does the session/weekday/calendar imply, "
    "which of your features disagree with the price.\n"
    "4. TRADE: EXACTLY 3 trades - the three best asymmetric setups you can defend with your own numbers and your research. For "
    "each: side, kind (intraday 3-12h or swing 24-72h), leverage, margin (your split of the budget), tp/sl as fractions of price "
    "(stop sized from YOUR residual vol: intraday 0.5-1.0 own daily move, swing 1.5-3.0; tp >= 1.5 x sl), a falsifier (wrong-side "
    "move by an hour that proves you wrong before the stop), a checkpoint, thesis (who must trade and why), why now, what the "
    "crowd is missing, the URLs you relied on, confidence. Not three coats of one bet: state the book's net beta and the loss at "
    "all three stops.\n"
    "5. Say what you rejected and why, and what you still do not know. Answer ONLY in the required JSON."
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=100.0)
    ap.add_argument("--portfolio", type=str, default="P2")
    ap.add_argument("--effort", type=str, default="xhigh")
    ap.add_argument("--rounds", type=int, default=4)
    a = ap.parse_args()
    st = login_status()
    print("codex:", st.get("status") or st.get("error"))
    if not st.get("ok"):
        sys.exit(1)
    files, info = gather()
    print(f"raw data: {len(info['coins'])} coins, {info['n_1h_rows']} hourly rows, {info['n_1d_rows']} daily rows, {info['n_funding_rows']} funding prints, "
          f"{info['n_trades']} trades, {info['n_book_rows']} book rows, lighter {info['n_lighter_funding']}/{info['n_lighter_stats']}, okx {info['n_okx']}, "
          f"upbit {info['n_upbit']}, calendar {info['n_calendar']}, {info['bytes'] / 1e6:.1f} MB, {info['gather_seconds']}s", flush=True)
    session_dir = WORK / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_rawcompute"
    print("compute rounds (ChatGPT writes the Python, the desk runs it here, no network) ...", flush=True)
    comp = compute_rounds(files, session_dir, max_rounds=a.rounds)
    fin = (comp.get("final") or {}).get("run", {})
    arts = fin.get("artifacts", {})
    feats_txt = (session_dir / "features.csv").read_text(encoding="utf-8", errors="replace") if (session_dir / "features.csv").exists() else ""
    summary_txt = arts.get("summary.txt", {}).get("text", "")
    corr_txt = (session_dir / "corr_resid.csv").read_text(encoding="utf-8", errors="replace")[:20000] if (session_dir / "corr_resid.csv").exists() else ""
    prompt = RAW_MANDATE.replace("${budget}", f"{a.budget:.0f}").replace("{file_list}", ", ".join(sorted(k.split("/")[-1] for k in files)))
    prompt += ("\n\nNOW (UTC): " + info_now() +
               "\n\n=== YOUR summary.txt ===\n" + summary_txt +
               "\n\n=== YOUR features.csv ===\n" + feats_txt[:120000] +
               "\n\n=== YOUR corr_resid.csv (residual correlations) ===\n" + corr_txt +
               "\n\n=== RAW hl_state.csv ===\n" + files["data/hl_state.csv"] +
               "\n\n=== calendar.csv ===\n" + files["data/calendar.csv"] +
               "\n\n=== macro.json ===\n" + files["data/macro.json"] +
               "\n\n=== own_record.json ===\n" + files["data/own_record.json"][:8000])
    r = chat(prompt, DEEP_SCHEMA, tag="raw", timeout_s=5400, web=True, effort=a.effort)
    r["compute"] = {"session_dir": str(session_dir), "rounds": len(comp.get("history", [])),
                    "features_cols": arts.get("features.csv", {}).get("cols"), "features_rows": arts.get("features.csv", {}).get("rows"),
                    "history_notes": [h.get("notes") for h in comp.get("history", [])]}
    print(f"raw session: ok={r.get('ok')} {r.get('seconds')}s usage={r.get('usage')} {r.get('error', '')}", flush=True)
    searched = searches_from_events(r.get("dir", "")) if r.get("dir") else []
    print(f"  web searches made: {len(searched)}")
    for q in searched[:80]:
        print("   -", q[:140])
    feats = Path(r["compute"]["session_dir"]) / "features.csv"
    if feats and feats.exists():
        try:
            fdf = pd.read_csv(feats)
            print(f"  features.csv written by the model: {fdf.shape[0]} coins x {fdf.shape[1]} columns")
        except Exception as e:  # noqa: BLE001
            print("  features.csv unreadable:", type(e).__name__)
    else:
        print("  features.csv: NOT written")
    # a minimal packet so settlement / the dashboard can price the trades
    packet = {"now_utc": info_now(), "raw_mode": True, "candidates": {c: {"mark": m, "liquidity": {"max_leverage": info["max_leverage"].get(c)}} for c, m in info["marks"].items()},
              "board": {c: {"mark": m} for c, m in info["marks"].items()}, "data_files": {k: len(v) for k, v in files.items()}}
    if r.get("ok"):
        d = r["data"]
        d["trades_as_proposed"] = [dict(t) for t in d["trades"]]
        d["trades"] = enforce_desk_rules(d["trades"], packet)          # leverage by conviction + budget; stop bands cannot be checked (no own-move from us) - its own numbers stand
        tot = sum(float(t.get("margin_usd") or 0) for t in d["trades"])
        if tot > a.budget > 0:
            for t in d["trades"]:
                t["margin_usd"] = round(float(t["margin_usd"]) * a.budget / tot, 2)
                t.setdefault("desk_fixes", []).append(f"margin scaled to fit ${a.budget:.0f}")
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run = {"stamp": stamp, "portfolio": a.portfolio, "budget": a.budget, "mode": "raw", "entry_ms": int(time.time() * 1000), "packet": packet,
           "asked": None, "research": ({"deep": True, "raw": True, "research_log": r["data"].get("research_log"), "theories": r["data"].get("theories"),
                                        "searches": searched, "what_i_still_do_not_know": r["data"].get("what_i_still_do_not_know"),
                                        "features_csv": str(feats) if feats and feats.exists() else None} if r.get("ok") else {"error": r.get("error")}),
           "calls": r, "with_manual": False, "with_research": True, "raw_info": {k: v for k, v in info.items() if k not in ("marks", "max_leverage")}}
    path = OUT / f"{stamp}.json"
    path.write_text(json.dumps(run, indent=1, default=str), encoding="utf-8")
    if r.get("ok"):
        d = r["data"]
        print("\nMARKET READ:", d["market_read"])
        for th in d.get("theories", []):
            print("  THEORY:", th["claim"], "| kills it:", th["what_would_kill_it"])
        for tr in d["trades"]:
            print(f"  {tr['coin']:6s} {tr['side']:5s} {tr.get('kind', '?'):8s} {tr['leverage']}x ${float(tr['margin_usd']):.0f} tp {tr['tp_pct']} sl {tr['sl_pct']} hold {tr['hold_hours']}h conf {tr['confidence']} | {tr['thesis']}")
            print("       why now:", tr.get("why_now"))
            print("       crowd misses:", tr.get("what_the_crowd_is_missing"))
            for u in tr.get("research_facts_used", [])[:6]:
                print("       uses:", u)
            for fx in tr.get("desk_fixes", []):
                print("       desk:", fx)
        print("BOOK:", d["book_note"])
        for w in d["what_i_did_not_trade_and_why"][:12]:
            print("  rejected:", w)
        for w in d["what_i_still_do_not_know"][:8]:
            print("  unknown:", w)
    print("saved", path)


def info_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


if __name__ == "__main__":
    main()
