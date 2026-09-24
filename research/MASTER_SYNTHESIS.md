# MASTER SYNTHESIS — everything we now know, in one place

**Date:** 2026-09-02
**What this is:** the combination of 8 research documents totalling ~450 KB, produced across three independent tracks that did not see each other's work.
**What this is NOT:** verified truth. Almost everything below is *read from papers*, not measured on our data. Where three independent tracks agree, confidence is higher — but agreement is not proof.

---

## 0. THE DOCUMENT INVENTORY

| Doc | Lines | Size | Who wrote it | What it covers |
|---|---|---|---|---|
| `CROSS_VENUE_FEATURES.md` | 1,001 | 65 KB | earlier work | The 26-venue panel: features, 15 ranked build items, failure modes, validation maths |
| `NEWS_IMPACT.md` | 654 | 45 KB | earlier work | Event taxonomy with sizes/decay, cap tiers, contagion, long/short playbook, 15 testable hypotheses |
| `SOURCES.md` | 511 | 64 KB | earlier work | News/data source master list, ranked top-25, dedup problem |
| `HOW_PROS_TRADE.md` | 128 | 20 KB | earlier work | Desk types, what edge is reachable at retail |
| `MARKET_MECHANICS.md` | 218 | 22 KB | **me, today** | How markets work from zero: price formation, impact, vol, factors, derivatives, efficiency |
| `EXECUTION_AND_GAPS.md` | 202 | 22 KB | **me, today** | Execution + the 5 gaps nobody had covered |
| `DRIVER_TAXONOMY.md` | 560 | 86 KB | **Agent 2, today** | Every price driver quantified: direction/size/horizon/speed/decay |
| `WORLD_CONTEXT.md` | 988 | 108 KB | **Agent 1, today** | Geography, law, calendar, company events, competitive dynamics — the 29 items |

**Total: ~4,262 lines / ~432 KB.**

---

## 1. THE CONVERGENT FINDINGS (highest confidence — independent tracks agreed)

These matter most because three separate research efforts, with no visibility into each other, landed on the same conclusions.

### 1.1 The binding constraint is STATISTICAL, not informational

Every track hit this independently:

| Source | The finding |
|---|---|
| `CROSS_VENUE` §4.3 | An IC of 0.03 **cannot be distinguished from zero** on one year of daily data. SE(IC) ≈ 1/√365 ≈ 0.05 |
| `CROSS_VENUE` §6.6 | ~1,200 candidate features × 365 dates ⇒ **~60 "significant" results by pure chance** at α=0.05 |
| Harvey-Liu-Zhu (via both) | A new factor needs **t > 3.0**, not 2.0 — and we're in a worse multiple-testing position than the published literature |
| `MARKET_MECHANICS` §6 / Agent 2 §12 | McLean-Pontiff: **−58% post-publication decay**. Universal haircut **× 0.42** |
| Agent 2 §12 | Hou-Xue-Zhang: **65% of 452 anomalies fail t>1.96**; 82% fail t>2.78 |
| Agent 1 §H | The world layer **makes small-N worse** — a country changes its crypto tax law roughly once |
| Our own DB audit | **9.9 days** of stored cross-venue history. 31 days of positioning. |

**Conclusion: more features and more sources cannot fix this. Only time and ruthless selection can.** This is the single most important line in 432 KB of research, and it was reached from four different directions.

### 1.2 Look-ahead is the #1 way we will fool ourselves

| Source | The specific trap |
|---|---|
| `newsystem.md` §12.4 | LLM contamination — a model that already knows how 2023 resolved |
| `CROSS_VENUE` §6.7 | Full-sample z-scoring / centred windows — "the most common silent lookahead" |
| `CROSS_VENUE` §6.4 | Survivorship — today's coin list excludes everything that died |
| `NEWS_IMPACT` trap #7 | News archive timestamps are *publication*, not *when we'd have received it* |
| Agent 1 §H | **Bitemporal rule**: using a law's `effective_date` without storing when it was *knowable* |
| `EXECUTION_AND_GAPS` §2 | Fitting an HMM on the full sample then labelling history backwards |

**All six are the same bug wearing different clothes: using information that did not exist yet.** The defence is one rule — **every record stores both when it was true (`valid_from`) and when we learned it (`observed_at`), and every backtest filters on the latter.**

### 1.3 Costs decide everything

