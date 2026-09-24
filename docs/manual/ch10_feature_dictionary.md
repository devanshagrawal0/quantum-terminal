# Chapter 10 — The feature dictionary: every column in the store, what it measures, what it is for, its limit

The store (`data/store.db`) computes **323 feature columns** in 21 tables. The model never
sees them raw; it sees the market table (a chosen slice), the candidate rows, the coin
card and the tool results — all built from these. This chapter is the reference for what
each column *is*, so that when a number appears, the reading is known. Column families are
grouped; a row covers all members of the pattern. "Rows" = how many rows the table holds
today (0 = defined, not filled yet — do not expect it in a tool result).

Reading rule that applies to all of it: **a feature is a measurement of one economic
quantity (chapter 2), not a signal.** It becomes information when it sits at an extreme of
its own history, when two of them disagree, or when it changes after you entered.

## A. Returns and momentum — `feat_ret` (4.78M rows, hourly, all coins) and `feat_price` (26.7k rows, daily)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `r_1h, r_4h, r_12h, r_1d, r_3d, r_7d, r_14d, r_30d, r_90d` | simple return over the window | movers list; "has it already moved" | raw, includes BTC's part |
| `mom_7d_skip1, mom_30d_skip1, mom_90d_skip7` | return over the window **excluding the most recent day/week** | cross-sectional momentum rank (the academic form skips the last period to avoid reversal) | momentum is a crowd, chapter 5 |
| `rev_1h, rev_1d` | the most recent move, as a reversal candidate | short-horizon reversal | **[measured]** 1-day reversal is real and dead after costs |
| `ret_zscore` | today's return ÷ its own recent vol | "how unusual is today" | window-dependent |
| `logret_cum` | cumulative log return | plotting, drawdown math | not a signal |
| `resid_r_1d, resid_r_7d, resid_mom_7d_skip1` | returns after removing beta × BTC | the coin's **own** move; the basis for own-story theses | NULL in `feat_price`; live in `feat_cross` |
| `session_bucket` | which session the bar belongs to | time reading (chapter 9) | — |

## B. Volatility — `feat_volat` (4.78M rows) and `feat_vol` (0 rows)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `rv_24h, rv_7d, rv_30d` | realised vol over the window, annualised (√365) | daily move = rv / √365; stop band; regime | raw (total) vol; use `idio_vol` for stops on own-story coins |
| `parkinson, garman_klass, rogers_satchell, yang_zhang` | range-based vol estimators (use high/low/open/close) | more efficient than close-to-close; same reading | sensitive to bad wicks |
| `bipower, jump_frac` | vol split into continuous vs jump part; share of variance from jumps | "is this coin's vol made of gaps" (news-driven) | needs intraday bars |
| `atr_14, atr_pct` | average true range, absolute and % of price | stop distance in the trader's usual unit | same thing as daily move, differently averaged |
| `ewma_vol` | exponentially weighted vol | reacts faster than rv_30d | can overreact to one day |
| `vol_of_vol` | how unstable vol itself is | regime-change warning | — |
| `realized_skew, realized_kurt` | asymmetry and fat tails of recent returns | "does it crash or melt up" | noisy on short windows |
| `semi_vol_up, semi_vol_down, ud_vol_ratio` | vol of up moves vs down moves | crash-prone (down > up) vs squeeze-prone | — |
| `vol_ratio_7_30, vol_pctile_1y, vol_zscore` | short vs long vol; vol vs its own year; vol surprise | "vol is expanding / compressing"; breakouts follow compression (chapter 5 §indicators) | direction unknown |
| `feat_vol.*` (garch_fc, har_fc, bb_width …) | forecast vols, band widths | forecasts | **0 rows** |

## C. Trend — `feat_trend` (4.78M rows)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `sma_5…sma_200, ema_9…ema_200` | moving averages | trend direction and distance from it (`px_vs_sma50`, `px_vs_sma200`) | lag; all trend tools are late |
| `macd, macd_signal, macd_hist` | difference of two EMAs and its smoothing | momentum turning | whipsaws in ranges |
| `adx_14, di_plus, di_minus` | trend strength (ADX) and direction (DI) | ADX > 25 = trending; RSI extremes mean less in a trend | — |
| `aroon_up/down/osc` | bars since the high/low | trend age | — |
| `psar, supertrend, chandelier_exit` | trailing-stop style trend lines | where a trend-follower's stop sits (liquidation/stop clusters) | — |
| `linreg_slope, hurst` | slope of a fitted line; persistence exponent (0.5 = random walk, > 0.5 trending) | trend vs mean-reversion regime | hurst needs long windows |
| `donchian_hi/lo/mid` | highest high / lowest low of the window | breakout levels | — |
| `ich_*` | Ichimoku lines | popular retail levels | — |
| `golden_cross` | sma_50 crossed above sma_200 | narrative-level trend flag | very late |

