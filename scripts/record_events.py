"""Watch every event source, store only what is genuinely new.

    python scripts/record_events.py            # every 2 min
    python scripts/record_events.py --once
    python scripts/record_events.py --new      # show what changed last pass
    python scripts/record_events.py --stats

The whole value is in the diff. Each source is polled, and an event is written
only the first time its id is seen - so `first_seen_ms` is honestly the moment
we could first have known, and a new Hyperliquid perp or a fresh Upbit notice
shows up as exactly one new row the pass after it appears.

The Hyperliquid universe is special: it is diffed structurally, so a coin
LEAVING the list (a delisting) and a maxLeverage CHANGE are detected too, not
just additions.

Nothing here is classified. Storing the raw event is the job; deciding what it
means is the reasoning layer's.
"""
from __future__ import annotations

import argparse
import json
import signal
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl import events  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNNING = True

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  event_id   TEXT PRIMARY KEY,
  first_seen_ms INTEGER NOT NULL,   -- when WE first saw it. the honest one.
  source     TEXT, kind TEXT, title TEXT, url TEXT,
  publish_ts TEXT, extra TEXT
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_events_seen ON events(first_seen_ms);
CREATE INDEX IF NOT EXISTS idx_events_src ON events(source, first_seen_ms);

-- Structural changes to the Hyperliquid universe: listings, delistings,
-- leverage changes. Derived by diffing, not by reading a notice.
CREATE TABLE IF NOT EXISTS hl_universe_changes (
  ts_ms INTEGER NOT NULL, coin TEXT NOT NULL, change TEXT NOT NULL,
  detail TEXT,
  PRIMARY KEY (ts_ms, coin, change)
);

CREATE TABLE IF NOT EXISTS event_runs (
  ts_ms INTEGER PRIMARY KEY, sources_ok INTEGER, sources_failed INTEGER,
  new_events INTEGER, universe_changes INTEGER, errors TEXT, took_ms INTEGER
);
"""


def stop(*_a) -> None:
    global RUNNING
    RUNNING = False
    print("\nstopping after this pass...")


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def diff_universe(conn: sqlite3.Connection, evs: List[dict], ts: int) -> int:
    """Compare this pass's perp list to the last recorded one."""
    prev = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT coin, max_leverage, delisted FROM hl_universe_state")}
    now = {e["title"]: (e["extra"].get("maxLeverage"),
                        int(bool(e["extra"].get("isDelisted")))) for e in evs}
    changes = []
    for coin, (lev, delisted) in now.items():
        if coin not in prev:
            if prev:                      # not the very first run
                changes.append((coin, "listed", json.dumps({"maxLeverage": lev})))
        else:
            old_lev, old_del = prev[coin]
            if old_lev != lev:
                changes.append((coin, "leverage_change",
                                json.dumps({"from": old_lev, "to": lev})))
            if old_del != delisted and delisted:
                changes.append((coin, "delisted", ""))
    for coin in prev:
        if coin not in now:
            changes.append((coin, "removed", ""))
    with conn:
        conn.executemany("INSERT OR REPLACE INTO hl_universe_changes VALUES (?,?,?,?)",
                         [(ts, c, k, d) for c, k, d in changes])
        conn.execute("DELETE FROM hl_universe_state")
        conn.executemany("INSERT INTO hl_universe_state VALUES (?,?,?)",
                         [(c, now[c][0], now[c][1]) for c in now])
    for c, k, d in changes:
        print(f"  UNIVERSE: {c} {k} {d}")
    return len(changes)


def one_pass(conn: sqlite3.Connection) -> Dict[str, int]:
    ts = int(time.time() * 1000)
    got = {"new": 0, "changes": 0, "ok": 0, "failed": 0}
    errors = {}
    for name, fn in events.DETECTORS.items():
        if not RUNNING:
            break
        try:
            evs = fn()
            got["ok"] += 1
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"[:150]
            got["failed"] += 1
            continue
        if name == "hl_universe":
            got["changes"] += diff_universe(conn, evs, ts)
        rows = [(e["event_id"], ts, e["source"], e["kind"], e["title"],
                 e["url"], e["publish_ts"], json.dumps(e["extra"])) for e in evs]
        before = conn.total_changes
        with conn:
            conn.executemany(
                "INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?)", rows)
        new = conn.total_changes - before
        # The universe detector emits one row per coin every pass; only the
        # first sighting of each is new, so its "new events" after the first run
        # is just genuinely new coins.
        got["new"] += new
        if new and name != "hl_universe":
            for e in evs[:new]:
                print(f"  NEW {name}: {e['title'][:90]}")
    with conn:
        conn.execute("INSERT OR REPLACE INTO event_runs VALUES (?,?,?,?,?,?,?)",
                     (ts, got["ok"], got["failed"], got["new"], got["changes"],
                      json.dumps(errors), int(time.time() * 1000) - ts))
    if errors:
        for k, v in errors.items():
            print(f"    {k}: {v}")
    return got


def ensure_state(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS hl_universe_state "
                 "(coin TEXT PRIMARY KEY, max_leverage INTEGER, delisted INTEGER)")


def stats(conn: sqlite3.Connection) -> None:
    n = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    print(f"\n{n:,} events stored")
    for s, c in conn.execute("SELECT source, COUNT(*) FROM events GROUP BY source ORDER BY 2 DESC"):
        print(f"  {s:<14}{c:>6}")
    ch = conn.execute("SELECT COUNT(*) FROM hl_universe_changes").fetchone()[0]
    print(f"\nuniverse changes detected: {ch}")
    for ts, coin, k, d in conn.execute(
            "SELECT ts_ms, coin, change, detail FROM hl_universe_changes "
            "ORDER BY ts_ms DESC LIMIT 8"):
        print(f"  {time.strftime('%m-%d %H:%M', time.localtime(ts/1000))}  {coin:<10}{k}  {d}")
    print("\nmost recent announcements (raw, unclassified):")
    for s, t, seen in conn.execute(
            "SELECT source, title, first_seen_ms FROM events WHERE kind='announcement' "
            "ORDER BY first_seen_ms DESC LIMIT 8"):
        print(f"  {time.strftime('%H:%M', time.localtime(seen/1000))} {s:<9}{t[:82]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=120.0)
    ap.add_argument("--db", default="data/events.db")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    db = ROOT / args.db if not Path(args.db).is_absolute() else Path(args.db)
    conn = open_db(db)
    ensure_state(conn)
    if args.stats:
        stats(conn)
        return

    signal.signal(signal.SIGINT, stop)
    print(f"watching {len(events.DETECTORS)} event sources into {db}, "
          f"every {args.interval:.0f}s\n")
    passes = 0
    while RUNNING:
        t0 = time.time()
        got = one_pass(conn)
        passes += 1
        print(f"[{passes:>4}] {time.strftime('%H:%M:%S')}  {got['new']} new events, "
              f"{got['changes']} universe changes, {got['ok']} ok, "
              f"{got['failed']} failed, {time.time()-t0:.0f}s")
        if args.once:
            break
        end = t0 + args.interval
        while RUNNING and time.time() < end:
            time.sleep(0.5)
    conn.close()
    print("stopped cleanly")


if __name__ == "__main__":
    main()