- OFI at 10-second frequency: **bid-ask cost exceeded gross edge by 164×** (`MARKET_MECHANICS` §2)
- Borrow fees: a **+0.14%/mo gross** long-short becomes **−0.01%/mo net** (Agent 2 §12)
- Funding at our horizon: **21 bps over a 7-day hold vs 9 bps round-trip fees** — funding is the *bigger* line (`CROSS_VENUE` §1.6)
- Break-even IC at our cost level: **~0.012**; realistic target 0.03–0.05; anything **>0.10 means a bug** (`CROSS_VENUE` §4.3)
- Novy-Marx–Velikov: only **sub-50%-monthly-turnover** strategies generally clear costs (Agent 2)

**Every candidate must be evaluated after costs from day one, never as an afterthought.**

### 1.4 Mechanical beats predictive

Things where *someone is structurally forced to transact* persist. Things that merely *predict* decay.

- **Carry / hedged funding** — our own walk-forward already found it's the only survivor. Agent 2 independently ranked it Tier-1 #4, citing BIS WP 1087.
- **Token unlocks** — mechanical one-directional supply. Agent 2 Tier-1 #2, flagged *"best fit for a Hyperliquid-based system."* 88.5% negative in 72h across 52 events.
- **Lockup expiry** — −1.5%, no reversal, **stable over a 10-year sample**.
- **Liquidation cascades** — OI = fuel, funding = which side, liquidations = reset. Fragility is measurable *in advance*.

### 1.5 Overnight vs intraday must be a separate column

Both agents flagged this independently. Lou/Polk/Skouras (JFE 2019): essentially the **entire US equity risk premium accrues overnight**; momentum is overnight-only, while value/profitability/investment are intraday with **opposite-signed overnight legs**. Merging the buckets destroys real effects.

For crypto: the equivalent is **session bucket** — the weekend/Asia/US-hours split, where a $5M order moves BTC **$20–30 on a Wednesday vs $80–150 on a Sunday morning** (4–5×).

### 1.6 Attention ≠ sentiment (and blending them gives zero)

- Agent 2: attention and sentiment predict **opposite signs**; the blend is null.
- `HOW_PROS_TRADE`: social sentiment predicts **volatility and volume, not direction**. Liu-Tsyvinski's *attention* factor works; "Twitter is bullish" does not.
- `NEWS_IMPACT` §6.1: an LLM-sentiment study found **significant in-sample gains, zero out-of-sample**.

**This is why a sentiment score is the wrong primitive** — the exact point made at the start of this project, now confirmed from three directions.

---

## 2. WHAT IS DEAD (do not build)

Consolidated from Agent 2 §12 and the others:

| Dead | Evidence |
|---|---|
| S&P 500 index inclusion | 9.6% → 7.5% → 5.1% → 1.6% → ~0 |
| Pre-FOMC drift | +49 bps → gone after 2015 |
| Large-cap PEAD | Zero for non-microcaps since ~2001, large caps by ~2006 |
| Industry momentum | Cumulative ≈ 0 since 2000 |
| Textbook sector rotation | "Early-cycle leaders" **underperformed by 5 bps/month** |
| Russell reconstitution | "Much smaller to nonexistent"; crowding documented |
| Analyst-consensus long-short | 102 bps/mo gross, eaten by near-daily rebalancing |
| Halt-fade | LULD removed the reversal |
| Naive blended social sentiment | Attention/sentiment sign conflict ⇒ null |
| Venue-to-venue lead-lag at 5-min | Our sampling can't resolve it; collection-order artifacts |
| Amihud illiquidity (for us) | Already diagnosed as an outlier artifact in this system |
| Kimchi zero-crossing signal | Unverified, no sample period, no SEs, smells overfit |

---

## 3. WHAT SURVIVES — filtered for **crypto + our size**

Agent 2's Tier-1 list is **heavily equities-weighted** (insider Form 4, lockup expiry, SEO dilution). Filtering to what we can actually trade on Hyperliquid:

