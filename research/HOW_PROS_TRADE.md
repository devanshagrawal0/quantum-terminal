# How Pros Actually Trade Crypto — Testing the "Pure Sentiment / News Is Everything" Thesis

*Research doc, 2026-08-24. Every claim tagged **[EVIDENCE]** (source+URL), **[PRACTICE]** (desk behaviour, widely reported, no single hard study) or **[INFERENCE]** (my reasoning). Written for a small discretionary trader running reasoning+AI, holding hours-to-days, Hyperliquid perps only, who cannot win on latency or capital.*

## The thesis under test
> Crypto has NO fundamental base (no cashflows, earnings, book value), so price is PURELY sentiment, narrative, positioning and crowd movement — reflexive, more like a prediction market than equities. News, exchange listings and social sentiment are THE dominant driver. "Looking at all the quant features" is the wrong game.

**Verdict up front (blunt):**
- **Right** that crypto has a far weaker fundamental anchor than equities, that it is unusually reflexive/narrative-driven, and that *attention and catalysts* dominate more than in most asset classes. The academic evidence backs this.
- **Half-right** that "news/listings/sentiment is the key." Specific, structural catalysts (exchange listings, unlocks, hacks) have documented, tradeable edges. But *social sentiment as a return predictor* mostly fails out-of-sample — it predicts volatility, not direction.
- **Wrong** in the dangerous part: "ignore the quant features." The two things that DO predict crypto returns in peer-reviewed work — **momentum** and **investor attention** — are quant features. And "news is the key" collides with the fact that public news is priced in **seconds**; if his edge is reading the same headline everyone sees, he's the exit liquidity, not the edge. His real edge is *reasoning about positioning and second-order reaction*, not the headline itself.

---

## 1. Is crypto fundamentally different? (no anchor, attention-driven)

**Where the "pure sentiment" thesis holds:**

- **No cashflow anchor is basically true.** There are no earnings, dividends or book value to discount. Valuation models that tried to supply an anchor have failed out-of-sample (see below), which is itself evidence the anchor is weak. **[INFERENCE]**
- **Attention and momentum are the strongest documented predictors.** Liu & Tsyvinski (*Review of Financial Studies*, 2021, "Risks and Returns of Cryptocurrency") find the two strongest predictors of crypto returns are **time-series momentum** and **investor attention** (Google search + Twitter proxies). A 1-SD rise in weekly Google searches → ~1.84% higher BTC return; a 1-SD rise in current-week return → ~3.16% higher next-week return. Crucially, crypto returns load on *network/attention* factors, NOT on production-cost factors. **[EVIDENCE]** https://academic.oup.com/rfs/article-abstract/34/6/2689/5912024 · NBER PDF: https://www.nber.org/system/files/working_papers/w24877/w24877.pdf
- **Reflexivity is a real, named mechanism.** Soros's reflexivity (price → changes the fundamentals it's supposed to reflect → reinforces the bias) and Shiller's *Narrative Economics* both describe exactly the boom-bust feedback loop crypto runs on. This is not folklore; it's the mainstream framework for bubbles and it fits crypto unusually well because there's no fundamental to snap back to. **[EVIDENCE]** https://blogs.cfainstitute.org/investor/2019/01/07/robert-j-shiller-on-bubbles-reflexivity-and-narrative-economics/

**Where it breaks (the counter-case):**

- **On-chain "fundamentals" have partial, real predictive power.** Exchange net-flows, active addresses, transaction volume and large-holder accumulation explain cross-sectional crypto returns and predict 1–4 week direction with statistical significance in multiple studies. So there *is* a weak anchor — usage and flow — it's just not cashflow. **[EVIDENCE]** https://www.nansen.ai/post/onchain-token-flow-analysis-how-it-boosts-cryptocurrency-trading-insights
- **The famous valuation models failed exactly where "pure narrative" predicts they would.** Stock-to-Flow (PlanB) reported in-sample R²≈0.95 then broke completely after late 2021. NVT and Metcalfe explain returns *in-sample* but have "limited to no" out-of-sample predictive power (MDPI 2024). Lesson: crypto has no stable valuation anchor — which supports the trader's core claim — but it *also* means you can't replace narrative with a tidy on-chain formula either. **[EVIDENCE]** https://www.coindesk.com/markets/2020/06/30/why-the-stock-to-flow-bitcoin-valuation-model-is-wrong · https://www.mdpi.com/1911-8074/17/10/443

