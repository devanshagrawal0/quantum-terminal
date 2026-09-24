# The perception layer — news and data processed as they arrive, kept for the bot
2026-09-16. Dev's requirement: "not only morning — all the news and all should be a constant as it comes; the databases are there; when a value changes the news is analysed, processed and kept for the bot." This is the design, researched before building.

## What the research says (fetched today)
- **News → events, not raw text.** The GDELT event-detection framework (arXiv 2406.10552, text extracted): LLM keyword/concept extraction → text embeddings → clustering (agglomerative / HDBSCAN / k-means / GMM compared) → one summary and label per cluster; LLM embeddings gave the most stable clusters (their CSAI index). *Structured Event Representation* (arXiv 2512.19484): event features extracted by an LLM into a fixed schema beat raw sentiment for out-of-sample return prediction and are interpretable. Polygon.io's production pipeline (B10): copy what the article says (safe), let a database link entities (tickers) and a second call verify — never let the model invent the link.
- **Hermes Agent** (fetched): a background review after every turn decides what becomes a memory entry; core notes are hard-capped and frozen per session so the working picture is small and cache-friendly.
- **Always-on hedge fund** (ai-hedge-fund VISION): perception is point-in-time; analysts emit conviction with a thesis; the ledger persists everything; a single `run_cycle` serves backtest and live.
- **Robustness** (AutoRedTrader, TradeTrap): numbers before text; injected fakes flip decisions unless facts are stamped; state (positions) must come from the ledger, never from text.
- **Local compute**: llama-server serves embeddings (`--embeddings --pooling last`) for GGUF embedding models such as Qwen3-Embedding-0.6B; small reader models (Qwen3-1.7B/4B GGUF) run on CPU at several times the big model's speed — to be measured on this box before relying on them.

## Design
**Three processes, one shared store.**

1. **Feeds (existing watchdog jobs, extended).** Every source writes raw rows with `observed_at`: hourly candles (fix the daily-zip gap), funding prints every 8 h, OI/positioning hourly, cross-venue, calendar (FOMC/CPI/NFP/expiry/unlocks/listings), news every 15 min (GDELT DOC live; RSS of ~20 crypto/macro outlets; SearXNG on demand), prediction-market odds hourly, Fear & Greed daily, macro series daily. In the **simulator** the same feeds are replayed from the archives at each 4-hour step, time-locked by `observed_at`.

2. **The perception daemon (engine + small models, runs continuously, cheap).** On every new row:
   - **Change detection by code**, in the coin's own units: price move since last look in own-daily-moves; funding print flipped sign or crossed ±0.15%/day; OI change beyond 2σ of its own daily changes; positioning long-share ±5 pts; breadth/one-trade share crossed a regime edge; calendar item entered the 24 h / 3 day windows; prediction-market odds moved ≥10 pts. Each becomes a `signal` row: `{ts, kind, coin|market, value, prior, magnitude_in_own_units, surprise_bits, source}`.
   - **News processing by small models** (never the big one): embed each article (Qwen3-Embedding-0.6B); dedup at cosine ≥ 0.92; assign to an existing *story* if cosine ≥ 0.80 to the story centroid, else open a story; for a new or materially grown story, the reader model (Qwen3-1.7B or 4B, measured first) extracts **claims** into a fixed schema: `{quote (verbatim), entity_text, event_type ∈ taxonomy, direction_hypothesis, magnitude_text, time_ref, source_url, fetched_at}`. The engine links `entity_text` to coins/events through the lookup table (coin names, tickers, project slugs, "FOMC/CPI") and stamps `entity_confidence`; the model never assigns a ticker. Corroboration = number of distinct domains in the story. Novelty = 1 − max cosine to any story in the last 14 days. Story importance = corroboration × novelty × (coin is in our universe or is BTC/ETH/macro).
   - **World state** (Hermes-style, hard-capped ~2,000 tokens, versioned): the current regime line, the top signals of the last 24 h, the live stories with importance ≥ threshold (one line each with quote count and coins), the next three calendar items, the open positions with their latest checkpoint status, and "what changed since the last decision". Rewritten by code on every signal; the model reads it at every wake-up instead of re-asking the same eight questions. The full raw rows stay queryable by the tools.

3. **Wake-ups from signals (the runner).** Position re-check (short, no thinking) when any signal touches a held coin or its cluster, when a checkpoint is due, or when an event enters 24 h; a full decision when the world state's importance sum since the last decision crosses a threshold or on the daily morning slot. Everything the daemon produced is logged with the decision so the benchmark can score provenance and speed (time from a row's `observed_at` to its `signal` row = the "how fast does it receive it" number, reported per feed).

## Simulator vs live
- Sim: 4-hour clock; the daemon runs over the archives (GDELT 2017→, our series) producing the same `signal`/`story`/`claim`/`world_state` rows *as of each step*; decisions use them. Backtests therefore include news the way a trader would have read it, and the junk test injects fakes into the same pipeline.
- Live paper: the daemon runs on real time under the watchdog; identical code path (`run_cycle`), same tables.

## Cost on this box (to be measured, not assumed)
- Embedding 0.6B: expected tens of articles per second on CPU; reader 1.7B: expected 40–80 tok/s; a claim extraction ≈ 200 tokens ≈ 3–5 s per story. RAM: +~2.5 GB for both small models — feasible only with the other chats closed, or by running the reader in the gaps between the big model's decisions.
- Big model calls per day in the sim: 1 morning scan (~2 min) + re-checks only on signals (~1–2 min each) + full decisions on demand (~10 min). August ≈ 3 h.

## Tables
`signal(id, ts, observed_at, kind, coin, value, prior, magnitude_units, surprise_bits, source)` · `story(id, first_ts, last_ts, centroid, n_articles, n_domains, importance, label, coins)` · `article(id, ts, url, domain, title, text_hash, story_id, embedding)` · `claim(id, story_id, article_id, quote, entity_text, entity_link, entity_confidence, event_type, direction_hypothesis, magnitude_text, time_ref)` · `world_state(version, ts, text, tokens)`.

## Build order (each step shown on real output)
P1. Measure the two small models on this box (speed, RAM) and choose them.
P2. `signal` detector over the existing feeds + `world_state` writer; wire into the sheet and the wake-ups. (No news yet; proves the change-detection half on the August data.)
P3. GDELT historical pull for 2025–2026 + RSS live; article/story/claim pipeline with the small models; junk-test hooks.
P4. 4-hour sim clock with position re-checks and management actions (hold/trim/add/move stop/exit), hold cap 7 days.
P5. Live paper day on the watchdog with the same code path.

Nothing here is built yet. The benchmark gains the timing metric (observed_at → signal latency per feed) under C16.
