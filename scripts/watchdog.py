"""Keeps every collector alive, and records the fact that it had to.

    python scripts/watchdog.py              # supervise all three
    python scripts/watchdog.py --status     # what is healthy right now
    python scripts/watchdog.py --only venues,social

Supervises three jobs:

    venues       every coin on every reachable exchange, every 5 min
    social       telegram / reddit / 4chan / stocktwits, every 10 min
    positioning  binance crowd positioning top-up, hourly

The watchdog OWNS each one as a child process, so "is it alive" is answered by
the operating system instead of by scanning a process list and guessing.

Two ways a collector fails and only one of them is obvious:

  * it dies   - the process exits. Easy to see.
  * it hangs  - the process is alive, the CPU is idle, and nothing has been
                written for an hour. A check that only asks "is the process
                running" calls this healthy, which is worse than no check.

So health means DATA: each job names a table whose newest timestamp must keep
moving. A hung child is killed and replaced exactly like a dead one.
"""
from __future__ import annotations

import argparse
import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY = sys.executable

# name, argv after python, database, "how fresh is it" query, seconds before stale
JOBS = [
    {
        "name": "venues",
        "args": [str(HERE / "record_venues.py"), "--interval", "300"],
        "db": "data/venues.db",
        "freshness": "SELECT MAX(ts_ms) FROM runs",
        # a pass takes ~8s but a slow venue can stretch it, so allow 2.5 intervals
        "stale_after": 750,
    },
    {
        "name": "social",
        "args": [str(HERE / "record_social.py"), "--interval", "600"],
        "db": "data/social.db",
        "freshness": "SELECT MAX(ts_ms) FROM social_runs",
        # reddit backoff alone can eat 5 minutes of a round
        "stale_after": 2400,
    },
    {
        "name": "events",
        "args": [str(HERE / "record_events.py"), "--interval", "120"],
        "db": "data/events.db",
        "freshness": "SELECT MAX(ts_ms) FROM event_runs",
        "stale_after": 600,
    },
    {
        "name": "settle",
        "args": [str(HERE / "settle_loop.py"), "--interval", "60"],
        "db": "data/paper.db",
        "freshness": "SELECT MAX(ts_ms) FROM settle_heartbeat",
        "stale_after": 300,
    },
    {
        "name": "triggers",
        "args": [str(HERE / "trigger_loop.py"), "--interval", "30"],
        "db": "data/triggers.db",
        "freshness": "SELECT MAX(ts_ms) FROM trigger_heartbeat",
        "stale_after": 180,
    },
    {
        # Reads Binance's public ARCHIVE (data.binance.vision), not the API -
        # the API is geo-blocked (HTTP 451) from India and the US. A day's file
        # appears the next day, so an hourly check is plenty.
        "name": "positioning",
        "args": [str(HERE / "backfill_positioning.py"), "--every", "3600"],
        "db": "data/venues.db",
        "freshness": "SELECT MAX(ts_ms) FROM backfill_log",
        "stale_after": 7800,
    },
    {
        "name": "unlocks",
        "args": [str(HERE / "unlocks_refresh.py"), "--every", "21600"],
        "db": "data/unlocks.db",
        "freshness": "SELECT MAX(ts_ms) FROM unlock_runs",
        "stale_after": 43200,   # 12h (the scan is slow + runs every 6h)
    },
    {
        "name": "tracker",
        "args": [str(HERE / "tracker_loop.py"), "--every", "21600"],
        "db": "data/tracker.db",
        "freshness": "SELECT MAX(ts_ms) FROM tracker_runs",
        "stale_after": 50400,   # 14h (refresh+snapshot+grade runs every 6h, funding paging is slow)
    },
    {
        # Copies new rows from the legacy DBs into the unified store
        # (data/store.db). Temporary: retire once collectors write direct.
        "name": "store_sync",
        "args": [str(HERE.parent / "data_layer" / "store" / "sync.py"),
                 "--interval", "60"],
        "db": "data/store.db",
        "freshness": "SELECT MAX(ts_ms) FROM collector_run",
        "stale_after": 300,
    },
]

