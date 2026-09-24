# Crypto News Ingestion — Master Source List

For an automated Hyperliquid perps bot holding **1–7 day** positions.

Compiled 2026-08-23. **207 entries.**

---

## How to read the "Verified" column

I actually hit endpoints from this machine with `curl` during research. Statuses mean:

| Marker | Meaning |
|---|---|
| **VERIFIED-200** | I requested it, got HTTP 200, feed/endpoint is live right now. |
| **VERIFIED-AUTH** | I requested it, got 401/402/403-with-auth-challenge. The endpoint **exists** and works; it just needs a key. This is a positive verification of existence, not of the free tier. |
| **BLOCKED** | Got 403 (bot-wall / Cloudflare) or connection failure (`000`) from this machine. The source is almost certainly fine from a normal client or a non-US IP — do not conclude it is dead. Re-test from your box. |
| **DEAD-404** | The URL I guessed returned 404. The publisher exists; my guessed path is wrong. Find the real path before wiring. |
| **unverified** | Listed from knowledge. I did **not** confirm the endpoint, the limits, or the price. **Treat every number in that row as a claim to check.** |

**Honesty note on pricing:** every price below that I did not fetch from a live pricing page is marked unverified. Vendor pricing in this space changes every few months. The only prices I read off a live page in this session are NewsAPI's and X's (via secondary reporting). Assume everything else is stale until you check.

---

## 1. Crypto-native news APIs and aggregators

