"""The recorder. Every coin Hyperliquid lists, priced on every venue we can reach.

    python scripts/record_venues.py                 # every 60s, all venues
    python scripts/record_venues.py --interval 300
    python scripts/record_venues.py --once
    python scripts/record_venues.py --stats         # what has been collected

This is the thing that has to be running. Hyperliquid publishes no history for
open interest, no history for the book, and nothing at all about what the same
coin costs somewhere else. None of that can be bought later at any price - it
exists only if it was recorded as it happened.

What one row is: one coin, on one venue, at one timestamp, with the raw prices
that venue published. Derived numbers (the gap, the premium) are NOT stored -
they are computed from the raw rows, so a change in how we define a gap does not
require throwing the history away.

Deliberate choices, each one learned from a bug:
  * a venue that fails is absent from the pass and named in the run log, never
    written as a zero,
  * KRW and INR prices are stored in KRW and INR. Converting to dollars here
    would hide an FX assumption inside the data,
  * every pass records the seconds since the previous pass, so a hole in the
    history is visible instead of quietly becoming a signal,
  * delisted Hyperliquid markets are excluded - their price is frozen at the
    final print and reads as a several-thousand-bps arbitrage that is not real.
"""
from __future__ import annotations

import argparse
import json
import signal
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl.exchanges import snapshot  # noqa: E402

RUNNING = True
DB_DEFAULT = "data/venues.db"

# Two venues quoting the same asset cannot sit 10% apart for more than seconds.
# Past that it is a shared ticker naming two different tokens - Bybit and HTX
# both list a PURR that is not Hyperliquid's PURR, at 80x the price. Rows are
# flagged, never dropped: deleting them hides the problem, and a real
# dislocation should be inspected rather than silently discarded.
SUSPECT_RATIO = 1.10
USD_FAMILY = {"USD", "USDT", "USDC", "USDD", "TUSD", "FDUSD", "BUSD", "DAI"}

# Venue and coin names repeat on every single row. Stored as text that was
# 160 bytes a row, which is 750 MB a day at one pass a minute. They live in
# lookup tables instead and the hot table holds small integers. The symbol and
# quote currency belong to the (venue, coin) pair, not to the tick, so they are
# recorded once in `pairs` rather than 1,440 times a day.
SCHEMA = """
CREATE TABLE IF NOT EXISTS venues (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS coins  (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS pairs (
  venue_id INTEGER NOT NULL, coin_id INTEGER NOT NULL,
  symbol TEXT, quote TEXT, first_seen_ms INTEGER, last_seen_ms INTEGER,
  PRIMARY KEY (venue_id, coin_id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS prices (
  ts_ms    INTEGER NOT NULL,
  venue_id INTEGER NOT NULL,
  coin_id  INTEGER NOT NULL,
  bid REAL, ask REAL, mid REAL, vol REAL,
  suspect  INTEGER,          -- 1 = far from Hyperliquid, 0 = agrees, NULL = not comparable
  PRIMARY KEY (ts_ms, venue_id, coin_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_prices_coin ON prices(coin_id, ts_ms);

CREATE TABLE IF NOT EXISTS hl_state (
  ts_ms INTEGER NOT NULL, coin TEXT NOT NULL,
  mid REAL, mark REAL, oracle REAL, funding_hourly REAL, oi_base REAL, vol24 REAL,
  PRIMARY KEY (ts_ms, coin)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS runs (
  ts_ms INTEGER PRIMARY KEY,
  venues_ok INTEGER, venues_failed INTEGER, coins INTEGER, rows INTEGER,
  errors TEXT, took_ms INTEGER, since_last_s REAL
);
"""


def stop(*_a) -> None:
    global RUNNING
    RUNNING = False
    print("\nfinishing this pass, then stopping...")


