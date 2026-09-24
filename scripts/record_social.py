"""Collect the crowd's words. Raw, timestamped, deduplicated, unscored.

    python scripts/record_social.py             # every 3 min
    python scripts/record_social.py --once
    python scripts/record_social.py --stats

Stores three timestamps per post and they are not interchangeable:

    publish_ts   what the platform claims. Often missing, sometimes backdated.
    fetch_ts     when our request returned. THIS is the honest event time.
    first_seen   the fetch_ts of the first time we ever saw this post id.

Why that matters more than it sounds: backtest on publish_ts and the system will
look brilliant, because it will be reading posts at times we could not actually
have had them. first_seen is what we could really have known, and it is the only
one a backtest is allowed to use.

Nothing here is scored. No sentiment number, no coin tagging. The one exception
is StockTwits' Bullish/Bearish label, kept because the author applied it to
their own post - that is a stated position, not our guess about their mood.
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

from hl import social  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNNING = True

# Verified reachable from this machine. Telegram needs no account at all:
# t.me/s/<channel> is the channel's own public web preview.
SOURCES: List[tuple] = [
    ("telegram", "whale_alert_io"),        # large transfers to/from exchanges
    ("telegram", "bwenews"),               # asian exchange announcements, fast
    ("telegram", "wublockchainenglish"),   # china policy and asia exchanges
    ("telegram", "binance_announcements"),
    ("telegram", "cointelegraph"),
    ("telegram", "WatcherGuru"),
    ("telegram", "unfolded"),
    ("reddit", "CryptoCurrency"),
    ("reddit", "Bitcoin"),
    ("reddit", "ethereum"),
    ("reddit", "solana"),
    ("reddit", "CryptoMarkets"),
    ("reddit", "SatoshiStreetBets"),
    ("4chan", "biz"),
    ("stocktwits", "BTC.X"),
    ("stocktwits", "ETH.X"),
    ("stocktwits", "SOL.X"),
    ("stocktwits", "XRP.X"),
    ("stocktwits", "DOGE.X"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
  source TEXT NOT NULL, channel TEXT NOT NULL, post_id TEXT NOT NULL,
  first_seen_ms INTEGER NOT NULL,   -- when WE first had it. use this one.
  fetch_ts_ms   INTEGER NOT NULL,
  publish_ts    TEXT,               -- what the platform claims
  author TEXT, text TEXT, url TEXT,
  stated_sentiment TEXT,            -- only where the AUTHOR labelled it
  extra TEXT,
  PRIMARY KEY (source, channel, post_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_posts_seen ON posts(first_seen_ms);
CREATE INDEX IF NOT EXISTS idx_posts_src ON posts(source, first_seen_ms);

CREATE TABLE IF NOT EXISTS social_runs (
  ts_ms INTEGER NOT NULL, source TEXT NOT NULL, channel TEXT NOT NULL,
  returned INTEGER, new_posts INTEGER, error TEXT, took_ms INTEGER,
  PRIMARY KEY (ts_ms, source, channel)
);
"""


def stop(*_a) -> None:
    global RUNNING
    RUNNING = False
    print("\nstopping after this round...")


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def store(conn: sqlite3.Connection, posts: List[dict]) -> int:
    """Insert only posts we have never seen. first_seen_ms is written once and
    never updated, so re-polling can never move an event later in time."""
    rows = []
    for p in posts:
        extra = {k: v for k, v in p.items()
                 if k not in ("source", "channel", "post_id", "publish_ts",
                              "fetch_ts", "author", "text", "url",
                              "stated_sentiment")}
        rows.append((p["source"], p["channel"], str(p["post_id"]),
                     p["fetch_ts"], p["fetch_ts"],
                     str(p.get("publish_ts")) if p.get("publish_ts") else None,
                     p.get("author"), p.get("text"), p.get("url"),
                     p.get("stated_sentiment"),
                     json.dumps(extra) if extra else None))
    before = conn.total_changes
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO posts VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    return conn.total_changes - before


def one_round(conn: sqlite3.Connection, sources) -> Dict[str, int]:
    got = {"posts": 0, "new": 0, "errors": 0}
    for source, channel in sources:
        if not RUNNING:
            break
        t0 = time.time()
        err = None
        posts: List[dict] = []
        try:
            posts = social.FETCHERS[source](channel)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"[:200]
            got["errors"] += 1
        new = store(conn, posts) if posts else 0
        got["posts"] += len(posts)
        got["new"] += new
        with conn:
            conn.execute("INSERT OR REPLACE INTO social_runs VALUES (?,?,?,?,?,?,?)",
                         (int(time.time() * 1000), source, channel, len(posts),
                          new, err, int((time.time() - t0) * 1000)))
        if err:
            print(f"    {source}/{channel}: {err}")
        # pacing is per-host, inside hl.social - a flat pause here either
        # crawls for every source or gets refused by the strictest one
    return got


def stats(conn: sqlite3.Connection) -> None:
    n = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    if not n:
        print("nothing collected yet")
        return
    lo, hi = conn.execute("SELECT MIN(first_seen_ms), MAX(first_seen_ms) FROM posts").fetchone()
    print(f"\n{n:,} posts, first seen span {(hi-lo)/3600000:.2f} hours")
    print(f"\n  {'source':<12}{'channel':<24}{'posts':>8}{'last seen':>12}")
    print("  " + "-" * 56)
    for s, c, cnt, last in conn.execute(
            "SELECT source, channel, COUNT(*), MAX(first_seen_ms) FROM posts "
            "GROUP BY source, channel ORDER BY source, COUNT(*) DESC"):
        print(f"  {s:<12}{c:<24}{cnt:>8}{time.strftime('%H:%M:%S', time.localtime(last/1000)):>12}")
    fails = conn.execute("SELECT source, channel, error FROM social_runs "
                         "WHERE error IS NOT NULL ORDER BY ts_ms DESC LIMIT 5").fetchall()
    if fails:
        print("\n  recent failures:")
        for s, c, e in fails:
            print(f"    {s}/{c}: {e[:90]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=180.0)
    ap.add_argument("--db", default="data/social.db")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_absolute():
        db = ROOT / db
    conn = open_db(db)
    if args.stats:
        stats(conn)
        return

    signal.signal(signal.SIGINT, stop)
    print(f"collecting {len(SOURCES)} channels into {db}, every {args.interval:.0f}s\n")
    rounds = 0
    while RUNNING:
        t0 = time.time()
        got = one_round(conn, SOURCES)
        rounds += 1
        print(f"[{rounds:>4}] {time.strftime('%H:%M:%S')}  {got['posts']} returned, "
              f"{got['new']} new, {got['errors']} errors, {time.time()-t0:.0f}s")
        if args.once:
            break
        end = t0 + args.interval
        while RUNNING and time.time() < end:
            time.sleep(0.5)
    conn.close()
    print("stopped cleanly")


if __name__ == "__main__":
    main()
