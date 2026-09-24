"""The desk clock: runs the ChatGPT desk on a schedule and keeps the books settled.

Every cycle (default every 30 min):
  1. settle every run whose trades are still open (writes a new settlement into its file);
  2. review every run whose trades are ALL closed and that has no review yet (one ChatGPT call);
  3. at the decision slots (08:00 and 20:00 New York, DST-aware) start a new desk call -
     once per slot, never twice (a marker file per slot).
State on disk only: data/desk_calls/*.json and data/desk_calls/.slots. Kill and restart freely.

Usage:
  python scripts/desk_loop.py                 # run forever
  python scripts/desk_loop.py --once          # one cycle, then exit (for a Task Scheduler entry)
  python scripts/desk_loop.py --slots 08:00,20:00 --every 30
Nothing here touches an exchange account.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import desk_call as dc  # noqa: E402
import urllib.request  # noqa: E402
from sim.codex_backend import research, chat  # noqa: E402

RUNS = ROOT / "data" / "desk_calls"
SLOTS_FILE = RUNS / ".slots"
NY = ZoneInfo("America/New_York")
LOG = ROOT / "data" / "desk_loop.log"


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}Z {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, run: dict) -> None:
    path.write_text(json.dumps(run, indent=1, default=str), encoding="utf-8")


def all_closed(settlement: dict) -> bool:
    ts = settlement.get("trades") or []
    return bool(ts) and all(t.get("reason") not in (None, "open") for t in ts if "error" not in t)


def settle_open_runs() -> None:
    for path in sorted(RUNS.glob("*.json")):
        try:
            run = load(path)
        except Exception as e:  # noqa: BLE001
            log(f"skip {path.name}: {type(e).__name__}"); continue
        if not ((run.get("calls") or {}).get("ok")):
            continue
        last = (run.get("settlements") or [None])[-1]
        if last and all_closed(last):
            continue
        try:
            s = dc.settle(run)
        except Exception as e:  # noqa: BLE001
            log(f"settle {path.name} failed: {type(e).__name__}: {str(e)[:100]}"); continue
        run.setdefault("settlements", []).append(s)
        save(path, run)
        n_open = sum(1 for t in s["trades"] if t.get("reason") == "open")
        log(f"settled {path.name}: total ${s['total_pnl_usd']:+.2f}, {n_open} open")


def review_closed_runs() -> None:
    for path in sorted(RUNS.glob("*.json")):
        try:
            run = load(path)
        except Exception:
            continue
        if run.get("reviews") or not ((run.get("calls") or {}).get("ok")):
            continue
        last = (run.get("settlements") or [None])[-1]
        if not (last and all_closed(last)):
            continue
        log(f"reviewing {path.name} ...")
        try:
            rv = dc.review(run)
        except Exception as e:  # noqa: BLE001
            log(f"review {path.name} failed: {type(e).__name__}: {str(e)[:100]}"); continue
        run.setdefault("reviews", []).append(rv)
        save(path, run)
        res = rv.get("result") or {}
        log(f"reviewed {path.name}: ok={res.get('ok')} {res.get('seconds')}s {res.get('error', '')}")


# ---------------------------------------------------------------- the watcher
LOCAL = "http://127.0.0.1:8080/v1/chat/completions"
DELTA_EVERY_MIN = 60

WATCH_SCHEMA = {
    "type": "object",
    "properties": {"decisions": {"type": "array", "items": {
        "type": "object",
        "properties": {"coin": {"type": "string"}, "action": {"type": "string", "enum": ["hold", "cut"]},
                       "reason": {"type": "string"}, "what_changed": {"type": "string"}},
        "required": ["coin", "action", "reason", "what_changed"], "additionalProperties": False}}},
    "required": ["decisions"], "additionalProperties": False}

WATCH_RULES = (
    "You are the watcher on a crypto perpetuals desk. Each open trade below has the chain it was opened with (thesis, mechanism, "
    "falsifier, checkpoint), its live path, and what the research desk found in the last hour. Decide per trade: HOLD (the mechanism "
    "is intact; being underwater is not a reason) or CUT (the mechanism is dead: the thesis was disproved by news or by the checkpoint "
    "being missed with no new reason, or a risk event hit the coin). Never widen a stop, never add. Give the fact that decides it. "
    "Answer ONLY in the required JSON."
)


def local_triage(coin: str, thesis: str, delta: str) -> dict:
    """Local Qwen, thinking off: does this hour's delta matter for THIS thesis? Cheap gate before ChatGPT."""
    body = {"model": "qwen", "temperature": 0.1, "max_tokens": 120,
            "messages": [{"role": "system", "content": "Answer ONLY with JSON {\"matters\": true|false, \"why\": \"one sentence\"}."},
                         {"role": "user", "content": f"Open trade thesis on {coin}: {thesis}\n\nNew facts from the last hour:\n{delta}\n\n"
                                                     "Does anything here confirm, weaken or disprove the thesis, or add a risk (delisting, hack, "
                                                     "halt, regulatory hit)? If the facts are unrelated or not_found, matters=false."}],
            "chat_template_kwargs": {"enable_thinking": False}}
    try:
        req = urllib.request.Request(LOCAL, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            txt = json.loads(r.read())["choices"][0]["message"].get("content") or ""
        a, b = txt.find("{"), txt.rfind("}")
        d = json.loads(txt[a:b + 1])
        return {"matters": bool(d.get("matters")), "why": str(d.get("why", ""))[:200], "by": "local"}
    except Exception as e:  # noqa: BLE001
        return {"matters": True, "why": f"local triage unavailable ({type(e).__name__}); escalated", "by": "fallback"}


def watch_run(path: Path, run: dict) -> bool:
    """One watcher pass on a run with open trades. Returns True if the run file changed."""
    last = (run.get("settlements") or [None])[-1]
    if not last:
        return False
    open_tr = [t for t in last["trades"] if t.get("reason") == "open" and "error" not in t]
    if not open_tr:
        return False
    now = int(time.time() * 1000)
    changed = False
    # 1. hourly delta research on the open coins (ChatGPT, low effort, 1 search each)
    st = run.setdefault("watch", {"last_delta_ms": 0, "log": []})
    delta = None
    if now - int(st.get("last_delta_ms") or 0) >= DELTA_EVERY_MIN * 60_000:
        qs = [f"{t['coin']}: anything in the last 90 minutes that moves this token - dated news, exchange notice, hack, halt, large "
              f"liquidation, regulatory action, macro print. At most 1 search; say not_found if nothing." for t in open_tr]
        r = research(qs, {"open": [{k: t[k] for k in ("coin", "side", "price_move_pct", "hours")} for t in open_tr]},
                     tag="delta", timeout_s=600, effort="low")
        st["last_delta_ms"] = now
        delta = r.get("data") if r.get("ok") else {"error": r.get("error")}
        st["last_delta"] = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "seconds": r.get("seconds"), "usage": r.get("usage"),
                            "ok": r.get("ok"), "error": r.get("error")}
        log(f"delta {path.name}: ok={r.get('ok')} {r.get('seconds')}s {len(open_tr)} coins {r.get('error', '')}")
        changed = True
    # 2. which trades need a decision: checkpoint MISSED (not yet judged), falsifier is engine-enforced in settle
    to_decide = []
    for t in open_tr:
        coin = t["coin"]
        reasons = []
        if (t.get("checkpoint") or {}).get("status") == "MISSED" and not any(a.get("coin") == coin and a.get("kind") == "checkpoint" for a in run.get("actions", [])):
            reasons.append("checkpoint MISSED")
        if delta and isinstance(delta, dict):
            facts = []
            for a in delta.get("answers", []):
                if a.get("question", "").startswith(coin + ":") and not a.get("not_found"):
                    facts += [f"{f.get('fact')} [{f.get('source_url')}]" for f in a.get("facts", [])]
            for x in delta.get("risks_for_the_desk", []):
                if coin in str(x):
                    facts.append("RISK: " + str(x))
            if facts:
                tri = local_triage(coin, t.get("thesis") or "", chr(10).join(facts))
                st["log"].append({"at": datetime.now(timezone.utc).strftime("%H:%M"), "coin": coin, "triage": tri, "n_facts": len(facts)})
                if tri["matters"]:
                    reasons.append(f"news matters ({tri['by']}): {tri['why']}")
                    t["_facts"] = facts
        if reasons:
            t["_reasons"] = reasons
            to_decide.append(t)
    if not to_decide:
        if changed:
            save(path, run)
        return changed
    # 3. ChatGPT decides hold / cut for the flagged trades only
    items = [{"coin": t["coin"], "side": t["side"], "kind": t.get("kind"), "hours_in": t["hours"], "hold_h": t["hold_h"],
              "price_move_pct": t["price_move_pct"], "path_pct": t.get("path_pct"), "mfe_pct": t.get("mfe_pct"), "mae_pct": t.get("mae_pct"),
              "falsifier": t.get("falsifier"), "checkpoint": t.get("checkpoint"), "thesis": t.get("thesis"), "mechanism": t.get("mechanism"),
              "why_flagged": t.get("_reasons"), "new_facts": t.get("_facts", [])} for t in to_decide]
    prompt = WATCH_RULES + chr(10) + chr(10) + "=== OPEN TRADES FLAGGED ===" + chr(10) + json.dumps(items, default=str)
    r = chat(prompt, WATCH_SCHEMA, tag="watch", timeout_s=600, web=False, effort="medium")
    log(f"watch {path.name}: {len(to_decide)} flagged -> ok={r.get('ok')} {r.get('seconds')}s {r.get('error', '')}")
    if r.get("ok"):
        for d in r["data"]["decisions"]:
            t = next((x for x in to_decide if x["coin"] == d["coin"]), None)
            kind = "checkpoint" if t and "checkpoint MISSED" in (t.get("_reasons") or []) else "news"
            run.setdefault("actions", []).append({"coin": d["coin"], "at_ms": now, "action": d["action"], "kind": kind,
                                                  "reason": d["reason"], "what_changed": d["what_changed"],
                                                  "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")})
            log(f"  {d['coin']}: {d['action'].upper()} - {d['reason'][:140]}")
    save(path, run)
    return True


