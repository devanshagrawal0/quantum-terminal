"""ChatGPT through the Codex CLI (`codex exec`) - the desk's web-access research agent and,
later, its strong-model backend for the strategist/skeptic.

Why a CLI and not an API key: Dev pays for ChatGPT already; the Codex CLI rides that login
(`codex login` once, done by Dev - this module never touches auth). No key, no per-token bill,
the subscription's usage cap applies.

Contract (spec: docs/LIVE_CHAIN_PLAN_2026-09-17.md section 5):
  research(questions, context) -> a report whose every fact carries a URL and a fetched time;
  facts without a URL are dropped by the caller (provenance rule). The answer shape is forced
  with --output-schema so the model cannot wander. Seconds and token usage are logged on
  every call. Any failure (not signed in, cap hit, binary moved, bad JSON) is returned as
  {"ok": False, "error": ...} - never raised, never silent.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "codex"          # prompts, schemas, raw outputs, one folder per call

RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "answers": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "answer": {"type": "string"},
                "facts": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "fact": {"type": "string"},
                        "quote": {"type": "string"},
                        "source_url": {"type": "string"},
                        "published_at": {"type": "string"},
                        "fetched_at": {"type": "string"}},
                    "required": ["fact", "quote", "source_url", "published_at", "fetched_at"],   # strict mode: every property listed
                    "additionalProperties": False}},
                "not_found": {"type": "boolean"},
                "confidence": {"type": "number"}},
            "required": ["question", "answer", "facts", "not_found", "confidence"],
            "additionalProperties": False}},
        "new_since_context": {"type": "array", "items": {"type": "string"}},
        "risks_for_the_desk": {"type": "array", "items": {"type": "string"}}},
    "required": ["answers", "new_since_context", "risks_for_the_desk"],
    "additionalProperties": False,
}

RESEARCH_RULES = (
    "You are the research desk for a crypto perpetuals trading agent. You have web access; use it. "
    "Answer each question below with facts you actually found, each with its source URL, the page's "
    "publication time if shown, and the time you fetched it (UTC). Copy short verbatim quotes. "
    "If you cannot find it, set not_found=true and say so - never guess, never fill from memory. "
    "Do not recommend trades. Do not add facts that were not asked for unless they are in "
    "new_since_context (things the desk's context shows it does not know) or risks_for_the_desk "
    "(hacks, delistings, depegs, exchange outages, regulatory actions found while searching). "
    "Prefer primary sources: exchange announcements, project channels, official data releases, filings. "
    "Answer ONLY in the required JSON shape."
)


def find_codex() -> Optional[str]:
    """Resolve the binary fresh every call - the extension folder name changes on updates."""
    cands = []
    home = Path.home()
    cands += glob.glob(str(home / ".vscode" / "extensions" / "openai.chatgpt-*" / "bin" / "windows-x86_64" / "codex.exe"))
    cands += glob.glob(str(Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin" / "**" / "codex.exe"), recursive=True)
    cands = [c for c in cands if Path(c).exists()]
    if cands:
        return sorted(cands, key=lambda p: Path(p).stat().st_mtime, reverse=True)[0]
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if (Path(p) / "codex.exe").exists():
            return str(Path(p) / "codex.exe")
    return None


def login_status() -> Dict:
    exe = find_codex()
    if not exe:
        return {"ok": False, "error": "codex.exe not found"}
    try:
        r = subprocess.run([exe, "login", "status"], capture_output=True, text=True, timeout=30)
        out = (r.stdout + r.stderr).strip()
        return {"ok": "Not logged in" not in out and r.returncode == 0, "status": out[:200], "exe": exe}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "exe": exe}


def _run(prompt: str, schema: Optional[Dict], tag: str, timeout_s: int = 900, web: bool = True,
         model: Optional[str] = None, effort: str = "medium", files: Optional[Dict[str, str]] = None,
         sandbox: str = "read-only", extra_args: Optional[List[str]] = None) -> Dict:
    exe = find_codex()
    if not exe:
        return {"ok": False, "error": "codex.exe not found (ChatGPT VS Code extension / Codex CLI not installed)"}
    d = WORK / f"{time.strftime('%Y%m%d_%H%M%S')}_{tag}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "prompt.txt").write_text(prompt, encoding="utf-8")
    for rel, content in (files or {}).items():                     # raw data the agent may read and compute on
        fp = d / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
    args = [exe, "exec", "-", "--ephemeral", "-s", sandbox, "--skip-git-repo-check", "-C", str(d),
            "-o", str(d / "answer.json"), "--json", "--color", "never"] + list(extra_args or [])
    if schema:
        (d / "schema.json").write_text(json.dumps(schema), encoding="utf-8")
        args += ["--output-schema", str(d / "schema.json")]
    if web:
        args += ["-c", 'web_search="live"']          # verified after login: the key name changes across Codex versions
    if model:
        args += ["-m", model]
    args += ["-c", f'model_reasoning_effort="{effort}"']   # the 150k-token first test ran at the default; medium + search caps in the prompt
    t0 = time.time()
    try:
        r = subprocess.run(args, input=prompt, capture_output=True, text=True, timeout=timeout_s, encoding="utf-8")
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"codex exec timed out after {timeout_s}s", "dir": str(d)}
    secs = round(time.time() - t0, 1)
    (d / "events.jsonl").write_text(r.stdout or "", encoding="utf-8")
    (d / "stderr.txt").write_text(r.stderr or "", encoding="utf-8")
    usage = _usage_from_events(r.stdout or "")
    if r.returncode != 0:
        return {"ok": False, "error": f"codex exit {r.returncode}: {(r.stderr or r.stdout)[-400:]}", "seconds": secs, "dir": str(d), "usage": usage}
    ans_path = d / "answer.json"
    if not ans_path.exists():
        return {"ok": False, "error": "no answer file written", "seconds": secs, "dir": str(d), "usage": usage}
    raw = ans_path.read_text(encoding="utf-8")
    try:
        s, e = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[s:e + 1]) if schema else raw
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": f"answer not JSON: {type(ex).__name__}", "raw": raw[:500], "seconds": secs, "dir": str(d), "usage": usage}
    return {"ok": True, "data": data, "seconds": secs, "dir": str(d), "usage": usage, "backend": "codex"}


def _usage_from_events(events: str) -> Dict:
    """Token usage from the --json event stream (field names vary by version; take what is there)."""
    tot: Dict = {}
    for line in events.splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        for key in ("usage", "token_usage", "total_token_usage"):
            u = ev.get(key) if isinstance(ev, dict) else None
            if isinstance(u, dict):
                for k, v in u.items():
                    if isinstance(v, (int, float)):
                        tot[k] = v
    return tot


def research(questions: List[str], context: Optional[Dict] = None, tag: str = "research", timeout_s: int = 900,
             effort: str = "low", depth_note: str = "") -> Dict:
    """The desk's questions -> a report with URL-stamped facts. `context` is what the desk already
    knows (anonymised coins are fine: pass real names only for questions that need the web)."""
    qs = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    ctx = json.dumps(context or {}, default=str)[:12000]
    prompt = (RESEARCH_RULES + (" " + depth_note if depth_note else "") + f"\n\nNOW (UTC): {time.strftime('%Y-%m-%d %H:%M', time.gmtime())}\n\n"
              f"WHAT THE DESK ALREADY KNOWS (do not repeat it; flag what is new):\n{ctx}\n\nQUESTIONS:\n{qs}")
    out = _run(prompt, RESEARCH_SCHEMA, tag, timeout_s=timeout_s, web=True, effort=effort)   # low for hourly deltas, high at decisions
    if out.get("ok"):
        kept, dropped = [], 0
        for a in out["data"].get("answers", []):
            facts = [f for f in a.get("facts", []) if str(f.get("source_url", "")).startswith("http")]
            dropped += len(a.get("facts", [])) - len(facts)
            a["facts"] = facts
            kept.append(a)
        out["data"]["answers"] = kept
        out["facts_dropped_no_url"] = dropped
    return out


def chat(prompt: str, schema: Optional[Dict] = None, tag: str = "chat", timeout_s: int = 900, web: bool = False,
         effort: str = "medium") -> Dict:
    """Plain strong-model call (strategist / skeptic / review later). Same logging, same failure shape."""
    return _run(prompt, schema, tag, timeout_s=timeout_s, web=web, effort=effort)


if __name__ == "__main__":
    import sys
    print(json.dumps(login_status(), indent=1))
    if "--test" in sys.argv:
        r = research(["What is Hyperliquid's current base-tier perp taker fee, in basis points?",
                      "Did any token get delisted from Hyperliquid perps in the last 7 days? Name them with the announcement URL."],
                     {"note": "connection test from the desk"}, tag="test", timeout_s=600)
        print(json.dumps({k: v for k, v in r.items() if k != "data"}, indent=1))
        if r.get("ok"):
            print(json.dumps(r["data"], indent=1)[:3000])


def run_with_files(prompt: str, schema: Optional[Dict], files: Dict[str, str], tag: str = "raw", timeout_s: int = 3600,
                   effort: str = "high", web: bool = True, sandbox: str = "workspace-write",
                   extra_args: Optional[List[str]] = None) -> Dict:
    """A session with raw data files in its working directory and permission to run code there.
    On Windows the exec policy blocks commands under workspace-write ("blocked by policy", 2026-09-20);
    callers pass extra_args such as ["--ignore-rules"] after probing what the installed Codex allows."""
    return _run(prompt, schema, tag, timeout_s=timeout_s, web=web, effort=effort, files=files, sandbox=sandbox, extra_args=extra_args)
