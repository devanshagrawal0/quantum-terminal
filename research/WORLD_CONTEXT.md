# THE WORLD LAYER

**Everything outside pure market data that determines what happens to prices.**

Research dossier for a trading intelligence system that must reason about cause and effect across the whole world — not just the US, not just crypto.

Compiled 2026-09-02. Every claim below is either sourced (see §SOURCES) or explicitly flagged as a design opinion.

---

## 0. THE CORE THESIS

A price feed tells you *what happened*. The world layer tells you *why it happened* and *what is scheduled to happen next*.

Three structural facts drive the whole design:

1. **Most large moves are caused by objects the current system does not model.** A jurisdiction changed a rule. A strait closed. A CEO said a sentence. A rival shipped a product. None of these are ticks.
2. **A large fraction of the world's market-moving events are known in advance.** FOMC dates for 2026 were published in 2025. BoJ's 2026 meeting schedule was published 2025-07-31. Earnings dates are confirmed weeks ahead. Index rebalances are announced 2–3 weeks ahead. This is not a news feed problem — it is a *calendar* problem, and a calendar is a fundamentally different data structure (see §C).
3. **The interesting alpha is in second and third-order effects**, because first-order effects are priced in seconds by faster systems. The edge is in the chain: *China restricts dysprosium exports → magnet costs rise → EV motor BOM rises → margin guidance cut two quarters later → the auto OEM misses → its lithium supplier misses.* That chain is a graph traversal, not a regression.

**Design consequence:** the system needs a *world state graph* with first-class `Jurisdiction`, `Law`, `ScheduledEvent`, `Company`, `Facility`, `Commodity`, `RivalryEdge`, and `CausalLink` entities. Section §F specifies them.

---

# A. GEOGRAPHY / COUNTRY / CONTINENT

## A1. Politics of each country — how political events transmit to markets

**What it is.** Political events change (a) expected policy, (b) expected property rights, (c) expected risk premium demanded by foreign capital. These are three distinct channels and they have different horizons.

**Transmission mechanisms — the actual causal paths:**

| Channel | Mechanism | Speed |
|---|---|---|
| **Policy expectation** | Election/appointment changes expected fiscal or monetary path → repricing of the sovereign curve → discount rate on every domestic asset | minutes (headline) to weeks (curve reprices) |
| **Risk premium / capital flight** | Perceived expropriation, capital-control, or default risk → foreign investors demand higher yield → currency depreciates → local equities fall in USD terms even if flat in local terms | hours to months |
| **Sanctions / exclusion** | State A designates entity B → counterparties must unwind → forced selling irrespective of fundamentals | minutes to days |
| **Regulatory capture / sector targeting** | Government targets a sector (tech crackdown, energy windfall tax, mining royalty) → that sector's terminal margin assumption is cut | days to quarters |
| **War / conflict** | Physical destruction or blockade of production/transport → supply curve shifts → commodity spot > forward (backwardation) | minutes to years |
| **Leadership instability** | Coup, impeachment, sudden resignation → uncertainty premium → vol up, correlation up, carry unwinds | minutes to weeks |

**Real historical examples (verified):**

- **Japan, 2024-07-31 → 2024-08-05.** BoJ raised the policy rate from ~0–0.1% to ~0.25%. Combined with a soft US payroll print on 2024-08-02, the US–Japan rate differential narrowed. The Nikkei-225 fell ~20% over 4 sessions; the 2024-08-05 single-day drop of 12.4% exceeded Black Monday 1987. S&P 500 −6% in three days, VIX ~65. **Mechanism: leveraged short-yen carry books, often paired against US tech longs, had to cover both legs simultaneously.** This is the canonical "one central bank's 15bp move causes a global cross-asset crash" case, and it is *purely* a world-layer event — nothing in the price data of NVDA predicted it. Horizon: 3 days for the crash, ~4 weeks to fully retrace.
- **China, 2025-04 and 2025-10.** April 2025: seven heavy rare earths (incl. dysprosium, terbium) placed under export licensing. October 2025: controls extended to rare-earth *processing technology* plus extraterritorial claim over any foreign product containing trace Chinese-origin REE. November 2025: controls temporarily suspended for one year (to 2026-11-10) after a Trump–Xi meeting — framed as a tactical pause, not a policy reversal. **Mechanism: licensing = a quantity constraint on an input with ~no short-run substitute.** European dysprosium/terbium traded up to ~6× Chinese domestic price at peak. Horizon: price spike in weeks, corporate margin impact 2–4 quarters later.
- **China antimony, 2024.** Export controls took antimony from ~$1,400/t to ~$38,000/t (≈2,600%); US shipments fell ~97%. USGS estimated the gallium+germanium ban alone at ~$3.4bn US economic damage, ~half in semiconductors.
- **India, 2022–present.** 30% flat tax on VDA gains + 4% cess (≈31.2% effective) + **1% TDS on every transaction's gross value**. Domestic daily crypto volume fell from ~$2.2bn to under $500m. KoinX put ~72.7% of Indian volume offshore in FY2025; other estimates >90%, ~$6.1bn/yr capital outflow. **Mechanism: a per-transaction tax destroys market-making economics, so liquidity leaves the jurisdiction rather than the asset.** This is the cleanest proof that *jurisdiction is a first-class determinant of where liquidity lives*, and it matters directly for a perp venue.

**Continent-by-continent political transmission cheatsheet (design opinion + sourced anchors):**

