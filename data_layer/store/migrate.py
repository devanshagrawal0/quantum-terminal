"""Migrate the 14 legacy SQLite files into the unified store.

Read-only on the legacy files. Idempotent — safe to re-run.
Every table reports rows-read vs rows-written so nothing is silently lost.

Run:  python data_layer/store/migrate.py
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

ROOT = store.ROOT
LEGACY = ROOT / "data"


def _open_ro(name):
    p = LEGACY / name
    if not p.exists():
        return None
    try:
        return sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error:
        return None


def _has(conn, table):
    if conn is None:
        return False
    r = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return r is not None


REPORT: list[tuple] = []


def _report(src, dst, read, wrote, note=""):
    REPORT.append((src, dst, read, wrote, note))
    print(f"  {src:<28} -> {dst:<16} read={read:<9} wrote={wrote:<9} {note}")


# ------------------------------------------------------------------ venues

def mig_venues(new):
    """venues.db: prices, hl_state, positioning, cv_features, symbol_map."""
    old = _open_ro("venues.db")
    if old is None:
        return
    print("\nvenues.db")

    # dimension maps: legacy integer ids -> canonical ids
    vmap, amap = {}, {}
    if _has(old, "venues"):
        for r in old.execute("SELECT id,name FROM venues"):
            vmap[r[0]] = store.venue_id(new, r[1], kind="cex")
    if _has(old, "coins"):
        for r in old.execute("SELECT id,name FROM coins"):
            amap[r[0]] = store.asset_id(new, r[1])
    new.commit()
    print(f"  mapped {len(vmap)} venues, {len(amap)} assets")

    if _has(old, "symbol_map"):
        rows, n, missing = [], 0, 0
        for r in old.execute(
            "SELECT venue,coin,symbol,quote,first_seen_ms,last_seen_ms FROM symbol_map"
        ):
            n += 1
            vid = store.venue_id(new, r[0])
            aid = store.asset_id(new, r[1])
            sym = r[2]
            if not sym:
                # LEGACY GAP: the venue's real symbol string was never stored.
                # Fall back to the coin name so the row survives; collectors
                # overwrite this with the true venue symbol on next run.
                sym = r[1]
                missing += 1
            rows.append((vid, aid, sym, r[3], 1.0, r[4], r[5]))
        w = store.insert_many(
            new, "venue_symbol",
            ["venue_id", "asset_id", "symbol", "quote", "multiplier", "first_seen_ms", "last_seen_ms"],
            rows, replace=True)
        new.commit()
        note = f"WARNING: {missing}/{n} had NULL venue symbol (legacy gap)" if missing else ""
        _report("symbol_map", "venue_symbol", n, w, note)

    if _has(old, "prices"):
        n = old.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        wrote, batch = 0, []
        for r in old.execute("SELECT ts_ms,venue_id,coin_id,bid,ask,mid,vol,suspect FROM prices"):
            v, a = vmap.get(r[1]), amap.get(r[2])
            if v is None or a is None:
                continue
            batch.append((r[0], v, a, r[3], r[4], r[5], r[6], r[7] or 0))
            if len(batch) >= 50_000:
                wrote += store.insert_many(
                    new, "quote", ["ts_ms", "venue_id", "asset_id", "bid", "ask", "mid", "vol", "suspect"], batch)
                new.commit(); batch = []
        if batch:
            wrote += store.insert_many(
                new, "quote", ["ts_ms", "venue_id", "asset_id", "bid", "ask", "mid", "vol", "suspect"], batch)
        new.commit()
        _report("prices", "quote", n, wrote)

    if _has(old, "hl_state"):
        hl = store.venue_id(new, "hyperliquid", kind="perp")
        n, rows = 0, []
        for r in old.execute(
            "SELECT ts_ms,coin,mid,mark,oracle,funding_hourly,oi_base,vol24 FROM hl_state"
        ):
            n += 1
            rows.append((r[0], hl, store.asset_id(new, r[1]), r[2], r[3], r[4], r[5], r[6], None, r[7]))
            if len(rows) >= 50_000:
                store.insert_many(new, "perp_state",
                    ["ts_ms", "venue_id", "asset_id", "mid", "mark", "oracle",
                     "funding_hourly", "oi_base", "oi_usd", "vol24"], rows)
                new.commit(); rows = []
        w = store.insert_many(new, "perp_state",
            ["ts_ms", "venue_id", "asset_id", "mid", "mark", "oracle",
             "funding_hourly", "oi_base", "oi_usd", "vol24"], rows) if rows else 0
        new.commit()
        _report("hl_state", "perp_state", n, n)

    if _has(old, "positioning"):
        bv = store.venue_id(new, "binance", kind="cex")
        n, rows = 0, []
        for r in old.execute(
            "SELECT ts_ms,coin,period,oi_coins,oi_usd,long_frac,ls_ratio,"
            "top_long_frac,top_ls_ratio,taker_buy_vol,taker_ratio FROM positioning"
        ):
            n += 1
            rows.append((r[0], bv, store.asset_id(new, r[1]), r[2], r[3], r[4],
                         r[5], r[6], r[7], r[8], r[9], r[10]))
        w = store.insert_many(new, "positioning",
            ["ts_ms", "venue_id", "asset_id", "period", "oi_coins", "oi_usd",
             "long_frac", "ls_ratio", "top_long_frac", "top_ls_ratio",
             "taker_buy_vol", "taker_ratio"], rows)
        new.commit()
        _report("positioning", "positioning", n, w)

    # the 17 features that already exist, for 0.9 days
    if _has(old, "cv_features"):
        n, xv, fl = 0, [], []
        for r in old.execute(
            "SELECT ts_ms,coin,cp,n_venues,n_stale,hl_dev_bps,disp_iqr_bps,cp_perp,"
            "cp_spot,sp_basis_bps,best_spread_bps,hl_spread_bps,hhi,hl_vol_share,"
            "credible_vol_usd,premium_krw_bps,premium_inr_bps FROM cv_features"
        ):
            n += 1
            aid = store.asset_id(new, r[1])
            xv.append((r[0], aid, r[3], r[4], r[6], r[5], r[15], r[16]))
            fl.append((r[0], aid, r[12], r[13], r[14]))
        w1 = store.insert_many(new, "feat_xvenue",
            ["ts_ms", "asset_id", "n_venues", "n_stale", "disp_iqr_bps",
             "hl_dev_bps", "premium_krw_bps", "premium_inr_bps"], xv, replace=True)
        w2 = store.insert_many(new, "feat_flow",
            ["ts_ms", "asset_id", "hhi", "hl_vol_share", "credible_vol_usd"], fl, replace=True)
        # sp_basis + cp belong to their own families
        pr = [(r[0], store.asset_id(new, r[1]), r[2]) for r in
              old.execute("SELECT ts_ms,coin,cp FROM cv_features")]
        w3 = store.insert_many(new, "feat_price", ["ts_ms", "asset_id", "cp"], pr, replace=True)
        dv = [(r[0], store.asset_id(new, r[1]), r[2]) for r in
              old.execute("SELECT ts_ms,coin,sp_basis_bps FROM cv_features")]
        w4 = store.insert_many(new, "feat_deriv", ["ts_ms", "asset_id", "sp_basis_bps"], dv, replace=True)
        lq = [(r[0], store.asset_id(new, r[1]), r[2], r[3]) for r in
              old.execute("SELECT ts_ms,coin,best_spread_bps,hl_spread_bps FROM cv_features")]
        w5 = store.insert_many(new, "feat_liq",
            ["ts_ms", "asset_id", "spread_bps", "spread_hl_rel"], lq, replace=True)
        new.commit()
        _report("cv_features", "feat_* (5 tables)", n, w1 + w2 + w3 + w4 + w5,
                "split by family")
    old.close()


# ------------------------------------------------------------------ social

def mig_social(new):
    old = _open_ro("social.db")
    if old is None or not _has(old, "posts"):
        return
    print("\nsocial.db")
    n, rows = 0, []
    for r in old.execute(
        "SELECT source,channel,post_id,first_seen_ms,publish_ts,author,text,url,"
        "stated_sentiment,extra FROM posts"
    ):
        n += 1
        rows.append((r[0], r[1], r[2], r[4], r[3], r[5], r[6], r[7], r[8], r[9]))
    w = store.insert_many(new, "social_post",
        ["source_name", "channel", "post_id", "published_ts", "first_seen_ms",
         "author", "text", "url", "stated_sentiment", "extra"], rows)
    new.commit()
    _report("posts", "social_post", n, w)
    old.close()


# ------------------------------------------------------------------ events

def mig_events(new):
    old = _open_ro("events.db")
    if old is None or not _has(old, "events"):
        return
    print("\nevents.db")
    n, rows = 0, []
    for r in old.execute(
        "SELECT source,kind,title,url,publish_ts,first_seen_ms,extra FROM events"
    ):
        n += 1
        rows.append((r[0], r[3], r[4], r[5], r[2], r[6]))
    w = store.insert_many(new, "document",
        ["source_name", "url", "published_ts", "first_seen_ms", "title", "extra"], rows)
    new.commit()
    _report("events", "document", n, w)
    old.close()


# ------------------------------------------------------------ unlocks (calendar)

def mig_unlocks(new):
    old = _open_ro("unlocks.db")
    if old is None or not _has(old, "unlocks"):
        return
    print("\nunlocks.db")
    now = int(time.time() * 1000)
    n, rows = 0, []
    for r in old.execute("SELECT gecko_id,slug,next_ts,next_days,next_desc,updated_ms FROM unlocks"):
        n += 1
        if not r[2]:
            continue
        aid = store.asset_id(new, (r[1] or r[0] or "").upper(), coingecko_id=r[0])
        ts = int(r[2]) * 1000 if int(r[2]) < 10_000_000_000 else int(r[2])
        rows.append(("unlock", r[1], aid, ts, "day", 0, r[4], r[5] or now, r[5] or now))
    w = store.insert_many(new, "scheduled_event",
        ["kind", "entity", "asset_id", "scheduled_ts", "ts_precision", "confirmed",
         "source_url", "valid_from", "observed_at"], rows)
    new.commit()
    _report("unlocks", "scheduled_event", n, w, "NOTE: no unlock SIZES in legacy data")
    old.close()


# ------------------------------------------------- trading / predictions / journal

def mig_trading(new):
    print("\ntrading + learning")
    # Legacy ids are TEXT hashes -> keep them in legacy_id, use integer PKs here.
    old = _open_ro("paper.db")
    if old and _has(old, "positions"):
        n, rows = 0, []
        for r in old.execute(
            "SELECT id,opened_ms,closed_ms,coin,side,leverage,notional_usd,margin_usd,"
            "entry_px,exit_px,mark_px,btc_entry_px,stop_px,target_px,hold_hours,"
            "entry_fee,exit_fee,pnl_usd,funding_usd,status,exit_reason,is_hedge,tag,thesis "
            "FROM positions"
        ):
            n += 1
            fees = (r[15] or 0) + (r[16] or 0)
            rows.append((r[0], r[1], r[2], store.asset_id(new, r[3]), r[4], r[6],
                         r[8], r[9], r[10], r[11], r[5], r[7], r[12], r[13], r[14],
                         r[18], fees, r[17], r[19], r[20], r[21], r[22], r[23]))
        w = store.insert_many(new, "position",
            ["legacy_id", "opened_ms", "closed_ms", "asset_id", "side", "notional_usd",
             "entry_px", "exit_px", "mark_px", "btc_entry_px", "leverage", "margin_usd",
             "stop_px", "target_px", "hold_hours", "funding_usd", "fees_paid", "pnl_usd",
             "status", "exit_reason", "is_hedge", "tag", "thesis_text"], rows)
        new.commit()
        _report("paper.positions", "position", n, w)
        old.close()

    # predictions.db carries RESOLVED outcomes — that's the learning-loop data.
    old = _open_ro("predictions.db")
    if old and _has(old, "predictions"):
        n, rows = 0, []
        for r in old.execute(
            "SELECT id,created_ms,source,coin,direction,horizon_h,entry_px,confidence,"
            "size_pct,invalidation_px,thesis,state_json FROM predictions"
        ):
            n += 1
            rows.append((r[0], r[1], store.asset_id(new, r[3]), r[2], r[4], r[5],
                         r[6], r[7], r[8], r[9], r[10], r[11]))
        w = store.insert_many(new, "thesis",
            ["legacy_id", "created_ms", "asset_id", "source", "direction", "horizon_h",
             "entry_px", "confidence", "size_pct", "invalidation_px", "reasoning",
             "features_json"], rows)
        new.commit()
        _report("predictions", "thesis", n, w)

        # grade them: join legacy_id -> new integer id
        idmap = {r[0]: r[1] for r in new.execute(
            "SELECT legacy_id,id FROM thesis WHERE legacy_id IS NOT NULL")}
        n2, rows2 = 0, []
        for r in old.execute(
            "SELECT id,resolved_ms,exit_px,ret_pct,funding_pct,net_ret_pct,"
            "mkt_ret_pct,excess_pct,outcome,notes FROM predictions WHERE resolved_ms IS NOT NULL"
        ):
            tid = idmap.get(r[0])
            if tid is None:
                continue
            n2 += 1
            correct = 1 if (r[7] or 0) > 0 else 0
            rows2.append((tid, r[1], r[2], r[3], r[4], r[5], r[6], r[7], correct, r[8], r[9]))
        w2 = store.insert_many(new, "thesis_outcome",
            ["thesis_id", "graded_ms", "exit_px", "ret_pct", "funding_pct",
             "net_ret_pct", "mkt_ret_pct", "excess_pct", "correct", "outcome", "lesson"],
            rows2, replace=True)
        new.commit()
        _report("predictions(resolved)", "thesis_outcome", n2, w2, "graded predictions")
        old.close()

    old = _open_ro("journal.db")
    if old and _has(old, "reviews"):
        pmap = {r[0]: r[1] for r in new.execute(
            "SELECT legacy_id,id FROM position WHERE legacy_id IS NOT NULL")}
        n, rows = 0, []
        for r in old.execute(
            "SELECT position_id,recorded_ms,pnl_usd,worked,outcome,lesson,exit_reason "
            "FROM reviews"
        ):
            n += 1
            rows.append((pmap.get(r[0]), r[1], r[2], 1 if r[3] else 0, r[4], r[5], r[6]))
        w = store.insert_many(new, "position_review",
            ["position_id", "recorded_ms", "pnl_usd", "worked", "outcome", "lesson",
             "exit_reason"], rows)
        new.commit()
        _report("journal.reviews", "position_review", n, w)
        old.close()


def mig_universe(new):
    """Point-in-time universe + listing changes — the survivorship defence."""
    print("\nuniverse / listings")
    old = _open_ro("venues.db")
    if old and _has(old, "universe_pit"):
        n, rows = 0, []
        for r in old.execute("SELECT ts_ms,coin,on_hl,n_venues,hl_vol_usd FROM universe_pit"):
            n += 1
            rows.append((r[0], store.asset_id(new, r[1]), r[2], r[3], r[4]))
        w = store.insert_many(new, "universe_pit",
            ["ts_ms", "asset_id", "on_hl", "n_venues", "hl_vol_usd"], rows, replace=True)
        new.commit()
        _report("universe_pit", "universe_pit", n, w, "survivorship defence")
    if old:
        old.close()

    old = _open_ro("events.db")
    if old:
        hl = store.venue_id(new, "hyperliquid", kind="perp")
        if _has(old, "hl_universe_changes"):
            n, rows = 0, []
            for r in old.execute("SELECT ts_ms,coin,change,detail FROM hl_universe_changes"):
                n += 1
                rows.append((r[0], hl, store.asset_id(new, r[1]), r[2], r[3]))
            w = store.insert_many(new, "listing_change",
                ["ts_ms", "venue_id", "asset_id", "change", "detail"], rows)
            new.commit()
            _report("hl_universe_changes", "listing_change", n, w)
        if _has(old, "hl_universe_state"):
            n, rows = 0, []
            for r in old.execute("SELECT coin,max_leverage,delisted FROM hl_universe_state"):
                n += 1
                rows.append((hl, store.asset_id(new, r[0]), r[1], r[2] or 0))
            w = store.insert_many(new, "listing_state",
                ["venue_id", "asset_id", "max_leverage", "delisted"], rows, replace=True)
            new.commit()
            _report("hl_universe_state", "listing_state", n, w)
        old.close()

    old = _open_ro("hl.db")
    if old and _has(old, "gaps"):
        n, rows = 0, []
        for r in old.execute(
            "SELECT ts_ms,coin,venue,hl_bid,hl_ask,hl_mid,hl_mark,hl_oracle,"
            "v_bid,v_ask,v_mid,gap_bps FROM gaps"
        ):
            n += 1
            rows.append((r[0], store.asset_id(new, r[1]), store.venue_id(new, r[2]),
                         r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11]))
        w = store.insert_many(new, "venue_gap",
            ["ts_ms", "asset_id", "venue_id", "hl_bid", "hl_ask", "hl_mid", "hl_mark",
             "hl_oracle", "v_bid", "v_ask", "v_mid", "gap_bps"], rows)
        new.commit()
        _report("hl.gaps", "venue_gap", n, w)
    if old:
        old.close()


def mig_signals(new):
    """Our own signal + gate history. signal_log is our LONGEST series."""
    print("\nsignals / decisions")
    old = _open_ro("tracker.db")
    if old and _has(old, "signal_log"):
        n, rows = 0, []
        for r in old.execute(
            "SELECT ts_ms,as_of,coin,mode,dir,score,exp_move,entry_px,btc_entry,"
            "matured,exit_px FROM signal_log"
        ):
            n += 1
            rows.append((r[0], r[1], store.asset_id(new, r[2]), r[3], r[4], r[5],
                         r[6], r[7], r[8], r[9], r[10]))
        w = store.insert_many(new, "signal_log",
            ["ts_ms", "as_of", "asset_id", "mode", "direction", "score", "exp_move",
             "entry_px", "btc_entry", "matured", "exit_px"], rows)
        new.commit()
        _report("signal_log", "signal_log", n, w, "295 days - our longest series")
        old.close()

    old = _open_ro("gate_exp.db")
    if old and _has(old, "gate_log"):
        n, rows = 0, []
        for r in old.execute(
            "SELECT ts_ms,as_of,coin,allowed,block_reason,entry_px,btc_entry,beta,"
            "matured,exit_px,btc_exit FROM gate_log"
        ):
            n += 1
            rows.append((r[0], r[1], store.asset_id(new, r[2]), r[3], r[4], r[5],
                         r[6], r[7], r[8], r[9], r[10]))
        w = store.insert_many(new, "gate_log",
            ["ts_ms", "as_of", "asset_id", "allowed", "block_reason", "entry_px",
             "btc_entry", "beta", "matured", "exit_px", "btc_exit"], rows)
        new.commit()
        _report("gate_log", "gate_log", n, w)
        old.close()

    old = _open_ro("triggers.db")
    if old:
        if _has(old, "triggers"):
            rows = [(r[0], store.asset_id(new, r[1]), r[2], r[3], r[4], r[5], r[6],
                     r[7], r[8], r[9], r[10])
                    for r in old.execute(
                        "SELECT created_ms,coin,kind,side,pct,level,floor,peak,trough,"
                        "stop_pct,target_pct FROM triggers")]
            w = store.insert_many(new, "trigger_rule",
                ["created_ms", "asset_id", "kind", "side", "pct", "level", "floor",
                 "peak", "trough", "stop_pct", "target_pct"], rows)
            new.commit(); _report("triggers", "trigger_rule", len(rows), w)
        if _has(old, "alerts"):
            rows = [(r[0], store.asset_id(new, r[1]), r[2], r[3])
                    for r in old.execute("SELECT ts_ms,coin,level,message FROM alerts")]
            w = store.insert_many(new, "alert",
                ["ts_ms", "asset_id", "level", "message"], rows)
            new.commit(); _report("alerts", "alert", len(rows), w)
        if _has(old, "risk_state"):
            rows = [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in old.execute(
                "SELECT ts_ms,bp_score,bp_level,crash_score,crash_level,detail FROM risk_state")]
            w = store.insert_many(new, "risk_state",
                ["ts_ms", "bp_score", "bp_level", "crash_score", "crash_level", "detail"], rows)
            new.commit(); _report("risk_state", "risk_state", len(rows), w)
        old.close()

    old = _open_ro("watchlist.db")
    if old and _has(old, "watchlist"):
        rows = [(store.asset_id(new, r[0]), r[1], r[2], r[3], r[4], r[5], r[6], r[7],
                 r[8], r[9], r[10])
                for r in old.execute(
                    "SELECT coin,added_ms,added_px,kind,bull_side,bear_side,lean,quant,"
                    "status,resolved_ms,winner FROM watchlist")]
        w = store.insert_many(new, "watchlist",
            ["asset_id", "added_ms", "added_px", "kind", "bull_side", "bear_side",
             "lean", "quant", "status", "resolved_ms", "winner"], rows)
        new.commit(); _report("watchlist", "watchlist", len(rows), w)
        old.close()


def mig_account_research(new):
    print("\naccount / research")
    old = _open_ro("paper.db")
    if old:
        if _has(old, "equity_curve"):
            rows = [tuple(r) for r in old.execute(
                "SELECT ts_ms,total_pnl,realized,unrealized,n_open FROM equity_curve")]
            w = store.insert_many(new, "equity_curve",
                ["ts_ms", "total_pnl", "realized", "unrealized", "n_open"], rows, replace=True)
            new.commit(); _report("equity_curve", "equity_curve", len(rows), w)
        if _has(old, "account"):
            rows = [(r[3], r[0], r[1], r[2]) for r in old.execute(
                "SELECT balance,realized_pnl,fees_paid,created_ms FROM account")]
            w = store.insert_many(new, "account_state",
                ["ts_ms", "balance", "realized_pnl", "fees_paid"], rows, replace=True)
            new.commit(); _report("paper.account", "account_state", len(rows), w)
        old.close()

    old = _open_ro("research.db")
    if old and _has(old, "notes"):
        rows = [(store.asset_id(new, r[0]), r[1], r[2], r[3], r[4], r[5], r[6],
                 r[7], r[8], r[9], r[10])
                for r in old.execute(
                    "SELECT coin,created_ms,headline,what_it_is,sector,catalysts,"
                    "sentiment,bull,bear,verdict,confidence FROM notes")]
        w = store.insert_many(new, "research_note",
            ["asset_id", "created_ms", "headline", "what_it_is", "sector", "catalysts",
             "sentiment", "bull", "bear", "verdict", "confidence"], rows)
        new.commit(); _report("research.notes", "research_note", len(rows), w)
        old.close()

    old = _open_ro("intel.db")
    if old and _has(old, "reports"):
        rows = [(store.asset_id(new, r[0]), r[1], r[2], r[3], r[4], r[5], r[6],
                 r[7], r[8], r[9], r[10], r[11])
                for r in old.execute(
                    "SELECT coin,updated_ms,short_score,long_score,sentiment_short,"
                    "sentiment_long,catalyst_strength,sector_heat,influence,conviction,"
                    "short_term,long_term FROM reports")]
        w = store.insert_many(new, "intel_report",
            ["asset_id", "updated_ms", "short_score", "long_score", "sentiment_short",
             "sentiment_long", "catalyst_strength", "sector_heat", "influence",
             "conviction", "short_term", "long_term"], rows, replace=True)
        new.commit(); _report("intel.reports", "intel_report", len(rows), w)
        old.close()

    old = _open_ro("journal.db")
    if old and _has(old, "entries"):
        pmap = {r[0]: r[1] for r in new.execute(
            "SELECT legacy_id,id FROM position WHERE legacy_id IS NOT NULL")}
        rows = [(pmap.get(r[0]), store.asset_id(new, r[1]), r[2], r[3], r[4], r[5])
                for r in old.execute(
                    "SELECT position_id,coin,side,snapshot_ms,thesis,signals FROM entries")]
        w = store.insert_many(new, "position_entry_note",
            ["position_id", "asset_id", "side", "snapshot_ms", "thesis", "signals"], rows)
        new.commit(); _report("journal.entries", "position_entry_note", len(rows), w)
        old.close()


def main():
    t0 = time.time()
    print(f"Creating store at {store.DB_PATH}")
    new = store.init()
    print("schema applied\n" + "=" * 78)
    mig_venues(new)
    mig_social(new)
    mig_events(new)
    mig_unlocks(new)
    mig_trading(new)
    mig_universe(new)
    mig_signals(new)
    mig_account_research(new)

    print("=" * 78)
    print(f"\nMIGRATION SUMMARY ({time.time()-t0:.1f}s)")
    tr = sum(r[2] for r in REPORT)
    tw = sum(r[3] for r in REPORT)
    print(f"  total read={tr:,}  written={tw:,}")
    print("\nSTORE CONTENTS (non-empty tables):")
    for t, c in sorted(store.counts(new).items()):
        if c > 0:
            print(f"  {t:<26} {c:>10,}")
    new.commit()
    new.close()


if __name__ == "__main__":
    main()
