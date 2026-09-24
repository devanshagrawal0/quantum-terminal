# Cross-Venue Features for a 1–7 Day Directional Hyperliquid Perp Book

**Scope.** ~177 coins × 26 venues × 5-minute bid/ask/mid/volume snapshots, plus hourly Binance
positioning (OI, long/short account ratio, top-trader position ratio, taker flow) and Hyperliquid
funding history. Target: directional long/short calls held 1–7 days, 5–10 new entries/day,
20–50 concurrent positions, ~9bps round-trip fees + 0.1–7.7bps slippage.

**Evidence tags used throughout:**
- `[MEASURED]` — a specific number or result from a study, with a URL.
- `[PRACTICE]` — what practitioners actually do; no clean published study.
- `[INFERENCE]` — my reasoning from the above plus the specifics of this panel.

**The single most important framing up front `[INFERENCE]`:** almost every published cross-venue
result in crypto is a *microstructure* result measured at seconds-to-minutes and monetised by
arbitrage or market-making. This bot holds 1–7 days. Therefore the cross-venue panel is **not**
useful here as a lead-lag alpha source. It is useful as a **state/conditioning and quality-of-price
instrument**: it tells you how stressed, how segmented, how concentrated and how liquid a coin's
market is right now, and those states plausibly persist for days. Design the feature set around
that, not around "which venue ticks first."

---

## 0. Panel geometry and what it can/cannot resolve

| Property | Value | Consequence |
|---|---|---|
| Sampling | 5 min | Nyquist limit ≈ 10 min. Anything documented at <5 min is invisible. `[INFERENCE]` |
| Bars/day | 288 | 288 × 177 coins × 26 venues ≈ 1.3M quote observations/day |
| Holding period | 1–7 days | 288–2016 bars per holding period |
| Effective independent obs | ~1 per coin per day | With 177 coins, ~177 cross-sectional obs/day. **This is your real sample size**, not 1.3M. `[INFERENCE]` |
| Data type | Quotes (bid/ask/mid) + volume | You have **no trade prints, no signed order flow, no depth beyond top-of-book**. This rules out true Kyle's lambda and true Amihud without proxies. `[INFERENCE]` |

A one-year history gives roughly 365 cross-sectional dates. A daily-rebalanced cross-sectional
signal tested on 365 dates has a standard error on its information coefficient of roughly
1/√365 ≈ 0.05 `[INFERENCE]`. **You cannot statistically distinguish an IC of 0.03 from zero on one
year of daily data.** Every design decision below follows from that constraint.

---

## 1. Per-venue features

