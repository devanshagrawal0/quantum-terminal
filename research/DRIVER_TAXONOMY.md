# DRIVER TAXONOMY — Quantified Price Drivers

**Purpose:** for every factor that moves an asset's price, answer *how much*, *which way*, *over what horizon*, *how fast it is priced in*, *can we compute it*, *is it already crowded*, and *where do we get the data free*.

**Scope note:** this document is **depth per driver**, not breadth of the world. A separate map covers geography/law/calendar breadth. Everything here is about magnitude, sign, horizon, and decay.

**Date of compilation:** 2026-09-02. Numbers are from published studies unless marked. Where a number is practitioner-sourced or I could not verify it, it says so explicitly. **Do not treat unmarked practitioner claims as evidence.**

---

## 0. Conventions used in every table

**Speed-of-pricing-in scale** (how long an edge survives after the information is public):

| Code | Meaning | Implication for us |
|---|---|---|
| **S0** | < 1 second | HFT-only. Dead to us. Do not build. |
| **S1** | seconds → ~30 min | Needs colocated/low-latency feeds. Mostly dead to us. |
| **S2** | hours → 1 session | Reachable if we are already positioned and automated. |
| **S3** | 1–10 trading days | The sweet spot for an automated small operator. |
| **S4** | 2–12 weeks | Sweet spot; lowest turnover, survives costs best. |
| **S5** | months / persistent risk premium | Not an "edge", a *compensation*. Size it as beta, not alpha. |

**Direction convention:** sign is for the *long* side of the named condition (e.g. "positive surprise → +"). "Flips when" lists the known regime that reverses the sign — these flips are where most naive systems lose money.

**Measurability tiers:**
- **M1** — computable exactly from free public data, deterministic.
- **M2** — computable from free data but needs estimation/modelling choices (surprise definitions, expected-return model).
- **M3** — needs paid data, or a proxy that is materially noisier than the real thing.

**Magnitude convention:** "CAR" = cumulative abnormal return (market/factor-model adjusted). bps = 0.01%.

---

## 1. COMPANY

| Factor | Direction | Typical Size | Horizon | Speed priced-in | Measurable from | Decayed/Crowded? | Free source |
|---|---|---|---|---|---|---|---|
| Earnings surprise (immediate reaction) | + with SUE sign | Large-cap 3-day CAR roughly linear in SUE; the *reaction* is now the whole move | Minutes | **S1** — after-hours discovery is near-efficient: 2008–2015 a 10s delay still left ~0.80%/trade; 2016–2020 that return is small/insignificant once spreads are paid | 8-K Item 2.02, XBRL EPS vs consensus | Fully arbitraged in large caps | SEC EDGAR `data.sec.gov`, 8-K feed |
| **PEAD (post-earnings drift)** | + with SUE sign | Bernard–Thomas (1990): extreme-SUE decile hedge ≈ **8–9% per quarter**. Today: **~0 for large caps since ~2006** (Martineau 2022); still **>2% over 60 days** in extreme deciles for small/mid caps with low analyst coverage | 20–60 trading days | **S3–S4** | SUE from EDGAR + IBES-substitute (analyst consensus is the hard part on free data) | **Heavily decayed and heavily crowded in liquid names. Alive only in the illiquid tail.** | EDGAR XBRL `companyconcept`; consensus is the paid gap |
| Guidance (forward outlook) | Sign of guide, dominates the print | "Beat and lower-guide" is routinely net-negative; forward-looking content adds explanatory power *after* controlling for the surprise | Same session + 1–4 days | **S1–S2** | 8-K exhibit text / call transcript NLP | Not a factor, an *input*. Not crowded as a nuance signal | 8-K exhibits; call audio is often free on IR sites |
| Pre-open vs after-hours announcement timing | n/a (modifier) | Pre-open announcements show **36% weaker initial reaction** and **greater 4-day drift** than after-hours ones | 1–4 days | **S2–S3** | Filing timestamp on 8-K (`acceptanceDatetime`) | Under-exploited; free to compute | EDGAR filing index timestamps |
| Buyback announcement | + | Announcement CAR **+2.9% to +3.5%** (Ikenberry 1995). 4-year BHAR **+12.1%**; value-side **+45.3%**, glamour-side **≈0** | Days → 4 years | **S3** for the pop; **S5** for the drift | 8-K / press release + 10-Q share count | Announcement pop is efficient. **Long-run drift is materially lower for post-2001 announcements** | EDGAR 8-K, 10-Q cover-page share counts |
| Actual buyback *execution* (not announcement) | + (price support) | Not cleanly quantified in free data; execution is disclosed only quarterly (10-Q Item 5 table) | Weeks | **S4** | 10-Q monthly repurchase table (lagged) | Under-used because it is lagged and tabular | EDGAR 10-Q |
| Dividend initiation | + | 12-month market-adjusted **+7.5%**; documented drift **+5.84%** confined to ~1 year (Michaely–Thaler–Womack) | 12 months | **S5** | 8-K / dividend declaration | Old result; expect substantial decay | EDGAR, Nasdaq dividend calendar |
| Dividend omission/cut | − | 12-month market-adjusted **−11.0%**; 3-day CAR negative in **80%** of cases | Days → 12 months | **S3 → S5** | Declaration absence + history | Asymmetry (cuts >> initiations) is robust and persists | EDGAR |
| Stock split | + | Announcement **+3.38%**; 1-yr drift **+7.93%**; 3-yr **+12.15%** (Ikenberry–Rankine–Stice, 1975–1990) | Days → 3 years | **S3 → S5** | 8-K, corporate action feed | **Old sample, drift concentrated in announcement→effective window; treat as largely decayed** | EDGAR, exchange corp-action files |
| Insider buying (Form 4, open-market) | + | Lakonishok–Lee: heaviest-buy decile beats lightest **~5% / 12mo**, concentrated in small firms (**~7.4%** abnormal for small caps). Cohen–Malloy–Pomorski: **opportunistic** insiders **+82 bps/month (~10%/yr)**; **routine** insiders **zero** | 1–12 months, **front-loaded in first 21–60 trading days** | **S3–S4** | Form 4 XML: transaction code `P`, price, share count, role, plus 2-year history to classify routine vs opportunistic | Known but **not fully arbitraged in microcaps**; the routine/opportunistic split is the part most systems skip | **EDGAR Form 4 XML — free, real-time, structured. One of the best free edges available.** |
| Insider selling | − but very weak | Much weaker than buying (10b5-1 plans, diversification, tax). Form 144 vs Form 4 reporting asymmetry masks intent | Months | **S4** | Form 4 code `S` + `F` (tax withholding — exclude), 10b5-1 checkbox | Low signal; most sells are noise | EDGAR Form 4 (10b5-1 flag exists in modern XML) |
| Management change (CEO turnover) | Ambiguous — **sign genuinely flips** | Evidence conflicts: one 426-firm 1995–2015 sample finds forced turnover CAR **−1.78% to −2.93%**; other samples find forced turnover *positive* (~+0.5% France/US). Consistent finding: **equity volatility rises**, more after forced departures | Days; vol effect persists months | **S2** | 8-K Item 5.02 | Not tradeable directionally. **Tradeable as a volatility signal** | EDGAR 8-K 5.02 |
| Product launch / event | Usually "sell the news" | No reliable published magnitude. Anticipation is priced; realization is often negative | Days | **S2** | Event calendars | Weak, narrative-driven | Company IR pages |
| **M&A — target** | **+, very large** | 3-day CAR typically **+15% to +30%** (one large sample: **+14.12%**). Premium **+2.20–2.25 pp** higher per 1 SD of industry takeover competition | Instant, then deal-spread grind to close | **S0/S1 at announcement; S4–S5 for merger-arb spread** | 8-K, SC 14D9, DEFM14A | Announcement gap is uncatchable. **Merger arb spread is a crowded but real risk premium** | EDGAR |
| **M&A — pre-announcement run-up** | + | **~40% of the eventual takeover premium** appears as pre-announcement run-up; target avg **+32.5%** over the 30 days before announcement; leakage detectable up to **12 trading days** prior (Keown–Pinkerton) | 12–30 days pre-event | **S4 (anticipatory)** | Abnormal volume + abnormal option volume + short-dated OTM call skew | This is where the money is, and it is genuinely hard. Not crowded because it needs *prediction*, not reaction | Options volume (Cboe delayed), volume from any price feed |
| **M&A — acquirer** | − (mildly) | Average **−0.58%**; stock-financed deals **2–5 pp worse** 3-day CAR than cash deals; acquirers of *public* targets significantly negative, of private/subsidiary targets not | 3 days | **S1** | 8-K + consideration type parsed from press release | Well-known; the cash-vs-stock split is the durable part | EDGAR |
| Lawsuits / securities class action | − | 3-day CAR around filing **≈ −3.5%**; when a law-firm investigation was announced first, the **10-day pre-filing CAR ≈ −17%**; around the class *end* date **≈ −25%** | Days | **S2** — but the investigation announcement front-runs the filing by a median of ~9 days | Stanford SCAC database, 8-K Item 8.01 | The **investigation → filing gap (median 9 days)** is the exploitable structure | securities.stanford.edu (free) |
| Credit rating downgrade | − | **−2.66%** average announcement return (Holthausen–Leftwich 1986). Magnitude scales with notches and with crossing IG/HY boundary | Days | **S2** | Agency press releases; 8-K Item 8.01 | Old but the **asymmetry survives** | Agency sites; EDGAR 8-K |
| Credit rating upgrade | ~0 | **No significant positive abnormal return** in most studies (Hand–Holthausen–Leftwich; Dichev–Piotroski) | — | — | — | **Do not trade upgrades long.** The asymmetry is the finding | — |
| Dilution / secondary offering (SEO) | − | 2-day announcement CAR from **−0.82%** (broad modern samples) to **−2.7%** (Asquith–Mullins) and **−3.25%** (Masulis–Korwar, industrials). 3-year post-issue underperformance for "general corporate purposes" issuers | Days → 3 years | **S2 → S5** | 424B5 / S-3 shelf takedown filings, ATM programs | Robust; the *use-of-proceeds language* is the un-crowded part | EDGAR 424B5, S-3ASR, prospectus text |
| IPO lockup expiry | − | **−1.5% 3-day abnormal return**, **permanent +40% volume increase**, **not reversed**, stable over a 10-year sample; much larger when VC-backed (Field–Hanka 2001) | 3–5 days around expiry, date known ~180 days ahead | **S3, fully anticipable** | S-1 lockup clause + IPO date | Well known; still works better in small/VC-heavy names because supply is real | EDGAR S-1/424B4 text |
| FDA / clinical readouts | ± , very large in small caps | Large biopharma: median day-0 CAR **+0.8%** (positive events), **−2.0%** (negative). **Early-stage biotechs earn +8.3% (day 0) and +11.0% (day 0–1) MORE than large pharma.** Final approval itself only **+0.35% day 0, +0.44% day 1** — approval is pre-priced; the *trial readout* is the event | Instant | **S0/S1 on the readout** | ClinicalTrials.gov phase/completion dates, openFDA PDUFA calendar | Binary; the *date prediction* (not the reaction) is the edge | ClinicalTrials.gov API, openFDA — both free |

