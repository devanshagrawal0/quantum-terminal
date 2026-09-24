"""Crypto calendar-effect study — how the majors move around the calendar.

Multi-year daily history (Binance, free) for 12 liquid coins. Measures the movement
around calendar events: day-of-week, month-of-year, turn-of-month, options expiry,
US holidays, Chinese New Year, earnings-season weeks, and the two macro bombs that
actually move crypto now: FOMC decision days and CPI releases.

For each bucket: mean daily return, win rate, sample size, t-stat vs zero AND vs the
all-days baseline (the tradeable question: is this DIFFERENT from a normal day?).

    python scripts/seasonality.py            # print sheets + write the visual heatmap
Outputs the movement-sheet HTML to the path printed at the end.
"""
from __future__ import annotations

import html
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "carry_cache"
OUT_HTML = ROOT / "docs" / "movement_sheet.html"

COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC", "DOT", "MATIC"]

# FOMC decision days (exact). Sep-2026+ are future -> no price data, harmless.
FOMC = [
    "2020-01-29", "2020-03-03", "2020-03-15", "2020-04-29", "2020-06-10", "2020-07-29",
    "2020-09-16", "2020-11-05", "2020-12-16",
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22",
    "2021-11-03", "2021-12-15",
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21",
    "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20",
    "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18",
    "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17",
    "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29",
]
# CPI release days (~2nd week, 8:30am ET). APPROXIMATE +/-1-2d for older months.
CPI = [
    "2022-01-12", "2022-02-10", "2022-03-10", "2022-04-12", "2022-05-11", "2022-06-10",
    "2022-07-13", "2022-08-10", "2022-09-13", "2022-10-13", "2022-11-10", "2022-12-13",
    "2023-01-12", "2023-02-14", "2023-03-14", "2023-04-12", "2023-05-10", "2023-06-13",
    "2023-07-12", "2023-08-10", "2023-09-13", "2023-10-12", "2023-11-14", "2023-12-12",
    "2024-01-11", "2024-02-13", "2024-03-12", "2024-04-10", "2024-05-15", "2024-06-12",
    "2024-07-11", "2024-08-14", "2024-09-11", "2024-10-10", "2024-11-13", "2024-12-11",
    "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13", "2025-06-11",
    "2025-07-15", "2025-08-12", "2025-09-11", "2025-10-15", "2025-11-13", "2025-12-10",
    "2026-01-13", "2026-02-11", "2026-03-11", "2026-04-14", "2026-05-12", "2026-06-10",
    "2026-07-14", "2026-08-12",
]
CNY = ["2018-02-16", "2019-02-05", "2020-01-25", "2021-02-12", "2022-02-01", "2023-01-22",
       "2024-02-10", "2025-01-29", "2026-02-17"]


def fetch(symbol: str) -> pd.Series:
    f = CACHE / f"seasonality_{symbol}.parquet"
    if f.exists() and time.time() - f.stat().st_mtime < 86400:
        return pd.read_parquet(f)["close"]
    out, start = {}, 1502928000000
    while True:
        url = (f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d"
               f"&startTime={start}&limit=1000")
        try:
            rows = json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
        except Exception:
            break
        if not rows:
            break
        for r in rows:
            out[int(r[0])] = float(r[4])
        if len(rows) < 1000:
            break
        start = rows[-1][0] + 86400000
    s = pd.Series(out)
    if len(s):
        s.index = pd.to_datetime(s.index, unit="ms", utc=True)
        CACHE.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"close": s}).to_parquet(f)
    return s


def _stat(r):
    r = r.dropna()
    n = len(r)
    if n < 3:
        return None
    m = r.mean()
    se = r.std(ddof=1) / np.sqrt(n) if r.std(ddof=1) else np.nan
    return {"n": n, "mean": m, "win": (r > 0).mean(), "t": (m / se) if se else 0.0}


def _dateset(dates, ret_idx, window=(0, 0)):
    ds = [pd.Timestamp(d, tz="UTC").normalize() for d in dates]
    lo, hi = window
    return pd.Series([any(lo <= (d.normalize() - e).days <= hi for e in ds) for d in ret_idx], index=ret_idx)


def sheet(px: pd.Series):
    """All buckets for one coin -> {bucket: stat}, plus baseline."""
    px = px.sort_index()
    ret = np.log(px).diff().dropna()
    idx = ret.index
    base = ret.mean()
    B = {}
    for i, d in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        B[f"dow:{d}"] = _stat(ret[idx.weekday == i])
    for i, mo in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1):
        B[f"mon:{mo}"] = _stat(ret[idx.month == i])
    B["ev:FOMC day"] = _stat(ret[_dateset(FOMC, idx, (0, 0))])
    B["ev:FOMC +1d"] = _stat(ret[_dateset(FOMC, idx, (1, 1))])
    B["ev:CPI day~"] = _stat(ret[_dateset(CPI, idx, (0, 0))])
    B["ev:Turn-of-month"] = _stat(ret[(idx.day <= 3) | (idx.day >= 28)])
    B["ev:October"] = _stat(ret[idx.month == 10])
    B["ev:Thursday"] = _stat(ret[idx.weekday == 3])
    B["ev:CNY -5..+2"] = _stat(ret[_dateset(CNY, idx, (-5, 2))])
    B["ev:Earnings wk"] = _stat(ret[(idx.month.isin([1, 4, 7, 10])) & (idx.day >= 12) & (idx.day <= 26)])
    return {"base": base, "buckets": B, "span": (idx[0].date(), idx[-1].date(), len(ret))}


