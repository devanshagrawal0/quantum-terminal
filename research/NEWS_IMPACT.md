# NEWS_IMPACT.md — What news actually moves crypto, how much, how fast, how long

Scope: built for an automated bot on **Hyperliquid perps**, holding **1–7 days**, long or short,
hourly funding, ~230 listed perps from BTC/ETH down to memecoins.
Written 2026-08-23.

## How to read the evidence tags

Every claim below carries one of three tags. Do not mix them up.

- **[M] Measured** — a number from a published study or a dataset-wide count. URL given. Still may not
  replicate on your universe/period.
- **[T] Trader-believed** — widely held in practitioner/desk writing, plausibly true, **not** cleanly measured.
  Treat as a hypothesis to test, not a parameter to hardcode.
- **[I] Inference** — my reasoning from the above plus market structure. Lowest confidence. Never trade it
  before your own measurement confirms it.

**Blanket caveat:** almost all crypto event studies suffer from short samples, regime change (pre-ETF vs
post-ETF, pre-2022 vs post-2022), survivorship in coin universes, and event-date ambiguity. Effect sizes
below are **orders of magnitude, not parameters**. Any number you copy into a bot without re-measuring on
your own recorded data is a bug.

---

# 1. EVENT TAXONOMY

Format per event: direction · magnitude · time-to-peak · persistence · mean-reverting? · most-affected tier.

## 1.1 Macro

### FOMC decision / statement / dot plot
- **Direction:** conditional on *surprise*, not on the level. Hawkish surprise → negative. **[M]**
- **Magnitude:** an unexpected tightening of **1bp in the 2-year Treasury yield ≈ −0.25% Bitcoin**
  (Finance Research Letters, "Do FOMC and macroeconomic announcements affect Bitcoin prices?").
  A typical 5–10bp 2y surprise therefore maps to roughly **−1% to −2.5% BTC**. **[M]**
  https://www.sciencedirect.com/science/article/abs/pii/S154461231930159X
- **Volatility, not drift, is the reliable part:** BTC mean absolute *hourly* return rises from **0.66%**
  in the pre-announcement hour to **1.25%** in the announcement hour (+0.59pp). **[M]**
  https://www.sciencedirect.com/science/article/abs/pii/S1544612326006021
- **Time to peak:** minutes. Level adjustment is essentially complete within the announcement hour;
  elevated vol persists ~1 hour. **[M]**
- **Persistence at 1–7 days:** weak and contested. Several studies find the *level* effect of FOMC on BTC
  statistically negligible once surprise is not controlled for. **[M]**
- **Sell-the-news:** BTC fell after Fed announcements in most of 2025 — reported as rallying after only
  **1 of 8** 2025 FOMC meetings. Practitioner tally, not a peer-reviewed study. **[T]**
  https://www.coingecko.com/learn/fomc-meetings-impact-on-crypto
- **Tier:** BTC/ETH lead; alts inherit via beta with amplification (see §3).
- **Bot verdict [I]:** the directional edge in the first hour is gone before you can act. The tradeable
  residue is (a) **vol regime** — do not hold small-cap perps into FOMC hour, and (b) the 1–3 day
  **de-risking drift** after a hawkish surprise, which is a beta trade, not a news trade.

### CPI / PCE / NFP
- **Direction:** hot inflation → risk-off; cool → risk-on. Conditional on surprise vs consensus. **[M/T]**
- **Magnitude on levels:** older evidence finds CPI/PPI effects on BTC **statistically insignificant** on
  price levels. **[M]** (same FRL paper above). **Volatility** does react around release, including in the
  *pre*-announcement window. **[M]**
  https://www.sciencedirect.com/science/article/pii/S1059056025006720
- **Time to peak:** seconds to minutes. **Persistence:** typically < 1 day. Frequently fully reversed
  within the session. **[T]**
- **Tier:** BTC/ETH first, alts follow with lag of seconds and larger amplitude.
- **Bot verdict [I]:** untradeable as a directional 1–7 day signal. Use only as a **risk gate** (flatten or
  halve size across the book in the ±30 min window).

### DXY / real yields / equity risk-off days
- **Direction:** dollar up + real yields up → crypto down. **[T]**, with **[M]** support only indirectly via
  the 2y-yield channel above.
- **Magnitude/persistence:** this is a *slow-moving regime variable*, not an event. It matters over
  weeks. The 1–7 day version of it is just "crypto beta to risk assets."
- **Bot verdict [I]:** best used as a **regime filter that scales gross exposure and long/short skew**,
  not as an entry trigger.

## 1.2 Regulation

### SEC enforcement / lawsuit / "is a security" classification
- **Direction:** negative for the named token and its sector. **[M]**
- **Magnitude:** the peer-reviewed study reports statistically significant negative abnormal returns and a
  sharp contraction in trading volume; it does not publish a single headline % that generalises. **[M]**
  https://www.sciencedirect.com/science/article/abs/pii/S1544612324014429
- **Persistence:** unusually long for crypto. **More volatile / smaller assets keep declining and the
  effect intensifies over the following month.** Large-cap, older, more liquid, lower-vol assets absorb it
  far better. **[M]** — this is one of the few documented *multi-week drifts* in crypto.
- **Mean-reverts:** only on legal resolution (see below), not spontaneously.
- **Tier most affected:** **mid and small caps.** Large caps mitigate the effect. **[M]**

