# Chapter 5 — The crowd: funding, open interest, CVD, liquidations, positioning, sentiment

The perp market shows you where the leveraged crowd stands. Your edge is not in knowing
that a crowd exists; it is in asking one question every time: **who is aggressive, and are
they being rewarded?** [source: https://www.bitget.com/news/detail/12560603860656]. A crowd
that is aggressive and *not* rewarded is fragile. A crowd that is aggressive and rewarded is
a trend. Numbers marked **[measured in our store]** are ours (`docs/MEASURED_LINKS_2026-09-16.md`).

## 1. What each thing is

| measure | what it is | who it describes |
|---|---|---|
| **Funding** | periodic payment between longs and shorts that pins the perp to spot. Positive = perp above spot = **longs pay shorts** = crowded longs. Negative = perp below spot = **shorts pay longs** = crowded shorts, **squeeze risk is UP** [source: https://hmaquant.substack.com/p/perpetual-futures-and-funding-rates] | leveraged perp traders, both sides |
| **Open interest (OI)** | total notional of open perp positions. Always 50/50 long/short by construction; what changes is *who is aggressive* [source: bitget/CryptoCred above] | how much leverage is in the coin |
| **CVD** | cumulative (market buys − market sells): aggressive taker flow. Rising CVD = net aggressive **buying** [source: bitget/CryptoCred] | who is crossing the spread |
| **Liquidations** | forced closes when margin runs out. Long liquidations = forced *selling*; short liquidations = forced *buying* [source: bitget/CryptoCred] | who has already been wrong |
| **Positioning / long-short ratio** | share of accounts (or top traders) net long | how one-sided the retail crowd is |
| **Fear & Greed** | a composite sentiment index 0–100 | mood, slow-moving |

## 2. Why it matters (the economics)

Leverage has to be unwound. A crowded long book is a queue of forced sellers waiting for a
trigger; a crowded short book is a queue of forced buyers ("every leveraged long is a forced
seller waiting for a trigger" [source: hmaquant]). Funding is the *price* of that crowding:
at +0.05%/8h a long pays about **54.75% a year** to hold [source: hmaquant] — a cost that
only makes sense if the move is coming soon. When the move does not come, the crowd is
"unrewarded" and the payoff is asymmetric against it.

**[measured in our store]** funding → forward return, 172 coins, 377 daily cross-sections:
| horizon | Q1 (most negative funding) excess | Q5 (most positive) excess | rank-IC | t |
|---|---|---|---|---|
| 1 day | +6 bps | +8 bps | −0.002 | −0.3 (nothing) |
| 3 days | +11 | +12 | −0.011 | −1.5 (nothing) |
| 7 days | **+54** | **+29** | **−0.027** | **−3.8** (real, small) |

With the funding itself counted over 7 days: **long the crowded-short quintile (Q1) = +101
bps** (48 bps funding received + 54 bps price bounce); **short the crowded-long quintile
(Q5) = −6 bps** (the +22 bps funding collected did not cover price still drifting +28).
Readings that follow, and that the desk enforces:
- crowded **shorts** get squeezed and pay you to hold the other side — that is the measured
  edge, and it is a 7-day effect, not a 1-day one;
- crowded **longs** do *not* fall on schedule — a short on a Q5 coin is a hedge, not a
  source of return, unless there is a catalyst;
- a long on a Q5 coin pays ~22 bps/week: the thesis must be worth more than that; a short on
  a Q1 coin pays ~48 bps/week against you: it needs a much stronger thesis.

## 3. Reading rules

### 3a. Price × OI (who is opening, who is closing) [source: bitget/CryptoCred]
| price | OI | reading |
|---|---|---|
| ↑ | ↑ | new longs opening, buyers aggressive — momentum building (and fragility building) |
| ↓ | ↑ | new shorts opening, sellers aggressive — bearish momentum (or shorts pressing into a low) |
| ↑ | ↓ | short covering — rally without new buyers, likely to fade |
| ↓ | ↓ | longs closing — selling without new shorts, often near exhaustion |
| flat | ↑ | positions piling up with no follow-through — vulnerability; the next move is violent |

### 3b. Funding × price (is the aggressive side rewarded?) [source: bitget/CryptoCred]
| funding | price | reading |
|---|---|---|
| high positive | stalling / falling | longs aggressive and unrewarded → bearish, especially at resistance |
| high negative | stalling / rising | shorts aggressive and unrewarded → bullish, especially at support |
| turning more positive | falling | dip-buyers in disbelief; spot is likely selling → bearish |
| turning more negative | rising | sellers fading the move; spot is likely buying → bullish |
| extreme after a liquidation flush | any | **not** positioning — perps dislocate harder than spot after a cascade; funding normalises without a squeeze |

### 3c. CVD × price (aggression vs absorption) [source: bitget/CryptoCred]
| CVD | price | reading |
|---|---|---|
| higher high | lower high | aggressive buying being absorbed by passive sellers → reversal risk down |
| lower low | higher low | aggressive selling absorbed by passive buyers → reversal risk up |
| rising | falling | net aggressive **buying** while price falls: buyers absorbed — weak, or a squeeze setting up if OI is rising too |
| perp CVD up hard into a level, spot CVD flat | — | perps over-excited, spot not confirming → reversal likely |

CVD limits: sophisticated flow can move price with limit orders that leave no CVD trace;
CVD works only with confluence (level + funding/OI) [source: bitget/CryptoCred].

### 3d. Liquidations × OI (forced flow) [source: bitget/CryptoCred]
| context | pattern | reading |
|---|---|---|
| range | OI ↓ + liquidations | flush inside the range → mean-reverting |
| trend | OI ↑ + liquidations | forced flow feeds the trend → continuation |
| breakout | OI ↑ + short liquidations | continuation up |
| breakdown | OI ↑ + long liquidations | continuation down |
| dump to support | long liquidations + OI ↓ | reversal setup up |
| rally to resistance | short liquidations + OI ↓ | reversal setup down |

Liquidation *heatmaps* are estimates built from OI, funding and leverage data, not leaked
positions; dense clusters act as price magnets because forced exits inject one-way flow
[source: https://www.coinglass.com/learn/how-to-use-liqmap-to-assist-trading-en]. Clusters
below price are long liquidations (forced selling if reached); above price, short
liquidations (forced buying).

### 3e. Positioning and sentiment
- Long/short **account** ratio counts accounts, not dollars; top-trader **position** share
  is dollar-weighted and usually more informative. Both are inputs to "is the crowd
  one-sided", neither times anything alone.
- Fear & Greed 90 is not a short signal: extremes persist; use it to name the mood, then
  look for the crowd being unrewarded before acting.

### 3f. Signs a move is a short squeeze, not buying (crypto version)
1. funding was negative going in and OI **falls** during the move (shorts closing, not longs opening);
2. short liquidations spike on the way up;
3. perp CVD leads, spot CVD flat; the move retraces once liquidations stop.
(Stock-market signs — borrow fees, short interest, "available shares" — do not exist here.)

## 4. Worked example

Coin X: funding −0.03%/8h (Q1 of the universe), OI +15% in 3 days, price flat, top-trader
share net short.
- Sign: negative → **shorts pay longs** → crowded **shorts** → squeeze risk **UP**.
- Price × OI: flat/↑ → positions piling up, no follow-through → fragile.
- Who is aggressive? Shorts. Rewarded? No (price flat) → **bullish**.
- **[measured]** Q1 longs made +101 bps/7d including +48 bps funding received.
- Trade shape: long, hold ~7 days (the effect is a 7-day one), stop 1.5–3 *own* daily
  moves, falsifier "OI keeps rising and price breaks down through support" (shorts are
  being rewarded after all). Not a 1-day trade.

Coin Y: funding +0.08%/8h (Q5), OI record, price flat 3 days.
- Longs aggressive, unrewarded → fragile. But **[measured]** shorting Q5 alone made −6 bps:
  the crowd does not fall on schedule. A short needs a catalyst (event, breakdown level,
  spot CVD selling); otherwise it is a hedge, not a trade.

## 5. Common misreads

1. **Funding sign flipped.** Negative funding = shorts pay = crowded shorts = squeeze **UP**.
   The exam answer "negative funding: crowded long, squeeze down" is backwards on both counts.
2. **CVD backwards.** Rising CVD = net aggressive *buying*. Rising CVD + falling price =
   buyers being absorbed, not "aggressive selling".
3. **Extreme funding = imminent squeeze.** Max negative funding on a small alt often
   normalises via a spot dump, not a squeeze; needs OI confluence and a reason the
   aggressors are wrong [source: bitget/CryptoCred].
4. **Post-flush funding read as positioning.** After a cascade, funding reflects the perp
   dislocation, not fresh shorts [source: bitget/CryptoCred].
5. **Shorting crowded longs "because funding is high".** **[measured]** −6 bps/7d. Collecting
   funding is not the same as the price falling.
6. **Trading funding on a 1-day horizon.** **[measured]** no link at 1 or 3 days; the effect
   is weekly.
7. **Any single indicator.** Indicators become informative when something does not add up or
   sits at a relative extreme; in bland conditions they are noise [source: bitget/CryptoCred].

## 6. Sources
- Our store: `docs/MEASURED_LINKS_2026-09-16.md` §4, §4b (377 daily cross-sections, ~27k coin-days, funding 2025-08 → 2026-09).
- CryptoCred, "Comprehensive Guide to Crypto Futures Indicators" (OI/funding/CVD/liquidation tables) — https://www.bitget.com/news/detail/12560603860656
- Perpetual futures and funding mechanics, annualisation, cascade risk — https://hmaquant.substack.com/p/perpetual-futures-and-funding-rates
- Liquidation heatmaps: what they are and are not — https://www.coinglass.com/learn/how-to-use-liqmap-to-assist-trading-en
