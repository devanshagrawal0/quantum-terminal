# The full capability list — everything the trader should have, and what it has
2026-09-16. Built from: Dev's list (graph, chains, event history, sentiment, F&G, order books, market read, search/news, other exchanges, timezones/sessions, who is trading, 100 questions, risk balance, coin types, whales, entry timing, open-trade management, portfolio VaR/CVaR, weights), the two research dossiers (A–J, B1–B10), Hermes Agent's design (fetched: memory tool add/replace/remove with hard size limits, MEMORY.md/USER.md frozen per session, FTS5 session search, background review after each turn that writes memory *and* skills, SKILL.md with When-to-use/Procedure/Pitfalls/Verification, progressive disclosure `skills_list → skill_view`, `skill_manage patch`, write-approval staging, cron with delivery, 7 terminal backends, subagents via RPC scripts; ClawStreet agents storing pattern-skills like "RSI<35 on weekend low volume worked 4/5"), and the always-on AI-hedge-fund vision (perception → analysts with conviction and thesis → allocator over strategy pods → master risk model no agent can override → broker → ledger; research lab backtests candidates and promotes winners).

Status: **H** have (runs today) · **P** partial · **—** missing. Category = benchmark category (C16–C20 are new; see bottom).

## A. Market structure, time and sessions (C16, new)
1. Sessions clock: Asia / Europe / US, weekend, holiday flags per bar — (`session_bucket` column empty) · —
2. Event times in UTC with DST: FOMC 14:00 ET, CPI 08:30 ET, Deribit expiry 08:00 UTC, funding prints every 8h — · —
3. "Who is trading now": volume share by session, weekend liquidity haircut in the risk desk — · —
4. Intraday bars for entries (hourly exists in store; sim decides daily only) · P
5. Market-hours awareness for TradFi-linked moves (US equity open/close, futures) · —
6. Overnight-vs-intraday return split feature · —
7. Liquidity clock: spreads/depth by hour of day per coin — · —
8. Time-to-next-event on every candidate row · —
9. Fed blackout / collision flags · —
10. Calendar of listings, delistings, governance votes, ETF decision dates, quarter-ends · P (unlocks only)

## B. Market read (C2/C3/C4)
11. Regime label from BTC trend × common-share (one-trade %) × vol tercile (12 cells) · P (BTC trend + breadth)
12. Rotation ladder BTC → ETH → large → mid → small → memes with dominance and ETH/BTC slope (`hl/rotation.py` live-only) · P
13. Breadth 1d/7d/above-SMA50 · H
14. Correlation matrices normal and stressed; PC1 share; effective N · H (computed) / — (not shown to model)
15. Cluster map with stability; sector residual indices; cluster rotation table · P (unstable clusters)
16. Beta / crash-beta / R² / idio vol per coin · H
17. Cross-venue dispersion, Korea/India premiums, HL deviation · P (history from 2026-08-23)
18. Overall risk tide score (`hl/macro_regime.py`) time-locked · —
19. Coin archetype: major / large alt / mid / small / meme / new listing, with typical behaviour stats (daily move, crash beta, listing age, tail ratio) · —
20. Per-coin dossier ("how this coin behaves"): own move, crash beta, funding habits, event history, our record on it · —

## C. Crowd, flow, order book (C4, C17 new)
21. Funding with engine crowd labels · H
22. Long-share / top-trader share / 7d change with labels · H
23. Open interest change × price change quadrant · P (OI from 2026-08-23)
24. Funding z-score vs own history; cumulative funding paid 7d · —
25. Liquidation volume and liquidation clusters / heatmap proxy · —
26. Cascade fragility (OI × funding APR × leverage proxy) · —
27. Taker buy/sell ratio, CVD · — (columns empty)
28. Order book: depth at 2%, imbalance, walls, slippage for our size — live only · —
29. Cross-exchange basis and funding gap (HL vs Binance vs Bybit) · P
30. Measured link strengths for every crowd signal shown to the strategist · — (measured, not wired)

## D. Whales and on-chain (C18 new)
31. Exchange netflows, stablecoin supply and mints/burns, TVL · — (columns empty)
32. Whale wallet tracking (HL leaderboard / whale registry), whale net position, flip flag · —
33. Large-transfer alerts, token unlock wallets moving before the date · —
34. Active addresses, MVRV/NVT for majors · —
35. Hack/exploit feed with loss/mcap (DeFiLlama) · —

