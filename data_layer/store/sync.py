"""Keep the unified store current from the legacy databases.

WHY THIS EXISTS
---------------
The 8 running collectors still write to the old 14 files. Rather than edit
live collectors (which risks breaking data collection), this service copies
NEW rows from the legacy files into data/store.db.

- Read-only on legacy files. It can never corrupt them.
- Idempotent: tracks a high-water mark per table, only copies what's new.
- Safe to run repeatedly or as a loop.

Once new collectors write directly to the store, the legacy tables they
replace can be dropped from SYNCS and the old collector retired.

Run once:   python data_layer/store/sync.py
Run a loop: python data_layer/store/sync.py --interval 60
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

LEGACY = store.ROOT / "data"


def _ro(name):
    p = LEGACY / name
    if not p.exists():
        return None
    try:
        return sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error:
        return None


def _watermark(conn, table, ts_col="ts_ms"):
    """Highest timestamp already in the store for this table."""
    r = conn.execute(f'SELECT MAX({ts_col}) FROM "{table}"').fetchone()
    return r[0] if r and r[0] is not None else 0


# ---------------------------------------------------------------- syncers
# Each returns (rows_read, rows_written).

def sync_quotes(new):
    old = _ro("venues.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "quote")
    vmap = {r[0]: store.venue_id(new, r[1]) for r in old.execute("SELECT id,name FROM venues")}
    amap = {r[0]: store.asset_id(new, r[1]) for r in old.execute("SELECT id,name FROM coins")}
    rows = []
    for r in old.execute(
        "SELECT ts_ms,venue_id,coin_id,bid,ask,mid,vol,suspect FROM prices WHERE ts_ms>?",
        (wm,),
    ):
        v, a = vmap.get(r[1]), amap.get(r[2])
        if v is None or a is None:
            continue
        rows.append((r[0], v, a, r[3], r[4], r[5], r[6], r[7] or 0))
    w = store.insert_many(new, "quote",
        ["ts_ms", "venue_id", "asset_id", "bid", "ask", "mid", "vol", "suspect"], rows)
    old.close()
    return len(rows), w


def sync_perp_state(new):
    old = _ro("venues.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "perp_state")
    hl = store.venue_id(new, "hyperliquid", kind="perp")
    rows = [(r[0], hl, store.asset_id(new, r[1]), r[2], r[3], r[4], r[5], r[6], None, r[7])
            for r in old.execute(
                "SELECT ts_ms,coin,mid,mark,oracle,funding_hourly,oi_base,vol24 "
                "FROM hl_state WHERE ts_ms>?", (wm,))]
    w = store.insert_many(new, "perp_state",
        ["ts_ms", "venue_id", "asset_id", "mid", "mark", "oracle",
         "funding_hourly", "oi_base", "oi_usd", "vol24"], rows)
    old.close()
    return len(rows), w


def sync_positioning(new, loaded_since=None):
    """Since 2026-09-13 backfill_positioning.py reads Binance's daily ARCHIVE,
    so it routinely writes rows OLDER than the newest one (a day published
    late, a retried day, a deeper --days run). A timestamp watermark alone
    would skip those forever. So: copy a row if it is past the watermark OR
    its (coin, day) was loaded since the last successful sync of this table,
    per positioning_days.loaded_ms. Pass loaded_since=0 to re-copy every day
    (safe: INSERT OR IGNORE)."""
    old = _ro("venues.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "positioning")
    if loaded_since is None:
        r = new.execute("SELECT MAX(ts_ms) FROM collector_run "
                        "WHERE source_name='sync:positioning' AND ok=1").fetchone()
        # 2-minute overlap: a day loaded while the previous sync was reading
        # would otherwise carry a loaded_ms just under that sync's log time
        loaded_since = (r[0] or 0) - 120_000
    has_days = old.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                           "AND name='positioning_days'").fetchone()
    cols = ("SELECT ts_ms,coin,period,oi_coins,oi_usd,long_frac,ls_ratio,"
            "top_long_frac,top_ls_ratio,taker_buy_vol,taker_ratio FROM positioning ")
    if has_days:
        q = old.execute(cols + "WHERE ts_ms>? OR (coin, date(ts_ms/1000,'unixepoch')) IN "
                        "(SELECT coin, day FROM positioning_days WHERE loaded_ms>?)",
                        (wm, loaded_since))
    else:
        q = old.execute(cols + "WHERE ts_ms>?", (wm,))
    bv = store.venue_id(new, "binance", kind="cex")
    rows = [(r[0], bv, store.asset_id(new, r[1]), r[2], r[3], r[4], r[5], r[6],
             r[7], r[8], r[9], r[10]) for r in q]
    w = store.insert_many(new, "positioning",
        ["ts_ms", "venue_id", "asset_id", "period", "oi_coins", "oi_usd",
         "long_frac", "ls_ratio", "top_long_frac", "top_ls_ratio",
         "taker_buy_vol", "taker_ratio"], rows)
    old.close()
    return len(rows), w


def sync_social(new):
    old = _ro("social.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "social_post", "first_seen_ms")
    rows = [(r[0], r[1], r[2], r[4], r[3], r[5], r[6], r[7], r[8], r[9])
            for r in old.execute(
                "SELECT source,channel,post_id,first_seen_ms,publish_ts,author,text,"
                "url,stated_sentiment,extra FROM posts WHERE first_seen_ms>?", (wm,))]
    w = store.insert_many(new, "social_post",
        ["source_name", "channel", "post_id", "published_ts", "first_seen_ms",
         "author", "text", "url", "stated_sentiment", "extra"], rows)
    old.close()
    return len(rows), w


def sync_documents(new):
    old = _ro("events.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "document", "first_seen_ms")
    rows = [(r[0], r[3], r[4], r[5], r[2], r[6])
            for r in old.execute(
                "SELECT source,kind,title,url,publish_ts,first_seen_ms,extra "
                "FROM events WHERE first_seen_ms>?", (wm,))]
    w = store.insert_many(new, "document",
        ["source_name", "url", "published_ts", "first_seen_ms", "title", "extra"], rows)
    old.close()
    return len(rows), w


def sync_cv_features(new):
    """The 17 features that already exist, split across their families."""
    old = _ro("venues.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "feat_xvenue")
    src = list(old.execute(
        "SELECT ts_ms,coin,cp,n_venues,n_stale,hl_dev_bps,disp_iqr_bps,cp_perp,cp_spot,"
        "sp_basis_bps,best_spread_bps,hl_spread_bps,hhi,hl_vol_share,credible_vol_usd,"
        "premium_krw_bps,premium_inr_bps FROM cv_features WHERE ts_ms>?", (wm,)))
    if not src:
        old.close()
        return 0, 0
    xv, fl, pr, dv, lq = [], [], [], [], []
    for r in src:
        aid = store.asset_id(new, r[1])
        xv.append((r[0], aid, r[3], r[4], r[6], r[5], r[15], r[16]))
        fl.append((r[0], aid, r[12], r[13], r[14]))
        pr.append((r[0], aid, r[2]))
        dv.append((r[0], aid, r[9]))
        lq.append((r[0], aid, r[10], r[11]))
    w = 0
    w += store.insert_many(new, "feat_xvenue",
        ["ts_ms", "asset_id", "n_venues", "n_stale", "disp_iqr_bps", "hl_dev_bps",
         "premium_krw_bps", "premium_inr_bps"], xv, replace=True)
    w += store.insert_many(new, "feat_flow",
        ["ts_ms", "asset_id", "hhi", "hl_vol_share", "credible_vol_usd"], fl, replace=True)
    w += store.insert_many(new, "feat_price", ["ts_ms", "asset_id", "cp"], pr, replace=True)
    w += store.insert_many(new, "feat_deriv", ["ts_ms", "asset_id", "sp_basis_bps"], dv, replace=True)
    w += store.insert_many(new, "feat_liq",
        ["ts_ms", "asset_id", "spread_bps", "spread_hl_rel"], lq, replace=True)
    old.close()
    return len(src), w


def sync_universe_pit(new):
    old = _ro("venues.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "universe_pit")
    rows = [(r[0], store.asset_id(new, r[1]), r[2], r[3], r[4])
            for r in old.execute(
                "SELECT ts_ms,coin,on_hl,n_venues,hl_vol_usd FROM universe_pit WHERE ts_ms>?",
                (wm,))]
    w = store.insert_many(new, "universe_pit",
        ["ts_ms", "asset_id", "on_hl", "n_venues", "hl_vol_usd"], rows, replace=True)
    old.close()
    return len(rows), w


def sync_signal_log(new):
    old = _ro("tracker.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "signal_log")
    rows = [(r[0], r[1], store.asset_id(new, r[2]), r[3], r[4], r[5], r[6], r[7],
             r[8], r[9], r[10])
            for r in old.execute(
                "SELECT ts_ms,as_of,coin,mode,dir,score,exp_move,entry_px,btc_entry,"
                "matured,exit_px FROM signal_log WHERE ts_ms>?", (wm,))]
    w = store.insert_many(new, "signal_log",
        ["ts_ms", "as_of", "asset_id", "mode", "direction", "score", "exp_move",
         "entry_px", "btc_entry", "matured", "exit_px"], rows)
    old.close()
    return len(rows), w


def sync_gate_log(new):
    old = _ro("gate_exp.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "gate_log")
    rows = [(r[0], r[1], store.asset_id(new, r[2]), r[3], r[4], r[5], r[6], r[7],
             r[8], r[9], r[10])
            for r in old.execute(
                "SELECT ts_ms,as_of,coin,allowed,block_reason,entry_px,btc_entry,beta,"
                "matured,exit_px,btc_exit FROM gate_log WHERE ts_ms>?", (wm,))]
    w = store.insert_many(new, "gate_log",
        ["ts_ms", "as_of", "asset_id", "allowed", "block_reason", "entry_px",
         "btc_entry", "beta", "matured", "exit_px", "btc_exit"], rows)
    old.close()
    return len(rows), w


def sync_equity(new):
    old = _ro("paper.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "equity_curve")
    rows = [tuple(r) for r in old.execute(
        "SELECT ts_ms,total_pnl,realized,unrealized,n_open FROM equity_curve WHERE ts_ms>?",
        (wm,))]
    w = store.insert_many(new, "equity_curve",
        ["ts_ms", "total_pnl", "realized", "unrealized", "n_open"], rows, replace=True)
    old.close()
    return len(rows), w


def sync_alerts(new):
    old = _ro("triggers.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "alert")
    rows = [(r[0], store.asset_id(new, r[1]), r[2], r[3])
            for r in old.execute(
                "SELECT ts_ms,coin,level,message FROM alerts WHERE ts_ms>?", (wm,))]
    w = store.insert_many(new, "alert", ["ts_ms", "asset_id", "level", "message"], rows)
    old.close()
    return len(rows), w


def sync_listing_changes(new):
    old = _ro("events.db")
    if old is None:
        return 0, 0
    wm = _watermark(new, "listing_change")
    hl = store.venue_id(new, "hyperliquid", kind="perp")
    rows = [(r[0], hl, store.asset_id(new, r[1]), r[2], r[3])
            for r in old.execute(
                "SELECT ts_ms,coin,change,detail FROM hl_universe_changes WHERE ts_ms>?",
                (wm,))]
    w = store.insert_many(new, "listing_change",
        ["ts_ms", "venue_id", "asset_id", "change", "detail"], rows)
    old.close()
    return len(rows), w


SYNCS = [
    ("quote",          sync_quotes),
    ("perp_state",     sync_perp_state),
    ("positioning",    sync_positioning),
    ("social_post",    sync_social),
    ("document",       sync_documents),
    ("feat_*",         sync_cv_features),
    ("universe_pit",   sync_universe_pit),
    ("signal_log",     sync_signal_log),
    ("gate_log",       sync_gate_log),
    ("equity_curve",   sync_equity),
    ("alert",          sync_alerts),
    ("listing_change", sync_listing_changes),
]


def run_once(new, verbose=True):
    total_r = total_w = 0
    for name, fn in SYNCS:
        t0 = time.time()
        try:
            r, w = fn(new)
            new.commit()
            store.log_run(new, f"sync:{name}", True, w, int((time.time() - t0) * 1000))
            total_r += r
            total_w += w
            if verbose and r:
                print(f"  {name:<14} +{w:,} rows  ({(time.time()-t0):.1f}s)")
        except Exception as e:  # noqa: BLE001
            new.commit()
            store.log_run(new, f"sync:{name}", False, 0,
                          int((time.time() - t0) * 1000), str(e)[:200])
            print(f"  {name:<14} ERROR: {str(e)[:120]}")
    new.commit()
    return total_r, total_w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=0,
                    help="seconds between syncs; 0 = run once and exit")
    a = ap.parse_args()

    new = store.init()
    if a.interval <= 0:
        print("sync: one pass")
        r, w = run_once(new)
        print(f"sync: {w:,} new rows written")
        new.close()
        return

    print(f"sync: looping every {a.interval:.0f}s (ctrl-C to stop)")
    while True:
        t0 = time.time()
        _, w = run_once(new, verbose=False)
        print(f"[{time.strftime('%H:%M:%S')}] +{w:,} rows ({time.time()-t0:.1f}s)", flush=True)
        time.sleep(max(1.0, a.interval - (time.time() - t0)))


if __name__ == "__main__":
    main()
