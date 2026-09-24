"""Endpoints, limits and enums for Hyperliquid. All values verified against the
live API and https://hyperliquid.gitbook.io/hyperliquid-docs (Aug 2026)."""

MAINNET_API = "https://api.hyperliquid.xyz"
TESTNET_API = "https://api.hyperliquid-testnet.xyz"
MAINNET_WS = "wss://api.hyperliquid.xyz/ws"
TESTNET_WS = "wss://api.hyperliquid-testnet.xyz/ws"

# ---- rate limits (IP based) -------------------------------------------------
# Aggregate REST weight budget is 1200 / minute per IP.
IP_WEIGHT_PER_MIN = 1200

# Cheap requests cost 2, everything else costs 20, userRole costs 60.
WEIGHT_2 = {
    "l2Book", "allMids", "clearinghouseState", "orderStatus",
    "spotClearinghouseState", "exchangeStatus",
}
WEIGHT_60 = {"userRole"}
DEFAULT_WEIGHT = 20

# Paged responses add weight per items returned.
EXTRA_WEIGHT_PER_20 = {
    "recentTrades", "historicalOrders", "userFills", "userFillsByTime",
    "fundingHistory", "userFunding", "nonUserFundingUpdates", "twapHistory",
    "userTwapSliceFills", "userTwapSliceFillsByTime", "delegatorHistory",
    "delegatorRewards", "validatorStats",
}
EXTRA_WEIGHT_PER_60 = {"candleSnapshot"}

# ---- websocket limits -------------------------------------------------------
WS_MAX_CONNECTIONS = 10
WS_MAX_SUBSCRIPTIONS = 1000
WS_MAX_UNIQUE_USERS = 10
WS_MSGS_PER_MIN = 2000
WS_MAX_INFLIGHT_POSTS = 100
WS_PING_SECONDS = 30          # server drops idle connections at ~60s

# ---- market conventions -----------------------------------------------------
PERP_MAX_DECIMALS = 6         # price decimals <= 6 - szDecimals
SPOT_MAX_DECIMALS = 8         # price decimals <= 8 - szDecimals
PRICE_SIG_FIGS = 5            # except integers, which are always allowed
FUNDING_INTERVAL_HOURS = 1    # Hyperliquid charges funding every hour
HOURS_PER_YEAR = 24 * 365

INTERVALS = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h",
             "12h", "1d", "3d", "1w", "1M")
INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000,
    "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000,
    "3d": 259_200_000, "1w": 604_800_000, "1M": 2_592_000_000,
}
MAX_CANDLES = 5000            # server only keeps the most recent 5000

SIDE_BID, SIDE_ASK = "B", "A"