**Company-section notes:**

- **The single most important structural fact:** for large caps, essentially every company factor above has moved from S3/S4 (drift you can trade) to S1 (reaction you cannot). Martineau's finding that PEAD went to zero for large caps by ~2006 is the template — decimalization, Reg NMS, and machine-readable filings killed the drift where the liquidity is. **What survives lives in small/micro caps and in low-analyst-coverage names.**
- **The routine-vs-opportunistic insider split is the best free, structured, still-alive company signal I found.** It requires only Form 4 XML and a 2-year lookback per insider, and the null result on routine traders is what makes the opportunistic 82 bps/month credible rather than data-mined.
- **Asymmetries are more durable than levels.** Downgrades move prices, upgrades do not. Dividend cuts move prices ~1.5× as much as initiations. Negative clinical events move more and longer than positive ones. Build the system to expect asymmetry rather than symmetric betas.

---

## 2. SECTOR / INDUSTRY

| Factor | Direction | Typical Size | Horizon | Speed priced-in | Measurable from | Decayed/Crowded? | Free source |
|---|---|---|---|---|---|---|---|
| Peer read-across on earnings (intra-industry information transfer) | + (same sign as announcer), except **rivals can be −** | Peer 3-day CAR ≈ **1.8% of the announcer's own CAR** (country-industry peers). Larger when announcer is big, when the surprise is large, and in high past-volatility regimes | Same 3-day window | **S1–S2** | Announcer CAR × peer set (SIC/GICS or revenue-similarity) | Large-cap-to-large-cap transfer is priced. **Large-announcer → small-peer transfer is not fully priced** | EDGAR SIC codes; free peer sets |
| Rival vs non-rival peers | **Sign flips** | Information transfer from **non-rival** peers is **positive**; from **rival** peers it is **negative** (share-shift) | 3 days | **S2** | Requires a competitive-overlap map, not just SIC | This distinction is why naive "sector peer" logic produces zero average alpha — the two signs cancel | 10-K Item 1 "Competition" text, product-market text similarity |
| **Supply chain propagation (customer → supplier)** | + (supplier follows customer shock) | Cohen–Frazzini: long/short customer-momentum **>150 bps/month alpha**, robust to 3-factor, liquidity, own momentum, industry momentum, and cross-industry momentum | **1 month** | **S4** | SEC Reg S-K major-customer disclosure (customers >10% of revenue) in 10-K | Published 2008, Smith Breeden winner → **expect meaningful post-publication decay** (McLean–Pontiff base rate: −58%). Still likely the best-motivated cross-firm link | **10-K Item 1 / Note "Concentration of credit risk" — free but requires text extraction. This is the highest-value hard-to-build free dataset.** |
| Industry / sector momentum | + historically | **Stopped working around 2000**; cumulative industry-momentum return ≈ **0 from 2000 to present** | — | — | Sector ETF returns | **DEAD. Do not build.** Note that *factor* momentum post-2000 is indistinguishable from pre-2000 — the death is specific to *industry* momentum | — |
| Business-cycle sector rotation | Direction claimed by phase | **The textbook rotation does not verify.** Industries expected to lead in early expansion **underperformed the market by 0.05%**; mid-expansion leaders also **−0.05%**. Risk-adjusted, the match to popular expectations is even worse | Months | n/a | Sector ETF returns vs NBER/ISM phase | **The popular version is a myth (Molchanov 2024).** Sector *betas* differ (early-cycle β>1, defensives β<1) — that is a beta story, not alpha | FRED for cycle indicators |
| Input costs (commodity pass-through) | − to margin, lagged | No single clean coefficient; sector-specific. Sign depends on whether the commodity move is demand-driven (see §3 oil) | Weeks–quarters | **S4** | COGS sensitivity from 10-K segment data + commodity series | Under-exploited but low signal-to-noise | FRED commodity series |
| Substitutes / complements | ± | Not quantified in general; only tractable pairwise (e.g. airlines vs jet fuel) | Days–weeks | **S3** | Hand-built pair map | Small, idiosyncratic edges | — |

**Sector notes:**

- **Sector rotation as usually taught is not supported by the data.** The Molchanov (2024) result — expected early-cycle leaders *underperform* by ~5 bps/month — is the single most important negative finding in this section. Do not build a rotation model on the standard phase→sector table.
- **What *is* alive in this section is the network, not the sector.** Customer-supplier links (Cohen–Frazzini, 150 bps/month) and the rival/non-rival distinction both work because they encode a real economic mechanism at a firm-pair level. GICS-bucket logic does not.
- Peers moving at **1.8% of the announcer's CAR** is a small number, but it is the *average across all peers*. Conditioning on (large announcer, small illiquid peer, big surprise) is where the exploitable version lives.

---

## 3. MACRO

| Factor | Direction | Typical Size | Horizon | Speed priced-in | Measurable from | Decayed/Crowded? | Free source |
|---|---|---|---|---|---|---|---|
| **Monetary policy surprise (FOMC)** | − for equities on hawkish surprise | **Bernanke–Kuttner: a surprise 25 bp CUT ≈ +1% on the CRSP value-weighted index.** Modern high-frequency estimate: a **100 bp surprise → −5.4% on the S&P 500 (t ≈ 8)** | 30-min window around 2:00pm ET / press conference | **S0–S1** | Fed funds futures (front contract) change across the announcement window | The *level* effect is textbook and fully priced. **Only the surprise's cross-sectional dispersion (duration-sensitive vs not) is left** | CME FedWatch (free, delayed); FRED `DFF`, `DFEDTARU` |
| **CPI print** | + for equities on downside inflation surprise (in a tightening regime) | 2021–2025, 48 releases: downside surprises produced abnormal returns averaging **+0.88%**, CAR **+1.16% to +1.19%**. **Asymmetric** — the reaction to soft prints was larger than to hot prints | 8:30am ET, mostly within the session | **S1** | BLS release vs consensus | Reaction speed is S1. **The asymmetry and the regime-dependence are the durable parts** | BLS API `api.bls.gov/publicAPI/v2`; FRED `CPIAUCSL`, `CPILFESL` |
| **Nonfarm payrolls** | **Sign flips by regime** — good news is bad news when the Fed is tightening, good news is good news when growth is the binding worry | 10y yield moves of **~7 bp** on ordinary surprise days, up to **~20 bp** on large ones. Equity sign is regime-conditional. Traders have reacted **more to employment than to CPI** over the last four years | 8:30am ET | **S1** | BLS release vs consensus | The **regime-conditional sign flip** is the whole game and is not "crowded" so much as *hard* | BLS API; FRED `PAYENS`/`PAYEMS`, `ICSA` (weekly claims) |
| Growth / GDP | + weakly | GDP is a lagging, revised, low-surprise release. Materially less market-moving than NFP or CPI | Minutes | **S1** | BEA release | Low value; use nowcasts instead | BEA API; Atlanta Fed GDPNow (free) |
| **Currency (USD)** | − for S&P EPS on USD strength | **Every 10% move in the trade-weighted dollar shifts S&P 500 aggregate earnings ~3–4% in the opposite direction.** Cross-sectionally: firms with <15% foreign revenue have minimal sensitivity; semis are the extreme (AMAT ~94%, LRCX ~92%, KLAC ~89% international revenue) | Quarters (earnings), days (sentiment) | **S3 for the cross-section** | 10-K geographic segment revenue vs DTWEXBGS | The index-level effect is known. **The firm-level foreign-revenue cross-section is computable free and under-used** | FRED `DTWEXBGS`; EDGAR segment XBRL |
| **Oil** | **Sign depends on shock type** | Kilian–Park decomposition: **aggregate-demand-driven oil ↑ → equities ↑**; **oil-market-specific demand shock → equities ↓**; **oil supply shocks → small/insignificant** for US equities | Days–weeks | **S2–S3** | Requires a structural decomposition (VAR with production, activity, inventories) | **The single most common macro modelling error is treating "oil up" as one signal.** Decomposition is the edge | FRED `DCOILWTICO`, EIA API (free), Kilian index |
| **Credit spreads / Excess Bond Premium** | − for equities on EBP widening | Gilchrist–Zakrajšek: the GZ spread has higher predictive power for activity than BAA-AAA. **EBP shocks orthogonal to the current state cause significant declines in consumption, investment, output, and equity prices** | Weeks–quarters | **S4–S5** | HY OAS as the free proxy; true EBP needs bond-level data | Widely watched. Still the best single risk-off state variable | FRED `BAMLH0A0HYM2` (HY OAS), `BAMLC0A0CM` — **daily, free** |
| Liquidity conditions (Fed net liquidity = WALCL − TGA − RRP) | + claimed | Level co-movement with the S&P during 2020–2022; a cited "stealth easing" window May 2023–Dec 2025 with S&P +64.6%. **This is a practitioner construct with an unstable correlation and no causal identification** | Weeks | n/a | WALCL − TGA − RRP | **Treat as narrative, not signal.** The relationship breaks in-sample repeatedly | FRED `WALCL`, `RRPONTSYD`, `WTREGEN` — free daily |
| VIX / implied vol level | Vol is a state variable, not a directional signal | Regime conditioner. Positive-gamma vs negative-gamma regimes (see §6) matter more than VIX level | Days | **S2** | Cboe | Fully priced as a level; useful only as a conditioner | Cboe daily VIX history (free CSV) |

**Macro notes:**

- **All headline macro reactions are S0/S1.** You will never beat the machines to the print. What you *can* do: (a) trade the **cross-section** of exposure to a known surprise over S2–S3 (dollar-sensitivity baskets, duration baskets), and (b) trade the **regime-conditional sign flip**, which is a modelling problem rather than a latency problem.
- **The good-news-is-bad-news flip on NFP/CPI is the highest-value macro modelling target.** It is not crowded because it requires correctly classifying the current regime (is the market worried about inflation or about growth?), which is exactly what a well-built state classifier can do and what a fixed beta cannot.
- **Do not build on Fed net liquidity.** I found no peer-reviewed identification behind it; the co-movement is level-on-level with the obvious confound (both trend).

---