| # | Edge | Why it's ours | Status |
|---|---|---|---|
| 1 | **Crypto carry (hedged funding)** | Already proven in our own walk-forward as the *only* survivor. Free complete data. A genuine premium, not an anomaly | **Proven on our data** |
| 2 | **Token unlocks** | Free deterministic schedules. Mechanical supply. 88.5% negative/72h. Weakening starts **30 days early** ⇒ no latency race. Perps ⇒ no borrow wall | `unlocks.db` has 142 tokens (dates only, **no sizes**) |
| 3 | **Post-listing decay** | ~98% dump after the initial pump; +2.78% day-1 → −22.66% at 3mo → −37.64% at 6mo. The trade is the **fade**, not the chase | Not built |
| 4 | **Liquidation-cascade fragility** | OI + funding + positioning measure how loaded the market is *before* the trigger. We already collect all three | Data exists, unused |
| 5 | **Spot-perp basis** (`CROSS_VENUE` #1) | The panel's unique asset — consolidated spot AND perp for 177 coins. Cross-sectional (177 obs/day), persistent, mechanistically grounded | **Best untested candidate** |
| 6 | **Residual 7d momentum, skip-1d** | The only crypto cross-sectional predictor with real published evidence at our exact horizon | Not built |
| 7 | **`top_minus_retail`** (Binance top-trader vs account ratio) | Closest available proxy for informed-vs-uninformed positioning; persists for days | **31 days of data already stored** |

---

## 4. THE ARCHITECTURAL INSIGHTS

### 4.1 A calendar is not a feed (Agent 1's core finding)

| | Feed | Calendar |
|---|---|---|
| Time direction | past only | **future** |
| Primary key | `(source, published_at)` | `(entity, scheduled_ts)` |
| Mutation | append-only | **rows mutate** — dates move, `confirmed` flips, outcome fills in |
| Latency need | milliseconds | **none — prepare for weeks** |
| Edge lives in | speed | **positioning + conditional priors** |

**A feed has no repeat key**, so it can never build `P(move | event_type, entity, regime)`. A calendar can. This is the concrete mechanism for the "anticipatory not reactive" idea we had only as a hypothesis.

Derived for free from a calendar: **Fed blackout windows** (exact published rule — 00:00 ET the second Saturday before the meeting), collision detection (two events in 48h), and event-vol vs diffusive-vol decomposition.

### 4.2 The type system the graph is missing

`Iran → oil → inflation → yields → risk → BTC → alts` is currently **one hardcoded chain**. With `jurisdiction`, `facility`, `chokepoint`, `commodity`, `company`, `law_instrument` as real node types, it becomes a **traversal** — which also produces the chains we didn't think to write down.

Highest-value single table (Agent 1): **`company_jurisdiction(company_id, jurisdiction_id, role)`** where role ∈ {incorporation, tax_residence, listing, primary_operations, regulator}. A company has five different "wheres" and they diverge.

### 4.3 Execution: at our size, the textbook problem doesn't exist

Median Hyperliquid metaorder = **$8,500**. Our account = **~$90**. We are ~100× below the median.

> **Market impact is irrelevant to us. Cost = spread + fees + funding.**

Almgren-Chriss, participation optimisation, iceberg splitting — all solve a problem we do not have.

**But one HL-specific finding does apply:** Barone & Lillo measured that **visible native TWAPs cost ~8.9 bps LESS** than hidden metaorders on Hyperliquid (permanent impact 5.4 bps less; impact exponent β=0.303, not 0.5). Announcing intent *attracts* liquidity (+$4,200 depth within 5 spreads). That is the opposite of the standard instinct, measured on our venue.

---

## 5. HONEST CONTRADICTIONS BETWEEN THE DOCS

Not everything agrees. Flagging rather than papering over:

1. **`HOW_PROS_TRADE` says discretionary/narrative is "his lane"; `NEWS_IMPACT` says public news is priced in seconds and retail is ~47s late.** *Resolution:* both are right about different things — the *headline* is unreachable, the *second-order consequence* (fade, positioning unwind, scheduled follow-through) is reachable. The lane is real but it is not "read news fast."

2. **`CROSS_VENUE` assumes impact matters; `EXECUTION_AND_GAPS` says it doesn't.** *Resolution:* not a contradiction — different size regimes. CROSS_VENUE was written for a 20–50 position book; at $90 with 1–2 positions, impact vanishes and spread dominates.

3. **Agent 2 ranks equities edges Tier-1; we trade crypto.** *Resolution:* its ranking was asset-agnostic by design. Filtered to crypto (§3 above), only unlocks and carry survive its own Tier-1.

4. **Post-ETF BTC–alt "decoupling"** — one 2026 paper claims BTC is no longer a systemic factor for alts; `NEWS_IMPACT` calls this **contested, one paper against a lot of contrary tape.** Agent 1 notes BTC–NDX swung from ≈−0.68 to ≈+0.72 in ~two weeks in early 2026. *Resolution:* **never hardcode a correlation.** Measure it rolling, and detect breaks.

---

## 6. THE BLOCKERS (what actually stops us)

| # | Blocker | Detail |
|---|---|---|
| 1 | **9.9 days of history** | Cannot estimate a single causal edge (`newsystem.md` §11) or validate any signal. **Only fixable by bulk backfill + time.** |
| 2 | **`hl.db::book_snapshots` is EMPTY** | Designed with microprice/imbalance/spread/depth columns, **0 rows**. So is `candles`, `funding`, `trades`, `ctx_snapshots`, `feature_snapshots`. The cost model has no data behind it. |
| 3 | **No arrival-price logging** | Without decision-time price stored, TCA is impossible retroactively — and cost *is* our whole execution problem. |
| 4 | **`unlocks.db` has dates, not sizes** | Our #2 edge needs unlock/float and unlock/ADV (thresholds: >1% supply, >2.4× ADV). Currently unusable. |
| 5 | **No options data** | Only the DVOL index. No skew, no RR, no term structure, no gamma. |
| 6 | **No borrow-fee source (free)** | Agent 2: "the highest-value missing dataset." Blocks most equity short signals — less relevant for us since perps have no borrow. |
| 7 | **Macro read live, never stored** | The §11 causal chain (oil→inflation→yields→risk) needs stored deep history. FRED fixes this cheaply. |

---

## 7. THE FREE DATA STACK (consolidated, both agents + our audit)

**Already wired & verified:** 26 CEX venues, Hyperliquid (incl. wallet-level `recentTrades.users`), Lighter, Binance top-trader positioning (172 coins/1h/31d), 19 social channels, CoinGecko, unlocks, F&G, arXiv, Kalshi/Polymarket.

**Free, high-value, NOT wired:**
- **`data.binance.vision`** — bulk historical archive. **The fix for blocker #1.**
- **FRED** — free key; `DGS10`, `DGS2`, `T10Y2Y`, `DCOILWTICO`, `CPIAUCSL`, `PAYEMS`, `WALCL`, `VIXCLS`, HY/IG OAS. Decades of history.
- **Deribit options chain** — `get_instruments`, `get_book_summary_by_currency`, `ticker`.
- **GDELT 2.0** — global news volume + tone, **65 languages**, 15-min updates. The honest free substitute for local-language sentiment.
- **Federal Register API** — structured, timestamped rules/tariffs. Agent 1: "under-used."
- **IMF PortWatch** — daily transits for 28 chokepoints (exact ArcGIS endpoint captured).
- **GLEIF** — jurisdiction + parent hierarchy, no key, no registration.
- **Geopolitical Risk Index** — monthly GPR + **daily GPRD**, free CSV.
- **SEC EDGAR** — full XBRL/Form 4/full-text stack, no key, ≤10 req/s.
- **Central-bank calendars** — seed from `bis.org/cbanks.htm` (treat aggregators as convenience, not primary).

---

## 8. WHAT WE STILL DON'T HAVE

- **No free borrow-fee data** (Agent 2's #1 gap)
- **No free local-language retail sentiment** (Naver/Weibo) — genuinely paid; GDELT is the substitute
- **No vessel cargo detail** — PortWatch gives counts, not contents
- **No analyst consensus** (blocks clean PEAD)
- **No point-in-time index constituents** (survivorship contamination)
- **No historical options chains with OI** (only forward collection is free)
- **No peer-reviewed vanna/charm magnitudes** — gamma has Barbon-Buraschi; vanna/charm has vendor numbers only
- **Zero code** in `data_layer/` — the structure exists, nothing is built

---

## 9. THE ONE-PARAGRAPH SUMMARY

We have excellent, broad, free data and now ~432 KB of research telling us what to do with it. Three independent tracks converged on the same verdict: **the constraint is not information, it is statistics and time.** The things that survive are *mechanical* (someone is forced to transact) rather than *predictive*, and for us on Hyperliquid that shortlist is short — carry, unlocks, post-listing decay, cascade fragility, spot-perp basis. The architecture needs two things it doesn't have: a **calendar** (future rows, so we can anticipate rather than react) and a **typed entity graph** (so causal chains are traversals, not hardcoded strings). And every single track independently warned about the same failure mode: **using information that didn't exist yet.** The fix for all of it starts with the least glamorous possible task — **backfill history, log arrival prices, fill the empty tables** — because without those, nothing above can be tested at all.

---

## 10. SOURCE DOCUMENTS

All in `research/`: `CROSS_VENUE_FEATURES.md` · `NEWS_IMPACT.md` · `SOURCES.md` · `HOW_PROS_TRADE.md` · `MARKET_MECHANICS.md` · `EXECUTION_AND_GAPS.md` · `DRIVER_TAXONOMY.md` · `WORLD_CONTEXT.md`
Plus the design doc: `../newsystem.md` and the data layer: `../data_layer/`