## E. News, sentiment, search (C5, C4)
36. Time-locked news history (GDELT DOC 2.0, 2017→) as quote-grounded claim cards · —
37. Live search morning/evening/interval (SearXNG self-hosted, Tavily fallback) · —
38. Social volume / dominance / sentiment balance (Santiment-type), Google Trends, X/Farcaster mentions · —
39. Fear & Greed with 30-day path · H
40. Prediction-market odds (8,500 Kalshi/Polymarket markets stored) as consensus · — (not exposed)
41. International sentiment by region/timezone (news tone by country from GDELT) · —
42. Source reliability table; corroboration rule before a side changes · —
43. Fake/irrelevant/instruction injection test (junk harness) with scores · —
44. Narrative tracker: which stories are trending and which coins they touch · —

## F. Questions and investigation (C1)
45. Checklist coverage enforced by the engine (no `done` until 8/8) · —
46. Second-order questions conditioned on answers, logged by round · — (rounds not logged)
47. `compute()` sandbox over time-locked frames with verification gate · —
48. Cross-check rule: a fact that changes a side needs two sources · —
49. Tool-use examples and tool search when >20 tools · —
50. Per-coin dossier tool (BFS-2 over the graph) · —
51. What-changed-since-last-view diff · —
52. Budget: ≤3 computes, ≤N tool calls, per-hat token/latency caps · P

## G. Reasoning, chains, weights (C2, C6)
53. Chains with mechanism → instrument → direction → size → falsifier → checkpoint · H
54. Mechanism vocabulary (fixed seed + proposals with promotion) · —
55. Measured links (local projections / event studies) with admission rule and vintages · — (first link measured by hand)
56. Confidence cap by weakest measured link; unmeasured chains capped · —
57. Belief board: claim, kind, p_model/p_engine/p_final, evidence for/against, falsifier, revisions, Brier · —
58. Outside view first: base rate / analogues injected before the story · —
59. Weights: how much each evidence type counts = its measured link strength × source reliability, shown as "for: 3 (w 2.4) / against: 2 (w 1.9)" · —
60. Combination rule: chain probability ≤ weakest link · —
61. Priced-in score for scheduled events; scheduled ⇒ fade / surprise ⇒ follow prior · —
62. Abstention rule (base-rate n<8, or outside view ≈ market price) and its opposite (must call when evidence is strong) · —
63. Median-of-3 for the number, thinking on for the strategist only · P
64. Contradiction check: orders vs live beliefs vs own market view · —

## H. Memory, learning, skills (C7, C12)
65. Experiences with grades, counterfactuals, lessons, verdicts · H
66. Evidence (decayed), similar (k-NN), calibration, insights lifecycle, notes · H
67. Bi-temporal memory graph (coins, events, mechanisms, beliefs, trades, decisions, sources) with earned links · —
68. Analogues by event type ("6 unlock trades: 5 down") · —
69. Reflection trigger (Σ|excess| or 20 closes) → 3 questions with cited node ids → proposed insights · —
70. Reviewer hat: loss classification (thesis/timing/risk/regime), paired success/failure rounds · —
71. Skills as code (Voyager/SkillOps) with validators, promotion after 2 verified uses, nightly re-validation, retirement · —
72. Hermes-style procedural notes: SKILL.md per pattern with When-to-use / Procedure / Pitfalls / Verification, patch-in-place, write-approval staging · —
73. Hermes-style memory hygiene: hard size cap on the "core notes" loaded every decision, add/replace/remove only, frozen per run for cache · —
74. Session/run search (FTS over past decisions) · P (recall over lessons only)
75. Background review after each decision that writes memory and skills (Hermes) — engine-gated · —
76. Prompt-instruction versions A/B'd against the rule twin (ATLAS offline) · —
77. Curriculum: hypothesis families unlocked as data arrives · —
78. Forgetting by decay only; expired edges, never deleted · —

## I. Skeptic and risk (C8, C9, C10, C11)
79. Skeptic attacks the thesis with counter-evidence; names the card that breaks it; no arithmetic · P (stop remarks only)
80. Risk desk code-only: vol bands, falsifier geometry, target/hold, cluster caps, beta band, stress margin, funding cost, CVaR brake, drawdown breakers · H
81. Event blackout / event-ahead rule for open and new positions · —
82. Stamped-fact, stale-dossier, ledger-truth checks · —
83. `hl/preflight.py` rules ported (no melt-up shorts, no correlated over-concentration) · —
84. Sizing: quarter-Kelly on calibrated p × vol target × caps, validated vs twins · P (formula only)
85. Portfolio-level risk budget: target book vol, gross/net exposure limits · —
86. Capacity / ADV participation per coin · —
87. Stress scenarios a–f (crash+corr→0.9, liquidity vanish, funding flip, calendar error, fake card, stale dossier) · —