def open_db(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    return conn


class Ids:
    """Name to small integer, cached in memory, persisted in the db."""

    def __init__(self, conn: sqlite3.Connection, table: str):
        self.conn, self.table = conn, table
        self.cache = {n: i for i, n in
                      conn.execute(f"SELECT id, name FROM {table}")}

    def __call__(self, name: str) -> int:
        hit = self.cache.get(name)
        if hit is not None:
            return hit
        cur = self.conn.execute(
            f"INSERT OR IGNORE INTO {self.table}(name) VALUES (?)", (name,))
        row = self.conn.execute(
            f"SELECT id FROM {self.table} WHERE name=?", (name,)).fetchone()
        self.cache[name] = row[0]
        return row[0]


def one_pass(conn: sqlite3.Connection, last_ts, vid, cid):
    ts = int(time.time() * 1000)
    snap = snapshot()
    quotes, errors = snap["quotes"], snap["errors"]

    hl = quotes.get("hyperliquid")
    if not hl:
        # Without Hyperliquid there is no universe to record against. Say so
        # rather than writing a pass full of other venues that cannot be joined.
        raise RuntimeError("hyperliquid unreachable this pass: "
                           + str(errors.get("hyperliquid", "unknown")))

    rows, pairs = [], []
    n_suspect = 0
    for venue, coins in quotes.items():
        v = vid(venue)
        for coin in hl:                       # only what we can actually trade
            rec = coins.get(coin)
            if not rec or not rec.get("mid"):
                continue
            c = cid(coin)
            # Compared against Hyperliquid, because Hyperliquid is the asset we
            # actually trade - the question is "is this the same coin as our
            # perp", not "do these venues agree with each other". A median
            # across venues cannot answer it: on PURR the venues split 2-2 and
            # the median lands between two different assets.
            suspect = None
            hl_mid = hl[coin].get("mid")
            if rec.get("quote") in USD_FAMILY and hl_mid:
                ratio = rec["mid"] / hl_mid
                suspect = 1 if (ratio > SUSPECT_RATIO or ratio < 1 / SUSPECT_RATIO) else 0
                n_suspect += suspect
            rows.append((ts, v, c, rec.get("bid"), rec.get("ask"),
                         rec.get("mid"), rec.get("vol"), suspect))
            pairs.append((v, c, rec.get("symbol"), rec.get("quote"), ts, ts))

    hl_rows = [(ts, c, r.get("mid"), r.get("mark"), r.get("oracle"),
                r.get("funding"), r.get("oi"), r.get("vol"))
               for c, r in hl.items()]

    with conn:
        conn.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?,?)", rows)
        conn.executemany(
            "INSERT INTO pairs VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(venue_id, coin_id) DO UPDATE SET last_seen_ms=excluded.last_seen_ms,"
            " symbol=excluded.symbol, quote=excluded.quote", pairs)
        conn.executemany("INSERT OR REPLACE INTO hl_state VALUES (?,?,?,?,?,?,?,?)", hl_rows)
        conn.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?)",
                     (ts, len(quotes), len(errors), len(hl), len(rows),
                      json.dumps({k: v[:120] for k, v in errors.items()}),
                      snap["took_ms"],
                      (ts - last_ts) / 1000.0 if last_ts else 0.0))
    return ts, len(rows), len(quotes), errors, snap["took_ms"], n_suspect


def stats(conn: sqlite3.Connection) -> None:
    q = conn.execute
    n_rows = q("SELECT COUNT(*) FROM prices").fetchone()[0]
    if not n_rows:
        print("nothing recorded yet")
        return
    first, last = q("SELECT MIN(ts_ms), MAX(ts_ms) FROM prices").fetchone()
    span_h = (last - first) / 3_600_000
    passes = q("SELECT COUNT(*) FROM runs").fetchone()[0]
    print(f"\n{n_rows:,} price rows over {passes} passes, {span_h:.2f} hours of history")
    print(f"  first {time.strftime('%Y-%m-%d %H:%M', time.localtime(first/1000))}"
          f"   last {time.strftime('%Y-%m-%d %H:%M', time.localtime(last/1000))}")
    size = Path(conn.execute("PRAGMA database_list").fetchone()[2]).stat().st_size
    print(f"  db size {size/1e6:.1f} MB"
          + (f", growing at ~{size/1e6/span_h*24:.0f} MB/day" if span_h > 0.01 else ""))

    print("\n  rows per venue:")
    for v, c in q("SELECT v.name, COUNT(*) FROM prices p JOIN venues v ON v.id=p.venue_id"
                  " GROUP BY v.name ORDER BY 2 DESC"):
        print(f"    {v:<15}{c:>9,}")

    gaps = q("SELECT COUNT(*), MAX(since_last_s) FROM runs WHERE since_last_s > 0").fetchone()
    if gaps[0]:
        print(f"\n  longest gap between passes: {gaps[1]:.0f}s")
    bad = q("SELECT ts_ms, errors FROM runs WHERE errors != '{}' ORDER BY ts_ms DESC LIMIT 3").fetchall()
    if bad:
        print("  most recent venue failures:")
        for ts, err in bad:
            print(f"    {time.strftime('%H:%M:%S', time.localtime(ts/1000))}  {err[:120]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    conn = open_db(args.db)
    if args.stats:
        stats(conn)
        return

    signal.signal(signal.SIGINT, stop)
    print(f"recording to {Path(args.db).resolve()}   every {args.interval:.0f}s"
          f"   Ctrl+C to stop\n")

    vid, cid = Ids(conn, "venues"), Ids(conn, "coins")
    last_ts, passes = None, 0
    while RUNNING:
        t0 = time.time()
        try:
            ts, n, nv, errors, took, nsus = one_pass(conn, last_ts, vid, cid)
        except Exception as exc:
            print(f"  pass failed: {type(exc).__name__}: {exc}")
            time.sleep(5)
            continue
        since = (ts - last_ts) / 1000.0 if last_ts else 0.0
        last_ts = ts
        passes += 1
        warn = ("  MISSING " + ",".join(errors)) if errors else ""
        if nsus:
            warn += f"  {nsus} flagged"
        print(f"[{passes:>5}] {time.strftime('%H:%M:%S')}  {n:,} rows from {nv} venues"
              f"  {took}ms  +{since:.0f}s{warn}")
        if args.once:
            break
        end = t0 + args.interval
        while RUNNING and time.time() < end:
            time.sleep(0.5)

    conn.close()
    print("stopped cleanly")


if __name__ == "__main__":
    main()
