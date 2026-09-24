"""The dashboard: the $50 paper book, and a detailed market overview.

    python scripts/dashboard.py          # serves on http://localhost:8770

No trades are placed here - the book is empty and ready. This turn is the
overview: every tradable Hyperliquid coin with its funding, basis, regional
premia and recent price, searchable and sortable, so a trade can be chosen well.
Stdlib http.server only, no dependencies, same pattern as the cryptobot relay.
"""
from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl.market import market_overview  # noqa: E402
from hl.paper import Paper, TRADE_SIZE_USD  # noqa: E402
import hl.triggers as tg  # noqa: E402
from hl import journal  # noqa: E402
from hl import watchlist as wl  # noqa: E402
from hl import regime as regime_mod  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PORT = int(__import__("os").environ.get("QT_PORT", "8770"))
_cache = {"t": 0.0, "data": None}
_spark = {"t": 0.0, "px": None}
_narr = {"t": 0.0, "raw": None, "syms": None}


def market_cached():
    if time.time() - _cache["t"] > 20 or _cache["data"] is None:
        _cache["data"] = market_overview()
        _cache["t"] = time.time()
    return _cache["data"]


def _spark_frame():
    """Daily-close history (cached 5 min) for per-row sparklines."""
    if time.time() - _spark["t"] > 300 or _spark["px"] is None:
        try:
            import pandas as pd
            f = ROOT / "data" / "carry_cache" / "daily_365.parquet"
            _spark["px"] = pd.read_parquet(f) if f.exists() else None
        except Exception:
            _spark["px"] = None
        _spark["t"] = time.time()
    return _spark["px"]


def spark_series(coin, n=32):
    px = _spark_frame()
    if px is None or coin not in px.columns:
        return []
    s = px[coin].dropna().tail(n)
    return [round(float(v), 8) for v in s.tolist()]


def equity_series(limit=240):
    """The real portfolio equity curve, logged each settle beat."""
    import sqlite3
    db = ROOT / "data" / "paper.db"
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT ts_ms, total_pnl FROM equity_curve ORDER BY ts_ms DESC LIMIT ?",
            (limit,)).fetchall()
        conn.close()
        return [{"t": r[0], "v": r[1]} for r in reversed(rows)]
    except Exception:
        return []


def book_state():
    """The real paper engine: cumulative ledger + live open positions."""
    bk = Paper()
    try:
        a = bk.account()
        opens = bk.open_positions()
        closed = bk.closed_positions(200)
        compare = bk.book_compare()
    finally:
        bk.close()

    def slim_open(p):
        return {"coin": p["coin"], "side": p["side"], "leverage": p["leverage"],
                "entry_px": p["entry_px"], "mark": p.get("mark_now"),
                "stop_px": p["stop_px"], "target_px": p["target_px"],
                "hold_hours": p["hold_hours"], "opened_ms": p["opened_ms"],
                "close_after_ms": p["close_after_ms"],
                "unrealized_pnl": p.get("unrealized_pnl"),
                "unrealized_pct": p.get("unrealized_pct"), "thesis": p["thesis"],
                "funding_accrued": p.get("funding_accrued"),
                "is_hedge": bool(p.get("is_hedge")), "tag": p.get("tag") or "fused",
                "spark": spark_series(p["coin"])}

    def slim_closed(c):
        return {"coin": c["coin"], "side": c["side"], "reason": c["exit_reason"],
                "entry_px": c["entry_px"], "exit_px": c["exit_px"],
                "pnl_usd": c["pnl_usd"], "opened_ms": c["opened_ms"],
                "closed_ms": c["closed_ms"], "thesis": c["thesis"]}

    return {"trade_size_usd": TRADE_SIZE_USD, "leverage_default": 2, "leverage_max": 4,
            "n_open": a["n_open"], "n_closed": a["n_closed"], "n_trades": a["n_trades"],
            "realized_pnl": a["realized_pnl"], "unrealized_pnl": a["unrealized_pnl"],
            "total_pnl": a["total_pnl"], "win_rate": a["win_rate"],
            "fees_paid": a["fees_paid"], "open_notional": a["open_notional"],
            "open": [slim_open(p) for p in opens],
            "closed": [slim_closed(c) for c in closed],
            "triggers": [{"coin": t["coin"], "kind": t["kind"], "side": t["side"],
                          "pct": t["pct"], "level": t["level"], "peak": t["peak"],
                          "trough": t["trough"], "fires_at":
                              (t["peak"] * (1 - t["pct"]) if t["kind"] == "drop_from_peak" and t["peak"] and t["pct"]
                               else t["trough"] * (1 + t["pct"]) if t["kind"] == "rise_from_trough" and t["trough"] and t["pct"]
                               else t["level"]),
                          "thesis": t["thesis"]}
                         for t in tg.list_triggers("armed")],
            "alerts": [{"ts_ms": a["ts_ms"], "coin": a["coin"], "level": a["level"],
                        "message": a["message"]} for a in tg.recent_alerts(8)],
            "learn": _learn_summary(),
            "equity": equity_series(),
            "watchlist": _watchlist(),
            "regime": _regime(),
            "risk": _risk(),
            "rotation": _rotation(),
            "radar": _radar(),
            "scorecard": _scorecard(),
            "hedge": a.get("hedge"),
            "compare": compare,
            "tide": _tide(),
            "layer2": _layer2(),
            "gate_exp": _gate_exp()}


_ge = {"t": 0.0, "data": None}


def _gate_exp():
    """Gated-vs-ungated forward experiment scorecard (DB read, cheap). Cached 60s."""
    import time as _t
    if _t.time() - _ge["t"] < 60 and _ge["data"] is not None:
        return _ge["data"]
    try:
        from hl import gate_experiment
        _ge["data"] = gate_experiment.scorecard()
    except Exception as e:
        _ge["data"] = {"error": str(e)}
    _ge["t"] = _t.time()
    return _ge["data"]


_l2 = {"t": 0.0, "data": None}


def _layer2():
    """Layer-2 beat-the-tide leaderboard (residual strength + funding). Cached 180s."""
    import time as _t
    if _t.time() - _l2["t"] < 180 and _l2["data"] is not None:
        return _l2["data"]
    try:
        from hl import layer2
        _l2["data"] = layer2.leaderboard(8)
    except Exception as e:
        _l2["data"] = {"error": str(e), "leaders": [], "laggards": []}
    _l2["t"] = _t.time()
    return _l2["data"]


_td = {"t": 0.0, "data": None}


def _tide():
    """Layer-1 macro risk-on/off regime (the ~70% tide). Reads the BTC parquet; cache 300s.
    Validated: step-aside-in-RISK-OFF cuts maxDD 77%->58%, lifts Sharpe 0.42->0.60."""
    import time as _t
    if _t.time() - _td["t"] < 300 and _td["data"] is not None:
        return _td["data"]
    try:
        from hl import macro_regime
        d = macro_regime.read()
        d["validated"] = {"bh_maxdd": -77, "sa_maxdd": -58, "bh_sharpe": 0.42, "sa_sharpe": 0.60}
        _td["data"] = d
    except Exception as e:
        _td["data"] = {"label": "UNKNOWN", "score": None, "error": str(e)}
    _td["t"] = _t.time()
    return _td["data"]


_tf = {"t": 0.0, "data": None}

_COMMOD = {"GOLD", "SILVER", "OIL", "CL", "BRENTOIL", "GAS", "NATGAS", "COPPER", "PLATINUM",
           "PALLADIUM", "ALUMINIUM", "WHEAT", "GOLDJM", "SILVERJM", "USOIL"}
_INDEX = {"SP500", "XYZ100", "US500", "USTECH", "SMALL2000", "MAG7", "SEMIS", "ROBOT",
          "NUCLEAR", "DEFENSE", "ENERGY", "BIOTECH", "INFOTECH", "USENERGY", "SOXL", "NASDAQ"}


def _tradfi():
    """Live TradFi markets (equities/commodities/indices) from the xyz builder dex.
    Cached 60s. Returns markets sorted by 24h volume + our open equity positions."""
    import time as _t
    if _t.time() - _tf["t"] < 60 and _tf["data"] is not None:
        return _tf["data"]
    import json as _j
    import urllib.request as _u

    def post(b):
        return _j.loads(_u.urlopen(_u.Request(
            "https://api.hyperliquid.xyz/info", data=_j.dumps(b).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}), timeout=20).read())
    out = []
    try:
        r = post({"type": "metaAndAssetCtxs", "dex": "xyz"})
        for u, c in zip(r[0]["universe"], r[1]):
            px = float(c.get("markPx") or 0)
            prev = float(c.get("prevDayPx") or 0)
            if px <= 0:
                continue
            tick = u["name"].split(":", 1)[1]
            fund = c.get("funding")
            cat = ("commodity" if tick in _COMMOD else "index" if tick in _INDEX else "stock")
            out.append({"coin": u["name"], "ticker": tick, "price": px,
                        "change": (px / prev - 1) if prev else None,
                        "vol": float(c.get("dayNtlVlm") or 0),
                        "oi": float(c.get("openInterest") or 0) * px,
                        "funding_apr": (float(fund) * 24 * 365) if fund else None,
                        "maxLev": u.get("maxLeverage"), "cat": cat})
        out.sort(key=lambda x: -x["vol"])
    except Exception as e:
        _tf["data"] = {"markets": [], "error": str(e)}
        _tf["t"] = _t.time()
        return _tf["data"]
    # our open equity positions (from the paper book)
    positions = []
    try:
        bk = Paper()
        for p in bk.open_positions():
            if ":" in p["coin"] and not p.get("is_hedge"):
                positions.append({"coin": p["coin"], "side": p["side"], "entry_px": p["entry_px"],
                                  "mark": p.get("mark_now"), "unrealized_pnl": p.get("unrealized_pnl"),
                                  "unrealized_pct": p.get("unrealized_pct"), "thesis": p.get("thesis")})
        bk.close()
    except Exception:
        pass
    _tf["data"] = {"markets": out, "n": len(out), "positions": positions}
    _tf["t"] = _t.time()
    return _tf["data"]


_sc = {"t": 0.0, "data": None}


def _scorecard():
    """The forward score-tracker's running record (DB read, cheap). Cached 60s."""
    import time as _t
    if _t.time() - _sc["t"] < 60 and _sc["data"] is not None:
        return _sc["data"]
    try:
        from hl import tracker
        _sc["data"] = tracker.scorecard()
    except Exception as e:
        _sc["data"] = {"error": str(e)}
    _sc["t"] = _t.time()
    return _sc["data"]


_rad = {"t": 0.0, "data": None}


def _radar():
    if time.time() - _rad["t"] < 90 and _rad["data"] is not None:
        return _rad["data"]
    try:
        from hl import radar
        _rad["data"] = radar.scan(top=15)
        _rad["t"] = time.time()
    except Exception:
        _rad["data"] = []
    return _rad["data"]


_rot = {"t": 0.0, "data": None}


def _rotation():
    if time.time() - _rot["t"] < 180 and _rot["data"]:
        return _rot["data"]
    try:
        from hl import rotation
        _rot["data"] = rotation.stage()
        _rot["t"] = time.time()
    except Exception:
        _rot["data"] = None
    return _rot["data"]


def _risk():
    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{ROOT/'data'/'triggers.db'}?mode=ro", uri=True)
        r = conn.execute("SELECT bp_score,bp_level,crash_score,crash_level,detail FROM risk_state WHERE id=1").fetchone()
        conn.close()
        if not r:
            return None
        import json as _j
        return {"bp_score": r[0], "bp_level": r[1], "crash_score": r[2],
                "crash_level": r[3], "detail": _j.loads(r[4] or "{}")}
    except Exception:
        return None


def _regime():
    try:
        return regime_mod.read()
    except Exception:
        return None


def _watchlist():
    try:
        return wl.list_all()
    except Exception:
        return []


