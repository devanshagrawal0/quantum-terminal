"""Universe cache: asset ids, decimals, leverage, and the price/size rounding
rules the exchange enforces. Get this wrong and orders get rejected, so the
rules live in one place and are unit-testable.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .constants import PERP_MAX_DECIMALS, PRICE_SIG_FIGS, SPOT_MAX_DECIMALS
from .info import Info


class Universe:
    """Perp + spot metadata, refreshed lazily (new listings appear often)."""

    def __init__(self, info: Info, ttl_seconds: float = 600.0):
        self.info = info
        self.ttl = ttl_seconds
        self._fetched_at = 0.0
        self.perp_universe: List[Dict[str, Any]] = []
        self.perp_index: Dict[str, int] = {}
        self.margin_tables: Dict[int, Any] = {}
        self.spot_universe: List[Dict[str, Any]] = []
        self.spot_tokens: List[Dict[str, Any]] = []
        self.spot_index: Dict[str, int] = {}
        self.spot_pair_for_token: Dict[str, str] = {}

    # ---- loading -----------------------------------------------------------
    def refresh(self, force: bool = False) -> None:
        if not force and time.time() - self._fetched_at < self.ttl and self.perp_universe:
            return
        meta = self.info.meta()
        self.perp_universe = meta["universe"]
        self.perp_index = {a["name"]: i for i, a in enumerate(self.perp_universe)}
        self.margin_tables = {int(t[0]): t[1] for t in meta.get("marginTables", [])}

        spot = self.info.spot_meta()
        self.spot_universe = spot["universe"]
        self.spot_tokens = spot["tokens"]
        self.spot_index = {p["name"]: i for i, p in enumerate(self.spot_universe)}
        # Map base token name -> canonical pair name, so a perp can be paired
        # with its spot market when one exists.
        self.spot_pair_for_token = {}
        for pair in self.spot_universe:
            base_id = pair["tokens"][0]
            if base_id < len(self.spot_tokens):
                base = self.spot_tokens[base_id]["name"]
                if pair.get("isCanonical") or base not in self.spot_pair_for_token:
                    self.spot_pair_for_token[base] = pair["name"]
        # Bridged spot assets are listed under a "U" prefix (UBTC, UETH, USOL)
        # while the perp keeps the bare ticker. Alias the stripped name when it
        # is a real perp, so BTC -> UBTC/USDC resolves. Derived from the live
        # token list, not a fixed list of coins.
        for token_name, pair_name in list(self.spot_pair_for_token.items()):
            if len(token_name) > 1 and token_name.startswith("U"):
                bare = token_name[1:]
                if bare in self.perp_index and bare not in self.spot_pair_for_token:
                    self.spot_pair_for_token[bare] = pair_name
        self._fetched_at = time.time()

    def _ensure(self) -> None:
        if not self.perp_universe:
            self.refresh()

    # ---- lookups -----------------------------------------------------------
    def coins(self) -> List[str]:
        self._ensure()
        return [a["name"] for a in self.perp_universe]

    def perp(self, coin: str) -> Dict[str, Any]:
        self._ensure()
        if coin not in self.perp_index:
            self.refresh(force=True)
        if coin not in self.perp_index:
            raise KeyError(f"{coin} is not a Hyperliquid perp")
        return self.perp_universe[self.perp_index[coin]]

    def asset_id(self, coin: str) -> int:
        """Exchange asset id: perp index, or 10000 + spot pair index for spot."""
        self._ensure()
        if coin in self.perp_index:
            return self.perp_index[coin]
        if coin in self.spot_index:
            return 10_000 + self.spot_index[coin]
        raise KeyError(f"unknown asset {coin}")

    def sz_decimals(self, coin: str) -> int:
        self._ensure()
        if coin in self.perp_index:
            return int(self.perp(coin)["szDecimals"])
        if coin in self.spot_index:
            pair = self.spot_universe[self.spot_index[coin]]
            return int(self.spot_tokens[pair["tokens"][0]]["szDecimals"])
        raise KeyError(f"unknown asset {coin}")

    def max_leverage(self, coin: str) -> int:
        return int(self.perp(coin)["maxLeverage"])

    def margin_table(self, coin: str) -> Any:
        self._ensure()
        return self.margin_tables.get(int(self.perp(coin).get("marginTableId", -1)))

    def spot_pair(self, coin: str) -> Optional[str]:
        """API name of the canonical spot market, e.g. BTC -> "@142".

        Only a handful of spot markets carry a readable name (PURR/USDC); the
        rest are addressed as "@<index>", and that is the string the l2Book and
        candle endpoints expect. Use spot_pair_label() for display.
        """
        self._ensure()
        return self.spot_pair_for_token.get(coin)

    def spot_pair_label(self, coin: str) -> Optional[str]:
        """Readable form of the spot pair, e.g. BTC -> "UBTC/USDC"."""
        name = self.spot_pair(coin)
        if not name:
            return None
        for pair in self.spot_universe:
            if pair["name"] == name:
                try:
                    return "/".join(self.spot_tokens[t]["name"] for t in pair["tokens"])
                except (IndexError, KeyError):
                    return name
        return name

    def is_spot(self, coin: str) -> bool:
        self._ensure()
        return coin in self.spot_index

    # ---- exchange rounding rules ------------------------------------------
    def round_px(self, coin: str, px: float) -> float:
        """Prices: max 5 significant figures AND max (MAX_DECIMALS - szDecimals)
        decimal places. Integers are always accepted regardless of sig figs."""
        return round_px_raw(px, self.sz_decimals(coin), self.is_spot(coin))

    def round_sz(self, coin: str, sz: float) -> float:
        return round(float(sz), self.sz_decimals(coin))


def round_px_raw(px: float, sz_decimals: int, is_spot: bool = False) -> float:
    px = float(px)
    if px <= 0:
        raise ValueError("price must be positive")
    max_dec = (SPOT_MAX_DECIMALS if is_spot else PERP_MAX_DECIMALS) - sz_decimals
    if px >= 10 ** (PRICE_SIG_FIGS - 1):
        # Already >= 5 digits before the point: only integers are representable.
        return float(round(px))
    return round(float(f"%.{PRICE_SIG_FIGS}g" % px), max_dec)


def valid_px(px: float, sz_decimals: int, is_spot: bool = False) -> bool:
    return round_px_raw(px, sz_decimals, is_spot) == float(px)
