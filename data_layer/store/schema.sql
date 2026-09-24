-- ============================================================================
-- UNIFIED STORE — one database for news, market data, and features.
-- Replaces 14 scattered SQLite files that cannot be JOINed.
--
-- RULES ENFORCED BY THIS SCHEMA:
--  1. POINT-IN-TIME: every fact carries when it was TRUE (published_ts /
--     valid_from) AND when WE SAW IT (first_seen_ms / observed_at).
--     Backtests filter on the second one. This is the #1 fake-alpha defence.
--  2. NO TICKER JOINS: assets are joined by canonical id, never by symbol
--     string. venue_symbol carries the multiplier (1000PEPE vs PEPE).
--  3. EVERY time-series table is indexed on (asset_id, ts_ms).
--  4. Features are WIDE tables keyed (ts_ms, asset_id) so families JOIN cheaply.
--  5. Source status is EARNED — see source.status / verified_on.
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- DIMENSIONS

CREATE TABLE IF NOT EXISTS asset (
  id            INTEGER PRIMARY KEY,
  symbol        TEXT NOT NULL UNIQUE,      -- canonical, e.g. 'BTC'
  name          TEXT,
  kind          TEXT,                      -- crypto | equity | commodity | fx | index
  coingecko_id  TEXT,
  first_seen_ms INTEGER,
  last_seen_ms  INTEGER
);

CREATE TABLE IF NOT EXISTS venue (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  kind          TEXT,                      -- cex | dex | perp | spot | data
  jurisdiction  TEXT,
  credibility   REAL DEFAULT 0.5           -- used to weight the consolidated price
);

-- The symbol-collision defence. NEVER join on ticker text.
CREATE TABLE IF NOT EXISTS venue_symbol (
  venue_id      INTEGER NOT NULL REFERENCES venue(id),
  asset_id      INTEGER NOT NULL REFERENCES asset(id),
  symbol        TEXT NOT NULL,             -- venue's own string, e.g. '1000PEPEUSDT'
  quote         TEXT,
  multiplier    REAL DEFAULT 1.0,          -- 1000PEPE -> 1000
  first_seen_ms INTEGER,
  last_seen_ms  INTEGER,
  PRIMARY KEY (venue_id, symbol)
);

-- The registry. status is EARNED, never assumed.
CREATE TABLE IF NOT EXISTS source (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  category      TEXT,                      -- crypto_cex | news | social | macro | onchain | ...
  base_url      TEXT,
  auth          TEXT,                      -- none | key | token
  free          INTEGER DEFAULT 1,
  status        TEXT DEFAULT 'unverified', -- unverified | verified | dead
  verified_on   TEXT,
  http_status   INTEGER,
  latency_ms    INTEGER,
  rate_limit    TEXT,
  notes         TEXT,
  sample_json   TEXT
);

-- ------------------------------------------------------------- MARKET DATA