## D. Oscillators — `feat_osc` (4.78M rows)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `rsi_7, rsi_14, rsi_21` | speed of recent gains vs losses, 0–100 | overbought/oversold **in ranges**; > 70 in a strong trend is momentum, not a sell | fails in trends |
| `stoch_k, stoch_d, stoch_rsi, williams_r` | close within the recent range | same reading, faster | same limit |
| `cci_20, roc_5/10/20, momentum_10, chande_mom, tsi, ultimate_osc, kst, coppock, awesome_osc, fisher_transform, trix` | alternative momentum/rate-of-change measures | confirmation between two of them; divergence vs price | all of them are the same information reshaped; never stack five as five facts |

## E. Bands — `feat_bands` (4.78M rows)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `bb_upper/mid/lower, bb_width, bb_pctb` | mean ± 2 sd; band width; where price sits in the band | width at a multi-month low precedes expansion (direction unknown); %b > 1 = outside the band | — |
| `keltner_up/lo/width, atr_band_up/lo` | ATR-based bands | same, different scale | — |
| `squeeze_flag` | Bollinger inside Keltner | compression | direction unknown |

## F. Volume and flow — `feat_vol_flow` (4.78M rows) and `feat_flow` (26.7k rows, daily)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `vol_sma_20, vol_zscore, vol_surprise, volume_rsi` | volume vs its own norm | "is this move on volume" | volume can be wash-traded on some venues |
| `vwap_24h, vwap_dev` | volume-weighted average price and distance from it | institutional benchmark; below VWAP on rising volume = sellers in control | intraday tool |
| `obv, ad_line, pvt, cmf, mfi_14, force_index, eom` | volume signed by price direction, cumulated or smoothed | accumulation/distribution divergence vs price | proxies for CVD when no tape |
| `cvd, taker_imbalance` | cumulative taker buys − sells; taker imbalance | **who is aggressive** (chapter 5) | needs the trade tape; daily only today |
| `trade_count, avg_trade_size` | number and size of trades | retail (many small) vs large flow | — |
| `credible_vol_usd, fringe_vol_share, hhi, n_eff, hl_vol_share` | volume on credible venues; share on fringe venues; venue concentration; Hyperliquid's share | how real the volume is; where price discovery happens | — |

## G. Liquidity — `feat_liq` (26.7k rows, daily)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `spread_bps, spread_z, spread_eff_bps, spread_hl_rel` | quoted/effective spread; vs its norm; vs other venues | cost per side (the desk charges half the spread each side); a widening spread = stress | — |
| `roll, corwin_schultz, abdi_ranaldo` | spread estimated from prices alone | when no book data | rough |
| `amihud_log, impact_proxy, kyle_lambda_proxy` (micro) | price move per $ traded | how much your size moves price; thin coins | — |
| `depth_tob_usd, depth_5spread_usd, depth_2pct_usd, slippage_bps_1k, slippage_bps_10k` | resting size near the top; slippage for a $1k / $10k order | can the trade be done at all at this size | book snapshots |
| `turnover, adv_7d, adv_30d` | volume ÷ market cap; average daily volume | sizing cap (capacity) | — |
| `spread_widen_breadth` | share of coins whose spread widened | market-wide stress | — |

## H. Derivatives and crowd — `feat_deriv` (26.7k rows, daily)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `funding, funding_z, funding_expected, funding_gap` | funding rate; vs its own history; the interest baseline; gap to it | crowd side and cost of carry (chapter 5) | sign convention: positive = longs pay |
| `funding_carry_7d` | funding a long would pay over 7 days | the carry a thesis must beat | **[measured]** Q5 ≈ 22 bps/week |
| `sp_basis_bps, perp_basis_bps, hl_basis_resid` | perp − spot gap; Hyperliquid's gap vs other venues | crowd on this venue specifically | basis is the gap, funding is the payment |
| `oi_usd, oi_chg_1d, oi_price_regime` | open interest; its change; the price×OI cell (new longs / new shorts / covering / closing) | who is opening and who is closing (chapter 5 table) | OI is always 50/50 |
| `liq_vol_1h, liq_cluster_score, cascade_fragility` | liquidations; nearby liquidation density; OI-growth × funding × liquidation intensity | forced-flow risk; cascade wake-up | columns exist, mostly NULL today |
| `long_frac, ls_ratio, top_long_frac, top_ls_ratio, top_minus_retail` | account-level long share (all / top traders); the gap between them | one-sided crowd; top-trader dollars beat retail counts | counts, not dollars, for the retail series |

## I. Cross-venue — `feat_xvenue` (26.7k rows)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `n_venues, n_stale` | venues quoting; stale feeds | data quality | — |
| `disp_iqr_bps, disp_z, hl_dev_bps, prem_ma_bps, prem_resid_bps` | dispersion of prices across venues; Hyperliquid's deviation and premium | a local squeeze on one venue; arbitrage stress | — |
| `premium_krw_bps, premium_inr_bps, kimchi_breadth` | Korean / Indian premium; share of coins at a premium | regional retail demand (Korea is a real one) | — |