- **North America (US, CA, MX).** US: the dominant global policy exporter. Fed + Treasury + Congress + SEC/CFTC + BIS(Commerce) export controls + OFAC. MX: Banxico paused cuts after inflation ticked to 3.92% in early 2026; peso anchored by high real rates and USMCA. CA: BoC, energy/pipeline politics.
- **Europe (EU, UK, CH, Nordics, CEE).** EU acts through *regulation as market structure* (MiCA, GDPR, DMA/DSA, CBAM). UK: BoE MPC dates published a year ahead (2026 dates announced Dec 2024). CH: SNB, safe-haven CHF bid on any European stress. Energy dependence on non-EU gas is the standing macro vulnerability.
- **Asia — East.** CN (PBoC, MOFCOM export controls, CSRC, delisting/VIE risk), JP (BoJ — the world's carry funding currency), KR (KRX, capital controls → kimchi premium), TW (**the single largest concentrated physical risk on earth for equities**: TSMC has >90% of ≤7nm and ~90% of ≤3nm capacity, >90% of advanced-node capacity physically in Taiwan; Arizona Fab 21 Ph2 not at volume until 2H2027+, 2nm not before ~2030).
- **Asia — South/SE.** IN (RBI, SEBI, and the tax regime above; NSE/BSE session), ID/TH/VN/PH (commodity + manufacturing beta), SG (regional booking centre for crypto/FX; jurisdiction of many exchange entities).
- **Middle East.** SA/AE/QA/IR/IL. Oil supply politics + the Strait of Hormuz. Sovereign wealth funds are marginal buyers in global equity and increasingly crypto/AI infra.
- **Africa.** Currency + eurobond channel dominates. Egypt's pound lost >2/3 of value vs USD since early 2022; Nigeria's naira −49.4% in a year; NGN eurobond Dec-2024 (~$1.7bn) oversubscribed 5.4× at 9.625%/10.375%. Kenya, Ghana, Zambia, Ethiopia, Zimbabwe all in the same regime class. **Mechanism to global markets: frontier eurobond spreads are a risk-appetite thermometer, and devaluation events destroy USD earnings of multinationals with local operations.**
- **Latin America.** BR: Selic held at 15% into early 2026 after +275bp in 2025; JPM projected ~250bp of cuts through 2026. AR: monthly inflation 12.8% pre-Milei → 2.1% by late 2025. ECLAC/World Bank/IMF converge on ~2.2–2.3% regional 2026 GDP. **Mechanism: LatAm is the highest-carry, highest-beta expression of global risk appetite; when the Fed is expected to cut, LatAm FX rallies first.**
- **Oceania.** AU (RBA 2026 dates published: Feb 2–3, Mar 16–17, May 4–5, Jun 15–16, Aug 10–11, Sep 28–29, Nov 2–3, Dec 7–8) — the pure China-demand proxy via iron ore and the AUD; NZ (RBNZ) — dairy + a clean small-open-economy rate signal.

**Horizon summary:** headline → 30s–5min repricing; positioning unwind → 1–5 days; policy implementation → weeks–quarters; structural relocation of capital → years.

**Free data:**
- **GDELT 2.0** — `api.gdeltproject.org/api/v2/doc/doc` (DOC 2.0 fulltext, 15-min updates), GEO 2.0, TV 2.0; bulk Events/Mentions/GKG at `data.gdeltproject.org`, 15-min files; also mirrored in Google BigQuery. Free, no key. This is the single best global political-event firehose available at zero cost.
- **ACLED** — `acleddata.com` / `developer.acleddata.com`. Free registration; disaggregated political violence + protest events with lat/lon, actors, fatalities. API access requires the Research/Partner tier; open myACLED gives aggregated real-time.
- **World Bank Indicators API** — `https://api.worldbank.org/v2/country/all/indicator/<CODE>?format=json`. **No key required.**
- **IMF / OECD / Eurostat / BIS / FRED aggregated** — **DBnomics** (`api.db.nomics.world`) aggregates 90+ official providers including IMF, OECD, Eurostat, ECB, World Bank, BIS, Fed, BLS. Free.
- **Cloudflare Radar** — `api.cloudflare.com/client/v4/radar/...` (`/annotations/outages`, `/traffic_anomalies`). Free API key; CC BY-NC 4.0. Detects national internet shutdowns and traffic anomalies — an excellent *leading* indicator of coups, protests, and censorship events.

**DB representation:** `political_event(id, jurisdiction_id, type ENUM(election, coup, sanction, protest, conflict, leadership_change, policy_announcement), start_ts, end_ts, severity, actors[], source_ids[], geo POINT/POLYGON)` → edges to `Jurisdiction`, `Company` (via exposure), `Commodity`.

---

## A2. Geography — where things physically are

**What it is.** Markets price claims on physical things that sit at specific coordinates. When you know *where* production and transport physically are, you can convert a geographic event into a supply-curve shift mechanically.

**The categories that actually matter:**

### Maritime chokepoints (verified EIA/IMF numbers)
| Chokepoint | Oil throughput | Why it matters |
|---|---|---|
| **Strait of Malacca** | 23.2 mb/d (H1 2025); ~29.1% of global maritime oil trade | Busiest oil chokepoint; the China/Japan/Korea energy artery |
| **Strait of Hormuz** | 20.9 mb/d (H1 2025); ~1/5 of global oil consumption | No practical bypass for most Gulf crude; the highest-convexity closure risk |
| **Suez Canal + SUMED** | 4.9 mb/d (H1 2025) | Gulf → Europe/N.America; Red Sea disruption reroutes via Cape (+~10–14 days) |
| **Bab el-Mandeb** | 4.2 mb/d (H1 2025) | Gate to the Red Sea; Houthi attack surface |
| **Panama Canal** | (container/LNG dominant) | Drought-driven transit rationing is a *climate* variable that becomes a *freight rate* variable |
| **Taiwan Strait / Bashi Channel** | — | Not oil; **semiconductor + container** exposure |
| **Turkish Straits, Danish Straits, Cape of Good Hope** | — | Russian crude and reroute capacity |

Hormuz + Malacca combined = **~57% of all seaborne oil trade**.

### Other physical geography classes to model
- **Fabs.** TSMC Hsinchu/Tainan (>90% of world advanced-node), Samsung Pyeongtaek, Intel Arizona/Ohio, SK Hynix Icheon/Wuxi, Micron Hiroshima/Taichung. ASML Veldhoven is a **single-site global monopoly** on EUV.
- **Mines & refineries.** Copper: Chile (Escondida), Peru, DRC. Lithium: Australia (Greenbushes), Chile (Atacama), Argentina. Cobalt: DRC (~70%+). Rare earths: China mining ~60–70% but **separation/processing ~85–90%** — *processing is the real chokepoint, not the ore.* Nickel: Indonesia. Uranium: Kazakhstan (Kazatomprom).
- **Pipelines & LNG.** Druzhba, Nord Stream (destroyed), TurkStream, Power of Siberia; LNG terminals: Sabine Pass, Ras Laffan, Gorgon, Yamal.
- **Ports.** Shanghai/Ningbo, Singapore, Rotterdam, LA/Long Beach, Jebel Ali, Santos.
- **Data centres & power.** Northern Virginia (Ashburn), Dublin, Singapore, Loudoun; and now the *grid interconnect queue* is the binding constraint on AI capex — a physical-geography variable that moves utility, turbine, and transformer equities.
- **Submarine cables.** Red Sea cable cluster, SEA-ME-WE, transatlantic. A cable cut = latency + regional internet degradation = a real, observable, tradable event (see Cloudflare Radar).

**Real examples:**
- **Red Sea / Bab el-Mandeb 2023–24.** Attacks → carriers reroute via Cape of Good Hope → container freight rates multiply → 2–3 month lag into European retail inventory and margins.
- **Hormuz escalation, June 2025.** Insurance/war-risk premia and tanker rates repriced within hours of headlines; IMF PortWatch daily transit counts are the primary public verification instrument.
- **DeepSeek, 2025-01-27.** Not a chokepoint but a geography-adjacent shock: NVDA −17%, ≈$589–600bn market cap erased in one session; Broadcom −17%, ASML −7%. See §E24.

**Horizon:** shipping/insurance repricing minutes–hours; freight rates days–weeks; physical inventory effects 4–12 weeks; capex relocation years.

**Free data:**
- **IMF PortWatch** — `portwatch.imf.org`. **The single best free physical-trade dataset in existence.** Daily chokepoint transit calls + preliminary transit trade volume for **28 major chokepoints**, plus ~1,600 ports. AIS/satellite derived (IMF + Oxford ECI). Refreshed **weekly, Tuesdays ~09:00 ET**, with daily granularity. Vessel classes broken out: container, dry bulk, general cargo, RoRo, tanker. Dataset id for daily chokepoints: `42132aa4e2fc4d41bdaf9a445f688931_0`; `portid` values are `chokepoint1..chokepoint28`.
  **Exact free REST endpoint (no key):**
  ```
  https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query
    ?where=portid='chokepoint1'&outFields=*&f=json&maxRecordCountFactor=5&returnCountOnly=FALSE&resultOffset=0
  ```
  Same pattern with `Daily_Port_Activity_Data_and_Trade_Estimates` for ports. Paginate with `resultOffset`. This is the verification instrument for every §A2 chokepoint claim — do not trust a headline about a strait closing without checking the transit count.
- **EIA** — `api.eia.gov` (free key). World Oil Transit Chokepoints special topic page carries the authoritative throughput series.
- **OpenStreetMap Overpass API** — `overpass-api.de/api/interpreter`. Free. Query `man_made=pipeline`, `landuse=quarry`, `industrial=port`, `power=plant`, `telecom=...` to build the physical asset layer with real coordinates.
- **AIS free tiers** — `aisstream.io` (free API key, websocket), Norwegian Coastal Administration open AIS. (MarineTraffic/Spire/Kpler are the paid tier.)
- **NASA FIRMS** (fires), **USGS earthquake API** `earthquake.usgs.gov/fdsnws/event/1/query` (free, no key), **NOAA/NHC** (hurricanes) — for physical disruption to facilities with known coordinates.
- **USGS Mineral Commodity Summaries** — free PDFs/CSV; country production shares per commodity.

**DB representation:** `facility(id, type ENUM(fab, mine, refinery, port, pipeline_node, terminal, datacenter, cable_landing), geo POINT, country_id, operator_company_id, capacity, capacity_unit, commodity_id, share_of_world_supply)` and `chokepoint(id, name, geo LINESTRING, throughput_series_id, bypass_cost_days, commodities[])`. Then `facility_disruption(facility_id, event_id, pct_capacity_lost, start, expected_end)`.

---

## A3. Jurisdiction exposure — where a company is legally based

**What it is.** A company has at least **five different "wheres"**, and they diverge constantly:
1. **Jurisdiction of incorporation** (legal home — Cayman, Delaware, Ireland, BVI, Marshall Islands)
2. **Jurisdiction of tax residence** (often different — Ireland/Netherlands/Singapore)
3. **Jurisdiction of listing** (NYSE/Nasdaq/HKEX/LSE — determines disclosure regime)
4. **Jurisdiction of operations / revenue** (where the cash is actually earned)
5. **Jurisdiction of regulatory control** (who can actually shut it down)

**Why it matters — the transmission mechanisms:**

| Risk | Mechanism | Example |
|---|---|---|
| **Delisting** | Listing regulator can force removal regardless of fundamentals | **HFCAA (2020):** SEC must ban trading if PCAOB cannot inspect audits for 3 consecutive years. Chinese ADRs repriced on *pure jurisdiction risk*, not earnings. |
| **VIE non-ownership** | Investors own a **Cayman holdco with contracts**, not equity in the Chinese operating company | Standard for Alibaba/Baidu/JD-class names; the contractual claim can be voided by PRC law |
| **Sanctions / entity listing** | Designation forces global counterparties to unwind | OFAC SDN, BIS Entity List, EU/UK lists |
| **Capital controls** | Cash exists but cannot be repatriated | Nigeria/Egypt FX backlogs; Korea's crypto controls (§A6) |
| **Tax regime change** | Post-tax cash flow changes with no operational change | Pillar Two 15% global minimum tax; India's 30%+1% TDS |
| **Licensing regime** | Right to operate is granted/revoked per jurisdiction | MiCA CASP authorisation; NYDFS BitLicense |
| **Legal recourse** | Bondholder/shareholder rights differ by governing law | NY-law vs local-law sovereign bonds price differently in a restructuring |

**Crypto-specific (directly relevant to a perp venue):** exchange entity domicile determines which users can be served, which stablecoins can be listed, and whether the venue can be geo-fenced. MiCA is the sharpest recent case — see §B9/§B13.

**Horizon:** headline/designation → minutes. Structural repricing of a whole cohort (e.g. "all China ADRs") → weeks to years, and it *does not mean-revert on earnings beats*.

**Free data:**
- **GLEIF LEI API** — `https://api.gleif.org/api/v1/lei-records?filter[entity.legalName]=...`. **Free, no registration, no key.** Returns legal name, **legal jurisdiction**, legal form, registered address, HQ address, entity status, BIC, **and the full parent/child ownership hierarchy** (`/direct-parents`, `/ultimate-parents`, `/direct-children`). This is the backbone for a jurisdiction graph. Demo at `api.gleif.org/demo`.
- **SEC EDGAR submissions API** — `https://data.sec.gov/submissions/CIK##########.json`. Free, no key, requires a descriptive `User-Agent` header. Gives `stateOfIncorporation`, `stateOfIncorporationDescription`, SIC code, addresses, tickers/exchanges, and the complete filing history.
- **SEC EDGAR full-text search** — `https://efts.sec.gov/LATEST/search-index?q=...&forms=8-K&dateRange=...`. Free, unauthenticated, JSON. Indexes filing bodies + exhibits from 2001 on; new filings searchable within minutes–hours.
- **Consolidated Screening List (CSL) API** — `https://data.trade.gov/consolidated_screening_list/v1/search` (developer.trade.gov key, free). Merges **eleven** US lists: BIS Entity List, Denied Persons, Unverified List, OFAC SDN, OFAC non-SDN, State ITAR Debarred, etc. **Updated hourly**, JSON, with fuzzy name search.
- **OFAC Sanctions List Service** — `ofac.treasury.gov/sanctions-list-service` (raw SDN/CONS in XML/CSV, free).
- **OpenSanctions** — `api.opensanctions.org` — consolidates OFAC + EU + UN + UK + PEPs into one schema. **Free for non-commercial; a data licence is required for business use.** Bulk files at `data.opensanctions.org`.
- **sanctions.network** — free JSON screening against OFAC SDN + UNSC + EU financial sanctions file.
- **Wikidata SPARQL** — `https://query.wikidata.org/sparql`. Free. Properties: P17 (country), P159 (HQ), P1454/P1454 legal form, P414 (stock exchange), P946/P249 (ISIN/ticker), P749 (parent org). Good for coarse global coverage where EDGAR does not reach (Asian/European issuers).

**DB representation:** this is the single highest-value schema addition.
```
jurisdiction(id, iso2, iso3, name, parent_id /*EU→member*/, currency, timezone_default,
             capital_controls_level, sanctions_regime, tax_regime_id)
company(id, lei, cik, name, ...)
company_jurisdiction(company_id, jurisdiction_id, role ENUM(
    incorporation, tax_residence, listing, primary_operations, regulator),
    since, until, evidence_url)
company_revenue_geo(company_id, jurisdiction_id, fiscal_period, revenue, pct_of_total)
```
The `role` enum is the whole point: a query like *"which listed names have `incorporation=KY` AND `primary_operations=CN` AND `listing=US`?"* instantly returns the HFCAA-exposed cohort **before** the next headline.

---

## A4. Every continent and country accounted for

Design rule: **the country table is the root of the world graph and must be complete (ISO 3166 all ~249 entries), not a US-plus-friends list.** Attach to every country: exchanges, central bank, policy calendar, currency, tax regime, sanctions status, timezone(s), major listed issuers, commodity production shares, and chokepoint adjacency.

**Per-region "what actually transmits" (condensed, with the anchors already sourced above):**

- **Asia-Pacific developed:** JP (carry funding — the global leverage tap), KR (chaebol + memory + capital controls), TW (fabs, §A2), AU/NZ (China demand proxy), SG/HK (booking centres, HK is the CN→global equity gateway).
- **Asia emerging:** CN (policy is the market: PBoC RRR/LPR, MOFCOM export controls, CSRC listing rules, and the property/local-government-financing complex), IN (RBI + SEBI + the crypto tax regime; NSE is now a top-3 global derivatives venue by contracts), ID/VN/TH/MY/PH (supply-chain relocation beneficiaries).
- **Europe:** EU regulation is *extraterritorial by design* (MiCA, GDPR, CBAM, DMA) — an EU rule is a global rule for anyone serving EU users. ECB, BoE, SNB, Riksbank, Norges. Energy import dependency is the standing macro shock channel.
- **Middle East:** oil supply politics; Hormuz; SWFs (PIF, ADIA, QIA, Mubadala) as marginal global bidders; UAE/Bahrain as crypto-friendly licensing jurisdictions (VARA/ADGM) — directly relevant to venue domicile arbitrage.
- **Africa:** FX + eurobond channel (§A1); plus **commodity supply concentration** (DRC cobalt, South Africa PGMs/gold, Guinea bauxite, Zambia copper, Nigeria oil). Africa is under-modelled and over-determines several metals.
- **LatAm:** BR (Selic/Copom, iron ore, soy, Petrobras/Vale), MX (nearshoring + USMCA + remittances), CL/PE (copper, lithium), AR (the extreme-regime laboratory), CO/VE (oil).
- **Oceania:** AU/NZ as above; PNG/Pacific for nickel/LNG.

**Free data:** World Bank country API (no key), `restcountries.com` (free, ISO/currency/timezone/borders), IMF via DBnomics, BIS `bis.org/cbanks.htm` (full list of every central bank and monetary authority website — the canonical seed list for a global policy calendar crawler), BIS Data Portal `data.bis.org` (CBPOL = **central bank policy rates for all reporting countries**, free).

**DB representation:** `country` (ISO-complete) → `exchange` (MIC, ISO-10383) → `central_bank` → `policy_calendar`. Everything else foreign-keys into `country`.

---

## A5. Time zones — which session is awake

**What it is.** The 24h clock is a *structural* variable, not a cosmetic one. Liquidity, who is trading, and which risks are hedgeable all change by the hour.

**Mechanisms:**

1. **Session handoff = information handoff.** Asia opens, prices the US close + any overnight news; Europe opens and re-prices with more capital; US opens with the deepest book and usually sets the day's level. A shock during a thin session produces a *larger* price move for the same information because depth is lower.
2. **The overnight/intraday split is one of the largest documented anomalies in equities.** Lou, Polk & Skouras ("A Tug of War: Overnight versus Intraday Expected Returns", *JFE* 2019): essentially the entire long-run US equity risk premium accrued **overnight** (close→open), while the intraday (open→close) component averaged slightly negative. Momentum earns its premium almost exclusively overnight; value, profitability, investment, beta, idio-vol, issuance, accruals and turnover earn theirs **intraday and with the opposite sign overnight**. The NY Fed staff report "The Overnight Drift" (SR 917, Boyarchenko/Larsen/Whelan) documents the same in index futures. **Implication: any signal must be evaluated separately in the overnight and intraday buckets — collapsing them destroys the effect.**
3. **Crypto has no close, but it has *sessions* anyway.** Funding-rate resets, CME futures gaps (weekend gap), Asian-hours vs US-hours flow, and stablecoin mint/redeem windows all create clock structure. Hyperliquid funding is hourly — that is an 24×/day scheduled event that is trivially calendarable.
4. **Regional premium/discount.** Segmented markets with capital controls price the *same* asset differently:
   - **Korea — "kimchi premium".** Korean exchanges have traded BTC at persistent premia (peak ~20.8% on 2021-05-19). Cause: **capital controls + AML rules make the arbitrage leg (getting KRW out / USD in) slow, expensive, or illegal**, so the premium is a *price of the capital control*, not a mispricing. It went **negative** in Oct-2024. Foreign arbitrageurs captured most historical premium. Academic treatment: Nonlinear dynamics of the Kimchi premium (*Economic Modelling*, 2024); "The Kimchi premium and bitcoin-cashing outlets" (*Finance Research Letters*, 2022).
   - **Japan/India:** similar segmentation logic; India's TDS is a *transaction* tax that pushes flow to offshore venues (§A1), producing a persistent onshore/offshore basis.
   - **Equity ADR/ordinary premium:** the ADR vs local line diverges exactly when the local market is shut — that gap is the market's overnight opinion.
5. **Scheduled intraday fixes.** WM/Refinitiv 16:00 London FX fix, 15:00 JST Tokyo close, 15:30 CST China close, US 16:00 close + MOC imbalance publication (15:50), options expiry 4pm, index rebalance trades at the close.

**Real examples:** the 2024-08-05 Nikkei −12.4% happened while the US was asleep and the S&P could only respond at the US open; the Hormuz/Red Sea headlines repeatedly land in the Asian session because that is when Middle East business hours overlap Asian trading.

**Horizon:** minutes (session open), daily (overnight vs intraday split), persistent (regional premia can last months).

**Free data:**
- **IANA tzdata** (via `zoneinfo`/`pytz`) — the authoritative timezone + DST database; **DST transitions differ by country and must be handled, not hard-coded**.
- **`exchange_calendars`** (PyPI, `gerrymanoim/exchange_calendars`) — 50+ exchanges keyed by **ISO-10383 MIC** (`XNYS`, `XHKG`, `XKRX`, `XTKS`, `XNSE`, ...), with correct open/close, lunch breaks, early closes, holidays. `pandas_market_calendars` is the alternative. Free. **Caveat: holiday definitions are user-contributed — verify the exotic exchanges.**
- Per-exchange holiday pages (authoritative) + `leogregianin/stock-exchange-holidays` for cross-checking.
- Regional premium: compute directly from venue APIs — Upbit/Bithumb (KRW), Coinbase/Kraken (USD), WazirX/CoinDCX (INR) — plus a FX rate. All have free public REST tickers.

**DB representation:**
```
exchange(mic, name, country_id, tz, asset_class)
session(exchange_mic, date, open_ts_utc, close_ts_utc, lunch_start, lunch_end, is_early_close)
venue_price(asset_id, venue_id, ts, price, quote_ccy)
regional_basis(asset_id, venue_a, venue_b, ts, basis_pct, fx_rate_used)
```
Every returns computation should carry a `session_bucket ENUM(overnight, intraday, asia, europe, us)` column so the tug-of-war split is queryable by default.

---

## A6. Sentiment INSIDE a country vs global sentiment

**What it is.** Global (English) sentiment and domestic-language sentiment are *different variables*, and the gap between them is itself a signal. A stock can be hated on FinTwit and adored on Xueqiu.

**Mechanisms:**
- **Local retail is the marginal buyer in several markets.** KR retail (~high share of KRX turnover and historically the dominant force in altcoins), CN retail on A-shares, IN retail in F&O, JP retail in FX margin ("Mrs Watanabe" — a real, measurable carry-trade participant).
- **Information reaches local language first.** A Korean exchange listing announcement, a Chinese regulator's WeChat post, a Japanese Nikkei scoop, an Indian ET exclusive — all move price before the English wire.
- **Local platforms have distinct behaviour.** Korea's crypto community centres on **Naver Cafe** and Telegram and skews heavily to *altcoins listed on Korean CEXs* (a structural reason Korean listings pump specific tickers). China's is **Xueqiu** (largest investor community, cashtag-indexed, covers A-share/HK/US-listed-China) and **Weibo** (580M+ users). Japan: 5ch/Yahoo!掲示板, X. India: Telegram + YouTube + Moneycontrol forums.

**The tradeable construct:** `sentiment_divergence = local_sentiment(country, asset) − global_sentiment(asset)`. Historically the Korean-premium/Korean-sentiment complex has been a *late-cycle retail euphoria* marker; a negative kimchi premium (Oct-2024) coincided with local capitulation.

**Horizon:** hours to days for listing/announcement effects; weeks for retail-flow regimes.

**Free data (honest assessment — this is the weakest free tier):**
- **GDELT** covers **65+ languages** and gives per-article tone + themes with country attribution — the best free multilingual sentiment proxy that exists. `api.gdeltproject.org/api/v2/doc/doc?query=...&mode=timelinetone&format=json`.
- **Xueqiu** — public web endpoints work without login for cashtag search (third-party scrapers exist; rate-limit and ToS caution).
- **Weibo / Naver** — no usable free official API for this purpose. Naver restricts third-party access. **Paid:** FactSet "Xueqiu Analytics for China Retail Investor Sentiment" (6,000 A-share/HK/US-listed-China names) is the commercial answer.
- **Reddit** free API (rate-limited), **Telegram** public channels via MTProto (free), **X/Twitter** — effectively paid now.
- **Google Trends** (`pytrends`, free, unofficial) with `geo=KR`, `geo=IN`, `geo=JP` — the cheapest genuine per-country retail-attention proxy.
- **Venue-native proxies** are better than text: Upbit KRW volume share, Binance TR/ARS/NGN pair volumes, CoinDCX INR volume, KRX retail net-buy (published by KRX).

**DB representation:** `sentiment_reading(asset_id, jurisdiction_id, language, source_id, ts, tone, volume, method)` — **language and jurisdiction must be columns, not tags**, so divergence is a `GROUP BY`.

---

## A7. That country's laws

Covered structurally in §B, but the country-specific point: **law is a property of a jurisdiction that a company/asset is *exposed to* through the §A3 role graph.** The system must be able to answer "which of my positions are exposed to jurisdiction X's law changes, and through which role?" That is only possible if `company_jurisdiction.role` exists.

---

# B. LAW / REGULATION / POLICY

## B8. US federal law/rules and how they transmit

**Mechanisms, ranked by speed:**

1. **Enforcement action / designation** (OFAC SDN add, SEC/CFTC complaint, DOJ indictment) — *minutes*. Forced unwind, no discretion.
2. **Rule proposal → comment → final rule** (SEC/CFTC/Fed/OCC/Treasury). The **proposal** moves price, often more than the final rule, because the proposal is the surprise. Published in the **Federal Register** with a fixed lifecycle: NPRM → comment period → final rule → effective date. **This lifecycle is a state machine and should be modelled as one.**
3. **Legislation** (Congress) — slow, many veto points, but with observable stage transitions: introduced → committee → floor vote → other chamber → conference → signature. Prediction markets and the bill's stage are jointly informative.
4. **Court decisions** — binary and fast (e.g. a vacated rule).
5. **Executive orders / export controls** (BIS rules, EO) — fast and extraterritorial.
6. **Tax code changes** — slow but permanent, and they change the *after-tax* discount rate on every cash flow.

**Real examples:** HFCAA → mass repricing of an entire national cohort (§A3). BIS chip export controls → NVDA/AMD China revenue writedowns and a persistent "China-exposure" factor in semis. Spot Bitcoin ETF approval 2024-01-10 → §B13.

**Free data:**
- **Federal Register API** — `https://www.federalregister.gov/api/v1/documents.json?conditions[term]=...&conditions[type][]=RULE`. **Free, no key.** Types: Notice, Proposed Rule, Rule, Presidential Document. Also `/api/v1/public-inspection-documents.json` — **documents on public inspection *before* they hit the Register** (this is a genuine few-hours lead).
- **Congress.gov API v3** — `https://api.congress.gov/v3/bill/...` (free key via api.data.gov). Bills, amendments, votes, committees, CRS reports. JSON/XML.
- **GovInfo API** — `https://api.govinfo.gov/` (free key) for bulk bill status, CFR, US Code.
- **SEC** — `sec.gov/rules/` RSS, `efts.sec.gov` full-text, `data.sec.gov` submissions/XBRL frames. Free.
- **CFTC** — press releases RSS; **COT reports** released **Fridays 15:30 ET** for the prior Tuesday. Free official API on the CFTC public reporting environment (Socrata); free mirrors: FuturesBench (`futuresbench.com/api/` — static CDN CSV/JSON, no key, no rate limit, 107 markets back to 1986), `cot_reports` Python lib.
- **Regulations.gov API** (free key) — dockets and comments; comment volume/sentiment is a leading indicator of whether a rule survives.
- **FRED API** (free key) — `api.stlouisfed.org/fred/releases` gives the **release calendar** for every US macro series, i.e. *when the next print is scheduled*.

**DB representation:**
```
law_instrument(id, jurisdiction_id, kind ENUM(statute, regulation, rule_proposal,
   executive_order, enforcement_action, court_decision, guidance, tax_rule),
   title, citation, issuing_body_id, status ENUM(proposed, comment, final, effective,
   stayed, vacated, repealed), proposed_date, comment_close, final_date, effective_date,
   source_url, full_text_ref)
law_effect(law_id, target_type ENUM(sector, company, asset, commodity, jurisdiction),
   target_id, direction, expected_magnitude, confidence, rationale)
```
The `status` field with dates is what turns law into a *calendar* (see §C).

---

## B9. New laws anywhere in the world

**The general pattern:** every jurisdiction has (a) a gazette/official journal, (b) a regulator's rule feed, (c) a legislature's bill tracker. The architecture should be one generic crawler with per-jurisdiction adapters, not 200 bespoke integrations.

**Sources by region (free):**
- **EU:** EUR-Lex (`eur-lex.europa.eu`, SPARQL + REST, free), Official Journal RSS, ESMA/EBA registers, European Commission press.
- **UK:** `legislation.gov.uk` (free API, Atom/XML), FCA handbook feed, Bank of England.
- **China:** `gov.cn`, MOFCOM announcements (export controls appear here first), PBoC, CSRC, SAFE. Chinese-language; machine translation is mandatory. **No convenient API — HTML + RSS.**
- **Japan:** e-Gov 法令API (free), FSA press releases, BoJ.
- **India:** `egazette.gov.in`, RBI press releases (RBI has structured data on `dbie.rbi.org.in`), SEBI circulars.
- **Korea:** `law.go.kr` Open API (free key), FSC/FSS press.
- **Brazil:** Diário Oficial, CVM, BCB (`api.bcb.gov.br` — free, no key, excellent).
- **Global aggregator:** **GDELT** picks up regulatory news in 65+ languages and is the pragmatic first-pass detector; then confirm against the primary gazette.

**DB representation:** same `law_instrument` table, partitioned by `jurisdiction_id`. Add `law_source(jurisdiction_id, kind, url, format, adapter_name, poll_interval)` so new countries are *config*, not code.

## B10. New tax rules

**Mechanism.** Tax changes the after-tax cash flow and therefore the price with **no change in operations**. Three sub-types with different signatures:
- **Rate changes on income/gains** — repricing of terminal value; horizon weeks–quarters.
- **Transaction taxes (FTT, TDS, stamp duty)** — destroy *liquidity*, widen spreads, move volume to other venues; horizon **days**, and the effect is on volume and basis, not just price. India's 1% TDS is the textbook case (§A1): −77% domestic volume, ~$6.1bn/yr offshore.
- **Withholding / repatriation rules** — change where cash can go; affects buybacks/dividends.

**Other live examples:** OECD **Pillar Two 15% global minimum tax** (changes the value of Irish/Dutch/Singapore domiciles — a §A3 jurisdiction interaction); UK stamp duty on shares; windfall taxes on European energy 2022–23; US wash-sale rules **not** applying to crypto (a real December tax-loss-harvest seasonality in crypto that does not exist in equities).

**Free data:** OECD Tax Database + Pillar Two implementation tracker (free), IMF/World Bank tax data, national budget documents (India's Union Budget on 1 Feb is a *scheduled* annual crypto/equity tax event — put it on the calendar), Federal Register/IRS for the US, EUR-Lex for the EU.

**DB representation:** `tax_rule(id, jurisdiction_id, base ENUM(income, capital_gain, transaction, withholding, wealth, tariff), asset_class, rate, threshold, effective_from, effective_to, source_url)` + `tax_rule_effect` to sectors/assets. **Store `effective_from` in the future** — that is what makes it anticipatory.

## B11. Interest rate rules / central bank policy frameworks

**What it is.** Not just "the rate" but the **framework**: inflation target, reaction function, forward guidance regime, QE/QT balance-sheet path, FX intervention rules, reserve requirements, yield-curve control.

**Mechanisms:**
- **Rate level** → discount rate on all assets; carry differential drives FX.
- **Rate *path* (expectations)** → this is what actually moves markets; a hold with a hawkish dot plot moves more than a cut.
- **Balance sheet (QT/QE)** → duration supply and bank reserves → risk-asset liquidity. **This is the dominant crypto macro driver.**
- **FX intervention** → BoJ MoF interventions, PBoC daily fix, SNB.
- **Framework change** → e.g. BoJ ending YCC/NIRP; the *regime change* re-prices the whole global carry complex (§A1 Aug-2024).

**Free data:**
- **BIS Data Portal, CBPOL** — `data.bis.org/topics/CBPOL/data` — **central bank policy rates for all reporting jurisdictions in one series family.** Free, SDMX.
- **FRED** — `api.stlouisfed.org/fred/series/observations?series_id=DFF|FEDFUNDS|WALCL|RRPONTSYD` (free key). WALCL (Fed balance sheet) and RRP are the liquidity variables that actually correlate with crypto.
- **ECB Data Portal API** — `https://data-api.ecb.europa.eu/service/data/<FLOW>/<KEY>?format=csvdata` — **free, no key, no registration, 139,000+ series**, SDMX 2.1, CSV/JSON/XML.
- **Bank of Japan** — `boj.or.jp` statistics + BOJ Time-Series Data Search (free).
- **Bank of England** — Statistical Interactive Database (free CSV).
- **PBoC** — `pbc.gov.cn` (LPR, RRR, MLF announcements; Chinese, HTML).
- **BCB Brazil** — `api.bcb.gov.br/dados/serie/...` free, no key (SELIC, FX, everything).
- **RBI** — `dbie.rbi.org.in`.
- **DBnomics** — one API over all of the above.

**DB representation:**
```
central_bank(id, jurisdiction_id, name, target_type, target_value, framework_notes)
policy_rate(central_bank_id, ts, rate_name, value, change_bp, decision_event_id)
balance_sheet(central_bank_id, ts, metric, value)
policy_stance(central_bank_id, as_of, stance ENUM(hiking,hold_hawkish,hold,hold_dovish,cutting), evidence)
```

## B12. WHEN the meetings are — the global scheduled policy calendar

**This is the highest ROI item in the entire dossier and the cheapest to build.**

Central banks publish their meeting dates **6–18 months in advance**. Verified examples:
- **FOMC 2026:** Jan 31, Mar 20, May 1, Jun 12, Jul 31, Sep 18, Nov 7, Dec 18. Source: `federalreserve.gov/monetarypolicy/fomccalendars.htm`.
- **BoE MPC 2026:** Feb 5, Mar 19, Apr 30, Jun 18, Jul 30, Sep 17, Nov 5, Dec 17. Announced **December 2024**.
- **RBA 2026:** Feb 2–3, Mar 16–17, May 4–5, Jun 15–16, Aug 10–11, Sep 28–29, Nov 2–3, Dec 7–8. Announced in a 2025 media release.
- **BoJ 2026:** published as a PDF on 2025-07-31 (`boj.or.jp/en/mopo/mpmsche_minu/m_ref/mref250731a.pdf`).
- **ECB:** Governing Council monetary policy meeting dates published years ahead on `ecb.europa.eu`.

**Why it matters mechanically:**
- **Implied vol has a term structure that must contain the event.** Options expiring after a meeting carry event premium; the *event-vol* can be extracted and traded.
- **Collision weeks** (two or more majors within 7 days) are systematically higher-vol and higher cross-asset-correlation. `centralbank.watch` explicitly flags these and publishes **.ics files for 9 banks** (Fed, ECB, BoE, RBA, BoJ, BoC, RBI, SNB, PBoC).
- **The pre-FOMC drift** and the post-decision press-conference reversal are both intraday-clock phenomena that require the exact minute, not the date.
- **For crypto:** the Fed decision + presser is reliably the largest scheduled vol event of the month for BTC/ETH perps, and funding rates predictably distort into it.

**Free data:**
- **Primary (best, always do this):** scrape each central bank's own calendar page. Seed the crawler from **`bis.org/cbanks.htm`**, which lists **every central bank and monetary authority website on earth**.
- `centralbank.watch/tools/economic-calendar/` — free .ics for 9 banks (convenience, not primary).
- **FRED release calendar** — `api.stlouisfed.org/fred/releases/dates` gives future US data-release dates.
- **BLS**, **BEA**, **Census** each publish annual release schedules (free, static).
- **Eurostat / ONS / Destatis / China NBS** each publish release calendars.
- Trading Economics calendar API — has a free/limited tier but is licensed; treat as paid.

**DB representation — the calendar is a table of *future rows*:**
```
scheduled_event(
  id, kind ENUM(cb_decision, cb_minutes, cb_speech, macro_release, earnings,
                index_rebalance, expiry, unlock, hardfork, halving, ipo_lockup,
                product_launch, court_date, election, summit, opec_meeting),
  jurisdiction_id, entity_id /*company or central_bank*/,
  scheduled_ts_utc, ts_precision ENUM(exact_minute, hour, day, week, month, quarter),
  confirmed BOOL, source_url, expected_metric, consensus, previous,
  historical_abs_move_bp, realized_ts, realized_value, surprise)
```
Two columns carry the whole design: **`ts_precision`** (a confirmed 14:00 ET FOMC vs an estimated "week of Nov 12" earnings date are different objects) and **`confirmed`** (estimated → confirmed is itself a tradeable transition — see §D22).

## B13. Legalisation events (approvals, bans, licensing regimes)

**Mechanism.** A legalisation event changes the **set of legal buyers** or the **legal channel** for an asset. That is a discrete shift in the demand curve, not a sentiment change — which is why the moves are large and persistent.

**Real examples:**
- **US spot Bitcoin ETF approval, 2024-01-10.** Created a compliant channel for RIA/wirehouse/401k capital that legally could not hold spot before. The *approval* was a classic sell-the-news (priced over the prior 3 months); the *flows* were the multi-quarter driver.
- **MiCA (EU).** In force 2023-06-29; **stablecoin (ART/EMT) rules applicable 2024-06-30**; **full CASP regime from 2024-12-30**; national transitional periods ending anywhere from 2025-07-01 (Netherlands) to 2026-07-01. Consequence: Title V bars authorised CASPs from serving EEA retail with non-authorised EMTs → **USDT delisting wave**: Coinbase Europe announced early Dec-2024, Crypto.com Jan-2025, **Binance removed USDT spot pairs for EEA on 2025-03-31**. USDT global cap fell ~$141bn → ~$138bn between 2024-12-19 and 2024-12-30; EEA flow migrated to USDC/EURC. **This is a jurisdiction+law+calendar event that reallocated liquidity between two assets on a known date. A system with no `Law` object cannot see it coming; a system with one sees it 6 months out.**
- **China crypto bans (2017, 2021)**, **India's tax regime (2022)**, **Japan FSA licensing**, **UAE VARA / ADGM licences**, **NYDFS BitLicense** — each redraws the map of who may trade what, where.
- **Non-crypto:** cannabis rescheduling, gambling/sports-betting legalisation state-by-state (a clean US example of a *rolling* legalisation calendar), drug approvals (FDA PDUFA dates are literally a published legalisation calendar).

**Horizon:** rumour → weeks of drift; decision → minutes; **flow consequence → months**.

**Free data:** Federal Register + SEC rules RSS (US), EUR-Lex + ESMA registers (EU), **FDA PDUFA/AdCom calendars** (free, and the purest "scheduled binary legalisation event" dataset that exists), national regulator press feeds, `openFDA` API (free).

**DB representation:** a specialisation of `law_instrument` where `kind='approval'`, plus `approval_event(asset_id/product_id, jurisdiction_id, decision_date, outcome, channel_created ENUM(etf, license, listing, prescription), aum_unlocked_estimate)`.

---

# C. THE CALENDAR AS A FIRST-CLASS SYSTEM

## Why a calendar is architecturally different from a feed

This is the conceptual core of the whole document.

| | **Event stream (news feed)** | **Calendar (schedule)** |
|---|---|---|
| Time direction | past only | **future** |
| Arrival | unpredictable | known |
| Primary key | `(source, published_at)` | `(entity, scheduled_ts)` |
| Mutation | append-only, immutable | **rows mutate**: date moves, precision sharpens, `confirmed` flips, consensus updates, then the outcome is filled in |
| Query pattern | "what just happened?" | **"what is about to happen, to what I hold, and what happened last N times?"** |
| Latency requirement | milliseconds — you are racing | **none** — you can prepare for weeks |
| Where the edge is | speed | **positioning, vol structure, and conditional priors** |
| Failure mode | you missed it | you were surprised by something you could have known |

**Five things only a calendar can do:**

1. **Anticipation.** Reduce or hedge risk *before* a scheduled binary. A feed can only react.
2. **Vol term structure.** Map each future event to the options/perp-funding term structure it sits inside → decompose implied vol into event vol and diffusive vol → know whether an event is cheap or rich.
3. **Conditional priors from history.** Because events are typed and repeat (`NVDA earnings`, `FOMC`, `CPI`), you can maintain `P(move | event_type, entity, regime)` and the empirical move distribution. A feed has no repeat key. This is the machinery behind §D23.
4. **Collision detection.** Two events on the same day compound; the calendar can flag *ex ante* that FOMC and NVDA earnings and monthly opex land in the same 48h.
5. **Blackout / regime windows.** These are *derived intervals* computed from the calendar, and they change the market's microstructure:
   - **Fed blackout (exact rule, from the FOMC's own external-communications policy):** begins **00:00 ET on the second Saturday before the meeting** and ends **23:59 ET the day after the meeting**. So a Tue–Wed meeting has a blackout starting the Saturday ten days earlier. **Two consequences worth trading: (a) inside the window, Fed-speaker headline risk is *zero by rule*, so any "Fed source" story is either the WSJ leak channel or noise; (b) officials deliberately schedule their most informative speeches in the days immediately *before* blackout starts — so the 2–3 sessions pre-blackout are a systematically high-information window.**
   - **Earnings quiet periods** and **buyback blackouts** (a real, mechanical withdrawal of the corporate bid, typically from quarter-end to ~2 days after the release).

**Implementation notes:**
- Store `scheduled_ts_utc` **and** the local time + timezone id, because DST changes shift the UTC time of a recurring local-time event.
- Keep an **event revision log** (`scheduled_event_revision`) — the *history of the schedule* is data (a company moving its earnings date is a signal; see §D22).
- Model **recurrence rules** (RRULE-style) for genuinely periodic events (Hyperliquid hourly funding, quarterly opex, monthly CPI, weekly EIA/COT, Friday 15:30 ET COT, Tuesday 09:00 ET PortWatch refresh).
- Materialise a `market_regime_window` table: `(kind, start, end)` for blackouts, index-rebalance windows, roll windows, holiday-thinned sessions.

## C14. Market events calendar (all types)

The taxonomy the system needs, with sources:

| Type | Cadence | Free source |
|---|---|---|
| Central bank decisions/minutes/speeches | 6–12/yr per bank | Each CB site; seed from `bis.org/cbanks.htm` |
| Macro releases (CPI, NFP, GDP, PMI, PCE) | monthly/quarterly | `api.stlouisfed.org/fred/releases/dates`; BLS/BEA/Census schedules; Eurostat/ONS/NBS calendars |
| Earnings | quarterly | §C15 |
| Index rebalances | quarterly/semi-annual | MSCI Quarterly Index Review page; S&P announces ~5 trading days ahead, MSCI 2–3 weeks ahead; **FTSE Russell moves to semi-annual (June + November) from 2026** |
| Derivatives expiry | monthly/quarterly | CME/CBOE/Deribit calendars (free) |
| Auctions (Treasury, gilt, JGB, Bund) | weekly/monthly | TreasuryDirect API (free), national DMOs |
| OPEC+ meetings | ~monthly/quarterly | opec.org |
| G7/G20/COP/summits | annual | official sites |
| Elections | national | IFES ElectionGuide, Wikipedia/Wikidata |
| Crypto-native: halvings, unlocks, hard forks, mainnet launches, token migrations | irregular but **scheduled** | TokenUnlocks/DefiLlama (free-ish), chain governance forums, exchange announcement RSS |
| Exchange listings/delistings | irregular, pre-announced | Binance/Upbit/Coinbase announcement feeds — see note below |
| Lockup expiries, IPO/direct listings | one-off | S-1/424B filings via EDGAR |
| Court dates, regulatory deadlines | one-off | PACER (paid) / Federal Register / CourtListener (free API) |

**The Korean listing effect — a worked example of jurisdiction + segmentation + calendar in one object.**
When Upbit publishes a KRW listing notice, the token frequently moves **30–200% within the first minutes on global venues**, before any Korean can actually trade it. Verified instances: **DRIFT +90%**, **Centrifuge (CFG) +180% intraday**, **CAP +34.5% within one minute of the notice**. One 2025 study put the *maximum* expected return from Upbit listings at ~51.9% on average.
**Why it happens (the mechanism, not the vibe):** the KRW market is segmented from global liquidity by capital controls (§A5), Korean retail is a large and concentrated marginal buyer, and the announcement is a *pre-scheduled, publicly-timestamped* creation of new demand — so global traders front-run the Korean bid.
**And the mandatory counter-fact:** a September SolanaFloor study found **76% of Solana-ecosystem tokens listed on major exchanges later traded *below* their listing price**. So the honest precedent record is **violent pump on announcement, majority fade over weeks** — which is exactly the shape a `event_outcome` table with multiple horizons (5m / 1h / 1d / 21d) captures and a single-number "listing = bullish" rule does not.

## C15. Quarterly performance / earnings dates

**Mechanism:** earnings is the single highest-density scheduled information event for an individual name. Three separately tradeable parts:
1. **The print** (EPS/revenue vs consensus) — seconds.
2. **The guidance** — usually the larger mover; delivered on the call, 30–90 minutes after the print.
3. **The drift** (PEAD). Modern evidence: drift persists but has decayed vs the 1980s–90s. A 2025/26 study measuring buy-and-hold abnormal returns from **day +2 to day +75** found a 1.8–3.4pp spread between securities followed by long-horizon vs short-horizon retail investors (≈2.83pp raw, ≈2.08pp with controls/FE) — **and the effect accumulates over the full 75-day window, not just the first two days.** So the correct PEAD horizon to model is **~3 months, not 3 days**.

**Free data:**
- **SEC EDGAR** is the ground truth for *what was reported*: `data.sec.gov/submissions/CIK.json` for the filing event; `data.sec.gov/api/xbrl/companyconcept/...` and `/api/xbrl/frames/...` for **structured XBRL financials across all filers for a given period** — free, no key. 8-K **Item 2.02** is the earnings release itself.
- **Finnhub** free tier: `finnhub.io/api/v1/calendar/earnings?from=&to=&token=` — 60 calls/min free, no credit card. Earnings calendar with EPS estimates.
- **Financial Modeling Prep** free tier: `financialmodelingprep.com/stable/earnings-calendar` — date, EPS estimate/actual.
- **Nasdaq's own JSON** (`api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD`) — unofficial but free.
- Company IR pages + **8-K Item 7.01/8.01** announcements of the *date* (this is how you get the confirmed date first — see §D22).

**DB representation:** `earnings_event(company_id, fiscal_period, scheduled_ts, ts_precision, confirmed, call_ts, consensus_eps, consensus_rev, actual_eps, actual_rev, surprise_pct, guidance_delta, price_move_1d, price_move_75d)` — the last two columns are what make §D23 possible.

## C16. Monthly statements / releases

- **Company monthly:** **Taiwan (TWSE/TPEx) requires every listed company to file monthly operating revenue by the 10th of the following month** — TSMC, Hon Hai/Foxconn, MediaTek, Quanta, Wiwynn all report on this cadence. **There is no US equivalent, and it is a legally mandated, free, ~30–45 day lead on the AI-hardware quarter.** TWSE publishes the full listed-company monthly revenue set (current month, prior month, same month last year). Also: monthly auto sales (China CAAM, US SAAR), airline monthly traffic, REIT occupancy, Brazilian/Indian monthly filings.
- **Macro monthly:** CPI, NFP, PCE, retail sales, PMIs (S&P Global/ISM/Caixin), China trade balance, Japan Tankan (quarterly).
- **Weekly:** EIA petroleum status (Wed 10:30 ET), Baker Hughes rig count (Fri), **CFTC COT (Fri 15:30 ET, as of prior Tuesday)**, initial claims (Thu 08:30 ET), Fed H.4.1 balance sheet (Thu 16:30 ET).
- **Daily/other:** IMF PortWatch refresh **Tuesdays ~09:00 ET**; Cloudflare Radar continuous.

**Free data:** TWSE/MOPS (Taiwan monthly revenue, free), FRED release calendar, EIA API, CFTC/FuturesBench, Baker Hughes site.

**DB representation:** these are just `scheduled_event` rows with `recurrence_rule` set and `entity_id` pointing at a company or a statistical agency.

---

# D. COMPANY FUNDAMENTALS & EVENTS

## D17. Revenues

**Mechanism.** Price = f(expected future cash flows, discount rate). Revenue is the top of that stack and the hardest line to manipulate. What actually moves price is **revenue vs expectation** and **revenue *mix* and *geography*** (an AI-datacenter dollar is valued differently from a gaming dollar).

**The world-layer angle:** `revenue_by_geography` is a **jurisdiction exposure vector**. If you know NVDA's China revenue share, a BIS export-control headline is instantly quantifiable. This segment data is disclosed under ASC 280 in the 10-K and is machine-readable in XBRL.

**Free data:** `data.sec.gov/api/xbrl/companyconcept/CIK##########/us-gaap/Revenues.json` and `/api/xbrl/frames/us-gaap/Revenues/USD/CY2025Q4I.json` (**frames = the same concept for every filer in one call** — free, no key). Segment/geography tags: `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` with `srt:StatementGeographicalAxis` members. Finnhub/FMP free tiers for convenience.

**DB representation:** `financial_fact(company_id, concept, period_start, period_end, value, unit, dimension_axis, dimension_member, filing_id)` — keep the XBRL dimensions, because the geography axis *is* the jurisdiction link.

## D18. Quarterly performance metrics

Beyond EPS/revenue, the metrics that actually move each sector: gross margin (semis), RPO/backlog (AI infra), net dollar retention (SaaS), same-store sales (retail), ARPU/churn (telecom), NIM/credit provisions (banks), production guidance (miners/E&P), take rate (marketplaces), daily active users (consumer). **Model these as `kpi(company_id, kpi_name, period, value, consensus)` with a per-sector KPI registry**, because "the number that matters" is a property of the sector, not of the company.

**Free data:** XBRL frames for GAAP items; non-GAAP KPIs generally require parsing the 8-K Ex-99 press release text (free via EDGAR, needs NLP).

## D19. Monthly statements
See §C16. The key exploitable asymmetry: **Taiwan's mandatory monthly revenue disclosure gives a ~30–45 day lead on the semiconductor/AI-hardware quarter that US filers do not provide.**

## D20. CEO / management statements as tradeable events

**Mechanism.** A statement changes the market's *distribution over future fundamentals* without any change in realised fundamentals. Sub-types by reliability:
- **Formal guidance** (in an 8-K/press release, legally consequential) — highest weight.
- **Earnings-call language** (prepared remarks vs Q&A; hedging language, "we are seeing", "visibility") — the Q&A is where guidance actually leaks.
- **Conference appearances** (Goldman/Morgan Stanley tech conferences, CES, Davos) — under-covered and frequently market-moving.
- **Social posts** — Musk is the canonical case; a single post has repeatedly moved TSLA, DOGE, and BTC by double-digit percentages within minutes.
- **Central-bank-adjacent officials** — Powell's presser is a 45-minute continuous event where the *direction of the move reverses* mid-way more often than not.
- **Departures** — 8-K **Item 5.02** (departure of directors/principal officers) is one of the three most market-moving 8-K item codes alongside **2.02** (results) and **4.01/4.02** (auditor change / non-reliance restatement).

**Horizon:** seconds–minutes for the headline; days for the re-rating; quarters if it changes guidance.

**Free data:** EDGAR 8-K item codes (parse `<items>` from the submissions JSON — filter `2.02`, `4.01`, `4.02`, `5.02`, `1.03`, `3.01`, `7.01`), company IR RSS, earnings-call transcripts (free-ish: Motley Fool, Seeking Alpha limited; `api.gdeltproject.org` TV 2.0 for broadcast quotes), Federal Reserve speeches RSS (`federalreserve.gov/feeds/speeches.xml`, free), ECB speeches feed, BIS central bankers' speeches archive (free, **aggregates speeches from all central banks worldwide**).

**DB representation:**
```
statement(id, speaker_person_id, company_or_cb_id, ts, venue ENUM(8k, call_prepared,
  call_qa, conference, interview, social, presser, speech), channel_url,
  text, stance_delta, topics[], asset_refs[])
person(id, name, role, company_id, since)
```
Person must be first-class: people move between companies and carry credibility with them.

## D21. Product / version releases as events

**Mechanism.** A launch (a) validates or invalidates the revenue thesis, (b) resets the competitive clock (§E24), (c) is usually *known in advance* → the trade is in the expectation build-up and the sell-the-news.

**Real pattern (Apple, verified):** across most iPhone cycles the stock rallies ~10–15% into the event; then a 5–10% pullback lasting weeks–months after (notably 6s, 7, 12); MarketWatch's sample: ~flat on the day, **+5.5% at 3 months, +10.3% at 6 months**. So the empirical structure is **run-up → sell-the-news → medium-term recovery**, and the tradeable object is the *pattern*, not the product.

**Other launch classes:** NVIDIA GTC (architecture announcements), model releases (OpenAI/Anthropic/Google/DeepSeek — these now move *semiconductor and power* equities, not just software), game launches, drug approvals, satellite/rocket launches, chain hard forks and mainnet launches, exchange listing of a token.

**Free data:** company IR/newsroom RSS, conference schedules (GTC/WWDC/CES/MWC/Computex — all published months ahead), **FCC OET equipment authorization database** (`fcc.gov/oet/ea/fccid` — free; a device must be certified before it ships, so new FCC IDs are a **hard, public, pre-announcement leak**), app-store release notes, GitHub release feeds and merged PRs for open protocols, patent grants (USPTO free API `developer.uspto.gov`), trademark filings (USPTO TSDR free).

**DB representation:** `product(id, company_id, name, category, launch_event_id, predecessor_product_id)` + `scheduled_event(kind='product_launch')` + `product_signal(product_id, source ENUM(fcc, patent, trademark, job_post, supply_chain, app_store), observed_ts, confidence)`.

## D22. PRE-ANNOUNCEMENT HINTS — how companies signal before they announce

**This is the highest-value under-built capability in the whole dossier.** Companies leak on a predictable schedule because of legal and logistical necessity.

**The concrete, detectable, free signals — ranked by reliability:**

1. **Regulatory necessity leaks.**
   - **FCC equipment authorization** must exist before a wireless device ships. New FCC IDs appear weeks–months early. Free searchable database.
   - **Patent and trademark filings** publish on fixed schedules (US patents publish 18 months after filing). Free USPTO APIs.
   - **Antitrust filings** (HSR, EU merger notifications on `ec.europa.eu/competition`) precede deal announcements.
   - **Prospectus/S-1/424B** on EDGAR precede raises and IPOs.
   - **8-K Item 7.01 (Reg FD)** is often used to pre-announce the *date* of something.
2. **Calendar-schedule leaks.** The earnings-date announcement itself. **A company moving its earnings date later than its historical pattern is a documented (if noisy) negative signal**; the *revision history* of the calendar is data. This is why `scheduled_event_revision` matters.
3. **IR behaviour.** New investor-day scheduling, sudden addition of conference appearances, "business update" 8-Ks outside the normal cycle, a CFO appearing at a bank conference the week before quarter-end.
4. **Hiring.** Job postings are budget decisions already made. Convergent evidence: **5+ postings for a specific new role within 90 days**, and when **three independent signals from one company converge over two quarters, a launch is typically 6–9 months out**. Free-ish: company careers pages, Greenhouse/Lever public JSON boards (`boards-api.greenhouse.io/v1/boards/<company>/jobs` is **free and public** for any company using Greenhouse — a genuinely underused free alt-data source).
5. **Supply chain.** Import/export manifests (US CBP bill-of-lading data is public; ImportGenius/Panjiva are the paid packaging, but the underlying is FOIA-able), Taiwan monthly revenue (§C16) as an upstream read, component orders reported in Asian trade press (DigiTimes).
6. **Insider transactions.** **Form 4** filings on EDGAR within 2 business days — free, structured, and the **Rule 10b5-1 plan adoption date** is disclosed. Cluster buying by multiple insiders is one of the few genuinely robust pre-announcement signals in the literature.
7. **Web/product artefacts.** Sitemap and robots.txt changes, unreleased SKUs in a retailer's own API, app-store metadata, CDN asset uploads, GitHub commits referencing an unannounced feature, DNS records for a new subdomain, TLS certificate transparency logs (`crt.sh` — **free**, and a new cert for `newproduct.company.com` is a real leak).
8. **Options market.** Unusual pre-event skew/volume in a name with no scheduled catalyst.
9. **Language drift.** Comparing consecutive 10-Q/10-K risk-factor sections: **added or reworded risk factors are a legally-compelled disclosure of a change in management's belief.** Free via EDGAR + diffing.

**Horizon:** FCC/patent/cert = weeks–months; hiring = 2–3 quarters; risk-factor drift = 1 quarter; insider clusters = weeks; earnings-date revision = days.

**DB representation:**
```
pre_signal(id, company_id, signal_type, observed_ts, payload JSONB, strength,
           predicted_event_kind, predicted_window_start, predicted_window_end,
           resolved_event_id NULL, outcome ENUM(confirmed, disconfirmed, expired))
```
The `resolved_event_id` + `outcome` columns are essential: they make the pre-signal detector **self-scoring**, so precision per signal type is measured rather than assumed.

## D23. HISTORICAL PRECEDENT LOOKUP

**What it is.** "What happened last time this company — or this *type* of company — did this thing?" This is the retrieval layer that turns a typed event into a prior.

**Why it needs a schema, not a search engine.** Free-text search over news gives anecdotes. What you need is: given `(event_type, entity, entity_attributes, market_regime)`, return the **empirical distribution of forward returns** at multiple horizons, with N, and with the confounders visible.

**Design:**
```
event_instance(id, event_type, entity_id, ts, attributes JSONB, regime_id)
event_outcome(event_instance_id, horizon ENUM(5m,1h,1d,5d,21d,63d),
              ret, ret_vs_sector, ret_vs_market, vol_realized, volume_ratio)
regime(id, as_of, vix_bucket, rates_direction, dxy_trend, btc_trend, breadth)
```
Then precedent lookup is:
`SELECT ... FROM event_instance JOIN event_outcome WHERE event_type=? AND (entity_id=? OR entity_id IN (SELECT peer_id FROM peer_group WHERE ...)) AND regime_similarity(regime_id, current) > τ`

**Three levels of matching, in priority order:**
1. **Same entity, same event type** (NVDA's last 20 earnings) — highest relevance, small N.
2. **Peer group, same event type** (all mega-cap semis' earnings) — bigger N, needs a `peer_group` table built from SIC/GICS **plus** revenue-correlation, not just sector labels.
3. **Analogy by structure** (all "dominant incumbent hit by a cheap open-source challenger" events → DeepSeek/NVDA, Linux/Microsoft, Android/Nokia). This one cannot be done by SQL alone and is where an LLM over a curated `analogy_case` table earns its keep. **Keep it as a curated table with explicit structural attributes, not as vibes.**

**Critical honesty note:** precedent counts are small (a company has ~40 earnings events in a decade) and regimes change. The system must always return **N and the dispersion**, and must never present a 4-observation median as a forecast.

**Free data for building history:** EDGAR (all filings back to 1993, full-text back to 2001), FRED, Yahoo/Stooq/`yfinance` for daily OHLCV, GDELT back to 1979 (Events) / 2015 (GKG 2.0), exchange APIs for crypto.

---

# E. COMPETITIVE / STRUCTURAL DYNAMICS

## E24. Rival response dynamics

**Mechanism.** Markets price *relative* position. One firm's action mechanically re-prices its rivals through: expected share shift, expected price war (margin), expected capex response, and narrative reassignment ("who is the winner now").

**Canonical example (verified): DeepSeek, 2025-01-27.** A Chinese lab released an open-weights model claimed to be trained for <$6m in ~2 months with reasoning performance rivalling frontier US models. Consequences in one session: **NVDA −17% (≈$589–600bn of market cap, the largest single-day dollar loss in market history at the time)**, **Broadcom −17%**, **ASML −7%**, with AMD, Marvell, TSMC down materially. **Mechanism: the market re-priced the *quantity of compute required per unit of AI capability*, which is the demand curve for the entire semi complex.** Eleven months later all three had not just recovered but grown (NVDA first to $5tn in Oct-2025; AVGO +49% across 2025; ASML +36%) — **so the correct precedent lesson is "the first-order panic overshot the second-order reality" (Jevons paradox: cheaper inference increased total compute demand).** That is exactly the kind of lesson a precedent table should store.

**The rivalry response taxonomy the graph needs:**
- **Price cut** → rival must match or lose share → sector margin compression (airlines, telcos, streaming, EV, exchange fee wars).
- **Capacity add** → future oversupply → commodity/memory cycles (DRAM, shipping, lithium).
- **Feature/product parity** → narrative reassignment.
- **Capex escalation** → good for suppliers, bad for the spender's near-term FCF (the AI-capex trade: hyperscaler capex up → NVDA/AVGO/VRT/power up, hyperscaler FCF down).
- **M&A** → target +premium, acquirer usually −, and **the *other* rivals re-rate** because consolidation is now expected.
- **Exit/bankruptcy** → survivors re-rate up on capacity removal.

**Horizon:** minutes for the sympathy move; days for the sell-side re-rating; quarters for the actual share shift.

**Free data:** company newsrooms/RSS, EDGAR 8-K Item 1.01 (material definitive agreement) and 2.01 (completed acquisition), EU/US merger filings, GDELT for global coverage, patent citations (a *quantitative* rivalry graph — who cites whom).

**DB representation:**
```
rivalry(company_a, company_b, market_id, intensity, symmetric BOOL, evidence[])
market_segment(id, name, parent_id, TAM_estimate)
company_segment(company_id, segment_id, share_estimate, revenue_exposure_pct)
rival_response(trigger_event_id, responder_company_id, response_type, lag_days, observed)
```
`rivalry` must be **market-scoped** — Amazon and Google are rivals in cloud and ads but not in logistics. A single undirected "competitor" edge is useless.

## E25. Substitutes

**Mechanism.** Cross-price elasticity. If A's price rises or A becomes unavailable, demand shifts to B. The substitution edge should carry a **substitutability coefficient and a switching lag**, because a substitute with a 3-year switching lag is not a substitute on a trading horizon.

**Examples across domains:**
- **Energy:** nat-gas ↔ coal (power burn switching, weeks); oil ↔ EV (years); LNG ↔ pipeline gas (months, capex-bound).
- **Metals:** copper ↔ aluminium in wiring (months, engineering-bound); palladium ↔ platinum in autocats (the 2020–22 substitution is the textbook case, ~18-month lag).
- **Semis:** GPU ↔ custom ASIC (TPU/Trainium) — the live one; **the DeepSeek event was partly a substitution-shock repricing**.
- **Crypto:** USDT ↔ USDC (MiCA forced exactly this substitution in the EEA in Q1-2025 — a *regulatory-induced* substitution, the cleanest kind to trade because the date was known); CEX ↔ DEX perps (each CEX enforcement action pushes volume onshore→onchain — directly relevant to Hyperliquid volume); L1 ↔ L2 blockspace; ETH ↔ SOL.
- **Software:** proprietary ↔ open-source (the structural analogue class in §D23).
- **Logistics:** Suez ↔ Cape of Good Hope (**substitution with a measurable +10–14 day cost, which is why Red Sea disruption is a *freight-rate* trade rather than a *volume* trade**).

**Free data:** relative price series from any free market data source (that's the point — substitution is measurable as a *ratio* series), EIA for fuel switching, USGS for metals, DefiLlama for CEX/DEX volume share (free API `api.llama.fi`), stablecoin supply by chain (DefiLlama/Artemis free tiers).

**DB representation:** `substitution(from_asset, to_asset, context, elasticity_est, switching_lag_days, capex_required BOOL, evidence[])` — **directed and asymmetric** (gas→coal is easier than coal→gas).

## E26. Complementary markets

**Mechanism.** Demand for A raises demand for B (negative cross-price elasticity). Complements propagate a shock *forward along the value chain* with a lag, and that lag is the trade.

**Chains worth hard-coding:**
- **AI:** model demand → GPU → HBM (SK Hynix/Micron/Samsung) → CoWoS packaging (TSMC/Amkor) → substrates (Ibiden) → **power** (turbines: GE Vernova/Siemens Energy; transformers: Hitachi Energy; grid: Quanta; uranium/gas) → cooling (Vertiv) → real estate (data-centre REITs) → **copper**.
- **EV:** vehicle sales → battery cells → lithium/nickel/cobalt → mining equipment → shipping.
- **Housing:** rates → mortgage apps → homebuilders → appliances/furniture → lumber → retail.
- **Crypto:** BTC price → miner revenue → miner capex (ASICs, Bitmain) → power contracts → **and now** miner→AI-datacentre conversion (a *new* complement edge created in 2024–25 that did not exist before — the graph must be time-versioned).
- **Travel:** airlines → hotels → OTAs → jet fuel → aircraft leasing.

**Horizon:** the lag is the whole point — typically 1–3 quarters from the demand signal to the complement's revenue, and the equity often front-runs by a quarter.

**Free data:** the chain itself is best built from 10-K "customers"/"suppliers" language + ASC 280 major-customer disclosure (**companies must disclose customers >10% of revenue** — this is the free, legally-mandated seed for a supply-chain graph, extractable from EDGAR full-text), plus UN Comtrade (free tier) for country-level product flows, plus earnings-call co-mentions.

**DB representation:** `complement(from_node, to_node, chain_id, lag_days_est, transmission_strength, evidence[])` as a **directed, weighted, lagged, time-versioned** edge in the same graph as `substitution` and `rivalry`.

## E27. Sector rotation

**Mechanism.** Capital moves between sectors as a function of the macro regime (growth/inflation/rates/dollar). It is a *flow* phenomenon with persistence, which is why it is tradeable.

**The standard mapping (design opinion, widely used):** early-cycle → financials/discretionary/industrials; mid → tech/materials; late → energy/staples; recession → staples/utilities/healthcare. Overlaid by: **rates up → value/financials over long-duration growth; dollar up → domestic over international and commodity-exporters hurt; oil up → energy over transports.**

**The world-layer additions most systems miss:**
- Rotation is **also geographic** (US ↔ Europe ↔ EM ↔ Japan), and that leg is driven by the **dollar and relative policy paths** (§B11).
- Index rebalances (§C14) cause *mechanical* rotation on known dates.
- **Crypto has its own rotation** (BTC → ETH → large-alt → small-alt → back to BTC), and the BTC-dominance series is the cleanest free proxy for where in that cycle you are.

**Free data:** sector ETF prices (XLK/XLF/XLE/... free via Stooq/yfinance), FRED for the macro regime variables, MSCI/FTSE rebalance calendars, BTC dominance from CoinGecko free API (`api.coingecko.com/api/v3/global`).

**DB representation:** `sector(id, scheme ENUM(gics, icb, custom), code, name, parent_id)`, `regime`, and `rotation_prior(regime_id, sector_id, expected_relative_ret, n_obs)` — i.e. rotation stored as **conditional priors indexed by regime**, computed from history, not hard-coded rules.

## E28. Stock ↔ crypto correlation, and when it breaks

**Mechanism.** BTC's correlation to Nasdaq is not a constant — it is a **regime variable driven by who the marginal holder is**. When the marginal buyer is a macro-allocator sizing risk with equities, correlation is high. When the marginal driver is crypto-idiosyncratic (an exchange failure, a stablecoin depeg, a regulatory unlock, an ETF flow), correlation collapses or inverts.

**Verified recent history:** 30d/rolling BTC–NDX correlation averaged ~0.23 in 2024 → **~0.52 in 2025**; ranged 0.40–0.70 across 2021–22 with a peak near 0.85; **from early Oct-2025 BTC fell >30% from its peak while tech surged on earnings**, and by early 2026 the 30-day reading swung from about **−0.68 to +0.72 in roughly two weeks**. Some 2026 readings put BTC–NDX near −0.20 during the decoupling phase, and other analyses put it back near 0.88 later.

**Read the numbers correctly:** the level of the correlation matters far less than the fact that **it is unstable on a 2-week timescale**. Any risk model that hard-codes a BTC-equity correlation will be wrong at exactly the moment it matters.

**The documented breakers of the correlation:**
1. **Crypto-idiosyncratic shocks** — exchange failures, stablecoin depegs, large liquidation cascades.
2. **Regulatory regime changes** that alter *who holds it and why* (ETF approval, MiCA, custody rules).
3. **Uneven policy pivots** — when the Fed path repricing hits duration-sensitive equities and crypto differently.
4. **Structural demand that is not equity-linked** — tokenised RWAs, sovereign/corporate treasury buying, on-chain yield.

**Design consequence:** store correlation as a **rolling, regime-tagged series with an explicit break detector**, and expose `correlation_regime` as a feature, not a constant.

**Free data:** any free OHLCV source for both legs; compute rolling 30/90d correlations yourself. `api.coingecko.com` (free), Stooq/yfinance for NDX, FRED for DXY/rates.

**DB representation:** `correlation(asset_a, asset_b, window_days, as_of, rho, regime_id, break_flag)` + `correlation_break(ts, pair, trigger_event_id, magnitude)` — **and the `trigger_event_id` link back to the world-layer event is the entire value of the table.**

## E29. Second and third-order forward effects

**What it is.** The chain of consequence forward in time. First-order is priced in seconds by faster participants. **The realistic edge for a reasoning system is at order 2–3, where the effect is knowable but requires a graph traversal plus a time lag that humans and simple models don't do systematically.**

**Worked chains (each verified at the first-order link):**

**Chain 1 — Rare earth controls (2025):**
`China licenses Dy/Tb (Apr-2025)` → *O1:* REE miner equities spike, EU Dy/Tb price → ~6× Chinese domestic → *O2 (weeks):* magnet makers' input cost up; EV/wind/defence BOM up → *O3 (2–4 quarters):* auto and turbine OEM margin guidance cuts; **substitution R&D funded** (§E25) → *O4 (years):* non-China separation capacity financed (MP Materials, Lynas), which *permanently* lowers the value of Chinese leverage. **And then the Nov-2025 one-year suspension partially unwound O1 while leaving O3–O4 intact** — which is exactly why the graph needs `until` dates on law rows.

**Chain 2 — BoJ hike (2024):**
`BoJ 0.1%→0.25%` → *O1 (minutes):* JPY up, Nikkei down → *O2 (1–3 days):* **carry unwind forces liquidation of the paired long leg — US tech — so a Japanese rate decision crashes the S&P 500 6%** → *O3:* VIX 65, vol-target funds mechanically de-gross, correlation → 1 → *O4 (weeks):* the Fed's reaction function is now conditioned on foreign policy, and BoJ becomes a permanently-watched calendar item for US equity risk.

**Chain 3 — MiCA (2024-12-30):**
`Title V effective` → *O1:* CASPs must delist non-authorised EMTs → *O2 (Dec-24–Mar-25):* Coinbase EU, Crypto.com, then Binance remove USDT/EEA; USDT cap −$3bn in 11 days → *O3:* EEA liquidity migrates to USDC/EURC; **EUR-quoted pairs deepen** → *O4:* venue market-share shifts by jurisdiction; a perp venue's EEA flow re-routes.

**Chain 4 — DeepSeek (2025-01-27):**
`Cheap open model` → *O1:* NVDA −17%, AVGO −17%, ASML −7% → *O2:* the market questions hyperscaler capex → power/cooling/REIT complex sells off in sympathy → *O3 (months):* **the opposite happens** — cheaper inference raises total demand (Jevons), capex guidance *rises*, and all three names make new highs within the year. **The third-order effect inverted the first-order sign.** Storing this as a precedent is worth more than any single feature.

**How to represent it:**
```
causal_link(id, cause_type, cause_id, effect_type, effect_id, order INT,
            lag_min INTERVAL, lag_max INTERVAL, sign, strength, confidence,
            mechanism_text, evidence_event_ids[], valid_from, valid_to,
            times_observed, times_falsified)
```
Rules that make it honest rather than a fantasy:
- **`times_observed` / `times_falsified` are mandatory.** A causal edge that has never been checked against realised prices is a hypothesis, and must be labelled as one.
- **`order` is derived from traversal depth, not asserted.**
- **`lag_min`/`lag_max` gate the query:** "what is due to hit *this week* from causes that fired 60–90 days ago" is the single most useful query in the whole system and it is impossible without lag bounds.
- **`valid_from`/`valid_to`:** relationships expire (miner→AI-datacentre did not exist in 2021).
- Confidence must **decay with order** — a 3rd-order edge with 0.9 confidence is a bug.

**Academic grounding:** this is an active research area — temporal event-causality graphs for financial contagion learn "event-type A triggers event-type B with lag distribution L and conditional intensity κ" from news (MDPI 2026); TRACE (arXiv 2603.12500) does temporal rule-anchored chain-of-evidence over KGs for interpretable stock-movement prediction. **The lag distribution being learned rather than asserted is the part worth copying.**

---

# F. FREE DATA SOURCES — SUMMARY TABLE

**Free, no key, no registration (use these first):**

| Source | Endpoint | What you get | Cadence |
|---|---|---|---|
| SEC EDGAR submissions | `data.sec.gov/submissions/CIK##########.json` | filings, 8-K item codes, state of incorporation, tickers | real-time |
| SEC EDGAR XBRL | `data.sec.gov/api/xbrl/frames/...`, `/companyconcept/...` | structured financials, all filers per period | quarterly |
| SEC full-text search | `efts.sec.gov/LATEST/search-index?q=&forms=` | text inside filings+exhibits, 2001→ | minutes after filing |
| Federal Register | `federalregister.gov/api/v1/documents.json` | rules, proposed rules, notices, EOs | daily |
| Federal Register public inspection | `federalregister.gov/api/v1/public-inspection-documents.json` | **documents before publication** | intraday |
| GLEIF | `api.gleif.org/api/v1/lei-records` | legal jurisdiction, legal form, parent/child hierarchy | daily |
| World Bank | `api.worldbank.org/v2/country/all/indicator/X?format=json` | 1,400+ dev indicators, all countries | varies |
| ECB Data Portal | `data-api.ecb.europa.eu/service/data/...` | 139k+ euro-area series, SDMX | daily |
| BIS Data Portal | `data.bis.org` (CBPOL) | **policy rates, all reporting central banks** | daily |
| BIS central bank list | `bis.org/cbanks.htm` | every CB/monetary authority website | static |
| Banco Central do Brasil | `api.bcb.gov.br/dados/serie/...` | SELIC, FX, all BCB series | daily |
| GDELT 2.0 | `api.gdeltproject.org/api/v2/doc/doc`, `data.gdeltproject.org` | global news events, 65+ languages, tone, geo | **15 min** |
| IMF PortWatch | `portwatch.imf.org` (ArcGIS FeatureServer + CSV/GeoJSON) | **daily transits + trade volume, 28 chokepoints, ~1,600 ports** | weekly refresh, daily granularity |
| USGS earthquakes | `earthquake.usgs.gov/fdsnws/event/1/query` | seismic events w/ coordinates | real-time |
| Overpass (OSM) | `overpass-api.de/api/interpreter` | ports, pipelines, mines, plants, cable landings | on demand |
| Wikidata SPARQL | `query.wikidata.org/sparql` | global company↔country↔exchange graph | continuous |
| FuturesBench COT | `futuresbench.com/api/` | CFTC COT, 107 markets, 1986→, CSV/JSON, no limits | weekly (Fri 15:30 ET) |
| CoinGecko | `api.coingecko.com/api/v3/...` | crypto prices, dominance, global | minutes |
| DefiLlama | `api.llama.fi` | TVL, DEX/CEX volume, stablecoin supply by chain | minutes |
| crt.sh | `crt.sh/?q=%25.company.com&output=json` | certificate transparency → unannounced subdomains | continuous |
| Greenhouse boards | `boards-api.greenhouse.io/v1/boards/<co>/jobs` | public job postings for any Greenhouse customer | daily |
| RestCountries | `restcountries.com/v3.1/all` | ISO codes, currencies, timezones, borders | static |
| FCC equipment auth | `fcc.gov/oet/ea/fccid` | device certifications before launch | continuous |
| sanctions.network | free JSON | OFAC SDN + UNSC + EU screening | daily |
| Fed / ECB speeches RSS | `federalreserve.gov/feeds/speeches.xml`, BIS speeches archive | central banker speeches, all CBs | continuous |

**Free with a key (registration only, no payment):**

| Source | Endpoint | What | Limit |
|---|---|---|---|
| FRED | `api.stlouisfed.org/fred/...` | 800k+ US/intl series + **release calendar** | generous |
| EIA | `api.eia.gov` | energy, chokepoint throughput, weekly petroleum status | generous |
| Congress.gov v3 | `api.congress.gov/v3/...` | bills, votes, committees | 5k/hr |
| GovInfo | `api.govinfo.gov` | CFR, US Code, bill status bulk | generous |
| Regulations.gov | `api.regulations.gov` | dockets, public comments | moderate |
| Trade.gov CSL | `data.trade.gov/consolidated_screening_list/v1/search` | **11 US restricted-party lists, hourly** | generous |
| Cloudflare Radar | `api.cloudflare.com/client/v4/radar/...` | internet outages, traffic anomalies by country/ASN | generous (CC BY-NC) |
| ACLED | `acleddata.com` API | conflict/protest events w/ coordinates | tiered; API needs Research tier |
| Finnhub | `finnhub.io/api/v1/...` | earnings calendar, company news, filings, WS quotes | 60/min |
| FMP | `financialmodelingprep.com/stable/...` | earnings/IPO/dividend/split calendars | limited |
| aisstream.io | websocket | live AIS vessel positions | free tier |
| openFDA | `api.fda.gov` | drug approvals, adverse events | generous |
| USPTO | `developer.uspto.gov` | patents, trademarks, assignments | generous |
| UN Comtrade | `comtradeapi.un.org` | bilateral trade by product | free tier |
| CourtListener | `courtlistener.com/api/rest/v4/` | US court dockets and opinions | free tier |

**Paid (note only — do not build dependencies on these):** Bloomberg/Refinitiv, FactSet (incl. **Xueqiu China retail sentiment**), Kpler/Vortexa/Spire (vessel-level cargo), Panjiva/ImportGenius (bills of lading), Trading Economics calendar licence, RavenPack/Bitfinex-style news NLP, S&P Capital IQ supply-chain, OpenSanctions commercial licence, PACER, DigiTimes, exchange colo feeds.

**Gaps that free data genuinely cannot close (be honest about these):**
- Vessel-level *cargo* (what's on the ship, not just that it moved). PortWatch gives counts and class-level volume estimates, not cargo detail.
- Real-time non-English retail sentiment at scale (Naver/Weibo have no usable free API).
- Verified supplier→customer graphs beyond the >10%-of-revenue ASC 280 disclosure.
- Confirmed earnings dates for non-US small caps.
- Credit/CDS levels.
- Tick-level global equity data.

---

# G. RECOMMENDED FIRST-CLASS ENTITIES

The current architecture has no concept of jurisdiction, law, schedule, company, or rivalry. Here is the minimum entity set, in the order I would build it.

### Tier 1 — build first (unlocks the most with the least work)

1. **`jurisdiction`** — ISO-complete. `(id, iso2, iso3, name, parent_id, currency, capital_controls_level, sanctions_regime, default_tz)`. Root of the world graph.
2. **`entity`** (polymorphic supertype) with subtypes **`company`**, **`central_bank`**, **`regulator`**, **`exchange`**, **`person`**, **`sovereign`**. Keys: `lei` (GLEIF), `cik` (SEC), `wikidata_qid`, `mic` (ISO-10383).
3. **`company_jurisdiction(company_id, jurisdiction_id, role, since, until, evidence_url)`** with `role ENUM(incorporation, tax_residence, listing, primary_operations, regulator)`. **This one table is the single highest-value addition in the document** — it makes "who is exposed to a Chinese rule change / an HFCAA action / a MiCA deadline" a one-line query.
4. **`scheduled_event`** + **`scheduled_event_revision`** + **`recurrence_rule`**. Future rows, `ts_precision`, `confirmed`, `source_url`. The calendar (§C).
5. **`asset`** and **`venue_listing(asset_id, venue_id, quote_ccy, since, until)`** — because "the same asset on two venues in two jurisdictions" is the regional-premium primitive (§A5).

### Tier 2 — the world state

6. **`law_instrument`** (with the proposed→comment→final→effective→stayed→vacated state machine and all five dates) + **`law_effect`** to targets.
7. **`tax_rule`** — separate from `law_instrument` because the fields differ (base, rate, threshold) and because forward-dated tax changes are a distinct query.
8. **`central_bank`** + **`policy_rate`** + **`policy_stance`** + **`balance_sheet`**.
9. **`facility`** (fab/mine/port/pipeline/datacenter/cable, with `geo POINT`, operator, capacity, world-supply share) and **`chokepoint`** (with `geo LINESTRING`, throughput series, bypass cost in days).
10. **`commodity`** + **`commodity_production(commodity_id, jurisdiction_id, share_pct, stage ENUM(extraction, processing, refining))`** — **the `stage` column matters: China's rare-earth power is in processing, not extraction.**
11. **`sanction_designation(entity_id, list_id, jurisdiction_id, designated_at, removed_at)`** fed from CSL + OFAC + OpenSanctions.

### Tier 3 — the relationship graph (all directed, weighted, lagged, time-versioned)

12. **`rivalry(company_a, company_b, market_segment_id, intensity)`** — market-scoped, not global.
13. **`substitution(from, to, context, elasticity, switching_lag_days)`** — asymmetric.
14. **`complement(from, to, chain_id, lag_days, strength)`**.
15. **`supply_edge(supplier_id, customer_id, component, revenue_share_pct, source ENUM(asc280, filing_text, press, inferred))`**.
16. **`exposure(entity_id, exposure_type, target_id, magnitude, unit)`** — the generic join that lets a jurisdiction/commodity/chokepoint event fan out to positions.
17. **`causal_link`** as specified in §E29, with `order`, `lag_min/lag_max`, `times_observed`, `times_falsified`, `valid_from/valid_to`.

### Tier 4 — memory and scoring

18. **`event_instance`** + **`event_outcome`** (multi-horizon forward returns, absolute and relative) + **`regime`** — the precedent engine (§D23).
19. **`pre_signal`** with `resolved_event_id` and `outcome` — self-scoring pre-announcement detection (§D22).
20. **`peer_group`** — built from GICS/SIC **plus** revenue correlation, so precedent lookup can widen N intelligently.
21. **`correlation`** + **`correlation_break(trigger_event_id)`** (§E28).
22. **`sentiment_reading(asset, jurisdiction, language, source, tone)`** — jurisdiction and language as columns (§A6).
23. **`market_regime_window(kind, start, end)`** — blackouts, rebalance windows, thin-liquidity holidays, derived from the calendar.

### Cross-cutting rules

- **Bitemporal everything.** Every fact needs `valid_from/valid_to` (when it was true in the world) and `observed_at` (when we learned it). Backtests that use `valid_from` without `observed_at` leak the future — this is the #1 way world-layer research produces fake alpha.
- **Every edge carries evidence.** `evidence_url[]` or `evidence_event_ids[]`, always. No unsourced edges in the graph.
- **Every derived/causal edge carries a falsification counter.** If it has never been checked, it is a hypothesis and must render as one.
- **Confidence decays with graph distance.** Enforce it in the traversal, not in prose.
- **Store `session_bucket` on every return.** Overnight and intraday are different variables (§A5) and merging them destroys real effects.
- **`ts_precision` on every timestamp.** "Q3 2026" and "2026-09-18 14:00:00Z" cannot share a column type without a precision tag.
- **Language and jurisdiction are columns, never tags.**

---

# H. HOW THIS PLUGS INTO THE EXISTING SYSTEM (`newsystem.md`)

Read against `newsystem.md` §3.3 (the RAW INFO → causal graph → base rates pipeline) and §11 (how the causal graph is trained), the world layer is **not a replacement — it is the missing node/edge *type system* and the missing *future* half of the timeline.**

**What `newsystem.md` already has and should be kept as-is:**
- The event→thesis pipeline, dedup, priced-in agent, expected-vs-actual divergence, live-market confirmation.
- **HISTORICAL ANALOGUES + EVENT STUDY BASE RATES** — this is exactly §D23. My `event_instance` / `event_outcome` / `regime` / `peer_group` tables are the *storage form* for what that stage already does; adopt them so analogue retrieval is a JOIN with an N attached rather than a similarity search.
- **§3.4.1 — edge weights earned from event studies, never LLM-guessed.** Fully endorsed. My `causal_link.times_observed` / `times_falsified` columns are the enforcement mechanism for that rule.
- **§3.5 Information-Flow Graph (who reported first).** Keep it, and extend it with **language and jurisdiction** (§A6): the finding you are most likely to discover is that a Korean/Chinese-language source leads the English wire on specific event classes (exchange listings, MOFCOM export controls, PBoC actions). That is a latency edge you can measure with the machinery you already planned.

**Four concrete gaps this dossier closes:**

1. **The pipeline starts at `RAW INFO`, which means it is a *feed* and can only be reactive.** `newsystem.md` §3.4.3 correctly lists "anticipatory, not just reactive" as a `[HYPOTHESIS]`. **The calendar (§C) is the concrete mechanism that delivers it.** `scheduled_event` is a table of *future rows*; the "peacetime playbook" idea becomes a query — `SELECT playbook FROM scheduled_event JOIN exposure WHERE scheduled_ts BETWEEN now() AND now()+7d`. Build §B12 first: it is a few hundred lines of scrapers seeded from `bis.org/cbanks.htm` and it immediately makes the system anticipatory.

2. **The graph has transmission channels but no typed nodes.** `Iran→oil→inflation→yields→risk→BTC→alts` is currently one hardcoded chain. With `jurisdiction`, `facility`, `chokepoint`, `commodity`, `company`, `law_instrument` as real node types, that chain stops being hardcoded and becomes a *traversal* — and the same traversal then also produces the chains you did not think to write down. This is the difference between a graph with 20 hand-authored edges and one that generalises.

3. **There is no `Law` or `Jurisdiction` object, so an entire class of large, scheduled, knowable moves is invisible.** MiCA's 2024-12-30 date was known ~18 months ahead and mechanically reallocated USDT→USDC liquidity in the EEA (§B13). India's TDS moved ~73–90% of a national market offshore (§A1). Neither is detectable by a news pipeline until after the fact; both are trivial for a `law_instrument` table with an `effective_date` in the future.

4. **Crypto-first priority ordering for a Hyperliquid venue.** Given the venue, wire in this order — highest value per unit of work:
   - **(a) Policy calendar** (FOMC/ECB/BoJ + CPI/NFP). The Fed decision is reliably the largest scheduled vol event of the month for BTC/ETH perps, and funding predictably distorts into it. Free, static, tiny.
   - **(b) Fed blackout + collision-week windows** (§C). Derived from (a) at zero extra cost; changes how you size.
   - **(c) Exchange listing/delisting announcement feeds, with Upbit/Bithumb tagged by jurisdiction** (§C14 worked example: 30–200% first-minute moves, majority fade later — a perfect multi-horizon `event_outcome` test case).
   - **(d) Token unlock calendar** — pure `scheduled_event` rows, and §11's event-study machinery already handles the base rates.
   - **(e) Law/regulation feed** — Federal Register API + EUR-Lex + MOFCOM. Free, and it is where the MiCA-class events live.
   - **(f) Correlation-break detector with `trigger_event_id`** (§E28) — BTC–NDX swung from ≈−0.68 to ≈+0.72 in about two weeks in early 2026; a hard-coded correlation in the risk model will be wrong exactly when it matters.
   - **(g) Only then** the physical layer (PortWatch, chokepoints) and the equity-company layer — high value, but they pay off mainly once the system is asset-agnostic (§3.4.5).

**One warning that applies to all of it.** `newsystem.md` §11 already worries about small-N. The world layer makes that worse, not better: a country changes its crypto tax law roughly once. **Every world-layer edge must carry N and dispersion, and the bitemporal rule (`valid_from` vs `observed_at`) is not optional** — using a law's `effective_date` in a backtest without also storing *when you could have known about it* is the single easiest way to manufacture fake alpha out of this entire dossier.

---

# SOURCES

**Physical geography / trade**
- IMF PortWatch — https://portwatch.imf.org/ ; data & methodology https://portwatch.imf.org/pages/data-and-methodology ; daily chokepoint dataset https://portwatch.imf.org/datasets/42132aa4e2fc4d41bdaf9a445f688931_0/about
- EIA World Oil Transit Chokepoints — https://www.eia.gov/international/content/analysis/special_topics/World_Oil_Transit_Chokepoints ; https://www.eia.gov/todayinenergy/detail.php?id=18991
- TSMC/Taiwan concentration — https://mapshock.com/briefings/tsmc-taiwan-geopolitical-risk-concentration-resilience ; https://www.hungyichen.com/en/insights/semiconductor-geopolitics

**Politics / conflict / sanctions**
- GDELT Project data documentation — https://www.gdeltproject.org/data.html
- ACLED API documentation — https://acleddata.com/acled-api-documentation ; https://developer.acleddata.com/
- Consolidated Screening List API — https://developer.export.gov/consolidated-screening-list.html ; https://data.commerce.gov/consolidated-screening-list-api
- OFAC Sanctions List Service — https://ofac.treasury.gov/sanctions-list-service
- OpenSanctions — https://www.opensanctions.org/datasets/us_ofac_sdn/ ; https://www.opensanctions.org/datasets/sanctions/
- sanctions.network — https://sanctions.network/
- Cloudflare Radar outages/anomalies API — https://developers.cloudflare.com/api/resources/radar/subresources/annotations/subresources/outages/methods/get/ ; https://developers.cloudflare.com/radar/investigate/outages/
- China mineral export restrictions — https://www.ui.se/globalassets/ui.se-eng/publications/other-publications/chinas-mineral-export-restrictions_market-impacts-and-implications_nkk_2025.pdf ; https://anderseninstitute.org/chinas-export-control-architecture-and-its-use-of-critical-minerals-as-strategic-pressure-points/ ; https://nai500.com/blog/2025/11/china-lifts-export-ban-on-gallium-germanium-and-antimony-to-the-u-s-reshaping-supply-demand-dynamics-in-critical-metals-market/

**Jurisdiction / corporate legal identity**
- GLEIF API — https://www.gleif.org/en/lei-data/gleif-api ; https://documenter.getpostman.com/view/7679680/SVYrrxuU
- SEC EDGAR full-text search API — https://tldrfiling.com/blog/sec-edgar-full-text-search-api ; https://edgarscout.com/full-text-search/
- SEC EDGAR free API guide — https://tldrfiling.com/blog/free-sec-edgar-api-guide/
- HFCAA — https://www.davispolk.com/insights/client-update/sec-finalizes-rules-may-delist-china-based-companies ; https://journals.law.harvard.edu/hblr/wp-content/uploads/sites/87/2024/10/01_HLB_14_2_Jesse-M.-Fried-Tamar-Groswald-Ozery-2.pdf ; https://law.asia/chinese-privatization-cayman-islands/
- Wikidata Query Service — https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/queries/examples

**Law / regulation / policy calendars**
- Federal Register API — https://www.federalregister.gov/developers/documentation/api/v1 ; https://www.federalregister.gov/reader-aids/developer-resources/rest-api
- Congress.gov API — https://github.com/LibraryOfCongress/api.congress.gov/ ; https://www.loc.gov/apis/additional-apis/congress-dot-gov-api/
- FOMC calendar — https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- BoE MPC 2026 dates — https://www.bankofengland.co.uk/news/2024/december/mpc-dates-for-2026
- BoJ 2026 MPM schedule — https://www.boj.or.jp/en/mopo/mpmsche_minu/m_ref/mref250731a.pdf
- RBA 2026 board dates — https://www.rba.gov.au/media-releases/2025/mr-25-02.html
- Multi-bank calendar + iCal — https://centralbank.watch/tools/economic-calendar/ ; collision weeks https://centralbank.watch/compare/meeting-calendar/
- BIS central bank websites — https://www.bis.org/cbanks.htm ; BIS policy rates https://data.bis.org/topics/CBPOL/data
- ECB SDMX API — https://data.ecb.europa.eu/help/api/overview ; https://data.ecb.europa.eu/help/getting-data-web-services-sdmx
- World Bank Indicators API — https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation
- MiCA / USDT delistings — https://www.scorechain.com/blog/eu-stablecoin-regulation-mica ; https://vaultody.com/blog/296-what-mica-means-for-tether-usdt-delistings-custody-and-the-future-of-stablecoins-in-the-eea ; https://hacken.io/discover/mica-regulation/
- India crypto tax impact — https://www.techtimes.com/articles/317939/20260607/india-crypto-tax-drives-61-billion-offshore-each-year-parliament-demands-answers.htm ; https://www.benzinga.com/markets/cryptocurrency/22/07/27947625/tax-laws-see-trading-volumes-plunge-70-on-indian-crypto-exchanges

**Calendar / market structure**
- MSCI Quarterly Index Review — https://www.msci.com/indexes/quarterly-index-review
- Index rebalance mechanics/flows — https://www.eastspring.com/insights/deep-dives/navigating-index-rebalancing-effects-key-insights-for-smarter-execution
- exchange_calendars — https://github.com/gerrymanoim/exchange_calendars ; pandas_market_calendars — https://pandas-market-calendars.readthedocs.io/en/latest/usage.html
- CFTC COT — https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm ; free API https://futuresbench.com/api/ ; https://github.com/NDelventhal/cot_reports
- Finnhub earnings calendar — https://finnhub.io/docs/api/earnings-calendar
- FMP calendars — https://site.financialmodelingprep.com/datasets/calendars
- FOMC blackout rule (primary) — https://www.federalreserve.gov/monetarypolicy/files/fomc_extcommunicationparticipants.pdf ; staff policy https://www.federalreserve.gov/monetarypolicy/files/FOMC_ExtCommunicationStaff.pdf ; blackout calendar PDF https://www.federalreserve.gov/monetarypolicy/files/fomc-blackout-period-calendar.pdf ; https://www.stlouisfed.org/about-us/resources/blackout-periods
- Taiwan monthly revenue disclosure — https://www.twse.com.tw/en/trading/statistics/index04.html ; continuing obligations https://resourcehub.bakermckenzie.com/en/resources/cross-border-listings-guide/asia-pacific/taiwan-stock-exchange/topics/continuing-obligationsperiodic-reporting ; TWSE operating rules https://twse-regulation.twse.com.tw/m/en/LawContent.aspx?FID=FL007304
- Korean exchange listing effect — https://medium.com/@datamaxiplus/the-rise-of-korean-exchange-listing-alpha-capturing-upbit-and-bithumb-listing-pumps-9c9055388f15 ; https://solanafloor.com/news/drift-up-90-on-upbit-listing-why-korean-exchange-important ; https://www.kucoin.com/news/articles/centrifuge-price-action-understanding-the-impact-of-the-upbit-cfg-listing

**Company events / anomalies**
- 8-K item codes & which move markets — https://www.sec.gov/files/form8-k.pdf ; https://portolio.app/learn/what-is-an-8-k ; https://www.geminiq.com/blog/what-is-8-k
- PEAD (modern magnitude/horizon) — https://arxiv.org/html/2512.00280 ; review: https://www.sciencedirect.com/science/article/pii/S2214635020303750
- Overnight vs intraday — Lou, Polk & Skouras, "A Tug of War" https://personal.lse.ac.uk/polk/research/TugOfWar.pdf ; NY Fed SR 917 "The Overnight Drift" https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf ; https://elmwealth.com/night-moves-overnight-drift/
- Apple launch event patterns — https://stocktwits.com/news-articles/markets/equity/how-apple-stock-typically-moves-during-i-phone-launch-events/chw0x9NRdsL ; https://www.bitget.com/wiki/do-apple-stocks-go-up-after-events
- Pre-announcement / hiring signals — https://crustdata.com/blog/hiring-signals ; https://predictleads.com/blog/job-openings-data-company-growth/ ; https://www.itonics-innovation.com/blog/industrial-product-launches
- Supplier/customer disclosure (ASC 280 >10% rule) — https://guides.newman.baruch.cuny.edu/c.php?g=188434&p=1244107

**Competitive / structural**
- DeepSeek shock — https://www.cnbc.com/2025/01/27/nvidia-falls-10percent-in-premarket-trading-as-chinas-deepseek-triggers-global-tech-sell-off.html ; https://techcrunch.com/2025/01/27/nvidia-drops-600bn-off-its-market-cap-amid-the-rise-of-deepseek/ ; one-year-later https://www.cnbc.com/2026/01/06/why-deepseek-didnt-cause-an-investor-frenzy-again-in-2025.html
- Yen carry unwind Aug-2024 — https://www.hdfcfund.com/learn/deep-dives/tuesday-talking-point/yen-carry-trade-unwinding-story-global-event ; https://www.lambdafin.com/articles/yen-carry-trade-unwind
- BTC–Nasdaq correlation regimes — https://www.coindesk.com/markets/2025/12/04/bitcoin-s-negative-correlation-with-nasdaq-persists-and-history-suggests-a-bottom-may-be-forming ; https://crypto.com/us/market-updates/bitcoin-and-nasdaq-100-break-correlation-what-happens-next ; https://coincub.com/blog/bitcoin-dollar-index/
- Kimchi premium — https://www.sciencedirect.com/science/article/pii/S0264999324000828 ; https://www.sciencedirect.com/science/article/abs/pii/S1544612322004056 ; https://www.theblock.co/learn/251472/what-is-the-kimchi-premium
- Korean crypto community structure (Naver Cafe / altcoin skew) — https://research.despread.io/di-03/
- Causal/event knowledge graphs — TRACE https://arxiv.org/pdf/2603.12500 ; temporal event-causality graphs for financial contagion https://www.mdpi.com/2673-9909/6/8/132 ; https://link.springer.com/article/10.1007/s44443-025-00330-w

**Regional macro**
- LatAm 2026 — https://am.jpmorgan.com/content/dam/jpm-am-aem/americas/br/en/insights/market-insights/mi-gtm-latam-br-en.pdf ; https://gfmag.com/economics-policy-regulation/central-banker-report-cards-2025-latin-america/ ; https://americasmi.com/insights/latin-america-2026-economic-outlook/
- Africa FX/eurobonds — https://www.worldfinance.com/markets/africas-currency-crisis ; https://www.weforum.org/stories/financial-and-monetary-systems/overview-of-the-sub-saharan-african-eurobond-market/ ; https://www.oecd.org/en/publications/africa-capital-markets-report-2025_7d26e1d3-en/full-report/local-currency-bond-markets-for-development-financing-in-africa_b9d9f859.html ; https://www.cgdev.org/blog/sub-saharan-africas-credit-crunch-really-over

---

## APPENDIX: THE 20 QUERIES THE SCHEMA MUST ANSWER

If the architecture cannot answer these in SQL/Cypher, it is not done.

1. What scheduled events hit my open positions in the next 7 days, sorted by historical absolute move?
2. Which of my positions are exposed to jurisdiction X, and through which role (incorporation / operations / listing / regulator)?
3. Which listed companies have `incorporation != primary_operations` and `listing = US`? (the HFCAA cohort)
4. Which assets get delisted or restricted if law L reaches `effective`?
5. What is the empirical forward-return distribution for `event_type = earnings` for this company, last 20 occurrences, in the current regime — with N?
6. Which second- and third-order effects, from causes that fired 60–90 days ago, are due to land this week?
7. Which chokepoints do my commodity exposures traverse, and what is today's transit count vs its 90-day mean?
8. Which companies operate facilities within 100km of an active conflict/disaster event?
9. Where does the same asset trade at the largest cross-venue premium right now, and which capital control explains it?
10. Which central bank decisions collide within 7 days in the next quarter?
11. Which of my names are in an earnings blackout or a buyback blackout right now?
12. What is the current BTC–NDX 30d correlation, is it in a break regime, and what event triggered the last break?
13. Which pre-signals fired for company C in the last 90 days, and what is each signal type's historical precision?
14. If company A cuts price in segment S, which companies have >20% revenue exposure to S?
15. Which commodities have >60% *processing* concentration in a single jurisdiction?
16. What is scheduled during the thinnest liquidity window (holiday/low-volume session) in the next month?
17. Which sanctions designations in the last 30 days touch any entity in my exposure graph within 2 hops?
18. Which sector has the highest historical relative return conditional on the *current* regime vector?
19. For every open position, what is the overnight-vs-intraday decomposition of its last 60 days of return?
20. Which laws currently in `proposed` or `comment` status have a `comment_close` date in the next 30 days and target a sector I hold?