**Net for section 1:** Crypto is genuinely more attention/narrative-driven and less anchored than equities — the trader is directionally correct. But "no anchor at all" overshoots: momentum and on-chain flow are weak-but-real anchors, and both are *quant features*, which contradicts "ignore the features."

---

## 2. How pros actually make money, by desk type

| Desk | The edge | Crowded? | Reachable at retail on HL perps? |
|---|---|---|---|
| **HFT / market-makers** | Rebates, spread capture, latency arbitrage, inventory management. Co-located, sub-10ms. | Extremely | **No.** He explicitly can't win on latency. |
| **Systematic / quant funds** | Real factors: time-series & cross-sectional momentum, carry (funding), low-vol, on-chain factors. Honest Sharpes 1–2 net; the flashy "Sharpe 7" numbers below are delta-neutral carry, not directional. | Getting crowded | **Partially** — momentum/trend is reachable, factor zoo is not. |
| **Discretionary / narrative traders** | Judgment on which narrative rotates next, sizing, timing, risk. No formal edge — pays for being early and disciplined. | Medium | **Yes — this is his lane.** |
| **Event / listing traders** | Front-run/fade structural events: listings, unlocks, delistings, index inclusions. Documented abnormal returns. | Rising, decaying | **Yes, with caveats** (speed of the announcement leg). |
| **On-chain / flow ("smart money")** | Track whale accumulation, exchange net-flows, smart-money wallets before the crowd. | Medium | **Yes** — data is public (Nansen/Arkham/free explorers). |
| **Funding / basis carry** | Delta-neutral: long spot / short perp, harvest funding. | Very crowded | **Partially** — HL is perps-only, so true cash-and-carry needs a spot venue too. |

**Honest Sharpes / returns:**
- **Delta-neutral funding carry:** reported 19% annualized (2025) up to eye-watering Sharpe ~7.5 with <1% drawdown — but that Sharpe is the reward for a *market-neutral* strategy with tail/basis risk, not a directional bet. Rates can flip negative for days and turn income into cost. **[EVIDENCE]** https://www.kraken.com/learn/futures-trading-funding-rate-arbitrage · https://hyperdash.com/learn/basis-trading-and-funding-rate-arbitrage-on-perps
- **Directional discretionary** has no published Sharpe because it's not a strategy, it's a person. Assume most lose (see the Polymarket 7.6%-profitable stat in §4 as a proxy for "belief trading is hard"). **[INFERENCE]**

**Key takeaway:** the desks with *proven, repeatable* edge (MM, carry) are the ones he can't run. The desk he *can* run (discretionary narrative + on-chain flow + event) has real but fragile edge that lives or dies on discipline and being early.

---

## 3. The news / listing / sentiment playbook in depth (his thesis)

This is where his thesis is strongest — but it splits sharply into "structural catalysts (real edge)" vs "social sentiment (mostly not)."

