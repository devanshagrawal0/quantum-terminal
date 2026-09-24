"""Read-only view of a Hyperliquid account.

No key material is touched here - the /info endpoint takes a public address and
returns state. Nothing in this package can place, cancel or sign an order.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import pandas as pd

from .info import Info, now_ms


def _f(x: Any) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


class Account:
    def __init__(self, address: Optional[str] = None, info: Optional[Info] = None,
                 testnet: bool = False):
        self.address = (address or os.getenv("HL_ACCOUNT_ADDRESS") or "").strip()
        if not self.address:
            raise ValueError(
                "no address: pass address=... or set HL_ACCOUNT_ADDRESS "
                "(your public 0x wallet address - never a private key)")
        if not self.address.startswith("0x"):
            raise ValueError(f"address should start with 0x, got {self.address!r}")
        self.info = info or Info(testnet=testnet)

    # ---- state -------------------------------------------------------------
    def state(self) -> Dict[str, Any]:
        return self.info.clearinghouse_state(self.address)

    def equity(self) -> Dict[str, Any]:
        s = self.state()
        ms = s.get("marginSummary", {})
        cross = s.get("crossMarginSummary", {})
        return {
            "account_value": _f(ms.get("accountValue")),
            "total_notional": _f(ms.get("totalNtlPos")),
            "total_margin_used": _f(ms.get("totalMarginUsed")),
            "total_raw_usd": _f(ms.get("totalRawUsd")),
            "cross_account_value": _f(cross.get("accountValue")),
            "cross_maintenance_margin": _f(s.get("crossMaintenanceMarginUsed")),
            "withdrawable": _f(s.get("withdrawable")),
            "leverage": (_f(ms.get("totalNtlPos")) / _f(ms.get("accountValue"))
                         if _f(ms.get("accountValue")) else None),
            "time_ms": s.get("time"),
        }

    def positions(self) -> pd.DataFrame:
        s = self.state()
        rows: List[Dict[str, Any]] = []
        for ap in s.get("assetPositions", []):
            p = ap.get("position", {})
            lev = p.get("leverage", {}) or {}
            szi = _f(p.get("szi")) or 0.0
            rows.append({
                "coin": p.get("coin"),
                "size": szi,
                "side": "long" if szi > 0 else ("short" if szi < 0 else "flat"),
                "entry_px": _f(p.get("entryPx")),
                "position_value": _f(p.get("positionValue")),
                "unrealized_pnl": _f(p.get("unrealizedPnl")),
                "return_on_equity": _f(p.get("returnOnEquity")),
                "liquidation_px": _f(p.get("liquidationPx")),
                "margin_used": _f(p.get("marginUsed")),
                "max_leverage": p.get("maxLeverage"),
                "leverage_type": lev.get("type"),
                "leverage_value": _f(lev.get("value")),
                "funding_since_open": _f((p.get("cumFunding") or {}).get("sinceOpen")),
                "funding_all_time": _f((p.get("cumFunding") or {}).get("allTime")),
            })
        return pd.DataFrame(rows)

    def spot_balances(self) -> pd.DataFrame:
        s = self.info.spot_clearinghouse_state(self.address)
        return pd.DataFrame(s.get("balances", []))

    # ---- activity ----------------------------------------------------------
    def open_orders(self) -> pd.DataFrame:
        return pd.DataFrame(self.info.frontend_open_orders(self.address))

    def fills(self, days: int = 7) -> pd.DataFrame:
        rows = self.info.user_fills_by_time(self.address, now_ms() - days * 86_400_000)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        for c in ("px", "sz", "closedPnl", "fee", "startPosition"):
            if c in df:
                df[c] = df[c].astype(float)
        df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
        df["notional"] = df["px"] * df["sz"]
        return df.sort_values("time")

    def funding_paid(self, days: int = 7) -> pd.DataFrame:
        rows = self.info.user_funding(self.address, now_ms() - days * 86_400_000)
        if not rows:
            return pd.DataFrame()
        recs = []
        for r in rows:
            d = r.get("delta", {})
            recs.append({
                "time": pd.to_datetime(r["time"], unit="ms", utc=True),
                "coin": d.get("coin"),
                "usdc": _f(d.get("usdc")),
                "funding_rate": _f(d.get("fundingRate")),
                "szi": _f(d.get("szi")),
            })
        return pd.DataFrame(recs).sort_values("time")

    def pnl_summary(self, days: int = 7) -> Dict[str, Any]:
        f = self.fills(days)
        fund = self.funding_paid(days)
        return {
            "window_days": days,
            "n_fills": 0 if f.empty else len(f),
            "traded_notional": 0.0 if f.empty else float(f["notional"].sum()),
            "closed_pnl": 0.0 if f.empty else float(f["closedPnl"].sum()),
            "fees_paid": 0.0 if f.empty else float(f["fee"].sum()),
            "funding_net": 0.0 if fund.empty else float(fund["usdc"].sum()),
            "net_pnl": ((0.0 if f.empty else float(f["closedPnl"].sum() - f["fee"].sum()))
                        + (0.0 if fund.empty else float(fund["usdc"].sum()))),
        }

    def rate_limit(self) -> Dict[str, Any]:
        return self.info.user_rate_limit(self.address)

    def asset_state(self, coin: str) -> Dict[str, Any]:
        """Leverage, availableToTrade and max size for this account on one coin."""
        return self.info.active_asset_data(self.address, coin)
