"""Keeps the forward score-tracker actually accruing — the daily job behind the
Journal scorecard.

Every cycle it: (1) refreshes the daily price parquet from Hyperliquid (fast, one
candle call per coin) and the daily funding parquet if it has gone stale (slow, so
only ~once a day), (2) refreshes Fear&Greed, (3) records today's live composite
picks (deduped per day), (4) grades any pick whose 10-day hold has matured, and
(5) writes a heartbeat the watchdog reads. Without this running daily the
out-of-sample record never grows and the whole edge rests on one backtest.

    python scripts/tracker_loop.py --every 21600     # every 6h, under the watchdog
    python scripts/tracker_loop.py --once            # one cycle, then exit
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CACHE = ROOT / "data" / "carry_cache"
DAY_MS = 86_400_000
PRICE_PARQUET = CACHE / "daily_365.parquet"
FUNDING_PARQUET = CACHE / "funding_daily_365.parquet"
TAIL_DAYS = 7                   # only fetch the recent tail, then merge onto history


def _log(msg: str) -> None:
    print(f"[{time.strftime('%m-%d %H:%M:%S')}] tracker: {msg}", flush=True)


def _live_coins(info) -> list:
    """Currently-tradable HL perps only. Delisted coins keep their static history in
    the parquet from the one-time backfill — no reason to re-fetch a dead market daily."""
    meta, ctxs = info.meta_and_asset_ctxs()
    live = [(a["name"], float(c.get("dayNtlVlm") or 0))
            for a, c in zip(meta["universe"], ctxs) if not a.get("isDelisted")]
    live.sort(key=lambda x: -x[1])
    return [n for n, _ in live[:100]]


def refresh_data() -> None:
    """INCREMENTAL refresh: fetch only the last TAIL_DAYS of candles + funding for the
    live coins and merge onto the existing year of history. Seconds, not the ~15 min a
    full 365d x 135-coin re-page took. The one-time full history stays intact."""
    import numpy as np
    import pandas as pd
    from hl.info import Info, now_ms
    info = Info()
    coins = _live_coins(info)
    end = now_ms()
    start = end - (TAIL_DAYS + 2) * DAY_MS

    # --- prices: recent daily candles, merged onto history ---
    try:
        base = pd.read_parquet(PRICE_PARQUET) if PRICE_PARQUET.exists() else pd.DataFrame()
        tail = {}
        for c in coins:
            try:
                rows = info.candles(c, "1d", start, end)
            except Exception:
                continue
            if rows:
                tail[c] = pd.Series({int(r["t"]): float(r["c"]) for r in rows})
        if tail:
            tdf = pd.DataFrame(tail).sort_index()
            merged = tdf if base.empty else base.combine_first(tdf).copy()
            # combine_first keeps base where both exist; we want NEW values to win:
            if not base.empty:
                merged.update(tdf)
            merged = merged.sort_index().tail(400)
            merged.to_parquet(PRICE_PARQUET)
            _log(f"price parquet updated: +{len(tail)} coins tail, {merged.shape[0]} days")
    except Exception as e:
        _log(f"price refresh FAILED (using cached): {e}")

    # --- funding: recent hourly funding summed to daily, merged onto history ---
    try:
        base = pd.read_parquet(FUNDING_PARQUET) if FUNDING_PARQUET.exists() else pd.DataFrame()
        tail = {}
        for c in coins:
            try:
                page = info.funding_history(c, start)     # 500 rows ~ 21d, one page covers 7d
            except Exception:
                continue
            if page:
                s = pd.Series({int(r["time"]): float(r["fundingRate"]) for r in page})
                s.index = (s.index // DAY_MS) * DAY_MS
                tail[c] = s.groupby(level=0).sum()
        if tail:
            tdf = pd.DataFrame(tail).sort_index()
            merged = tdf if base.empty else base.combine_first(tdf).copy()
            if not base.empty:
                merged.update(tdf)
            merged = merged.sort_index().tail(400)
            merged.to_parquet(FUNDING_PARQUET)
            _log(f"funding parquet updated: +{len(tail)} coins tail, {merged.shape[0]} days")
    except Exception as e:
        _log(f"funding refresh FAILED (using cached): {e}")


def cycle() -> None:
    from hl import tracker
    try:
        refresh_data()
    except Exception as e:
        _log(f"data refresh error (continuing on cached): {e}")
    try:
        from hl import fng
        fng.refresh()
    except Exception as e:
        _log(f"fng refresh error: {e}")
    # clear the 5-min composite cache so the snapshot uses the just-refreshed parquet
    try:
        from hl import signals
        signals._cache["t"] = 0.0
    except Exception:
        pass
    try:
        n = tracker.snapshot_live()
        g = tracker.grade()
        sc = tracker.scorecard()
        live = sc.get("live", {})
        _log(f"snapshot +{n} live picks · graded {g} matured · "
             f"live record: n={live.get('n', 0)} hit={live.get('hit')} "
             f"open={sc.get('live_open')}")
        tracker.heartbeat(f"snap={n} graded={g}")
    except Exception as e:
        _log(f"snapshot/grade FAILED: {e}")
        try:
            tracker.heartbeat(f"error: {e}")
        except Exception:
            pass
    # gated-vs-ungated forward experiment: record today's gate verdict for the whole
    # universe + grade any matured (10d) picks BTC-neutral.
    try:
        from hl import gate_experiment
        gr = gate_experiment.snapshot()
        gg = gate_experiment.grade()
        gsc = gate_experiment.scorecard()
        _log(f"gate-exp: snapshot allowed={gr.get('allowed')} blocked={gr.get('blocked')} · "
             f"graded {gg} · edge so far={gsc.get('gate_edge_pct')}%")
    except Exception as e:
        _log(f"gate-exp FAILED: {e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=float, default=21600.0)   # 6h
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    _log(f"starting (every {args.every:.0f}s)" if not args.once else "one cycle")
    while True:
        cycle()
        if args.once:
            break
        time.sleep(args.every)


if __name__ == "__main__":
    main()
