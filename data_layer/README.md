# DATA LAYER — architecture & contract

**Purpose:** one disciplined way in for every piece of external data. If a source dies, changes shape, or gets rate-limited, **nothing downstream breaks.**

This is the layer everything in `newsystem.md` sits on. Read this before adding any source.

---

## The five layers (never skip one)

```
  providers/     FETCH ONLY.  One module per provider. Knows its API, its auth,
                 its rate limit, its quirks. Returns a NORMALIZED contract record.
                 Never writes to disk. Never schedules itself.
        │
  contracts/     The normalized record shapes. Every provider MUST emit one of
                 these. This is what stops a provider change from breaking
                 anything downstream.
        │
  collectors/    SCHEDULE + ORCHESTRATE. Calls providers, handles retry/backoff,
                 writes through store/. One collector may use many providers.
        │
  store/         PERSIST. Schema, upserts, dedup keys, point-in-time discipline.
                 Nothing else touches the DB files directly.
        │
  quality/       VALIDATE. Freshness SLAs, gap detection, duplicate clustering,
                 outlier flags, LLM-contamination probes (newsystem.md §13).
```

**Rule:** a layer may only call the layer directly above it. A collector never
hand-rolls an HTTP call; a provider never writes to a database.

---

## Why this shape (the failure it prevents)

The old layout put fetch + schedule + persist in one flat script per job
(`record_social.py`, `record_venues.py`, …). That works until:

- an API changes response shape → the collector silently writes garbage
- a source dies → you find out days later from a stale chart
- you want the same provider in two collectors → copy-paste drift
- you need point-in-time correctness → it was never recorded

Provider abstraction is the pattern OpenBB uses, and the numeric/narration split
is FinRobot's (see `newsystem.md` §6). Both exist for exactly this reason.

---

## Provider contract (every provider implements this)

```python
class Provider:
    name: str            # "binance_futures"
    category: str        # matches the directory it lives in
    auth: str            # "none" | "key" | "token"
    free: bool
    rate_limit: str      # documented, enforced by the collector
    status: str          # "verified" | "unverified" | "dead"

    def fetch(self, **params) -> list[Record]:
        """Return NORMALIZED contract records. Raise on failure — never
        return partial/garbage. The collector decides retry policy."""
```

**Status values are earned, not assumed:**
- `verified` — we called it and saw real data. Date of verification recorded.
- `unverified` — referenced in code/docs but never confirmed working.
- `dead` — confirmed broken (e.g. HL `leaderboard` → HTTP 422 on 2026-09-02).

---

## Point-in-time discipline (non-negotiable)

Every stored record carries **both**:

- `publish_ts` — when the event/data actually happened
- `first_seen_ms` — when **we** first observed it

Backtests must filter on `first_seen_ms`, never `publish_ts`. Without this,
every backtest silently look-aheads. This is the storage-side half of
`newsystem.md` §12.4/§13.

---

## Categories (each has its own section in `SOURCES.md`)

| Directory | What belongs here |
|---|---|
| `crypto_cex/` | Centralised exchange market data (price, book, trades, funding, OI, L/S ratios) |
| `crypto_onchain/` | On-chain & transparent-venue data (Hyperliquid wallets, Lighter, DefiLlama, TVL, stablecoins) |
| `derivatives/` | Options chains, vol surfaces, skew, DVOL |
| `news/` | Editorial + official announcements (RSS, exchange notices, regulators) |
| `social/` | Crowd text (Reddit, StockTwits, 4chan, Telegram, Farcaster, LunarCrush, X) |
| `macro/` | Rates, FX, commodities, inflation, liquidity (FRED, Treasury, Yahoo, BEA) |
| `prediction_markets/` | Kalshi, Polymarket — implied probabilities (the "what was expected" input for §3.3's priced-in agent) |
| `reference/` | Slow-moving facts: token metadata, unlock calendars, SEC filings, arXiv |

**Adding a source = add it to its category directory AND its section in
`SOURCES.md` AND `registry/sources.yaml`. All three, or it doesn't exist.**

---

## Single source of truth

`registry/sources.yaml` is machine-readable and authoritative: every source, its
category, auth, cost, rate limit, verification status and freshness SLA.
`SOURCES.md` is the human-readable version with the per-API detail.
`quality/` reads the registry to know what "healthy" means for each source.