## J. Cross-section — `feat_cross` (192k rows, daily, all coins) and `feat_xsec` (0 rows)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `beta_btc, beta_eth` | sensitivity to BTC / ETH (Vasicek-shrunk) | hedge size; "how much is BTC" (chapter 3) | unstable; shrunk on purpose |
| `corr_btc_30d, corr_btc_90d` | correlation to BTC over two windows | 30d ≪ 90d = trading idiosyncratically | — |
| `r2_btc` | share of variance explained by BTC | which kind of coin (chapter 3 table) | — |
| `resid_r_1d, resid_r_7d, resid_mom_7d_skip1` | own returns and own momentum | own-story theses; cross-sectional momentum net of BTC | — |
| `idio_vol` | own (residual) volatility | **the stop unit** | — |
| `rank_ret_1d, rank_ret_7d, rank_vol` | cross-sectional ranks | movers and vol leaders | — |
| `feat_xsec.cluster_id, sector_resid, rrg_x/y, corr_break_flag` | cluster membership, sector residual, rotation coordinates, correlation-break flag | book rules, rotation reading | **0 rows** in the table; clusters live in the xsec cache used by the desk |

## K. Risk — `feat_risk` (4.78M rows)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `drawdown, max_dd_30d, max_dd_1y, ulcer_index` | fall from peak, now and worst over windows | "how wounded is this coin"; overhead supply | — |
| `sharpe_30d, sortino_30d, calmar` | return per unit risk over the window | quality of a recent trend | 30 days is short |
| `var_95, cvar_95, tail_ratio` | 5% worst-day size; average of the worst 5%; right tail ÷ left tail | stress sizing | — |
| `autocorr_1, variance_ratio, entropy` | persistence of returns; random-walk test; unpredictability | trend vs mean-reversion regime | noisy |

## L. Candles — `feat_candle` (4.78M rows)
| column(s) | what it measures | use | limit |
|---|---|---|---|
| `body_pct, upper_wick_pct, lower_wick_pct, range_pct, close_loc` | bar anatomy: body, wicks, range, where the close sits | rejection (long wick) vs conviction (big body, close at extreme) | one bar is one bar |
| `gap_pct, inside_bar, outside_bar, doji, hi_lo_2d, n_up_bars_7d, consec_up` | gaps, compression/expansion bars, indecision, streaks | pattern context | folklore-level |

## M. Defined, not filled (0–2 rows) — do not expect these in tool results yet
| table | columns | would measure |
|---|---|---|
| `feat_micro` | microprice, book_imbalance, ofi, trade_sign_imb, vpin, sweep/absorption flags, refill_rate | order-book pressure |
| `feat_options` (2 rows) | atm_iv_7d/30d/90d, rr_25d, bf_25d, skew, term_ratio, vrp, put_call_ratio, max_pain, gex, vanna, charm, iv_rank/pctile | what options traders expect; dealer positioning |
| `feat_onchain` | exch_netflow_usd, stablecoin_supply, tvl_usd, active_addresses, whale_net_pos/flip | slow on-chain flows |
| `feat_regime` | vol/trend/funding/liq regime labels, hmm_state, stress_score, breadth, btc_dominance | regime in one line (the `regime` tool computes a version of this live) |
| `feat_calendar` | days_to_next_event, next_event_kind, in_fed_blackout, collision_flag, expected_funding_through_event, hist_move_median/n | the calendar as features (the `calendar` tool computes this live) |

## Reading a coin from its features, in order
1. **What kind of coin** — `r2_btc`, `beta_btc`, `idio_vol`, cluster (chapter 3/6).
2. **Where the crowd is** — `funding_z`, `oi_price_regime`, `long_frac`/`top_long_frac`, `cvd` (chapter 5).
3. **How big a normal day is** — `idio_vol`, `atr_pct`, `vol_pctile_1y` (chapter 7).
4. **Has it already moved** — `r_7d`, `mom_7d_skip1`, `resid_r_7d`, `ret_zscore`.
5. **Can it be traded** — `spread_bps`, `slippage_bps_1k`, `adv_7d`.
6. **What is on the clock** — calendar tool (chapter 9), `funding_carry_7d`.
Everything else is confirmation or colour. Five oscillators agreeing is one fact, not five.

## Sources
- `data/store.db` schema (21 `feat_*` tables, 323 columns, row counts as of 2026-09-17); `scripts/build_features.py`; `sim/xsec.py`; `sim/tools.py`.
- Standard definitions of the indicators are textbook (e.g. Wilder's RSI/ATR/ADX, Bollinger, Ichimoku); their limits as stated in chapter 5 §indicators and the CryptoCred guide — https://www.bitget.com/news/detail/12560603860656