Notation: for coin *i*, venue *v*, 5-minute bar *t*: bid `b`, ask `a`, mid `m = (b+a)/2`,
volume `V` (quote-currency notional preferred; if base units, convert with that venue's own mid).
Log return `r_{i,v,t} = ln(m_{i,v,t} / m_{i,v,t-1})`.

### 1.1 Returns / momentum

Compute per venue, then aggregate; but **compute the trading signal on a consolidated price**, not
a single venue (see §1.7).

```
r_h(i,v,t) = ln( m(i,v,t) / m(i,v,t-h) )        h ∈ {12, 288, 864, 2016}   # 1h, 1d, 3d, 7d
mom_skip(i)  = ln( m(i,t-288) / m(i,t-2016) )   # 7d→1d, skipping last day
rev_1d(i)    = -r_288(i)                         # short-horizon reversal
```

- **Skip-a-day construction is standard and matters.** Crypto cross-sectional momentum studies
  form deciles on past-7-day returns *skipping the most recent day* precisely to avoid the
  short-reversal contamination `[MEASURED]`
  (https://www.starkiller.capital/post/cross-sectional-momentum-in-cryptocurrency-markets).
- Coins that outperform over 30 days tend to continue outperforming over the following 7 days
  `[MEASURED]` (same source; also
  https://link.springer.com/article/10.1007/s11408-025-00474-9).
- At intraday/1-day horizons the sign flips toward **reversal** in crypto, attributed to
  overreaction to non-fundamental information `[MEASURED]`
  (https://www.sciencedirect.com/science/article/abs/pii/S1062940822000833). Whether momentum or
  reversal is the correct "third factor" for crypto is genuinely contested in the literature
  `[MEASURED]` (https://www.sciencedirect.com/science/article/abs/pii/S1544612321002208).
- **Practical implication `[INFERENCE]`:** at a 1–7 day hold you sit exactly on the crossover
  between the reversal regime (<1d) and the momentum regime (7–30d). Do not assume a sign.
  Fit the sign per horizon and let the 1d and 7d terms enter as *separate* features with
  independently estimated signs.

**What a per-venue return difference means.** If `r_1h(i, Binance) ≠ r_1h(i, MEXC)`, at 5-min
sampling that is almost never real information flow — it is one venue's quote being stale, or a
different quote currency (USDT vs USDC vs USD vs KRW vs INR), or a wide spread making the mid
noisy. Treat per-venue return *dispersion* as a data-quality and stress metric (§2.4), not as
directional signal.

### 1.2 Volatility

You have 5-min mids only, so you can build all four families from the 5-min mid series by
constructing synthetic OHLC bars (open/high/low/close of the 5-min mids within each hour or day).

```
# Realised (close-to-close), the workhorse
RV(i,v,T)   = sqrt( (288/n) * Σ_t r(i,v,t)^2 )          # annualise/dailyise as needed

# Parkinson — uses the high-low range, ~5x more efficient than close-to-close
PK(i,v,T)   = sqrt( (1/(4 ln2)) * ln(H/L)^2 )

# Garman-Klass — adds open/close, ~7-8x efficient
GK(i,v,T)   = sqrt( 0.5*ln(H/L)^2 - (2 ln2 - 1)*ln(C/O)^2 )

# Rogers-Satchell — GK's drift-robust cousin; use this if the coin trends hard
RS(i,v,T)   = sqrt( ln(H/C)ln(H/O) + ln(L/C)ln(L/O) )

# Bipower variation — jump-robust; RV - BPV isolates jump variation
BPV(i,v,T)  = (π/2) * Σ_t |r_t| * |r_{t-1}|
JumpFrac    = max(0, RV^2 - BPV) / RV^2
```

**Caveat on Parkinson/GK from 5-min mids `[INFERENCE]`:** the H and L of 288 5-min *mid* samples
systematically understate the true intraday high/low (you miss everything between samples) and
also inherit half the bid-ask spread as noise. The bias is a roughly stable multiplicative factor
per coin, so these estimators remain fine as *cross-sectional rankings* and as *time-series
changes*, but do not treat their level as a true vol estimate.

**What differing vol across venues means `[INFERENCE]`:**
- Higher measured vol on a thin venue (MEXC, BingX, Phemex) with the *same* price path = quote
  noise / wide spreads, not real vol. Spread-adjust before comparing:
  `RV_clean ≈ sqrt(max(0, RV² − 2·(spread/2)²·(1/Δt)))` (Roll-style spread-noise subtraction).
- Higher vol on a *deep* venue (Binance, Bybit) than on others = real information arriving
  there first. That is the interesting case.
- **Vol-of-vol across venues** (`std_v(RV(i,v))`) is a cleaner stress metric than any single-venue
  vol. When market-makers pull back, venue-level vol estimates fan out.

### 1.3 Liquidity

```
# Quoted spread (the only truly clean liquidity measure you have)
spr(i,v,t)      = (a - b) / m                       # in bps: *1e4
spr_eff(i,t)    = volume-weighted median over venues of spr(i,v,t)
spr_z(i,t)      = (spr(i,t) - mean_60d) / std_60d   # spread *widening*, not level

# Amihud illiquidity — |return| per unit dollar volume
ILLIQ(i,v,T)    = mean_t( |r(i,v,t)| / (V(i,v,t) + eps) )
# Use log(ILLIQ) always. Raw ILLIQ is violently right-skewed and one bad bar dominates.

# Kyle's lambda — you CANNOT compute the real one without signed order flow.
# Proxy A (return-volume regression, unsigned): regress |r| on sqrt(V) over a rolling window
#   |r_t| = λ_hat * sqrt(V_t) + e_t     -> λ_hat is a price-impact proxy
# Proxy B (cross-venue impact): regress the venue's return residual on its share of volume
#   (this is the closest thing to Makarov-Schoar's exchange-specific signed-volume regression)

# Roll effective spread from serial covariance (a sanity check on quoted spread)
Roll(i,v)       = 2 * sqrt( max(0, -Cov(r_t, r_{t-1})) )

# Corwin-Schultz high-low spread estimator — useful where quotes are suspect
```

- Amihud's illiquidity ratio is the canonical price-impact proxy and is a documented
  cross-sectional return predictor in equities (illiquid assets earn higher expected returns)
  `[MEASURED]` (https://www.cis.upenn.edu/~mkearns/finread/amihud.pdf). It has been applied to
  crypto with 30-minute rolling windows `[MEASURED]`
  (https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2026.1811716/full).
- Momentum and liquidity interact in the crypto cross-section `[MEASURED]`
  (https://arxiv.org/pdf/1904.00890).
- **Hard warning `[INFERENCE]`:** in *this specific system* Amihud has already been diagnosed as
  an outlier artifact in a prior study on this book (see the CrashGuard occurrence-bug finding —
  Amihud survived selection there only because a handful of extreme bars dominated it). If you
  recompute it: winsorise at 1%/99% *before* averaging, use the median not the mean over the
  window, and take logs. If the feature dies under those three changes, it was never real.
- **Kyle's lambda honesty `[INFERENCE]`:** without trade-level signed flow you are estimating
  |return|-per-√volume, which is a *volatility-to-volume* ratio, not a price-impact coefficient.
  Call it what it is (`impact_proxy`), do not call it lambda, and expect it to be ~80% collinear
  with `log(RV/√ADV)`.

**What differing liquidity across venues means `[INFERENCE]`:**
- A coin with tight spreads on Binance/Bybit but 50bps spreads on 20 other venues is a
  *concentrated-liquidity* coin: safe to trade at size on Hyperliquid if HL itself is deep, but
  fragile — one venue's outage moves everything.
- A coin whose spread has widened on *most* venues simultaneously over the past day is a genuine
  risk-off signal for that coin. Cross-venue **breadth of spread widening** (fraction of venues
  where spread_z > 1) is a much more robust feature than any single venue's spread.
- Hyperliquid's own spread relative to the cross-venue median tells you your **execution
  disadvantage**, which is directly tradeable information: skip signals where
  `spr_HL / median_v(spr) > 2`.

### 1.4 Volume / turnover

```
ADV(i,v)        = trailing 7d mean of daily quote volume on venue v
share(i,v,t)    = V(i,v,t) / Σ_v V(i,v,t)
turnover(i,t)   = Σ_v V(i,v,t) / marketcap_i        # if you have supply; else use ADV-relative
vol_surprise(i) = log( V_1d(i) / median(V_1d over 30d) )     # volume shock
amihud_adv(i)   = log(RV_1d / sqrt(ADV))
```

Volume shock is one of the few genuinely persistent, well-behaved short-horizon crypto features
`[PRACTICE]`. It is also a *conditioner*: a momentum signal on a coin with a 3× volume surge
behaves differently from the same signal on a dead coin.

**Cross-venue caution `[INFERENCE]`:** raw volume from MEXC, BingX, and several others is widely
believed to be inflated by wash trading and maker rebate farming. Never sum raw volume across
26 venues and call it "true volume." Either (a) use a trimmed sum that drops the top and bottom
venues, or (b) use **Binance + Bybit + OKX + Coinbase + Kraken volume only** as the "credible
volume" aggregate and treat the rest as a separate `fringe_volume_share` feature. That share
itself is informative: high fringe share = retail/degenerate coin.

### 1.5 Order flow

You do not have signed trades. What you *do* have:

1. **Binance hourly positioning** (OI, long/short account ratio, top-trader position ratio,
   taker buy/sell flow). This is the closest thing to real flow in the panel.
   ```
   oi_chg(i,h)      = ln(OI_t / OI_{t-24h})
   ls_ratio_z(i)    = z-score of long/short account ratio vs its own 30d history
   top_minus_retail = z(top_trader_ratio) - z(account_ratio)    # smart-vs-dumb spread
   taker_imbal(i)   = (takerBuy - takerSell) / (takerBuy + takerSell)
   ```
   `top_minus_retail` is the highest-conceptual-value feature in this group `[INFERENCE]`:
   Binance publishes both a *headcount* ratio (dominated by small accounts) and a *top-trader
   position* ratio. Their divergence is a crude but real proxy for informed-vs-uninformed
   positioning, and it is a positioning *state* that persists for days — the right timescale
   for this book. I know of no clean published study on it; it is `[PRACTICE]`.

2. **OI × price sign classification** `[PRACTICE]` — the standard practitioner 2×2:
   | | price up | price down |
   |---|---|---|
   | **OI up** | new longs (continuation) | new shorts (continuation) |
   | **OI down** | short covering (exhaustion) | long liquidation (exhaustion) |
   Encode as `oi_price_regime = sign(Δprice) * sign(ΔOI)`. No clean study; widely used.

3. **Cross-venue mid drift vs the consolidated mid** as a signed-flow proxy. Makarov & Schoar
   found that exchange-specific residuals of *signed volume* significantly explain
   exchange-specific residuals of returns at the 5-minute and hourly level `[MEASURED]`
   (https://personal.lse.ac.uk/makarov1/index_files/CryptocurrencyMarkets.pdf, JFE 2020). You
   don't have signed volume, but the return residual itself is the observable half of that
   relationship — see §2.2.

### 1.6 Funding (Hyperliquid, and inferred elsewhere)

```
fund_8h(i)       = HL funding rate
fund_carry_7d(i) = Σ funding over trailing 7d       # what a holder actually paid/earned
fund_z(i)        = z-score of funding vs own 60d history
fund_expected(i) = forward cost of the 1-7d hold at current funding  # in bps -> add to cost model
basis_implied(i) = (perp_mid - spot_mid) / spot_mid  # see §2.6
```

Perpetuals are ~93% of crypto futures volume `[MEASURED]`
(https://www.mdpi.com/2227-7390/14/2/346); the funding mechanism is the arbitrage tether between
perp and spot `[MEASURED]` (https://arxiv.org/pdf/2212.06888). Sustained extreme funding has
historically preceded some of the sharpest reversals in crypto derivatives `[PRACTICE]` — this is
widely asserted in industry writeups but I did not find a clean event-study with confidence
intervals.

**Critical for this bot `[INFERENCE]`:** funding is not just a signal, it is a *cost line*. At 1–7
day holds, funding at 0.01%/8h = 0.03%/day = 3bps/day = **21bps over a 7-day hold**, which is
larger than your entire 9bps round-trip fee. Funding must appear in the cost model before it
appears in the alpha model.

### 1.7 The consolidated reference price (build this first)

Before any of the above is trustworthy you need one number per coin per 5-min bar:

```
w(i,v,t) = credibility(v) * (1 / spr(i,v,t)) * sqrt(V(i,v,t)) * fresh(i,v,t)
CP(i,t)  = Σ_v w(i,v,t) * m(i,v,t) / Σ_v w(i,v,t)
```
where `fresh(i,v,t) = 1` if the venue's quote has changed within the last N bars, decaying to 0
otherwise (§6.1), and `credibility(v)` is a fixed per-venue prior. Weighting by inverse spread and
√volume concentrates the reference on venues where price discovery actually happens; price
discovery concentrates on the deepest, highest-volume venues because informed traders execute
there at lowest cost `[MEASURED]` (https://arxiv.org/abs/2506.08718).

**Every dispersion feature in §2 is defined relative to `CP`, not relative to Binance.** Anchoring
on one venue makes every feature a bet on that venue's data quality.

---

## 2. Cross-venue features

These are the features that exist *only* because 26 venues are sampled simultaneously.

### 2.1 Price dispersion

```
disp_std(i,t)   = std_v( ln(m(i,v,t) / CP(i,t)) )               # bps
disp_range(i,t) = max_v ln m  -  min_v ln m                      # the "arbitrage index"
disp_iqr(i,t)   = 75th - 25th pctile of ln(m/CP)                 # robust version, USE THIS ONE
disp_z(i,t)     = (disp_iqr - median_30d) / MAD_30d
```

`disp_range` is essentially Makarov & Schoar's *arbitrage index* — the max cross-exchange price
difference `[MEASURED]` (JFE 2020, link above). They find arbitrage opportunities open
recurrently and **persist for several hours, in some cases days and weeks** `[MEASURED]`. That
persistence is the entire reason this feature is usable at a 1–7 day horizon: a microstructure
quantity that persists for days is a *state variable*, not a fleeting print.

**Use `disp_iqr`, not `disp_range`.** The max/min are exactly the two venues most likely to be
stale or wrong `[INFERENCE]`. Range-based dispersion is a stale-quote detector wearing an alpha
costume.

**What it means when high:** capital cannot move freely between venues right now (funding rails
congested, withdrawals paused, stablecoin depeg, or simply nobody is arbitraging a thin alt).
Historically dispersions co-move across countries and **open up in times of large bitcoin
appreciation** `[MEASURED]` (JFE 2020) — so `disp` is partly a bull-stress proxy, and you must
control for market-wide dispersion before using coin-level dispersion cross-sectionally.

### 2.2 Persistently rich / cheap venues

```
prem(i,v,t)      = ln( m(i,v,t) / CP(i,t) )                      # signed, bps
prem_ma(i,v)     = 7-day EWMA of prem                            # the "structural" premium
prem_resid(i,v,t)= prem(i,v,t) - prem_ma(i,v)                    # the transient deviation
```

**This decomposition is the single most valuable idea in §2 `[INFERENCE]`.** A venue that is
*always* 20bps rich (Upbit in KRW, Coinbase in USD during US-inflow regimes, HTX on some alts) is
telling you about a persistent structural feature — quote currency, fee model, captive user base,
capital controls. That level is not a signal. The **deviation from a venue's own structural
premium** is.

Published support: Makarov & Schoar find that **when the price on any exchange deviates above
(below) the average price on other exchanges, subsequent returns on that exchange are predicted
to be lower (higher)** `[MEASURED]` (JFE 2020). That is mean-reversion of `prem_resid`, and it is
a *relative-venue* prediction, not a prediction about the coin. **It does not by itself tell you
whether the coin goes up.**

The tradeable inference for this book `[INFERENCE]`: if Hyperliquid specifically is rich relative
to `CP` at entry, your fill is worse than the cost model believes, and the subsequent
venue-convergence works against you. So `prem_HL` is best used as an **execution filter and a
cost adjustment**, not as alpha. Add `prem_HL` (signed by trade direction) directly to the
expected-cost term.

Second-order and genuinely interesting `[INFERENCE]`: **which venue leads the convergence.** If
`prem_resid` on the deep venues (Binance/Bybit/OKX) moves first and the thin venues follow, the
move is informed. If a thin venue is the outlier and it snaps back, it was noise. Compute
`lead_share(i,v) = corr(prem_resid(i,v,t), Δ CP(i,t+1))` over a long window — a stable per-venue
statistic, not a per-bar one.

### 2.3 Volume concentration (Herfindahl)

```
HHI(i,t)      = Σ_v share(i,v,t)^2                # share in *credible* volume only
n_eff(i,t)    = 1 / HHI(i,t)                      # effective number of venues
HHI_chg(i)    = HHI_1d - HHI_30d_median
top1_share(i) = max_v share(i,v)
hl_share(i)   = share of volume on Hyperliquid itself
```

- `n_eff` low (1–3) = a coin traded essentially on one venue. Fragile, prone to single-venue
  manipulation, wider realised slippage than the spread suggests `[INFERENCE]`.
- `HHI` **rising** = liquidity consolidating onto the leader, typically during stress as MMs pull
  from fringe venues `[INFERENCE]`. This makes `ΔHHI` a decent cheap volatility predictor.
- `hl_share` is directly operational: if Hyperliquid is 40% of a coin's volume, *you* are the
  market and your slippage estimate from a small-size probe is meaningless at real size.

I found **no published study** testing Herfindahl-across-venues as a return predictor in crypto.
Treat it as `[PRACTICE]`/`[INFERENCE]`, and expect it to be a *risk* feature (predicting vol and
slippage) rather than a *direction* feature.

### 2.4 Venue disagreement as a volatility predictor

```
disagree(i,t) = std_v( r_1h(i,v,t) )   over credible venues only, freshness-filtered
```

The claim: when venues' short-horizon returns disagree, market-making capital is thin and
realised volatility over the next days is higher. `[INFERENCE]` — I found no direct published test
of *cross-venue return dispersion → future realised vol* in crypto. What is published and adjacent:
deviations from parity are influenced by overall market volatility and arbitrage becomes riskier
in volatile periods `[MEASURED]` (JFE 2020 and follow-ups), i.e. the causal arrow documented in
the literature runs **volatility → dispersion**, not dispersion → volatility.

**Be honest about this.** Since vol is autocorrelated, dispersion will forecast vol simply by
being a contemporaneous vol proxy. To claim anything more you must show `disagree` adds R² *over*
lagged realised vol (Parkinson/GK) and over implied vol from Deribit. My prior is that it adds
little `[INFERENCE]`. Test it as: `RV_{t+1..t+3} ~ RV_t + GK_t + disagree_t`; look at the t-stat
on `disagree` only.

**The Deribit angle you are underusing `[INFERENCE]`:** you sample Deribit. If you can extract any
option-derived quantity (ATM IV, or even just the term structure of the perp/future basis), the
**IV − RV spread (variance risk premium)** is a far better-founded volatility and tail predictor
than venue disagreement, and it exists for BTC/ETH and a handful of alts. Prioritise that over
`disagree` if the data permits.

### 2.5 Regional premia — Korean (kimchi) and Indian

```
kimchi(t)      = ( P_Upbit_KRW / FX_USDKRW ) / CP_USD  - 1
kimchi_bithumb = same on Bithumb
india(t)       = ( P_CoinDCX_INR / FX_USDINR ) / CP_USD - 1
kimchi_z       = z-score vs 90d
kimchi_cross   = 1 if kimchi crosses 0 from below, else 0
kimchi_breadth = fraction of KRW-listed coins with positive premium
```

**What is measured:**
- Mean kimchi premium 3.41%, median 1.97% — Korean BTC is persistently and substantially above
  global `[MEASURED]` (https://www.sciencedirect.com/science/article/abs/pii/S1544612319301357).
- The premium is **positively associated with Korean trading volume** after controlling for
  volatility and liquidity, and both premium and volume rise with price volatility `[MEASURED]`
  (same paper). It is a *speculative-demand* thermometer.
- Cross-country deviations are far larger than within-country ones; capital controls are the
  binding constraint. Korea's regime (documentation for remittances >USD 50k, foreigners
  effectively excluded from domestic exchanges) is the mechanism `[MEASURED]`
  (https://personal.lse.ac.uk/makarov1/index_files/CryptocurrencyMarkets.pdf).
- Country premia **co-move and widen during large BTC appreciation** `[MEASURED]` (same).
- Lead-lag between the premium and BTC is **asymmetric and time-varying**; rolling-window Granger
  causality and transfer entropy show the direction of causality flips across regimes `[MEASURED]`
  (https://www.mdpi.com/2227-7390/14/9/1501). This is the most important honest finding: **there
  is no stable "kimchi leads BTC by X hours" relationship.**

**What is folklore:**
- "Kimchi premium front-runs BTC." One industry writeup reports zero-crossings (negative→positive)
  followed by +1.7% average 7-day and +6.2% average 30-day returns with 67%/70% win rates, while
  the *level* of the premium correlates ≈ **−0.06** with forward returns `[MEASURED, but low
  quality]` (https://cryptoslate.com/does-thes-kimchi-premium-still-front-run-btc/). No sample
  period, no standard errors, no multiple-testing correction, and the specific "zero-crossing"
  event definition smells strongly of a chosen threshold. Treat the −0.06 level-correlation as
  the credible number and the zero-crossing result as unverified `[INFERENCE]`.

**Indian premium: essentially undocumented `[INFERENCE]`.** CoinDCX/WazirX in INR carry a
structural premium driven by the 1% TDS on crypto transfers and INR on/off-ramp friction. That
tax is a *fixed structural wedge*, not a sentiment signal — it should show up almost entirely in
`prem_ma` (§2.2) and almost nothing should be left in the residual. Use it as an FX/segmentation
robustness check, not as alpha, until proven otherwise.

**Design guidance `[INFERENCE]`:** regional premia are **market-level** (one number per day),
not cross-sectional. With ~365 daily observations per year you have almost no statistical power
to validate them. Use them at most as a slow regime conditioner (e.g. scale gross exposure), or —
better — use `kimchi_breadth` across the ~50 KRW-listed coins, which *is* cross-sectional and
gives you 50× the observations.

### 2.6 Perp-to-perp basis

```
perp_basis(i, v1, v2) = ln( perp_mid(i,v1) / perp_mid(i,v2) )
hl_vs_binance(i)      = ln( m_HL(i) / m_BinancePerp(i) )
hl_basis_resid(i)     = hl_vs_binance - EWMA_7d(hl_vs_binance)
```

Perp prices across venues are anchored to each other by funding and by cross-venue arbitrageurs;
persistent divergence between two *perp* venues means the funding mechanism is not clearing
`[INFERENCE]`. In practice for this bot the relevant one is `hl_basis_resid`: Hyperliquid's perp
rich/cheap versus the CEX perp complex. High absolute values mean HL-specific positioning
pressure. `[PRACTICE]` — routinely watched by HL traders, no published study I could find.

### 2.7 Spot-vs-perp divergence

```
sp_basis(i)     = ln( CP_perp(i) / CP_spot(i) )          # both consolidated across venues
sp_basis_z(i)   = z vs own 60d
funding_gap(i)  = fund_HL(i) - implied_fund_from_basis(i)
```

Positive basis = leveraged longs crowded, pushing perp above spot; funding then makes longs pay
shorts, which pulls the perp back toward spot `[MEASURED]`
(https://arxiv.org/pdf/2212.06888, https://www.coinbase.com/institutional/research-insights/research/market-intelligence/a-primer-on-perpetual-futures).

**This is the crown jewel of your panel `[INFERENCE]`,** because you sample both perp venues
(Binance, Bybit, dYdX, Paradex, Backpack, HL...) and spot venues (Coinbase, Kraken, Upbit,
Bithumb) simultaneously for the same coins. Very few systems have a clean consolidated *spot* and
consolidated *perp* price for 177 coins at 5-min resolution. `sp_basis` is:
- **cross-sectional** (one value per coin → ~177 obs/day, enough statistical power),
- **persistent** at a days timescale (funding accrues 3×/day and only slowly corrects crowding),
- **mechanistically grounded**, not a data-mined correlation,
- and **not redundant with funding**, because funding is a lagged, clamped, venue-specific
  administrative response to basis while `sp_basis` is the raw imbalance.

`funding_gap` — realised HL funding minus what the observed basis implies — is the residual worth
studying: it isolates HL-specific positioning from market-wide leverage.

**Honest statement of evidence:** the *mechanism* is well documented; a clean published study of
`spot-perp basis → 1-7 day cross-sectional crypto returns` I did not find. This is
`[PRACTICE]` + `[INFERENCE]`, and it is the thing I would test first.

### 2.8 Summary: evidence quality of the cross-venue family

| Feature | Evidence | Verdict |
|---|---|---|
| Cross-venue dispersion persists hours→days | `[MEASURED]` JFE 2020 | Real |
| Rich venue → lower subsequent returns *on that venue* | `[MEASURED]` JFE 2020 | Real, but **relative-venue, not directional** |
| Kimchi premium level ↔ Korean volume/volatility | `[MEASURED]` FRL 2019 | Real |
| Kimchi premium level → BTC forward returns | `[MEASURED]` corr ≈ −0.06 | Real but near-zero |
| Kimchi zero-crossing → +1.7% / 7d | low-quality `[MEASURED]` | **Unverified, likely overfit** |
| Kimchi/BTC causality direction stable | `[MEASURED]` — it is **not**, it flips | Folklore as usually stated |
| Herfindahl volume concentration → returns | none found | `[INFERENCE]`, expect risk feature only |
| Venue disagreement → future vol | none found; reverse arrow is documented | **Probably circular**, test hard |
| Perp-perp basis → returns | none found | `[PRACTICE]` |
| Spot-perp basis → returns | mechanism `[MEASURED]`, prediction not | **Best untested candidate** |

---

## 3. Lead-lag: what is actually known

### 3.1 Venue-to-venue

- Price discovery concentrates on the deepest, highest-volume venues; Binance generally leads,
  and its average deviation from a composite BTC-USDT reference is ~0.40bps `[MEASURED]`
  (https://arxiv.org/abs/2506.08718, https://www.coindesk.com/research/the-evolution-of-the-crypto-cex-landscape-a-case-study-on-binance).
- Documented CEX-to-CEX lead-lags in crypto are on the order of **tens to hundreds of
  milliseconds up to a few seconds**. `[MEASURED]` — the practitioner critique of a widely-shared
  price-discovery article makes exactly this point: numbers derived from 10/50/100ms windows are
  fragile and often wrong (https://x.com/ltrd_/status/2064064213601923519).
- One 2026 study reports much larger lags — BTC CEX leading by ~5 minutes, SOL DEX leading Binance
  by ~40 minutes `[MEASURED, but implausible]` (https://zenodo.org/records/17084252). A 40-minute
  exploitable lead between SOL on a DEX and on Binance would be arbitraged into oblivion within a
  day. Almost certainly an artifact of resampling/alignment. **Do not build on it.** `[INFERENCE]`

**Plain statement for this system `[INFERENCE]`: at 5-minute sampling you cannot see any
venue-to-venue lead-lag that matters.** A 200ms Binance→Bybit lead is 1/1500th of one bar. Even a
generous 30-second lead is 1/10th of a bar. Your 5-minute panel resolves *nothing* below ~10
minutes, and there is no credible evidence of exploitable venue-to-venue leads above 10 minutes on
liquid coins. Do not spend a single day of work on venue-to-venue lead-lag. Spend it on §2.7.

The one exception worth checking `[INFERENCE]`: **thin venues on thin alts**. A coin whose only
real liquidity is on Binance may genuinely take minutes to reprice on Phemex/BingX. That lag is
real but it is *their* staleness, not *your* alpha — you cannot trade Phemex and you wouldn't want
to. Its correct use is as a **staleness detector** feeding `fresh()` in §1.7.

### 3.2 Coin-to-coin

This is where the surviving, tradeable lead-lag lives, because it operates at daily horizons.

- **The five largest coins lead small coins, and not vice versa** — and notably the large-coin
  returns *negatively* predict next-period small-coin returns `[MEASURED]`
  (https://www.sciencedirect.com/science/article/abs/pii/S0165188924000551, JEDC 2024). Note the
  sign: this is not naive "BTC up → alts up tomorrow."
- Bitcoin responds to information first, and its lagged return is a strong predictor for other
  cryptocurrencies; the mechanism is slow information diffusion under limited investor attention
  `[MEASURED]` (same).
- A "seesaw effect" in cross-predictability has been documented `[MEASURED]`
  (https://www.sciencedirect.com/science/article/abs/pii/S0927539823000956) — capital rotating
  between coins produces negative cross-predictability, consistent with the JEDC sign.
- Daily lagged BTC has significant positive interaction with ETH, ADA, BNB but **not XRP**
  `[MEASURED]` (https://dergipark.org.tr/en/download/article-file/2206815) — i.e. it is
  coin-specific, not universal.
- Long-short portfolios formed on past returns of cryptocurrencies generate sizable out-of-sample
  returns after transaction costs `[MEASURED]` (JEDC 2024).

**Concrete features `[INFERENCE]`:**
```
beta_btc(i)        = rolling 30d regression beta of r_i on r_BTC (daily)
resid_ret(i,h)     = r_h(i) - beta_btc(i) * r_h(BTC) - beta_eth(i)*r_h(ETH)
btc_lag_load(i)    = coefficient of r_1d(BTC, t-1) on r_1d(i, t), rolling 90d
sector_ret(s,h)    = equal-weight return of coins in cluster s
sector_resid(i)    = r_h(i) - sector_ret(s(i), h)
```
**Almost every directional feature should be computed on `resid_ret`, not raw returns.** Otherwise
your entire 20–50 position book is one leveraged bet on BTC beta wearing 40 different tickers.

Sector/cluster labels: do **not** hand-label ("L1", "meme", "DeFi"). Derive them by hierarchical
clustering on the 90-day correlation matrix of daily residual returns, re-estimated monthly.
Hand labels go stale and leak your priors `[INFERENCE]`.

### 3.3 Estimators for lead-lag on asynchronous data, and their pitfalls

| Estimator | What it's for | Pitfalls |
|---|---|---|
| **Hayashi-Yoshida cross-correlation** | Covariance/lead-lag on irregular, asynchronous tick data without resampling. Consistent and immune to asynchronous-trading (Epps) bias `[MEASURED]` (https://arxiv.org/pdf/1111.7103) | Not robust to microstructure noise — at high noise, plain realised covariance can be *more* efficient `[MEASURED]` (https://www.sciencedirect.com/science/article/abs/pii/S0304407610000576). Has a documented intrinsic telescoping/formulaic bias that discards relevant data `[MEASURED]` (https://arxiv.org/abs/2404.18233). **Also: pointless on 5-min bars — HY exists to exploit tick asynchrony you have already destroyed by sampling.** `[INFERENCE]` |
| **Cross-correlation of returns at lag k** | Simple, interpretable, fine on regular grids | Spurious lead-lag from differing liquidity: the illiquid series' returns are smoothed by stale prices, which *manufactures* an apparent lag `[INFERENCE]`. Correct by comparing against a stale-price null. Also strongly contaminated by the common market factor — always cross-correlate *residual* returns |
| **Granger causality** | Testing whether X's history improves the forecast of Y | Requires stationarity; finds "causality" whenever one series is smoother; results are lag-order dependent; and in crypto the direction **flips across regimes** — rolling-window Granger on the kimchi premium shows exactly that `[MEASURED]` (https://www.mdpi.com/2227-7390/14/9/1501). A full-sample Granger result in crypto is close to meaningless |
| **Transfer entropy** | Model-free, catches nonlinear dependence | Data-hungry (needs discretisation + long samples), badly biased in small samples, sensitive to bin choice. Used alongside Granger in the kimchi study, and it too shows time-varying asymmetric structure `[MEASURED]` (same URL) |
| **Hasbrouck information share / Gonzalo-Granger** | Attributing price discovery across venues of the *same* asset | Hasbrouck gives only bounds when innovations are contemporaneously correlated (they always are at 5-min); the upper/lower bounds are often uselessly wide. Requires cointegration, which fails when a venue's quote goes stale `[INFERENCE]` |

**Recommendation `[INFERENCE]`:** for this system use **lagged cross-correlation of residual daily
returns**, with a stale-price null and a Newey-West correction, and nothing more exotic. HY,
transfer entropy and Hasbrouck are the right tools for a tick-level microstructure study and the
wrong tools for a 5-min, daily-horizon panel. Choosing a sophisticated estimator for data that
cannot support it is one of the most common ways these studies produce publishable-looking
nonsense.

---

## 4. Combining features into a prediction

### 4.1 The standard pipeline

```
1. Compute raw feature f(i,t) for all coins
2. Winsorise cross-sectionally at 1%/99%  (NOT time-series winsorisation)
3. Cross-sectional rank -> [0,1] -> inverse-normal transform  (rank-z, robust to fat tails)
4. Neutralise: regress rank-z on {beta_btc, log(ADV), log(mktcap), sector dummies},
   keep the RESIDUAL. This is where most fake alpha dies.
5. Orthogonalise against already-accepted signals (Gram-Schmidt, in a fixed priority order,
   or symmetric/Löwdin orthogonalisation if you don't want to privilege one signal)
6. Sign-correct each signal so a positive value means "expected to outperform"
7. Combine: composite(i,t) = Σ_k w_k * z_k(i,t)
8. Rank the composite cross-sectionally -> long top decile, short bottom decile
```

Steps 2–4 are not optional. In crypto, *any* uncorrected cross-sectional signal loads on
size/liquidity and on BTC beta, and will backtest beautifully for reasons that have nothing to do
with the feature `[INFERENCE]`.

### 4.2 Why equal weights beat fitted weights on short samples

- Gu, Kelly & Xiu: expanding a linear model to 900+ predictors **overfits disastrously —
  out-of-sample R² goes negative** — and only penalisation or dimension reduction recovers
  predictability (~0.26% monthly R²); trees and neural nets do best, and their gains come from
  nonlinear interactions `[MEASURED]`
  (https://dachxiu.chicagobooth.edu/download/ML.pdf, RFS 33(5) 2020).
- Note the scale: **the state of the art in equity return prediction is an out-of-sample monthly
  R² of a fraction of one percent, with 60 years of data and thousands of stocks** `[MEASURED]`.
  You have one panel, ~1–2 years, 177 coins. Expecting more than that is the primary way this
  project fails `[INFERENCE]`.
- Harvey, Liu & Zhu reviewed 316 published factors and concluded a newly discovered factor needs
  **t > 3.0**, not 2.0, once multiple testing and publication bias are accounted for `[MEASURED]`
  (https://www.nber.org/papers/w20592). With hundreds of feature×venue combinations you are in a
  far worse multiple-testing position than the published literature — your bar should be **higher
  than 3.0, not lower** `[INFERENCE]`.

**Practical rule `[PRACTICE]` + `[INFERENCE]`:** with N features and T≈365 effective
cross-sectional dates, fitting N weights is estimating N parameters from 365 noisy observations
where the signal-to-noise ratio is ~0.03. Equal-weighting sign-corrected z-scores is
mathematically equivalent to imposing an extremely strong prior that all weights are equal — which
is exactly the right prior when your weight estimates have standard errors larger than the weights
themselves. Deviate from equal weights only via **shrinkage**:
```
w_final = δ * w_fitted + (1 - δ) * w_equal        with δ ≈ 0.2 - 0.3
```
and cap `|w_k|` so no feature exceeds ~3× the equal weight.

Other shrinkage that matters `[PRACTICE]`:
- **Ledoit-Wolf** shrinkage of the covariance matrix toward a constant-correlation target (177
  coins, 365 days — the sample covariance is nearly singular; the fix is mandatory, not optional).
- Shrink each feature's estimated *sign* too: if a feature's sign is unstable across
  non-overlapping sub-periods, drop it rather than trusting the full-sample sign.

### 4.3 What IC is worth trading at this cost level

Definition: `IC = Spearman correlation( signal(t), forward return(t → t+h) )` computed
cross-sectionally each period, then averaged.

**The arithmetic `[INFERENCE]` (this is the number to hold onto):**

Expected return of a position sized at 1 cross-sectional sigma:
```
E[r] ≈ IC × σ_cs × z_position
```
where `σ_cs` = cross-sectional standard deviation of h-day returns. For 177 crypto perps at a
3-day horizon, daily vol per coin is ~5–8%, so 3-day vol is ~9–14%, and cross-sectional dispersion
of 3-day residual returns is realistically **~10–12%**.

Costs per round trip:
- fees 9bps
- slippage 0.1–7.7bps in, same out → call it 4bps average round trip on a mixed book
- funding over a 3-day hold at typical rates: ~5–10bps, direction-dependent
- **Total ≈ 18–23bps ≈ 0.20%** per round trip.

Break-even IC for a top/bottom-decile book (average |z| ≈ 1.5 for decile portfolios):
```
IC_breakeven ≈ 0.0020 / (1.5 × 0.11) ≈ 0.012
```

| IC | Verdict |
|---|---|
| < 0.015 | **Not tradeable.** Costs eat it. Also indistinguishable from zero on 1 year of data |
| 0.02 – 0.03 | Marginal. Tradeable only with strict no-trade bands and cost-aware sizing |
| 0.03 – 0.05 | **The realistic target.** This is what a good, honestly-validated multi-feature crypto cross-sectional composite looks like |
| 0.05 – 0.08 | Excellent. Be suspicious; re-audit for lookahead |
| > 0.10 | **You have a bug.** Lookahead, survivorship, or stale-price leakage. Find it before trading |

Sanity check via the fundamental law `[MEASURED]` framework
(https://analystprep.com/study-notes/cfa-level-2/state-and-interpret-the-fundamental-law-of-active-portfolio-management-including-its-component-terms-transfer-coefficient-information-coefficient-breadth-and-active-risk-aggressiveness/):
`IR ≈ IC × √BR × TC`. With IC = 0.04, breadth = 177 coins × ~120 rebalances/year ≈ 21,000 (but
heavily correlated, so effective breadth is far lower — call it 1,500), and a transfer coefficient
of 0.5 after constraints: `IR ≈ 0.04 × 39 × 0.5 ≈ 0.78`. That is a realistic, respectable, and
*unexciting* answer, and it is the honest one. Note the turnover-adjusted IR is always strictly
below the naive IR `[MEASURED]` (https://arxiv.org/pdf/2105.10306).

**Report IC with error bars, always.** `SE(IC) ≈ std(IC_t)/√T`. If your reported IC is 0.04 and
your SE is 0.05, you have found nothing.

---

## 5. Long/short construction

### 5.1 Cross-sectional vs directional

At 5–10 entries/day into a 20–50 book with 1–7 day holds, **cross-sectional long/short is the
correct default** `[INFERENCE]`:
- Directional (net long/short crypto) means your P&L is ~90% BTC beta. You have no BTC-timing
  edge in this feature set, and BTC timing gives you 1 observation per day instead of 177.
- Cross-sectional lets you extract the ~177 obs/day of breadth documented above and kills the
  dominant risk factor for free.
- Published crypto long-short portfolios formed on past returns survive transaction costs
  `[MEASURED]` (JEDC 2024) — the cross-sectional form is the one with evidence.

Keep a *small*, explicitly separate directional sleeve if you want (sized off funding/basis and
regional-premium regime features), but budget it as a distinct strategy with its own risk limit —
never let it leak into the cross-sectional book through sloppy netting.

### 5.2 Beta hedging / market neutrality

```
beta_btc(i) = OLS beta of daily r_i on r_BTC, 60d, shrunk toward 1.0:
              beta_used = 0.7*beta_raw + 0.3*1.0
net_beta    = Σ_i w_i * beta_used(i)
```
Enforce `|net_beta| < 0.05` by adding/removing a BTC (or ETH) perp hedge leg, **not** by
distorting position weights `[PRACTICE]`. Rebalance the hedge daily, with a no-trade band, so it
doesn't dominate turnover.

Also neutralise: sector/cluster (from §3.2), size (log market cap), and liquidity (log ADV).
Dollar-neutral is *not* the same as beta-neutral in crypto because high-beta alts dominate the
short book naturally.

### 5.3 Sizing by residual volatility

**Size by residual vol, never total vol** `[PRACTICE]`:
```
resid_i,t = r_i,t - beta_btc(i)*r_BTC,t - beta_sector*r_sector,t
σ_res(i)  = EWMA vol of resid_i over ~30d, floored at the 10th percentile across coins
w_i       ∝ z_i / σ_res(i)
```
Total-vol sizing systematically under-weights high-beta coins that are actually *low* idiosyncratic
risk, and over-weights low-beta coins whose entire vol is idiosyncratic. Since the book is
beta-hedged, only residual risk is your risk `[INFERENCE]`.

Floor `σ_res` — otherwise a coin that happened to be quiet for 30 days gets an enormous weight,
which is the classic vol-targeting blowup.

### 5.4 Cluster / correlation caps

```
- max weight per coin:        4-6% of gross
- max weight per cluster:     20-25% of gross (clusters from §3.2 hierarchical clustering)
- max gross:                  a fixed leverage cap, sized so a 3σ cluster move ≠ margin call
- max positions:              20-50 as specified; enforce a MINIMUM too (~15) --
                              a 5-position book is a punt, not a portfolio
```
Correlations in crypto go to ~0.9 in a drawdown `[PRACTICE]`. Cluster caps computed on calm-period
correlations will be violated exactly when it matters. Compute the cluster correlation matrix on
the **worst 10% of market days only** and set caps from that stressed matrix `[INFERENCE]`.

### 5.5 No-trade bands and turnover

At 5–10 entries/day with a 20–50 book, you replace roughly 20% of the book daily → implied average
hold ≈ 5 days, consistent with the stated 1–7 days `[INFERENCE]`.

Turnover control that works `[PRACTICE]`:
```
- Enter only if rank(composite) is in the top/bottom 10%
- Exit only if rank leaves the top/bottom 30%    <- asymmetric band, this is the key
- Additionally require: expected_edge(i) > 2 x expected_cost(i)
  where expected_cost includes fee + measured slippage for THAT coin + expected funding
  over the expected hold + the current HL premium (prem_HL from 2.2)
```
The asymmetric entry/exit band (enter at decile 1, exit at tercile 1) is the single highest-value
turnover control: it cuts turnover roughly in half for a small loss of gross IC `[PRACTICE]`.

**The 7.7bps-slippage alts need a higher bar.** Cost is coin-specific and varies 77× across your
book. A single global edge threshold will systematically over-trade the thin alts, where the
backtest looks best (highest raw dispersion) and the live P&L is worst `[INFERENCE]`.

### 5.6 Holding period vs signal half-life

```
half_life(k) = the lag h at which IC_k(h) falls to half of IC_k(1)
```
Compute the **IC decay curve** for every feature: `IC(h)` for h = 1..14 days. Then:
- Hold period should be roughly **the signal half-life**, not longer `[PRACTICE]`. Holding past the
  half-life pays full costs for decayed edge.
- Features with different half-lives should not be equal-weighted into one composite and traded on
  one schedule. Either split into a fast book and a slow book, or weight each feature by
  `IC(h_target)` rather than `IC(1)`.
- A feature whose IC(1) is high but IC(3) is zero is a microstructure/execution signal, not a
  1–7 day signal. Given 9bps costs, **discard it** — you cannot monetise a 1-day half-life at
  this cost level `[INFERENCE]`.

### 5.7 Crypto short asymmetries (this is where naive long/short dies)

1. **Funding is the short's friend *and* the short's tax.** When perps trade at a premium, shorts
   *receive* funding — free carry. When the crowd is short (negative funding), your short *pays*.
   Since your short book will systematically select coins the crowd is also short (bad momentum,
   bad flow), **your shorts will disproportionately be the ones paying funding** `[INFERENCE]`.
   Fix: include `expected funding over the hold` in the entry cost, with the correct sign per
   side. Do not use a symmetric cost model.

2. **Squeeze risk is real and asymmetric.** Sustained extreme funding has historically preceded
   the sharpest reversals `[PRACTICE]`. Concretely: cap or veto shorts where
   `funding_z < -2 AND OI at a 30-day high AND long/short account ratio at an extreme`. That is a
   crowded-short configuration, and crowded shorts in crypto unwind violently.

3. **Return distribution asymmetry.** Alt perps have a bounded downside (−100%) and unbounded
   upside; a short can lose several multiples of the position. Cross-sectional vol-scaling assumes
   symmetric risk and understates short tail risk `[INFERENCE]`. Apply an explicit short-side
   haircut (e.g. size shorts at 0.8× the vol-implied weight) or hard stop-losses on shorts only.

4. **Liquidation mechanics.** On perps you have no borrow to recall, but you do have a maintenance
   margin and auto-deleveraging. The relevant risk is not "short squeeze" in the equity sense but
   **cascading liquidation of the whole book** when a correlated move hits margin. That means the
   binding constraint is portfolio-level margin, not per-position. Size gross so that a 3σ
   correlated move (using the stressed correlation matrix from §5.4) leaves margin intact.

5. **Listing/delisting asymmetry.** Newly-listed HL perps have thin books, no history for
   `σ_res`, and extreme funding. Impose a minimum listing age (e.g. 30 days) before a coin is
   eligible, on both sides `[INFERENCE]`.

---

## 6. What kills this — specific failure modes

### 6.1 Stale quotes (the number one killer)

A thin venue that hasn't traded in an hour still returns a bid/ask. Every one of your dispersion,
disagreement, lead-lag, and volatility features will be dominated by that venue.

Symptoms and effects `[INFERENCE]`:
- Stale prices produce **artificial autocorrelation and artificial lead-lag** — a stale series
  "follows" a live one by construction. Every venue-lead-lag result computed without a staleness
  filter is measuring which venue is deadest.
- Stale prices **understate volatility** and **overstate dispersion**, in the same dataset,
  for different coins.
- Stale prices make Amihud explode (|return| jumps when a stale quote finally updates, on near-zero
  volume) — the exact mechanism behind the "Amihud is an outlier artifact" finding already
  recorded for this system.

Mandatory defences:
```
fresh(i,v,t):
  - reject if mid unchanged for > K bars (K ~ 6, i.e. 30 min) AND volume == 0 over the window
  - reject if spread > max(50bps, 5 x cross-venue median spread)
  - reject if |prem(i,v,t)| > 200bps  (nobody is really 2% off; it's stale or wrong)
  - reject if the venue has < some minimum share of credible volume for that coin
  - track and LOG the rejection rate per venue per coin -- this rate is itself a feature
```
Then run every headline result twice: once with the freshness filter, once without. **If a result
changes materially, it was a staleness artifact.**

### 6.2 Symbol collisions

Across 26 venues, the same ticker is a different asset. Classic traps `[PRACTICE]`:
- Rebrands and redenominations (MATIC→POL, LUNA/LUNC, FTM→S) — the ticker persists across a
  discontinuous price change.
- Token splits/redenominations where one venue applies a 1000× factor and another doesn't
  (SHIB-style 1000SHIB contracts, 1000PEPE, 1MBABYDOGE). This produces a permanent 1000×
  "dispersion" that will pass any percentage-based sanity check *only if* you normalise it away —
  and will destroy everything if you don't.
- Genuinely different assets sharing a ticker on different venues.
- Wrapped/bridged variants (BTCB, WBTC, renBTC) priced separately.

Defence: **do not join on ticker.** Build an explicit `(venue, venue_symbol) → canonical_asset_id`
mapping with a multiplier field, and validate it continuously with a cheap automated check: for
every (coin, venue) pair, the trailing-30-day median `|prem(i,v)|` must be < 100bps. Anything above
that is a mapping bug until proven otherwise `[INFERENCE]`.

### 6.3 Non-synchronous timestamps

Your "5-minute snapshot" is 26 API calls that do not complete at the same instant, against venues
with different clock skew, different rate limits, and different queueing.

- If venue A's snapshot is systematically taken 20 seconds after venue B's, A will appear to lead
  B by 20 seconds, forever, on every coin `[INFERENCE]`. This will look like a beautiful,
  highly significant lead-lag discovery. It is a collection-order artifact.
- **Test for it:** the apparent lead should be *identical across all 177 coins* if it is a
  collection artifact, and *coin-dependent* if it is real. Run that test before believing any
  venue lead-lag number.
- Record the actual per-call timestamp (venue-reported *and* local receipt time), not just the bar
  label. If you only store the bar label, this bug is undiagnosable.
- Epps effect: measured cross-venue correlation falls toward zero as sampling frequency rises,
  purely from asynchrony `[MEASURED]` (the whole motivation for Hayashi-Yoshida,
  https://arxiv.org/pdf/1111.7103). At 5-min this is mild but nonzero for thin alts.

### 6.4 Survivorship in the coin universe

If your 177-coin list is "coins that are listed on Hyperliquid today," your backtest excludes every
coin that was delisted, collapsed, or was never listed. In crypto the delisted set is not a small
tail — it is the entire left side of the return distribution `[INFERENCE]`.

Effects:
- A short book will look catastrophically bad (you removed the coins that went to zero — exactly
  what shorts want to catch).
- Momentum will look better than it is.
- Any liquidity feature will look weak, because the illiquid coins that died are gone.

Defence: maintain a **point-in-time universe** — a table of (asset, venue, first_seen, last_seen)
built from the panel itself as it was collected. Backtest each date against the universe as it
existed *on that date*. If the historical panel was built by querying today's coin list
retroactively, this is unfixable for existing history and you should say so explicitly rather than
report the backtest.

### 6.5 Currency conversion (KRW / INR) hides an FX assumption

`kimchi = P_KRW / FX_USDKRW / P_USD − 1` is a **two-asset** quantity. Failure modes `[INFERENCE]`:
- **FX timestamp mismatch.** KRW spot FX trades on a Seoul session; crypto trades 24/7. On a
  weekend or a Korean holiday your USDKRW is a stale Friday print, and the "kimchi premium" you
  compute over the weekend is mostly an FX staleness artifact. Weekend kimchi signals are the most
  suspicious part of the whole panel.
- **Which FX rate?** Interbank mid vs the rate a real arbitrageur can achieve after remittance
  fees and the >USD 50k documentation requirement `[MEASURED]` (Makarov-Schoar) differ by enough
  to swamp the signal. The *tradeable* premium is much smaller than the *quoted* premium.
- **INR has a 1% TDS wedge**, which is a tax, not a premium. Failing to subtract it makes every
  Indian-premium number a constant plus noise.
- **Stablecoin leg.** Upbit KRW markets are KRW/coin; your CP is USDT-denominated. So
  `kimchi` also embeds the **USDT/USD basis**. During a stablecoin depeg your kimchi premium moves
  for reasons that have nothing to do with Korea. Decompose explicitly:
  `KRW premium = (KRW/USD leg) + (USD/USDT leg) + (true segmentation)`.

### 6.6 Multiple testing across hundreds of feature×venue combinations

You have ~6 feature families × ~8 variants × 26 venues ≈ **1,200+ candidate features**, tested on
~365 effective dates. At α=0.05 you get ~60 "significant" features by pure chance. Harvey-Liu-Zhu
already argue t>3.0 is the right bar for *published* equity factors after accounting for the
field's collective data mining `[MEASURED]` (https://www.nber.org/papers/w20592).

Defences `[PRACTICE]` + `[INFERENCE]`:
1. **Pre-register.** Write the feature list and hypothesised sign *before* running the study.
   The ranked list in §7 is intended to be that pre-registration.
2. **Aggregate over venues before testing.** Do not test `spread_on_MEXC` and `spread_on_Gate` as
   separate features. Test `spread_consolidated`, `spread_dispersion`, and `spread_HL_relative` —
   three features, not 26. This alone cuts the test count by ~8×.
3. **Family-level control.** Benjamini-Hochberg FDR within each feature family, not
   feature-by-feature p-values.
4. **Deflated Sharpe / Bailey-López de Prado** on the final composite, given the number of
   configurations tried.
5. **Hold out the last 6 months and never look at it** until the composite is frozen. One look
   burns it.
6. **Sign stability across non-overlapping sub-periods** is a better filter than any p-value. A
   real feature has the same sign in 3 of 3 sub-periods. Data-mined ones don't.
7. **Track the number of configurations you actually tried** and report it. Everyone forgets this
   and every reported t-stat is inflated accordingly.

### 6.7 One more the brief didn't ask about: lookahead through the consolidated price

`CP(i,t)` is built from a volume-weighted average — if you compute weights using volume from bar
`t` and then predict return from `t` to `t+1`, you are fine. But if any smoothing window
(`prem_ma`, `σ_res`, EWMA) is centred rather than trailing, or if winsorisation limits are computed
on the full sample rather than expanding, you have leaked. **Every normalisation must be expanding
or trailing-window.** Full-sample z-scoring is the most common silent lookahead in cross-sectional
studies `[INFERENCE]`.

---

## 7. Ranked build list — the first 15 features

Ordered by (expected value per unit of engineering effort) × (robustness to the §6 failure modes).
Everything here is computable from the described panel.

**Tier 0 — infrastructure that must exist before any feature is trustworthy**

| # | Feature | Why |
|---|---|---|
| 0a | `(venue, symbol) → canonical_asset_id` map with multiplier | Without it every cross-venue number is garbage (§6.2) |
| 0b | `fresh(i,v,t)` staleness mask + per-venue rejection-rate log | Stale quotes are the #1 source of fake cross-venue results (§6.1) |
| 0c | `CP(i,t)` consolidated price (credibility × 1/spread × √volume × freshness) | Every feature below is defined relative to it (§1.7) |
| 0d | Point-in-time universe table | Otherwise the short book's backtest is a fiction (§6.4) |

**Tier 1 — the 15 features, in build order**

| # | Feature | Formula sketch | One-line reason |
|---|---|---|---|
| 1 | **`sp_basis`** — consolidated perp vs consolidated spot | `ln(CP_perp/CP_spot)`, z-scored per coin | The panel's unique edge: mechanistically grounded crowding measure, cross-sectional (177 obs/day), persistent at a days timescale (§2.7) |
| 2 | **`resid_mom_7d_skip1`** — BTC/sector-residual 7-day momentum skipping the last day | `r(t-1d → t-7d)` on residual returns | Only crypto cross-sectional predictor with real published evidence at this exact horizon `[MEASURED]` (JEDC 2024, Starkiller) |
| 3 | **`rev_1d_resid`** — 1-day residual reversal | `−r_1d(resid)` | The documented crypto short-horizon reversal; opposite sign to #2, so it also orthogonalises it (§1.1) |
| 4 | **`funding_carry_expected`** — signed expected funding over the expected hold | Σ forward funding, per side | Not alpha — this is a **cost line worth 21bps on a 7-day hold**, larger than fees. Must exist before any P&L claim is credible (§1.6) |
| 5 | **`spread_HL_relative`** + measured slippage curve per coin | `spr_HL / median_v(spr)` | Your execution disadvantage, coin by coin. Directly gates which signals are tradeable (77× cost spread across the book) |
| 6 | **`top_minus_retail`** — Binance top-trader ratio z minus account-ratio z | z-diff, hourly → daily | Closest proxy to informed-vs-uninformed positioning available; a state that persists for days (§1.5) |
| 7 | **`oi_chg_1d` × `sign(Δprice)`** — OI/price regime | signed product, plus raw `Δln(OI)` | Distinguishes new positioning from unwinding; standard practitioner primitive with a clear mechanism (§1.5) |
| 8 | **`disp_iqr_z`** — robust cross-venue price dispersion, z-scored | IQR of `ln(m/CP)` | The Makarov-Schoar arbitrage index in robust form; documented to persist hours→days `[MEASURED]`; a segmentation/stress state (§2.1) |
| 9 | **`GK_vol` + `JumpFrac`** — Garman-Klass vol and jump fraction on the consolidated price | from synthetic OHLC of `CP` | Needed anyway for sizing (§5.3); jump fraction separates trending vol from gap risk (§1.2) |
| 10 | **`vol_surprise`** — credible-volume shock vs 30-day median | `log(V_1d / median_30d)` on credible venues only | Cheap, persistent, well-behaved; also the best conditioner for #2/#3 (§1.4) |
| 11 | **`taker_imbal`** — Binance taker buy/sell imbalance, 1d and 7d | `(buy−sell)/(buy+sell)` | The only genuinely signed flow in the panel; everything else is a proxy (§1.5) |
| 12 | **`HHI` + `hl_share`** — venue concentration and Hyperliquid's own share | Herfindahl on credible volume | Risk/eligibility feature: flags coins where your own trading is the market and where slippage estimates break (§2.3) |
| 13 | **`prem_resid_HL`** — Hyperliquid rich/cheap vs its own 7-day structural premium | `prem_HL − EWMA_7d(prem_HL)` | Entry-timing and cost adjustment; the documented rich-venue mean reversion applies to your own fill `[MEASURED]` (§2.2) |
| 14 | **`spread_widening_breadth`** — fraction of credible venues with `spr_z > 1` | count/total | Far more robust than any single venue's spread; a genuine coin-level risk-off signal (§1.3) |
| 15 | **`kimchi_breadth`** — fraction of KRW-listed coins at a positive premium, plus `kimchi_z` for BTC | needs the §6.5 FX decomposition | Cross-sectional version of the one regional premium with real published evidence; the breadth form gives ~50× the statistical power of the single BTC series (§2.5) |

**Deliberately excluded from the first 15, and why `[INFERENCE]`:**
- *Venue-to-venue lead-lag of any kind* — 5-min sampling cannot see it (§3.1); high risk of the
  collection-order artifact (§6.3).
- *Amihud illiquidity* — already diagnosed as an outlier artifact in this system; if included at
  all, only as `log(median(winsorised))`, and only after #1–15 are validated.
- *Kyle's lambda* — not computable without signed trades; the proxy is ~collinear with #9/#10.
- *Transfer entropy / Hasbrouck information share* — wrong tools for this data (§3.3).
- *Hand-labelled sector membership* — replace with correlation-derived clusters (§3.2).
- *Any per-venue feature tested separately across 26 venues* — collapse to
  consolidated/dispersion/HL-relative triples first (§6.6).

**Validation order `[INFERENCE]`:** build Tier 0 → compute #1–#15 → report `IC(h)` for h=1..14 with
standard errors for each, individually, **before** combining anything. Then equal-weight the
sign-stable survivors, shrink toward equal weights with δ≤0.3, and only then look at the held-out
period once.

---

## Sources

- Makarov & Schoar, *Trading and Arbitrage in Cryptocurrency Markets*, JFE 2020 — https://personal.lse.ac.uk/makarov1/index_files/CryptocurrencyMarkets.pdf
- Gu, Kelly & Xiu, *Empirical Asset Pricing via Machine Learning*, RFS 2020 — https://dachxiu.chicagobooth.edu/download/ML.pdf
- Harvey, Liu & Zhu, *…and the Cross-Section of Expected Returns* — https://www.nber.org/papers/w20592
- *Cross-cryptocurrency Return Predictability*, JEDC 2024 — https://www.sciencedirect.com/science/article/abs/pii/S0165188924000551
- *A seesaw effect in the cryptocurrency market* — https://www.sciencedirect.com/science/article/abs/pii/S0927539823000956
- *Intraday return predictability in cryptocurrency markets: momentum, reversal, or both* — https://www.sciencedirect.com/science/article/abs/pii/S1062940822000833
- *Momentum or reversal: which is the appropriate third factor for cryptocurrencies?* — https://www.sciencedirect.com/science/article/abs/pii/S1544612321002208
- *Kimchi premium and speculative trading in bitcoin*, FRL 2019 — https://www.sciencedirect.com/science/article/abs/pii/S1544612319301357
- *Asymmetric and Time-Varying Lag Structures in Bitcoin's Kimchi Premium* (rolling Granger + transfer entropy), Mathematics 2026 — https://www.mdpi.com/2227-7390/14/9/1501
- *Price Discovery in Cryptocurrency Markets* — https://arxiv.org/abs/2506.08718
- Huth & Abergel, *High frequency lead/lag relationships — empirical facts* — https://arxiv.org/pdf/1111.7103
- *A Note on Asynchronous Challenges: Formulaic Bias and Data Loss in the Hayashi-Yoshida Estimator* — https://arxiv.org/abs/2404.18233
- *Covariance measurement with non-synchronous trading and microstructure noise* — https://www.sciencedirect.com/science/article/abs/pii/S0304407610000576
- Amihud, *Illiquidity and stock returns* — https://www.cis.upenn.edu/~mkearns/finread/amihud.pdf
- *Momentum and liquidity in cryptocurrencies* — https://arxiv.org/pdf/1904.00890
- *Fundamentals of Perpetual Futures* — https://arxiv.org/pdf/2212.06888
- *The Two-Tiered Structure of Cryptocurrency Funding Rate Markets*, Mathematics 2026 — https://www.mdpi.com/2227-7390/14/2/346
- *Microstructure alpha: hierarchical learning and cross-asset transfer in cryptocurrency markets* — https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2026.1811716/full
- *Cross-sectional Momentum in Cryptocurrency Markets* — https://www.starkiller.capital/post/cross-sectional-momentum-in-cryptocurrency-markets
- *Cryptocurrency momentum has (not) its moments* — https://link.springer.com/article/10.1007/s11408-025-00474-9
- *Turnover-Adjusted Information Ratio* — https://arxiv.org/pdf/2105.10306
- Fundamental law of active management (IC × √BR × TC) — https://analystprep.com/study-notes/cfa-level-2/state-and-interpret-the-fundamental-law-of-active-portfolio-management-including-its-component-terms-transfer-coefficient-information-coefficient-breadth-and-active-risk-aggressiveness/
- *Is the Korean Kimchi Premium still front-running Bitcoin price?* (low-quality, cited as folklore) — https://cryptoslate.com/does-thes-kimchi-premium-still-front-run-btc/
- DEX/CEX lead-lag study (cited as implausible) — https://zenodo.org/records/17084252
- Practitioner critique of HFT-window price-discovery numbers — https://x.com/ltrd_/status/2064064213601923519
- Coinbase Institutional, *A Primer on Perpetual Futures* — https://www.coinbase.com/institutional/research-insights/research/market-intelligence/a-primer-on-perpetual-futures
- CoinDesk Research, *Evolution of the Crypto CEX Landscape: Binance* — https://www.coindesk.com/research/the-evolution-of-the-crypto-cex-landscape-a-case-study-on-binance