### Structural catalysts — documented edge
- **Exchange listings (Binance/Coinbase/Upbit effect).** Historically huge: Binance-listed tokens jumped ~41% day-1, ~73% over 30 days ("Binance effect"), mirroring the older "Coinbase effect." **BUT the edge has decayed and inverted:** a 2025 study of 389 tokens found ~98% dump after the initial pump (avg +54% surge → avg −52% decline; +2.78% day-1 → −22.66% at 3 months → −37.64% at 6 months). **The trade is now the fade, not the chase, and the announcement pop happens in seconds.** **[EVIDENCE]** https://www.coindesk.com/markets/2023/01/06/binance-effect-means-41-price-spike-for-newly-listed-tokens · https://bitpinas.com/cryptocurrency/binance-token-listing-dump/
- **Korean listings (Upbit/Bithumb).** A KRW listing on Upbit (>70% of Korean volume) can spike a token 30–100% within minutes on global venues via Korean retail demand; AZTEC +82% on dual KR listing. Fast, real, but the alpha is in the *announcement latency*, which retail loses. **[EVIDENCE]** https://www.coindesk.com/markets/2026/02/20/dual-s-korea-listings-send-ethereum-layer-2-token-aztec-surging-82
- **Token unlocks / vesting cliffs.** ~88.5% of 52 major unlock events showed negative returns within 72 hours; ~90% create negative pressure via front-running. This is *scheduled, public, and calendar-tradeable* — arguably the cleanest reachable edge (short/avoid into a large cliff, especially unlock >2.4× ADV). **[EVIDENCE]** https://papers.ssrn.com/sol3/Delivery.cfm/6632838.pdf?abstractid=6632838 · https://tokenomist.ai/
- **Narrative rotations (AI/DePIN/RWA/meme).** Real and violent: 2024 AI +2,940%, memes +2,180%, RWA +820%; then 2025 flipped — RWA +186%, L1 +80%, while AI −50%, memes −32%, DePIN −77%, GameFi −75%. Sector momentum is real but *mean-reverts hard after the hype*; chasing last quarter's winner is how you eat the −77%. **[EVIDENCE]** https://www.ccn.com/news/crypto/crypto-sector-coingecko-rwa-win-ai-memecoin-lose/
- **Hacks/delistings:** near-instant, mechanical repricing down; only tradeable if you're first or you fade the overreaction. **[PRACTICE]**

### Social sentiment — mostly NOT a return predictor
- The literature is **contested and mostly null on direction.** Message-board / Twitter activity reliably predicts **volatility and volume**, not the **sign** of returns. Studies split between weak-momentum, contrarian, and near-null; causal direction is unresolved (returns drive sentiment as much as the reverse). **[EVIDENCE]** https://www.sciencedirect.com/science/article/abs/pii/S1544612319314199 · https://www.mdpi.com/2227-7390/11/16/3441
- Where sentiment *does* work: **investor attention / novelty / first-mover on a real catalyst** (Liu-Tsyvinski attention factor). That's "a genuinely new thing is getting discovered," not "Twitter is bullish today." The distinction is the whole game. **[EVIDENCE]** NBER w24877 (above).

**The decay problem (critical):** every one of these edges is public and priced fast. Markets price liquid news in **~1 minute or less**; the average retail investor takes **~47 seconds** to act vs <10ms for algos; missing an entry by 5s cut avg profit ~12%/trade. So the *announcement-latency* version of the news trade is unwinnable at retail. The reachable version is the *slower second-order* move: the fade, the follow-through over hours, the positioning unwind. **[EVIDENCE]** https://www.daytrading.com/how-fast-are-things-priced-in · https://www.globenewswire.com/news-release/2026/05/20/3298648/0/en/New-Data-Shows-81-of-Retail-Investors-Struggle-With-Market-Speed-AriseAlpha-Launches-AI-Trading-Bot-for-Crypto-Stocks-and-Forex.html

---

## 4. The prediction-market analogy

**Is "crypto = a prediction market on sentiment" a useful model?** Partly yes as *intuition*, no as *mechanics*.