## 4. POLICY / LEGAL / REGULATORY

| Factor | Direction | Typical Size | Horizon | Speed priced-in | Measurable from | Decayed/Crowded? | Free source |
|---|---|---|---|---|---|---|---|
| **Tariffs (large regime shift)** | − broad, **hugely dispersed cross-sectionally** | 2 Apr 2025 "Liberation Day": US total market **−12.4%**, S&P **−12%+ in a week**; global CARs **−10% to −15%+** in exposed countries. Firms with **higher tariff exposure had significantly lower CARs**; worst among high-leverage, high-growth/valuation, high-advertising-intensity, low-earnings-quality firms. **Partial recovery at implementation** when realized tariffs were milder than signalled | Days at announcement; weeks to reprice exposure | **S1 for the index, S3 for the cross-section** | 10-K risk-factor text mentioning tariffs; import/COGS geography | **The index move is uncatchable. The exposure cross-section is catchable and was *not* efficiently priced** — firms that *disclosed* tariff risk in 10-Ks had significantly lower CARs, i.e. the market used the disclosure but slowly | Federal Register API, USTR, EDGAR 10-K full-text search |
| **Antitrust investigation opened** | − | **−0.82%** on announcement day, **−0.99%** day +1. EU **dawn raids −4.7%**, final decision **−1.9%**. Antitrust complaint against a merger: **bidder −1.4%, target −7.6%** (3-day). Extreme case (SAMR v Alibaba) long-horizon **−17% to −25%** | Days; long-horizon for structural cases | **S2** | DOJ/FTC/EC press releases, 8-K | Small average effect, fat tail. **Competitor stocks rise** — the pair trade is the cleaner expression | DOJ/FTC RSS, EC competition case database, Federal Register |
| **Sanctions / export controls (Entity List)** | − for suppliers of the listed firm; **+ for domestic substitutes** | US suppliers of newly-listed Chinese firms show **negative CARs**; **Chinese upstream suppliers show POSITIVE CAAR of +3.48% over [−5,+5]** (import substitution). Semiconductor-chain volatility rises significantly. Balance-sheet effects: lower cash flow, revenue, profitability, employment | Days at announcement; quarters for fundamentals | **S2–S3** | BIS Entity List additions + customer-concentration map | **The substitution winner side is systematically under-priced** — the market reacts to the victim, not the beneficiary | BIS Entity List (Federal Register), OFAC SDN list (free) |
| Subsidies / IRA-style support | + for named beneficiaries | No clean general magnitude; effects are large but idiosyncratic and heavily anticipated during legislative passage | Weeks (legislative path) | **S3–S4** | Congress.gov bill status + beneficiary mapping | The **bill-stage probability path** (committee → floor → signature) is the tradeable structure | Congress.gov API, Federal Register |
| New rules / legalisation / approval | + for approved, − for incumbent | Case-by-case. The FDA analogue (§1) is the best-quantified template: approval itself only +0.35%, because it is pre-priced | Days | **S2** | Federal Register final rules | The **date is known; the outcome is the uncertainty**. Same shape as FDA | Federal Register API (free, structured, excellent) |
| Taxes | ± by exposure | Effects flow through effective tax rate; cross-section is computable | Weeks | **S3–S4** | Effective tax rate from XBRL vs statutory | Under-exploited; requires XBRL work | EDGAR XBRL `IncomeTaxExpenseBenefit` |

**Policy notes:**

- **The repeated pattern across every policy event: the aggregate move is S1 and untradeable; the cross-sectional exposure ranking is S3 and tradeable.** Tariffs 2025 is the cleanest demonstration — the market clearly used firms' own 10-K tariff-risk disclosure, but *over days*, not instantly.
- **Beneficiary sides are under-priced relative to victim sides.** Export controls: Chinese upstream suppliers +3.48% while everyone watched the listed firm. Antitrust: competitors rise while everyone watches the defendant. This is a systematic, exploitable asymmetry in attention.
- The Federal Register API is a genuinely under-used free structured source of regulatory events with timestamps.

---

## 5. GEOPOLITICS

| Factor | Direction | Typical Size | Horizon | Speed priced-in | Measurable from | Decayed/Crowded? | Free source |
|---|---|---|---|---|---|---|---|
| **Geopolitical risk shock (GPR spike)** | − for equities, **+ for defense** | Caldara–Iacoviello: higher GPR → **short-lived but statistically significant drop** in stock returns; **defense sector earns positive excess returns**; higher GPR foreshadows lower investment/employment and higher disaster probability. **The paper does not give a single clean per-SD equity coefficient — magnitude is regime-dependent** | Days (returns), months (real activity) | **S2** — reaction is fast; **the "short-lived" finding means mean-reversion is the trade, not continuation** | GPR / GPRD index directly | Index is public and widely used; the **daily GPRD + sector cross-section** is less crowded | **matteoiacoviello.com/gpr.htm — free monthly AND daily (GPRD) CSVs** |
| War / conflict escalation | − risk assets, + oil/gold/defense | Magnitude scales with oil-supply relevance of the geography. Isolated conflicts with no commodity channel produce day-scale noise, not durable repricing | Days–weeks | **S2** | GPRD + commodity chokepoint mapping | The **"does it touch a commodity chokepoint" filter** is what separates real events from headlines | GPRD, EIA (chokepoint data) |
| Elections | ± by policy exposure | 2024 US: **brown (low-ESG) portfolios CAR peaked +2.5% to +3% by day 10**. Largest single market response comes **when the official result removes uncertainty**, not during polling. Cross-country reactions scale with **trade openness and financial linkage to the US** | Overnight + 10 days | **S2–S3** — the drift to day 10 means this is *not* instantaneous | Prediction-market odds + policy-exposure baskets built from 10-K text | The **10-day drift in exposure baskets is real and repeatedly documented** | Polymarket/Kalshi public odds; EDGAR text for exposure |
| Trade disputes | − for exposed | See §4 tariffs | Days–weeks | **S1/S3** | Same | Same | Same |
| Country risk / domicile exposure | − | Cross-country CAR dispersion in the 2024 election and 2025 tariff studies both loaded on **US trade/financial linkage**, confirming domicile exposure is priced but with a lag | Days | **S3** | Revenue-by-geography from 10-K segments | Under-exploited on free data | EDGAR XBRL geographic segments |

**Geopolitics notes:**

- **The critical quantitative finding is that the GPR equity effect is "short-lived".** That means a naive "geopolitics = short risk" system is systematically wrong at the 1–2 week horizon; the *reversion* is the higher-expectancy side. This is the exact opposite of what headline-driven systems do.
- **Elections drift for ~10 days.** That is S3 and reachable. The pre-election anticipation is efficiently priced by prediction markets; the post-result exposure re-ranking is not.
- I could not find a credible single "X% per SD of GPR" equity coefficient. Anyone quoting one is likely over-fitting a specific sample.

---

## 6. FLOWS / POSITIONING