RUNNING = True

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchdog_events (
  ts_ms INTEGER NOT NULL, job TEXT NOT NULL,
  event TEXT, detail TEXT, data_age_s REAL,
  PRIMARY KEY (ts_ms, job)
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    """The first version of this file wrote a 4-column events table with no job
    column. Rename it rather than dropping it - those rows are the record of
    real restarts and a hole in the data still has to be explainable."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(watchdog_events)")]
    if cols and "job" not in cols:
        with conn:
            conn.execute("ALTER TABLE watchdog_events RENAME TO watchdog_events_v1")
    conn.executescript(SCHEMA)


def stop(*_a) -> None:
    global RUNNING
    RUNNING = False
    print("\nwatchdog stopping (all collectors go with it)...")


def db_path(db: str) -> Path:
    p = Path(db)
    return p if p.is_absolute() else ROOT / p


def data_age(job: dict) -> float:
    """Seconds since this job last wrote. Infinite if it never has."""
    path = db_path(job["db"])
    if not path.exists():
        return float("inf")
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        row = conn.execute(job["freshness"]).fetchone()
        conn.close()
    except sqlite3.Error:
        return float("inf")
    if not row or not row[0]:
        return float("inf")
    return (time.time() * 1000 - row[0]) / 1000.0


def log_event(job: dict, event: str, detail: str, age: float) -> None:
    path = db_path(job["db"])
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(path, timeout=10)
        ensure_schema(conn)
        with conn:
            conn.execute("INSERT OR REPLACE INTO watchdog_events VALUES (?,?,?,?,?)",
                         (int(time.time() * 1000), job["name"], event, detail,
                          None if age == float("inf") else age))
        conn.close()
    except sqlite3.Error as exc:
        print(f"  could not log event: {exc}")


LOCK = ROOT / "data" / "watchdog.lock"


def pid_alive(pid: int) -> bool:
    if os.name != "nt":
        return False
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue) -ne $null"],
                         capture_output=True, text=True, timeout=20)
    return out.stdout.strip().lower() == "true"


def claim_lock(force: bool) -> bool:
    """Single instance, by lock file rather than by pattern-killing.

    Matching 'watchdog.py' in a command line and killing it was a trap: on
    Windows each script runs as TWO processes, a launcher shim plus the real
    interpreter, so excluding only os.getpid() left the watchdog free to kill
    its own parent - which it did, silently, taking itself down at startup.
    """
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        try:
            old = int(LOCK.read_text().split()[0])
        except (ValueError, IndexError):
            old = -1
        if old > 0 and old != os.getpid() and pid_alive(old):
            if not force:
                print(f"another watchdog is already running (pid {old}).")
                print("stop it, or re-run with --force to take over.")
                return False
            print(f"taking over from watchdog pid {old}")
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"Stop-Process -Id {old} -Force"],
                           capture_output=True, timeout=20)
            time.sleep(2)
    LOCK.write_text(f"{os.getpid()} {int(time.time())}")
    return True


def kill_strays(jobs: List[dict]) -> int:
    """Kill COLLECTORS started outside this watchdog. Never matches watchdog.py
    itself - see claim_lock for why that was removed."""
    if os.name != "nt":
        return 0
    names = "|".join(Path(j["args"][0]).name for j in jobs)
    mypid = os.getpid()
    ps = (f"$pat='{names}'; Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
          f"Where-Object {{ $_.CommandLine -match $pat -and $_.ProcessId -ne {mypid} }} | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=40)
        return len([l for l in out.stdout.split() if l.strip().isdigit()])
    except Exception:
        return 0


def spawn(job: dict) -> subprocess.Popen:
    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    log = (ROOT / "data" / f"{job['name']}.log").open("a", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")   # emoji in telegram posts
    return subprocess.Popen([PY, "-u"] + job["args"], cwd=str(ROOT),
                            stdout=log, stderr=subprocess.STDOUT, env=env)


def status(jobs: List[dict]) -> None:
    print(f"\n{'job':<14}{'last wrote':>14}{'stale after':>13}   health")
    print("-" * 58)
    for j in jobs:
        age = data_age(j)
        shown = "never" if age == float("inf") else f"{age:.0f}s ago"
        health = "STALE" if age > j["stale_after"] else "ok"
        print(f"{j['name']:<14}{shown:>14}{j['stale_after']:>13}   {health}")
    for j in jobs:
        path = db_path(j["db"])
        if not path.exists():
            continue
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            ev = conn.execute("SELECT ts_ms, job, event, detail FROM watchdog_events "
                              "WHERE job=? ORDER BY ts_ms DESC LIMIT 3",
                              (j["name"],)).fetchall()
            conn.close()
        except sqlite3.Error:
            continue
        if ev:
            print(f"\n  {j['name']} recent events:")
            for ts, _job, e, d in ev:
                print(f"    {time.strftime('%m-%d %H:%M:%S', time.localtime(ts/1000))}"
                      f"  {e:<18}{d}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-every", type=float, default=20.0)
    ap.add_argument("--only", default="", help="comma separated job names")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="take over from a watchdog that is already running")
    args = ap.parse_args()

    jobs = JOBS
    if args.only:
        want = {n.strip() for n in args.only.split(",")}
        jobs = [j for j in JOBS if j["name"] in want]

    if args.status:
        status(jobs)
        return

    signal.signal(signal.SIGINT, stop)
    if not claim_lock(args.force):
        return
    n = kill_strays(jobs)
    if n:
        print(f"stopped {n} collector process(es) already running")

    children: Dict[str, subprocess.Popen] = {}
    started: Dict[str, float] = {}
    for j in jobs:
        children[j["name"]] = spawn(j)
        started[j["name"]] = time.time()
        log_event(j, "started", f"pid {children[j['name']].pid}", data_age(j))
        print(f"  {j['name']:<14} pid {children[j['name']].pid}")
    print(f"watchdog up, checking every {args.check_every:.0f}s. Ctrl+C stops everything.")

    while RUNNING:
        time.sleep(args.check_every)
        if not RUNNING:
            break
        for j in jobs:
            name = j["name"]
            child = children[name]
            code = child.poll()
            if code is not None:
                age = data_age(j)
                print(f"[{time.strftime('%H:%M:%S')}] {name} exited (code {code}) - restarting")
                log_event(j, "restarted_dead", f"exit code {code}", age)
                children[name] = spawn(j)
                started[name] = time.time()
                print(f"    {name} new pid {children[name].pid}")
                continue

            age = data_age(j)
            # Give a fresh child one full cycle before judging it on data age.
            grace = j["stale_after"] + 120
            if age > j["stale_after"] and time.time() - started[name] > grace:
                print(f"[{time.strftime('%H:%M:%S')}] {name} alive but silent for "
                      f"{age:.0f}s - killing and restarting")
                log_event(j, "restarted_stale", f"killed pid {child.pid}", age)
                child.kill()
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    pass
                children[name] = spawn(j)
                started[name] = time.time()
                print(f"    {name} new pid {children[name].pid}")

    for j in jobs:
        log_event(j, "stopped", "watchdog shut down", data_age(j))
    for name, child in children.items():
        child.terminate()
        try:
            child.wait(timeout=20)
        except subprocess.TimeoutExpired:
            child.kill()
    try:
        if LOCK.exists() and LOCK.read_text().split()[0] == str(os.getpid()):
            LOCK.unlink()
    except (OSError, IndexError):
        pass
    print("watchdog and all collectors stopped")


if __name__ == "__main__":
    main()