- **Useful part:** Both are markets on *belief and positioning*, not discounted cashflows. On Polymarket the edge is explicitly "speed, data access, structural arbitrage, and understanding market mechanics — NOT having good opinions." Same is true in crypto: being *right about the narrative* isn't enough; you have to be right about **what's already priced and how the crowd is positioned.** **[EVIDENCE]** https://medium.com/thecapital/the-complete-polymarket-playbook-finding-real-edges-in-the-9b-prediction-market-revolution-a2c1d0a47d9d
- **The sobering stat:** only **7.6% of Polymarket wallets are profitable.** Belief-trading against other belief-traders is close to zero-sum minus fees; most "I have a good take" traders lose. **[EVIDENCE]** https://predscope.com/guide/how-to-make-money-on-prediction-markets (and repeated across the Polymarket-strategy sources)
- **Where the analogy breaks:** a prediction market *resolves* to a truth on a date (that's your anchor and your convergence force). Crypto **never resolves** — there's no settlement that forces price to a fair value, so reflexive trends can run far longer and reverse for no news at all. That makes crypto *harder* than a prediction market, not easier, because you lose the one anchor prediction markets give you. **[INFERENCE]**

**"Trading belief/positioning not value," operationally** = ask three questions on every trade: (1) What does price currently *imply* people believe? (2) Is that belief about to change, or just already fully held? (3) How are people *positioned* (funding, OI, leverage) such that a move forces them to unwind? You're trading the *gap between consensus and what's about to happen*, and the *fuel* (over-leveraged positioning) — not your opinion of fair value. **[INFERENCE / PRACTICE]**

---

## 5. What a small discretionary trader SHOULD do (HL perps, hours-to-days, reasoning+AI)

He can't win on latency or capital. He *can* win on **reasoning, breadth of monitoring, and discipline.** Concrete reachable setups:

1. **Scheduled-catalyst calendar (best risk/reward).** Trade the *known future* events, not breaking news. Unlock cliffs (short/avoid into unlock >2.4× ADV; ~88% print negative), listing fades (short the pump 1–24h after the initial spike once the algos are done), major index/ETF dates. These are public, dated, and reward *preparation over speed*. **[EVIDENCE-backed, §3]**
2. **Fade the listing/news pop, don't chase it.** The day-1 pop is gone in seconds; the 6-month −38% average is the real signal. Reachable trade = short strength into exhaustion with a stop above the wick. **[EVIDENCE, §3]**
3. **Positioning/funding unwinds.** On HL you can see funding + open interest directly. Extreme positive funding + crowded longs into a known event = asymmetric short (a "belief already fully held" trade, §4). This is the single most HL-native edge he has. **[PRACTICE]**
4. **On-chain flow as a slow confirming signal.** Sustained exchange outflows / smart-money accumulation over 1–4 weeks predicts direction with some significance — use it as a *bias filter* for which coins to be long/short, not a trigger. Free/cheap via explorers, Nansen, Arkham. **[EVIDENCE, §1/§2]**
5. **Narrative-rotation, early not late.** Rotate *toward* a narrative when attention is *inflecting up from a low base* (the attention factor that works), and refuse to chase one that's already the "most-followed" (that's where 2025's −50%/−77% happened). **[EVIDENCE, §3]**
6. **The little quant that survives — use it, don't worship it:** (a) **time-series momentum / trend** is the most robust crypto predictor — align entries with it; (b) **volatility/regime** sizing (his own resolved CrashGuard work shows VaR/vol is the feature that actually survives). Combine: reasoning picks the *catalyst and side*, momentum + funding confirm *timing*, vol sets *size*. **[EVIDENCE — Liu-Tsyvinski + his own memory note]**

**How news + reasoning + the little quant combine (the actual loop):** News/AI surfaces a *candidate catalyst* → reasoning asks "is this priced, and how is the crowd positioned?" → funding/OI/momentum confirm the *second-order* trade (fade or follow) → vol sets size → exit on the calendar/mechanical target, not on vibes.

---

## 6. Where he's right and where he's wrong (blunt)

**Right:**
- Crypto has no cashflow anchor and is more reflexive/attention-driven than equities. ✔ (Liu-Tsyvinski; Soros/Shiller; failure of S2F/NVT/Metcalfe out-of-sample.)
- Structural catalysts — **listings, unlocks, hacks, Korean listings, narrative rotations** — are real, documented, tradeable drivers. ✔
- "Prediction-market-like" is a useful *mindset*: trade belief and positioning, not fair value. ✔

**Half-right / needs a caveat:**
- "Sentiment drives price." Sentiment drives *volatility and attention*; as a *directional* predictor social sentiment is mostly null out-of-sample. Attention/novelty on a *real* catalyst works; "Twitter is bullish" does not. ⚠
- "Listings are free money." *Were.* The effect decayed and inverted — 98% dump post-pump. The edge is now the fade and the calendar, not the chase. ⚠

**Wrong (and this is the trap):**
- **"News is THE key, ignore the quant features."** Two problems. (1) Public news is priced in **seconds**; retail is ~47s slow. If his plan is to read a headline and act, he is *structurally the exit liquidity.* The edge was never the news — it's the *reasoning about what's already priced and how people are positioned*, which is a slower, reachable game. (2) The features that actually predict crypto returns in peer-reviewed work — **momentum and investor attention** — *are* quant features, and **his own CrashGuard result found vol/VaR is the feature that survives.** "Ignore the features" throws away the two things with real out-of-sample edge and keeps the one thing (raw news speed) he can't win. **[EVIDENCE + INFERENCE]**

**Bottom line:** He's right that crypto is a sentiment/narrative/positioning game more than a valuation game. He's wrong that this means "news in, ignore features." The correct synthesis: **use reasoning/AI to trade the *second-order* reaction to catalysts (fades, positioning unwinds, scheduled unlocks) — and let the small surviving quant signals (momentum, funding, vol) time and size it.** News is the *trigger to think*, not the edge itself.

---
## Sources
- Liu & Tsyvinski, "Risks and Returns of Cryptocurrency," RFS 2021 — https://academic.oup.com/rfs/article-abstract/34/6/2689/5912024 · https://www.nber.org/system/files/working_papers/w24877/w24877.pdf
- Shiller on bubbles/reflexivity/narrative economics — https://blogs.cfainstitute.org/investor/2019/01/07/robert-j-shiller-on-bubbles-reflexivity-and-narrative-economics/
- Stock-to-Flow critique — https://www.coindesk.com/markets/2020/06/30/why-the-stock-to-flow-bitcoin-valuation-model-is-wrong
- S2F / Metcalfe out-of-sample failure (MDPI 2024) — https://www.mdpi.com/1911-8074/17/10/443
- Binance effect (+41%/+73%) — https://www.coindesk.com/markets/2023/01/06/binance-effect-means-41-price-spike-for-newly-listed-tokens
- Binance listings 98% dump / decay — https://bitpinas.com/cryptocurrency/binance-token-listing-dump/
- Upbit/Korea listing effect (AZTEC +82%) — https://www.coindesk.com/markets/2026/02/20/dual-s-korea-listings-send-ethereum-layer-2-token-aztec-surging-82
- Token unlocks 88.5% negative / 72h (SSRN) — https://papers.ssrn.com/sol3/Delivery.cfm/6632838.pdf?abstractid=6632838
- Narrative rotation returns 2024→2025 — https://www.ccn.com/news/crypto/crypto-sector-coingecko-rwa-win-ai-memecoin-lose/
- Funding/basis carry — https://www.kraken.com/learn/futures-trading-funding-rate-arbitrage · https://hyperdash.com/learn/basis-trading-and-funding-rate-arbitrage-on-perps
- Social sentiment predicts volatility not direction — https://www.sciencedirect.com/science/article/abs/pii/S1544612319314199 · https://www.mdpi.com/2227-7390/11/16/3441
- Speed of pricing / retail lag (~47s vs <10ms) — https://www.daytrading.com/how-fast-are-things-priced-in · https://www.globenewswire.com/news-release/2026/05/20/3298648/...
- On-chain flow / smart-money predictive value — https://www.nansen.ai/post/onchain-token-flow-analysis-how-it-boosts-cryptocurrency-trading-insights
- Polymarket edge & 7.6% profitable — https://medium.com/thecapital/the-complete-polymarket-playbook-finding-real-edges-in-the-9b-prediction-market-revolution-a2c1d0a47d9d · https://predscope.com/guide/how-to-make-money-on-prediction-markets