| Factor | Direction | Typical Size | Horizon | Speed priced-in | Measurable from | Decayed/Crowded? | Free source |
|---|---|---|---|---|---|---|---|
| **S&P 500 index inclusion** | + historically, **now ~0** | Greenwood–Sammon "The Disappearing Index Effect": direct additions **9.6%** (late 90s) → **7.5%** (early 00s) → **5.1%** (late 00s) → **1.6%** (early 10s) → **4.1%** (late 10s/2020) → **near zero over the past decade**. Deletions: announcement and implementation returns **indistinguishable from zero by the 2010s** | Days | **S2, and now ~nothing to price** | Index announcements | **DEAD. This is the textbook case of a factor arbitraged to zero.** Causes: more migrations from S&P MidCap, better liquidity provision, more predictable changes | S&P DJI press releases (free) |
| **Russell reconstitution** | + adds / − deletes, **decayed** | Older samples: R1000 adds **+10.9%** cumulative excess (2d before May 31 → Jun 30); R2000 adds **+4.6%**; deleted R2000 Growth **−6.6%**. **Effect weakens markedly in recent years; price-pressure reversal now "much smaller to nonexistent"** | ~4 weeks (May rank day → June recon) | **S3–S4 historically** | FTSE Russell preliminary lists (public), float-adjusted rank estimates | **Heavily crowded — arXiv work explicitly documents crowding on Russell recon events.** Residual edge only in the small/illiquid tail | FTSE Russell recon schedule + preliminary add/delete lists (free) |
| **Aggregate flows → price (inelastic markets)** | + | Gabaix–Koijen: **$1 of net equity inflow raises aggregate market value ~$5** (multiplier range **3–8**). Flows drive **>1/3** of market fluctuations | Weeks–quarters | **S4–S5** | Requires flow data; ICI weekly and ETF creation/redemption are the free proxies | The *hypothesis* is famous; the *implementable version* is not, because flow data is the bottleneck | ICI weekly estimates (free), ETF shares-outstanding daily from issuer sites |
| **13F institutional holdings** | + weakly | One 2013–2023 study of >150,000 constructed portfolios claims top-quartile clones beat the S&P by **24.3% annualized risk-adjusted**. **Treat this number with heavy scepticism — selection of "top quartile" ex-post is exactly the flaw that inflates cloning studies.** Structural fact: **45-day reporting lag**; long-holding-period managers are clonable, quant funds are not | Quarter | **S5** | 13F-HR XML | Widely done. **Alive only for genuinely long-horizon, concentrated managers.** Alpha decay is driven by holding period, not by the lag per se | **EDGAR 13F-HR XML — free, structured** |
| **Short interest (cross-section)** | − | High short interest **combined with a binding constraint** (low institutional ownership) underperformed by **−215 bps/month** equal-weighted (1988–2002). Note: it is the *constraint*, not short interest alone, that drives it | 1 month (bi-monthly reporting) | **S4** | FINRA/exchange short interest + institutional ownership from 13F | Known; the interaction term is the part that still works | **Nasdaq Trader short interest files + FINRA daily short volume — free** |
| Short interest (aggregate/market-level) | − for future market returns | Rapach–Ringgenberg–Zhou: **"arguably the strongest known predictor of aggregate stock returns"**; annual R² of **12.89% and 13.24%**; utility gains **>300 bps/yr** for a mean-variance investor | Months | **S5** | Aggregate short interest series | Published 2016 → apply the −58% post-publication haircut | Nasdaq Trader aggregate files |
| **Borrow fee / cost to short** | − (expensive to short → low future returns) | Drechsler & Drechsler: cheap-minus-expensive-to-short portfolio, **gross +1.43%/month, net +0.91%/month, 4-factor alpha +1.53%/month**. And critically: a long-short anomaly averaging **+0.14%/month gross becomes −0.01%/month once borrow fees are paid** | 1 month | **S4** | Borrow fee is the gap — no reliable free source | **This is the best-performing positioning signal I found, and its data is the hardest to get free.** Utilization proxies from broker APIs are the practical substitute | No good free source. IBKR API stock-loan data if you have an account; **this is a genuine data gap** |
| **Short squeeze mechanics** | + violently | GME 2021: short interest **>140% of float**, days-to-cover **6–14**, price **+2,315%**. Practitioner threshold: **DTC > 8 days** flags difficulty covering; double-digit DTC in small caps → sharp spikes. **These are descriptive thresholds, not tested predictors** | Days | **S2** | SI/float + DTC + utilization | Everyone watches SI/float. **Utilization (shares on loan ÷ lendable) is the scarcer and better metric** | Nasdaq SI files + volume; utilization needs paid/broker data |
| **Dealer gamma (GEX)** | Positive gamma → **mean reversion / vol suppression**; negative gamma → **momentum / vol amplification** | Barbon–Buraschi ("Gamma Fragility", peer-reviewed): **intraday momentum is explained by the interaction of negative aggregate gamma imbalance × market illiquidity; intraday reversal by positive gamma imbalance**. Practitioner (SpotGamma-adjacent, **not peer-reviewed**): positive-GEX regimes show **~50% lower realized vol** than negative-GEX regimes (SPX 2012–2023) | Intraday to a few days | **S2** — this is a *state*, not an event; it persists until positioning changes | Full options chain OI × gamma per strike, with a dealer-sign assumption | The signal is popular; **the dealer-sign assumption is the weak link everyone shares** — that is both the risk and the reason it isn't fully arbitraged | Cboe delayed options data; OCC OI; free chains via broker APIs |
| **Vanna / charm** | Vanna: IV ↓ → dealer buying → spot ↑ (self-reinforcing). Charm: time decay mechanically unwinds hedges into expiry | **No peer-reviewed magnitude estimate found.** All the specific numbers I saw were vendor-produced | Days into expiry | **S2** | Second-order greeks across the chain | Vendor-crowded, academically thin | Same as GEX |
| **0DTE** | Amplifies intraday, suppresses close-to-close | SPX 0DTE: **~1.5M contracts/day (2024) → ~2.3M/day (2025) = ~59% of SPX volume → ~63% by Feb 2026**. Dealer hedging estimated at **25–40% of SPX volume**. Net effect described as **more quiet days punctuated by sharper intraday reversals** | Intraday | **S2** | Cboe volume stats | Structurally new; genuinely under-modelled. Dim–Eraker–Vilkov (2024) is the academic anchor | Cboe market statistics (free) |
| **Retail order flow** | + short-horizon | Boehmer–Jones–Zhang–Zhang: stocks with net retail buying beat net retail selling by **~10 bps over the following week (~5%/yr)**; informative **up to 12 weeks**; **strongest in smaller, lower-priced stocks** | 1 week → 12 weeks | **S3–S4** | The BJZZ algorithm: sub-penny price improvement on TAQ trades identifies retail marketable orders | Published in the *Journal of Finance* (2021) → **expect decay**. But the **small/low-price concentration is exactly where big money cannot go** | TAQ is paid. **Free proxy: FINRA daily short-sale volume files + off-exchange (TRF) volume share** |
| ETF flows (single-name/sector) | + | Follows the inelastic-markets multiplier logic; no clean single-name coefficient found | Days–weeks | **S3** | ETF shares outstanding daily × NAV | Under-exploited for sector ETFs | Issuer daily holdings/shares files (free) |
| Crypto ETF flows (BTC) | + | One 2024–2025 cointegration study: elasticity **0.27** (10× cumulative flows ↔ 1.8× price), **R² 0.692**. At peak, daily ETF inflows exceeded daily mining supply by **>12×** | Days–weeks | **S2–S3** | Daily ETF flow prints | **Single study, cointegration on a 16-month sample, weak causal identification. Directionally believable, numerically fragile** | Issuer daily flow disclosures; Farside-style trackers |
| Crypto perp funding rate | Extreme positive funding → crowded longs → **reversal risk**; extreme negative → capitulation → **bounce risk** | **No peer-reviewed effect size found.** BIS working paper 1087 ("Crypto carry") documents the carry structure; the reversal-prediction claim is practitioner-only | Hours–days | **S2** | Funding rate + OI + basis directly from exchange APIs | Very widely watched in crypto. The **carry (hedged funding) is a real, harvestable premium**; the **directional reversal signal is folklore** | **Binance / Bybit / Hyperliquid public REST APIs — free, complete, real-time** |

**Flows notes:**

- **Index inclusion is the cleanest documented death of a factor in this entire document** — 9.6% → ~0 in twenty years, with a named mechanism. Use it as the mental model for every "well-known flow event".
- **Borrow fee is the strongest positioning signal (net +0.91%/month after paying the fee itself) and simultaneously the biggest free-data gap.** Worth solving.
- The **−0.14%/month → −0.01%/month** result on borrow fees is the most important cost number in the document: **a typical published long-short anomaly is entirely consumed by short-side borrow cost.** Any backtest that ignores borrow is not a backtest.
- **Dealer gamma has one solid peer-reviewed anchor (Barbon–Buraschi) and a cloud of vendor numbers.** The peer-reviewed version is conditional: negative gamma *interacted with illiquidity*. Build the interaction, not the raw GEX level.

---

## 7. MARKET STRUCTURE

| Factor | Direction | Typical Size | Horizon | Speed priced-in | Measurable from | Decayed/Crowded? | Free source |
|---|---|---|---|---|---|---|---|
| **Market-cap tier / microcap** | + (higher raw alpha, higher cost) | The size premium is **concentrated in microcaps**. Anomaly alphas are systematically larger in small, illiquid, high-idio-vol stocks (McLean–Pontiff find post-publication returns remain **higher** in exactly those stocks). Capacity: a microcap manager caps at **$600–800M**, vs **$6–10B** for small cap | Weeks–months | **S4** | Market cap + ADV | **This is the structural advantage of a small operator and it is not arbitrageable away** — the constraint is institutional, not informational | Any price feed |
| Float size | Smaller float → larger price impact per dollar of flow | Mechanically links to the inelastic-markets multiplier; low float amplifies every flow effect in §6 | Days | **S2** | Shares outstanding (10-Q cover) − insider/affiliate holdings (Form 4 + SC 13D/G) | Computable free; commonly done badly (people use shares outstanding, not free float) | EDGAR 10-Q cover XBRL + SC 13D/G |
| **Borrow availability** | Hard-to-borrow → short side is uneconomic | See §6 borrow fee. **Practical rule: if you cannot verify borrow, the short leg does not exist** | — | — | Broker locate list | — | Broker API |
| **Trading halts (LULD)** | Mostly noise, reverts | Most limit-state events come from **temporary liquidity gaps and reverse within 15 seconds**. LULD **reduces the magnitude of maximum price reversal** vs pre-LULD days; it curbs short-term vol **without delaying price discovery**. A "magnet effect" exists as price approaches the band | Seconds–minutes | **S1** | LULD band data, halt feeds | **Do not build a directional halt strategy.** The published evidence says the mechanism removes the very overreaction you would be trying to trade | UTP/CTA halt feeds (free delayed) |
| **Overnight vs intraday session split** | Overnight >> intraday in the US | Overnight returns exceed intraday returns despite **lower overnight volatility**. Lachance: **~1/5 of stocks have statistically significant positive overnight bias**; investing overnight in those yields **~2× the market return at ~1/3 the market beta**. Bogousslavsky: **size and illiquidity premia are realized in the last 30 minutes of trading**; profitability and idio-vol accrue intraday and **lose money overnight** | Daily, persistent for years | **S4–S5** | Open/close/prior-close from any daily bar | **This decomposition is under-used and the effects persist several years after formation.** It is also a costs trap — capturing it requires trading twice daily | Any free OHLC feed (Stooq, yfinance) |
| Time-zone / session effects | Regional handoff effects | ADR/underlying asynchrony creates documented overnight-vs-intraday structure | Daily | **S3** | Cross-listing pairs | Small, real, capacity-limited | Free price feeds |
| Liquidity tier (Amihud illiquidity) | + premium, − tradability | Illiquidity premium is real but is the **first thing transaction costs eat**. Note from our own prior work: Amihud in low-liquidity venues is prone to **outlier artifacts** — winsorize hard before trusting it | Months | **S5** | \|return\| / dollar volume | The premium is a compensation, not an edge | Any price+volume feed |

**Market-structure notes:**

- **This section contains the small operator's actual structural edge and it is entirely about capacity.** A $600–800M ceiling on microcap strategies is not a market inefficiency that will be arbitraged — it is a fee-economics constraint on the asset-management industry. It is permanent as long as institutions are paid on AUM.
- **The overnight/intraday decomposition is the most under-used free measurement in the document.** Every price feed already has open, high, low, close, prior close. The finding that *different anomalies live in different parts of the day* means a factor tested on close-to-close returns may be measuring the average of two opposite effects.
- **Halts: the literature says the mechanism works.** LULD reduces reversal magnitude and most limit states resolve in 15 seconds. A halt-fade strategy is trading against a mechanism explicitly designed to remove that trade.

---

## 8. SENTIMENT / NARRATIVE

