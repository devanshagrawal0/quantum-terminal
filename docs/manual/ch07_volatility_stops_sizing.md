# Chapter 7 — Volatility, stops and sizing: the coin's own move is the unit

Everything about a trade's shape is measured in one unit: **the coin's own typical daily
move**. Stops, targets, hold time and size all come from it. The engine computes it and
prints it on every candidate row (`own_daily_move_pct`); you copy it. This chapter is what
the numbers mean and why the desk's bands are where they are. **[measured in our store]**
marks our data; **[our desk]** marks a rule in `sim/risk.py`.

## 1. What it is

| term | meaning |
|---|---|
| **Realised volatility (rv)** | standard deviation of daily returns over a window (7d, 30d), annualised with **√365** — crypto trades every day. rv_7d 95% → daily move 95 / √365 = **4.97%** (with √252 you would get 5.98%, wrong). |
| **Own (residual, idiosyncratic) daily move** | daily volatility of the coin's return after removing beta × BTC. This is what your stop must survive when your thesis is about the coin. **[measured]** median idiosyncratic vol share **0.84** — for most coins most of the noise is their own. |
| **Noise stop vs thesis stop** | a stop inside one daily move is hit by ordinary noise on a random day; a stop at 1.5–3 moves is hit when the coin is going against you for a reason. |
| **Target in moves** | how many own daily moves the trade needs to pay. A 2-move target needs, on average, about (2)² = 4 days of random walk to be reachable; 3 moves ≈ 9 days; 4 moves ≈ 14. |
| **Vol targeting** | size ∝ 1 / volatility so each position carries the same risk. Robust evidence it improves risk-adjusted returns and tail behaviour [source: Moreira & Muir 2017, "Volatility-Managed Portfolios", J. Finance 72(4), via `D:\crypto trading\quant project\06-risk-portfolio-backtesting\02-position-sizing-money-management.md`]. |
| **Kelly fraction** | the bankroll fraction that maximises long-run growth for a bet with win probability p and payoff ratio b (win b per 1 risked): **f\* = p − (1−p)/b** [source: Kelly 1956, via the same library file]. Full Kelly assumes your p and b are exactly right — they never are; half-Kelly captures ~75% of the growth with about half the volatility, and practitioners use ¼ to ½ Kelly [same source]. **[our desk]** uses quarter-Kelly. |
| **MFE / MAE** | best and worst point reached during the trade, in bps. Logged on every closed trade; the review reads them to judge stop and target placement. |

## 2. Why it matters (the economics)

A stop is a bet that "price here means I am wrong". If the stop sits inside the coin's
normal daily wobble, price reaches it for no reason on a coin flip, and you pay the round
trip (≈ 12–15 bps) plus the loss for nothing. A wider stop costs more per loss but is hit
only when something real happened. The desk's band, 1.5–3 own moves, is where the stop
starts to mean something without giving away the whole target.

The target must be far enough to pay for the stop and the costs: at least 2 own moves and
at least 1.5 × the stop **[our desk]**. And it must be reachable inside the hold: random
walks cover distance ∝ √time, so a target of k moves needs about k² days. A 3-move target
with a 2-day hold is a wish, not a plan — the engine sets the hold from the target for this
reason.

Size follows from p and the stop/target ratio (Kelly), then from volatility (vol target),
then from the book (chapter 6), then from the brakes. Sizing is the one lever that cannot
turn a bad trade good but can turn a good record into ruin: a 50% loss needs a 100% gain to
recover; volatility is a tax on compounding (g ≈ μ − σ²/2) [source: library file above].

**[measured in our store]** the model, when asked to set its own stops, put 0.55× daily
moves on coins with the vol printed in front of it (`docs/HOW_IT_WORKS_2026-09-16.md` §9),
and a 5% stop on ACE (17.6%/day own move) was 0.3 of one move. That is why the engine
prints the band and the desk bounces anything outside it.

## 3. Reading rules

### 3a. The plan bands **[our desk]**
| item | rule | why |
|---|---|---|
| stop | 1.5 – 3.0 own daily moves | below 1.5 = noise; above 3 = the target cannot pay for it |
| target | ≥ 2 own moves **and** ≥ 1.5 × stop | pays for costs and for the stop's hit rate |
| hold | engine-set: ceil((target / move)²) days, max 14 | the time the target needs; never a violation |
| falsifier | correct side, **smaller than the stop**, with a day | thesis death must fire before the stop does |
| size | quarter-Kelly × vol scale × brakes, 0.25–1.0 of the $100 unit | edge → vol → book → brakes, in that order |

### 3b. Kelly, as the desk computes it
kelly_scale = clip( (2p − 1) × (stop / target) × 4, 0, 1 ) — a quarter-Kelly for a
stop/target bet, where p is **p_final** (the stated confidence shrunk toward your own win
rate on that side, then mapped through the calibration table). Read the result, don't
recompute it.
| p_final | stop:target 1:2 | 1:1.5 |
|---|---|---|
| 0.52 | 0.08 | 0.11 |
| 0.58 | 0.32 | 0.43 |
| 0.65 | 0.60 | 0.80 |
| ≤ 0.50 | 0 → rejected ("no edge") | 0 |

