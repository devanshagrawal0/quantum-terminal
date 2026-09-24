# Prediction Test — 2026-08-25 (1–2 day horizon)

**Pre-registered.** Written and the bets placed (hashed in `paper.db`, tag `pred_test`)
BEFORE the outcome exists. Graded 2026-08-26 / 08-27. The point is an honest test of the
**fused pipeline** — quant signal + deep news/catalyst + **what top traders are doing** +
**how the crowd is positioned on the big platforms** — on a SHORT (tomorrow / day-after)
horizon, which is exactly the horizon our own backtests said the *mechanical* score has no
edge on (L9/L11). So this is a test of the *reasoning*, not the quant, and it can fail.

Method = the 10-step pipeline (`PIPELINE.md`): regime → catalyst → deep research →
priced? → crowd positioning → character → momentum/vol timing → pre-mortem → fit → log.
Universe = top 40 Hyperliquid perps by 24h volume.

---

## Step 1 — Market regime (the tape everything hangs on)

- **BTC $79.6k, +3.1% today, +25% on the week**, tapped $81k this morning then faded.
  Highest open in 3 months. Driver: **spot-BTC-ETF inflows $1.92B (strongest in 10 months)**
  + Treasury bond-buyback liquidity + regulatory optimism (White House / Coinbase / Robinhood).
- **BUT the melt-up is maturing:** on 08-24 **long liquidations ($30.85M) outpaced shorts
  ($16M)** — the short-squeeze fuel that drove $65k→$80k is spent; the move is now
  long-crowded. Polymarket prices only a **1% chance of $100k by month-end**. StanChart sees
  $100k by year-end (not days).
- **Read:** don't fight the up-tape with size (L7), but it's tiring and long-heavy, so a
  1–2 day pullback is a live risk. Favour catalyst-backed momentum longs + fade names with a
  *concrete* bearish catalyst; avoid pure "overbought" shorts (that's what burned us, L11).

## Step 3 — What the top traders are doing (new input)

- **Arthur Hayes / Maelstrom at "maximum risk": BTC, ETH, ENA, ETH.fi (ETHFI).** Core is
  **ETH**. Bought ~25M **ENA** at $0.08–0.09 into its Aug-5 unlock. **HYPE $150 target** (long-term).
  Thesis: Treasury defending the 5% yield ceiling = sustained dollar liquidity = crypto up.
- **Caveat (honest):** Hayes-linked wallets have repeatedly bought narratives *late* and
  exited early — a confirmation input, not a signal to blindly copy. So: ETH/ETHFI get a
  mild long lean from this; ENA is already +90% and late; HYPE we *fade the unlock* despite
  his long-term bull.

## Step 5 — How the crowd is positioned (big-platform data)

Coinglass aggregates 30+ exchanges (Binance/OKX/Bybit): funding = long/short cost balance;
**top-trader L/S ratio** = net lean of the top-20%-by-margin accounts. Our own `positioning`
feed (Binance) gives the same per coin. The standouts:

- **Crowd heavily LONG** (crowded, pullback-exposed): DOGE (73%, L/S 3.90), LTC (72%), MON
  (72%, 3.59), BNB (70%), ETH/XRP (71%), TAO (3.92), XPL (**4.57**), LIT (4.04), ZRO (3.58).
- **Contrarian — crowd SHORT / top-traders short** (squeeze-up fuel): **ZEC (33% long, L/S
  0.97)**, **XMR (L/S 0.66)**, **VVV (L/S 0.63 despite +110%/yr funding)**.
- Funding mostly normal (~+11%/yr); extremes: **VVV +110%**, XMR +34%, CASHCAT +27%,
  TRUMP −33% (shorts paying), ADA −6%.

---

## The bets (placed, tag `pred_test`, directional, unhedged, 24–48h)

| # | Coin | Side | Entry | Stop | Target | Hold | Conviction | The fused thesis |
|---|------|------|-------|------|--------|------|-----------|------------------|
| 1 | **HYPE** | SHORT | 81.37 | 86.25 | 74.86 | 48h | high | **$1.2B unlock Aug 29** (46.6% to insiders) into ATH $83 + crowded long. Scheduled-cliff fade. Hayes bull long-term, but supply hits first. |
| 2 | **XMR** | LONG | 447.9 | 416.6 | 488.2 | 48h | med-high | Whale $14.3M **4× long** (TP 475–516) + supply squeeze (delisted 73 exch) + **top-traders short** (L/S 0.66) = squeeze fuel; cup-handle→427. |
| 3 | **ZEC** | LONG | 829.9 | 755.2 | 921.1 | 30h | med (small) | **Grayscale ETF ZCSH live TODAY** on NYSE Arca + **crowd SHORT** (33%) = squeeze. Frothy after +47% to 8yr-high, futures 9.5× spot → tight/small. |
| 4 | **VVV** | SHORT | 18.12 | 19.93 | 16.31 | 48h | spec (small) | Funding **+110%/yr** extreme crowded-long paying, yet top-traders SHORT + no catalyst. Extreme-funding fade (the one measured HL edge). Thin. |
| 5 | **ETH** | LONG | 2478 | 2354 | 2652 | 48h | med | Hayes **core**, Glamsterdam upgrade Q3 + ETF staking, rotation leader. Crowded (71%) so moderate. |
| 6 | **ETHFI** | LONG | 0.595 | 0.548 | 0.655 | 48h | med | On Hayes' max-risk list, ETH-staking rotation beneficiary. Crowded (L/S 3.05) so moderate. |

Net: 2 shorts (both catalyst-backed, not vibe), 4 longs. Deliberately no pure "overbought"
short (that's L11's graveyard). These are **unhedged directional** bets — this test predicts
the actual move, unlike the market-neutral fused book.

## 40-coin directional leans (the full pre-registered call)

LONG-lean: ETH, ETHFI, XMR, ZEC, ADA (−6% funding = shorts paying), ONDO (RWA), TAO (AI,
crowded), AAVE. SHORT-lean: HYPE (unlock), VVV (funding), TRUMP (unlock+SEC), and the
most-crowded-no-catalyst names are pullback-exposed (DOGE/XPL/LIT/MON/ZRO) though we don't
short them into the up-tape. FLAT/no-edge: BTC (priced, +25% wk), SOL/XRP/BNB/SUI/NEAR/LINK/
UNI/CRV/AERO/LTC/INJ/AVAX/WLD/PENGU/FARTCOIN/kPEPE/PURR/ASTER/CASHCAT/VIRTUAL/JTO/ZRO,
ENA (real catalyst but already +90%, chasing).

## How it's graded

Each bet auto-closes on stop/target/time at the live HL price (fees both ways). On
2026-08-26/27 we read: how many hit target vs stop, and the BTC-neutral move on each. The
question this answers: **does fusing top-trader + crowd-positioning + catalyst reasoning
beat noise on a 1–2 day horizon** — where the pure quant score demonstrably does not.

**Sources:** Yahoo/Fortune (BTC 08-25), CoinDesk/crypto.news (liquidations), CoinGlass
(long/short, funding), Arkham/CoinCodex/Stocktwits (Hayes/Maelstrom holdings), news.bitcoin.com
/cryptotimes (ZEC ETF), Decrypt/tokenomist (HYPE unlock), coinpedia (XMR whale), crypto-economy
(ETH rotation).