def _learn_summary():
    try:
        r = journal.review()
        if not r.get("n"):
            return None
        return {"overall": r["overall"], "by_side": r["by_side"],
                "by_setup": r["by_setup"], "by_regime": r.get("by_regime", {}),
                "pending": len(journal.pending_reviews()),
                "lessons": r["lessons"]}
    except Exception:
        return None


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hyperliquid Paper Desk</title>
<style>
:root{--bg:#0a0e14;--panel:#111823;--line:#1e2a3a;--txt:#c9d6e5;--dim:#6b7c93;
--grn:#3fd07f;--red:#ff5f6d;--acc:#4aa3ff;--warn:#ffb454}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:13px/1.4 ui-monospace,Menlo,Consolas,monospace}
header{padding:12px 18px;border-bottom:1px solid var(--line);display:flex;
gap:24px;align-items:baseline;flex-wrap:wrap}
h1{font-size:15px;margin:0;color:#fff;letter-spacing:.5px}
.book{display:flex;gap:20px;color:var(--dim);font-size:12px}
.book b{color:var(--txt)}
.bal{color:var(--grn);font-size:15px}
main{padding:14px 18px}
.bar{display:flex;gap:10px;margin-bottom:10px;align-items:center;flex-wrap:wrap}
input,select{background:var(--panel);border:1px solid var(--line);color:var(--txt);
padding:6px 9px;border-radius:5px;font:inherit}
input{width:180px}
.chip{padding:5px 10px;border:1px solid var(--line);border-radius:14px;cursor:pointer;
color:var(--dim);user-select:none}
.chip.on{background:var(--acc);color:#001;border-color:var(--acc)}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:right;padding:7px 9px;border-bottom:1px solid var(--line);color:var(--dim);
cursor:pointer;white-space:nowrap;position:sticky;top:0;background:var(--bg)}
th:first-child,td:first-child{text-align:left}
td{padding:6px 9px;border-bottom:1px solid #131c28;white-space:nowrap}
tr:hover td{background:#0e1520}
.coin{color:#fff;font-weight:600}
.pos{color:var(--grn)}.neg{color:var(--red)}.mut{color:var(--dim)}
.hot{color:var(--warn);font-weight:600}
.foot{color:var(--dim);font-size:11px;margin-top:10px}
.pill{font-size:10px;padding:1px 6px;border-radius:8px;background:#16202e;color:var(--dim)}
.ptitle{color:var(--acc);font-size:11px;letter-spacing:.5px;margin:12px 0 4px}
.ptab{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:6px}
.ptab th{position:static;text-align:right;padding:5px 9px;border-bottom:1px solid var(--line);color:var(--dim)}
.ptab td{padding:5px 9px;border-bottom:1px solid #131c28;text-align:right}
.ptab th:first-child,.ptab td:first-child,.ptab .thesis{text-align:left}
.ptab .thesis{color:var(--dim);max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style></head><body>
<header>
  <h1>HYPERLIQUID PAPER DESK</h1>
  <div class="book" id="book"></div>
  <div class="book" id="asof" style="margin-left:auto"></div>
</header>
<main>
  <div id="watchers"></div>
  <div id="positions"></div>
  <div id="learn"></div>
  <div class="bar">
    <input id="q" placeholder="search coin...">
    <span class="chip" data-f="all" >all</span>
    <span class="chip on" data-f="liq">liquid &gt;$20m</span>
    <span class="chip" data-f="hifund">funding &gt;50% apr</span>
    <span class="chip" data-f="basis">|basis| &gt;10bps</span>
    <span class="chip" data-f="kr">has KR/IN premium</span>
    <span class="mut" id="count"></span>
  </div>
  <table id="tbl"><thead><tr>
    <th data-k="coin">coin</th>
    <th data-k="price">price</th>
    <th data-k="funding_apr">funding APR</th>
    <th data-k="funding_pctile">f%ile</th>
    <th data-k="basis_bps">perp-spot bps</th>
    <th data-k="hl_dev_bps">HL vs world</th>
    <th data-k="dispersion_bps">venue disp</th>
    <th data-k="premium_krw_bps">KR prem</th>
    <th data-k="premium_inr_bps">IN prem</th>
    <th data-k="top_minus_retail">top-retail</th>
    <th data-k="ret_1d">1d</th>
    <th data-k="ret_7d">7d</th>
    <th data-k="ret_30d">30d</th>
    <th data-k="vol_30d">vol</th>
    <th data-k="credible_vol_usd">24h vol</th>
    <th data-k="n_venues">venues</th>
  </tr></thead><tbody id="rows"></tbody></table>
  <div class="foot" id="foot"></div>
</main>
<script>
let DATA=[], sortK="credible_vol_usd", sortDir=-1, filter="liq", q="";
const bps=x=>x==null?'<span class=mut>-</span>':(x>0?'+':'')+x.toFixed(1);
const pc=x=>x==null?'<span class=mut>-</span>':((x>0?'<span class=pos>+':'<span class=neg>')+(x*100).toFixed(1)+'%</span>');
const pct=x=>x==null?'<span class=mut>-</span>':(x*100).toFixed(0);
const usd=x=>x==null?'<span class=mut>-</span>':'$'+(x/1e6).toFixed(1)+'m';
const px=x=>x==null?'-':x<0.01?x.toPrecision(3):x.toLocaleString(undefined,{maximumSignificantDigits:6});
function apr(x){if(x==null)return '<span class=mut>-</span>';const c=Math.abs(x)>0.5?'hot':(x>0?'pos':'neg');return '<span class='+c+'>'+(x>0?'+':'')+(x*100).toFixed(0)+'%</span>';}

function pass(r){
  if(q && !r.coin.toLowerCase().includes(q)) return false;
  if(filter==='liq') return (r.credible_vol_usd||0)>2e7;
  if(filter==='hifund') return r.funding_apr!=null && Math.abs(r.funding_apr)>0.5;
  if(filter==='basis') return r.basis_bps!=null && Math.abs(r.basis_bps)>10;
  if(filter==='kr') return r.premium_krw_bps!=null || r.premium_inr_bps!=null;
  return true;
}
function render(){
  let rows=DATA.filter(pass);
  rows.sort((a,b)=>{let x=a[sortK],y=b[sortK];if(x==null)return 1;if(y==null)return -1;
    return (x<y?-1:x>y?1:0)*sortDir;});
  document.getElementById('count').textContent=rows.length+' coins';
  document.getElementById('rows').innerHTML=rows.map(r=>`<tr>
    <td class=coin>${r.coin}</td><td>${px(r.price)}</td>
    <td>${apr(r.funding_apr)}</td><td class=mut>${pct(r.funding_pctile)}</td>
    <td>${bps(r.basis_bps)}</td><td>${bps(r.hl_dev_bps)}</td><td class=mut>${bps(r.dispersion_bps)}</td>
    <td>${bps(r.premium_krw_bps)}</td><td>${bps(r.premium_inr_bps)}</td>
    <td>${pc(r.top_minus_retail)}</td>
    <td>${pc(r.ret_1d)}</td><td>${pc(r.ret_7d)}</td><td>${pc(r.ret_30d)}</td>
    <td class=mut>${r.vol_30d==null?'-':(r.vol_30d*100).toFixed(0)+'%'}</td>
    <td class=mut>${usd(r.credible_vol_usd)}</td><td class=mut>${r.n_venues||'-'}</td></tr>`).join('');
}
function renderWatchers(b){
  const el=document.getElementById('watchers');
  const ts=b.triggers||[], al=b.alerts||[];
  if(!ts.length && !al.length){el.innerHTML='';return;}
  let h='';
  if(ts.length){
    h+='<div class=ptitle>ARMED WATCHERS ('+ts.length+') — the bot fires these on its own</div>'+
      '<table class=ptab><thead><tr><th>coin</th><th>condition</th><th>fires at</th>'+
      '<th>tracking</th><th class=thesis>plan</th></tr></thead><tbody>'+
      ts.map(t=>{const cond=t.kind=='drop_from_peak'?('short if -'+(t.pct*100).toFixed(0)+'% from peak'):
        t.kind=='rise_from_trough'?('long if +'+(t.pct*100).toFixed(0)+'% from trough'):
        (t.side+' if '+(t.kind=='cross_below'?'≤':'≥')+' '+px(t.level));
        const track=t.peak?('peak '+px(t.peak)):(t.trough?('trough '+px(t.trough)):'-');
        return `<tr><td class=coin>${t.coin}</td><td class=${t.side=='long'?'pos':'neg'}>${cond}</td>`+
          `<td class=hot>${px(t.fires_at)}</td><td class=mut>${track}</td>`+
          `<td class=thesis title="${(t.thesis||'').replace(/"/g,'&quot;')}">${(t.thesis||'').slice(0,64)}</td></tr>`;}).join('')+
      '</tbody></table>';
  }
  if(al.length){
    h+='<div class=ptitle>ALERTS</div><table class=ptab><tbody>'+
      al.map(a=>{const c=a.level=='FIRED'?'pos':a.level=='ERROR'?'neg':'mut';
        const t=new Date(a.ts_ms).toLocaleTimeString();
        return `<tr><td class=mut>${t}</td><td class=${c}>[${a.level}]</td><td class=thesis>${(a.message||'').replace(/</g,'&lt;')}</td></tr>`;}).join('')+
      '</tbody></table>';
  }
  el.innerHTML=h;
}
function renderLearn(b){
  const el=document.getElementById('learn');
  const L=b.learn;
  if(!L){el.innerHTML='';return;}
  const o=L.overall;
  let h='<div class=ptitle>WHAT WE\'VE LEARNED — '+o.n+' closed · '+(o.win_rate*100).toFixed(0)+
    '% win · $'+o.total_pnl.toFixed(2)+(L.pending?(' · <span class=neg>'+L.pending+' awaiting post-mortem</span>'):'')+'</div>';
  h+='<table class=ptab><thead><tr><th>bucket</th><th>trades</th><th>win</th><th>P&L $</th></tr></thead><tbody>';
  for(const [s,v] of Object.entries(L.by_side||{}))
    h+=`<tr><td class=${s=='long'?'pos':'neg'}>${s}</td><td>${v.n}</td><td>${(v.win_rate*100).toFixed(0)}%</td><td class=${v.total_pnl>=0?'pos':'neg'}>${v.total_pnl>=0?'+':''}${v.total_pnl.toFixed(2)}</td></tr>`;
  for(const [t,v] of Object.entries(L.by_setup||{}))
    h+=`<tr><td class=mut>${t}</td><td>${v.n}</td><td>${(v.win_rate*100).toFixed(0)}%</td><td class=${v.total_pnl>=0?'pos':'neg'}>${v.total_pnl>=0?'+':''}${v.total_pnl.toFixed(2)}</td></tr>`;
  h+='</tbody></table>';
  if(L.lessons && L.lessons.length){
    h+='<table class=ptab><tbody>'+L.lessons.map(l=>
      `<tr><td class=coin>${l.coin}</td><td class=mut>[${l.setup_tag||'-'}]</td><td class=thesis title="${(l.lesson||'').replace(/"/g,'&quot;')}">${(l.lesson||'').slice(0,90)}</td></tr>`).join('')+'</tbody></table>';
  }
  el.innerHTML=h;
}
function renderPositions(b){
  const el=document.getElementById('positions');
  if(!b.open.length && !b.closed.length){el.innerHTML='';return;}
  const dur=ms=>{const h=(Date.now()-ms)/3.6e6;return h<1?Math.round(h*60)+'m':h.toFixed(1)+'h';}
  const left=ms=>{const h=(ms-Date.now())/3.6e6;return h<0?'due':h<1?Math.round(h*60)+'m':h.toFixed(1)+'h';}
  let h='';
  if(b.open.length){
    h+='<div class=ptitle>OPEN POSITIONS ('+b.open.length+')</div><table class=ptab><thead><tr>'+
      '<th>coin</th><th>side</th><th>lev</th><th>entry</th><th>mark</th><th>stop</th><th>target</th>'+
      '<th>P&L $</th><th>P&L %</th><th>age</th><th>time left</th><th class=thesis>thesis</th></tr></thead><tbody>'+
      b.open.map(p=>{const pc=(p.unrealized_pnl||0)>=0?'pos':'neg';
      return `<tr><td class=coin>${p.coin}</td><td class=${p.side=='long'?'pos':'neg'}>${p.side}</td>`+
        `<td class=mut>${p.leverage}x</td><td>${px(p.entry_px)}</td><td>${px(p.mark)}</td>`+
        `<td class=mut>${px(p.stop_px)}</td><td class=mut>${px(p.target_px)}</td>`+
        `<td class=${pc}>${(p.unrealized_pnl||0)>=0?'+':''}${(p.unrealized_pnl||0).toFixed(2)}</td>`+
        `<td class=${pc}>${(p.unrealized_pct||0).toFixed(1)}%</td>`+
        `<td class=mut>${dur(p.opened_ms)}</td><td class=mut>${left(p.close_after_ms)}</td>`+
        `<td class=thesis title="${(p.thesis||'').replace(/"/g,'&quot;')}">${(p.thesis||'').slice(0,60)}</td></tr>`;}).join('')+
      '</tbody></table>';
  }
  if(b.closed.length){
    h+='<div class=ptitle>CLOSED ('+b.closed.length+')</div><table class=ptab><thead><tr>'+
      '<th>coin</th><th>side</th><th>entry</th><th>exit</th><th>reason</th><th>P&L $</th><th>held</th></tr></thead><tbody>'+
      b.closed.slice(0,15).map(c=>{const pc=(c.pnl_usd||0)>=0?'pos':'neg';
      return `<tr><td class=coin>${c.coin}</td><td class=${c.side=='long'?'pos':'neg'}>${c.side}</td>`+
        `<td>${px(c.entry_px)}</td><td>${px(c.exit_px)}</td><td class=mut>${c.reason}</td>`+
        `<td class=${pc}>${(c.pnl_usd||0)>=0?'+':''}${(c.pnl_usd||0).toFixed(2)}</td>`+
        `<td class=mut>${((c.closed_ms-c.opened_ms)/3.6e6).toFixed(1)}h</td></tr>`;}).join('')+
      '</tbody></table>';
  }
  el.innerHTML=h;
}
async function load(){
  const m=await (await fetch('/api/market')).json();
  DATA=m.coins;
  const b=await (await fetch('/api/book')).json();
  const tp=b.total_pnl||0, rp=b.realized_pnl||0;
  const pcls=tp>=0?'pos':'neg';
  document.getElementById('book').innerHTML=
    `<span class=bal><span class=${pcls}>${tp>=0?'+':''}$${tp.toFixed(2)}</span> total P&L</span>`+
    `<span>trades <b>${b.n_trades}</b> (${b.n_open} open · ${b.n_closed} closed)</span>`+
    `<span>realized <span class=${rp>=0?'pos':'neg'}>${rp>=0?'+':''}$${rp.toFixed(2)}</span></span>`+
    `<span>win <b>${b.win_rate==null?'-':(b.win_rate*100).toFixed(0)+'%'}</b></span>`+
    `<span>$${b.trade_size_usd}/trade · ${b.leverage_default}x</span>`;
  renderWatchers(b);
  renderPositions(b);
  renderLearn(b);
  const a=m.as_of;
  const ago=t=>t?Math.round((Date.now()-t)/1000)+'s':'-';
  document.getElementById('asof').innerHTML=
    `<span>${m.n_tradable} tradable · basis ${m.n_with_basis} · daily ${m.n_with_daily}</span>`+
    `<span>prices ${ago(a.hl_ms)} · features ${ago(a.cross_venue_ms)}</span>`;
  document.getElementById('foot').textContent=
    'tradable = coins Hyperliquid is currently pricing. Percentiles are across the tradable set. '+
    'Blank cells = not enough data yet (daily returns need the candle cache; premia need KR/IN venues).';
  render();
}
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{
  document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));
  c.classList.add('on');filter=c.dataset.f;render();});
document.querySelectorAll('th').forEach(t=>t.onclick=()=>{
  const k=t.dataset.k;if(sortK===k)sortDir*=-1;else{sortK=k;sortDir=-1;}render();});
document.getElementById('q').oninput=e=>{q=e.target.value.toLowerCase();render();};
load();setInterval(load,20000);
</script></body></html>"""


_ov = {}


# how far back each timeframe looks, in hours (1h candles, HL caps ~5000)
_TF_HOURS = {"1D": 48, "1W": 192, "1M": 744, "1Y": 8760, "YTD": None}
# days back that each timeframe compares against, for history-capable series
_TF_DAYS = {"1D": 1, "1W": 7, "1M": 30, "1Y": 364, "YTD": None}
_cg = {"t": 0.0, "glob": None, "btc": None}
_fng = {"t": 0.0, "data": None}


def _cg_get(url, key, ttl=180):
    """CoinGecko is rate-limited on the free tier; cache across timeframes."""
    import time as _t
    import json as _j
    import urllib.request as _u
    if _t.time() - _cg["t"] < ttl and _cg.get(key) is not None:
        return _cg[key]
    r = _j.loads(_u.urlopen(_u.Request(
        url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
    _cg[key] = r
    _cg["t"] = _t.time()
    return r


def _overview(tf="1D"):
    """Everything the Market Overview panel shows. Every number is live:
      - crypto cap / 24h volume / BTC dominance : CoinGecko /global
      - Fear & Greed                            : alternative.me/fng
      - regional rows                           : BTC's return across each
        region's real cash-equity session hours (UTC), from HL 1h candles.
    Cached 120s."""
    import time as _t
    import json as _j
    import urllib.request as _u
    import datetime as _dt
    tf = tf if tf in _TF_HOURS else "1D"
    slot = _ov.get(tf)
    if slot and _t.time() - slot["t"] < 120:
        return slot["data"]
    hours = _TF_HOURS[tf]
    if hours is None:   # YTD: hours since Jan 1, capped to what the API returns
        now = _dt.datetime.utcnow()
        hours = int((now - _dt.datetime(now.year, 1, 1)).total_seconds() // 3600) + 24

    def get(u):
        return _j.loads(_u.urlopen(_u.Request(
            u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())

    out = {}
    try:
        d = _cg_get("https://api.coingecko.com/api/v3/global", "glob")["data"]
        out["cap"] = d["total_market_cap"]["usd"]
        # total-market-cap history is not on the free tier: only 1D is real
        out["cap_chg"] = d["market_cap_change_percentage_24h_usd"] if tf == "1D" else None
        out["cap_chg_note"] = "24h only (no free history)" if tf != "1D" else None
        out["vol"] = d["total_volume"]["usd"]
        out["btc_dom"] = d["market_cap_percentage"]["btc"]
    except Exception as e:
        out["global_error"] = str(e)
    try:
        import time as _tt
        if _tt.time() - _fng["t"] > 900 or _fng["data"] is None:
            _fng["data"] = get("https://api.alternative.me/fng/?limit=400")["data"]
            _fng["t"] = _tt.time()
        f = _fng["data"]
        out["fng"] = int(f[0]["value"])
        out["fng_label"] = f[0]["value_classification"]
        # compare against the value at the START of the selected window
        back = _TF_DAYS[tf]
        if back is None:      # YTD -> 1 Jan of this year
            import datetime as _d2
            jan1 = _d2.date(_d2.datetime.utcnow().year, 1, 1)
            back = (_d2.datetime.utcnow().date() - jan1).days
        idx = min(max(back, 1), len(f) - 1)
        out["fng_prev"] = int(f[idx]["value"])
        out["fng_prev_days"] = idx
    except Exception as e:
        out["fng_error"] = str(e)
    # BTC's own change over the selected window (real, from CoinGecko)
    try:
        m = _cg_get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
                    "&ids=bitcoin&price_change_percentage=24h%2C7d%2C30d%2C1y", "btc")[0]
        field = {"1D": "price_change_percentage_24h_in_currency",
                 "1W": "price_change_percentage_7d_in_currency",
                 "1M": "price_change_percentage_30d_in_currency",
                 "1Y": "price_change_percentage_1y_in_currency",
                 "YTD": "price_change_percentage_1y_in_currency"}[tf]
        out["btc_chg"] = m.get(field)
        out["btc_price"] = m.get("current_price")
    except Exception as e:
        out["btc_error"] = str(e)
    # region name -> that region's main cash-equity session, in UTC hours
    SESSIONS = [("ASIA", 0, 8), ("EUROPE", 7, 16),
                ("N. AMERICA", 13, 21), ("S. AMERICA", 13, 20)]
    try:
        import datetime as _dt
        ms = int(_t.time() * 1000)
        interval, step = ("1h", 1) if hours <= 4800 else ("4h", 4)
        body = {"type": "candleSnapshot",
                "req": {"coin": "BTC", "interval": interval,
                        "startTime": ms - 1000 * 3600 * hours, "endTime": ms}}
        c = _j.loads(_u.urlopen(_u.Request(
            "https://api.hyperliquid.xyz/info", data=_j.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "User-Agent": "Mozilla/5.0"}), timeout=20).read())
        buckets = {}
        for k in c:
            h = _dt.datetime.utcfromtimestamp(k["t"] / 1000)
            buckets.setdefault(h.date(), []).append((h.hour, float(k["o"]), float(k["c"])))
        for d_ in buckets:
            buckets[d_].sort()
        import math as _m
        rows = []
        for name, h0, h1 in SESSIONS:
            tot, n_sess = 0.0, 0
            lo = (h0 // step) * step                 # snap outward to the
            hi = -(-h1 // step) * step                # candle grid
            for day in sorted(buckets):
                inside = [b for b in buckets[day] if lo <= b[0] < hi]
                if len(inside) < 2:
                    continue
                o, cl = inside[0][1], inside[-1][2]
                if o and cl:
                    tot += _m.log(cl / o)      # compound across sessions
                    n_sess += 1
            rows.append({"name": name,
                         "hours": "%02d-%02dZ" % ((h0 // step) * step, -(-h1 // step) * step),
                         "sessions": n_sess,
                         "pct": ((_m.exp(tot) - 1) * 100) if n_sess else None})
        out["regions"] = rows
        out["tf"] = tf
        out["window_hours"] = hours
        out["interval"] = interval
    except Exception as e:
        out["regions"] = []
        out["regions_error"] = str(e)
    _ov[tf] = {"data": out, "t": _t.time()}
    return out


# ---------------------------------------------------------------- news
# Feed list and the exchange-announcement endpoints are the same ones proven in
# the cryptobot relay: all keyless, all public. Browsers cannot fetch RSS
# cross-origin, so this has to happen server-side.
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

# (name, url, category) - category comes from the SOURCE, never from parsing
# headline words.
_FEEDS = [
    ("CoinDesk",         "https://www.coindesk.com/arc/outboundfeeds/rss/",      "CRYPTO"),
    ("Cointelegraph",    "https://cointelegraph.com/rss",                        "CRYPTO"),
    ("Decrypt",          "https://decrypt.co/feed",                              "CRYPTO"),
    ("CryptoSlate",      "https://cryptoslate.com/feed/",                        "CRYPTO"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/feed",                     "CRYPTO"),
    ("Bitcoin.com",      "https://news.bitcoin.com/feed/",                       "CRYPTO"),
    ("CoinJournal",      "https://coinjournal.net/feed/",                        "CRYPTO"),
    ("Bitcoinist",       "https://bitcoinist.com/feed/",                         "CRYPTO"),
    ("NewsBTC",          "https://www.newsbtc.com/feed/",                        "CRYPTO"),
    ("Crypto Briefing",  "https://cryptobriefing.com/feed/",                     "CRYPTO"),
    ("Protos",           "https://protos.com/feed/",                             "CRYPTO"),
    ("SEC",              "https://www.sec.gov/news/pressreleases.rss",           "MACRO"),
    ("Federal Reserve",  "https://www.federalreserve.gov/feeds/press_all.xml",   "MACRO"),
    ("BEA",              "https://apps.bea.gov/rss/rss.xml",                     "MACRO"),
]

_ANNOUNCE = [
    ("Binance", "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
                "?type=1&catalogId=48&pageNo=1&pageSize=15"),
    ("Upbit",   "https://api-manager.upbit.com/api/v1/announcements"
                "?os=web&page=1&per_page=15&category=trade"),
    ("Bybit",   "https://api.bybit.com/v5/announcements/index?locale=en-US&limit=15"),
]

# Publishers tag their own stories; these are THEIR label strings normalised
# onto the panel's chips. This is not keyword-matching on headline text - no
# story is classified by words in its title, only by the tag its publisher set.
_TAG_MAP = {
    "MARKETS":   {"markets", "market", "markets and prices", "trading", "price analysis",
                  "etf", "prediction markets"},
    "MACRO":     {"macro", "politics", "policy", "regulation", "regulation & legal",
                  "law and order", "legal", "government"},
    "COMPANIES": {"business", "companies", "company news", "ipo", "stocks", "finance",
                  "people"},
}


def _cat_from_tags(tags, default):
    """Category from the publisher's own tags; falls back to the source default."""
    low = {(t or "").strip().lower() for t in tags}
    for cat in ("MACRO", "MARKETS", "COMPANIES"):
        if low & _TAG_MAP[cat]:
            return cat
    return default


_news = {"t": 0.0, "data": None}


def _rss(name, url, cat, out):
    import urllib.request as _u
    import email.utils as _eu
    from xml.etree import ElementTree as _ET
    try:
        raw = _u.urlopen(_u.Request(url, headers=_UA), timeout=12).read()
        root = _ET.fromstring(raw)
        items = root.findall(".//item") or root.findall(
            ".//{http://www.w3.org/2005/Atom}entry")
        got = []
        for it in items[:20]:
            title = (it.findtext("title")
                     or it.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
            link = (it.findtext("link")
                    or it.findtext("{http://www.w3.org/2005/Atom}id") or "").strip()
            pub = (it.findtext("pubDate")
                   or it.findtext("{http://www.w3.org/2005/Atom}published")
                   or it.findtext("{http://www.w3.org/2005/Atom}updated")
                   or it.findtext("published") or "").strip()
            ts = None
            try:
                ts = _eu.parsedate_to_datetime(pub).timestamp()
            except Exception:
                try:
                    import datetime as _dd
                    ts = _dd.datetime.fromisoformat(
                        pub.replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass
            tags = [c.text for c in it.findall("category") if c.text]
            if title:
                # regulators and exchanges keep their source-level category;
                # publishers get theirs from their own tags
                use = cat if cat != "CRYPTO" else _cat_from_tags(tags, "CRYPTO")
                got.append({"title": title, "url": link, "ts": ts,
                            "source": name, "cat": use, "tags": tags[:4]})
        out.extend(got)
    except Exception as e:
        out.append({"__error__": "%s: %s" % (name, e)})


def _announce(name, url, out):
    """Exchange listing announcements - a new listing moves price hard."""
    import json as _j
    import urllib.request as _u
    try:
        d = _j.loads(_u.urlopen(_u.Request(url, headers=_UA), timeout=20).read())
        rows = []
        if name == "Binance":
            for a in (d.get("data") or {}).get("catalogs", [{}])[0].get("articles", [])[:15]:
                rows.append((a.get("title"), a.get("releaseDate")))
        elif name == "Upbit":
            for a in (d.get("data") or {}).get("notices", [])[:15]:
                rows.append((a.get("title"), a.get("listed_at")))
        elif name == "Bybit":
            for a in ((d.get("result") or {}).get("list") or [])[:15]:
                rows.append((a.get("title"), a.get("dateTimestamp")))
        for title, when in rows:
            if not title:
                continue
            ts = None
            if isinstance(when, (int, float)):
                ts = when / 1000.0 if when > 1e11 else float(when)
            elif isinstance(when, str):
                try:
                    import datetime as _d
                    ts = _d.datetime.fromisoformat(
                        when.replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass
            rows_out = {"title": title.strip(), "url": "", "ts": ts,
                        "source": name, "cat": "MARKETS"}
            out.append(rows_out)
    except Exception as e:
        out.append({"__error__": "%s: %s" % (name, e)})


def _news_all():
    """Every source in parallel, merged newest-first. Cached 120s."""
    import time as _t
    import threading as _th
    if _t.time() - _news["t"] < 120 and _news["data"] is not None:
        return _news["data"]
    bag, threads = [], []
    for nm, u, c in _FEEDS:
        th = _th.Thread(target=_rss, args=(nm, u, c, bag), daemon=True)
        th.start()
        threads.append(th)
    for nm, u in _ANNOUNCE:
        th = _th.Thread(target=_announce, args=(nm, u, bag), daemon=True)
        th.start()
        threads.append(th)
    for th in threads:
        th.join(timeout=22)
    errors = [b["__error__"] for b in bag if "__error__" in b]
    items = [b for b in bag if "__error__" not in b]
    # de-duplicate: the same story is often syndicated under the same headline
    seen, uniq = set(), []
    for it in sorted(items, key=lambda x: x.get("ts") or 0, reverse=True):
        k = (it["title"] or "").lower()[:90]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    per = {}
    for it in items:
        src = it["source"]
        d0 = per.setdefault(src, {"n": 0, "newest_ts": None})
        d0["n"] += 1
        if it.get("ts") and (d0["newest_ts"] is None or it["ts"] > d0["newest_ts"]):
            d0["newest_ts"] = it["ts"]
    for src, d0 in per.items():
        d0["age_h"] = (round((_t.time() - d0["newest_ts"]) / 3600, 1)
                       if d0["newest_ts"] else None)
    expected = [f[0] for f in _FEEDS] + [a[0] for a in _ANNOUNCE]
    silent = [s2 for s2 in expected if per.get(s2, {}).get("n", 0) == 0]
    out = {"items": uniq[:120], "n": len(uniq),
           "per_source": per, "silent_sources": silent, "errors": errors,
           "sources_live": len(expected) - len(silent), "sources_total": len(expected)}
    _news["data"] = out
    _news["t"] = _t.time()
    return out


# ------------------------------------------------------- portfolio (READ ONLY)
# SAFETY: every call below is a READ. Hyperliquid's /info and Lighter's GET
# endpoints cannot place, cancel, transfer or withdraw anything. There is no
# signing key, no /exchange call and no sendTx anywhere in this file.
_PF_TF = {"1D": "day", "1W": "week", "1M": "month", "ALL": "allTime"}
# Measured against the live API 2026-08-28: Lighter answers /pnl at 1h
# resolution only for windows up to 9 days; 10 days returns HTTP 400.
_LT_1H_MAX_DAYS = 9
_LT_IN = ("inflow", "spot_inflow", "staking_inflow", "pool_inflow")
_LT_OUT = ("outflow", "spot_outflow", "staking_outflow", "pool_outflow")
_LT_PNL = ("trade_pnl", "trade_spot_pnl", "pool_pnl", "staking_pnl")


def _lt_sum(row, keys):
    return sum(float(row.get(k) or 0) for k in keys)
# How far back each chip actually looks, in days. ALL is deliberately large
# so the baseline lookup below never finds a row before the window start.
_TF_WINDOW_DAYS = {"1D": 1, "1W": 7, "1M": 30, "ALL": 3650}
_pf = {}



# ---------------------------------------------------------------- candles --
# Real OHLCV from Hyperliquid's candleSnapshot. Every interval offered in the
# toolbar was confirmed live 2026-08-28 to return 200 candles with the full
# o/h/l/c/v set, so nothing here is synthesised.
_CANDLE_IV = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h",
              "4h": "4h", "D": "1d", "W": "1w", "M": "1M"}
_IV_MS = {"1m": 60000, "5m": 300000, "15m": 900000, "1h": 3600000,
          "4h": 14400000, "D": 86400000, "W": 604800000, "M": 2592000000}
_cd = {}


def _ema(vals, n):
    """EMA seeded with the SMA of the first n points (Wilder/TA convention)."""
    if len(vals) < n:
        return [None] * len(vals)
    out = [None] * (n - 1)
    seed = sum(vals[:n]) / n
    out.append(seed)
    k = 2.0 / (n + 1)
    prev = seed
    for v in vals[n:]:
        prev = v * k + prev * (1 - k)
        out.append(prev)
    return out


def _rsi(closes, n=14):
    """Wilder's RSI - smoothed averages, not a rolling simple mean."""
    if len(closes) <= n:
        return [None] * len(closes)
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    out = [None] * n
    ag = sum(gains[:n]) / n
    al = sum(losses[:n]) / n
    def _val(ag, al):
        if al == 0:
            return 100.0 if ag else 50.0
        return 100.0 - 100.0 / (1.0 + ag / al)
    out.append(_val(ag, al))
    for i in range(n, len(gains)):
        ag = (ag * (n - 1) + gains[i]) / n
        al = (al * (n - 1) + losses[i]) / n
        out.append(_val(ag, al))
    return out


def _macd(closes, fast=12, slow=26, sig=9):
    ef, es = _ema(closes, fast), _ema(closes, slow)
    line = [(a - b) if (a is not None and b is not None) else None
            for a, b in zip(ef, es)]
    solid = [v for v in line if v is not None]
    sg_solid = _ema(solid, sig)
    sg, k = [], 0
    for v in line:
        if v is None:
            sg.append(None)
        else:
            sg.append(sg_solid[k]); k += 1
    hist = [(a - b) if (a is not None and b is not None) else None
            for a, b in zip(line, sg)]
    return line, sg, hist


def _candles(coin="BTC", tf="15m", n=200):
    import time as _t
    tf = tf if tf in _CANDLE_IV else "15m"
    coin = (coin or "BTC").upper()[:12]
    n = max(40, min(400, int(n)))
    key = (coin, tf, n)
    slot = _cd.get(key)
    ttl = 8 if tf in ("1m", "5m") else 25
    if slot and _t.time() - slot[0] < ttl:
        return slot[1]
    warm = 60                      # > MACD's 26+9 and RSI's 14
    ms = int(_t.time() * 1000)
    raw = _hl_info({"type": "candleSnapshot",
                    "req": {"coin": coin, "interval": _CANDLE_IV[tf],
                            "startTime": ms - _IV_MS[tf] * (n + warm + 5),
                            "endTime": ms}})
    rows = [{"t": int(k["t"]), "o": float(k["o"]), "h": float(k["h"]),
             "l": float(k["l"]), "c": float(k["c"]), "v": float(k["v"])}
            for k in raw]
    rows.sort(key=lambda r: r["t"])
    rows = rows[-(n + warm):]
    closes = [r["c"] for r in rows]
    line, sg, hist = _macd(closes)
    rsi = _rsi(closes)
    cut = max(0, len(rows) - n)          # drop the warm-up, keep the window
    rows = rows[cut:]
    out = {"coin": coin, "tf": tf, "candles": rows,
           "rsi": rsi[cut:], "macd": line[cut:], "signal": sg[cut:],
           "hist": hist[cut:], "n": len(rows), "warmup_used": cut}
    if rows:
        last, first = rows[-1], rows[0]
        out["last"] = last
        out["chg"] = last["c"] - last["o"]
        out["chg_pct"] = (out["chg"] / last["o"] * 100) if last["o"] else 0.0
        out["range_chg_pct"] = ((last["c"] - first["o"]) / first["o"] * 100
                                if first["o"] else 0.0)
    _cd[key] = (_t.time(), out)
    return out


# -------------------------------------------------------------- watchlist --
# Real 24h price / change / volume for every listed Hyperliquid perp, from
# metaAndAssetCtxs (232 markets live 2026-08-28). There is no user-defined
# watchlist yet, so the default list is the top markets BY REAL 24H VOLUME
# rather than a hardcoded ticker set that might not even be listed.
# Named _mkt_watchlist to avoid the paper-desk's own _watchlist().
_wl = {}


def _mkt_watchlist(n=12, movers=6):
    import time as _t
    slot = _wl.get((n, movers))
    if slot and _t.time() - slot[0] < 15:
        return slot[1]
    meta = _hl_info({"type": "metaAndAssetCtxs"})
    universe, ctxs = meta[0].get("universe", []), meta[1]
    rows = []
    for u, c in zip(universe, ctxs):
        if u.get("isDelisted"):
            continue
        try:
            px = float(c.get("markPx") or 0)
            prev = float(c.get("prevDayPx") or 0)
            vol = float(c.get("dayNtlVlm") or 0)
        except (TypeError, ValueError):
            continue
        if px <= 0 or prev <= 0:
            continue
        rows.append({"coin": u.get("name"), "px": px,
                     "chg": (px - prev) / prev * 100.0, "vol": vol})
    by_vol = sorted(rows, key=lambda r: -r["vol"])
    by_chg = sorted(rows, key=lambda r: -r["chg"])
    out = {"items": by_vol[:n], "gainers": by_chg[:movers],
           "losers": by_chg[::-1][:movers], "n_markets": len(rows),
           "source": "hyperliquid metaAndAssetCtxs",
           "ranked_by": "24h notional volume"}
    _wl[(n, movers)] = (_t.time(), out)
    return out


# ------------------------------------------------------- book + funding ----
# Both read straight from Hyperliquid. l2Book returns 20 levels a side with
# px / sz / n; predictedFundings carries the next funding timestamp per venue
# (HlPerp settles hourly). Nothing here is synthesised.
_ob = {}
_fr = {}


def _l2book(coin="BTC", depth=8):
    import time as _t
    coin = (coin or "BTC").upper()[:12]
    depth = max(3, min(20, int(depth)))
    slot = _ob.get((coin, depth))
    if slot and _t.time() - slot[0] < 2:
        return slot[1]
    b = _hl_info({"type": "l2Book", "coin": coin})
    lv = b.get("levels") or [[], []]
    def side(rows, reverse):
        out, run = [], 0.0
        for r in rows[:depth]:
            sz = float(r.get("sz") or 0)
            run += sz
            out.append({"px": float(r.get("px") or 0), "sz": sz,
                        "total": run, "n": int(r.get("n") or 0)})
        return out[::-1] if reverse else out
    bids = side(lv[0], False)
    asks = side(lv[1], False)
    best_bid = bids[0]["px"] if bids else None
    best_ask = asks[0]["px"] if asks else None
    out = {"coin": coin, "bids": bids, "asks": asks,
           "time": b.get("time"),
           "bid": best_bid, "ask": best_ask,
           "mid": ((best_bid + best_ask) / 2) if (best_bid and best_ask) else None,
           "spread": ((best_ask - best_bid) if (best_bid and best_ask) else None)}
    if out["spread"] is not None and out["mid"]:
        out["spread_bps"] = out["spread"] / out["mid"] * 10000.0
    mx = max([r["total"] for r in bids + asks] or [0])
    out["max_total"] = mx
    _ob[(coin, depth)] = (_t.time(), out)
    return out


def _funding(n=8):
    import time as _t
    slot = _fr.get(n)
    if slot and _t.time() - slot[0] < 20:
        return slot[1]
    meta = _hl_info({"type": "metaAndAssetCtxs"})
    universe, ctxs = meta[0].get("universe", []), meta[1]
    nxt = {}
    try:
        for name, venues in _hl_info({"type": "predictedFundings"}):
            for vname, v in venues:
                if vname == "HlPerp" and v:
                    nxt[name] = {"next_ms": v.get("nextFundingTime"),
                                 "hours": v.get("fundingIntervalHours")}
                    break
    except Exception as e:
        nxt = {}
    rows = []
    for u, c in zip(universe, ctxs):
        if u.get("isDelisted"):
            continue
        try:
            vol = float(c.get("dayNtlVlm") or 0)
            f = float(c.get("funding") or 0)
        except (TypeError, ValueError):
            continue
        if vol <= 0:
            continue
        e = nxt.get(u.get("name")) or {}
        anchor = e.get("next_ms")
        iv_h = e.get("hours") or 1
        nxt_ms = anchor
        if anchor:
            step = int(iv_h) * 3600000
            now_ms = int(_t.time() * 1000)
            if nxt_ms <= now_ms and step > 0:
                # roll forward whole intervals from the published anchor
                nxt_ms = anchor + step * (((now_ms - anchor) // step) + 1)
        rows.append({"coin": u.get("name"), "rate": f * 100.0,
                     "apr": f * 24 * 365 * 100.0, "vol": vol,
                     "oi": float(c.get("openInterest") or 0),
                     "next_ms": nxt_ms,
                     "next_ms_raw": anchor,
                     "next_stale": bool(anchor and nxt_ms != anchor),
                     "interval_h": iv_h})
    rows.sort(key=lambda r: -r["vol"])
    out = {"items": rows[:n], "n_markets": len(rows),
           "server_ms": int(_t.time() * 1000),
           "ranked_by": "24h notional volume"}
    _fr[n] = (_t.time(), out)
    return out


# ------------------------------------------------------------ correlation --
# Pearson correlation of DAILY LOG RETURNS over the trailing window, computed
# from real candleSnapshot data - one request per coin, cached 10 min because
# a daily correlation cannot move faster than that.
_cm = {}


def _corr(n=7, days=30):
    import time as _t
    import math as _m
    key = (n, days)
    slot = _cm.get(key)
    if slot and _t.time() - slot[0] < 600:
        return slot[1]
    coins = [r["coin"] for r in _mkt_watchlist(n)["items"]][:n]
    ms = int(_t.time() * 1000)
    series = {}
    for c in coins:
        try:
            raw = _hl_info({"type": "candleSnapshot",
                            "req": {"coin": c, "interval": "1d",
                                    "startTime": ms - 86400000 * (days + 3),
                                    "endTime": ms}})
            rows = sorted(raw, key=lambda k: int(k["t"]))
            series[c] = {int(k["t"]): float(k["c"]) for k in rows}
        except Exception as e:
            out_err = "corr %s: %s" % (c, e)
            series[c] = {}
    # only bars every coin has, so every pair is measured on the same days
    common = None
    for c in coins:
        ks = set(series[c].keys())
        common = ks if common is None else (common & ks)
    common = sorted(common or [])
    rets = {}
    for c in coins:
        px = [series[c][t] for t in common]
        rets[c] = [_m.log(px[i] / px[i - 1]) for i in range(1, len(px))
                   if px[i] > 0 and px[i - 1] > 0]
    m = min([len(v) for v in rets.values()] or [0])
    for c in coins:
        rets[c] = rets[c][-m:]

    def pearson(a, b):
        k = len(a)
        if k < 3:
            return None
        ma, mb = sum(a) / k, sum(b) / k
        va = sum((x - ma) ** 2 for x in a)
        vb = sum((y - mb) ** 2 for y in b)
        if va <= 0 or vb <= 0:
            return None
        cov = sum((a[i] - ma) * (b[i] - mb) for i in range(k))
        return cov / _m.sqrt(va * vb)

    matrix = [[(1.0 if i == j else pearson(rets[a], rets[b]))
               for j, b in enumerate(coins)] for i, a in enumerate(coins)]
    out = {"coins": coins, "matrix": matrix, "days": days,
           "samples": m, "window_bars": len(common)}
    _cm[key] = (_t.time(), out)
    return out


# ---------------------------------------------------------------- health --
# Each row below is a REAL probe of an upstream this dashboard depends on. A
# dead endpoint, a timeout or a bad payload flips the row to ERR and records
# why - this is deliberately a check that can fail, not a row of green ticks.
def _health():
    import time as _t
    rows = []

    def probe(name, fn):
        t0 = _t.time()
        try:
            detail = fn()
            rows.append({"name": name, "ok": True,
                         "ms": int((_t.time() - t0) * 1000), "detail": detail})
        except Exception as e:
            rows.append({"name": name, "ok": False,
                         "ms": int((_t.time() - t0) * 1000),
                         "detail": str(e)[:70]})

    def hl_info():
        m = _hl_info({"type": "metaAndAssetCtxs"})
        n = len(m[0].get("universe", []))
        if n < 1:
            raise RuntimeError("empty universe")
        return "%d markets" % n

    def hl_book():
        b = _l2book("BTC", 3)
        if not b.get("bids") or not b.get("asks"):
            raise RuntimeError("empty book")
        if b["bid"] >= b["ask"]:
            raise RuntimeError("crossed book")
        return "%.1f bps" % b.get("spread_bps", 0)

    def hl_candles():
        c = _candles("BTC", "15m", 40)
        if c["n"] < 20:
            raise RuntimeError("only %d candles" % c["n"])
        return "%d bars" % c["n"]

    def lighter_api():
        a = _lighter_get("/accountsByL1Address?l1_address=%s"
                         % _env("LIGHTER_L1_ADDRESS"))
        subs = a.get("sub_accounts") or a.get("accounts") or []
        if not subs:
            raise RuntimeError("no sub-accounts")
        return "%d account(s)" % len(subs)

    def portfolio():
        pf = _portfolio("1D")
        if pf.get("net_worth") is None:
            raise RuntimeError("no net worth")
        if pf.get("reconciled") is False:
            raise RuntimeError("reconcile gap %.3f" % (pf.get("reconcile_gap") or 0))
        return "$%.2f" % pf["net_worth"]

    def news():
        n = _news_all()
        k = len(n.get("items") or [])
        if k < 5:
            raise RuntimeError("only %d items" % k)
        return "%d items" % k

    probe("HYPERLIQUID API", hl_info)
    probe("ORDER BOOK", hl_book)
    probe("MARKET DATA", hl_candles)
    probe("LIGHTER API", lighter_api)
    probe("PORTFOLIO", portfolio)
    probe("NEWS FEED", news)
    return {"rows": rows, "ok": all(r["ok"] for r in rows),
            "checked_ms": int(_t.time() * 1000)}


# ---------------------------------------------------------------- risk -----
# Historical-simulation risk on the REAL open book. Daily log returns per coin
# come from candleSnapshot; the portfolio P&L series is the signed notional of
# each position times that coin's return on the same day. No parametric
# assumption and no invented numbers - if a coin has no history it is dropped
# and said so in `skipped`.
_rk = {}
_VAR_LIMIT_PCT = 5.0     # house limit: a 1-day 95% VaR worth 5% of equity


def _risk_overview(days=90):
    import time as _t
    import math as _m
    slot = _rk.get(days)
    if slot and _t.time() - slot[0] < 120:
        return slot[1]
    pf = _portfolio("1D")
    eq = pf.get("net_worth") or 0.0
    live = [q for q in pf.get("positions", [])
            if not q.get("is_cash") and q.get("size")]
    out = {"equity": eq, "n_positions": len(live), "errors": [], "skipped": []}

    gross = 0.0
    legs = []
    for q in live:
        notional = abs(float(q.get("value") or 0))
        if notional <= 0:
            continue
        sign = 1.0 if q.get("side") == "LONG" else -1.0
        gross += notional
        legs.append({"coin": q["coin"], "venue": q["venue"], "notional": notional,
                     "signed": sign * notional, "side": q.get("side"),
                     "mark": q.get("mark"), "liq": q.get("liq")})
    out["gross_notional"] = gross
    out["leverage"] = (gross / eq) if eq else None
    # Herfindahl concentration: 1/n when evenly spread, 1.0 when all in one
    out["concentration"] = (sum((l["notional"] / gross) ** 2 for l in legs)
                            if gross else None)

    ms = int(_t.time() * 1000)
    rets = {}
    for coin in sorted({l["coin"] for l in legs}):
        try:
            raw = _hl_info({"type": "candleSnapshot",
                            "req": {"coin": coin, "interval": "1d",
                                    "startTime": ms - 86400000 * (days + 3),
                                    "endTime": ms}})
            px = [float(k["c"]) for k in sorted(raw, key=lambda k: int(k["t"]))]
            rets[coin] = [_m.log(px[i] / px[i - 1]) for i in range(1, len(px))
                          if px[i] > 0 and px[i - 1] > 0]
        except Exception as e:
            out["skipped"].append("%s: %s" % (coin, str(e)[:40]))
    usable = [c for c in rets if len(rets[c]) >= 20]
    for l in legs:
        if l["coin"] not in usable:
            out["skipped"].append("%s: no usable history" % l["coin"])
    m = min([len(rets[c]) for c in usable] or [0])
    pnl = []
    if m >= 20:
        for t in range(-m, 0):
            pnl.append(sum(l["signed"] * rets[l["coin"]][t]
                           for l in legs if l["coin"] in usable))
    out["samples"] = len(pnl)
    if len(pnl) >= 20:
        srt = sorted(pnl)
        k = max(0, int(_m.floor(0.05 * len(srt))))
        var = -srt[k]
        tail = srt[:k + 1]
        out["var95"] = var
        out["es95"] = -(sum(tail) / len(tail)) if tail else None
        out["var95_pct"] = (var / eq * 100) if eq else None
        limit = eq * (_VAR_LIMIT_PCT / 100.0)
        out["var_limit"] = limit
        out["var_limit_pct"] = _VAR_LIMIT_PCT
        out["var_usage_pct"] = (var / limit * 100) if limit else None
        out["pnl_series"] = pnl[-40:]
        win = 20
        vs, es_s = [], []
        for e in range(win, len(srt if False else pnl) + 1):
            w = sorted(pnl[e - win:e])
            kk = max(0, int(_m.floor(0.05 * len(w))))
            vs.append(-w[kk])
            tl = w[:kk + 1]
            es_s.append(-(sum(tl) / len(tl)) if tl else None)
        out["var_series"] = vs[-40:]
        # summary stats over the same real daily P&L series the VaR uses
        w = pnl[-30:] if len(pnl) >= 30 else pnl
        if len(w) >= 5 and eq:
            rr = [v / eq for v in w]
            mu = sum(rr) / len(rr)
            sd = (sum((x - mu) ** 2 for x in rr) / (len(rr) - 1)) ** 0.5
            out["ret_30d_pct"] = (sum(w) / eq) * 100
            out["vol_30d_pct"] = sd * (365 ** 0.5) * 100
            out["sharpe_30d"] = (mu / sd * (365 ** 0.5)) if sd else None
            out["win_rate_30d"] = sum(1 for v in w if v > 0) / len(w) * 100
            peak = 0.0; cum = 0.0; dd = 0.0
            for v in w:
                cum += v
                peak = max(peak, cum)
                dd = min(dd, cum - peak)
            out["max_dd_30d_pct"] = (dd / eq) * 100
            out["days_30d"] = len(w)
        out["es_series"] = [v for v in es_s[-40:]]
    else:
        for k2 in ("var95", "es95", "var95_pct", "var_usage_pct"):
            out[k2] = None
        out["pnl_series"] = []
        out["var_series"] = []
        out["es_series"] = []

    # distance to liquidation, and the map the panel draws
    rows = []
    for l in legs:
        mark, liq = l.get("mark"), l.get("liq")
        if not mark or not liq or liq <= 0:
            continue
        dist = (liq - mark) / mark * 100.0        # signed: - below, + above
        rows.append({"coin": l["coin"], "venue": l["venue"], "side": l["side"],
                     "notional": l["notional"], "mark": mark, "liq": liq,
                     "dist_pct": dist, "abs_pct": abs(dist)})
    rows.sort(key=lambda r: r["abs_pct"])
    out["liq_levels"] = rows
    downs = sorted([r for r in rows if r["dist_pct"] < 0],
                   key=lambda r: -r["dist_pct"])
    ups = sorted([r for r in rows if r["dist_pct"] > 0],
                 key=lambda r: r["dist_pct"])
    prof_d, run = [], 0.0
    for r in downs:
        prof_d.append([r["dist_pct"], run])
        run += r["notional"]
        prof_d.append([r["dist_pct"], run])
    prof_u, run = [], 0.0
    for r in ups:
        prof_u.append([r["dist_pct"], run])
        run += r["notional"]
        prof_u.append([r["dist_pct"], run])
    out["liq_profile_down"] = prof_d
    out["liq_profile_up"] = prof_u
    out["liq_at_risk_down"] = sum(r["notional"] for r in downs)
    out["liq_at_risk_up"] = sum(r["notional"] for r in ups)
    out["nearest_liq_pct"] = rows[0]["abs_pct"] if rows else None
    nearest = out["nearest_liq_pct"]
    # stated policy, not measured: <10% HIGH, 10-25% MEDIUM, else LOW
    out["liq_risk"] = (None if nearest is None
                       else "HIGH" if nearest < 10
                       else "MEDIUM" if nearest < 25 else "LOW")
    out["liq_risk_policy"] = "HIGH <10%, MEDIUM <25%, else LOW"
    _rk[days] = (_t.time(), out)
    return out


# ------------------------------------------------------------ macro regime --
# A real, reproducible regime read from real daily BTC candles plus live
# breadth across every Hyperliquid market. The score is stated openly so it is
# auditable rather than a black box:
#     trend  = close vs its own 50-day SMA, squashed with tanh
#     vol    = 20-day realised vol as a percentile of the trailing year
#     score  = 100 * (0.60*trend + 0.40*(1 - vol_percentile))
# then smoothed over 5 days. >=60 RISK-ON, <=40 RISK-OFF, else NEUTRAL.
_rg = {}


def _macro_regime(days=365):
    import time as _t
    import math as _m
    slot = _rg.get(days)
    if slot and _t.time() - slot[0] < 300:
        return slot[1]
    ms = int(_t.time() * 1000)
    raw = _hl_info({"type": "candleSnapshot",
                    "req": {"coin": "BTC", "interval": "1d",
                            "startTime": ms - 86400000 * (days + 70),
                            "endTime": ms}})
    rows = sorted(raw, key=lambda k: int(k["t"]))
    px = [float(k["c"]) for k in rows]
    ts = [int(k["t"]) for k in rows]
    if len(px) < 80:
        return {"error": "only %d daily candles" % len(px)}
    rets = [_m.log(px[i] / px[i - 1]) for i in range(1, len(px))]
    out_pts = []
    vols = []
    for i in range(50, len(px)):
        sma = sum(px[i - 50:i]) / 50.0
        trend = _m.tanh(3.0 * (px[i] - sma) / sma)          # -1..1
        w = rets[max(0, i - 20):i]
        mu = sum(w) / len(w)
        vol = (sum((x - mu) ** 2 for x in w) / max(1, len(w) - 1)) ** 0.5
        vols.append(vol)
        rank = sorted(vols[-252:])
        pct = rank.index(vol) / max(1, len(rank) - 1)
        score = 100.0 * (0.60 * ((trend + 1) / 2) + 0.40 * (1 - pct))
        out_pts.append([ts[i], score])
    # 5-day smoothing
    sm = []
    for i in range(len(out_pts)):
        w = [v for _, v in out_pts[max(0, i - 4):i + 1]]
        sm.append([out_pts[i][0], sum(w) / len(w)])
    cur = sm[-1][1]
    label = "RISK-ON" if cur >= 60 else ("RISK-OFF" if cur <= 40 else "NEUTRAL")
    # how long the current label has held
    held = 0
    for _, v in reversed(sm):
        lb = "RISK-ON" if v >= 60 else ("RISK-OFF" if v <= 40 else "NEUTRAL")
        if lb != label:
            break
        held += 1
    # live breadth across every market
    up = tot = 0
    try:
        meta = _hl_info({"type": "metaAndAssetCtxs"})
        for u, c in zip(meta[0].get("universe", []), meta[1]):
            if u.get("isDelisted"):
                continue
            p0 = float(c.get("prevDayPx") or 0)
            p1 = float(c.get("markPx") or 0)
            if p0 > 0 and p1 > 0:
                tot += 1
                if p1 > p0:
                    up += 1
    except Exception:
        pass
    # derived states for the Regime Command panel (all from the real engine
    # above): volatility from the 20d realised-vol percentile, liquidity from
    # live market breadth, risk appetite = the composite regime score.
    vol_pct = pct                                   # latest 20d vol percentile
    trend_now = trend                               # latest trend -1..1
    vstate = ("LOW" if vol_pct < 0.34 else
              ("HIGH" if vol_pct > 0.66 else "MODERATE"))
    bp = (up / tot) if tot else 0.5
    lstate = ("AMPLE" if bp >= 0.55 else ("TIGHT" if bp <= 0.45 else "BALANCED"))
    out = {"label": label, "confidence": cur, "series": sm[-days:],
           "held_days": held, "breadth_up": up, "breadth_total": tot,
           "breadth_pct": (up / tot * 100) if tot else None,
           "since_ms": sm[-held][0] if held and held <= len(sm) else None,
           "vol_pct": vol_pct, "trend": trend_now,
           "volatility_state": vstate, "liquidity_state": lstate,
           "risk_appetite": int(round(cur)),
           "formula": "0.60*trend(tanh vs 50d SMA) + 0.40*(1 - 20d vol pctile)"}
    _rg[days] = (_t.time(), out)
    return out


_lv = {"t": 0.0, "data": None}


def _liqvol():
    """Liquidity & Volatility Analysis - every value live where a free feed
    exists (TGA, stablecoin supply, VIX, BTC/SPX realised vol, Deribit DVOL);
    Global M2 and exchange reserves have no free feed and are flagged."""
    import time as _t, json as _j, urllib.request as _u, math as _m
    if _lv["data"] and _t.time() - _lv["t"] < 300:
        return _lv["data"]
    ms = int(_t.time() * 1000)

    def get(u, hdr=None):
        return _j.loads(_u.urlopen(_u.Request(
            u, headers=hdr or {"User-Agent": "Mozilla/5.0"}), timeout=20).read())

    def rv(closes, ann):
        r = [_m.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        if len(r) < 2:
            return None
        mu = sum(r) / len(r)
        sd = (sum((x - mu) ** 2 for x in r) / (len(r) - 1)) ** 0.5
        return sd * (ann ** 0.5) * 100

    out = {"errors": []}
    # US TGA closing balance (real, US Treasury Fiscal Data)
    try:
        u = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1"
             "/accounting/dts/operating_cash_balance?filter=account_type:eq:"
             "Treasury%20General%20Account%20(TGA)%20Closing%20Balance"
             "&sort=-record_date&page[size]=1")
        r = (get(u).get("data") or [{}])[0]
        bal = float(r.get("open_today_bal") or r.get("close_today_bal") or 0)
        out["tga_b"] = bal / 1000.0
        out["tga_date"] = r.get("record_date")
    except Exception as e:
        out["errors"].append("tga: %s" % str(e)[:40])
    # Stablecoin supply (real, DefiLlama)
    try:
        d = get("https://stablecoins.llama.fi/stablecoins?includePrices=false")
        tot = sum(float((s.get("circulating") or {}).get("peggedUSD") or 0)
                  for s in d.get("peggedAssets", []))
        out["stable_b"] = tot / 1e9
    except Exception as e:
        out["errors"].append("stable: %s" % str(e)[:40])
    # VIX (real, Yahoo)
    try:
        r = get("https://query1.finance.yahoo.com/v8/finance/chart/"
                "%5EVIX?interval=1d&range=6mo")["chart"]["result"][0]
        ts = r["timestamp"]
        q = r["indicators"]["quote"][0]["close"]
        ser = [[int(ts[i]) * 1000, float(q[i])]
               for i in range(len(q)) if q[i] is not None]
        cl = [p[1] for p in ser]
        out["vix"] = cl[-1]
        out["vix_chg"] = (cl[-1] / cl[-2] - 1) * 100 if len(cl) > 1 else 0.0
        out["vix_series"] = ser
    except Exception as e:
        out["errors"].append("vix: %s" % str(e)[:40])
    # SPX 30D realised vol (real, Yahoo)
    try:
        r = get("https://query1.finance.yahoo.com/v8/finance/chart/"
                "%5EGSPC?interval=1d&range=2mo")["chart"]["result"][0]
        cl = [c for c in r["indicators"]["quote"][0]["close"] if c][-31:]
        out["spx_rv"] = rv(cl, 252)
    except Exception as e:
        out["errors"].append("spx_rv: %s" % str(e)[:40])
    # BTC 30D realised vol (real, HL candles)
    try:
        raw = _hl_info({"type": "candleSnapshot",
                        "req": {"coin": "BTC", "interval": "1d",
                                "startTime": ms - 86400000 * 40, "endTime": ms}})
        px = [float(k["c"]) for k in sorted(raw, key=lambda k: int(k["t"]))][-31:]
        out["btc_rv"] = rv(px, 365)
        if px:
            out["btc_dd"] = (px[-1] / max(px) - 1) * 100.0   # drawdown from 30d high
    except Exception as e:
        out["errors"].append("btc_rv: %s" % str(e)[:40])
    # Deribit DVOL - BTC implied-vol index (real): last value + 180d chart series
    try:
        d = get("https://www.deribit.com/api/v2/public/get_volatility_index_data"
                "?currency=BTC&start_timestamp=%d&end_timestamp=%d&resolution=43200"
                % (ms - 86400000 * 180, ms))
        dv = d.get("result", {}).get("data", [])
        if dv:
            out["dvol"] = float(dv[-1][4] if len(dv[-1]) > 4 else dv[-1][-1])
            out["dvol_series"] = [[int(x[0]), float(x[4] if len(x) > 4 else x[-1])]
                                  for x in dv]
    except Exception as e:
        out["errors"].append("dvol: %s" % str(e)[:40])
    # composite stress score (0-100) from real inputs: equity vol + crypto vol
    # + BTC drawdown. Higher = more stressed.
    try:
        comp = []
        if out.get("vix") is not None:
            comp.append(min(1.0, max(0.0, (out["vix"] - 12) / 28)))     # 12..40
        if out.get("dvol") is not None:
            comp.append(min(1.0, max(0.0, (out["dvol"] - 25) / 50)))    # 25..75
        if out.get("btc_dd") is not None:
            comp.append(min(1.0, max(0.0, -out["btc_dd"] / 25)))        # 0..-25%
        if comp:
            out["stress_score"] = int(round(100 * sum(comp) / len(comp)))
    except Exception:
        pass
    # no free feed for these two - flagged, never faked
    out["m2_note"] = "no free Global M2 feed"
    out["reserves_note"] = "exchange reserves need a paid feed"
    _lv["data"] = out
    _lv["t"] = _t.time()
    return out


_pp = {"t": 0.0, "data": None}


_desk_cache = {}


def _desk(run_id=None):
    """The ChatGPT desk: every run in data/desk_calls (calls, research, settlements, reviews).
    ?run=<stamp> returns one run with a fresh live settlement (Hyperliquid candles), cached 60 s."""
    import json as _j, time as _t, glob as _g, os as _os, io
    files = sorted(_g.glob(str(ROOT / "data" / "desk_calls" / "*.json")), reverse=True)
    if run_id is None:
        rows, closed, equity, tokens_today = [], [], [], 0
        today = _t.strftime("%Y-%m-%d", _t.gmtime())
        for f in files:
            try:
                r = _j.loads(io.open(f, encoding="utf-8").read())
            except Exception:
                continue
            calls = ((r.get("calls") or {}).get("data") or {}).get("trades") or []
            last = (r.get("settlements") or [None])[-1]
            tr = (last or {}).get("trades", [])
            done = [t for t in tr if t.get("reason") not in (None, "open") and "error" not in t]
            rows.append({"stamp": r.get("stamp"), "when_utc": (r.get("packet") or {}).get("now_utc"), "n_trades": len(calls),
                         "with_research": r.get("with_research"), "with_manual": r.get("with_manual"),
                         "settled_at": (last or {}).get("settled_at"), "total_pnl_usd": (last or {}).get("total_pnl_usd"),
                         "open": sum(1 for t in tr if t.get("reason") == "open") if last else None,
                         "closed": len(done), "wins": sum(1 for t in done if (t.get("pnl_usd_on_100_margin") or 0) > 0),
                         "reviewed": bool(r.get("reviews"))})
            closed += done
            for t in done:
                if t.get("closed_ms"):
                    equity.append((int(t["closed_ms"]), float(t.get("pnl_usd_on_100_margin") or 0)))
            if str(r.get("stamp", ""))[:8] == today.replace("-", ""):
                for k in ("asked", "research", "calls"):
                    u = ((r.get(k) or {}).get("usage") or {}) if isinstance(r.get(k), dict) else {}
                    tokens_today += int(u.get("input_tokens") or 0) + int(u.get("output_tokens") or 0)
                for rv in r.get("reviews") or []:
                    u = ((rv.get("result") or {}).get("usage") or {})
                    tokens_today += int(u.get("input_tokens") or 0) + int(u.get("output_tokens") or 0)
        equity.sort()
        cum, curve = 0.0, []
        for ts, v in equity:
            cum += v; curve.append([ts, round(cum, 2)])
        rs = [t.get("r_multiple") for t in closed if t.get("r_multiple") is not None]
        # loop status + next decision slot (New York 08:00 / 20:00)
        loop = {}
        try:
            lg = (ROOT / "data" / "desk_loop.log").read_text(encoding="utf-8").strip().splitlines()
            loop["last"] = lg[-1] if lg else None
            from datetime import datetime as _dt, timezone as _tz
            ts = _dt.strptime(lg[-1][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=_tz.utc) if lg else None
            loop["age_min"] = round((_dt.now(_tz.utc) - ts).total_seconds() / 60, 1) if ts else None
        except Exception:
            loop["last"] = None
        try:
            from datetime import datetime as _dt2, timedelta as _td
            from zoneinfo import ZoneInfo as _Z
            ny = _dt2.now(_Z("America/New_York"))
            cands = []
            for hh in (8, 20):
                for dd in (0, 1):
                    c = (ny + _td(days=dd)).replace(hour=hh, minute=0, second=0, microsecond=0)
                    if c > ny:
                        cands.append(c)
            nxt = min(cands)
            loop["next_call_ny"] = nxt.strftime("%a %H:%M"); loop["next_call_min"] = round((nxt - ny).total_seconds() / 60)
        except Exception:
            pass
        summary = {"n_runs": len(rows), "closed": len(closed), "wins": sum(1 for t in closed if (t.get("pnl_usd_on_100_margin") or 0) > 0),
                   "hit_rate": round(sum(1 for t in closed if (t.get("pnl_usd_on_100_margin") or 0) > 0) / len(closed), 2) if closed else None,
                   "avg_r": round(sum(rs) / len(rs), 2) if rs else None,
                   "realised_pnl_usd": round(sum(float(t.get("pnl_usd_on_100_margin") or 0) for t in closed), 2),
                   "funding_usd": round(sum(float(t.get("funding_usd") or 0) for t in closed), 2),
                   "exits": {k: sum(1 for t in closed if t.get("reason") == k) for k in ("target", "stop", "time", "liquidated")},
                   "tokens_today": tokens_today, "equity_curve": curve, "loop": loop}
        return {"runs": rows, "summary": summary}
    f = str(ROOT / "data" / "desk_calls" / f"{run_id}.json")
    if not _os.path.exists(f):
        return {"error": "no such run"}
    r = _j.loads(io.open(f, encoding="utf-8").read())
    c = _desk_cache.get(run_id)
    if c and _t.time() - c["t"] < 60:
        r["live"] = c["live"]
    else:
        try:
            import sys as _sys
            if str(ROOT / "scripts") not in _sys.path:
                _sys.path.insert(0, str(ROOT / "scripts"))
            import desk_call as _dc
            live = _dc.settle(r)
        except Exception as e:  # noqa: BLE001
            live = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
        _desk_cache[run_id] = {"t": _t.time(), "live": live}
        r["live"] = live
    r.pop("packet_full", None)
    return r


def _papers():
    """Research Paper Digest - real recent quant-finance papers from arXiv
    (free API), newest first. Title + arXiv id + date, cached 1h."""
    import time as _t, urllib.request as _u, re as _re
    if _pp["data"] and _t.time() - _pp["t"] < 3600:
        return _pp["data"]
    out = {"items": [], "errors": []}
    try:
        u = ("http://export.arxiv.org/api/query?search_query="
             "cat:q-fin.TR+OR+cat:q-fin.PM+OR+cat:q-fin.ST+OR+cat:q-fin.CP"
             "&sortBy=submittedDate&sortOrder=descending&max_results=6")
        x = _u.urlopen(_u.Request(u, headers={"User-Agent": "Mozilla/5.0"}),
                       timeout=20).read().decode()
        for e in _re.findall(r"<entry>(.*?)</entry>", x, _re.S)[:5]:
            tm = _re.search(r"<title>(.*?)</title>", e, _re.S)
            im = _re.search(r"<id>https?://arxiv.org/abs/([^<]+)</id>", e)
            pm = _re.search(r"<published>([^<]+)</published>", e)
            if tm and im:
                aid = im.group(1)
                out["items"].append({
                    "title": " ".join(tm.group(1).split()),
                    "ref": "arXiv:" + aid.split("v")[0],
                    "published": pm.group(1)[:10] if pm else "",
                    "url": "https://arxiv.org/abs/" + aid})
    except Exception as ex:
        out["errors"].append("arxiv: %s" % str(ex)[:50])
    _pp["data"] = out
    _pp["t"] = _t.time()
    return out


_coin_cache = {}


# ---------------------------------------------------------------- QUANT LAB
_QL_TABLES = ["feat_ret", "feat_volat", "feat_trend", "feat_osc",
              "feat_bands", "feat_vol_flow", "feat_risk", "feat_candle"]


def _ql_store():
    """Read-only handle on the unified store (data/store.db)."""
    import sqlite3
    p = Path(__file__).resolve().parent.parent / "data" / "store.db"
    if not p.exists():
        return None
    c = sqlite3.connect("file:%s?mode=ro" % p, uri=True, timeout=20)
    c.row_factory = sqlite3.Row
    return c


def _ql_coins():
    """Coins that actually have computed features, most history first."""
    c = _ql_store()
    if c is None:
        return []
    try:
        return [dict(sym=r[0], bars=r[1]) for r in c.execute(
            "SELECT a.symbol, COUNT(*) FROM feat_ret f JOIN asset a ON a.id=f.asset_id "
            "GROUP BY a.symbol ORDER BY COUNT(*) DESC")]
    finally:
        c.close()


def _ql_snapshot(sym):
    """Every computed feature for one coin at its most recent bar."""
    c = _ql_store()
    if c is None:
        return {"error": "store.db not found"}
    try:
        row = c.execute("SELECT id FROM asset WHERE symbol=?", (sym.upper(),)).fetchone()
        if not row:
            return {"error": "unknown coin %s" % sym}
        aid = row[0]
        out, ts = {}, None
        for t in _QL_TABLES:
            try:
                r = c.execute("SELECT * FROM %s WHERE asset_id=? ORDER BY ts_ms DESC LIMIT 1"
                              % t, (aid,)).fetchone()
            except Exception:
                continue
            if not r:
                continue
            d = dict(r)
            ts = ts or d.get("ts_ms")
            d.pop("ts_ms", None)
            d.pop("asset_id", None)
            out[t.replace("feat_", "")] = {k: v for k, v in d.items() if v is not None}
        px = c.execute("SELECT o,h,l,c,v FROM ohlcv WHERE asset_id=? AND interval='1h' "
                       "ORDER BY ts_ms DESC LIMIT 1", (aid,)).fetchone()
        n = sum(len(v) for v in out.values())
        return {"coin": sym.upper(), "ts_ms": ts, "n_features": n,
                "price": (dict(px) if px else None), "groups": out}
    finally:
        c.close()


def _ql_series(sym, field, n=400):
    """One feature's recent history, for charting."""
    c = _ql_store()
    if c is None:
        return {"error": "store.db not found"}
    try:
        row = c.execute("SELECT id FROM asset WHERE symbol=?", (sym.upper(),)).fetchone()
        if not row:
            return {"error": "unknown coin"}
        aid = row[0]
        tbl = None
        for t in _QL_TABLES + ["ohlcv"]:
            cols = [x[1] for x in c.execute("PRAGMA table_info(%s)" % t)]
            if field in cols:
                tbl = t
                break
        if tbl is None:
            return {"error": "unknown field %s" % field}
        extra = " AND interval='1h'" if tbl == "ohlcv" else ""
        rows = list(c.execute(
            "SELECT ts_ms, %s FROM %s WHERE asset_id=?%s AND %s IS NOT NULL "
            "ORDER BY ts_ms DESC LIMIT ?" % (field, tbl, extra, field), (aid, int(n))))
        rows.reverse()
        return {"coin": sym.upper(), "field": field, "table": tbl,
                "points": [[r[0], r[1]] for r in rows]}
    finally:
        c.close()


def _ql_status():
    """Coverage: how much of the feature build is actually done."""
    c = _ql_store()
    if c is None:
        return {"error": "store.db not found"}
    try:
        out = {"tables": [], "ohlcv_rows": 0, "ohlcv_coins": 0}
        for t in _QL_TABLES:
            try:
                n = c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                k = c.execute("SELECT COUNT(DISTINCT asset_id) FROM %s" % t).fetchone()[0]
                cols = len([x for x in c.execute("PRAGMA table_info(%s)" % t)]) - 2
                out["tables"].append({"name": t.replace("feat_", ""), "rows": n,
                                      "coins": k, "features": cols})
            except Exception:
                pass
        r = c.execute("SELECT COUNT(*), COUNT(DISTINCT asset_id) FROM ohlcv").fetchone()
        out["ohlcv_rows"], out["ohlcv_coins"] = r[0], r[1]
        out["total_features"] = sum(t["features"] for t in out["tables"])
        return out
    finally:
        c.close()


def _coin(sym):
    """Coin-analysis header: real metrics for one coin. HL (price/vol/funding/
    OI + candles for beta & spark & score), CoinGecko (mkt cap/FDV/supply),
    HL order book (liquidity score). Quant score is a composite of real signals."""
    import time as _t, math as _m, statistics as _st3
    sym = (sym or "BTC").upper()
    slot = _coin_cache.get(sym)
    if slot and _t.time() - slot[0] < 30:
        return slot[1]
    ms = int(_t.time() * 1000)
    out = {"sym": sym, "errors": []}
    # --- HL: price, 24h change, HL volume, funding, OI
    try:
        meta = _hl_info({"type": "metaAndAssetCtxs"})
        for u, c in zip(meta[0].get("universe", []), meta[1]):
            if u.get("name") == sym:
                px = float(c.get("markPx") or 0)
                p0 = float(c.get("prevDayPx") or 0)
                out["price"] = px
                out["chg24h"] = ((px - p0) / p0 * 100) if p0 else 0.0
                out["vol24h_hl"] = float(c.get("dayNtlVlm") or 0)
                out["funding"] = float(c.get("funding") or 0)
                out["oi_usd"] = float(c.get("openInterest") or 0) * px
                break
    except Exception as e:
        out["errors"].append("hl: %s" % str(e)[:40])
    # --- CoinGecko: market cap, FDV, circulating supply, 24h volume
    try:
        cg = _cg_get("https://api.coingecko.com/api/v3/coins/markets"
                     "?vs_currency=usd&symbols=" + sym.lower(),
                     "coin_" + sym, ttl=120)
        if cg:
            m = max(cg, key=lambda x: x.get("market_cap") or 0)
            out["name"] = m.get("name")
            out["mkt_cap"] = m.get("market_cap")
            out["fdv"] = m.get("fully_diluted_valuation")
            out["circ_supply"] = m.get("circulating_supply")
            out["vol24h"] = m.get("total_volume")
            mc = m.get("market_cap")
            out["vol_mc"] = (m.get("total_volume") / mc * 100) if mc else None
    except Exception as e:
        out["errors"].append("cg: %s" % str(e)[:40])
    # --- candles: 30d beta vs BTC, RSI/trend for the score, hourly spark
    rsi = trend = rel = None
    try:
        def closes(coin, interval, days):
            raw = _hl_info({"type": "candleSnapshot",
                            "req": {"coin": coin, "interval": interval,
                                    "startTime": ms - 86400000 * days, "endTime": ms}})
            return [float(k["c"]) for k in sorted(raw, key=lambda k: int(k["t"]))]
        d = closes(sym, "1d", 45)
        b = closes("BTC", "1d", 45)
        if len(d) >= 31 and len(b) >= 31:
            n = min(len(d), len(b))
            dr = [d[-n + i] / d[-n + i - 1] - 1 for i in range(1, n)]
            br = [b[-n + i] / b[-n + i - 1] - 1 for i in range(1, n)]
            k = min(30, len(dr))
            dr, br = dr[-k:], br[-k:]
            mb = sum(br) / len(br)
            varb = sum((x - mb) ** 2 for x in br) / len(br) or 1e-9
            md = sum(dr) / len(dr)
            cov = sum((dr[i] - md) * (br[i] - mb) for i in range(len(dr))) / len(dr)
            out["beta_30d"] = cov / varb
            rel = (d[-1] / d[-31] - 1) - (b[-1] / b[-31] - 1)   # rel strength vs BTC
            gains = losses = 0.0
            for i in range(len(d) - 14, len(d)):
                ch = d[i] - d[i - 1]
                gains += ch if ch >= 0 else 0.0
                losses += -ch if ch < 0 else 0.0
            rsi = 100.0 - 100.0 / (1 + (gains / losses if losses > 0 else 99))
            sma20 = sum(d[-20:]) / 20.0
            trend = (d[-1] - sma20) / sma20
        sp = closes(sym, "1h", 2)[-48:]
        out["spark"] = sp
    except Exception as e:
        out["errors"].append("candles: %s" % str(e)[:40])
    # --- liquidity score (0-10) from the real order book (spread + 2% depth)
    try:
        ob = _hl_info({"type": "l2Book", "coin": sym})
        levels = ob.get("levels") or [[], []]
        bids, asks = levels[0], levels[1]
        if bids and asks:
            bb = float(bids[0]["px"])
            ba = float(asks[0]["px"])
            mid = (bb + ba) / 2
            sprd_bps = (ba - bb) / mid * 1e4 if mid else 99
            lo, hi = mid * 0.98, mid * 1.02
            depth = sum(float(l["px"]) * float(l["sz"]) for l in bids if float(l["px"]) >= lo)
            depth += sum(float(l["px"]) * float(l["sz"]) for l in asks if float(l["px"]) <= hi)
            s_depth = max(0.0, min(6.0, (_m.log10(depth + 1) - 4) * 2))   # ~$10k..$10M
            s_spread = max(0.0, min(4.0, 4 - sprd_bps / 3))
            out["liquidity_score"] = round(s_depth + s_spread, 1)
            out["spread_bps"] = round(sprd_bps, 2)
            out["depth_2pct_usd"] = depth
    except Exception as e:
        out["errors"].append("ob: %s" % str(e)[:40])
    # --- quant score (0-100) + verdict, from real signals
    try:
        comp = []
        if rsi is not None:
            comp.append(rsi / 100.0)                       # momentum
        if trend is not None:
            comp.append(0.5 + max(-0.5, min(0.5, trend * 4)))   # trend vs SMA20
        if rel is not None:
            comp.append(0.5 + max(-0.5, min(0.5, rel * 3)))     # rel strength vs BTC
        if out.get("funding") is not None:
            comp.append(0.5 + max(-0.5, min(0.5, out["funding"] * 4000)))  # funding tilt
        if comp:
            sc = int(round(100 * sum(comp) / len(comp)))
            out["quant_score"] = sc
            out["verdict"] = ("STRONG BUY" if sc >= 78 else "BUY" if sc >= 60
                              else "NEUTRAL" if sc >= 42 else "SELL" if sc >= 25
                              else "STRONG SELL")
    except Exception as e:
        out["errors"].append("score: %s" % str(e)[:40])
    _coin_cache[sym] = (_t.time(), out)
    return out


# ------------------------------------------------------- research panels ----
# Real data for the three chart panels on the research tab. Where the
# reference shows something no free feed provides, the nearest REAL series is
# used and the panel is labelled for what it actually is - never dressed up as
# the reference's label.
_rp = {}


def _research_panels():
    import time as _t
    import math as _m
    slot = _rp.get(1)
    if slot and _t.time() - slot[0] < 300:
        return slot[1]
    ms = int(_t.time() * 1000)
    out = {"errors": []}

    # --- liquidity: BTC market-cap proxy, YoY. Real daily closes x circulating
    # supply. Labelled as a proxy because global M2 has no free feed.
    SUPPLY = 19_900_000
    try:
        raw = _hl_info({"type": "candleSnapshot",
                        "req": {"coin": "BTC", "interval": "1d",
                                "startTime": ms - 86400000 * 760, "endTime": ms}})
        rows = sorted(raw, key=lambda k: int(k["t"]))
        pts = [[int(k["t"]), float(k["c"]) * SUPPLY] for k in rows]
        yoy = []
        for i in range(len(pts)):
            j = i - 365
            if j >= 0 and pts[j][1]:
                yoy.append([pts[i][0], (pts[i][1] / pts[j][1] - 1) * 100])
        if not yoy:                      # <1y of history: fall back to 90d rate
            for i in range(len(pts)):
                j = i - 90
                if j >= 0 and pts[j][1]:
                    yoy.append([pts[i][0], (pts[i][1] / pts[j][1] - 1) * 100])
            out["liquidity_window"] = "90d"
        else:
            out["liquidity_window"] = "1y"
        out["liquidity"] = {"series": yoy[-365:],
                            "now": yoy[-1][1] if yoy else None,
                            "chg": (yoy[-1][1] - yoy[-2][1]) if len(yoy) > 1 else None,
                            "label": "BTC MARKET CAP GROWTH (%s)" % (
                                "YoY" if out["liquidity_window"] == "1y" else "90D"),
                            "basis": "close x %s BTC supply" % f"{SUPPLY:,}"}
    except Exception as e:
        out["errors"].append("liquidity: %s" % str(e)[:50])

    # --- narratives: real market narratives from CoinGecko categories.
    # We curate WHICH themes to show (the only choice we make); every strength
    # number, direction and member coin below is live from the API.
    try:
        import time as _t, json as _j, urllib.request as _u
        if _t.time() - _narr["t"] > 600 or _narr["raw"] is None:
            _narr["raw"] = _j.loads(_u.urlopen(_u.Request(
                "https://api.coingecko.com/api/v3/coins/categories",
                headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
            _narr["t"] = _t.time()
            _narr["syms"] = None
        cats = _narr["raw"]
        WANT = [("DeFi", "Decentralized Finance (DeFi)"),
                ("AI & Data", "Artificial Intelligence (AI)"),
                ("Meme", "Meme"),
                ("Layer 2", "Layer 2 (L2)"),
                ("DEX", "Decentralized Exchange (DEX)"),
                ("DePIN", "DePIN"),
                ("Gaming", "Gaming (GameFi)"),
                ("RWA", "Real World Assets (RWA)")]
        by = {c.get("name"): c for c in cats}
        rows = []
        for disp, cgname in WANT:
            c = by.get(cgname)
            if not c:
                continue
            rows.append({"name": disp,
                         "vol": float(c.get("volume_24h") or 0),
                         "chg": float(c.get("market_cap_change_24h") or 0),
                         "top_ids": (c.get("top_3_coins_id") or [])[:3]})
        # strength 0-100 = relative 24h volume dominance (sqrt-compressed so the
        # spread reads like a heat index); colour comes from 24h momentum sign
        vmax = max((r["vol"] for r in rows), default=1.0) or 1.0
        for r in rows:
            r["strength"] = int(round(100 * (r["vol"] / vmax) ** 0.5))
        rows.sort(key=lambda r: -r["strength"])
        # resolve top coin ids -> ticker symbols (cached with the categories)
        if _narr["syms"] is None:
            ids = sorted({i for r in rows for i in r["top_ids"]})
            smap = {}
            if ids:
                mk = _j.loads(_u.urlopen(_u.Request(
                    "https://api.coingecko.com/api/v3/coins/markets"
                    "?vs_currency=usd&per_page=250&ids=" + ",".join(ids),
                    headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
                smap = {m["id"]: (m.get("symbol") or "").upper() for m in mk}
            _narr["syms"] = smap
        sym = _narr["syms"] or {}
        for r in rows:
            r["members"] = [sym[i] for i in r["top_ids"] if sym.get(i)]
            r.pop("top_ids", None)
        out["narratives"] = {
            "items": rows, "n": len(rows),
            "basis": "CoinGecko categories - strength = 24h volume share, "
                     "colour = 24h momentum"}
    except Exception as e:
        out["errors"].append("narratives: %s" % str(e)[:60])

    # --- flow: real daily notional volume for the three largest markets.
    # The reference shows exchange/whale/retail on-chain flow, which needs a
    # paid feed - this is venue volume, and the legend says so.
    try:
        series = {}
        for coin in ("BTC", "ETH", "SOL"):
            raw = _hl_info({"type": "candleSnapshot",
                            "req": {"coin": coin, "interval": "1d",
                                    "startTime": ms - 86400000 * 200,
                                    "endTime": ms}})
            rr = sorted(raw, key=lambda k: int(k["t"]))
            series[coin] = [[int(k["t"]),
                             float(k["v"]) * float(k["c"])] for k in rr][-180:]
        out["flow"] = {"series": series,
                       "basis": "daily notional traded on hyperliquid"}
    except Exception as e:
        out["errors"].append("flow: %s" % str(e)[:50])

    # --- derivatives radar: real funding (crowding / carry) + open interest.
    try:
        meta = _hl_info({"type": "metaAndAssetCtxs"})
        rows = []
        for u, c in zip(meta[0].get("universe", []), meta[1]):
            if u.get("isDelisted"):
                continue
            mark = float(c.get("markPx") or 0)
            fund = float(c.get("funding") or 0)      # hourly rate (decimal)
            vol = float(c.get("dayNtlVlm") or 0)
            if mark <= 0 or vol < 1e5:               # skip dead markets
                continue
            rows.append({"coin": u.get("name"),
                         "fund_hr": fund,
                         "fund_apr": fund * 24 * 365 * 100.0,   # annualised %
                         "oi_usd": float(c.get("openInterest") or 0) * mark})
        by_f = sorted(rows, key=lambda r: r["fund_apr"])
        longs = [r for r in reversed(by_f) if r["fund_apr"] > 0][:5]   # crowded longs
        shorts = [r for r in by_f if r["fund_apr"] < 0][:5]           # crowded shorts
        fmax = max([abs(r["fund_apr"]) for r in rows] or [1.0]) or 1.0
        oi_top = sorted(rows, key=lambda r: -r["oi_usd"])[:6]
        out["derivs"] = {
            "longs": longs, "shorts": shorts, "fund_max": fmax,
            "oi": oi_top, "oi_max": (oi_top[0]["oi_usd"] if oi_top else 1.0),
            "n": len(rows),
            "basis": "hyperliquid funding (annualised APR) + open interest"}
    except Exception as e:
        out["errors"].append("derivs: %s" % str(e)[:50])

    # --- RRG: JdK-style relative rotation of the top coins vs BTC (real).
    # RS = coin/BTC; RS-Ratio = z-score of RS (100-centred); RS-Momentum =
    # z-score of the RS-Ratio's rate of change. Tail = last N daily points.
    try:
        import statistics as _stt
        meta = _hl_info({"type": "metaAndAssetCtxs"})
        vols = []
        for u, c in zip(meta[0].get("universe", []), meta[1]):
            nm = u.get("name")
            if u.get("isDelisted") or nm == "BTC":
                continue
            vols.append((nm, float(c.get("dayNtlVlm") or 0)))
        vols.sort(key=lambda t: -t[1])
        picks = [v[0] for v in vols[:9]]

        def _closes(coin, weeks=44):
            raw = _hl_info({"type": "candleSnapshot",
                            "req": {"coin": coin, "interval": "1w",
                                    "startTime": ms - 7 * 86400000 * weeks,
                                    "endTime": ms}})
            rr = sorted(raw, key=lambda k: int(k["t"]))
            return [float(k["c"]) for k in rr]

        def _zc(series, w):
            out2 = []
            for i in range(len(series)):
                win = series[max(0, i - w + 1):i + 1]
                if len(win) < 3:
                    out2.append(100.0)
                    continue
                m = _stt.mean(win)
                sd = _stt.pstdev(win) or 1e-9
                out2.append(100.0 + (series[i] - m) / sd)
            return out2

        def _ema(series, span):
            a = 2.0 / (span + 1.0)
            e = series[0] if series else 0.0
            out2 = []
            for v in series:
                e = a * v + (1 - a) * e
                out2.append(e)
            return out2

        bench = _closes("BTC")
        TAIL, STEP, W = 7, 1, 12          # 7 weekly points -> clean rotation arc
        need = (TAIL - 1) * STEP + 1
        items = []
        for coin in picks:
            p = _closes(coin)
            n = min(len(p), len(bench))
            if n < W + need + 2:
                continue
            pa, pb = p[-n:], bench[-n:]
            rs = [pa[i] / pb[i] for i in range(n)]
            ratio = _ema(_zc(rs, W), 3)                       # smoothed RS-Ratio
            roc = [(ratio[i] - ratio[i - 1]) if i else 0.0 for i in range(len(ratio))]
            mom = _ema(_zc(roc, W), 4)                        # smoothed RS-Momentum
            idx = [len(ratio) - 1 - (TAIL - 1 - k) * STEP for k in range(TAIL)]
            sc = lambda v: round(100.0 + (v - 100.0) * 2.4, 3)   # spread for display
            tail = [[sc(ratio[i]), sc(mom[i])] for i in idx]
            items.append({"coin": coin, "tail": tail,
                          "x": tail[-1][0], "y": tail[-1][1]})
        out["rrg"] = {"items": items, "benchmark": "BTC", "tail": TAIL,
                      "basis": "JdK relative rotation vs BTC (daily)"}
    except Exception as e:
        out["errors"].append("rrg: %s" % str(e)[:50])

    # --- quant signals: real per-coin technical signals from live candles
    # (RSI-14 + 20d breakout + 5d momentum). Rule-based on real price data.
    try:
        import statistics as _st2
        from concurrent.futures import ThreadPoolExecutor as _TPE
        meta = _hl_info({"type": "metaAndAssetCtxs"})
        top = []
        for u, c in zip(meta[0].get("universe", []), meta[1]):
            if u.get("isDelisted"):
                continue
            top.append({"coin": u.get("name"), "vol": float(c.get("dayNtlVlm") or 0),
                        "funding": float(c.get("funding") or 0)})
        top.sort(key=lambda r: -r["vol"])
        top = top[:12]

        def _fetch(name):
            raw = _hl_info({"type": "candleSnapshot",
                            "req": {"coin": name, "interval": "1d",
                                    "startTime": ms - 86400000 * 40, "endTime": ms}})
            return name, [float(k["c"]) for k in sorted(raw, key=lambda k: int(k["t"]))]
        closes = {}
        with _TPE(max_workers=12) as _ex:      # parallel - keeps the endpoint fast
            for name, cl in _ex.map(_fetch, [r["coin"] for r in top]):
                if len(cl) >= 22:
                    closes[name] = cl

        sigs = []
        for r in top[:6]:
            name = r["coin"]
            cl = closes.get(name)
            if not cl or len(cl) < 22:
                continue
            gains = losses = 0.0
            for i in range(len(cl) - 14, len(cl)):
                ch = cl[i] - cl[i - 1]
                gains += ch if ch >= 0 else 0.0
                losses += -ch if ch < 0 else 0.0
            rsi = 100.0 - 100.0 / (1 + (gains / losses if losses > 0 else 99))
            hi20, lo20 = max(cl[-21:-1]), min(cl[-21:-1])
            last = cl[-1]
            ret5 = (last / cl[-6] - 1) * 100
            if last > hi20:
                lab, strg, hor = "BREAKOUT", 60 + abs(ret5) * 3, "1D"
            elif last < lo20:
                lab, strg, hor = "REVERSAL", 55 + abs(ret5) * 3, "2D"
            elif rsi > 68 or rsi < 32:
                lab, strg, hor = "MEAN REVERT", 50 + abs(rsi - 50), "1D"
            elif ret5 > 2:
                lab, strg, hor = "MOMENTUM", 55 + ret5 * 4, "3D"
            else:
                lab, strg, hor = "NEUTRAL", 45, "3D"
            sigs.append({"coin": name + "-PERP", "signal": lab,
                         "strength": int(min(100, max(0, strg))),
                         "confidence": int(min(92, 50 + abs(rsi - 50))),
                         "horizon": hor})
        out["quant_signals"] = {
            "items": sigs,
            "basis": "RSI(14) + 20d breakout + 5d momentum on real daily candles"}

        # factor performance: long-short tercile returns, from the same candles
        fc = {c: closes[c][-31:] for c in closes if len(closes[c]) >= 31}
        coins = list(fc.keys())
        if len(coins) >= 3:
            rets = {c: [fc[c][i] / fc[c][i - 1] - 1 for i in range(1, 31)]
                    for c in coins}
            volm = {r["coin"]: r["vol"] for r in top}
            fund = {r["coin"]: r["funding"] for r in top}

            def _factor(scorefn):
                sc = {c: scorefn(c) for c in coins}
                order = sorted(coins, key=lambda c: sc[c])
                k = max(1, len(order) // 3)
                lo, hi = order[:k], order[-k:]
                ls = [sum(rets[c][d] for c in hi) / len(hi)
                      - sum(rets[c][d] for c in lo) / len(lo) for d in range(30)]
                cum, acc = [], 1.0
                for x in ls:
                    acc *= (1 + x)
                    cum.append(round((acc - 1) * 100, 3))
                mu = sum(ls) / len(ls)
                sd = _st2.pstdev(ls) or 1e-9
                return {"ir": mu / sd * (365 ** 0.5), "ret": cum[-1] if cum else 0.0,
                        "z": mu / sd * (len(ls) ** 0.5), "spark": cum}

            defs = [("Momentum", lambda c: fc[c][-1] / fc[c][0] - 1),
                    ("Low Vol", lambda c: -_st2.pstdev(rets[c])),
                    ("Carry", lambda c: fund.get(c, 0)),
                    ("Liquidity", lambda c: volm.get(c, 0))]
            fitems = []
            for nm, fn in defs:
                f = _factor(fn)
                fitems.append({"name": nm, "ir": round(f["ir"], 2),
                               "ret": round(f["ret"], 2), "z": round(f["z"], 2),
                               "spark": f["spark"]})
            out["factors"] = {
                "items": fitems, "n_coins": len(coins),
                "basis": "long-short terciles, 30d daily returns; "
                         "Value/Quality omitted (no free crypto fundamentals)"}
    except Exception as e:
        out["errors"].append("xsec: %s" % str(e)[:50])

    _rp[1] = (_t.time(), out)
    return out

def _env(key):
    import os
    v = os.getenv(key)
    if v:
        return v.strip()
    try:
        f = Path(__file__).resolve().parent.parent / ".env"
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def _hl_info(body):
    import json as _j
    import urllib.request as _u
    return _j.loads(_u.urlopen(_u.Request(
        "https://api.hyperliquid.xyz/info", data=_j.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0"}), timeout=20).read())


def _lighter_get(path, auth=False):
    import json as _j
    import urllib.request as _u
    h = {"User-Agent": "Mozilla/5.0"}
    if auth:
        tok = _env("LIGHTER_READONLY_TOKEN")
        if tok:
            h["Authorization"] = tok          # read-only: cannot trade/withdraw
    return _j.loads(_u.urlopen(_u.Request(
        "https://mainnet.zklighter.elliot.ai/api/v1" + path,
        headers=h), timeout=20).read())


def _portfolio(tf="1D"):
    """Combined Hyperliquid + Lighter, read-only. Cached 45s per timeframe."""
    import time as _t
    tf = tf if tf in _PF_TF else "1D"
    slot = _pf.get(tf)
    if slot and _t.time() - slot["t"] < 45:
        return slot["data"]

    out = {"tf": tf, "positions": [], "venues": {}, "errors": []}
    hl_addr = _env("HL_ACCOUNT_ADDRESS")
    lt_addr = _env("LIGHTER_L1_ADDRESS")

    hl_val = 0.0
    hl_upnl = 0.0
    try:
        ch = _hl_info({"type": "clearinghouseState", "user": hl_addr})
        ms = ch.get("marginSummary", {})
        hl_val = float(ms.get("accountValue") or 0)
        for ap in ch.get("assetPositions", []):
            po = ap.get("position", {})
            szi = float(po.get("szi") or 0)
            if not szi:
                continue
            up = float(po.get("unrealizedPnl") or 0)
            hl_upnl += up
            out["positions"].append({
                "venue": "HL", "kind": "PERP", "coin": po.get("coin"),
                "side": "LONG" if szi > 0 else "SHORT", "size": abs(szi),
                "entry": float(po.get("entryPx") or 0),
                "value": float(po.get("positionValue") or 0),
                "upnl": up,
                "lev": (po.get("leverage") or {}).get("value"),
                "alloc": float(po.get("marginUsed") or 0) - up,
                "equity": float(po.get("marginUsed") or 0),
                "liq": (float(po.get("liquidationPx"))
                        if po.get("liquidationPx") not in (None, "") else None),
            })
            _p = out["positions"][-1]
            _p["mark"] = (_p["value"] / _p["size"]) if _p["size"] else 0.0
            _cost = _p["entry"] * _p["size"]
            _p["pnl_pct"] = (up / _cost * 100) if _cost else 0.0
        out["venues"]["hyperliquid"] = {
            "account_value": hl_val, "upnl": hl_upnl,
            "notional": float(ms.get("totalNtlPos") or 0),
            "margin_used": float(ms.get("totalMarginUsed") or 0)}
    except Exception as e:
        out["errors"].append("hl_perps: %s" % e)

    # ---- Hyperliquid BUILDER SUB-DEXES (HIP-3) ----
    # The main clearinghouseState above only covers the primary perp dex.
    # HIP-3 lets anyone deploy their own perp dex (e.g. "xyz" -> xyz:CL /
    # "WTIOIL") with its OWN isolated collateral. Those positions and that
    # collateral live in a separate clearinghouseState keyed by `dex`, so
    # without this block they are invisible to the portfolio AND net worth.
    # We discover every deployed dex dynamically (no hardcoded names) and
    # fetch each in parallel.
    hl_builder_eq = 0.0
    try:
        from concurrent.futures import ThreadPoolExecutor
        dexs = _hl_info({"type": "perpDexs"}) or []
        names = [d.get("name") for d in dexs
                 if isinstance(d, dict) and d.get("name")]
        def _ch(dx):
            try:
                return dx, _hl_info({"type": "clearinghouseState",
                                     "user": hl_addr, "dex": dx})
            except Exception as _e:
                return dx, {"_err": str(_e)[:40]}
        if names:
            with ThreadPoolExecutor(max_workers=min(8, len(names))) as _ex:
                for dx, ch in _ex.map(_ch, names):
                    if ch.get("_err"):
                        out["errors"].append("hl_dex %s: %s" % (dx, ch["_err"]))
                        continue
                    dms = ch.get("marginSummary", {})
                    hl_builder_eq += float(dms.get("accountValue") or 0)
                    for ap in ch.get("assetPositions", []):
                        po = ap.get("position", {})
                        szi = float(po.get("szi") or 0)
                        if not szi:
                            continue
                        up = float(po.get("unrealizedPnl") or 0)
                        hl_upnl += up
                        raw = po.get("coin") or ""
                        tick = raw.split(":", 1)[1] if ":" in raw else raw
                        out["positions"].append({
                            "venue": "HL", "kind": "PERP", "coin": tick,
                            "raw_coin": raw, "dex": dx,
                            "side": "LONG" if szi > 0 else "SHORT",
                            "size": abs(szi),
                            "entry": float(po.get("entryPx") or 0),
                            "value": float(po.get("positionValue") or 0),
                            "upnl": up,
                            "lev": (po.get("leverage") or {}).get("value"),
                            "alloc": float(po.get("marginUsed") or 0) - up,
                            "equity": float(po.get("marginUsed") or 0),
                            "liq": (float(po.get("liquidationPx"))
                                    if po.get("liquidationPx") not in (None, "")
                                    else None),
                        })
                        _p = out["positions"][-1]
                        _p["mark"] = (_p["value"] / _p["size"]) if _p["size"] else 0.0
                        _cost = _p["entry"] * _p["size"]
                        _p["pnl_pct"] = (up / _cost * 100) if _cost else 0.0
        out["hl_builder_equity"] = hl_builder_eq
    except Exception as e:
        out["errors"].append("hl_builder: %s" % e)

    hl_spot = 0.0
    try:
        sp = _hl_info({"type": "spotClearinghouseState", "user": hl_addr})
        for b in sp.get("balances", []):
            tot = float(b.get("total") or 0)
            held = float(b.get("hold") or 0)
            free = tot - held
            coin = (b.get("coin") or "").upper()
            if coin in ("USDC", "USD"):
                hl_spot += tot           # the whole wallet; `hold` is margin
                out["spot_total"] = tot  # drawn from this same balance
                out["spot_hold"] = held
                out["available"] = free
            if tot > 0:
                if coin in ("USDC", "USD", "USDE", "USDT0", "USDH"):
                    out["positions"].append({
                        "venue": "HL", "kind": "CASH", "coin": coin,
                        "side": "-", "size": free, "entry": None,
                        "mark": None, "value": free,
                        "upnl": None, "pnl_pct": None, "lev": None,
                        "is_cash": True, "hold": held, "total": tot,
                        "alloc": free, "equity": free,
                    })
                else:
                    # a real spot token: size is the whole holding, and it is
                    # marked by the venue, not assumed to be worth 1.0
                    out["positions"].append({
                        "venue": "HL", "kind": "SPOT", "coin": coin,
                        "side": "-", "size": tot, "entry": None,
                        "mark": None, "value": 0.0,
                        "upnl": None, "pnl_pct": None, "lev": None,
                        "is_cash": False, "hold": held, "total": tot,
                        "alloc": 0.0, "equity": 0.0,
                    })
        out["venues"]["hyperliquid_spot"] = {"usdc_free": hl_spot}
    except Exception as e:
        out["errors"].append("hl_spot: %s" % e)

    # Lighter's own live prices (same source it marks perps with), used to
    # value Lighter spot token holdings that it leaves out of total_asset_value.
    _lt_px = {}
    _lt_spot_mkt = {}
    try:
        obd = _lighter_get("/orderBookDetails")
        for m in (obd.get("order_book_details") or obd.get("orderBookDetails") or []):
            sym = (m.get("symbol") or "").upper()
            px = m.get("mark_price") or m.get("index_price") or m.get("last_trade_price")
            if sym and px not in (None, ""):
                _lt_px[sym] = float(px)
    except Exception as e:
        out["errors"].append("lt_prices: %s" % str(e)[:50])
    try:                                     # spot markets ("SYM/USDC") -> id
        obk = _lighter_get("/orderBooks")
        for m in (obk.get("order_books") or obk.get("orderBooks") or []):
            sym = (m.get("symbol") or "").upper()
            if sym.endswith("/USDC") and m.get("market_id") is not None:
                _lt_spot_mkt[sym[:-5]] = m.get("market_id")
    except Exception as e:
        out["errors"].append("lt_spot_mkts: %s" % str(e)[:50])

    lt_coll = 0.0
    lt_upnl = 0.0
    lt_dep = 0.0
    lt_out = 0.0
    lt_real = 0.0
    lt_series = []
    lt_pnl_tf = None
    lt_genesis = None
    hl_genesis = None
    import time as _t
    try:
        acc = _lighter_get("/accountsByL1Address?l1_address=%s" % lt_addr)
        subs = acc.get("sub_accounts") or acc.get("accounts") or []
        for sub in subs:
            idx = sub.get("index")
            if idx is None:
                continue
            det = _lighter_get("/account?by=index&value=%s" % idx)
            for a in (det.get("accounts") or []):
                out["lighter_free"] = float(a.get("available_balance") or 0)
                lt_cash = float(a.get("collateral") or 0)
                out["lighter_cash"] = lt_cash
                if lt_cash > 0:
                    out["positions"].append({
                        "venue": "LT", "kind": "CASH", "coin": "USDC",
                        "side": "-", "size": lt_cash, "entry": None,
                        "mark": None, "value": lt_cash,
                        "upnl": None, "pnl_pct": None, "lev": None,
                        "is_cash": True,
                        "alloc": lt_cash, "equity": lt_cash,
                    })
                # Total Account Value = Collateral + Unrealized PnL.
                # Fall back only if the field is ever absent.
                tav = a.get("total_asset_value")
                if tav is not None:
                    lt_coll += float(tav)
                else:
                    lt_coll += (float(a.get("collateral") or 0)
                                + sum(float(q.get("allocated_margin") or 0)
                                      + float(q.get("unrealized_pnl") or 0)
                                      for q in (a.get("positions") or [])))
                for po in (a.get("positions") or []):
                    size = float(po.get("position") or 0)
                    if not size:
                        continue
                    up = float(po.get("unrealized_pnl") or 0)
                    lt_upnl += up
                    out["positions"].append({
                        "venue": "LT", "kind": "PERP", "coin": po.get("symbol"),
                        "side": "LONG" if int(po.get("sign") or 1) > 0 else "SHORT",
                        "size": size,
                        "entry": float(po.get("avg_entry_price") or 0),
                        "value": abs(float(po.get("position_value") or 0)),
                        "upnl": up, "lev": None,
                        "market_id": po.get("market_id"),
                        "alloc": float(po.get("allocated_margin") or 0),
                        "equity": float(po.get("allocated_margin") or 0) + up,
                        "liq": (float(po.get("liquidation_price"))
                                if po.get("liquidation_price") not in (None, "") else None),
                    })
                    _q = out["positions"][-1]
                    _q["mark"] = (_q["value"] / _q["size"]) if _q["size"] else 0.0
                    _c2 = _q["entry"] * _q["size"]
                    _q["pnl_pct"] = (up / _c2 * 100) if _c2 else 0.0
                # SPOT token holdings: Lighter lists these under `assets` with
                # margin_mode 'disabled' and leaves them OUT of total_asset_value,
                # so we value each at Lighter's own live price and add it - the
                # same treatment perps get, driven entirely by the live account
                # (any token bought later shows up automatically).
                _STABLE = ("USDC", "USD", "USDE", "USDT", "USDT0", "USDH", "USDG")
                for ast in (a.get("assets") or []):
                    sym = (ast.get("symbol") or "").upper()
                    bal = float(ast.get("balance") or 0)
                    if bal <= 0 or ast.get("margin_mode") != "disabled":
                        continue                      # only un-margined spot tokens
                    if sym in _STABLE:
                        lt_coll += bal                # a spot stablecoin ~= $1
                        continue
                    px = _lt_px.get(sym) or 0.0
                    if px <= 0:
                        out["errors"].append("lt_spot_price missing: %s" % sym)
                        continue
                    val = bal * px
                    lt_coll += val
                    # cost basis from the token's spot fills -> entry + PnL,
                    # so a spot row reads like a perp row (display only; the
                    # value above is what counts toward equity).
                    entry = spot_up = spot_pct = None
                    _mkt = _lt_spot_mkt.get(sym)
                    if _mkt is not None:
                        try:
                            _tr = (_lighter_get(
                                "/trades?sort_by=timestamp&account_index=%s"
                                "&market_id=%s&limit=100&ask_filter=-1"
                                % (idx, _mkt), auth=True).get("trades") or [])
                            _tr.sort(key=lambda t: int(t.get("timestamp") or 0))
                            # FIFO lot accounting - the cost basis of the CURRENT
                            # holding is its most recent unsold buys, not the
                            # average of every in-and-out trade.
                            _lots = []
                            for _trd in _tr:
                                _s = float(_trd.get("size") or 0)
                                _p = float(_trd.get("price") or 0)
                                _bid = _trd.get("bid_account_id")
                                _ask = _trd.get("ask_account_id")
                                if _bid is not None and int(_bid) == int(idx):
                                    _lots.append([_s, _p])           # bought base
                                elif _ask is not None and int(_ask) == int(idx):
                                    while _s > 1e-9 and _lots:       # sold base (FIFO)
                                        if _lots[0][0] <= _s + 1e-9:
                                            _s -= _lots[0][0]
                                            _lots.pop(0)
                                        else:
                                            _lots[0][0] -= _s
                                            _s = 0.0
                            _held = sum(l[0] for l in _lots)
                            _cost = sum(l[0] * l[1] for l in _lots)
                            if _held > 1e-9:
                                entry = _cost / _held
                                _basis = entry * bal          # value the held bal at cost
                                spot_up = val - _basis
                                spot_pct = (spot_up / _basis * 100) if _basis else None
                        except Exception as e:
                            out["errors"].append("lt_spot_pnl %s: %s"
                                                 % (sym, str(e)[:30]))
                    out["positions"].append({
                        "venue": "LT", "kind": "SPOT", "coin": sym,
                        "side": "-", "size": bal, "entry": entry,
                        "mark": px, "value": val, "upnl": spot_up,
                        "pnl_pct": spot_pct, "lev": None, "is_cash": False,
                        "alloc": val, "equity": val,
                    })
            # Deposits + realised PnL. Rows are CUMULATIVE snapshots, so the
            # LAST row is the running total - summing them double-counts.
            try:
                pnl = _lighter_get(
                    "/pnl?by=index&value=%s&resolution=1d"
                    "&start_timestamp=1750000000000&end_timestamp=1800000000000"
                    "&count_back=365" % idx, auth=True)
                rows = pnl.get("pnl") or []
                if rows:
                    lt_genesis = int(rows[0]["timestamp"]) * 1000
                    last = rows[-1]
                    lt_dep += _lt_sum(last, _LT_IN)
                    lt_out += _lt_sum(last, _LT_OUT)
                    lt_real += _lt_sum(last, _LT_PNL)
                    out["lighter_volume"] = float(last.get("volume") or 0)
                # equity curve for THIS venue: cash in, minus out, plus realised
                ms_now = int(_t.time() * 1000)
                span = {"1D": 2, "1W": 8, "1M": 32, "ALL": 400}[tf]

                def _pnl_rows(res, days, back):
                    try:
                        r = _lighter_get(
                            "/pnl?by=index&value=%s&resolution=%s"
                            "&start_timestamp=%d&end_timestamp=%d&count_back=%d"
                            % (idx, res, ms_now - 86400000 * days, ms_now, back),
                            auth=True)
                        return r.get("pnl") or []
                    except Exception as e:
                        out["errors"].append("lighter_hist %s: %s" % (res, e))
                        return []

                rows_by_ts = {}
                if span > _LT_1H_MAX_DAYS:          # long tail, coarse
                    for r in _pnl_rows("1d", span, 400):
                        rows_by_ts[int(r["timestamp"])] = r
                # recent detail, always - this is the only place the first
                # day of a young account shows up
                for r in _pnl_rows("1h", min(span, _LT_1H_MAX_DAYS), 240):
                    rows_by_ts[int(r["timestamp"])] = r

                lt_rows = [rows_by_ts[t] for t in sorted(rows_by_ts)]
                if lt_rows:
                    first = int(lt_rows[0]["timestamp"]) * 1000
                    lt_genesis = min(lt_genesis or first, first)
                lt_series = [[t * 1000,
                              _lt_sum(rows_by_ts[t], _LT_IN)
                              - _lt_sum(rows_by_ts[t], _LT_OUT)
                              + _lt_sum(rows_by_ts[t], _LT_PNL)]
                             for t in sorted(rows_by_ts)]
                # trade_pnl is CUMULATIVE, so the venue's PnL over this window
                # is (last - baseline). Baseline is 0 when the window starts
                # before the account had any history at all.
                if lt_rows:
                    win0 = ms_now - 86400000 * _TF_WINDOW_DAYS[tf]
                    base = 0.0
                    for r in lt_rows:
                        if int(r["timestamp"]) * 1000 <= win0:
                            base = _lt_sum(r, _LT_PNL)
                    lt_pnl_tf = _lt_sum(lt_rows[-1], _LT_PNL) - base
            except Exception as e:
                out["errors"].append("lighter_pnl: %s" % e)
        out["venues"]["lighter"] = {"collateral": lt_coll, "upnl": lt_upnl}
    except Exception as e:
        out["errors"].append("lighter: %s" % e)

    try:
        pf = _hl_info({"type": "portfolio", "user": hl_addr})
        want = _PF_TF[tf]
        series = []
        pnl_series = []
        for period, data in pf:
            if period == want:
                series = data.get("accountValueHistory") or []
                pnl_series = data.get("pnlHistory") or []
                out["volume"] = float(data.get("vlm") or 0)
        out["equity"] = [[int(t), float(v)] for t, v in series]
        # HL's own account value for the whole account. Measured: this equals
        # the spot USDC total exactly (47.975695), and the perp accountValue
        # (34.86) equals `hold` and sits INSIDE it - adding both double-counts.
        for period, data in pf:
            if period == "allTime":
                h = data.get("accountValueHistory") or []
                if h:
                    out["hl_equity"] = float(h[-1][1])
                    hl_genesis = int(h[0][0])
                ph = data.get("pnlHistory") or []
                if ph:
                    out["hl_pnl_all_time"] = float(ph[-1][1]) - float(ph[0][1])
        out["pnl_series"] = [[int(t), float(v)] for t, v in pnl_series]
        hl_pnl_tf = (float(pnl_series[-1][1]) - float(pnl_series[0][1])
                     if pnl_series else None)
        out["pnl_tf_hl"] = hl_pnl_tf
        out["pnl_tf_lt"] = lt_pnl_tf
        if hl_pnl_tf is None and lt_pnl_tf is None:
            out["pnl_tf"] = None
        else:
            out["pnl_tf"] = (hl_pnl_tf or 0.0) + (lt_pnl_tf or 0.0)
        # ---- COMBINED equity curve: HL series + Lighter series, step-held
        # onto one timeline then summed. Neither venue's prices touch the
        # other; these are two independent equity numbers being added.
        hl_series = out["equity"]
        if hl_series and lt_series:
            stamps = sorted({t for t, _ in hl_series} | {t for t, _ in lt_series})
            def hold(series, when, genesis):
                # before this venue existed it held nothing
                if genesis is not None and when < genesis:
                    return 0.0
                v = None
                for t, x in series:
                    if t <= when:
                        v = x
                    else:
                        break
                # inside the venue's life but with no point this early: the
                # money was there, we just lack a sample. Carry the earliest.
                return v if v is not None else series[0][1]
            merged = [[t, hold(hl_series, t, hl_genesis)
                        + hold(lt_series, t, lt_genesis)] for t in stamps]
            # anchor the final point to the true current equity
            if merged:
                merged[-1][1] = (out.get("hl_equity") or hl_series[-1][1]) + lt_coll
            out["equity"] = merged
            out["equity_note"] = "combined: Hyperliquid + Lighter"
            out["equity_hl_only"] = hl_series
            out["equity_lt_only"] = lt_series
        else:
            out["equity_note"] = ("Hyperliquid only - no Lighter history"
                                  if not lt_series else "Lighter only")
    except Exception as e:
        out["errors"].append("hl_portfolio: %s" % e)

    try:
        led = _hl_info({"type": "userNonFundingLedgerUpdates",
                        "user": hl_addr, "startTime": 0})
        dep = 0.0
        wdr = 0.0
        for e in led:
            d = e.get("delta", {}) or {}
            kind = d.get("type")
            amt = float(d.get("usdc") or d.get("usdcValue") or d.get("amount") or 0)
            if kind in ("deposit", "spotTransfer", "accountClassTransfer"):
                dep += amt
            elif kind == "withdraw":
                wdr += amt
        out["deposited"] = dep
        out["withdrawn"] = wdr
        out["deposits_note"] = "Hyperliquid ledger only - Lighter deposits are 403"
    except Exception as e:
        out["errors"].append("hl_ledger: %s" % e)

    # ---------- combine (each venue valued on its own, then summed) ----------
    hl_eq = out.get("hl_equity") or hl_spot      # HL's own figure, else the wallet
    hl_dep = out.get("deposited") or 0.0         # HL ledger deposits
    hl_wdr = out.get("withdrawn") or 0.0

    out["by_venue"] = {
        "hyperliquid": {"equity": hl_eq, "deposited": hl_dep, "withdrawn": hl_wdr,
                        "upnl": hl_upnl, "free": out.get("available", 0.0)},
        "lighter": {"equity": lt_coll, "deposited": lt_dep, "withdrawn": lt_out,
                    "upnl": lt_upnl, "realised": lt_real,
                    "free": out.get("lighter_free", 0.0)},
    }
    # NOTE: builder-dex (HIP-3) collateral is ALREADY inside HL's reported
    # account value (hl_equity), so it must NOT be added again here - doing so
    # double-counts net worth. We only surface the builder POSITIONS in the
    # list (above) for visibility; the money itself is already in hl_eq.
    out["net_worth"] = hl_eq + lt_coll
    out["deposited_total"] = hl_dep + lt_dep
    out["withdrawn_total"] = hl_wdr + lt_out
    out["upnl_total"] = hl_upnl + lt_upnl
    out["n_positions"] = sum(1 for q in out["positions"] if not q.get("is_cash"))
    out["n_cash_rows"] = sum(1 for q in out["positions"] if q.get("is_cash"))
    hl_avail = out.get("available", 0.0)
    lt_avail = out.get("lighter_free", 0.0)
    out["available_total"] = hl_avail + lt_avail
    out["available_by_venue"] = {"hyperliquid": hl_avail, "lighter": lt_avail}
    # idle cash: sums with position margin back to net worth, unlike the
    # tradeable figure above.
    out["cash_total"] = sum(q["value"] for q in out["positions"] if q.get("is_cash"))
    out["equity_alloc_total"] = sum(q.get("equity") or 0 for q in out["positions"])
    out["equity_alloc_gap"] = out["net_worth"] - out["equity_alloc_total"]
    # all-time PnL = what it is worth now, minus what went in, plus what came out
    # percentage base for the timeframe PnL. Dividing by (net_worth - pnl)
    # would treat a mid-window DEPOSIT as starting capital; use the equity
    # actually at risk when the window opened, and fall back to the cost
    # basis when the account was funded inside the window.
    eqc = out.get("equity") or []
    if out.get("pnl_tf") is not None and eqc:
        base = eqc[0][1]
        if base < 1.0:
            base = out["deposited_total"]
        out["pnl_tf_base"] = base
        out["pnl_tf_pct"] = (out["pnl_tf"] / base * 100) if base else None
    if out["deposited_total"]:
        out["pnl_all_time"] = (out["net_worth"] + out["withdrawn_total"]
                               - out["deposited_total"])
        out["pnl_all_time_pct"] = (out["pnl_all_time"] / out["deposited_total"]) * 100
        # realised per venue, from each venue's OWN all-time PnL minus its own
        # still-open PnL - not derived by subtracting from the line above.
        hl_all = out.get("hl_pnl_all_time")
        out["realised_hl"] = (hl_all - hl_upnl) if hl_all is not None else None
        out["realised_lt"] = lt_real - lt_upnl
        out["realised_total"] = (
            (out["realised_hl"] or 0.0) + out["realised_lt"]
            if hl_all is not None else out["pnl_all_time"] - out["upnl_total"])
        # two independent routes to all-time PnL; they must agree
        if hl_all is not None:
            out["pnl_venue_reported"] = hl_all + lt_real
            out["reconcile_gap"] = out["pnl_all_time"] - out["pnl_venue_reported"]
            out["reconciled"] = abs(out["reconcile_gap"]) < 0.05
            if not out["reconciled"]:
                out["errors"].append(
                    "reconcile: cash %.4f vs venues %.4f (gap %.4f)"
                    % (out["pnl_all_time"], out["pnl_venue_reported"],
                       out["reconcile_gap"]))
    else:
        out["pnl_all_time"] = None
        out["pnl_all_time_pct"] = None
        out["realised_total"] = None
        out["reconciled"] = None
    out["pnl_since_entry"] = out["pnl_all_time"]
    out["positions"].sort(key=lambda x: -x["value"])
    _pf[tf] = {"data": out, "t": _t.time()}
    return out


# ---------------------------------------------------- tradfi ticker (READ ONLY)
# SPX / VIX / DXY / US10Y are not crypto, so Hyperliquid's allMids cannot carry
# them. Yahoo's chart endpoint serves them with no key. Browsers cannot call it
# cross-origin, so it is proxied here. Cached 30s.
_TRADFI = [("SPX", "^GSPC"), ("VIX", "^VIX"),
           ("DXY", "DX-Y.NYB"), ("US10Y", "^TNX")]
_tf_cache = {"t": 0.0, "data": None}


def _tradfi():
    import time as _t
    import json as _j
    import urllib.request as _u
    import urllib.parse as _up
    if _t.time() - _tf_cache["t"] < 30 and _tf_cache["data"] is not None:
        return _tf_cache["data"]
    out = {"quotes": [], "errors": []}
    for label, sym in _TRADFI:
        try:
            url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s"
                   "?interval=1d&range=5d" % _up.quote(sym))
            d = _j.loads(_u.urlopen(_u.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/120 Safari/537.36"}),
                timeout=15).read())
            m = d["chart"]["result"][0]["meta"]
            px = m.get("regularMarketPrice")
            pc = m.get("chartPreviousClose") or m.get("previousClose")
            out["quotes"].append({
                "label": label, "symbol": sym, "price": px,
                "prev_close": pc,
                "chg_pct": ((px / pc - 1) * 100) if (px and pc) else None,
            })
        except Exception as e:
            out["errors"].append("%s: %s" % (label, e))
    _tf_cache["data"] = out
    _tf_cache["t"] = _t.time()
    return out


def _finite(o):
    """Replace NaN/Infinity (which Python's json emits but browsers reject as
    invalid JSON) with None, recursively, so /api responses always parse."""
    import math
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_finite(v) for v in o]
    return o


def _jdump(obj):
    return json.dumps(_finite(obj))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api/market"):
            self._send(_jdump(market_cached()), "application/json")
        elif self.path.startswith("/api/book"):
            self._send(_jdump(book_state()), "application/json")
        elif self.path.startswith("/api/portfolio"):
            from urllib.parse import urlparse as _up2, parse_qs as _pq2
            _t2 = (_pq2(_up2(self.path).query).get("tf", ["1D"])[0] or "1D").upper()
            self._send(_jdump(_portfolio(_t2)), "application/json")
        elif self.path.startswith("/api/tradfi_ticker"):
            self._send(_jdump(_tradfi()), "application/json")
        elif self.path.startswith("/api/news"):
            self._send(_jdump(_news_all()), "application/json")
        elif self.path.startswith("/api/overview"):
            from urllib.parse import urlparse as _up, parse_qs as _pq
            _tf = (_pq(_up(self.path).query).get("tf", ["1D"])[0] or "1D").upper()
            self._send(_jdump(_overview(_tf)), "application/json")
        elif self.path.startswith("/api/tradfi"):
            self._send(_jdump(_tradfi()), "application/json")
        elif self.path.startswith("/api/research"):
            self._send(_jdump(_research_panels()), "application/json")
        elif self.path.startswith("/api/regime"):
            self._send(_jdump(_macro_regime()), "application/json")
        elif self.path.startswith("/api/liqvol"):
            self._send(_jdump(_liqvol()), "application/json")
        elif self.path.startswith("/api/papers"):
            self._send(_jdump(_papers()), "application/json")
        elif self.path.startswith("/api/desk"):
            from urllib.parse import urlparse as _upd, parse_qs as _pqd
            _run = _pqd(_upd(self.path).query).get("run", [None])[0]
            self._send(_jdump(_desk(_run)), "application/json")
        elif self.path.startswith("/api/quant"):
            from urllib.parse import urlparse as _upq, parse_qs as _pqq
            _q = _pqq(_upq(self.path).query)
            _what = (_q.get("what", ["snapshot"])[0] or "snapshot").lower()
            _sym = (_q.get("coin", ["BTC"])[0] or "BTC").upper()
            if _what == "coins":
                _r = _ql_coins()
            elif _what == "status":
                _r = _ql_status()
            elif _what == "series":
                _r = _ql_series(_sym, _q.get("field", ["c"])[0],
                                int(_q.get("n", ["400"])[0]))
            else:
                _r = _ql_snapshot(_sym)
            self._send(_jdump(_r), "application/json")
        elif self.path.startswith("/api/coin"):
            import urllib.parse as _up
            qs = _up.parse_qs(_up.urlparse(self.path).query)
            self._send(_jdump(_coin((qs.get("sym") or ["BTC"])[0])),
                       "application/json")
        elif self.path.startswith("/api/risk"):
            self._send(_jdump(_risk_overview()), "application/json")
        elif self.path.startswith("/api/health"):
            self._send(_jdump(_health()), "application/json")
        elif self.path.startswith("/api/correlation"):
            from urllib.parse import urlparse as _up7, parse_qs as _pq7
            _q7 = _pq7(_up7(self.path).query)
            self._send(_jdump(_corr(int(_q7.get("n", ["7"])[0]),
                                    int(_q7.get("days", ["30"])[0]))),
                       "application/json")
        elif self.path.startswith("/api/orderbook"):
            from urllib.parse import urlparse as _up5, parse_qs as _pq5
            _q5 = _pq5(_up5(self.path).query)
            self._send(_jdump(_l2book(_q5.get("coin", ["BTC"])[0],
                                      int(_q5.get("depth", ["8"])[0]))),
                       "application/json")
        elif self.path.startswith("/api/funding"):
            from urllib.parse import urlparse as _up6, parse_qs as _pq6
            _q6 = _pq6(_up6(self.path).query)
            self._send(_jdump(_funding(int(_q6.get("n", ["8"])[0]))),
                       "application/json")
        elif self.path.startswith("/api/watchlist"):
            from urllib.parse import urlparse as _up4, parse_qs as _pq4
            _q4 = _pq4(_up4(self.path).query)
            self._send(_jdump(_mkt_watchlist(int(_q4.get("n", ["12"])[0]),
                                             int(_q4.get("movers", ["6"])[0]))),
                       "application/json")
        elif self.path.startswith("/api/candles"):
            from urllib.parse import urlparse as _up3, parse_qs as _pq3
            _q3 = _pq3(_up3(self.path).query)
            self._send(_jdump(_candles(_q3.get("coin", ["BTC"])[0],
                                       _q3.get("tf", ["15m"])[0],
                                       int(_q3.get("n", ["200"])[0]))),
                       "application/json")
        elif self.path.startswith("/api/graph"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            coin = (q.get("coin", ["BTC"])[0] or "BTC").upper()
            try:
                from hl import graph, intel, signals
                g = graph.build(coin)
                g["intel"] = intel.get(coin)   # the deep scored report, if we have one
                try:
                    g["signals"] = signals.coin_signals(coin)  # ranked, fee-aware factor set
                except Exception as se:
                    g["signals"] = {"error": str(se), "signals": [], "composite": None}
                self._send(_jdump(g), "application/json")
            except Exception as e:
                self._send(_jdump({"error": str(e), "coin": coin, "nodes": [], "edges": []}),
                           "application/json")
        elif self.path.startswith("/vendor/"):
            # static assets (three.min.js etc.) — served from scripts/vendor
            import re as _re
            name = _re.sub(r"[^a-zA-Z0-9._-]", "", self.path.split("/vendor/", 1)[1].split("?")[0])
            f = Path(__file__).resolve().parent / "vendor" / name
            if f.exists() and f.suffix in (".js", ".css", ".png", ".jpg", ".webp", ".geojson", ".json"):
                ct = {"js": "application/javascript", "css": "text/css",
                      "png": "image/png", "jpg": "image/jpeg", "webp": "image/webp",
                      "geojson": "application/json", "json": "application/json"}[f.suffix[1:]]
                self._send(f.read_bytes(), ct)
            else:
                self.send_response(404); self.end_headers()
        else:
            # Serve the pro terminal front-end from disk, read per request so the
            # UI can be iterated without restarting the server. Falls back to the
            # original inline PAGE if the file is missing.
            term = Path(__file__).resolve().parent / "terminal.html"
            if term.exists():
                self._send(term.read_text(encoding="utf-8"), "text/html; charset=utf-8")
            else:
                self._send(PAGE, "text/html; charset=utf-8")


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"dashboard on http://localhost:{PORT}   (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
