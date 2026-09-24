# The live chain — plan (2026-09-17)

What we are building: the sim agent (four hats + desk + memory) running on real time, on this
PC, with free data, ChatGPT doing the heavy thinking through the Codex CLI you already pay for,
the local Qwen doing the constant cheap work, and every trade landing in the terminal's paper
book at `localhost:8770` so you can watch it live. No exchange account is needed: Hyperliquid's
data API answers from a US IP (checked 2026-09-17: `allMids` returned prices; only the trading
front-end is geo-gated) and the paper book already exists (`data/paper.db`, 52 closed trades,
leverage 2-4x, stops/targets, funding, BTC hedge legs, settled by `scripts/settle_loop.py`).

Everything below is either already on disk (marked **have**) or not (marked **build**). Nothing
is claimed working until it is shown running.

---

## 1. The chain, in order

```
 feeds (watchdog, every 1-15 min)      have: candles/funding/OI/positioning/venues/unlocks/social/events
      │                                 build: GDELT + RSS news, Fear&Greed, prediction odds
      ▼
 perception daemon (code + local Qwen, thinking off, runs all day)     build (spec: PERCEPTION_LAYER_SPEC.md)
   - change detection in the coin's own units -> signal rows
   - news -> story -> claims (quote + source + time), coins linked by lookup, never by the model
   - world state: one 2,000-token page rewritten on every change ("what changed since last look")
      │
      ▼
 wake-ups (the clock)                                                   build
   - position check: every hour, and instantly when a signal touches a held coin
   - full decision: 08:00 and 20:00 New York, plus when enough has changed
   - nightly review: 23:30 NY; weekly benchmark: Sunday
      │
      ▼
 decision (the four hats)                                               have (sim) / build (backend switch)
   investigator  -> local Qwen (tool calls over the checklist; fast, no thinking)
   strategist    -> ChatGPT via `codex exec` (chains: mechanism -> falsifier -> checkpoint -> order)
   skeptic       -> ChatGPT via `codex exec` (attacks the dossier the engine gathered)
   risk desk     -> code only (stop/target bands, cluster, beta, stress, funding rule, sizing, book rules)
      │
      ▼
 paper book (terminal)                                                  have (book) / build (the wire)
   order -> data/paper.db position with leverage, stop, target, hold, thesis, plan hash
   settle_loop marks it every minute against live Hyperliquid prices; closes on stop/target/time
      │
      ▼
 position management (the watcher)                                     build
   each hour: falsifier / checkpoint verdict on the live path; cut, trim, hold; hold cap 7 days
      │
      ▼
 review + memory                                                        have (lessons) / build (loss_class, belief board)
   closed trade -> lesson with excess vs BTC, falsifier verdict, loss class -> memory.db
   nightly ChatGPT review -> stamped notes; Claude Code daily session -> scorer + one fix batch
```

## 2. Who does what

| worker | jobs | why this one | cost |
|---|---|---|---|
| **code** (engine, desk, settle loop) | every number, every rule, the clock, the logs | numbers must be right; models get arithmetic wrong (measured) | free |
| **local Qwen3.6-35B-A3B** (llama.cpp :8080, 6 threads, thinking off) | investigator tool calls, news claim extraction, hourly position checks, world-state summaries | always on, free, fine for short structured prompts; the measured weaknesses (arithmetic, sign flips, ignoring rules) are all jobs the code now owns | free, ~20-60 s per short call (to measure) |
| **ChatGPT via Codex CLI** (`codex exec`, your subscription) | strategist, skeptic, replan, nightly review, the scheduled research prompt | the reasoning-heavy calls where the local model is weakest; ~2-6 calls a day fits a subscription | $0 extra; subject to the plan's usage cap |
| **Claude Code** (this) | builds and fixes code, runs the benchmark, reads the day's failures, writes the daily build batch | it does not trade and should not | your existing plan |

The Codex CLI on this PC: `codex-cli 0.154.0`, bundled with the ChatGPT VS Code extension at
`~\.vscode\extensions\openai.chatgpt-<version>\bin\windows-x86_64\codex.exe` (version folder
changes on updates: resolve it fresh every run). `codex doctor` today: **auth missing** (you
sign in once: `codex login`, or the ChatGPT panel in VS Code), Defender exclusion not set
(optional), ripgrep missing (only matters for its code tools, not for us). Useful flags,
verified in `codex exec --help`: `--output-schema <file>` (forces the JSON shape — this is
the benchmark's `json_schema` rung), `-o <file>` (last message to a file), `--json` (events
incl. token usage), `--ephemeral` (no session files), `-m <model>`, `-C <dir>`,
`--skip-git-repo-check`, `-s read-only`. Web search inside Codex: the old flags are
deprecated and the new one is "under development" — to test after login, not assumed.