### Regulatory *resolution* (favourable ruling, dropped case, approval)
- **Direction:** strongly positive, and it is a **repricing of a removed tail risk**, so it tends to hold
  better than sentiment pumps. XRP moved above $3.30 on settlement with volume and institutional interest
  spiking. **[T/M-ish]** (press reporting, not an event study).
  https://capital.com/en-int/analysis/ripple-sec-suit-decision-timing-xrp-details
- **Time to peak:** minutes to hours; **persistence:** days.
- **Bot verdict [I]:** the *long* side of a legal resolution is the better half of this trade family,
  because the pre-event distribution was skewed by an overhang that just vanished. But headlines here are
  routinely misread by scrapers (partial rulings, appeals) — see §7.

### MiCA / non-US rules / sanctions / tax changes
- **Evidence: thin.** No good event-study effect size found in the time available. **[I]**
- **Structural mechanics matter more than sentiment:** an EU delisting requirement or an exchange
  geo-restriction is a *forced-seller / liquidity-removal* event and behaves like a delisting (§1.4).
- **Sanctions** on a mixer/entity: sharp negative for directly linked tokens, near-zero for the market. **[I]**

## 1.3 ETF and institutional

### Spot BTC ETF daily flows
- **Magnitude:** **$100M net flow ≈ +53bp same-day BTC return**, and about **96bp cumulative over 10
  trading days**. Flows explain **~21% of daily return variation** and **predict next-day returns**;
  Granger causality is **bidirectional** (returns also cause flows). **[M]**
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6592830
- **This is the single best-documented multi-day drift in this whole document.** ~53bp on day 0 growing to
  ~96bp by day 10 means roughly **45% of the total move arrives after day 0** — that is real, exploitable
  drift at your horizon.
- **Fatal timing caveat [I]:** flow data is published **after** the US close (Farside/issuer reporting),
  so "same-day return" is not something you could have traded. Your usable version is: *yesterday's
  published flow → today/next-3-days return*. That is the ~next-day predictive component, which is a
  fraction of the 53bp. Measure it yourself before sizing.
- **Mechanical caveat [M]:** authorised participants can meet demand without immediately buying spot, so
  a reported inflow is not a same-day exchange buy.
- **Tier:** BTC first, ETH via its own ETFs, alts only through beta.

### Corporate treasury buys / custody news
- **Direction:** positive; magnitude has decayed hard with repetition. Tesla's $1.5B disclosure in Feb 2021
  moved BTC **>15% in a session**; equivalent announcements in 2025–26 move it low single digits or less. **[T]**