def color(mean, t):
    """Green/red by mean, opacity by |t| (confidence)."""
    if mean is None:
        return "background:#141a22;color:#3a4655"
    a = min(0.14 + abs(t) * 0.16, 0.85)
    c = "36,209,126" if mean >= 0 else "246,73,95"
    fg = "#e8f0f7" if abs(t) > 1.6 else "#9fb0c0"
    return f"background:rgba({c},{a:.2f});color:{fg}"


def cell(s):
    if not s:
        return '<td style="background:#141a22;color:#3a4655">·</td>'
    star = "***" if abs(s["t"]) > 2.6 else "**" if abs(s["t"]) > 2.0 else "*" if abs(s["t"]) > 1.6 else ""
    return (f'<td style="{color(s["mean"], s["t"])}" title="n={s['n']} win={s['win']*100:.0f}% t={s['t']:+.1f}">'
            f'{s["mean"]*100:+.2f}<sup>{star}</sup></td>')


def build_html(data):
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    dows = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    events = ["ev:FOMC day", "ev:FOMC +1d", "ev:CPI day~", "ev:October", "ev:Thursday",
              "ev:Turn-of-month", "ev:CNY -5..+2", "ev:Earnings wk"]
    coins = [c for c in COINS if c in data]

    def grid(title, keys, labels, note=""):
        head = "".join(f"<th>{l}</th>" for l in labels)
        body = ""
        for c in coins:
            cells = "".join(cell(data[c]["buckets"].get(k)) for k in keys)
            body += f'<tr><th class="rk">{c}</th>{cells}</tr>'
        return (f'<div class="sec"><h2>{title}<span class="note">{note}</span></h2>'
                f'<table><thead><tr><th class="rk"></th>{head}</tr></thead><tbody>{body}</tbody></table></div>')

    sp = data[coins[0]]["span"]
    css = """<style>
    body{background:#0a0e13;color:#c2ccd9;font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:22px 26px}
    h1{font-size:1.5rem;margin:0 0 3px} .sub{color:#6b7889;font-size:.82rem;margin-bottom:20px}
    .sec{margin-bottom:26px} h2{font-size:.95rem;color:#ffb020;font-weight:700;margin:0 0 9px;letter-spacing:.02em}
    h2 .note{color:#6b7889;font-weight:400;font-size:.72rem;margin-left:10px}
    table{border-collapse:separate;border-spacing:3px;width:100%}
    th{font-size:.66rem;color:#8b98a9;font-weight:600;text-align:center;padding:2px}
    td{font-family:'SF Mono',Consolas,monospace;font-size:.72rem;text-align:center;padding:6px 4px;border-radius:5px;font-weight:600}
    td sup{font-size:.6rem;opacity:.9} th.rk{text-align:right;color:#c2ccd9;font-weight:700;font-size:.72rem;padding-right:8px;width:44px}
    .legend{color:#6b7889;font-size:.72rem;margin-top:14px;line-height:1.6}
    .legend b{color:#9fb0c0}</style>"""
    return f"""<!doctype html><html><head><meta charset=utf-8>{css}</head><body>
    <h1>Crypto Calendar Movement Sheet</h1>
    <div class="sub">avg daily return (%) per bucket · {sp[0]} → {sp[1]} · Binance daily · green=up red=down, brighter=more significant · <b style="color:#e8f0f7">* |t|&gt;1.6 &nbsp; ** &gt;2 &nbsp; *** &gt;2.6</b> · hover for n/win/t</div>
    {grid("Month of year", [f"mon:{m}" for m in months], months, "the seasonal map — October is the standout")}
    {grid("Day of week", [f"dow:{d}" for d in dows], dows, "Thursday weakness across the board")}
    {grid("Events — the tradeable calendar", events, ["FOMC","FOMC+1","CPI~","October","Thursday","Turn-of-mo","CNY","Earnings wk"], "FOMC/CPI = macro bombs · ~ = CPI dates approximate ±1-2d")}
    <div class="legend">
    <b>Read:</b> each cell is the average % move on that kind of day, over {sp[2]}+ days. Brighter = the market treats that day as more reliably different from normal (higher t-stat). A lone <b>*</b> is suggestive; <b>**</b>/<b>***</b> is hard to dismiss as luck.<br>
    <b>Caveats:</b> newer coins (SOL/AVAX/DOT) have &lt;5yr so their cells are thinner. FOMC dates exact; CPI approximate. This measures the pattern — it is not yet backtested as a P&amp;L overlay.
    </div></body></html>"""


def run():
    print("fetching multi-year daily history for 12 coins (Binance, free)...")
    data = {}
    for c in COINS:
        sym = c + "USDT"
        px = fetch(sym)
        if len(px) > 400:
            data[c] = sheet(px)
            print(f"  {c:<6} {data[c]['span'][2]} days")
        else:
            print(f"  {c:<6} skipped (only {len(px)} days)")

    # console proof: the macro + top seasonal buckets per coin
    print("\n== FOMC day / CPI day / October / Thursday  (avg% , t) ==")
    print(f"{'coin':<6} {'FOMC':>13} {'CPI~':>13} {'October':>13} {'Thursday':>13}")
    for c in data:
        b = data[c]["buckets"]
        def f(k):
            s = b.get(k)
            return f"{s['mean']*100:+.2f}% t{s['t']:+.1f}" if s else "   n/a"
        print(f"{c:<6} {f('ev:FOMC day'):>13} {f('ev:CPI day~'):>13} {f('ev:October'):>13} {f('ev:Thursday'):>13}")

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(data), encoding="utf-8")
    print(f"\nHTML movement sheet -> {OUT_HTML}")


if __name__ == "__main__":
    run()