## 3. Information — all free, with where it lands and how often

| source | what | cadence | status |
|---|---|---|---|
| Hyperliquid info API | prices (1h candles), funding, OI, mark, order book | 1 min marks; 1 h candles | **have** (`record.py`, `store_sync`) — but the sim's store stops 2026-08-31 (Binance monthly zips); **build**: hourly candle sync from HL so the store is never stale |
| Hyperliquid + Lighter + Binance/Bybit/OKX public | cross-venue funding/OI/basis | 5 min | **have** (`record_venues.py`) |
| positioning (long/short share) | crowd positioning | 1 h | **have** (`backfill_positioning.py`, watchdog `positioning`) |
| token unlocks | unlock calendar | daily | **have** (`unlocks_refresh.py`) |
| macro calendar | FOMC, CPI, NFP, opex, listings | seeded to 2026 | **have** (`sim/events.py`) — **build**: pull 2027 dates when published |
| GDELT DOC 2.0 API | global news, every 15 min, country + tone fields, free | 15 min | **build** (P3) |
| RSS (~20 outlets: CoinDesk, The Block, Cointelegraph, Reuters/FT/Bloomberg crypto+macro feeds, Fed, BLS) | headlines + text | 15 min | **build** (P3) |
| Fear & Greed (alternative.me) | sentiment index | daily | **build** (one call) |
| prediction markets (Polymarket/Kalshi public odds) | rate-cut odds, ETF decisions | 1 h | **build** (public endpoints; read only) |
| social (existing) | Reddit/X counts we already record | 15 min | **have** (`record_social.py`) |
| ChatGPT scheduled research | a structured "what happened, what changed, what matters, with sources" page twice a day | 2/day | **build** (§5) |

Rule that holds for every source: raw rows are stored with `observed_at`; the sim replays them
time-locked, the live run reads them live, same code path. Model output is never a source.

## 4. Autonomous tasks (Windows Task Scheduler + the watchdog)

| when | task | worker | output you can see |
|---|---|---|---|
| on boot | `scripts/watchdog.py` (nine jobs) + `run-qwen.ps1` + `scripts/dashboard.py` | code | terminal on :8770 |
| every 15 min | perception cycle: feeds → signals → stories → world state | code + Qwen | `world_state` table; WORLD panel on the terminal |
| every hour | position check on every open paper trade (falsifier, checkpoint, stop distance, news touching the coin) → hold / trim / cut | code + Qwen; ChatGPT only if the check says "thesis in doubt" | POSITIONS panel shows the verdict per trade |
| 08:00 and 20:00 NY | full decision (four hats) → orders → paper book | Qwen + ChatGPT + code | DECISIONS panel: chains, verdicts, what the desk rejected |
| 23:30 NY | nightly review: closed trades → lessons; ChatGPT writes the stamped review note | code + ChatGPT | REVIEW panel; memory.db |
| Sunday 06:00 | benchmark on the week (same scorer as the sim) | code | BENCHMARK_SCORES file + terminal tile |
| when you open the app | Claude Code `/desk` skill: reads the last 24 h of logs, the scorer's "next unmet", the failures, and proposes ONE fix batch | Claude Code | in chat |

## 5. ChatGPT — the two modes

**Mode A — on demand (the skill).** One function, `sim/backends/codex.py`:
prompt → temp file → `codex exec - --ephemeral -s read-only --skip-git-repo-check
--output-schema schema.json -o out.json --json` → parse `out.json` → log seconds and token
usage next to the decision. The strategist, skeptic and replan calls go through it when
`SIM_BACKEND=codex`; the investigator stays local. Same prompts as today, same logs, so the
benchmark scores it identically. If Codex fails (cap hit, not signed in, binary moved) the
call falls back to the local model and the decision is marked `backend_fallback` — never
silently.

**Mode B — scheduled research (the big prompt).** Twice a day the engine builds one prompt
that contains only stamped facts: the world state, new signals since last time, the calendar
for 7 days, open positions with their plans and latest checkpoint status, the agent's own
record, and the top stories with quotes and URLs. ChatGPT returns a fixed schema:
`{regime_read, what_changed:[{fact, source_id, why_it_matters}], theories:[{claim,
mechanism, falsifier, coins}], positions:[{coin, verdict: hold|trim|cut|add, reason}],
questions_for_the_desk:[...], confidence}`. Every `fact` must cite a `source_id` from the
prompt or it is dropped by the engine (provenance rung). The result is stored as a stamped
note, shown on the terminal, and fed into the next decision as "the research desk's read".
It is **not** allowed to place orders — only the four-hat decision does.