### 3c. Vol scale
vol_scale = clip( 12% / annualised own vol, 0.25, 1 ). A coin at 100%/yr own vol gets 0.25×;
a coin at 12% or less gets 1×. **[measured]** most of the universe sits at 60–150% own vol,
so most positions run at 0.25–0.5 of the unit — that is intended.

### 3d. Brakes **[our desk]**
| brake | trigger | effect |
|---|---|---|
| CVaR | today is in the worst 1% of the book's own daily history | sizes × 0.5 for 5 days |
| drawdown | $ from peak > 15% of risk capital ($2,000) | no new trades |
| day loss | today's $ loss > 3% of risk capital | no new trades |
| repeat after a loss | same coin, same side, lost within 7 days | needs p ≥ 0.65 |

### 3e. Reading a closed trade's MFE / MAE
| pattern | reading | next time |
|---|---|---|
| exit = stop, MFE ≥ target | the target was reached and given back: a noise-stop **after** the move — take-profit logic or a checkpoint, not a wider stop | trail after the checkpoint hits |
| exit = stop, MFE small | thesis never worked | the entry read was wrong; look at the loss class |
| exit = time, MFE ≥ 0.7 × target | too little time or too big a target | one fewer move, or one more hold day |
| exit = target, path went past it | left money | a 3-move target on this setup |
| MAE > 1 move before the win | it nearly stopped out | stop was right at 1.5–2; do not tighten |

## 4. Worked example

Candidate C57: own daily move **6.2%**, stated confidence 0.60, own win rate on longs 0.55
over 12 trades.
- stop band: 1.5–3 × 6.2% = **9.3%–18.6%** → choose 0.10 (10%).
- target: ≥ 2 × 6.2% = 12.4% and ≥ 1.5 × 10% = 15% → **0.155**. In moves: 2.5.
- hold: ceil(2.5²) = **7 days** (engine sets it).
- falsifier: long → negative, inside the stop: day 2, **−0.06** (60% of the stop).
- p_final: shrink k = 12/(12+10) = 0.55 → 0.45 × 0.60 + 0.55 × 0.55 = 0.572; calibration
  bucket 0.55–0.70 (n ≥ 10) maps to the bucket's real win rate, say 0.58.
- kelly_scale = (2 × 0.58 − 1) × (0.10/0.155) × 4 = 0.16 × 0.645 × 4 = **0.41**.
- own vol annualised = 6.2% × √365 = 118% → vol_scale = 12/118 = 0.10 → clipped to **0.25**.
- size = 0.41 × 0.25 = **0.10** of the unit → **$10 notional**. Risk at the stop = $1.
That is small on purpose: a 118%-vol coin with a 0.58 edge deserves a small ticket. If
that looks pointless, the answer is a better p or a calmer coin, not a bigger size.

## 5. Common misreads

1. **√252.** Crypto: √365. Every daily-move figure is ~20% off otherwise.
2. **Kelly wrong.** f\* = p − (1−p)/b with b = target/stop. p 0.58, b 2/1.5 = 1.33 →
   0.58 − 0.42/1.33 = **0.265**, not 0.125. Then quarter it. Or just read the desk's number.
3. **A stop at a "level".** Levels are fine only if they also sit at 1.5–3 own moves;
   otherwise the level is inside the noise.
4. **Tightening a stop because the coin is volatile.** Backwards: the stop widens with the
   vol; the **size** shrinks.
5. **A 2-day hold for a 3-move target.** Needs ~9 days. The engine will set it; plan for it.
6. **Full size on the highest-vol coin.** vol_scale is 0.25 there; the trade is a quarter
   ticket by design.
7. **Reading MFE as "should have held longer".** Only if the exit was stop/time *and* MFE
   was at or past the target; otherwise the plan was fine and the coin was not.

## 6. Sources
- Kelly (1956), fractional Kelly, vol targeting, volatility drag — `D:\crypto trading\quant project\06-risk-portfolio-backtesting\02-position-sizing-money-management.md` (cites Kelly 1956 Bell Syst. Tech. J.; Moreira & Muir 2017 J. Finance 72(4); Thorp).
- Our desk rules and formulas: `sim/risk.py` (STOP_MIN/MAX, TARGET_MIN_MOVES, hold, quarter-Kelly, VOL_TARGET_PCT, brakes).
- Our measurements: `docs/MEASURED_LINKS_2026-09-16.md` §1 (idio vol share 0.84, ACE 17.6%/day); `docs/HOW_IT_WORKS_2026-09-16.md` §9 (the 0.55×-move stops).
- Stop placement in ATR/vol units rather than at the swing level — https://fortraders.com/blog/trade-entry-exit-checklist