| # | Name | Access | URL / endpoint | Free tier & rate limit | Cost if paid | Latency | Uniquely covers | Machine readable | Verified |
|---|---|---|---|---|---|---|---|---|---|
| 1 | CryptoPanic API v2 | REST | `https://cryptopanic.com/api/developer/v2/posts/?auth_token=` | Free dev tier exists; limits not confirmed (docs page 403'd me) | Pro ~$? /mo | seconds–minutes | Best single aggregator of crypto headlines + community bull/bear votes; per-coin filtering | Yes (JSON) | BLOCKED (docs 403) |
| 2 | CoinDesk Data API (ex-CryptoCompare) news | REST | `https://data-api.coindesk.com/news/v1/article/list?lang=EN` | Free key tier exists | Paid tiers by call volume | seconds–minutes | Unified normalized feed across ~100 crypto outlets, one schema | Yes | VERIFIED-AUTH (401) |
| 3 | CryptoCompare min-api news (legacy) | REST | `https://min-api.cryptocompare.com/data/v2/news/?lang=EN` | Now key-required (used to be open) | see CoinDesk Data | seconds–minutes | Legacy path, same corpus | Yes | VERIFIED-AUTH (401) |
| 4 | CoinGecko news endpoint | REST | `https://api.coingecko.com/api/v3/news` | Demo key required; Demo plan ~30 calls/min (CoinGecko support docs say 30; a newer page says 100 — **conflicting, verify**) | Analyst $129/mo (unverified) | minutes | Ties news to their coin IDs; excellent coin metadata join key | Yes | VERIFIED-AUTH (401) |
| 5 | CoinGecko ping / market data | REST | `https://api.coingecko.com/api/v3/ping` | Keyless still works for some paths | as above | seconds | Free price/mcap join for enrichment | Yes | VERIFIED-200 |
| 6 | CoinMarketCap content/news | REST | `https://api.coinmarketcap.com/content/v3/news` | Undocumented public path, no key needed at time of test | CMC Pro from ~$29/mo (unverified) | minutes | CMC's own curated + community content | Yes | VERIFIED-200 |
| 7 | CoinMarketCap Pro API | REST | `https://pro-api.coinmarketcap.com/v1/` | Basic free 10k credits/mo (unverified) | Hobbyist ~$29/mo up (unverified) | minutes | Listings, categories; weak on news | Yes | unverified |
| 8 | Messari News API | REST | `https://api.messari.io/news/v1/news/feed` | Free tier limited; returned 402 Payment Required | Enterprise pricing (unverified) | minutes | Research-grade asset-tagged news + Messari's own analysis | Yes | VERIFIED-AUTH (402) |
| 9 | Messari Signals / Intel | REST | `https://api.messari.io/` | Paid | Enterprise (unverified) | minutes–hours | Governance proposals, protocol events, unlock calendar | Yes | unverified |
| 10 | NewsAPI.org | REST | `https://newsapi.org/v2/everything?q=bitcoin` | **100 req/day, 24h article delay, 1-month history, dev/localhost only — NOT licensed for production** | Business **$449/mo**, Advanced **$1,749/mo** | free tier: 24h delayed / paid: minutes | Broad mainstream + niche outlets in one query API | Yes | VERIFIED (pricing page read live) |
| 11 | TheNewsAPI | REST | `https://api.thenewsapi.com/v1/news/all` | Free ~100 req/day (unverified) | from ~$20/mo (unverified) | minutes | Cheap broad-coverage alternative to NewsAPI | Yes | unverified |
| 12 | Marketaux | REST | `https://api.marketaux.com/v1/news/all` | Free ~100 req/day (unverified) | from ~$29/mo (unverified) | minutes | Entity extraction + sentiment per article, incl. crypto tickers | Yes | BLOCKED (pricing 403) |
| 13 | Alpha Vantage NEWS_SENTIMENT | REST | `https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=CRYPTO:BTC&apikey=demo` | Free key: 25 req/day (recently tightened; older docs say 500/day — **verify**) | Premium from $50/mo (unverified) | minutes | Pre-scored sentiment + topic tags per article, free-ish | Yes | VERIFIED-200 (demo key works) |
| 14 | Finnhub news | REST + WS | `https://finnhub.io/api/v1/news?category=crypto` | Free ~60 calls/min (unverified — pricing page unreadable) | from ~$50/mo (unverified) | minutes | Company news + crypto news + earnings calendar in one key | Yes | unverified |
| 15 | Polygon.io news | REST | `https://api.polygon.io/v2/reference/news` | Free 5 calls/min (unverified) | from ~$29/mo (unverified) | minutes | Ticker-tagged news; strong equities cross-asset for BTC-proxy names | Yes | VERIFIED-AUTH (401) |
| 16 | Tiingo news | REST | `https://api.tiingo.com/tiingo/news` | News is a **paid add-on**, not in free tier | ~$50/mo add-on (unverified) | minutes | Deep archive + good source metadata for backtesting news | Yes | VERIFIED-AUTH (403 auth) |
| 17 | Benzinga News API | REST + WS | `https://api.benzinga.com/api/v2/news` | No meaningful free tier | Enterprise, ~$1k+/mo (unverified) | **sub-second to seconds** | Genuinely fast newsdesk; equities-first but covers crypto tickers/ETFs | Yes | unverified |
| 18 | GDELT DOC 2.0 API | REST | `https://api.gdeltproject.org/api/v2/doc/doc?query=bitcoin&mode=artlist&format=json` | Free, no key; aggressive rate limiting (I got **429**) — throttle to ~1 req/5s | Free | ~15 min (GDELT updates every 15 min) | Global news in 100+ languages, tone/theme scoring, geographic tagging. Best free geopolitics signal. | Yes | VERIFIED (429 = live, rate limited) |
| 19 | GDELT GKG / Events (BigQuery) | Bulk / BigQuery | `gdelt-bq.gdeltv2` | Free dataset, you pay BigQuery query cost | BQ query cost | 15 min | Full event/tone history for backtesting news-driven regimes | Yes | unverified |
| 20 | CoinStats news API | REST | `https://openapiv1.coinstats.app/news` | Free key tier (unverified) | paid tiers (unverified) | minutes | Compact aggregated feed, easy schema | Yes | VERIFIED-AUTH (401) |
| 21 | CryptoNews-API (cryptonews-api.com) | REST | `https://cryptonews-api.com/api/v1` | Trial only | from ~$29/mo (unverified) | minutes | Per-coin sentiment scoring, video news | Yes | unverified |
| 22 | Coinpaprika news/events | REST | `https://api.coinpaprika.com/v1/coins/{id}/events` | Free ~20k calls/mo (unverified) | from ~$99/mo (unverified) | hours | **Event calendar** (conferences, forks, mainnets) per coin | Yes | unverified |
| 23 | CoinMarketCal | REST | `https://developers.coinmarketcal.com/v1/events` | Free tier limited (unverified) | paid (unverified) | hours–days | Community-submitted forward event calendar — good for 1–7d holds | Yes | unverified |
| 24 | Nomics (status uncertain) | REST | — | — | — | — | Was acquired/sunset; **verify it still exists before wiring** | Yes | unverified |
| 25 | CoinAPI news/metadata | REST | `https://rest.coinapi.io/` | Free 100 req/day (unverified) | from ~$79/mo (unverified) | minutes | Broad exchange coverage, less news-focused | Yes | unverified |
| 26 | Amberdata | REST | `https://web3api.io/` | No free tier | Enterprise (unverified) | seconds | Institutional-grade on-chain + market + some event data | Yes | unverified |
| 27 | Kaiko | REST | — | No free tier | Enterprise (unverified) | seconds | Reference-grade market data, regulatory-quality | Yes | unverified |
| 28 | APITube news API | REST | `https://api.apitube.io/v1/news/everything` | Free tier exists (unverified) | paid (unverified) | minutes | 100+ language news, crypto filters | Yes | unverified |
| 29 | NewsData.io | REST | `https://newsdata.io/api/1/news?q=crypto` | Free 200 credits/day (unverified) | from ~$199/mo (unverified) | minutes | Good non-English coverage | Yes | unverified |
| 30 | Webz.io / Free News API | REST | `https://api.webz.io/newsApiLite` | Free 1000 calls/mo (unverified) | Enterprise (unverified) | minutes | Deep archive + forum/blog coverage beyond news | Yes | unverified |
| 31 | Bing News Search / Azure | REST | Azure AI Search | Free tier small (unverified) | pay-per-1k (unverified) | minutes | Broad index; **Bing Search API had a 2025 deprecation — verify it still exists** | Yes | unverified |
| 32 | Google News RSS | RSS | `https://news.google.com/rss/search?q=bitcoin` | Free, unofficial, no documented limit | Free | minutes | Cheapest broad net; but it's a scrape-adjacent grey area | Yes (RSS) | unverified |
| 33 | Perigon | REST | `https://api.goperigon.com/v1/all` | Free tier exists (unverified) | paid (unverified) | minutes | Clustered stories (they dedupe for you) + entity tagging | Yes | unverified |
| 34 | Aylien / Quantexa News API | REST | — | No free tier | Enterprise (unverified) | minutes | NLP-enriched news, event clustering | Yes | unverified |
| 35 | RavenPack / Bigdata.com | REST | — | None | Enterprise, very expensive (unverified) | seconds | The institutional standard for news analytics; entity relevance + novelty scores | Yes | unverified |

---

## 2. Crypto publications — RSS

All RSS below were hit live. Poll every 60–120s; they are not low-latency but they are free and reliable.

| # | Name | Access | URL | Free tier | Cost | Latency | Uniquely covers | MR | Verified |
|---|---|---|---|---|---|---|---|---|---|
| 36 | CoinDesk | RSS | `https://www.coindesk.com/arc/outboundfeeds/rss/` | Free | — | minutes | Institutional/regulatory scoops; market-moving | Yes | **VERIFIED-200** |
| 37 | Cointelegraph | RSS | `https://cointelegraph.com/rss` | Free | — | minutes | Highest volume; retail sentiment driver | Yes | **VERIFIED-200** |
| 38 | The Block | RSS | `https://www.theblock.co/rss.xml` | Free | Research paywalled | minutes | Best institutional/exchange investigative reporting | Yes | **VERIFIED-200** |
| 39 | Decrypt | RSS | `https://decrypt.co/feed` | Free | — | minutes | NFT/consumer/culture + solid breaking | Yes | **VERIFIED-200** |
| 40 | Blockworks | RSS | `https://blockworks.co/feed` | Free | — | minutes | Macro-crypto crossover, ETF and TradFi flows | Yes | **VERIFIED-200** |
| 41 | DL News | RSS | `https://www.dlnews.com/arc/outboundfeeds/rss/` | Free | — | minutes | DeFi-native investigative; regulation in EU | Yes | **VERIFIED-200** |
| 42 | Protos | RSS | `https://protos.com/feed/` | Free | — | minutes | Skeptic/fraud beat — early on blowups | Yes | **VERIFIED-200** |
| 43 | CryptoSlate | RSS | `https://cryptoslate.com/feed/` | Free | — | minutes | High volume, altcoin coverage | Yes | **VERIFIED-200** |
| 44 | BeInCrypto | RSS | `https://beincrypto.com/feed/` | Free | — | minutes | Multi-language editions | Yes | **VERIFIED-200** |
| 45 | The Defiant | RSS | `https://thedefiant.io/api/feed` | Free | Pro paid | minutes | DeFi protocol-level news | Yes | **VERIFIED-200** |
| 46 | Bitcoinist | RSS | `https://bitcoinist.com/feed/` | Free | — | minutes | BTC-focused, high volume | Yes | **VERIFIED-200** |
| 47 | AMBCrypto | RSS | `https://ambcrypto.com/feed/` | Free | — | minutes | Altcoin TA/news volume | Yes | **VERIFIED-200** |
| 48 | NewsBTC | RSS | `https://newsbtc.com/feed/` | Free | — | minutes | BTC + alt price commentary | Yes | **VERIFIED-200** |
| 49 | U.Today | RSS | `https://u.today/rss` | Free | — | minutes | Fast aggregation, some noise | Yes | **VERIFIED-200** |
| 50 | CoinJournal | RSS | `https://coinjournal.net/feed/` | Free | — | minutes | UK/EU angle | Yes | **VERIFIED-200** |
| 51 | Bitcoin Magazine | RSS | `https://bitcoinmagazine.com/feed` | Free | — | minutes | BTC ecosystem, mining, treasury companies | Yes | BLOCKED (403 bot-wall; use a UA + retry) |
| 52 | Crypto Briefing | RSS | `https://cryptobriefing.com/feed/` | Free | — | minutes | Research-leaning | Yes | BLOCKED (403) |
| 53 | Unchained (Laura Shin) | RSS | `https://unchainedcrypto.com/feed/` | Free | — | hours | Deep interviews; scoop-heavy on legal cases | Yes | unverified |
| 54 | Bankless | RSS | `https://newsletter.banklesshq.com/feed` | Free | Premium paid | hours | Ethereum/DeFi thesis-level | Yes | unverified |
| 55 | Odaily (CN) | REST/RSS | `https://www.odaily.news/v1/openapi/feeds` | Free public openapi | — | **seconds–minutes** | Chinese-language flash news; often ahead of EN outlets on Asia | Yes | **VERIFIED-200** |
| 56 | ChainCatcher (CN) | RSS | `https://www.chaincatcher.com/rss.xml` | Free | — | minutes | CN research + flash | Yes | **VERIFIED-200** |
| 57 | Wu Blockchain (Colin Wu) | Web/RSS/X | `https://www.wublock123.com/` | Free | — | minutes | **Single best China-policy and Asia-exchange source** | Partial | **VERIFIED-200** (site live; find RSS path) |
| 58 | CoinNess | Web/app | `https://coinness.com/` | Free web | Paid tiers (unverified) | **seconds** | Korean-origin flash news wire; very fast on Asia | Partial | **VERIFIED-200** |
| 59 | Jinse Finance (CN) | Web | `https://www.jinse.cn/lives` | Free | — | seconds–minutes | CN flash wire, huge Asia readership | Scrape | BLOCKED (`000` — likely geo/CDN; retry from your IP) |
| 60 | 8btc (CN) | RSS | `https://www.8btc.com/feed` | Free | — | minutes | Long-running CN outlet | Yes | BLOCKED (`000`) |
| 61 | PANews (CN) | RSS | `https://rss.panewslab.com/en/tvsq/rss` | Free | — | minutes | CN/EN dual; strong on Asia funding rounds | Yes | BLOCKED (`000`) |
| 62 | BlockBeats (CN) | RSS | (my guessed path 404'd) | Free | — | seconds–minutes | CN flash news, very fast | Yes | DEAD-404 (find real path) |
| 63 | Foresight News (CN) | Web | `https://foresightnews.pro/` | Free | — | minutes | CN research/flash | Scrape | unverified |
| 64 | TechFlow / 深潮 (CN) | Web | `https://www.techflowpost.com/` | Free | — | minutes | CN VC/funding + flash | Scrape | unverified |
| 65 | CoinPost (JP) | RSS | `https://coinpost.jp/?feed=rss2` | Free | — | minutes | **Japan FSA rulings, JP exchange listings** | Yes | unverified |
| 66 | CoinDesk Japan | RSS | `https://www.coindeskjapan.com/feed/` | Free | — | minutes | JP institutional | Yes | unverified |
| 67 | Tokenpost (KR) | RSS | `https://www.tokenpost.kr/rss` | Free | — | minutes | **Korean market — Upbit "kimchi premium" moves** | Yes | unverified |
| 68 | Blockmedia (KR) | RSS | `https://www.blockmedia.co.kr/feed` | Free | — | minutes | KR regulatory | Yes | unverified |
| 69 | Cryptonews.com | RSS | `https://cryptonews.com/news/feed/` | Free | — | minutes | High-volume aggregation | Yes | unverified |
| 70 | CoinGape | RSS | `https://coingape.com/feed/` | Free | — | minutes | India/Asia angle, high volume | Yes | unverified |
| 71 | The Big Whale (FR) | RSS | `https://www.thebigwhale.io/feed` | Free | Paid | hours | EU/France institutional | Yes | unverified |
| 72 | BTC-ECHO (DE) | RSS | `https://www.btc-echo.de/feed/` | Free | Paid | minutes | German-language, BaFin coverage | Yes | unverified |
| 73 | Cryptopolitan | RSS | `https://www.cryptopolitan.com/feed/` | Free | — | minutes | High volume | Yes | unverified |
| 74 | The Crypto Basic | RSS | `https://thecryptobasic.com/feed/` | Free | — | minutes | Altcoin/XRP-community volume | Yes | unverified |
| 75 | Milk Road | Email/RSS | `https://milkroad.com/` | Free | — | hours | Retail sentiment barometer | Partial | unverified |
| 76 | Rekt.news | Web/RSS | `https://rekt.news/` | Free | — | hours | Post-mortems on hacks — narrative, not first alert | Partial | BLOCKED (`000` on api path) |
| 77 | a16z crypto / Paradigm / Multicoin blogs | RSS | various | Free | — | days | Thesis-level; moves narratives not minutes | Yes | unverified |
| 78 | Ethereum Foundation blog | RSS | `https://blog.ethereum.org/en/feed.xml` | Free | — | hours | Upgrade/fork timing — schedulable catalysts | Yes | unverified |
| 79 | Solana / Base / Arbitrum official blogs | RSS | various | Free | — | hours | L1/L2 upgrade + incentive program announcements | Yes | unverified |
| 80 | Hyperliquid blog / Medium | RSS | `https://medium.com/@hyperliquid/feed` | Free | — | hours | **Your venue's own roadmap, HIP proposals, points/airdrop news** | Yes | unverified |

---

## 3. Macro and TradFi

Crypto in 2025–26 trades as a high-beta risk asset. For 1–7 day holds this category matters as much as crypto-native news.

| # | Name | Access | URL | Free tier | Cost | Latency | Uniquely covers | MR | Verified |
|---|---|---|---|---|---|---|---|---|---|
| 81 | Federal Reserve press releases | RSS | `https://www.federalreserve.gov/feeds/press_all.xml` | Free, no key | — | **seconds** after publication | **FOMC statements, minutes, emergency actions.** Single highest-impact macro feed for crypto. | Yes | **VERIFIED-200** |
| 82 | Fed H.10 / data feeds | RSS | `https://www.federalreserve.gov/feeds/h10.xml` | Free | — | daily | FX/rates series | Yes | **VERIFIED-200** |
| 83 | FOMC calendar | Scrape/ICS | `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm` | Free | — | scheduled | Pre-schedule your risk-off windows | Partial | unverified |
| 84 | BLS latest releases | RSS | `https://www.bls.gov/feed/bls_latest.rss` | Free | — | **seconds** at 8:30 ET | **CPI, NFP, PPI** — the single biggest scheduled crypto vol events | Yes | **VERIFIED-200** |
| 85 | BLS release calendar | REST/HTML | `https://www.bls.gov/schedule/news_release/` | Free | — | scheduled | Know exactly when to flatten | Partial | unverified |
| 86 | BEA (GDP, PCE) | REST | `https://apps.bea.gov/api/` | Free with key | — | seconds at release | **Core PCE** — the Fed's preferred inflation gauge | Yes | unverified |
| 87 | FRED API | REST | `https://api.stlouisfed.org/fred/` | Free with key; generous limits | Free | minutes–days | DXY, 2y/10y, real yields, M2, financial conditions — regime features | Yes | VERIFIED-AUTH (400 = live, needs valid key) |
| 88 | US Treasury press | RSS | `https://home.treasury.gov/` | Free | — | minutes | Sanctions, stablecoin policy, debt issuance | Yes | VERIFIED (302 on OFAC XML — follow redirect) |
| 89 | Treasury OFAC SDN list | XML/CSV | `https://sanctionslist.ofac.treas.gov/` | Free | — | minutes–hours | **Sanctioned crypto addresses (Tornado, mixers, exchanges)** — hits specific tokens hard | Yes | VERIFIED (redirect) |
| 90 | ECB press releases | RSS | `https://www.ecb.europa.eu/rss/press.html` | Free | — | seconds | EUR rate decisions; DXY driver | Yes | **VERIFIED-200** |
| 91 | Bank of Japan | RSS/HTML | `https://www.boj.or.jp/en/rss/whatsnew.xml` | Free | — | seconds | **BOJ policy = yen carry trade = the Aug-2024-style crypto crash driver** | Yes | unverified |
| 92 | PBOC (China) | HTML/scrape | `http://www.pbc.gov.cn/en/` | Free | — | hours | China liquidity + crypto bans | Scrape | unverified |
| 93 | Bank of England | RSS | `https://www.bankofengland.co.uk/boeapps/rss/feeds.aspx` | Free | — | seconds | GBP/gilt shocks | Yes | unverified |
| 94 | IMF news | RSS | `https://www.imf.org/en/News/RSS?language=eng` | Free | — | hours | EM/sovereign stress | Yes | BLOCKED (403) |
| 95 | Bloomberg markets | RSS | `https://feeds.bloomberg.com/markets/news.rss` | Free headlines (truncated) | Terminal $32k/yr (unverified) | minutes | Best-in-class scoops, but RSS is delayed vs terminal | Yes | **VERIFIED-200** |
| 96 | WSJ Markets | RSS | `https://feeds.a.dj.com/rss/RSSMarketsMain.xml` | Free headlines | Sub ~$40/mo | minutes | Fed-whisperer pieces (Timiraos) move rates instantly | Yes | **VERIFIED-200** |
| 97 | Financial Times | RSS | `https://www.ft.com/rss/home` | Free headlines | Sub ~$40/mo | minutes | EU/UK policy, institutional flows | Yes | **VERIFIED-200** |
| 98 | CNBC finance | RSS | `https://www.cnbc.com/id/10000664/device/rss/rss.html` | Free | — | minutes | Retail-visible narrative | Yes | **VERIFIED-200** |
| 99 | BBC Business | RSS | `https://feeds.bbci.co.uk/news/business/rss.xml` | Free | — | minutes | Global, non-US framing | Yes | **VERIFIED-200** |
| 100 | Yahoo Finance news | RSS | `https://finance.yahoo.com/news/rssindex` | Free | — | minutes | Broad aggregation | Yes | **VERIFIED-200** |
| 101 | Seeking Alpha market currents | RSS | `https://seekingalpha.com/market_currents.xml` | Free | Paid tiers | minutes | Fast equity-side headlines incl. COIN/MSTR/MARA | Yes | **VERIFIED-200** |
| 102 | Investing.com news | RSS | `https://www.investing.com/rss/news.rss` | Free | — | minutes | Broad + economic calendar on same site | Yes | **VERIFIED-200** |
| 103 | Al Jazeera all news | RSS | `https://www.aljazeera.com/xml/rss/all.xml` | Free | — | minutes | Middle East / geopolitics, non-Western framing | Yes | **VERIFIED-200** |
| 104 | Reuters | RSS | (my guessed reutersagency path 404'd) | Reuters killed public RSS; use Reuters.com sitemaps or a licensed feed | Licensed, expensive | seconds (licensed) | The wire that moves markets first | Yes | DEAD-404 — needs licensing |
| 105 | AP News | RSS/API | (guessed path 404'd) | AP requires licensing for the wire | Licensed | seconds | Second major wire | Yes | DEAD-404 |
| 106 | Forex Factory calendar | XML | `https://nfs.faireconomy.media/ff_calendar_thisweek.xml` | **Free, no key, works** | Free | scheduled | **The practical economic calendar with impact ratings** — best free calendar | Yes | **VERIFIED-200** |
| 107 | TradingEconomics | REST/Web | `https://tradingeconomics.com/calendar` | Free web; API paid | API from ~$100/mo (unverified) | seconds at release | Calendar + actual-vs-forecast in machine form | Partial | **VERIFIED-200** (web) |
| 108 | Frankfurter (FX rates) | REST | `https://api.frankfurter.app/latest` | **Free, no key** | Free | daily | Free FX reference for DXY proxying | Yes | **VERIFIED-200** |
| 109 | Federal Register API | REST | `https://www.federalregister.gov/api/v1/documents.json` | **Free, no key** | Free | hours | Every US rule/notice incl. crypto rulemaking, machine-searchable | Yes | **VERIFIED-200** |
| 110 | Congress.gov API | REST | `https://api.congress.gov/v3/` | Free with key | Free | hours | Stablecoin/market-structure bill progress | Yes | VERIFIED-AUTH (403 no key) |
| 111 | CME FedWatch | Web/scrape | `https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html` | Free web | — | minutes | Rate-cut odds — the number crypto reprices against | Scrape | unverified |
| 112 | ZeroHedge | RSS | `https://feeds.feedburner.com/zerohedge/feed` | Free | — | minutes | Fast, biased, but often first on risk-off chatter | Yes | unverified |
| 113 | MarketWatch | RSS | `https://feeds.marketwatch.com/marketwatch/topstories/` | Free | — | minutes | Retail-facing US markets | Yes | unverified |
| 114 | Nikkei Asia | RSS | `https://asia.nikkei.com/rss/feed/nar` | Free headlines | Paid | minutes | Japan/Asia policy | Yes | unverified |
| 115 | SCMP China | RSS | `https://www.scmp.com/rss/91/feed` | Free | — | minutes | China tech/policy | Yes | unverified |

---

## 4. Regulation and legal

| # | Name | Access | URL | Free tier | Cost | Latency | Uniquely covers | MR | Verified |
|---|---|---|---|---|---|---|---|---|---|
| 116 | SEC press releases | RSS | `https://www.sec.gov/news/pressreleases.rss` | Free (send a real User-Agent with contact email — SEC requires it) | Free | **seconds** | Enforcement actions, ETF approvals/denials — violent single-token moves | Yes | **VERIFIED-200** |
| 117 | SEC EDGAR full-text search | REST | `https://efts.sec.gov/LATEST/search-index?q=bitcoin` | Free, 10 req/sec cap, UA required | Free | minutes | Catch 8-K/S-1 mentioning crypto before press picks it up | Yes | unverified |
| 118 | SEC EDGAR company Atom feed | Atom | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001050446&type=8-K&output=atom` | Free | Free | minutes | **Per-company filing stream (this CIK = MicroStrategy/Strategy)** | Yes | **VERIFIED-200** |
| 119 | SEC EDGAR daily index | Bulk | `https://www.sec.gov/Archives/edgar/daily-index/` | Free | Free | hours | Full-day filing sweeps incl. 13F/13D | Yes | unverified |
| 120 | SEC litigation releases | RSS | `https://www.sec.gov/rss/litigation/litreleases.xml` | Free | Free | seconds–minutes | Lawsuits against exchanges/issuers | Yes | unverified |
| 121 | CFTC press releases | RSS | (my guessed path 404'd — find real one on cftc.gov) | Free | Free | seconds | **Perps/derivatives regulation — directly relevant to Hyperliquid** | Yes | DEAD-404 |
| 122 | DOJ press releases | RSS | (guessed path 404'd; DOJ moved feeds) | Free | Free | seconds | Criminal indictments (exchange execs, mixers) | Yes | DEAD-404 |
| 123 | FinCEN news | RSS | `https://www.fincen.gov/news-room/rss.xml` | Free | Free | hours | AML rules on wallets/mixers | Yes | unverified |
| 124 | OCC / FDIC / Fed joint guidance | RSS | agency sites | Free | Free | hours | Bank-crypto custody rules — big for adoption narratives | Yes | unverified |
| 125 | CourtListener / RECAP API | REST | `https://www.courtlistener.com/api/rest/v4/search/?q=coinbase` | **Free, works without key for search** (key recommended) | Free / donations | minutes–hours | **Docket entries in SEC v. exchanges, Ripple, bankruptcy cases — before news reports them** | Yes | **VERIFIED-200** |
| 126 | PACER | REST/scrape | `https://pacer.uscourts.gov/` | Pay per page ($0.10/page, capped) | ~pennies/page | minutes | The primary docket source; RECAP mirrors it free | Partial | unverified |
| 127 | Kroll / FTX & Celsius claims agents | Web | claims agent sites | Free | — | days | **Bankruptcy distribution schedules = known sell pressure dates** | Scrape | unverified |
| 128 | EU Official Journal / MiCA | RSS/REST | `https://eur-lex.europa.eu/` | Free | Free | hours | MiCA implementation, stablecoin restrictions in EU | Yes | unverified |
| 129 | ESMA news | RSS | `https://www.esma.europa.eu/rss.xml` | Free | Free | hours | EU securities regulator statements | Yes | unverified |
| 130 | UK FCA news | RSS | `https://www.fca.org.uk/news/rss.xml` | Free | Free | hours | UK crypto promotion/registration rules | Yes | unverified |
| 131 | Japan FSA | HTML/RSS | `https://www.fsa.go.jp/en/` | Free | Free | hours | **JP exchange licensing, JPY stablecoins** | Partial | unverified |
| 132 | Korea FSC / FSS | HTML | `https://www.fsc.go.kr/eng/` | Free | Free | hours | **Korea delisting orders — brutal on Upbit-listed alts** | Scrape | unverified |
| 133 | MAS Singapore | RSS | `https://www.mas.gov.sg/rss` | Free | Free | hours | SG licensing | Yes | unverified |
| 134 | Hong Kong SFC | HTML | `https://www.sfc.hk/en/` | Free | Free | hours | HK spot ETF and licensing regime | Partial | unverified |
| 135 | India CBDT/RBI | HTML | `https://rbi.org.in/` | Free | Free | hours | Tax/ban headlines drive INR-pair volume | Scrape | unverified |
| 136 | Brazil CVM / Turkey / UAE VARA | HTML | agency sites | Free | Free | hours | EM regulatory shocks | Scrape | unverified |
| 137 | FATF | HTML/RSS | `https://www.fatf-gafi.org/` | Free | Free | days | Travel-rule and grey-list decisions | Partial | unverified |
| 138 | BIS | RSS | `https://www.bis.org/rss/` | Free | Free | days | Central-bank thinking on stablecoins/CBDC | Yes | unverified |

---

## 5. Exchange and venue announcements

**This is the highest alpha-per-dollar category for small caps.** A Binance/Upbit listing can move a token 30–100% in seconds. Poll these aggressively.

| # | Name | Access | URL | Free tier | Cost | Latency | Uniquely covers | MR | Verified |
|---|---|---|---|---|---|---|---|---|---|
| 139 | Binance announcement CMS (unofficial) | REST | `https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=48&pageNo=1&pageSize=5` | **Free, no key, returns 200** — undocumented internal API, can break/ratelimit | Free | **~1–3s if polled fast** | **New listings, delistings, HODLer airdrops, Monitoring Tag** | Yes (JSON) | **VERIFIED-200** |
| 140 | Binance official announcement WebSocket | WS | Binance developer docs "announcement stream" | Free with key (unverified) | Free | **sub-second** | Push instead of poll — the right way to do Binance listings | Yes | unverified |
| 141 | Binance spot API (new symbol detection) | REST | `https://api.binance.com/api/v3/exchangeInfo` | Free, weight-limited (1200 wt/min) | Free | seconds | Diff the symbol list — a listing appears here at go-live | Yes | unverified |
| 142 | Bybit announcements API | REST | `https://api.bybit.com/v5/announcements/index?locale=en-US&limit=5` | **Free, documented, no key** | Free | seconds | Official supported endpoint — cleanest of all exchanges | Yes | **VERIFIED-200** |
| 143 | OKX announcements API | REST | `https://www.okx.com/api/v5/support/announcements` | Free (documented) | Free | seconds | Listings/delistings/maintenance | Yes | BLOCKED (`000` from this machine — likely geo; retest) |
| 144 | KuCoin announcements API | REST | `https://api.kucoin.com/api/v3/announcements` | **Free, documented** | Free | seconds | Small/mid cap first listings | Yes | **VERIFIED-200** |
| 145 | Upbit announcements (internal) | REST | `https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=5&category=all` | **Free, no key, returns 200** — undocumented | Free | **seconds** | **Korean listings = the most violent single-token pumps in crypto** | Yes | **VERIFIED-200** |
| 146 | Upbit market list | REST | `https://api.upbit.com/v1/market/all` | Free | Free | seconds | Diff to detect new KRW pairs | Yes | **VERIFIED-200** |
| 147 | Bithumb notices | REST/scrape | `https://api.bithumb.com/` + notice page | Free | Free | seconds | Second Korean venue | Partial | unverified |
| 148 | Coinbase blog / asset listings | RSS + REST | `https://blog.coinbase.com/feed` and `https://api.coinbase.com/v2/currencies` | Free | Free | seconds–minutes | "Coinbase effect" listings; roadmap posts | Yes | **VERIFIED-200** (currencies endpoint) |
| 149 | Coinbase Exchange products | REST | `https://api.exchange.coinbase.com/products` | Free | Free | seconds | Diff for new tradable pairs | Yes | unverified |
| 150 | Kraken status + announcements | REST/RSS | `https://api.kraken.com/0/public/SystemStatus` , `https://status.kraken.com/history.rss` | Free | Free | seconds | **Exchange outages** — outages cause dislocations you can trade or must avoid | Yes | **VERIFIED-200** |
| 151 | Gate.io currencies | REST | `https://api.gateio.ws/api/v4/spot/currencies` | Free | Free | seconds | Very early listings on long-tail tokens | Yes | **VERIFIED-200** |
| 152 | MEXC | REST | `https://api.mexc.com/api/v3/ping` (+ exchangeInfo) | Free | Free | seconds | Earliest listings of micro caps | Yes | **VERIFIED-200** |
| 153 | Bitget / HTX / Bitfinex announcements | REST/RSS | exchange docs | Free | Free | seconds | Broader listing coverage | Yes | unverified |
| 154 | **Hyperliquid info API** | REST (POST) | `POST https://api.hyperliquid.xyz/info` body `{"type":"meta"}` | **Free, no key.** Note: it is **POST-only** — a GET returns 405, which is how I confirmed it's live. IP weight limit ~1200/min (unverified) | Free | **sub-second** | **Your own venue: the perp universe, new listings, max leverage, funding, OI caps.** Diff `meta` to detect a new perp before anyone tweets it. | Yes | **VERIFIED (405 on GET = endpoint live)** |
| 155 | Hyperliquid WebSocket | WS | `wss://api.hyperliquid.xyz/ws` | Free | Free | **sub-second** | Live trades, L2 book, funding, liquidations on your own venue | Yes | unverified |
| 156 | HyperliquidX on X / Discord | Social | @HyperliquidX | Free | Free | seconds | HIP votes, listing auctions, incident notices | Partial | unverified |
| 157 | Exchange status pages (aggregate) | RSS | `status.binance.com`, `status.kraken.com`, `status.coinbase.com` | Free | Free | seconds | Withdrawal halts precede depegs and dislocations | Yes | unverified |
| 158 | cryptolisting.ws / listing-alert services | WS/REST | `https://cryptolisting.ws/` | Trial | ~$30–100/mo (unverified) | sub-second | Prebuilt multi-exchange listing websocket if you don't want to build it | Yes | unverified |

---

## 6. ETF and institutional flows

For 1–7 day holds, ETF flow is one of the few genuinely *predictive* daily series.

| # | Name | Access | URL | Free tier | Cost | Latency | Uniquely covers | MR | Verified |
|---|---|---|---|---|---|---|---|---|---|
| 159 | Farside Investors BTC/ETH ETF flows | Scrape (HTML table) | `https://farside.co.uk/bitcoin-etf-flow-all-data/` | Free web, **no API**, Cloudflare-protected | Free | ~T+1 evening | **The reference daily flow table everyone quotes** | Scrape only | BLOCKED (403 Cloudflare — needs a browser-like client; respect their ToS) |
| 160 | SoSoValue ETF API | REST | `https://api.sosovalue.xyz/openapi/v2/etf/currentEtfDataMetrics` (POST) | Free key tier (unverified) | paid (unverified) | ~T+1 | Machine-readable ETF flows — the API alternative to scraping Farside | Yes | **VERIFIED (405 on GET = live, POST-only)** |
| 161 | BitMEX Research ETF flows | X / spreadsheet | @BitMEXResearch | Free | Free | ~T+1 | Independent flow tally, often first | Partial | unverified |
| 162 | Issuer daily NAV pages (IBIT, FBTC, ARKB, GBTC…) | Scrape/CSV | issuer sites | Free | Free | ~T+1 | Ground truth per fund; slower but authoritative | Partial | unverified |
| 163 | Grayscale | Web/X | `https://www.grayscale.com/` | Free | Free | daily | GBTC/ETHE outflow pressure, new trust filings | Partial | unverified |
| 164 | SEC 13F filings | EDGAR | `https://www.sec.gov/cgi-bin/browse-edgar?...&type=13F` | Free | Free | **45 days lagged** | Institutional positioning — too slow to trade, useful as regime context | Yes | unverified |
| 165 | Strategy (MicroStrategy) 8-K | EDGAR Atom | CIK 0001050446 | Free | Free | minutes | **BTC purchase announcements move BTC and MSTR** | Yes | **VERIFIED-200** |
| 166 | Other treasury companies (Metaplanet, Marathon, Semler…) | EDGAR / TSE filings | per-company | Free | Free | minutes | Corporate BTC buying wave | Yes | unverified |
| 167 | bitcointreasuries.net | Scrape | `https://bitcointreasuries.net/` | Free | Free | daily | Aggregate corporate/ETF holdings | Scrape | unverified |
| 168 | CME crypto futures OI / COT | REST/CSV | CME + CFTC COT | Free | Free | weekly (COT), daily (OI) | Institutional positioning and basis | Yes | unverified |
| 169 | Coinglass | REST | `https://open-api.coinglass.com/` | Free tier limited | from ~$29/mo (unverified) | minutes | Aggregated OI, funding, **liquidation heatmaps** across venues | Yes | unverified |
| 170 | Velo Data | REST | `https://velodata.app/` | Free tier (unverified) | paid | minutes | Clean cross-venue derivatives data, trader-favored | Yes | unverified |
| 171 | Laevitas / Amberdata derivatives | REST | — | Trial | paid | minutes | Options skew/vol surface — reads fear before spot moves | Yes | unverified |
| 172 | Deribit options data | REST/WS | `https://www.deribit.com/api/v2/` | Free public | Free | sub-second | **DVOL, skew, max pain** — where event risk is priced | Yes | unverified |

---

## 7. On-chain and whale intelligence

| # | Name | Access | URL | Free tier | Cost | Latency | Uniquely covers | MR | Verified |
|---|---|---|---|---|---|---|---|---|---|
| 173 | Whale Alert API | REST/WS | `https://api.whale-alert.io/v1/` | Free personal tier (very limited) | from ~$20–700/mo (unverified) | **seconds** | Large transfers to/from exchanges — classic pre-dump signal | Yes | VERIFIED-AUTH (401) |
| 174 | Arkham Intelligence API | REST | `https://api.arkhamintelligence.com/` | Free tier w/ key (unverified) | paid tiers | seconds–minutes | **Entity-labeled wallets** — "this is Jump moving 40m USDC" | Yes | VERIFIED-AUTH (400 = live) |
| 175 | Nansen API | REST | `https://api.nansen.ai/api/beta/` | No real free tier | ~$100–1500/mo (unverified) | minutes | Smart Money labels, token god mode | Yes | VERIFIED-AUTH (401) |
| 176 | Lookonchain | X / web | @lookonchain | Free | Free | **seconds–minutes** | Human-curated whale moves, often the fastest narrative on a wallet | Partial | unverified |
| 177 | DefiLlama TVL | REST | `https://api.llama.fi/protocols` | **Free, no key**, be polite (~1 req/s) | Free | minutes | Protocol TVL moves = capital rotation | Yes | **VERIFIED-200** |
| 178 | DefiLlama hacks | REST | `https://api.llama.fi/hacks` | **Free, no key** | Free | hours | **Structured hack database** — amounts, chains, dates | Yes | **VERIFIED-200** |
| 179 | DefiLlama chains | REST | `https://api.llama.fi/v2/chains` | Free | Free | minutes | Chain-level TVL rotation | Yes | **VERIFIED-200** |
| 180 | DefiLlama unlocks / emissions | REST | `https://api.llama.fi/emissions` | Free | Free | daily | **Token unlock calendar — scheduled sell pressure, perfect for 1–7d holds** | Yes | unverified |
| 181 | DefiLlama stablecoins | REST | `https://stablecoins.llama.fi/stablecoins` | Free | Free | hours | Stablecoin supply = dry powder proxy | Yes | unverified |
| 182 | DefiLlama bridges / yields | REST | `https://bridges.llama.fi/` | Free | Free | hours | Cross-chain capital flow | Yes | unverified |
| 183 | TokenUnlocks | REST/web | `https://token.unlocks.app/` | Free web | paid API (unverified) | daily | Cliff/vesting schedules per token | Partial | BLOCKED (`000` on guessed API path) |
| 184 | CryptoRank unlocks | REST | `https://api.cryptorank.io/v1/` | Free key tier (unverified) | paid | daily | Alternative unlock + funding-round data | Yes | unverified |
| 185 | Etherscan API | REST | `https://api.etherscan.io/api` | **Free key, 5 calls/sec, 100k/day** (unverified numbers) | Pro from ~$200/mo (unverified) | seconds | Contract deploys, large transfers, verified-source events | Yes | **VERIFIED-200** |
| 186 | Blockchair | REST | `https://api.blockchair.com/bitcoin/stats` | **Free, keyless, limited** | paid tiers | minutes | Multi-chain stats in one schema | Yes | **VERIFIED-200** |
| 187 | mempool.space API | REST/WS | `https://mempool.space/api/v1/fees/recommended` | Free, self-hostable | Free | sub-second | BTC fee spikes = congestion/ordinals events | Yes | BLOCKED (`000` here; widely known good — retest) |
| 188 | Dune Analytics API | REST | `https://api.dune.com/api/v1/` | Free tier 1000 credits/mo (unverified) | from ~$390/mo (unverified) | minutes–hours | Any custom on-chain metric you can SQL | Yes | VERIFIED-AUTH (401) |
| 189 | Glassnode | REST | `https://api.glassnode.com/v1/` | Free tier very limited | ~$29–800/mo (unverified) | hours | SOPR, MVRV, exchange balances — regime not event | Yes | unverified |
| 190 | CryptoQuant | REST | `https://api.cryptoquant.com/v1/` | Trial | paid (unverified) | hours | Exchange netflow, miner flows | Yes | unverified |
| 191 | Chainalysis / TRM / Elliptic | REST | — | None | Enterprise | hours | Sanction/hack attribution; mostly a compliance product | Yes | unverified |
| 192 | Helius (Solana) / QuickNode / Alchemy webhooks | WS/webhook | provider sites | Free tiers exist | usage-based | **sub-second** | Push notifications on specific addresses/programs | Yes | unverified |
| 193 | Hypurrscan / Hyperliquid explorers | Web/REST | `https://hypurrscan.io/` | Free | Free | seconds | **Whale positions on your own venue** — visible perp positions are public on HL | Partial | unverified |

---

## 8. Social and sentiment

| # | Name | Access | URL | Free tier | Cost | Latency | Uniquely covers | MR | Verified |
|---|---|---|---|---|---|---|---|---|---|
| 194 | X (Twitter) API v2 | REST/stream | `https://api.x.com/2/` | **Free tier discontinued.** New devs are on pay-per-use: ~$0.005/post read, ~$0.015/post write, capped 2M reads/mo. Legacy $200/mo Basic closed to new signups. | pay-per-use; Enterprise $42k+/yr | **sub-second (filtered stream)** | Where crypto news breaks first, full stop | Yes | Verified via secondary reporting (Feb 2026 pricing change), **not from x.com itself** |
| 195 | X alternatives (twitterapi.io, apidance, socialdata.tools) | REST | vendor sites | Trials | ~$0.15–1.00 per 1k tweets (unverified) | seconds | Much cheaper X access; **ToS-grey, can vanish overnight** | Yes | unverified |
| 196 | Key X accounts to follow | Social | @WatcherGuru @Cointelegraph @unusual_whales @DeItaone @FirstSquawk @lookonchain @WuBlockchain @zerohedge @tier10k @DBCrypto | — | — | seconds | Curated human filter; @DeItaone and @FirstSquawk mirror the wires fastest | Partial | unverified |
| 197 | Reddit API | REST | `https://oauth.reddit.com/` | Free tier 100 QPM w/ OAuth (unverified). Unauthenticated `.json` now **403s** | Commercial from ~$0.24/1k calls (unverified) | minutes | r/CryptoCurrency, r/Bitcoin, r/SatoshiStreetBets retail froth | Yes | VERIFIED (403 on unauth `.json`) |
| 198 | Telegram Bot/Client API | REST/MTProto | `https://api.telegram.org/` | Free | Free | **sub-second** | **Join alpha channels and ingest them directly** — many news bots relay here first | Yes | unverified |
| 199 | Discord | WS/bot | `https://discord.com/developers` | Free | Free | sub-second | Protocol governance + team announcements | Yes | unverified |
| 200 | Farcaster (Neynar / hubs) | REST/WS | `https://api.neynar.com/` (Warpcast API now key-gated) | Free dev tier (unverified) | from ~$9/mo (unverified) | seconds | Crypto-native social with clean, spam-light data | Yes | VERIFIED-AUTH (401 on warpcast) |
| 201 | StockTwits | REST | `https://api.stocktwits.com/api/2/streams/symbol/BTC.X.json` | Public API deprecated/gated (403) | partner only | minutes | Retail equity+crypto sentiment | Yes | VERIFIED (403) |
| 202 | Google Trends (pytrends / SerpApi) | scrape/REST | `https://trends.google.com/` | Unofficial free (fragile — official endpoint 404'd) | SerpApi from ~$50/mo | hours | Retail attention — a slow but real 1–7d factor | Partial | DEAD-404 on guessed path |
| 203 | LunarCrush | REST | `https://lunarcrush.com/developers/api/` | Free tier (unverified) | from ~$24/mo (unverified) | minutes | Social volume/dominance per coin, ranked | Yes | BLOCKED (`000` on old v2 path) |
| 204 | Santiment | GraphQL | `https://api.santiment.net/graphql` | Free tier w/ key | from ~$49/mo (unverified) | hours | Social + on-chain composite metrics, dev activity | Yes | VERIFIED-AUTH (400 = live) |
| 205 | Alternative.me Fear & Greed | REST | `https://api.alternative.me/fng/?limit=1` | **Free, keyless, no limit stated** | Free | daily | The single most-quoted sentiment number | Yes | **VERIFIED-200** |
| 206 | Kaito AI | REST/web | `https://www.kaito.ai/` | Waitlist/paid | Enterprise (unverified) | minutes | **Narrative/mindshare tracking across CT** — what the market is *about to* care about | Partial | unverified |
| 207 | The TIE / Augmento | REST | vendor sites | None | Enterprise | minutes | Institutional crypto sentiment scoring | Yes | unverified |

---

## 9. Geopolitics and world events

Covered by rows 18–19 (GDELT), 95–105 (wires), 103 (Al Jazeera), plus:

- **ACLED** — `https://acleddata.com/data-export-tool/` — free academic/registered access, conflict event data, **weekly** latency. Useful for war-risk regime flags, too slow for trading. *unverified.*
- **Polymarket / Kalshi** — `https://clob.polymarket.com/` and `https://api.elections.kalshi.com/` — free public APIs, sub-second. **Prediction-market odds are the fastest machine-readable read on elections, Fed decisions, wars and tariffs.** Strongly recommended and cheap. *unverified endpoints — check both.*
- **Liveuamap / Wires on Telegram** — free, seconds, geopolitical breaking. Grey-area sourcing.
- **US Federal Register + Congress.gov** (rows 109–110) already cover tariff/sanction rulemaking.

---

## 10. Aggregation infrastructure and low-latency headline vendors

| Name | Access | Free tier | Cost | Latency | Notes | Verified |
|---|---|---|---|---|---|---|
| **Tree of Alpha / Tree News** | WebSocket (Tokyo-hosted) | API key required | Priced in **TREE tokens**, daily-accrued against a USD value set by their DAO — not a flat SaaS fee. Historically has also had a free-ish public tier. | **sub-second** | Monitors ~1000 news sources + ~2000 X accounts, relays through one low-latency WS. The de-facto retail-accessible fast feed. Docs: `docs.treeofalpha.com/websockets/api-key` | Verified it exists + token-based pricing model (from their litepaper/docs via search). **Exact price unverified.** |
| **Phoenix News** | WebSocket/app | Trial | subscription (unverified) | **sub-second** | Curated crypto + macro, filtered. Integrated into third-party terminals. | unverified |
| **BWEnews** | WebSocket/Telegram | Free Telegram, paid WS | subscription (unverified) | **sub-second** | Strong on **Chinese-language and Asian exchange** announcements — often ahead of English feeds. | unverified |
| **Tealstreet** | Terminal | Free tier | paid | sub-second | Bundles Tree/Phoenix/BWE feeds into one UI — useful as a reference for what pros wire. | unverified |
| **FirstSquawk / TradeNewsCast** | Audio squawk + text | none | ~$100–500/mo (unverified) | **sub-second** | Human squawk on macro wires; text API available on higher tiers. | unverified |
| **Newsquawk / Ransquawk** | Audio + API | none | ~$100+/mo (unverified) | sub-second | Macro squawk, institutional-grade | unverified |
| **RSSHub** | Self-hosted RSS | Free, self-host | server cost | minutes | Generates RSS for sites that have none (X accounts, CN outlets, exchange pages). **Very useful for the Asian sources that 403'd above.** | unverified |
| **Feedly / Inoreader API** | REST | Free tiers | ~$10–20/mo | minutes | Managed RSS with dedupe + full-text extraction, if you don't want to run your own poller | unverified |
| **Superfeedr / PubSubHubbub (WebSub)** | Push | free/paid | ~$10+/mo | seconds | Push instead of poll for feeds that support WebSub — cuts latency vs polling | unverified |
| **Cryptohopper/3Commas news modules** | — | — | — | minutes | Retail-bot news modules; mentioned only so you don't waste time on them | unverified |

---

# Ranked Top 25 — if you can only wire 25

Ranked for a 1–7 day Hyperliquid perps bot, balancing latency, coverage and cost.

| Rank | Source | Why it earns the slot | Cost |
|---|---|---|---|
| 1 | **Hyperliquid `/info` + WebSocket** | Your own venue. New perp listings, funding, OI caps, liquidations. Nobody else tells you this first. | Free |
| 2 | **Federal Reserve press RSS** | FOMC is the single largest scheduled crypto vol event. Seconds latency, free, no key. | Free |
| 3 | **BLS latest-release RSS** | CPI and NFP at 08:30 ET. Same argument. | Free |
| 4 | **Forex Factory calendar XML** | Tells you *when* #2 and #3 fire, with impact ratings. Lets you flatten before events instead of reacting. | Free |
| 5 | **Binance announcement CMS/WS** | Listings and delistings. Largest single-token moves in crypto. | Free |
| 6 | **Upbit announcements API** | Korean listings are the most violent pumps that exist. Undocumented but live. | Free |
| 7 | **SEC press releases + litigation RSS** | Enforcement and ETF decisions. Free, seconds. | Free |
| 8 | **CryptoPanic API** | Best single crypto aggregator; one integration replaces 30 RSS feeds. | Free tier |
| 9 | **Tree of Alpha WebSocket** | The only genuinely sub-second broad feed a retail budget can reach. | TREE-token priced |
| 10 | **CoinDesk RSS** | Highest signal-per-article of the majors. | Free |
| 11 | **The Block RSS** | Institutional scoops, exchange investigations. | Free |
| 12 | **Cointelegraph RSS** | Highest volume; drives retail flow even when low quality. | Free |
| 13 | **GDELT DOC API** | Your entire geopolitics + non-English layer for $0. 15-min latency, tone-scored. | Free |
| 14 | **DefiLlama (TVL + hacks + emissions)** | Hacks and **token unlocks** are perfect 1–7d catalysts. Free, keyless. | Free |
| 15 | **Bybit + KuCoin + Gate + MEXC announcement APIs** | Documented, free, covers long-tail listings Binance misses. | Free |
| 16 | **Wu Blockchain + CoinNess + Odaily** | China/Korea policy and flash news, routinely hours ahead of English media. | Free |
| 17 | **Whale Alert** | Exchange inflow spikes precede dumps. Cheap. | ~$20+/mo |
| 18 | **SoSoValue ETF flows (or Farside scrape)** | Daily ETF flow is one of few real 1–7d predictors of BTC. | Free tier |
| 19 | **FRED API** | Regime features: DXY, 2y, real yields, M2. You need these as model inputs, not headlines. | Free |
| 20 | **EDGAR Atom for Strategy/MSTR + treasury cos** | 8-K buy announcements move BTC. Free, minutes. | Free |
| 21 | **X API (or a cheap alternative) on ~50 curated accounts** | Still where things break first. Restrict to a whitelist to control cost. | pay-per-use |
| 22 | **Telegram client ingesting alpha channels** | Free, sub-second, and many fast feeds relay here before anywhere else. | Free |
| 23 | **Polymarket + Kalshi odds** | Machine-readable, sub-second consensus on Fed/elections/geopolitics. | Free |
| 24 | **CourtListener/RECAP** | Docket entries in the big cases land before the news writes them up. | Free |
| 25 | **Alternative.me Fear & Greed + Coinglass funding/OI** | Positioning context. Prevents you from chasing news into a crowded trade. | Free / ~$29 |

Total marginal cost of this stack: roughly **$50–250/month** depending on how you solve X and Tree of Alpha. Everything else is free.

---

# Lowest-latency tier — where the edge actually is

Ordered fastest to slowest. Anything at "minutes" is context, not edge.

**Sub-second (true event-time):**
- Exchange **WebSockets** (Binance announcement stream, Hyperliquid WS). Free. This is the only free sub-second channel and it is the most valuable one.
- **Tree of Alpha WS** — Tokyo-hosted, ~1000 sources + ~2000 X accounts. TREE-token priced.
- **Phoenix News / BWEnews WS** — subscription, unverified pricing, roughly $50–300/mo band based on comparable products.
- **X API filtered stream** on a curated account list — pay-per-use, ~$0.005/read.
- **Telegram MTProto client** on alpha channels — free, and genuinely fast.
- **Benzinga / FirstSquawk / Newsquawk** — $100–1000+/mo, equities-first but macro-fast.
- **Chain webhooks** (Helius/Alchemy/QuickNode) on specific addresses — free tier to usage-priced.

**1–5 seconds (fast polling of a fast origin):**
- Binance/Upbit/Bybit/KuCoin announcement REST, polled at 200–500ms. Free, but you will get rate-limited; use per-exchange budgets and jitter.
- Fed / BLS / SEC RSS polled at 1s in the 60s window around a scheduled release. Free, and the highest-value second in the whole stack.
- Exchange `exchangeInfo` / symbol-list diffing.

**5–60 seconds:**
- CryptoPanic, CoinNess, Odaily, CN flash wires.

**Minutes:**
- Every RSS feed in section 2. Standard news outlets simply do not publish in seconds.

**15 minutes+:**
- GDELT (15-min build cycle), aggregator APIs on free tiers, ETF flows (T+1), Glassnode.

**The honest framing:** at 1–7 day holding periods you are **not** competing on microseconds. The sub-second tier matters for exactly two things — exchange listing/delisting announcements, and scheduled macro prints. For everything else, a 30-second-latency stack performs the same as a 300ms one. Spend the money on the two cases where it matters and take free RSS everywhere else.

---

# The deduplication problem

One CPI print becomes 200 articles in 10 minutes. If you feed that raw into a model, "number of articles" becomes your dominant feature and it measures publisher behaviour, not the world. Concretely:

**Layer 1 — exact/near-exact (cheap, do it first)**
- **Canonical URL**: strip UTM and tracking params, follow redirects once, prefer `<link rel="canonical">` from the article HTML, lowercase host, drop `www.`, drop trailing slash. Hash it. This alone kills 20–30% of duplicates (syndication, AMP, mobile variants).
- **Content hash**: SHA-256 of normalized title+body (lowercase, strip punctuation and whitespace). Catches verbatim syndication (Yahoo republishing Reuters).

**Layer 2 — near-duplicate (the real workhorse)**
- **SimHash (Charikar, 64-bit)**: hash shingles of the text, weight, sum, sign. Two articles are near-duplicates if Hamming distance ≤ 3. Cheap enough to run on every ingest; you index by 4 rotated 16-bit prefixes so lookup is O(1)-ish. This is the classic Google-web-crawl approach and it is still the right answer for news text.
- **MinHash + LSH** (datasketch in Python): estimates Jaccard similarity on shingle sets. Better than SimHash when articles are heavily rewritten but share entities/phrasing. Band-and-row LSH gives you sublinear candidate lookup. Threshold ~0.6–0.7 Jaccard for "same story".
- Rule of thumb: SimHash for speed and syndication, MinHash/LSH for rewritten coverage. Many stacks run both.

**Layer 3 — semantic clustering (same *event*, different words)**
- **Sentence embeddings** (`all-MiniLM-L6-v2` for cheap/local, `bge-base`/`e5` for better, or a hosted embedding API) into a vector index (FAISS, Qdrant, pgvector). Cosine ≥ ~0.85 on title+lede.
- **Online/streaming clustering**, not batch k-means: maintain live clusters, assign each new article to the nearest centroid within threshold, else start a new cluster. Expire clusters after a time window (news events decay — 6–24h is a sensible TTL). This is essentially single-pass leader clustering and it is what production news systems use because you cannot re-cluster the whole corpus on every arrival.
- **Entity + time bucketing before embedding**: only compare articles that share at least one entity (ticker, person, protocol) and fall in the same ~6h window. Cuts the comparison space by orders of magnitude.

**Layer 4 — what you actually emit to the model**
- One record per **cluster**, not per article, with:
  - `first_seen_ts` — earliest ingest timestamp across the cluster. **This is your event time.** Never use the latest article's timestamp.
  - `source_count` and `unique_domain_count` — a real measure of how big the story is (a 40-outlet cluster is a bigger event than a 2-outlet one).
  - `tier_weighted_score` — weight CoinDesk/Bloomberg/The Block above content farms. Maintain a source-tier table manually; it's the single highest-ROI piece of hand-curation in the whole pipeline.
  - `novelty` — is this cluster new, or an update to a cluster you already traded? RavenPack built a business on exactly this field. Compute it as "time since cluster created" + "is this a materially new embedding direction".
- **Never** let a story re-trigger a signal because a 30th outlet picked it up.

**Practical gotchas**
- Publisher `pubDate` in RSS lies constantly (backdated, timezone-less, or set to fetch time). Trust **your own ingest timestamp** for ordering; keep `pubDate` only as metadata.
- Translation duplicates: a Chinese flash and its English rewrite are the same event. Multilingual embeddings (LaBSE, multilingual-e5) handle this; SimHash will not.
- Aggregators (CryptoPanic, NewsAPI) will re-serve you articles you already got from the origin RSS. Dedupe on canonical URL *before* dedupe on content, or you'll double-count.

---

# Practical ingestion notes

**Polling intervals by source type**
| Type | Interval | Reason |
|---|---|---|
| Exchange announcement APIs | 200ms–1s (event windows), 5s baseline | Where the money is; but respect weights |
| Hyperliquid WS / exchange WS | persistent connection | Push, no polling |
| Fed/BLS/SEC RSS | 1s in the ±60s window around a scheduled release, 60s otherwise | Publication is instantaneous at a known time |
| Crypto RSS (section 2) | 60–120s | Publishers update no faster than this |
| Aggregator APIs (CryptoPanic, CoinDesk Data) | 30–60s, budget-aware | Free tiers are call-capped |
| GDELT | 900s (15 min) | That's their build cycle; faster is wasted |
| ETF flows, unlocks, TVL | 1–4×/day | Daily-resolution data |
| X filtered stream | persistent | And bill-capped — set a hard monthly spend limit |

**Respecting rate limits**
- One token-bucket limiter **per host**, not global. Binance's weight system and SEC's 10/sec are different currencies.
- Send a real `User-Agent` with a contact email on all `.gov` requests. SEC will block you otherwise, and it's their stated policy.
- Honour `ETag` / `If-Modified-Since` on every RSS fetch. A 304 costs you nothing and most feeds support it. This alone lets you poll 3× faster within the same budget.
- Honour `Retry-After` on 429. Exponential backoff with jitter; never a tight retry loop.
- Cache aggressively: if two sources give you the same canonical URL, fetch the body once.

**Detecting a stale source** (this is the failure mode that silently kills news bots)
- Track per-source **inter-arrival time**. Compute a rolling median and p95 over 30 days. Alarm when time-since-last-item exceeds ~3× p95. CoinDesk going quiet for 6 hours at 2pm on a Tuesday is a broken feed, not a slow news day.
- Track **HTTP status distribution** per source. A source that flips from 200s to 403s has bot-walled you.
- Track **parse success rate**. Feeds change schema without warning; a 100% fetch rate with 0% parse rate looks healthy on a naive monitor.
- Hold a **canary**: at least one item per source per 24h, or page yourself.
- Never let a dead source silently mean "no news". Emit an explicit `source_stale` flag into the model's feature set so the bot can de-risk rather than assume calm.

**Timestamping "first seen" honestly**
- Record three separate fields, always: `publisher_ts` (what they claim), `fetch_ts` (when your request returned), `ingest_ts` (when it hit your store). Use `fetch_ts` as truth.
- Use **monotonic clocks** for intervals and NTP-synced UTC for absolute stamps. Store UTC only.
- For backtesting this matters enormously: if you backtest on `publisher_ts` you will look like a genius because you'll be reading news before you could actually have had it. Backtest on `fetch_ts` **as recorded at the time**, and never on a timestamp you reconstructed later.
- Log the poll interval alongside each item. An item found by a 60s poller has up to 60s of hidden latency, and your backtest must assume the worst case, not the best.

**Legal / ToS cautions**
- **NewsAPI's free tier explicitly forbids production use** — it's development-only. Using it in a live bot is a licence breach, and it's 24h-delayed anyway.
- **Undocumented endpoints** (Binance `bapi/composite/...`, Upbit `api-manager`, CMC `content/v3`) are internal APIs. They work today, they are not promised to you, they can change or start blocking without notice, and heavy polling of them may breach the site's terms. Wrap each in a circuit breaker and have a fallback. Do not build your only listing detector on one.
- **Scraping full article text** is a different legal question from reading an RSS feed. RSS is published for consumption; scraping paywalled or bot-walled bodies (Farside's Cloudflare, Bitcoin Magazine's 403) is at minimum a ToS breach. For Farside specifically: prefer SoSoValue's API or the issuers' own NAV files over defeating their bot protection.
- **X data resellers** operating outside the official API are in breach of X's developer terms. They're cheap and they work until they don't. Don't make one a single point of failure.
- Respect `robots.txt` for anything you crawl. It's not legally binding everywhere but it is the line between "reasonable" and "indefensible" if anyone complains.
- Store article **text** for your own analysis; do not redistribute it. Derived signals are fine, republishing bodies is not.

---

# Coverage gaps — retail stack vs a Bloomberg terminal

Be clear-eyed about what $200/month cannot buy.

**What you will simply miss:**
1. **The wires themselves.** Reuters and AP terminal feeds are sub-second and licensed. Their public RSS is dead or delayed. When a headline crosses Reuters, a terminal user has it before the article exists anywhere you can read. For a 1–7 day hold this costs you the first 30–120 seconds of a move — survivable, but it means you are never the one setting the price.
2. **Bloomberg First Word / scoops.** Bloomberg breaks a large share of institutional crypto news itself. Their RSS is truncated and lagged. You find out when it's re-reported.
3. **Structured, entity-resolved, novelty-scored news.** RavenPack/Bigdata give a machine relevance and novelty scores per entity, computed consistently for 20 years of history. You can approximate this with embeddings, but you cannot approximate the *history* — which means your news features have no long backtest.
4. **Full-tick consolidated market data across all venues.** Kaiko-grade reference data with proper corporate-action and delisting handling. You'll be stitching free APIs with inconsistent symbology.
5. **Options surfaces and dealer positioning.** Deribit's public API gets you far, but professional vol surface / gamma exposure products cost real money.
6. **Analyst and desk commentary.** Bank research, OTC desk colour, and block-trade flow are simply not available at retail.
7. **Sell-side estimate revisions and embargoed data.** Not accessible.
8. **Historical news archives with point-in-time integrity.** This is the biggest quiet gap. You can collect news from today forward, but you cannot buy a clean, unrevised, point-in-time crypto news archive at retail — so your news-driven model will always have a short training window, and any archive you assemble from web scrapes is contaminated by later edits and by survivorship (deleted articles).

**What you actually get that Bloomberg does not have:**
- Crypto-native on-chain and whale data (Arkham/Nansen/DefiLlama) — better than terminal coverage.
- Exchange announcement APIs at the source, at whatever poll rate you like.
- Chinese/Korean flash wires and Telegram alpha channels.
- Prediction market odds.
- Hyperliquid's own public order book and public whale positions — an information asymmetry that favours you, not the institution.

**The honest conclusion:** at 1–7 day holds, the terminal's latency advantage is nearly irrelevant and its *archive* advantage is the real one. Prioritise starting your own point-in-time capture **today** — store every headline with an honest `fetch_ts` — because in twelve months that archive is the asset you cannot buy.

---

## Verification summary

| Status | Count (approx) |
|---|---|
| VERIFIED-200 (live, hit successfully) | 48 |
| VERIFIED-AUTH (endpoint confirmed live, key required) | 14 |
| BLOCKED (403/`000` from this machine — retest locally) | 14 |
| DEAD-404 (my guessed path was wrong) | 6 |
| unverified (listed from knowledge only) | ~125 |

**Roughly 62 of 207 entries were positively confirmed to exist by direct HTTP request in this session.** Everything else — especially every price and every rate limit not marked verified — is a starting point for your own check, not a fact.

**Highest-priority things to verify before building:**
1. CryptoPanic's actual v2 free-tier limits (their docs page bot-walled me).
2. CoinGecko Demo plan rate limit — their own docs give two different numbers (30/min vs 100/min).
3. Alpha Vantage free-tier daily cap — widely reported to have dropped from 500/day to 25/day.
4. Tree of Alpha's real current cost in TREE terms.
5. The correct RSS paths for CFTC, DOJ, and BlockBeats (my guesses 404'd).
6. Whether the Binance announcement **WebSocket** (as opposed to polling the CMS endpoint) is available on a free key — this is the single biggest latency win available for free.