Limits, stated up front: the subscription has a usage cap (weekly, Codex); a decision is
~60-80k tokens in, so 2-6 calls a day is fine and a 30-decision backtest is not — backtests
stay on Qwen. `codex exec` is one prompt → one answer, no streaming. The binary path changes
on updates. None of this is a blocker; all of it is logged when it happens.

## 6. Claude Code — the `/desk` skill (build)

A repo skill (`.claude/skills/desk/SKILL.md`) that, when you run it: (1) reads the last 24 h of
`decisions.jsonl`, `paper.db`, `world_state`, and the scorer output; (2) prints the day in
plain English: trades opened/closed, P&L, what the desk rejected and why, what the watcher
did, where the model was wrong; (3) lists the benchmark's "next unmet" conditions; (4)
proposes ONE fix batch and stops for your yes. It never runs the model or places trades.

## 7. The portfolio page in the terminal (later, after the wire)

A new nav tab **DESK** on `localhost:8770` (same design tokens as the rest, `TERMINAL_DESIGN_SPEC.md`):
- **Book**: open paper positions with side, leverage, notional, entry, mark, P&L, stop/target
  distance in own daily moves, days held of hold cap, last watcher verdict, cluster, beta.
  The desk's book line ("3 long, 0 short, net 100% one way — room: shorts only") on top.
- **Decisions**: each decision as a card: market view, chains, skeptic verdict, desk verdicts
  (accepted / bounced / rejected with the number that decided it), seconds and which backend.
- **World**: the current world state page, signals in the last 24 h, live stories with quotes.
- **Research**: the last ChatGPT scheduled read, with its cited sources.
- **Score**: the 15 benchmark categories for the live week, same scorer as the sim.
- **Equity**: paper equity curve, per-trade excess vs BTC, hit rate, exits by reason.
All from `/api/desk/*` routes reading `paper.db`, the run logs and `memory.db`; no numbers
computed in the page.

## 8. Channels

Now: the terminal only (your rule: no delivery yet). The plumbing writes every event to one
`desk_event` table (decision, order, fill, close, watcher verdict, review, error) so that
when you say so, a channel (email, Telegram, Jarvis) is one
reader of that table, not a new code path. Nothing is sent anywhere until you ask.

## 9. Build order — one batch at a time, each shown running

| # | batch | proof you see |
|---|---|---|
| 1 | Codex backend (`SIM_BACKEND=codex`) + usage logging; you sign in first | 3 decisions of Window A on ChatGPT: seconds, tokens, its chains next to Qwen's, scorer run on both |
| 2 | sim → paper book wire (`sim/paper_bridge.py`): decision orders → `paper.db` positions; settle loop closes them | a trade the sim made appears on POSITIONS on `localhost:8770` and moves with the mark |
| 3 | live clock: hourly watcher on open trades (falsifier/checkpoint/cut/trim), 08:00/20:00 decisions, hold cap 7 d; hourly HL candle sync so data is never stale | a day of paper running by itself; the watcher's verdicts on the page |
| 4 | perception P2: signals + world state over the existing feeds (no news yet) | the WORLD panel updating every 15 min; a decision that cites a signal |
| 5 | news P3: GDELT + RSS → stories → claims with quotes and URLs | a story on the page with its sources; a decision card citing it |
| 6 | ChatGPT scheduled research (Mode B) + nightly review | the research read on the page with sources; lessons carrying `loss_class` |
| 7 | DESK tab (§7) | the page |
| 8 | `/desk` Claude Code skill (§6) | run it in chat |
| 9 | portfolio rules on (the net/gross book rule built 2026-09-16, currently unverified) + weekly target the model sees | desk rejecting a 4th same-side long with the reason; the target line in the prompt |
| 10 | benchmark on the live week, then the improvement loop one category at a time | scores file |

Each batch ends with "NOT verified — you test it" until the proof column is shown.

## 10. What you do

1. Sign in to ChatGPT for the CLI: run `codex login` from the bundled binary (or sign in in
   the VS Code ChatGPT panel). I don't touch logins.
2. Say whether the collectors (`scripts/watchdog.py`) should run now.
3. Later: a Task Scheduler entry for boot (I'll give you the exact command to run — it is a
   system setting, yours to run).

## 11. Honest limits

- Speed: local Qwen decisions are ~9 min (measured 446-676 s). ChatGPT via Codex is expected
  20-90 s — **not measured yet**; batch 1 measures it.
- The local model's weaknesses are measured (arithmetic, funding sign flips, rules known but
  not applied); the code now owns those jobs, but the strategist's judgement is still the model's.
- News is zero today. Until batch 5 lands, every decision is data + calendar only.
- The paper book is our own engine against live marks: real prices, but no real fills, no
  slippage beyond the modelled half-spread, no liquidation engine. Good enough to watch the
  logic; not proof of edge.
- The net/gross portfolio rule exists in code but has not been verified on real data
  (batch 9).