- **[I] Rule:** the *n*-th instance of a narrative is worth roughly 1/*n* of the first. Novelty decay is a
  first-class feature, not a nuisance (§6).

## 1.4 Exchange events

### New listings (the biggest small-cap event in crypto)
- **Aggregate:** across **389 tokens listed in 2024 on 6 major CEXs**: average **+54% at launch**, then
  **89% dump post-listing with average −52%**; Binance-listed tokens **−70% from listing price**; only
  **5.5%** positive six months later; cumulative **−31.2% vs market**. **[M-ish]** (industry study,
  summarised here): https://bitpinas.com/cryptocurrency/binance-token-listing-dump/
- **Academic event study:** CAAR peaks at **+14.7% on the event day**, decaying to **+12.8%** over the
  (−7,+7) window. **The largest share of CAAR is built up *before* the event; post-event returns are
  negative.** CAARs are already +0.2% to +2.4% in the week before. **[M]**
  https://www.blockchainresearchlab.org/wp-content/uploads/2019/10/Exploring-Market-Reactions-to-Exchange-Listings-of-Cryptocurrencies-BRL-working-paper3.pdf
- **Coinbase effect:** average **+91%** but distribution **−32% to +645%** — the mean is not the trade. **[M-ish]**
  https://finance.yahoo.com/news/coinbase-effect-means-average-91-161123386.html
- **Korean (Upbit/Bithumb):** still the sharpest one. Examples: CFG **+177%**, ESP **+103%**. Effect
  typically **wears off in days to weeks** as volume reverts. **[T]**
  https://thedefiant.io/news/markets/korean-cex-listings-continue-to-boost-altcoins
- **Insider front-running is documented, not alleged folklore:** wallets front-ran the Nov 2024 Binance
  memecoin listings for **>$100M**; most of PNUT's move happened *before* the announcement. **[T]**
  https://www.ccn.com/analysis/crypto/binances-meme-coin-listing-insider-trading/
- **Bot verdict [I]:** **the long side of listings is unreachable for you.** The pump is pre-announcement
  and first-minutes, and on Hyperliquid the perp often does not exist until after. **The tradeable side is
  short, on a 1–7 day horizon, into the documented post-listing decay** — with the caveats that (a) borrow
  is not the constraint on perps but **funding is** (post-listing funding is often violently positive,
  which pays you to be short), and (b) squeeze risk is extreme in the first 24–48h. **Wait for the first
  lower high, not the first tick down.**

### Hyperliquid-specific listings
- HL perp listings themselves create a *new* venue for an existing token, which is a smaller version of the
  same effect plus a genuine structural change: leverage becomes available where it wasn't. **[I]**
- **[I] Hypothesis worth testing on your own data:** new HL perps show elevated realised vol and
  persistently skewed funding for their first ~1–2 weeks; the funding skew is a better signal than the
  listing itself.

### Delistings
- **Direction:** sharply negative, mechanically (liquidity removal + forced exit). **[T]**
- **Persistence:** does not mean-revert; it is a permanent liquidity downgrade. **[I]**
- **Trap:** on a perp, a spot delisting can *raise* perp/spot basis noise and make the mark unreliable. **[I]**

### Exchange hack / insolvency rumour
- **Direction:** negative, market-wide when the venue is systemic. FTX was the reference; the Oct 2025
  cascade was ~**16× larger in liquidations** than FTX. **[M-ish]**
- **Tier:** everything, correlation → 1 (§3).

## 1.5 Protocol / security

### Hacks and exploits
- **Direction:** violently negative for the protocol token; roughly neutral for the market unless systemic.
- **Magnitude and persistence — this is a *permanent* repricing, not a dip:** STEP **−99.4%** (left
  insolvent), DRIFT **−80.2%** since its exploit, RESOLV **−71.7%**; Aave TVL fell **−44.5%** over three
  months post-incident. **[M-ish]** (dataset-level reporting, not peer-reviewed)
  https://www.chainalysis.com/blog/lessons-from-the-resolv-hack/
- **Time to peak:** minutes to hours for the first leg; **a second leg often lands over days** as the size
  of the hole and the solvency question get resolved and as TVL bleeds.
- **Mean-reverts:** **no**, when funds are unrecovered or the protocol is insolvent. Partially, when the
  exploit is refunded/whitehat.
- **Tier:** small and mid caps almost exclusively.
- **Bot verdict [I]:** the best *short* in crypto news, and one of very few with genuine multi-day drift,
  because (a) the news is unambiguous, (b) the repricing is fundamental not sentimental, and (c) the
  ambiguity about final losses resolves slowly. **Key discriminator to encode: is the token's own
  treasury/solvency impaired, or was it a third party?** Only the former drifts.

### Depegs
- USDC fell **−12% to $0.8789 within hours** on the SVB disclosure; contagion propagated to DAI and FRAX
  through collateral links, with rotation into USDT. **[M]** https://arxiv.org/abs/2606.07442
- **Persistence:** hours to days when the backing is real; permanent when it isn't (UST).
- **Bot verdict [I]:** the *contagion* leg — shorting collateral-linked tokens and long-vol on the majors —
  is the tradeable part, and it lasts long enough (hours to a couple of days) for a bot to act.

### Chain halts / critical bugs
- Negative, sized to the chain's economic importance; typically recovers within days if the chain restarts
  cleanly. **[T]**

## 1.6 Tokenomics

### Unlocks / vesting cliffs
- **Direction:** negative. **90% of >16,000 unlock events had negative price impact within a 30-day
  window** (Keyrock). A separate study of **52 large Binance-listed unlocks (2023–2025) found 46/52
  (88.5%) negative within 72 hours.** **[M-ish / M]**
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6632838
- **Threshold effect:** unlocks adding **<1% of circulating supply show no meaningful relationship**;
  **>1%** shows noticeable negative impact; pressure amplifies when the unlock exceeds ~**2.4× average
  daily volume**. **[M-ish]**
- **Time profile:** **price pressure begins roughly 30 days before the unlock** — anticipation and
  front-running. **[M-ish]**
- **Mean-reverts:** frequently, *after* the event — the classic "sell the rumour, the unlock itself is the
  bottom" pattern. Not universally.
- **Tier:** mid and small caps. Large caps have no meaningful cliffs left.
- **Bot verdict [I]:** the highest-quality *scheduled* short in your universe, because the date is known in
  advance (tokenomist.ai, TokenUnlocks), the sign is stable, and the pressure window (T−30 to T−1) is
  exactly your holding period. **This is the best fit to a 1–7 day bot in this entire document.** But:
  the anticipation is public, so measure whether the edge still exists on *your* period, and beware the
  post-unlock bounce — **be flat or long by T+1, not short.**

### Buybacks / burns / emissions cuts
- Positive, small, and heavily anticipated. Halving-type events are pre-priced. **[T]**
- **[I]** Treat announced-but-not-yet-executed buybacks as sentiment; treat on-chain-verifiable
  buy pressure as flow.

### Foundation / treasury selling
- Negative, and it behaves like a slow unlock. On-chain detectable. **[I]**

## 1.7 Narrative / social

### Influencer / celebrity / political posts
- **Musk study, 47 crypto-related Twitter events:** ~**+3% jump** on dissemination, price continues rising
  for **about an hour**, then declines. Individual events reached **CAR +7.10% and +14.48% at 10 minutes**,
  and one reached **+12.07% over 120 minutes**. Effects were **significant for DOGE but not BTC**, and
  **no lasting impact** — reversal is documented. **[M]**
  https://www.sciencedirect.com/science/article/abs/pii/S0040162522006333
- **Time to peak:** 10–120 minutes. **Persistence:** hours. **Mean-reverts:** yes, strongly.
- **Tier:** small caps / memecoins only.
- **Bot verdict [I]:** **the long side is pure latency and you lose it.** The *only* realistic version for
  you is the **fade**, 2–24h after the spike, on a token with no fundamental change — and even that is a
  1-day trade, not a 7-day one, and it is exactly where a squeeze kills you.

### Memecoin waves / sector rotations (AI, DePIN, RWA)
- These are **flows, not events**. They persist for weeks, which suits your horizon, but they are
  momentum/cross-sectional signals rather than news signals. **[I]**
- Liu & Tsyvinski: **time-series momentum at 1–4 week horizons is real** in crypto, and a market/size/
  momentum three-factor model prices the cross-section (1,827 coins, 2014–2020). Reported long/short
  momentum payoffs are large (weekly, formation 1–4 weeks) — **I would not trust the headline magnitude
  without replication**, but the *sign and horizon* line up with a 1–7 day bot. **[M, magnitude uncertain]**
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3914414
- **Attention** (Google search index) **predicts future crypto returns** in the same literature. **[M]**

## 1.8 Geopolitics

- **Wars / escalations:** immediate risk-off, usually **fully reversed within days** unless it changes
  the rate path. **[T]**
- **Tariffs — the counterexample, and it is the important one:** Trump's 100% China tariff threat on
  **2025-10-10** triggered the largest liquidation event in crypto history: **>$19B liquidated, 1.6M
  traders, BTC −14% (to ~$104.8k), ETH −12%, many small alts −40% to −70% intraday** with partial
  recovery. **[M-ish]** https://www.ccn.com/education/crypto/cryptos-19-billion-liquidation-explained-trump-china-tariff-leverage-crash/
- **What actually made that big was not the news — it was the positioning.** Record open interest plus
  crowded longs. **The news was the trigger; leverage was the mechanism.** **[M-ish/I]**
- **Elections / country adoption or ban:** long-horizon repricing, slow, and heavily anticipated. **[T]**

## 1.9 Crypto-idiosyncratic

### Liquidation cascades
- **Direction:** direction of the cascade, violently. **Time to peak:** minutes. **Persistence:** the
  overshoot mean-reverts within hours to ~2 days; the *deleveraging* (lower OI, normalised funding)
  persists for weeks. **[M-ish/T]**
- **Tier:** small caps take 3–5× the large-cap move (Oct 2025: BTC −14% vs alts −40/−70%).
- **Bot verdict [I]:** the **mean-reversion long after a cascade** is one of the few high-Sharpe multi-day
  trades available to a slow bot, precisely because the move is mechanical, not informational. Gate it on:
  OI collapsed, funding flipped negative, and the *news* trigger has not fundamentally changed.

### Funding-rate extremes
- Practitioner consensus: sustained funding **>0.1% per 8h** signals crowded longs and precedes snapbacks;
  **rising OI + rising funding = directional crowding; falling OI + extreme funding = trend losing
  participation.** **[T]** — widely believed, poorly measured publicly.
  https://web3.gate.com/en/crypto-wiki/article/how-do-futures-open-interest-funding-rates-and-liquidation-data-predict-crypto-price-movements-20251226
- **[I]** For you this is not a side-signal, it is a **P&L line item**: at 0.1%/8h you pay ~0.3%/day,
  ~2.1% over 7 days. A 7-day long into extreme positive funding needs >2% of drift just to break even.
  **Funding is simultaneously your cost and your best crowding sensor.**

### Whale transfers / exchange inflows
- **[T]** Large transfers *to* exchanges are read as sell intent. Evidence quality is poor; attribution
  (which wallet is whose) is the hard part and is where most retail signals are wrong.
- **[I]** Treat as a weak feature at best; never as a standalone trigger.

### Stablecoin mint / burn
- **[T]** Net USDT/USDC supply growth is a slow liquidity proxy, weeks-scale. Not an event signal.

---

# 2. CAP-TIER DIFFERENCES

| | **Large (BTC, ETH)** | **Mid (top ~10–50 by liquidity)** | **Small / memecoin long tail** |
|---|---|---|---|
| Reaction size to same news | 1× | ~1.5–3× | ~3–10× |
| Speed to full repricing | seconds | seconds–minutes | minutes–hours (slowest, because attention arrives in waves) |
| Persistence of the move | shortest — arbitraged flat fast | medium | longest, but mostly because it *keeps decaying*, not because it drifts up |
| Reversal probability | high for macro noise | medium | **very high after pumps, very low after hacks/unlocks** |
| Idiosyncratic share of variance | low (it *is* the factor) | medium | high — but collapses to 0 in crashes |
| Liquidity constraint | negligible | moderate | **binding — this is where the edge dies** |

**[M] anchor for the amplification:** on 2025-10-10, BTC −14%, ETH −12%, small alts −40% to −70%. That is
a realised beta of roughly **3–5×** in the tail, versus a normal-regime beta closer to 1–1.5×.

**[M] anchor for tier-dependent persistence:** the SEC study explicitly finds that **larger market cap,
older age, lower volatility and higher liquidity mitigate the negative abnormal returns**, while more
volatile (i.e. smaller) assets see declines that **intensify over the following month**. Small caps
don't just move more; they *keep* moving.

## Where slippage eats the edge [I]

The honest test is: **expected edge (bps) vs round-trip cost (spread + impact + 7 days of funding).**

- **BTC/ETH perps:** cost is a few bps round trip. Almost any statistically real edge survives. But the
  edges here are the smallest and most competed.
- **Mid caps:** typically low-tens of bps round trip at modest size. A 1–3% expected move survives
  comfortably. **This tier is the sweet spot for a 1–7 day news bot.**
- **Small caps / memecoin perps:** book depth is thin and, critically, **it evaporates exactly when the
  news hits**. You will get filled at the worst point of the move. A 20% headline move can easily net you
  under half of that, and if you are wrong you exit into a vacuum. Add funding that can run several
  percent per week on a crowded small-cap perp.

**[I] Tradeability verdict on a 1–7 day horizon:**
- **Mid caps: yes** — biggest ratio of (signal amplitude) to (cost + crowding).
- **Large caps: yes, but only for the flow-driven events** (ETF flows, macro regime), where the drift is
  documented and costs are trivial.
- **Small caps: only for scheduled/structural events** (unlocks, post-listing decay, hacks) where the
  edge is large enough to pay the slippage. **Never for social/sentiment spikes** — there the edge is
  smaller than the cost and the latency gap is fatal.

---

# 3. BETA AND CONTAGION

**The default state:** alts are levered BTC. Most alt "news" is BTC news arriving second-hand. **[T/M]**

- **Normal regime:** BTC–alt correlations are high but not 1; idiosyncratic events (listings, unlocks,
  hacks) do produce genuine single-name moves.
- **Stress regime:** correlation goes to **~0.85–0.9 and near 1.0 on crash days** (e.g. FTX, 2022 bear).
  Everything is one trade. **[M-ish]**
  https://arxiv.org/pdf/2501.09911
- **The mechanism is not sentiment, it is collateral.** Cross-margined perp books force simultaneous
  liquidation across names. That is why correlation spikes *only* in the down tail and *only* when OI is
  high — **conditional, asymmetric, leverage-driven correlation**, not statistical correlation.
- **Contested:** one 2026 paper argues for a **post-ETF structural decoupling**, with BTC no longer acting
  as a systemic factor for altcoins. I would treat this as **not settled** — it is one paper against a lot
  of contrary tape. **[M, contested]**
  https://www.tandfonline.com/doi/full/10.1080/23322039.2026.2625541

**[I] Practical consequences for the bot:**
1. **Every alt position is implicitly a BTC position.** Compute rolling beta per symbol and report
   portfolio *net BTC-equivalent* exposure. Twenty independent "idiosyncratic" alt longs is one big
   levered BTC long.
2. **Hedge idiosyncratic news trades with the beta leg.** Short a hacked token, long a BTC-beta-matched
   amount, and you isolate the thing you actually have an edge on.
3. **"Alt season" is a *conditional* state,** not a calendar. Encode it as: BTC realised vol low/falling,
   BTC dominance falling, funding positive but not extreme, breadth expanding. Idiosyncratic news works in
   this regime and stops working in stress.
4. **In stress, cut gross, not net.** Diversification is fake precisely when you need it.

---

# 4. LONG VS SHORT PLAYBOOK

Structural asymmetries first:

- **Crypto falls faster than it rises.** Down moves are leverage-mediated and self-reinforcing; up moves
  are inventory-mediated and gradual. Practical result: **short trades reach target faster** (hours-days),
  **long trades need patience** (days-weeks). **[T, strongly supported by the Oct-2025 shape]**
- **Shorting into a squeeze is the dominant failure mode.** Small-cap perps with negative funding, low
  float and concentrated OI can run 50–100% against you before the thesis plays out. Cap leverage and
  always define invalidation in *price*, not conviction.
- **Funding is directional tax.** When everyone is on your side you pay; when you're contrarian you get
  paid. On a 7-day hold at 0.1%/8h you're paying ~2.1%. **Size holding-cost into expected value up front.**
- **"Sell the news" happens after *anticipated* events, not after *surprises*.** The mechanism: for a
  scheduled event, positioning is built in advance, so the event releases positioning rather than
  information. For a surprise, the event *is* the information, so price must move and keep moving.
  **[I, but this is the single most useful organising principle in the document.]**
  → **Encode `anticipated` vs `surprise` as a first-class field on every event.** Scheduled = fade;
  unscheduled = follow.

| Event class | Edge side | Entry timing vs headline | Hold (within 1–7d) | Invalidation | Typical failure mode |
|---|---|---|---|---|---|
| Hack/exploit, treasury impaired | **Short** | T+15min to T+2h (after first-panic overshoot; not at T+0) | 2–5 days | funds recovered / whitehat return / credible backstop | shorting the wick bottom, then a 30% relief bounce stops you |
| Hack, third-party only | **Fade the drop (long)** | T+2h to T+12h | 1–3 days | contagion proves real | mistaking a real solvency hole for an overreaction |
| Token unlock >1% supply | **Short** | T−7 to T−3 days | until T−1 | unlock cancelled/extended; token already down >30% into it | staying short through T+1 into the relief bounce |
| Post-CEX-listing decay | **Short** | T+24h to T+72h, after first lower high | 3–7 days | new high above listing-day high | day-1/2 squeeze; extreme negative funding costs |
| Listing *announcement* | **none for you** | — | — | — | chasing a move that was pre-traded by insiders |
| SEC enforcement on a name | **Short** | T+1h to T+1d | 3–7 days (this one genuinely drifts) | case dropped; large-cap absorbs it in a day | trading it on a large cap, where the effect is mitigated away |
| Regulatory resolution / approval | **Long** | T+0 to T+2h | 1–3 days | headline misread (partial ruling, appeal) | "approval" already leaked and fully priced |
| ETF flow extreme (published) | **Follow the flow** | next session open | 2–5 days | flow sign flips | trading it as if you had the same-day print |
| FOMC / CPI | **no directional edge** | — | — | — | thinking you can trade a 2-second repricing |
| Liquidation cascade | **Long the reversion** | T+2h to T+24h, once OI has reset | 1–3 days | OI rebuilds without price recovering; trigger was structural not technical | catching a falling knife mid-cascade |
| Depeg with collateral links | **Short linked tokens** | T+minutes to T+1h | hours–2 days | issuer proves backing | shorting the peg asset itself (bounded upside, unbounded squeeze) |
| Influencer/meme spike | **Fade (short)** | T+2h to T+24h | 1 day | a second, larger catalyst | squeeze; the "no fundamentals" token doubles again |
| Delisting | **Short** | T+0 to T+2h | 2–5 days | relisting / migration | thin book, terrible fills, perp mark divergence |
| Geopolitical shock | **no edge** | — | — | — | reversal within 48h |

**[I] The two asymmetries that matter most for your bot:**
1. **Structural shorts beat sentiment shorts.** Unlocks, post-listing decay, hacks and enforcement all
   involve a *real change in supply, liquidity or solvency*. Sentiment shorts (fading a meme pump) are
   coin-flips with a fat left tail.
2. **Your best longs are mean-reversion, not news-following.** Post-cascade reversion and
   overreaction-fades are where a slow participant is *structurally advantaged*, because the fast money is
   busy being the overreaction.

---

# 5. TIMING AND DECAY — where your edge actually is

**Brutal summary [I], grounded in the measurements above:**

| Window | What has already happened |
|---|---|
| **T−30d to T−1d** | For *scheduled* events, most of it. Unlock pressure starts **~30 days early [M]**. Listing CAAR is **mostly built before the event [M]**. Exchange listing insiders front-ran for **>$100M [T]**. |
| **T+0 to T+60s** | For *macro* and *surprise* headlines: essentially all of the level adjustment. Macro repricing completes **within minutes [M]**. |
| **T+1min to T+1h** | Where the remaining discovery happens for token-specific news. Musk-tweet CAR keeps building for **~10–120 min [M]**. Vol stays elevated ~1h post-FOMC **[M]**. |
| **T+1h to T+1d** | Where a slow bot lives. Second-order interpretation, TVL bleed, forced unwinds, retail arrival in small caps. |
| **T+1d to T+7d** | Genuine drift only for: **ETF flows [M]**, **SEC enforcement on small/mid caps [M]**, **unlock run-ups [M]**, **hacks with unresolved solvency [M-ish]**, **post-listing decay [M-ish]**. |

## What a bot acting 1–10 minutes late still has

**Dead — do not build these:**
- FOMC/CPI/NFP directional trades. Gone in seconds.
- Listing-announcement longs. Gone before the announcement.
- Influencer-pump longs. Gone in 10 minutes, and reversed by hour 2.
- Any "breaking news, buy immediately" strategy on large caps.

**Alive at 1–10 minutes late:**
- Hack shorts on small/mid caps — the informational content (how big is the hole?) is genuinely unresolved
  for hours, and the market underreacts to solvency impairment. **[I, supported by the persistence data]**
- Depeg contagion in *linked* assets — the second-order link takes time to be mapped.
- Cascade-reversion longs — by construction you *want* to be late.

**Alive at hours-to-days late (i.e. entirely scheduled, no latency race at all):**
- Unlock run-up shorts.
- Post-listing decay shorts.
- Post-enforcement drift shorts on small/mid caps.
- ETF-flow-following on BTC/ETH.

**[I] The strategic conclusion: stop competing on latency. Your entire edge should be in event classes
where the *information is public and slow*, not where it is fast.** Every event type in the "alive at
hours-to-days" bucket is a calendar/state trade, not a news-wire trade. That also removes your dependence
on a fast, reliable, low-false-positive news feed — which is the hardest part of this to build.

---

# 6. SIGNAL CONSTRUCTION

## 6.1 Event classification beats sentiment scoring

**[M] Why naive sentiment underperforms:** an LLM-based (ChatGPT) news-sentiment study found sentiment
indicators **significantly improve in-sample fit for returns and volatility but produce no statistically
significant out-of-sample forecasting gains** — the measures capture *contemporaneous* information, not
persistent predictive signal.
https://link.springer.com/article/10.1186/s40537-026-01392-x

Broader picture: ML on crypto returns gives mixed results; some papers find real out-of-sample value
(Filippou/Rapach/Thimsen), others find excess returns essentially unpredictable, with predictability
concentrated in *specific sentiment regimes* (greed vs fear) rather than uniform.

**[I] The design implication is sharp:** a scalar "positive/negative, −1..+1" is the wrong
representation. It throws away the only things that carry information — **what type of event, whose
balance sheet, how large, and was it scheduled**. Build a **typed event extractor**, not a sentiment
score:

```
Event {
  type:            enum  (hack | unlock | listing | delisting | enforcement |
                          resolution | etf_flow | macro | partnership | depeg | ...)
  entities:        [ {symbol, role: primary|counterparty|sector} ]
  magnitude:       numeric, in the units of the event type
                   ($ stolen / % of supply unlocked / $ flow / bp of surprise)
  scheduled:       bool          # THE key field — drives fade vs follow
  novelty:         0..1          # first report vs Nth restatement
  source_tier:     0..1
  resolution_state: rumour | confirmed_by_party | confirmed_on_chain
}
```

**Magnitude must be normalised by the token, not absolute.** $10M stolen is fatal to a $30M-FDV protocol
and noise to Aave. Use `$ stolen / market cap`, `unlock / circulating supply` (**[M]** threshold: 1%), and
`unlock / ADV` (**[M]** threshold: ~2.4×).

## 6.2 Novelty / surprise vs already-priced

- Deduplicate aggressively: cluster headlines by (entity, event type, 24h window) and only the **first**
  member of a cluster is an event; the rest are **coverage volume**, which is a separate feature.
- **Surprise = realised − expected.** For macro, that's the actual consensus print. For unlocks and
  listings, the *expected* component is the scheduled part. For everything else, the cheap proxy is
  **pre-event price/funding drift**: if the token is already down 25% into an unlock, the unlock is priced.
- **[I] Build an explicit `priced_in` score** = |cumulative abnormal return over T−7..T−1| normalised by
  realised vol. High score → expect fade, not follow. This one feature will kill more bad trades than any
  sentiment model.

## 6.3 Source credibility and coverage volume

- **Tier sources:** on-chain/primary (protocol multisig tx, exchange API listing endpoint, SEC EDGAR/press
  release, issuer flow files) >> established wire (Bloomberg/Reuters/CoinDesk/The Block) >> aggregator >>
  crypto Twitter/anon accounts.
- **[I] Never trade tier-3 alone.** Require either (a) a tier-1 confirmation or (b) corroborating *market*
  evidence (see next section). This is your only defence against hoaxes (§7).
- **Coverage volume is a genuine feature, distinct from sentiment:** article count and unique-source count
  in a rolling window proxy **attention**, and attention (Google-trends style) **predicts crypto returns
  [M]** in the Liu–Tsyvinski literature.

## 6.4 Entity resolution — the boring part that decides whether this works

**[I]** In practice this is where most retail news bots actually fail, before any modelling question.
- Ticker collisions are everywhere (a headline about "ARB" the token vs arbitrage; "Solana ecosystem" is
  not SOL). Resolve to a **canonical asset ID**, then map ID → Hyperliquid perp symbol, and **hold a
  hand-checked mapping table** — do not regex tickers out of text.
- Distinguish **primary** entity (the thing that got hacked) from **counterparty** (the exchange it was
  hosted on) from **sector** (other lending protocols). They have different signs and magnitudes.
- If entity resolution confidence < threshold, **drop the event**. A misrouted trade is worse than a
  missed one.

## 6.5 Combining news with the market variables you already have

**[I] The single most valuable idea in this section: news should almost never fire a trade alone. Use it
as a *conditioner* on your existing market-state features.**

| Market variable | Role in the combination |
|---|---|
| **Funding rate** | Crowding + your cost. Short signals are best when funding is *positive* (you get paid). A short into deeply negative funding is a squeeze setup — veto or halve. |
| **Open interest** | OI rising with price = leverage-driven, fragile, fades well. OI collapsing = cascade exhausted, reversion long. |
| **Perp–spot basis** | Divergence flags perp-only positioning (crowded speculation) vs real spot demand. Real spot demand persists; perp-only doesn't. |
| **Order-book imbalance / depth** | **Use it as a tradeability gate, not a signal.** If top-of-book depth can't absorb your size at <X bps, skip the trade regardless of signal strength. This is how you stop small-cap slippage from eating the edge. |
| **Realised vol** | Position sizing (vol targeting) and stop distance. Never use fixed % stops across 230 symbols of wildly different vol. |
| **Beta to BTC** | Decompose expected move into systematic + idiosyncratic; hedge the systematic part on single-name news trades. |

**[I] Concrete gating structure:**
`trade = event_signal × priced_in_discount × liquidity_gate × funding_sanity × regime_filter`,
where any one of the last four can zero it. Most of your improvement will come from the **vetoes**, not
from a better alpha model.

---

# 7. FALSE POSITIVES AND TRAPS

1. **Hoaxes and fakes.** Fake ETF-approval and fake partnership headlines have repeatedly moved markets.
   Defence: require tier-1 or on-chain confirmation for any *positive* surprise; hoaxes skew positive
   because pumps are the profitable direction for the hoaxer. **[I]**
2. **Recycled and restated news.** Aggregators republish; "X announces Y" reappears at each of
   announcement / launch / integration. Defence: entity+type+window dedup, and a `novelty` decay term.
3. **Paid pumps and coordinated shilling.** Small-cap "news" is often bought. Defence: source tiering plus
   a check that *coverage came from unrelated sources*, not one syndicate.
4. **Headline ambiguity and negation.** "SEC delays decision", "court partially grants", "exchange
   *considering* delisting", "hacker returns funds". Sign errors here are catastrophic because you size up
   on a strong-looking signal. Defence: classify `resolution_state` explicitly; drop ambiguous states.
5. **Thin-liquidity gaps.** The 40–70% small-cap moves in the Oct-2025 cascade **[M-ish]** are what your
   fills look like in stress. Backtests that assume mid-price fills on small caps are fiction.
6. **The "priced in" problem.** Documented at the data level: listing CAAR is **built before the event**
   and post-event returns are **negative [M]**; unlock pressure starts **~30d early [M]**. If you don't
   model anticipation you will systematically enter at the exhaustion point.
7. **Look-ahead bias from timestamps** — the biggest backtest killer here. News archive timestamps are
   typically *publication* or *last-modified*, not the moment your feed would have received it. Defence:
   **only backtest on news you recorded yourself, with your own receipt timestamp.** Until you have 6+
   months of that, everything is a hypothesis.
8. **Survivorship in news archives and coin universes.** Delisted/dead tokens vanish from both. This
   biases *long* news strategies upward (the disasters are missing) and *short* strategies downward.
   Since your best edges are short, this bias is working against you — the real short edge is probably
   *larger* than a naive survivorship-biased backtest shows. **[I]**
9. **Overfitting.** With ~230 symbols × dozens of event types, you have thousands of implicit hypotheses.
   Any t-stat under ~3 on this many tests is noise. Pre-register hypotheses (§8), don't mine.
10. **Funding drag ignored.** A backtest that ignores hourly funding will show profitable crowded-side
    trades that lose money live.
11. **Perp mark vs index divergence.** On thin HL perps in fast moves, mark price can diverge; a backtest
    on index prices overstates achievable fills and understates liquidation risk.

---

# 8. WHAT TO MEASURE — hypotheses to test on your own recorded data

Set-up requirements first, because without them none of the tests are valid:
- Record **every** news item with **your receipt timestamp**, plus the full typed Event struct (§6.1).
- Record 1-minute bars, funding, OI, top-of-book depth, and your own realised fills per symbol.
- Define abnormal return as **AR = r_token − β_token · r_BTC** (rolling 30d β). Everything below is on AR,
  not raw return, or you're just measuring BTC.
- Standard event window: AR at **+5m, +1h, +4h, +1d, +2d, +3d, +7d**, and CAR over each. Always report the
  **median and the 25/75 percentiles**, not just the mean — the Coinbase-effect range of −32% to +645%
  **[M]** shows why means lie here.

**H1 — Unlock drift.** For unlocks >1% of circulating supply, mean CAR from T−7 to T−1 is negative, and
CAR from T+0 to T+3 is positive (relief bounce). *Measure:* split by unlock/ADV ratio (below/above 2.4×)
and by pre-event drawdown. *Kill criterion:* T−7→T−1 CAR not negative at t>3.

**H2 — Post-listing decay.** For new HL/CEX listings, CAR from T+1d to T+7d is negative. *Measure:*
condition on day-1 range and on day-1 funding. *Also record realised funding paid/received* — half this
trade's P&L is funding.

**H3 — Hack persistence and the solvency discriminator.** CAR at +7d after an exploit is significantly
more negative when the protocol's own treasury/backing is impaired than when a third party lost funds.
*Measure:* hand-label 30+ historical exploits on this one binary. If the split is real, it's your highest-
conviction short filter.

**H4 — Enforcement drift by cap tier.** After enforcement news, CAR at +7d is negative for small/mid caps
and ~0 for large caps. *Measure:* interact with market cap and 30d realised vol (the study's own
moderators).

**H5 — Cascade reversion.** After a >X% hourly market-wide drop with OI down >Y%, AR at +1d/+3d is
positive. *Measure:* sweep X, Y; require OI reset as the condition, not just price. *Kill criterion:*
positive only in one regime.

**H6 — Anticipated vs surprise (the master hypothesis).** For *scheduled* events, sign(CAR T+0→T+1d) is
opposite to sign(CAR T−7→T−1). For *unscheduled* events, they have the same sign (continuation).
*Measure:* pool all events, split on the `scheduled` flag. **If this holds on your data, it is worth more
than every individual event type below it.**

**H7 — Priced-in score.** Post-event CAR is monotonically decreasing in |pre-event CAR|/vol.
*Measure:* quintile-sort events on the priced_in score; look for monotonicity, not just top-vs-bottom.

**H8 — Latency decay curve.** For each event type, plot cumulative captured AR as a function of entry
delay: 0, 1, 5, 10, 30, 60 min, 4h, 1d. *This single chart tells you which event types to keep and which
to delete.* Do this before optimising anything else.

**H9 — Sentiment adds nothing beyond event type.** Fit two models — event-type+magnitude only, vs
+sentiment score — and compare **out-of-sample** (walk-forward, not in-sample R²). Expect the [M]
literature result: no OOS gain. If your sentiment feature "works" in-sample only, delete it.

**H10 — Coverage volume / attention.** Number of unique sources in the first hour predicts CAR at +1d.
*Measure:* control for event type so you're not just re-measuring "big events are big".

**H11 — Funding as a filter.** Short signals conditioned on funding > 0 outperform the same signals with
funding < 0, net of funding paid. *Measure:* report net-of-funding P&L only.

**H12 — Depth gate.** Realised slippage vs top-of-book depth at signal time, by symbol. Fit the curve,
then set a per-symbol max size such that expected slippage < 25% of expected edge. *This is the single
highest-ROI engineering task in the list — it converts "signal" into "P&L".*

**H13 — Beta contamination.** How much of your historical single-name news P&L is explained by BTC beta?
*Measure:* regress strategy returns on BTC returns. If R² is high, you don't have a news strategy, you
have a levered directional bet.

**H14 — ETF flow follow-through.** Using *publication* timestamps (not flow dates), does next-session BTC
return load on prior-day net flow? *Measure:* the [M] literature says ~53bp per $100M same-day and ~96bp
over 10 days; you must find out how much of that survives the publication lag.

**H15 — Correlation regime.** Rolling 30d BTC-alt correlation, conditioned on realised vol tercile. Verify
for yourself whether the "post-ETF decoupling" claim **[M, contested]** holds on your symbols — and use
the result to set gross-exposure caps in stress.

---

## Bottom line [I]

The evidence supports a narrow, unglamorous conclusion: **for a 1–7 day bot that acts minutes late, the
edge is not in reacting to news — it is in trading the slow, structural, scheduled consequences of news,
mostly from the short side, in mid-caps, gated hard by liquidity and funding.** Unlocks, post-listing
decay, hacks with unresolved solvency, and enforcement drift on small/mid caps are the four event classes
with both documented multi-day persistence and no latency race. Everything else in this document is
either already priced before you see it, reverted before your holding period ends, or too small to survive
your costs.