def watch_open_runs() -> None:
    for path in sorted(RUNS.glob("*.json")):
        try:
            run = load(path)
        except Exception:
            continue
        if not ((run.get("calls") or {}).get("ok")):
            continue
        try:
            if watch_run(path, run):
                s = dc.settle(run)                          # re-settle so a cut takes effect immediately
                run.setdefault("settlements", []).append(s)
                save(path, run)
        except Exception as e:  # noqa: BLE001
            log(f"watch {path.name} failed: {type(e).__name__}: {str(e)[:120]}")


def slot_key(now_ny: datetime, slot: str) -> str:
    return f"{now_ny.strftime('%Y-%m-%d')}_{slot}"


def due_slot(slots: list[str], window_min: int) -> str | None:
    """The slot whose time is within [slot, slot + window) right now, New York time, if not yet run."""
    now_ny = datetime.now(NY)
    done = set(SLOTS_FILE.read_text(encoding="utf-8").split()) if SLOTS_FILE.exists() else set()
    for slot in slots:
        hh, mm = [int(x) for x in slot.split(":")]
        start = now_ny.replace(hour=hh, minute=mm, second=0, microsecond=0)
        delta = (now_ny - start).total_seconds() / 60
        if 0 <= delta < window_min and slot_key(now_ny, slot) not in done:
            return slot
    return None