| Factor | Direction | Typical Size | Horizon | Speed priced-in | Measurable from | Decayed/Crowded? | Free source |
|---|---|---|---|---|---|---|---|
| **Analyst recommendation change** | + upgrade / − downgrade, **asymmetric** | Womack (1996): post-event drift **+2.4% for upgrades**, **−9.1% for downgrades** over ~6 months. **Upgrades drift ~30 days; downgrades persist up to 6 months.** Barber et al. (2001): most-favourable-consensus portfolio earned **+102 bps/month gross excess** | 1–6 months | **S3–S4** | Consensus rating changes | **The Barber et al. strategy required near-daily rebalancing and its gross alpha is largely consumed by turnover costs** — this is a textbook cost-death case. The **downgrade side (6-month persistence, low turnover) is the survivable half** | Consensus data is the paid gap. Free partials: Finnhub recommendation trends (60 req/min free tier) |
| Analyst estimate revisions | + with revision sign | Related to PEAD; same decay pattern (dead in large caps, alive in low-coverage names) | Weeks | **S3–S4** | Revision breadth | Crowded where coverage is dense; **the opportunity is where coverage is thin, which is also where free data is thinnest** | Finnhub free tier |
| **Media sentiment (professional news)** | − then **reverses** | Tetlock (2007): high media pessimism → **downward price pressure followed by reversal to fundamentals**; the measured reversal over lags 2–5 is **6.8 bps** (significant at 5%). Unusually high *or* low pessimism predicts **high trading volume** | 1–5 days | **S1 for the reaction, S2–S3 for the reversal** | Bag-of-words or LLM tone over a news corpus | **Institutionalized** — >70% of top quant funds use commercial news analytics (vendor claim). The reaction is priced in **milliseconds** at professional feeds | **GDELT 2.0 (free, 15-min global news tone/volume)**; company IR + EDGAR 8-K text |
| **Social sentiment (Reddit/StockTwits/X)** | **Contrarian for sentiment; NOT contrarian for attention** | Stocks heavily discussed and bought by retail **decline in subsequent weeks**. But the finding splits: **sentiment is a contrarian predictor of future returns**, while **when attention herds on a stock with high engagement, trades peak but there is NO return reversal**. Attention and sentiment **predict opposite outcomes** | 1–4 weeks | **S3–S4** | Post counts, engagement, and tone as **two separate variables** | The naive "social sentiment = signal" version is crowded and wrong-signed. **Separating attention from sentiment is the un-crowded part** | Reddit API (free tier), Pushshift-style archives, GDELT |
| **LLM/NLP on transcripts & filings** | + with extracted tone | Berkeley/arXiv work (2023–2025, Russell 3000, 7,382 transcripts / 1,831 firms): **overall transcript sentiment gave limited insight; segment-level sentiment showed meaningful patterns.** Semantic features outperformed raw sales/EPS for next-day direction in at least one study | 1–5 days | **S2–S3** | Transcript text → structured tone by business segment | **Rapidly crowding.** The generic "LLM reads earnings call" trade is being industrialized right now. The **segment-level decomposition** is the current frontier | Company IR transcripts, SEC 8-K exhibits |
| Thematic hype cycles | + then − | No reliable magnitude. Attention-driven; behaves like the social-attention factor above | Months | **S4–S5** | Search/news volume indices | Narrative; not quantifiable to a coefficient | Google Trends, Wikipedia pageviews API (free) |

**Sentiment notes:**