CREATE TABLE IF NOT EXISTS quote (
  ts_ms     INTEGER NOT NULL,
  venue_id  INTEGER NOT NULL,
  asset_id  INTEGER NOT NULL,
  bid REAL, ask REAL, mid REAL, vol REAL,
  suspect   INTEGER DEFAULT 0,             -- staleness / sanity flag
  PRIMARY KEY (asset_id, ts_ms, venue_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS perp_state (
  ts_ms     INTEGER NOT NULL,
  venue_id  INTEGER NOT NULL,
  asset_id  INTEGER NOT NULL,
  mid REAL, mark REAL, oracle REAL,
  funding_hourly REAL, oi_base REAL, oi_usd REAL, vol24 REAL,
  PRIMARY KEY (asset_id, ts_ms, venue_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS ohlcv (
  ts_ms     INTEGER NOT NULL,
  venue_id  INTEGER NOT NULL,
  asset_id  INTEGER NOT NULL,
  interval  TEXT NOT NULL,
  o REAL, h REAL, l REAL, c REAL, v REAL, n INTEGER,
  PRIMARY KEY (asset_id, interval, ts_ms, venue_id)
) WITHOUT ROWID;

-- The table that was designed and left empty. Microprice lives here.
CREATE TABLE IF NOT EXISTS book (
  ts_ms     INTEGER NOT NULL,
  venue_id  INTEGER NOT NULL,
  asset_id  INTEGER NOT NULL,
  bid REAL, ask REAL, mid REAL, microprice REAL,
  spread_bps REAL, depth_bid_usd REAL, depth_ask_usd REAL, imbalance REAL,
  buy_slip_bps REAL, sell_slip_bps REAL,
  PRIMARY KEY (asset_id, ts_ms, venue_id)
) WITHOUT ROWID;

-- Trades. buyer/seller are populated on transparent venues (Hyperliquid).
CREATE TABLE IF NOT EXISTS trade (
  tid       INTEGER,
  ts_ms     INTEGER NOT NULL,
  venue_id  INTEGER NOT NULL,
  asset_id  INTEGER NOT NULL,
  px REAL, sz REAL, side TEXT,
  buyer TEXT, seller TEXT,
  hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_trade_asset_ts ON trade(asset_id, ts_ms);
CREATE INDEX IF NOT EXISTS idx_trade_buyer    ON trade(buyer)  WHERE buyer  IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_seller   ON trade(seller) WHERE seller IS NOT NULL;

CREATE TABLE IF NOT EXISTS positioning (
  ts_ms     INTEGER NOT NULL,
  venue_id  INTEGER NOT NULL,
  asset_id  INTEGER NOT NULL,
  period    TEXT NOT NULL,
  oi_coins REAL, oi_usd REAL,
  long_frac REAL, ls_ratio REAL,
  top_long_frac REAL, top_ls_ratio REAL,
  taker_buy_vol REAL, taker_ratio REAL,
  PRIMARY KEY (asset_id, period, ts_ms, venue_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS liquidation (
  ts_ms INTEGER NOT NULL, venue_id INTEGER, asset_id INTEGER,
  side TEXT, px REAL, sz_usd REAL
);
CREATE INDEX IF NOT EXISTS idx_liq_asset_ts ON liquidation(asset_id, ts_ms);

-- ------------------------------------------------------------------- NEWS

-- Editorial / official documents. dedup_cluster_id collapses the same story
-- republished by 40 outlets into ONE event.
CREATE TABLE IF NOT EXISTS document (
  id            INTEGER PRIMARY KEY,
  source_id     INTEGER REFERENCES source(id),
  source_name   TEXT,
  url           TEXT UNIQUE,
  published_ts  INTEGER,                   -- when it happened
  first_seen_ms INTEGER NOT NULL,          -- when WE saw it  <-- backtest on this
  title         TEXT,
  body          TEXT,
  lang          TEXT,
  author        TEXT,
  source_tier   INTEGER,                   -- 1 official/primary .. 4 anon social
  dedup_cluster_id INTEGER,
  extra         TEXT
);
CREATE INDEX IF NOT EXISTS idx_doc_seen    ON document(first_seen_ms);
CREATE INDEX IF NOT EXISTS idx_doc_cluster ON document(dedup_cluster_id);

CREATE TABLE IF NOT EXISTS social_post (
  id            INTEGER PRIMARY KEY,
  source_name   TEXT NOT NULL,
  channel       TEXT NOT NULL,
  post_id       TEXT,
  published_ts  INTEGER,
  first_seen_ms INTEGER NOT NULL,
  author        TEXT,
  text          TEXT,
  url           TEXT,
  stated_sentiment TEXT,
  extra         TEXT,
  UNIQUE(source_name, channel, post_id)
);
CREATE INDEX IF NOT EXISTS idx_social_seen ON social_post(first_seen_ms);

-- A typed event, extracted from documents. NOT a sentiment score.
CREATE TABLE IF NOT EXISTS event (
  id            INTEGER PRIMARY KEY,
  event_type    TEXT NOT NULL,             -- hack|unlock|listing|enforcement|macro|...
  asset_id      INTEGER REFERENCES asset(id),
  entity        TEXT,
  ts            INTEGER,                   -- when the event occurred
  first_seen_ms INTEGER NOT NULL,          -- when WE could have known
  scheduled     INTEGER DEFAULT 0,         -- THE discriminator: scheduled=>fade, surprise=>follow
  magnitude     REAL,
  magnitude_unit TEXT,
  novelty       REAL,
  surprise      REAL,
  priced_in     REAL,
  source_tier   INTEGER,
  confidence    REAL,
  doc_id        INTEGER REFERENCES document(id),
  payload       TEXT
);
CREATE INDEX IF NOT EXISTS idx_event_asset_ts ON event(asset_id, ts);
CREATE INDEX IF NOT EXISTS idx_event_type     ON event(event_type);

-- THE CALENDAR: future rows that MUTATE. Different object from a feed.
CREATE TABLE IF NOT EXISTS scheduled_event (
  id             INTEGER PRIMARY KEY,
  kind           TEXT NOT NULL,            -- cb_decision|macro_release|earnings|unlock|expiry|...
  entity         TEXT,
  asset_id       INTEGER REFERENCES asset(id),
  jurisdiction   TEXT,
  scheduled_ts   INTEGER NOT NULL,
  local_ts       TEXT, tz_id TEXT,
  ts_precision   TEXT,                     -- exact_minute|hour|day|week|month|quarter
  confirmed      INTEGER DEFAULT 0,
  source_url     TEXT,
  consensus      REAL, previous REAL,
  realized_ts    INTEGER, realized_value REAL, surprise REAL,
  valid_from     INTEGER,                  -- BITEMPORAL
  observed_at    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sched_ts   ON scheduled_event(scheduled_ts);
CREATE INDEX IF NOT EXISTS idx_sched_kind ON scheduled_event(kind);

CREATE TABLE IF NOT EXISTS scheduled_event_revision (
  event_id   INTEGER NOT NULL REFERENCES scheduled_event(id),
  changed_at INTEGER NOT NULL,
  field      TEXT, old_value TEXT, new_value TEXT
);

-- Realised outcomes -> this is what turns precedent lookup into a JOIN with an N.
CREATE TABLE IF NOT EXISTS event_outcome (
  event_id   INTEGER NOT NULL,
  asset_id   INTEGER NOT NULL,
  horizon    TEXT NOT NULL,                -- 5m|1h|4h|1d|3d|7d|30d
  ret        REAL,
  ret_resid  REAL,                         -- BTC-beta removed
  vol_realized REAL,
  session_bucket TEXT,
  PRIMARY KEY (event_id, asset_id, horizon)
);

-- ---------------------------------------------------------------- FEATURES
-- WIDE tables, keyed (ts_ms, asset_id), one per family so they JOIN cheaply.
-- Adding a feature = ALTER TABLE ADD COLUMN, no migration of history.

CREATE TABLE IF NOT EXISTS feat_price (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  cp REAL,                                  -- consolidated price
  r_5m REAL, r_1h REAL, r_4h REAL, r_1d REAL, r_3d REAL, r_7d REAL, r_30d REAL,
  mom_7d_skip1 REAL, rev_1d REAL,
  resid_r_1d REAL, resid_r_7d REAL, resid_mom_7d_skip1 REAL,
  sma_20 REAL, ema_12 REAL, ema_26 REAL, macd REAL, macd_signal REAL, macd_hist REAL,
  adx_14 REAL, di_plus REAL, di_minus REAL,
  rsi_14 REAL, stoch_k REAL, stoch_d REAL, cci_20 REAL, roc_10 REAL, willr_14 REAL,
  session_bucket TEXT,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS feat_vol (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  rv REAL, rv_clean REAL, parkinson REAL, garman_klass REAL, rogers_satchell REAL,
  yang_zhang REAL, bipower REAL, jump_frac REAL,
  atr_14 REAL, bb_width REAL, keltner_width REAL, donchian_width REAL,
  ewma_vol REAL, garch_fc REAL, har_fc REAL, vol_of_vol REAL,
  skew_realized REAL, kurt_realized REAL,
  semi_vol_down REAL, semi_vol_up REAL, ud_vol_ratio REAL,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS feat_liq (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  spread_bps REAL, spread_z REAL, spread_eff_bps REAL,
  roll REAL, corwin_schultz REAL, abdi_ranaldo REAL,
  amihud_log REAL, impact_proxy REAL,
  depth_tob_usd REAL, depth_5spread_usd REAL, depth_2pct_usd REAL,
  slippage_bps_1k REAL, slippage_bps_10k REAL,
  turnover REAL, adv_7d REAL, adv_30d REAL,
  spread_hl_rel REAL, spread_widen_breadth REAL,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS feat_micro (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  microprice REAL, book_imbalance REAL, ofi REAL,
  trade_sign_imb REAL, vpin REAL,
  sweep_flag INTEGER, absorption_flag INTEGER, refill_rate REAL,
  kyle_lambda_proxy REAL,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS feat_flow (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  vol_surprise REAL, credible_vol_usd REAL, fringe_vol_share REAL,
  hhi REAL, n_eff REAL, hl_vol_share REAL,
  cvd REAL, taker_imbalance REAL,
  obv REAL, vwap REAL, cmf REAL, ad_line REAL, force_index REAL,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS feat_deriv (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  funding REAL, funding_z REAL, funding_carry_7d REAL, funding_expected REAL,
  sp_basis_bps REAL, perp_basis_bps REAL, hl_basis_resid REAL, funding_gap REAL,
  oi_usd REAL, oi_chg_1d REAL, oi_price_regime INTEGER,
  liq_vol_1h REAL, liq_cluster_score REAL,
  long_frac REAL, ls_ratio REAL, top_long_frac REAL, top_ls_ratio REAL,
  top_minus_retail REAL, cascade_fragility REAL,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS feat_xvenue (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  n_venues INTEGER, n_stale INTEGER,
  disp_iqr_bps REAL, disp_z REAL, hl_dev_bps REAL,
  prem_ma_bps REAL, prem_resid_bps REAL,
  premium_krw_bps REAL, premium_inr_bps REAL, kimchi_breadth REAL,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS feat_xsec (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  beta_btc REAL, beta_eth REAL, corr_btc_30d REAL, corr_break_flag INTEGER,
  cluster_id INTEGER, sector_resid REAL, rrg_x REAL, rrg_y REAL,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS feat_options (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  atm_iv_7d REAL, atm_iv_30d REAL, atm_iv_90d REAL,
  rr_25d REAL, bf_25d REAL, skew REAL, smile_curv REAL,
  term_ratio_30_7 REAL, fwd_vol REAL, vrp REAL,
  put_call_ratio REAL, max_pain REAL, gex REAL, vanna REAL, charm REAL,
  iv_rank REAL, iv_pctile REAL,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS feat_onchain (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  exch_netflow_usd REAL, stablecoin_supply REAL, tvl_usd REAL,
  active_addresses REAL, whale_net_pos REAL, whale_flip_flag INTEGER,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS feat_regime (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  vol_regime TEXT, trend_regime TEXT, funding_regime TEXT, liq_regime TEXT,
  hmm_state INTEGER, stress_score REAL, breadth REAL, btc_dominance REAL,
  session_bucket TEXT,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS feat_calendar (
  ts_ms INTEGER NOT NULL, asset_id INTEGER NOT NULL,
  days_to_next_event REAL, next_event_kind TEXT,
  in_fed_blackout INTEGER, collision_flag INTEGER,
  expected_funding_through_event REAL,
  hist_move_median REAL, hist_move_n INTEGER,   -- N is MANDATORY
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

-- ------------------------------------------------------- TRADING / LEARNING

CREATE TABLE IF NOT EXISTS ord (
  id INTEGER PRIMARY KEY,
  decision_ms INTEGER, decision_px REAL,     -- for TCA: the price when we DECIDED
  sent_ms INTEGER, arrival_px REAL,          -- the benchmark
  venue_id INTEGER, asset_id INTEGER,
  side TEXT, size REAL, order_type TEXT,
  status TEXT, thesis_id INTEGER
);

CREATE TABLE IF NOT EXISTS fill (
  id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES ord(id),
  ts_ms INTEGER, px REAL, sz REAL, fee REAL, liquidity TEXT  -- maker|taker
);

CREATE TABLE IF NOT EXISTS position (
  id INTEGER PRIMARY KEY,
  legacy_id TEXT UNIQUE,                     -- legacy hash ids are TEXT, keep the link
  opened_ms INTEGER, closed_ms INTEGER,
  venue_id INTEGER, asset_id INTEGER,
  side TEXT, size REAL, notional_usd REAL,
  entry_px REAL, exit_px REAL, mark_px REAL, btc_entry_px REAL,
  leverage REAL, margin_usd REAL,
  stop_px REAL, target_px REAL, hold_hours REAL,
  funding_usd REAL, fees_paid REAL, pnl_usd REAL,
  status TEXT, exit_reason TEXT, is_hedge INTEGER, tag TEXT,
  thesis_text TEXT, thesis_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_position_asset ON position(asset_id, opened_ms);

-- Every thesis stored as a PREDICTION with its reasoning, then graded.
CREATE TABLE IF NOT EXISTS thesis (
  id INTEGER PRIMARY KEY,
  legacy_id TEXT UNIQUE,
  created_ms INTEGER NOT NULL,
  asset_id INTEGER, source TEXT,
  direction TEXT, horizon_h REAL, confidence REAL, size_pct REAL,
  entry_px REAL, expected_move_pct REAL, invalidation_px REAL,
  reasoning TEXT, causal_chain TEXT, features_json TEXT,
  event_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_thesis_asset ON thesis(asset_id, created_ms);

CREATE TABLE IF NOT EXISTS thesis_outcome (
  thesis_id INTEGER PRIMARY KEY REFERENCES thesis(id),
  graded_ms INTEGER,
  exit_px REAL,
  ret_pct REAL,                              -- raw return
  funding_pct REAL,                          -- funding is a cost line, tracked separately
  net_ret_pct REAL,                          -- after funding
  mkt_ret_pct REAL,                          -- what BTC did
  excess_pct REAL,                           -- the part that was actually ours
  correct INTEGER, brier REAL,
  reasoning_correct INTEGER, outcome TEXT, failure_mode TEXT, lesson TEXT
);

-- ------------------------------------------------------------- OPERATIONS

-- Human/agent review of a closed position — the qualitative half of learning.
CREATE TABLE IF NOT EXISTS position_review (
  position_id  INTEGER REFERENCES position(id),
  recorded_ms  INTEGER,
  pnl_usd      REAL,
  worked       INTEGER,
  outcome      TEXT,
  lesson       TEXT,
  exit_reason  TEXT
);

-- ------------------------------------------------- UNIVERSE / SURVIVORSHIP

-- Point-in-time universe: which assets existed and were tradeable on a date.
-- Backtests MUST filter on this or they silently exclude everything that died
-- (CROSS_VENUE_FEATURES.md §6.4 — the left tail of the return distribution).
CREATE TABLE IF NOT EXISTS universe_pit (
  ts_ms      INTEGER NOT NULL,
  asset_id   INTEGER NOT NULL,
  on_hl      INTEGER,
  n_venues   INTEGER,
  hl_vol_usd REAL,
  PRIMARY KEY (asset_id, ts_ms)
) WITHOUT ROWID;

-- Listing / delisting / leverage changes = scheduled-ish catalysts.
CREATE TABLE IF NOT EXISTS listing_change (
  ts_ms    INTEGER NOT NULL,
  venue_id INTEGER,
  asset_id INTEGER,
  change   TEXT,
  detail   TEXT
);
CREATE INDEX IF NOT EXISTS idx_listing_ts ON listing_change(ts_ms);

CREATE TABLE IF NOT EXISTS listing_state (
  venue_id     INTEGER NOT NULL,
  asset_id     INTEGER NOT NULL,
  max_leverage REAL,
  delisted     INTEGER DEFAULT 0,
  PRIMARY KEY (venue_id, asset_id)
);

-- Cross-venue price gaps (HL vs other venues).
CREATE TABLE IF NOT EXISTS venue_gap (
  ts_ms INTEGER NOT NULL, asset_id INTEGER, venue_id INTEGER,
  hl_bid REAL, hl_ask REAL, hl_mid REAL, hl_mark REAL, hl_oracle REAL,
  v_bid REAL, v_ask REAL, v_mid REAL, gap_bps REAL
);
CREATE INDEX IF NOT EXISTS idx_gap_asset_ts ON venue_gap(asset_id, ts_ms);

-- ------------------------------------------------------ SIGNALS / DECISIONS

-- Our own historical signal output — the LONGEST series we own.
CREATE TABLE IF NOT EXISTS signal_log (
  id        INTEGER PRIMARY KEY,
  ts_ms     INTEGER NOT NULL,
  as_of     INTEGER,
  asset_id  INTEGER,
  mode      TEXT,
  direction TEXT,
  score     REAL,
  exp_move  REAL,
  entry_px  REAL,
  btc_entry REAL,
  matured   INTEGER,
  exit_px   REAL
);
CREATE INDEX IF NOT EXISTS idx_signal_asset_ts ON signal_log(asset_id, ts_ms);

-- Pre-trade gate decisions + what happened after (allowed vs blocked).
CREATE TABLE IF NOT EXISTS gate_log (
  id           INTEGER PRIMARY KEY,
  ts_ms        INTEGER NOT NULL,
  as_of        INTEGER,
  asset_id     INTEGER,
  allowed      INTEGER,
  block_reason TEXT,
  entry_px     REAL,
  btc_entry    REAL,
  beta         REAL,
  matured      INTEGER,
  exit_px      REAL,
  btc_exit     REAL
);
CREATE INDEX IF NOT EXISTS idx_gate_asset_ts ON gate_log(asset_id, ts_ms);

CREATE TABLE IF NOT EXISTS trigger_rule (
  id INTEGER PRIMARY KEY, created_ms INTEGER, asset_id INTEGER,
  kind TEXT, side TEXT, pct REAL, level REAL,
  floor REAL, peak REAL, trough REAL, stop_pct REAL, target_pct REAL
);

CREATE TABLE IF NOT EXISTS alert (
  id INTEGER PRIMARY KEY, ts_ms INTEGER, asset_id INTEGER,
  level TEXT, message TEXT
);
CREATE INDEX IF NOT EXISTS idx_alert_ts ON alert(ts_ms);

CREATE TABLE IF NOT EXISTS risk_state (
  ts_ms INTEGER NOT NULL, bp_score REAL, bp_level TEXT,
  crash_score REAL, crash_level TEXT, detail TEXT
);

CREATE TABLE IF NOT EXISTS watchlist (
  id INTEGER PRIMARY KEY, asset_id INTEGER, added_ms INTEGER, added_px REAL,
  kind TEXT, bull_side TEXT, bear_side TEXT, lean TEXT, quant REAL,
  status TEXT, resolved_ms INTEGER, winner TEXT
);

-- ------------------------------------------------------- ACCOUNT / RESEARCH

CREATE TABLE IF NOT EXISTS equity_curve (
  ts_ms      INTEGER PRIMARY KEY,
  total_pnl  REAL, realized REAL, unrealized REAL, n_open INTEGER
);

CREATE TABLE IF NOT EXISTS account_state (
  ts_ms INTEGER PRIMARY KEY, balance REAL, realized_pnl REAL, fees_paid REAL
);

-- Written research notes (human/agent), kept so precedent lookup can cite them.
CREATE TABLE IF NOT EXISTS research_note (
  id INTEGER PRIMARY KEY, asset_id INTEGER, created_ms INTEGER,
  headline TEXT, what_it_is TEXT, sector TEXT, catalysts TEXT,
  sentiment TEXT, bull TEXT, bear TEXT, verdict TEXT, confidence REAL
);

CREATE TABLE IF NOT EXISTS intel_report (
  asset_id INTEGER PRIMARY KEY, updated_ms INTEGER,
  short_score REAL, long_score REAL, sentiment_short TEXT, sentiment_long TEXT,
  catalyst_strength REAL, sector_heat REAL, influence REAL, conviction REAL,
  short_term TEXT, long_term TEXT
);

-- The entry-time snapshot of a position's thesis and signals.
CREATE TABLE IF NOT EXISTS position_entry_note (
  position_id INTEGER, asset_id INTEGER, side TEXT,
  snapshot_ms INTEGER, thesis TEXT, signals TEXT
);

CREATE TABLE IF NOT EXISTS collector_run (
  ts_ms INTEGER NOT NULL, source_name TEXT NOT NULL,
  ok INTEGER, rows_new INTEGER, took_ms INTEGER, error TEXT
);
CREATE INDEX IF NOT EXISTS idx_run_ts ON collector_run(ts_ms);

CREATE TABLE IF NOT EXISTS data_quality (
  ts_ms INTEGER NOT NULL, table_name TEXT, asset_id INTEGER,
  check_name TEXT, passed INTEGER, detail TEXT
);