## J. Portfolio management (C20 new)
88. Daily portfolio report the model reads: exposure long/short/net, book beta, cluster concentration, VaR/ES (95/99), drawdown, time under water, HHI of returns, hit, payoff, expectancy R, fees+funding %, turnover, calibration · —
89. VaR/CVaR from the stressed correlation matrix and idio vols (not from history alone) · —
90. Allocator over strategy sleeves (carry, event, squeeze, momentum) with a capital slice each and a master risk model no hat can override (ai-hedge-fund) · —
91. Rebalance to targets; drift monitoring · —
92. Margin utilisation under 3σ correlated move vs HL margin · P (stress loss only)
93. PSR/DSR/MinTRL/PBO reported per run · —

## K. Open-trade management (C19 new)
94. Falsifier and checkpoint enforcement · H
95. Mid-trade review at checkpoints: hold / trim / add / move stop, with a logged reason · —
96. Event-ahead check for held coins ("unlock in 3 days: trim") · —
97. Trailing/time stops from the stops_report evidence · —
98. Funding-cost watch on open positions (crowded side flipping) · —
99. Correlation-to-1 alarm → book-level de-risk · —
100. Position ledger reconciliation against the exchange in paper/live · —

## L. Timing and execution (C16/C19)
101. Entry timing inside the day (session, liquidity, event windows) · —
102. Fill model: next-bar-open option, slippage by depth, gap fills in stress · P (fill at level)
103. Order types in paper/live (limit vs market, resting orders, triggers via `hl/triggers.py`) · P (live module exists)
104. Scale-in / scale-out plans · —

## M. Coins and universe (C3)
105. Survivorship-correct universe (delisted stay until delisting) · —
106. New-listing handling (no beta yet, no history: special rules) · —
107. Liquidity floor by ADV and spread per size · P (spread only)
108. Coin knowledge nodes: what the project is, sector, catalysts (from research.db / intel) time-locked · —

## N. Evaluation, survival, honesty (C13, C14, C15)
109. Twins (rule, random, equal-weight, inverse-vol, buy-and-hold) on the same dates · —
110. Walk-forward anchored vs rolling; sign stability; ablations · —
111. Level ladder L0–L5 with kills and post-mortems · —
112. Junk test, seeds, replay cache, backbone swap · —
113. Schema-constrained JSON on every call · —
114. Calibration slope; abstention rate monitor · P
115. Outcome-ranked trace export for later fine-tuning · —

## O. Live paper day (C16–C20)
116. Morning brief (overnight moves, funding/OI, liquidations, ETF print, calendar with times, macro tape, news per position/candidate, odds) · —
117. Intraday monitors (engine) with event wake-ups scoped to the position/event · —
118. Evening review (grade, revise beliefs, market view, insights, calibration, next-24h search) · —
119. Weekly rule-compliance and portfolio metrics; memory consolidation · —
120. Hermes cron for the schedule with delivery (Telegram/email) of the brief and the log · —
121. Candle pipeline fixed (Binance daily zips; store stops at Aug 31 today) · —

## P. Viewer (C3, C6, C7)
122. Graph page, heatmaps (normal/stressed), beta-vs-idio map, belief board, links table, decision replay, kill log, compute audit, junk scores, calendar page · —

**Count: 122 capabilities. Have 12 · Partial 18 · Missing 92.** The benchmark protocol gains five categories: **C16 Market structure & sessions, C17 Order book & flow, C18 Whales & on-chain, C19 Open-trade management, C20 Portfolio risk & allocation** (rungs to be written into BENCHMARK_PROTOCOL.md before the next scoring).

## What Hermes does that we should copy exactly
- A hard-capped core-notes file loaded into every decision, edited only by add/replace/remove, frozen per run (cache-friendly, forces consolidation). Ours: none — the market view is the only carry-over.
- Background review after every decision that decides "memory entry, skill, or nothing", gated by write-approval (ours: the quant gate on insights; extend to notes and skills).
- SKILL.md with Verification section and patch-in-place; progressive disclosure so 100 skills cost ~3k tokens until one is opened.
- Cron with delivery: the paper day's brief and evening review land in Dev's Telegram/email.
- Subagents as RPC scripts that collapse multi-step tool pipelines into one call (our programmatic tool calling for the reviewer).

## Questions for Dev before building (answer in one line each)
1. Live data feeds cost money or keys: Coinglass (liquidations, taker ratio, OI history) is paid; Santiment (social/on-chain) is paid beyond a small free tier; FRED is free with a key. Which do you want: free-only first, or budget for Coinglass + Santiment?
2. Order books and whales cannot be backtested (no history) — accept forward-only for those (paper day), with the sim using only what has history?
3. Sessions/timezones: keep the sim daily for now and do intraday only in the paper day, or move the sim to a 4-hour clock now (4× the model calls)?
4. Delivery: where should the morning brief and evening review go — Telegram, email, or the terminal only?
5. Build order: W2 (calendar/sessions/links/enforced questions) first as planned, or the paper-day loop first so you can watch it live sooner?