def mark_slot(slot: str) -> None:
    now_ny = datetime.now(NY)
    with open(SLOTS_FILE, "a", encoding="utf-8") as f:
        f.write(slot_key(now_ny, slot) + "\n")


def new_call() -> None:
    log("desk call starting ...")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "desk_call.py")], capture_output=True, text=True,
                       encoding="utf-8", timeout=2400, cwd=str(ROOT))
    tail = (r.stdout or "").strip().splitlines()[-3:]
    log(f"desk call exit {r.returncode}: " + " | ".join(tail))
    if r.returncode != 0:
        log("stderr: " + (r.stderr or "")[-300:])


def cycle(slots: list[str], window_min: int) -> None:
    settle_open_runs()
    watch_open_runs()
    review_closed_runs()
    slot = due_slot(slots, window_min)
    if slot:
        mark_slot(slot)
        new_call()
        settle_open_runs()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slots", default="08:00,20:00", help="New York times for new desk calls")
    ap.add_argument("--every", type=int, default=30, help="minutes between cycles")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    slots = [s.strip() for s in a.slots.split(",") if s.strip()]
    RUNS.mkdir(parents=True, exist_ok=True)
    st = dc.login_status()
    log(f"desk loop up: slots {slots} NY, every {a.every} min, codex: {st.get('status') or st.get('error')}")
    while True:
        try:
            cycle(slots, window_min=a.every)
        except Exception as e:  # noqa: BLE001
            log(f"cycle error: {type(e).__name__}: {str(e)[:200]}")
        if a.once:
            break
        time.sleep(a.every * 60)


if __name__ == "__main__":
    main()
