# MARKET MECHANICS — how markets actually work, from zero

**Scope:** the *mechanics* — how price forms and moves. (The other two research tracks cover the world/context layer and the driver taxonomy.)
**Method:** web research, Sep 2026. Real numbers cited where they exist. Where a number is uncertain I say so rather than inventing it.
**Bias check:** every section ends with **"what this means for us"** — and several of them say *don't bother*, because that's the honest answer.

---

## 1. What a price actually is

A price is not a number the market "has". It's **the last agreement between two counterparties**, sitting inside a **limit order book (LOB)**.

- The LOB is a **continuous double auction**: resting buy orders (bids) below, resting sell orders (asks) above, sorted by **price priority, then time priority**.
- **Best bid / best ask** are the top of each queue. **Mid** = their average. **Spread** = the gap.
- Two order types do different jobs:
  - **Limit order** = joins a queue, *provides* liquidity, pays no spread, but may never fill.
  - **Market order** = crosses the spread, *consumes* liquidity, fills instantly, pays the spread.
- **Who provides liquidity:** market makers quoting both sides, earning the spread as compensation for two risks — **inventory risk** (being left holding a position) and **adverse selection** (the person hitting your quote knows something you don't).

**The mid-price is a lie for prediction purposes.** If there are 100 bids and 5 asks, the true "fair" price is much closer to the ask. The fix is the **microprice** — a size-weighted mid — which is a materially better short-horizon predictor than the naive mid.

**What this means for us:** any feature we compute off the naive mid is subtly wrong. If we're computing anything book-related, use microprice. We already store `microprice` and `imbalance` in `hl.db::book_snapshots` — but that table has **0 rows**. It was designed and never filled.

---

## 2. Why prices move

Three distinct causes, constantly mixed together:

1. **Information arrival** — new facts change what the asset is worth. Permanent price change.
2. **Order flow / inventory pressure** — someone big needs to trade. Temporary price change that *partially reverts*.
3. **Liquidity withdrawal** — nobody changed their mind about value, the book just got thin (weekends, holidays, pre-news). Same order now moves price far more.

**Market impact — the single most important practical fact:**

- **Kyle (1985)** predicts impact is **linear** in size ("Kyle's lambda") and permanent.
- **Reality disagrees.** Empirically impact follows the **square-root law**: impact ∝ √(volume), with the measured exponent between **0.5 and 0.7**. This holds with striking universality across markets, and is still not fully explained theoretically.

Practical consequence of √: **trading 4× the size costs ~2× the impact, not 4×.** Impact per unit *falls* with size — but total cost still rises, and it's why execution splitting exists.

**Order flow imbalance (OFI)** — the net of buy vs sell pressure — is one of the most reliable short-horizon predictors that exists. **But:**

> Research finding: an OFI strategy at **10-second** execution frequency did **not** survive costs — **bid-ask crossing cost exceeded the gross signal edge by a factor of 164.**

That is the whole retail-microstructure trap in one number.

**What this means for us:** OFI is real and predictive and **we cannot trade it directly** — we'd pay 164× our edge in spread. Its legitimate use for us is as a **confirmation feature** ("is flow agreeing with our thesis?"), not a standalone signal. Also: prices move for a reason that has *nothing to do with news* far more often than a news-driven system will assume.

---

## 3. Microstructure

| Concept | What it is | Why it matters |
|---|---|---|
| **Spread** | ask − bid | Your round-trip cost floor. Widens exactly when you want to trade. |
| **Depth** | size resting at each level | How much you can do before you move it |
| **Microprice** | size-weighted mid | Better short-horizon fair value than mid |
| **OFI** | net buy vs sell pressure | Strongest short-horizon predictor; killed by costs |
| **Adverse selection** | the informed pick you off | The reason spreads exist at all |
| **Tick size** | minimum increment | Larger tick ⇒ imbalance predicts *more* strongly |
| **Queue position** | where you are in line | Determines whether a passive order ever fills |

**Market making (Avellaneda–Stoikov):** the optimal quote decomposes into two pieces — an **inventory-risk premium** and a **liquidity/order-arrival edge**. The maker skews quotes based on current inventory, which acts as a mean-reverting control pulling the position back to flat. Reported to cut terminal-inventory variance by ~an order of magnitude vs symmetric quoting.

**Regime-dependence, stated plainly:** OFI's predictive strength is **not stable** — high in some regimes, near-random in others. A model fit on one regime will fail in another. This is the same warning as `newsystem.md` §11.5, arriving from a completely different direction.

**What this means for us:** the realistic microstructure edge for a small operator is **not** predicting the next tick — it's **paying less** (posting instead of crossing, avoiding thin books) and **not getting run over** (detecting when the book is thin before sizing up).

---

## 4. Volatility

- **Realized vol (RV)** — backward-looking, computed from returns.
- **Implied vol (IV)** — forward-looking, extracted from option prices.
- **Volatility clustering** — big moves follow big moves. Arises from mean-reverting vol dynamics; nearby points share history, correlation decays exponentially. Modelled with EWMA/GARCH/HAR.
- **Regimes** — vol is best described as switching between states, not drifting smoothly. Research finds risk premia *differ by regime*, and **low-vol regimes carry relatively high variance risk premium**.
- **Variance risk premium (VRP)** = implied − subsequently realized. **Persistently negative on average** (i.e. options are systematically priced above what gets realized) — compensation for bearing crash risk. Mean-reverting, spikes and clusters in crises.
- **Term structure** — usually upward sloping (**~53%** of samples) but **U-shaped ~23%** of the time. Not a simple monotone curve.

**What this means for us:** VRP is one of the few genuinely persistent, mechanically-explained premia — it exists because someone must be paid to insure crashes. It is also **exactly the thing that kills you when you're short it** at the wrong moment. Relevant to §3.4's convex structures: buying convexity is usually *paying* VRP, i.e. paying a small negative carry for protection. That cost is the price of surviving unvalidatable rare events.

---

## 5. Momentum vs mean reversion

They are not contradictory — **they live on different horizons**:

| Horizon | Behaviour |
|---|---|
| Days (short) | **Reversal** |
| 3–12 months | **Momentum / continuation** ← the classic momentum window |
| 3–5 years | **Reversal** again |

**Why (behavioural):** under-reaction to news at first (slow diffusion of information), then over-extrapolation, then eventual correction. Daniel et al. (1998), Barberis et al. (1998), Hong & Stein (1999).
**Why (risk-based):** factor loadings vary over time; some of what looks like over/under-reaction is time-varying conditional risk premia.

**Honest note:** it is genuinely hard to distinguish "risk premium" from "mispricing" empirically, and results are sensitive to which asset-pricing model you benchmark against.

**What this means for us:** the *horizon is part of the signal*. A momentum signal computed on the wrong window is a reversal signal with the sign flipped. Dev's prior finding — that momentum added nothing in his own walk-forward tests — is consistent with the literature *if* the window used was in the reversal zone rather than the 3–12 month continuation zone.

---

## 6. Risk premia and factors — why they exist at all

Two competing explanations, and the fight is unresolved:

1. **Risk-based** — the return is compensation for bearing a real risk nobody wants (crash risk, illiquidity, recession sensitivity). If true, **the premium persists** because the risk doesn't go away.
2. **Mispricing/behavioural** — persistent errors from behavioural biases. If true, **the premium decays once known**.

**The factor zoo / replication crisis:** hundreds of published factors, and a serious argument that most are multiple-testing artifacts. Counter-evidence exists too — Bayesian replication work claims the majority *do* replicate, cluster into ~13 themes, and hold out-of-sample across 93 countries. **The field genuinely disagrees.**

**The number that matters most:**

> **McLean & Pontiff:** returns to 97 published characteristics decline **~58% after publication** (~50% of alpha disappears). Investors read the paper and arbitrage it away.

And crucially: **decay scales with capacity constraints** — slower, *less liquid* strategies decay *more*, because they attract arbitrage capital relative to the liquidity available to absorb it.

**What this means for us:** every published factor we might use should be assumed **~50% weaker than its paper**, minimum. And a "well-known" factor in a liquid market is the worst of both worlds. This is direct empirical support for `newsystem.md` §1's capacity-constrained-corners thesis — *and* a warning that even those decay once found.

---

## 7. Derivatives mechanics — and how they feed back into spot

### Perpetual futures & funding
- A perp has no expiry; **funding payments** tether it to spot. Longs pay shorts when the perp trades rich, and vice versa.
- Typical construction: `funding = premium index + clamp(interest rate − premium index, ±0.05%)`, with the interest component often fixed near **0.01% per 8h**.
- **The crowded side pays.** Funding converts price divergence into a **carrying cost**, which is what pulls the perp back to spot.
- **Cash-and-carry** (long spot / short perp) harvests this: historically **~10–30% annualised** in bullish, persistently-positive-funding periods. **This is the one strategy family Dev's own walk-forward already found survives.**

### Price discovery has moved to perps
- Perps are ~**93%** of crypto futures volume; Binance perp-to-spot ratio for BTC runs roughly **5–10×**.
- Research finds **perpetuals on unregulated venues lead price discovery**, with regulated futures and US spot *reacting*. Evidence isn't unanimous (spot leads at some frequencies/during stress), and there's active debate about whether Hyperliquid has displaced Binance as the discovery venue.

### Options → spot feedback (dealer gamma / vanna / charm)
- **Positive dealer gamma** ⇒ hedging *suppresses* volatility ⇒ chop and **pinning** near heavy strikes.
- **Negative gamma** ⇒ hedging *amplifies* moves ⇒ acceleration.
- **Vanna:** IV falls ⇒ dealers short options must **buy** underlying ⇒ "volatility-reset" rallies.
- **Charm:** time decay forces continuous hedging into the close; small per minute, cumulatively significant.
- **Regime rule of thumb from the research:** in quiet tape gamma is silent and *vanna/charm dominate*; in violent tape *gamma dominates* and the second-order flows are noise.

**What this means for us:** funding/basis is mechanical, explainable, and already proven in our own testing — it deserves priority over anything predictive. The perp-leads-spot finding says our **lead-lag/venue analysis should treat perps as the signal source, not spot**. And options feedback is a real mechanism we currently have **zero** data for (we only pull the DVOL index).

---

## 8. Liquidity, capacity, and why edges die

- **Capacity** is the amount of money a strategy can absorb before its own impact eats the edge. Square-root impact means capacity is finite and *computable*.
- **Crowding** — when many run the same signal, they trade the same direction at the same time. Entry impact worsens, and exits become correlated (everyone runs for the same door).
- **Decay is empirical, not theoretical:** ~58% post-publication (§6), and worse for less-liquid strategies.

**The asymmetry that actually favours us:** a fund deploying $500M *cannot* trade a market that absorbs $50k. That market is therefore **structurally under-arbitraged** — not because it's hard, but because it's **not worth their time**. Small size converts from a weakness into the entry ticket.

**What this means for us:** capacity must be **estimated up front for every candidate edge**, not discovered after deployment. And "this edge only works in small size" is a *feature*, not a disclaimer.

---

## 9. Efficiency — why anomalies survive at all

Markets aren't efficient because arbitrage is free; they're *approximately* efficient because arbitrage is **risky and costly**. The four classic **limits to arbitrage**:

1. **Fundamental risk** — the market moves against you for unrelated reasons.
2. **Noise-trader risk** — the mispricing gets *worse* before it corrects. You can be right and still be liquidated first.
3. **Resale/horizon risk** — you may be forced to exit before convergence.
4. **Implementation costs** — spread, slippage, borrow costs, short-sale constraints. (See the **164×** OFI number in §2.)

Also: arbitrage capital is concentrated in few, specialised, poorly-diversified players who face their own constraints.

**What this means for us:** an anomaly persisting is *evidence someone couldn't or wouldn't take it*, and the first question must always be **"why hasn't this been arbitraged away?"** If we can't answer that, the likely answer is *it has been, and we're looking at noise*. Noise-trader risk is also the formal name for Dev's "right thesis, wrong timing" problem — and the reason for convex structures and survival sizing.

---

## 10. Crypto-specific mechanics

- **24/7, but not uniformly.** The weekend is a real, *structural* liquidity hole: BTC weekend share of weekly volume fell from **~24% (2018) to ~16–17%** recently. Institutional desks and market makers scale down Saturdays/Sundays and widen quotes.
- **Concrete impact number:** a **$5M** market buy that moves BTC **$20–30** on a liquid Wednesday can move it **$80–150** on a Sunday morning. *Same order, 4–5× the impact.* Time-of-week is a genuine feature, not trivia.
- **Liquidation cascades** — the defining crypto mechanic. Price falls → longs hit liquidation → exchange force-sells → price falls further → next tier liquidates. A heavily levered market can drop **20–30% in minutes** on pure forced unwinds, then stabilise once leverage is flushed.
- **The reflexive triangle:** **Open interest** = the fuel (how much leverage exists). **Funding** = which side it's on. **Liquidations** = the reset. High OI doesn't cause a cascade — it's the fuel a cascade needs, which is why the *same* percentage move produces wildly different outcomes at different OI levels.
- **Critical, and directly usable:** in the big 2026 events, *leverage build-up was visible beforehand* in OI and funding data. **The trigger is unpredictable; the fragility is not.** You can measure how loaded the market is before the match is lit.
- **On-chain is a genuine early-warning channel** — large BTC/stablecoin transfers *to* exchanges, especially into thin weekend liquidity, precede aggressive selling/buying.

**What this means for us:** this is the most exploitable section in the whole document for our situation. **Fragility is measurable in advance from data we already collect** (OI + funding + positioning). It doesn't require predicting news. It pairs perfectly with convex structures — you don't need to know *when*, you position for *how violently* it resolves.

---

## 11. Cross-cutting conclusions (the honest summary)

1. **Costs decide everything.** The 164× OFI result and the ~58% publication decay both say the same thing: gross edge is easy, net edge is rare. Every candidate must be evaluated **after costs from day one**, never as an afterthought.
2. **Mechanical > predictive.** Funding/basis, liquidation fragility, and VRP have *explainable mechanisms* (someone is structurally forced to pay). Predictive signals decay; mechanical ones persist while the structure persists. Dev's own testing already found exactly this — only carry survived.
3. **Horizon is part of the signal.** Momentum vs reversal flips sign by horizon. A signal without a stated horizon is meaningless.
4. **Everything is regime-conditional.** OFI, factor loadings, correlations, VRP — all shift by regime. Confirms `newsystem.md` §11.5 from an independent direction.
5. **Liquidity is a feature, not a constant.** Weekend/session/time-zone effects change impact by 4–5×. Our system must know *when* it is, not just *what* it is.
6. **We have a mid-price problem.** Book-derived features (microprice, imbalance, OFI) are the right primitives, and `hl.db::book_snapshots` — the table designed to hold them — is **empty**.
7. **Perps lead spot.** Our venue/lead-lag work should treat perp flow as the source, not spot.
8. **We have no options data.** Dealer gamma/vanna/charm is a documented, real driver of spot behaviour and we collect only a single vol index.

---

## 12. What I could NOT verify

- **Exact current funding-formula parameters per venue** — they differ (interval, clamp, index construction) and change. Must be read from each venue's live docs, not assumed.
- **Whether perps still lead spot on Hyperliquid specifically** — actively contested in the literature; needs our own lead-lag measurement on our own data.
- **Current capacity/decay for any specific factor** — publication-decay numbers are averages, not per-factor guarantees.
- **Whether the weekend effect still holds at 2026 liquidity levels for the coins we trade** — the cited numbers are BTC-wide; must be re-measured on our own venues.

---

## Sources

- Microstructure & order books: [Market microstructure survey](https://www.acsu.buffalo.edu/~keechung/MGF743/Readings/Market%20microstructure%20A%20surveyq.pdf) · [Order flow and price formation](https://arxiv.org/pdf/2105.00521) · [Microstructure for intraday trading control](https://arxiv.org/pdf/1302.4592)
- Impact: [Square-root law of market impact (Bouchaud)](https://bouchaud.substack.com/p/the-square-root-law-of-market-impact) · [Impact conditional on order-flow imbalance](https://arxiv.org/pdf/2004.08290) · [Square-root impact, imbalance & volatility](https://arxiv.org/html/2506.07711v1)
- OFI: [Cross-impact of OFI in equity markets](https://www.tandfonline.com/doi/full/10.1080/14697688.2023.2236159) · [Predictive OFI cross-asset alpha](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7053198) · [Explainable patterns in crypto microstructure](https://arxiv.org/html/2602.00776v1)
- Volatility: [Term structure of equity & variance risk premia](https://farfe.org/2015ConferencePapers/TheTermStructureofEquityandVarianceRiskPremia.pdf) · [Harvesting the volatility risk premium](https://www.imperial.ac.uk/media/imperial-college/faculty-of-natural-sciences/department-of-mathematics/math-finance/Shibo_Lu_01210524.pdf) · [Detecting regimes in the vol surface](https://harbourfrontquant.substack.com/p/detecting-regimes-in-the-volatility)
- Momentum/reversal: [Understanding momentum and reversal](https://www.sciencedirect.com/science/article/abs/pii/S0304405X21000878) · [Momentum & mean reversion across national equity markets](https://www.sciencedirect.com/science/article/abs/pii/S0927539805000708) · [Momentum and reversal (Conrad & Yavuz)](https://web.ics.purdue.edu/~myavuz/conrad_yavuz_RoF_2016.pdf)
- Factors & decay: [Does academic research destroy stock return predictability? (McLean & Pontiff)](https://www.fmg.ac.uk/sites/default/files/2020-08/Jeffrey-Pontiff.pdf) · [Not all factors crowd equally](https://arxiv.org/pdf/2512.11913) · [Navigating the factor zoo](https://pmc.ncbi.nlm.nih.gov/articles/PMC8074275/)
- Market making: [Avellaneda & Stoikov — HFT in a limit order book](https://people.orie.cornell.edu/sfs33/LimitOrderBook.pdf) · [Funding-aware optimal market making for perpetual DEXs](https://arxiv.org/pdf/2605.06405)
- Derivatives feedback: [Gamma exposure (GEX)](https://spotgamma.com/gamma-exposure-gex/) · [Vanna and charm explained](https://spotgamma.com/vanna-and-charm-explained/) · [Dealer hedging mechanics](https://menthorq.com/guide/dealer-hedging-mechanics/)
- Crypto: [Designing funding rates for perpetual futures](https://arxiv.org/pdf/2506.08573) · [Price discovery in cryptocurrency markets](https://arxiv.org/abs/2506.08718) · [Perps now lead crypto price discovery](https://www.coindesk.com/markets/2026/07/30/bitcoin-and-ether-markets-are-ruled-by-perps-spacex-showed-how-far-their-influence-can-go) · [BTC futures microstructure: cascades, funding regimes, OI](https://medium.com/@XT_com/bitcoin-futures-market-microstructure-liquidation-cascades-funding-regimes-and-open-interest-978b107b4889) · [The bitcoin weekend liquidity gap](https://blockearner.com.au/blog/the-bitcoin-liquidity-gap-why-the-24-7-crypto-market-gets-volatile-when-wall-street-logs-off/)
- Efficiency: [Limits to arbitrage — survey](https://www.researchgate.net/publication/333670504_LIMITS_TO_ARBITRAGE_A_SURVEY_OF_LITERATURE) · [Limits of arbitrage (Herschberg)](https://www.palermo.edu/economicas/PDF_2012/PBR7/PBR_01MiguelHerschberg.pdf)