- **The attention/sentiment split is the key quantitative insight in this section.** They predict *opposite* things. A system that computes one blended "sentiment score" is averaging two signals with opposite signs and will produce a null result.
- **The Womack asymmetry (+2.4% up vs −9.1% down) plus the persistence asymmetry (30 days vs 6 months) means the analyst factor is really a short-side factor** — which then runs straight into the borrow-cost wall from §6. That interaction is why the published alpha does not survive.
- Media sentiment reaction is now S0/S1 at professional latency. **What is left for us is the reversal (Tetlock's 6.8 bps over days 2–5), which is small and needs to be traded in size or in illiquid names to matter.**

---

## 9. SCHEDULED CALENDAR

| Factor | Direction | Typical Size | Horizon | Speed priced-in | Measurable from | Decayed/Crowded? | Free source |
|---|---|---|---|---|---|---|---|
| **Earnings announcement premium** | + (announcers beat non-announcers) | Frazzini–Lamont: the premium is **"large and robust"**, strongly tied to the **volume surge** around announcements; stocks with **high past announcement-period volume earn the highest premium**; driven by small-investor attention buying. **I could not verify a single canonical per-day bps figure in this pass — do not hardcode one** | The announcement month/window | **S4, fully anticipable** | Earnings calendar + historical announcement-window volume per stock | Well known. **The conditioning variable (past announcement-period volume) is what makes it work and is what most implementations omit** | EDGAR 8-K history to build your own calendar; Nasdaq earnings calendar |
| **Pre-FOMC drift** | + | Lucca–Moench: **+49 bps in the 24 hours before scheduled FOMC announcements (Sep 1994 – Mar 2011)**, accounting for **~80% of the annual equity return**. Boguth et al.: limited to **press-conference meetings**. **Then it essentially disappeared after 2015, for both press-conference and non-press-conference meetings** | 24 hours pre-announcement | Was **S4**; **now dead** | FOMC calendar + index returns | **DEAD — a textbook publication-decay case (published 2015, gone by 2015).** Keep it as a monitored null, not a live signal | federalreserve.gov FOMC calendar (free) |
| CPI / NFP release dates | Vol event, sign regime-dependent | See §3 | Minutes | **S1** | BLS release calendar | Vol-selling around known dates is crowded | BLS release calendar (free) |
| **Options expiry / pinning** | Toward max-OI strike | Ni–Pearson–Poteshman: **optionable stock returns are altered by at least 16.5 bps on average on each expiration date**, ≈**$9bn** of aggregate market-cap displacement. **Pin rate 8.2% on expiration days vs <6% on adjacent days.** Cause: **market-maker hedge rebalancing + proprietary-trader manipulation** | Expiry day | **S2** | OI by strike + current spot | Widely known; the effect is small per-name but **mechanical and repeatable, and larger in low-float names** | Cboe/OCC OI (free delayed) |
| Index rebalance dates | See §6 | See §6 | Weeks | **S3** | Published schedules | Crowded (Russell), dead (S&P) | FTSE Russell, S&P DJI |
| **Lockup expiry** | − | See §1: **−1.5% 3-day, permanent +40% volume, no reversal**, larger for VC-backed | 3–5 days, **date known 180 days in advance** | **S3** | S-1 lockup clause + IPO date | The date is public 6 months ahead; **the un-crowded part is the VC-concentration conditioning** | EDGAR S-1/424B4 |
| **Token unlocks (crypto)** | − | Keyrock: **>16,000 unlock events, ~90% showed negative price impact within a 30-day window.** SSRN 52-event Binance study: **46/52 (88.5%) negative within 72 hours.** ARB Mar-2024 cliff: circulating supply **+87%**, price **−33.8% in 30 days**. **Prices begin weakening ~30 days BEFORE the unlock and stabilize ~2 weeks after** | −30 days → +14 days | **S3–S4, partially anticipated** | Public vesting schedules + circulating supply | Increasingly watched, but the **size of the unlock relative to circulating supply and float** is the discriminating variable most trackers ignore | **DefiLlama unlocks API, TokenUnlocks — free; on-chain vesting contracts are the ground truth** |
| Quad witching / quarterly expiry | Vol + volume spike | Amplified version of opex pinning | Day | **S2** | Calendar | Known | Exchange calendars |

**Calendar notes:**

- **The pre-FOMC drift is the most instructive entry in this document.** A 49 bp, 24-hour, fully-scheduled, ~80%-of-annual-returns anomaly, published in a top journal — and it was gone within a few years of publication. Any calendar anomaly you find should be assumed to have the same fate.
- **Token unlocks are the crypto analogue of lockup expiry and are far less efficiently priced.** The 30-days-before weakening means the trade is anticipatory, and the discriminating variable (unlock size ÷ circulating supply) is trivially computable free.
- **Scheduled ≠ priced.** Lockups and unlocks are known 6 months ahead and still move prices, because the *supply* is real and someone has to absorb it. Compare index inclusion, where the flow was also known and the effect went to zero — the difference is that index flow is two-sided and predictable to liquidity providers, while lockup/unlock flow is one-directional selling.

---

## 10. HISTORICAL PRECEDENT — event-study methodology and its traps

### The measurement stack

| Step | What to compute | Notes |
|---|---|---|
| 1. Event identification | Exact timestamp, not date | Use the filing `acceptanceDatetime`, not the report date. The pre-open vs after-hours split alone changes the initial reaction by **36%** |
| 2. Expected return model | Market model, FF3, FF5, or characteristic-matched | For short windows (≤5 days) the model choice barely matters. **For long windows it dominates everything** |
| 3. Abnormal return | AR = actual − expected | — |
| 4. CAR | Sum of ARs over the window | Preferred for short horizons |
| 5. BHAR | Compounded, vs a matched benchmark | Preferred by Barber–Lyon for long horizons; **rejected by Fama**, who argues CAR is statistically better behaved |
| 6. Calendar-time portfolio | Form a portfolio of all firms currently "in event", regress on factors | **The safest long-horizon method** — it automatically handles cross-sectional correlation and event clustering |

### The traps — in order of how often they destroy a result

1. **Cross-sectional correlation of event-date returns.** If events cluster in time (they always do — earnings seasons, macro shocks, sector waves), your observations are not independent. *"Even a seemingly trivial (average) cross-correlation substantially changes the t-statistics, their asymptotic distribution, and the power of the tests."* Bootstrapping does **not** fix this.
   → **Fix:** calendar-time portfolios, or cluster standard errors by event date, or the BMP standardized cross-sectional test.

2. **The bad-model problem (Fama 1998).** *"Bad-model problems are most acute with long-term buy-and-hold abnormal returns (BHARs), which compound an expected-return model's problems."* A 1%/year model error becomes a 3% "abnormal return" over three years.
   → **Fix:** never report a multi-year BHAR as a standalone finding. Cross-check with calendar-time alphas.

3. **Pseudo-timing / clustering bias in BHAR.** BHAR *mechanically* produces underperformance when events cluster in an up market (e.g. IPO waves).
   → **Fix:** same as above.

4. **Overlapping events.** A firm with an earnings surprise, a downgrade, and a lockup expiry in the same 10 days contributes one observation to three studies, all contaminated.
   → **Fix:** an explicit event-conflict filter; report results with and without contaminated observations.

5. **Multiple testing.** Harvey–Liu–Zhu argue the appropriate t-statistic hurdle for a *new* factor is **~3.0**, not 1.96. Hou–Xue–Zhang: with NYSE breakpoints and value-weighted returns, **65% of 452 anomalies fail |t| > 1.96**; at the multiple-testing hurdle of **2.78, the failure rate is 82.1%**. Trading-frictions anomalies fail at **96%**.
   → **Fix:** adopt t > 3.0 as house standard. Value-weight. Use NYSE breakpoints.

6. **Small samples with fat tails.** Twenty M&A events is not a base rate. Report the full distribution and the median, not just the mean — the FDA and M&A distributions are strongly skewed.

7. **Survivorship and look-ahead in the event list.** Building an event list from a current index constituents file bakes in survivorship. Point-in-time constituent lists or nothing.

8. **The base-rate question is usually "conditional on what?"** "What happened last time" is only useful if the conditioning set is honest. Recording *how many events matched the conditions* alongside the average outcome is mandatory — an average over 4 events is not a base rate.

### The two numbers to keep pinned above the desk

- **McLean–Pontiff (JF 2016), 97 published predictors:** returns are **26% lower out-of-sample** and **58% lower post-publication**. The 26% is the data-mining bound; the extra 32% is real arbitrage from investors reading the papers.
- **Novy-Marx & Velikov (RFS 2016):** anomalies with **<50% monthly turnover generally generate significant net spreads** when designed to mitigate costs; **few with higher turnover do.** The most effective mitigation is a **buy/hold spread** (stricter entry threshold than exit threshold).

**Practical translation: take any published alpha, multiply by 0.42, then subtract costs, then check turnover < 50%/month. If it still clears, it might be real.**

---

## 11. CROSS-ASSET

| Factor | Direction | Typical Size | Horizon | Speed priced-in | Measurable from | Decayed/Crowded? | Free source |
|---|---|---|---|---|---|---|---|
| **BTC ↔ Nasdaq/equities** | + in risk-on/risk-off, **regime-unstable** | 30-day rolling correlation: **0.23 average in 2024 → 0.52 average in 2025 → −0.299 in Dec 2025 → ~0.18 in Jan 2026** (lowest since Nov-2022 FTX). 3-month rollings near zero mid-2026. **Asymmetric: BTC tracks Nasdaq sell-offs closely but sometimes ignores equity rallies** | Days–months, regime-dependent | **S2–S3** | Rolling correlation on daily/hourly returns | **The correlation itself is not a signal; the regime state is.** The asymmetry (downside beta > upside beta) is the durable, tradeable part | Any free price feed; FRED `NASDAQCOM` |
| BTC ↔ DXY | − (usually) | Recoupled to the dollar index in 2026 per market commentary. **No robust published coefficient** | Weeks | **S3** | Rolling regression | Narrative-heavy | FRED `DTWEXBGS` |
| Equities ↔ bonds | Correlation **sign flipped** in the inflation regime | Pre-2021: negative (bonds hedge equities). 2022+: positive when inflation is the driver. This flip is the defining cross-asset fact of the current era | Months | **S5** | Rolling stock-bond correlation | Widely known; **critically, it means "60/40 diversification" and any vol-target model calibrated pre-2021 is mis-specified** | FRED `DGS10` + index |
| Equities ↔ oil | Sign depends on shock type | See §3 | Days | **S2** | Structural decomposition | The decomposition is the edge | EIA API, FRED |
| Equities ↔ credit | Credit leads equity at turning points | EBP shocks orthogonal to state → declines in equity prices (Gilchrist–Zakrajšek) | Weeks | **S4** | HY OAS | Best free risk-off state variable | FRED `BAMLH0A0HYM2` |
| FX ↔ single-stock earnings | See §3 dollar row | **10% TWI ↔ 3–4% S&P EPS, opposite sign**; firm-level ranges from ~0 (<15% foreign revenue) to extreme (semis, ~90%+ international) | Quarters | **S3** | 10-K geographic segments | Firm-level version is under-exploited on free data | EDGAR XBRL |

**Cross-asset notes:**

- **The single most dangerous thing in this section is hardcoding a correlation.** BTC-Nasdaq went from +0.52 average to −0.30 within months. Any system with a fixed cross-asset beta will be catastrophically wrong at exactly the moment it matters.
- **Asymmetric correlation (downside beta ≠ upside beta) is the recurring, robust structure.** BTC tracks equity selloffs but not rallies. Model correlation conditionally on the sign and magnitude of the driver's move, not unconditionally.
- **The stock-bond correlation regime flip (2021→2022) invalidates any risk model calibrated on 2010s data.** Worth an explicit regime flag in the system.

---

## 12. WHAT SURVIVES OUT-OF-SAMPLE AND AFTER COSTS

### Survives — trade these

| Factor | Why it survives | Caveat |
|---|---|---|
| **Opportunistic insider buying** (82 bps/mo) | The routine/opportunistic split has a **clean null** (routine = zero), which is the signature of a real effect rather than a mined one. Free structured data. Low turnover | Concentrated in small caps; front-loaded in the first 21–60 days |
| **Borrow-fee cross-section** (net +0.91%/mo after fees) | Explicitly measured net of the exact cost that kills other anomalies | **Data is the blocker** — no good free source |
| **Customer/supplier link (Cohen–Frazzini, 150 bps/mo)** | Economically motivated, robust to every standard control they tested, monthly turnover | Published 2008; apply the −58% haircut → ~63 bps/mo expected today. Requires building the customer map from 10-K text |
| **PEAD in low-coverage small/mid caps** (>2% over 60 days) | Survived precisely where arbitrage capital cannot go | Dead in large caps. Needs a free consensus substitute |
| **Lockup expiry / token unlock** (−1.5% / mechanical crypto supply) | Real one-directional supply, not an information story. **Field–Hanka explicitly found it stable over a 10-year sample and not reversed** | Anticipated; the edge is in conditioning on VC concentration / unlock-to-float ratio |
| **Overnight vs intraday decomposition** | Persists several years after portfolio formation; documented profitable after costs | Requires 2 trades/day — costs are the whole question |
| **Downgrade persistence** (−9.1% over 6 months, low turnover) | Low turnover passes the Novy-Marx–Velikov filter | It is a short-side signal → borrow costs (see above) |
| **Rating-change asymmetry, dividend-cut asymmetry, negative-event asymmetry generally** | Asymmetries are behavioural and structural, not arbitrage-able by symmetric capital | Small per-event |
| **Microcap capacity advantage** | Not an anomaly — an **institutional constraint** ($600–800M ceilings). Permanent while AUM fees exist | Requires accepting illiquidity and wide spreads |
| **Crypto carry (hedged perp funding)** | A genuine, measurable, harvestable premium (BIS WP 1087) | Consistent with our own prior finding that carry is the only Hyperliquid strategy that survived walk-forward |

### Decayed or dead — do not build

| Factor | Evidence of death |
|---|---|
| **S&P 500 index inclusion** | 9.6% → 7.5% → 5.1% → 1.6% → ~0. Named mechanisms (migrations, liquidity provision, predictability) |
| **Pre-FOMC drift** | +49 bps → gone after 2015, in both press-conference and non-press-conference meetings |
| **PEAD in large caps** | Zero for non-microcaps from ~2001, zero for large caps by ~2006 |
| **Industry momentum** | Cumulative return ≈ 0 since 2000 |
| **Business-cycle sector rotation (textbook version)** | Expected early- and mid-expansion leaders each **underperformed by 5 bps/month** |
| **Russell reconstitution price pressure** | Reversal effects now "much smaller to nonexistent"; explicit crowding documented |
| **Analyst consensus long-short (102 bps/mo gross)** | Requires near-daily rebalancing; costs consume it |
| **Stock split drift (+7.9%/yr)** | 1975–1990 sample, drift concentrated in the announcement→effective window |
| **65–82% of published anomalies generally** | Hou–Xue–Zhang: 65% fail t>1.96, 82.1% fail t>2.78, with proper breakpoints and value weighting |
| **Naive social sentiment** | Attention and sentiment predict opposite signs; the blend is null |
| **Halt-fade** | LULD demonstrably removes the reversal you would be trading |

### The two universal haircuts

1. **× 0.42** — McLean–Pontiff post-publication decay (returns 58% lower).
2. **Then subtract real costs, including borrow.** Novy-Marx–Velikov: only sub-50%-monthly-turnover strategies generally clear. Drechsler: a +0.14%/mo gross long-short becomes **−0.01%/mo** after borrow fees.

---

## 13. EXPLOITABILITY RANKING FOR A SMALL OPERATOR

Ranked by **(expected edge after decay and costs) × (feasibility on free data) × (capacity fit for small size)**. A small operator's *only* structural advantages are: can trade illiquid/small things, no benchmark or drawdown-committee constraint, and no capacity floor. Everything below is ranked with that in mind.

### Tier 1 — build these first

| # | Factor | Why it ranks here |
|---|---|---|
| 1 | **Opportunistic insider buying in microcaps (Form 4)** | Free, real-time, fully structured XML from EDGAR. Clean null on routine trades. 82 bps/mo published, concentrated exactly where institutions cannot go. Monthly turnover → passes the cost filter. **This is the single best free-data edge in the document.** |
| 2 | **Token unlocks / vesting cliffs (crypto)** | Free, deterministic on-chain schedules. Mechanical one-directional supply. 88.5% negative in 72h, ~90% negative over 30 days across 16k events. Weakening starts 30 days early → anticipatory, so latency doesn't matter. Crypto venues have no borrow-cost problem for shorts (perps). **Best fit for a Hyperliquid-based system.** |
| 3 | **Lockup expiry (equities)** | Free (S-1 text), date known 180 days ahead, −1.5% with no reversal, stable over a decade, larger in VC-backed names. Same mechanical-supply logic as #2. |
| 4 | **Crypto carry / hedged funding** | Already proven in our own walk-forward as the only surviving Hyperliquid strategy. Free complete data from exchange APIs. A genuine premium, not an anomaly. |
| 5 | **SEO / dilution announcements in small caps** | 424B5 filings are free and timestamped. −0.8% to −3.25%. Small-cap ATM programs are chronic and under-covered. |

### Tier 2 — build once Tier 1 is live

| # | Factor | Why |
|---|---|---|
| 6 | **PEAD in low-coverage small/mid caps** | >2% over 60 days in extreme deciles. Blocked only by the free-consensus problem — a self-built consensus from historical revisions or a simple time-series surprise model is a viable substitute. |
| 7 | **Customer→supplier propagation (Cohen–Frazzini)** | 150 bps/mo published, ~63 bps/mo after the standard haircut. The hard part is extracting the customer map from 10-K text — which is exactly the kind of work that keeps it un-crowded. |
| 8 | **Peer read-across conditioned on (large announcer → small illiquid peer)** | The 1.8%-of-announcer-CAR average is unconditional; the conditional version is much larger and lives in names too small for the arbitrageurs. |
| 9 | **Policy-exposure cross-section (tariffs, export controls, elections)** | The consistent finding across §4 and §5: **the index move is untradeable, the exposure ranking drifts for days.** 10-K full-text search is free. The **beneficiary side is systematically under-priced.** |
| 10 | **Securities-class-action investigation → filing window (median 9 days)** | Free (Stanford SCAC + 8-K). A −17% pre-filing CAR when an investigation was pre-announced means the market grinds down over the gap. |
| 11 | **Overnight vs intraday decomposition** | Free from any OHLC feed. Persistent for years. Costs are the entire question — test carefully. |
| 12 | **Dealer gamma × illiquidity interaction (Barbon–Buraschi form)** | Peer-reviewed, and the *interaction* form is much less crowded than the raw GEX level everyone plots. Free chains via broker APIs. |

### Tier 3 — real but marginal for us

| # | Factor | Why it ranks lower |
|---|---|---|
| 13 | Opex pinning | Only 16.5 bps average per name; real but thin. Larger in low-float names, so worth it only there. |
| 14 | 13F cloning of long-horizon concentrated managers | Free structured data, but the "24.3%" claim is ex-post-selection-contaminated. Only defensible for managers with verified multi-year holding periods. |
| 15 | Short-interest × low-institutional-ownership interaction | −215 bps/mo, but the short side runs into borrow cost, and the free SI data is bi-monthly and stale. |
| 16 | Downgrade persistence | Real (−9.1%/6mo, low turnover) but short-side → borrow wall. |
| 17 | Retail order-imbalance (BJZZ) | ~10 bps/week, strongest in small/low-price names (good fit), but the sub-penny identification needs TAQ, which is paid. FINRA TRF volume share is a weak proxy. |
| 18 | Attention-vs-sentiment split on social data | The insight is real (opposite signs) but the data is noisy and the space is heavily fished. |
| 19 | Firm-level FX exposure baskets | Computable free from XBRL segments; slow-moving, quarterly, low Sharpe. |
| 20 | Macro-surprise regime-flip modelling (NFP/CPI) | High intellectual value, low direct tradability at our latency — better used as a **regime conditioner for everything above** than as a standalone signal. |

### Do not build

Index inclusion · pre-FOMC drift · large-cap PEAD · industry momentum · textbook sector rotation · Russell recon price pressure · analyst-consensus long-short · halt-fade · stock-split drift · Fed net liquidity · raw blended social sentiment · any correlation hardcoded as a constant.

---

## 14. FREE DATA SOURCE APPENDIX (specific endpoints)

### SEC / filings — the highest-value free stack
- **Company facts / concepts (XBRL):** `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`, `.../companyconcept/CIK##########/us-gaap/{Tag}.json`, `.../frames/us-gaap/{Tag}/USD/CY2026Q1I.json`
- **Submissions / filing index:** `https://data.sec.gov/submissions/CIK##########.json` — includes `acceptanceDateTime` (the pre-open vs after-hours discriminator)
- **Full-text search (2001→):** `https://efts.sec.gov/LATEST/search-index?q=%22tariff%22&dateRange=custom&forms=10-K`
- **Form 4 (insiders):** daily index `https://www.sec.gov/Archives/edgar/daily-index/` → XML with transaction codes (`P` buy, `S` sell, `F` tax), 10b5-1 flag
- **13F-HR** (institutional), **SC 13D/G** (blocks), **424B5** (offerings), **S-1** (lockup text), **8-K Item 2.02** (earnings), **5.02** (management change), **8.01** (other events)
- **Financial Statement Data Sets:** quarterly ZIPs at `https://www.sec.gov/dera/data/financial-statement-data-sets.html`
- Requirements: declared `User-Agent`, ≤10 req/s. **No key, no cost, no rate-limit tier.**

### Macro
- **FRED API:** `https://api.stlouisfed.org/fred/series/observations?series_id=...` (free key, effectively unlimited). Keys: `CPIAUCSL`, `CPILFESL`, `PAYEMS`, `ICSA`, `DGS10`, `DGS2`, `T10Y2Y`, `BAMLH0A0HYM2` (HY OAS), `BAMLC0A0CM` (IG OAS), `DTWEXBGS` (dollar), `DCOILWTICO`, `VIXCLS`, `WALCL`, `RRPONTSYD`, `WTREGEN`, `NASDAQCOM`
- **BLS API v2:** `https://api.bls.gov/publicAPI/v2/timeseries/data/` (free key, 500 queries/day)
- **BEA API** (GDP), **Treasury FiscalData API** (daily TGA), **Atlanta Fed GDPNow** (free nowcast)
- **FOMC calendar:** `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm`
- **EIA API** (oil/inventories, free key)

### Positioning / flows
- **Short interest (bi-monthly):** `https://www.nasdaqtrader.com/Trader.aspx?id=ShortInterest`
- **FINRA daily short-sale volume:** `https://cdn.finra.org/equity/regsho/daily/` (CNMSshvol{YYYYMMDD}.txt)
- **Cboe market statistics** (volume, put/call, delayed options): `https://www.cboe.com/us/options/market_statistics/`
- **OCC volume/OI statistics** (free)
- **ETF shares outstanding / daily holdings:** issuer sites (iShares, SPDR, Vanguard) publish daily CSVs
- **ICI weekly fund flow estimates** (free)
- **S&P DJI index-change press releases**; **FTSE Russell recon schedule and preliminary lists**

### Events / legal / regulatory
- **Federal Register API:** `https://www.federalregister.gov/api/v1/documents.json` — structured, timestamped rules, tariffs, notices. Under-used.
- **Congress.gov API** (bill status), **OFAC SDN list**, **BIS Entity List** (via Federal Register)
- **Stanford Securities Class Action Clearinghouse:** `https://securities.stanford.edu` (free)
- **openFDA API** + **ClinicalTrials.gov API** (free, structured, includes completion dates)

### Sentiment / attention
- **GDELT 2.0:** free global news volume + tone, 15-minute updates
- **Wikipedia Pageviews API** (attention proxy, free)
- **Reddit API** free tier; **Google Trends** (unofficial)
- **Finnhub** free tier: 60 calls/min, includes recommendation trends and news (20-min delay, limited history)
- **Alpha Vantage:** 25 requests/day free — too thin for production

### Prices
- **Stooq** free EOD CSV; **yfinance** (unofficial, breaks often, ToS-grey); broker APIs (IBKR, Alpaca) for real data
- **Crypto:** Binance / Bybit / **Hyperliquid** public REST + WS — funding rates, OI, order book, trades. Free, complete, real-time. **The best free market data of any asset class.**
- **DefiLlama API** (unlocks, TVL, stablecoin flows), **CoinGecko** free tier

### Research / factor benchmarks
- **Kenneth French Data Library** (factor returns, free)
- **global-q.org** (Hou–Xue–Zhang q-factors, free)
- **Geopolitical Risk Index:** `https://www.matteoiacoviello.com/gpr.htm` — monthly GPR **and daily GPRD**, free CSV
- **Economic Policy Uncertainty:** `https://www.policyuncertainty.com`

### Known gaps (no good free source)
1. **Borrow fee / utilization** — the highest-value missing dataset in this document.
2. **Analyst consensus (IBES-equivalent)** — blocks the cleanest PEAD implementation.
3. **Tick/TAQ with sub-penny flags** — blocks the BJZZ retail-flow signal.
4. **Point-in-time index constituents** — every long-horizon backtest is survivorship-contaminated without it.
5. **Historical full options chains with OI** — blocks proper GEX backtesting (only forward-collection is free).

---

## 15. SOURCES

**Factor decay / replication / costs**
- McLean & Pontiff, *Does Academic Research Destroy Stock Return Predictability?* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623 · https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365
- Hou, Xue & Zhang, *Replicating Anomalies* — https://www.nber.org/system/files/working_papers/w23394/w23394.pdf · https://academic.oup.com/rfs/article-abstract/33/5/2019/5236964
- Novy-Marx & Velikov, *A Taxonomy of Anomalies and Their Trading Costs* — https://www.nber.org/system/files/working_papers/w20721/w20721.pdf
- *Not All Factors Crowd Equally: Modeling, Measuring, and Trading on Alpha Decay* — https://arxiv.org/pdf/2512.11913

**Earnings / PEAD / announcement effects**
- Fink, *A Review of the Post-Earnings-Announcement Drift* — https://static.uni-graz.at/fileadmin/sowi/Working_Paper/2020-04_Fink.pdf
- https://www.sciencedirect.com/science/article/pii/S2214635020303750
- *Warp Speed Price Moves: Jumps after Earnings Announcements* — https://www.sciencedirect.com/science/article/abs/pii/S0304405X25000182 · https://arxiv.org/pdf/2601.08962
- Grégoire, *How is Earnings News Transmitted to Stock Prices?* — https://onlinelibrary.wiley.com/doi/full/10.1111/1475-679X.12394
- Lyle, Stephan & Yohn, *Processing Time and the Speed of the Market Response* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3064160
- Frazzini & Lamont, *The Earnings Announcement Premium and Trading Volume* — https://www.nber.org/system/files/working_papers/w13090/w13090.pdf
- Savor & Wilson, *Earnings Announcements and Systematic Risk* — https://faculty.wharton.upenn.edu/wp-content/uploads/2012/04/Draft20111215p_edited.pdf

**Corporate events**
- Ikenberry, Lakonishok & Vermaelen, *Market Underreaction to Open Market Share Repurchases* — https://ideas.repec.org/p/nbr/nberwo/4965.html
- *Repurchases after being well known as good news* — https://www.sciencedirect.com/science/article/abs/pii/S0929119919309368
- Michaely, Thaler & Womack, *Price Reactions to Dividend Initiations and Omissions* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=420313
- Ikenberry & Ramnath, *Underreaction* (splits) — http://www.econ.yale.edu/~shiller/behfin/2000-05/ikenberry.pdf
- Field & Hanka, *The Expiration of IPO Share Lockups* — https://onlinelibrary.wiley.com/doi/10.1111/0022-1082.00334 · http://www.snifferquant.com/docs/Studies/IPO/3rd%20Party%20studies/The%20expiration%20of%20IPO%20share%20lockups.pdf
- SEO announcement effects — https://www.sciencedirect.com/science/article/abs/pii/S0929119908000291 · https://www.mdpi.com/2227-7072/9/3/36
- Holthausen & Leftwich / rating-change asymmetry — https://link.springer.com/article/10.1007/s11142-020-09573-6 · https://www.tandfonline.com/doi/full/10.1080/16081625.2018.1481756
- M&A returns — https://www.brattle.com/wp-content/uploads/2017/10/7404_returns_to_acquirers_of_public_and_subsidiary_targets.pdf · https://www.sciencedirect.com/science/article/abs/pii/S1042443123001336
- M&A run-up / leakage (Keown–Pinkerton lineage) — https://repub.eur.nl/pub/130185/Repub_130185_O-A.pdf · https://arxiv.org/pdf/2012.11594
- Securities class actions — https://www.sciencedirect.com/science/article/abs/pii/S1386418123000666 · https://securities.stanford.edu/resources-academic.html
- CEO turnover — https://www.sciencedirect.com/science/article/abs/pii/S0929119921000043 · http://arc.hhs.se/download.aspx?MediumId=1426
- Clinical trials / FDA — https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0071966 · https://pmc.ncbi.nlm.nih.gov/articles/PMC9439234/ · https://www.sciencedirect.com/science/article/abs/pii/S106297690600007X

**Insiders**
- Cohen, Malloy & Pomorski (routine vs opportunistic) / Lakonishok & Lee lineage — https://www.researchgate.net/publication/5216856_Are_Insider_Trades_Informative
- https://arxiv.org/html/2602.06198v1 (microcap insider purchases) · https://arxiv.org/html/2602.17890 (Form 144 vs Form 4)
- https://blog.quantinsti.com/sec-form-4-insider-trading-python-event-study/

**Sector / network**
- Cohen & Frazzini, *Economic Links and Predictable Returns* — https://pages.stern.nyu.edu/~afrazzin/pdf/Economic%20Links%20and%20Predictable%20Returns%20-%20Cohen%20and%20Frazzini.pdf
- Intra-industry information transfer — https://care-mendoza.nd.edu/assets/293764/hann_kim_zheng_rast_oct2018.pdf · https://www.sciencedirect.com/science/article/abs/pii/S016541012100015X
- Molchanov, *The myth of business cycle sector rotation* — https://onlinelibrary.wiley.com/doi/full/10.1002/ijfe.2882
- Industry momentum death / factor momentum — https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2018/03/Juhani.pdf

**Macro**
- Bernanke & Kuttner via Bauer & Swanson, *A Reassessment of Monetary Policy Surprises and High-Frequency Identification* — https://www.nber.org/system/files/working_papers/w29939/w29939.pdf · https://www.michaeldbauer.com/files/mps.pdf
- CPI asymmetry 2021–2025 — https://www.tandfonline.com/doi/full/10.1080/13504851.2026.2624038
- CME, *Economic Indicators That Most Impact Markets* — https://www.cmegroup.com/insights/economic-research/2025/economic-indicators-that-most-impact-markets.html
- LSEG, *How do economic surprises impact the yield curve?* — https://www.lseg.com/en/insights/data-analytics/how-economic-surprises-impact-yield-curve
- Kilian & Park lineage (oil shock decomposition) — https://www.sciencedirect.com/science/article/abs/pii/S0275531918303131 · https://gattonweb.uky.edu/faculty/herrera/documents/HKR_JEPO.pdf
- Gilchrist & Zakrajšek, *Credit Spreads and Business Cycle Fluctuations* — https://mfm.uchicago.edu/wp-content/uploads/2020/07/Gilchrist_Zakrajsek_Credit-Spreads-and-Business-Cycle-Fluctuations-UPDATED.pdf
- Dollar / EPS sensitivity — https://www.spglobal.com/spdji/en/documents/research/research-the-impact-of-the-global-economy-on-the-sp-500.pdf · https://www.hartfordfunds.com/insights/market-perspectives/global-macro-analysis/dollar-dynamics-exploring-the-impact-of-dollar-trends.html

**Policy / geopolitics**
- Liberation Day tariff event studies — https://www.sciencedirect.com/science/article/pii/S1544612325013376 · https://www.sciencedirect.com/science/article/abs/pii/S016517652500624X · https://www.sciencedirect.com/science/article/pii/S0165176526001412
- Antitrust — https://www.networklawreview.org/wp-content/uploads/2017/02/Reputational-Penalties.pdf · https://www.sciencedirect.com/science/article/abs/pii/S0144818815000721 · https://link.springer.com/article/10.1007/s11151-025-10035-z
- Export controls / Entity List — https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1096.pd · https://www.sciencedirect.com/science/article/abs/pii/S0313592626000020
- Caldara & Iacoviello, *Measuring Geopolitical Risk* — https://www.federalreserve.gov/econres/ifdp/files/ifdp1222.pdf · data: https://www.matteoiacoviello.com/gpr.htm
- 2024 US election event studies — https://www.sciencedirect.com/science/article/abs/pii/S1544612325017702 · https://www.sciencedirect.com/science/article/pii/S1062940826000136 · https://www.mdpi.com/1911-8074/19/3/191

**Flows / positioning / options**
- Greenwood & Sammon, *The Disappearing Index Effect* — https://www.nber.org/system/files/working_papers/w30748/w30748.pdf · https://alphaarchitect.com/disappearing-index-effect/
- Madhavan, *The Russell Reconstitution Effect* — https://www.hillsdaleinv.com/uploads/The_Russell_Reconstitution_Effect,_Ananth_Madhaven,_Financial_Analysts_Journal,_JulyAugust_2003,_Pages_51-64.pdf
- *Evidence of Crowding on Russell 3000 Reconstitution Events* — https://arxiv.org/pdf/2006.07456
- Gabaix & Koijen, *The Inelastic Markets Hypothesis* — https://www.nber.org/system/files/working_papers/w28967/w28967.pdf
- Boehmer, Jones, Zhang & Zhang, *Tracking Retail Investor Activity* — https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.13033 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2822105
- Rapach, Ringgenberg & Zhou, *Short Interest and Aggregate Stock Returns* — https://www.sciencedirect.com/science/article/abs/pii/S0304405X16300320
- Asquith/Boehmer lineage, short interest × institutional ownership — https://www.sciencedirect.com/science/article/abs/pii/S0304405X05001170
- Drechsler & Drechsler, *The Shorting Premium and Asset Pricing Anomalies* — https://www.nber.org/system/files/working_papers/w20282/w20282.pdf
- Barbon & Buraschi, *Gamma Fragility* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3725454 · https://tashfeenomran.com/DB/Research%20Papers/Gamma%20Fragility.pdf
- Ni, Pearson & Poteshman, *Stock Price Clustering on Option Expiration Dates* — https://www.sciencedirect.com/science/article/abs/pii/S0304405X05000577
- Cboe, *0DTE Index Options and Market Volatility* — https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf · https://www.cboe.com/insights/posts/0-dt-es-decoded-positioning-trends-and-market-impact
- 13F cloning — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5399672 · http://wp.lancs.ac.uk/fofi2020/files/2020/04/FoFI-2020-090-Farouk-Jivraj.pdf

**Market structure / session**
- Lachance, *Night trading: Lower risk but higher returns?* — https://onlinelibrary.wiley.com/doi/full/10.1002/rfe.1180
- Bogousslavsky, *The cross-section of intraday and overnight returns* — https://www.sciencedirect.com/science/article/abs/pii/S0304405X21000854
- Elm Wealth, *Night Moves: Is the Overnight Drift the Grandmother of All Market Anomalies?* — https://elmwealth.com/wp-content/uploads/2026/04/Elm-Night-Moves-Overnight-Drift.pdf
- SEC DERA, *"Limit Up-Limit Down" Pilot Plan and Extraordinary Transitory Volatility* — https://www.sec.gov/files/marketstructure/research/dera_wp_luld_and_extraordinary_transitory_volatility.pdf
- Microcap capacity — https://www.osam.com/Commentary/microcaps-factor-spreads-structural-biases-and-the-institutional-imperative · https://acuitasinvestments.com/wp-content/uploads/2025/09/Acuitas-The-Case-for-Microcap_2025.pdf

**Sentiment**
- Womack (1996) lineage / Barber et al. (2001) — https://www.nber.org/system/files/working_papers/w14971/w14971.pdf · https://www.anderson.ucla.edu/documents/areas/fac/accounting/trueman_ratings.pdf
- Tetlock, *Giving Content to Investor Sentiment* — https://business.columbia.edu/sites/default/files-efs/pubfiles/3097/Tetlock_Media_Sentiment_JF.pdf
- *Dumb money? Social network attention herding, sentiment, and markets* — https://www.sciencedirect.com/science/article/pii/S2405918825000212
- *Social media attention and retail investor behavior: Evidence from r/wallstreetbets* — https://www.sciencedirect.com/science/article/pii/S1057521924006537
- *From Text to Alpha: Can LLMs Track Evolving Signals in Corporate Disclosures?* — https://arxiv.org/html/2510.03195v5

**Event-study methodology**
- Kothari & Warner, *Econometrics of Event Studies* — https://www.jufinance.com/mag/dba5/event_study_chapter_1_2008_vol_1.pdf
- Dutta, *Measuring long-run security price performance: a review* — https://www.businessperspectives.org/images/pdf/applications/publishing/templates/article/assets/6550/imfi_en_2015_02_Dutta.pdf
- *A Powerful Testing Procedure of Abnormal Stock Returns* — https://www.efmaefm.org/0efmameetings/efma%20annual%20meetings/2013-Reading/papers/EFMA2013_0407_fullpaper.pdf

**Crypto**
- Kim, *The 72-Hour Shock? Preliminary Evidence from 52 Token Unlock Events on Binance* — https://papers.ssrn.com/sol3/Delivery.cfm/6632838.pdf?abstractid=6632838
- BIS Working Paper 1087, *Crypto carry* — https://www.bis.org/publ/work1087.pdf
- *Institutional Adoption and Correlation Dynamics: Bitcoin's Evolving Role* — https://arxiv.org/pdf/2501.09911
- *The Impact of Bitcoin ETF Approval on Bitcoin's Hedging Properties* — https://arxiv.org/pdf/2512.12815
- *From Flows to Value: Cointegration Between Bitcoin Spot ETF Assets and Bitcoin Price* — https://www.researchgate.net/publication/398763174_From_Flows_to_Value_Cointegration_Between_Bitcoin_Spot_ETF_Assets_and_Bitcoin_Price
- *Exploring risk and return profiles of funding rate arbitrage on CEX and DEX* — https://www.sciencedirect.com/science/article/pii/S2096720925000818

**Data sources**
- https://github.com/jeff3388/awesome-financial-data-apis
- https://qveris.ai/guides/free-financial-api-comparison/

---

## 16. THINGS I COULD NOT PIN DOWN (honest gaps)

1. **A canonical bps figure for the earnings announcement premium.** Frazzini–Lamont establish it is large and robust and tied to volume; I could not verify a single agreed magnitude. Do not hardcode one.
2. **A per-standard-deviation equity coefficient for the GPR index.** The paper reports "short-lived but significant"; any specific "X% per SD" number is likely sample-specific.
3. **Peer-reviewed magnitudes for vanna and charm spot feedback.** Every number I found was vendor-produced. Gamma has Barbon–Buraschi; vanna/charm do not have an equivalent.
4. **A clean bps-per-100k-surprise coefficient for NFP.** The literature confirms the yield relationship and the regime-dependent equity sign but I found only illustrative day-moves (~7 bp, ~20 bp), not an estimated elasticity.
5. **The exact per-quarter units of the "SUE spread fell from ~5% to ~3%" claim.** The direction of the decay is well established (Martineau's zero-for-large-caps result is the solid anchor); the units on that specific figure are ambiguous in the source.
6. **Borrow fee / utilization free data.** No source found. This is the biggest practical blocker for anything short-side.
7. **The 13F cloning "24.3% annualized" figure is almost certainly contaminated by ex-post top-quartile selection.** I have reported it with that caveat rather than treating it as an effect size.
