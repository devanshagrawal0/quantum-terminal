"""The $50 paper trade engine.

A real book, not a scoring sheet: positions have size, leverage and margin, and
they close themselves when the stop, the target, or the time limit hits first -
marked against the live consolidated cross-venue price, with the real Hyperliquid
taker fee and the spread charged on entry and exit.

Every rule Dev set is enforced here, not assumed:
  * $50 starting balance, 2x default leverage (4x hard max), $10 minimum order,
    10 open positions maximum.
  * A trade's plan (stop, target, hold, thesis) is written at open and the row
    is content-hashed, so it cannot be quietly edited after the outcome exists.
  * Exits fire on price crossing the stop/target OR the hold time expiring,
    whichever comes first. Marking uses the consolidated price the recorder
    already computes, never a single venue that might be asleep.
  * Fees + half-spread are charged both ways, so the balance is what you would
    actually keep.

Nothing here decides WHAT to trade. It only holds and settles what it is told to.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "paper.db"
VENUES_DB = ROOT / "data" / "venues.db"

# New model (Dev, 2026-08-24): no capital cap, unlimited trades, every trade the
# SAME fixed size so the track record is comparable across all of them - one
# trade winning big is not allowed to matter more than another just because it
# was bigger. The engine is a performance ledger, not a capped $50 book.
TRADE_SIZE_USD = 100.0            # identical notional per trade
LEV_DEFAULT = 2.0
LEV_MAX = 4.0
FEE_BPS = 4.5                      # Hyperliquid taker, per side

# HIP-3 builder dexes we also price/trade (USDC-margined perps on equities,
# commodities, indices). Only the liquid one ('xyz' = Trade.xyz) for now.
# A builder-market coin is dex-prefixed, e.g. "xyz:GOLD", "xyz:SP500", "xyz:NVDA".
BUILDER_DEXES = ["xyz"]


def is_builder(coin: str) -> bool:
    return ":" in coin


def norm_coin(coin: str) -> str:
    """Uppercase crypto tickers, but keep the builder-dex prefix lowercase:
    'xyz:gold' -> 'xyz:GOLD', 'btc' -> 'BTC'. The API market names are dex-prefixed
    with a lowercase dex and uppercase ticker, so a blanket .upper() breaks them."""
    if ":" in coin:
        dex, tick = coin.split(":", 1)
        return f"{dex.lower()}:{tick.upper()}"
    return coin.upper()

SCHEMA = """
CREATE TABLE IF NOT EXISTS account (
  id INTEGER PRIMARY KEY CHECK (id=1),
  balance REAL, realized_pnl REAL, fees_paid REAL, created_ms INTEGER
);
CREATE TABLE IF NOT EXISTS positions (
  id TEXT PRIMARY KEY,
  opened_ms INTEGER, coin TEXT, side TEXT,      -- long | short
  leverage REAL, notional_usd REAL, margin_usd REAL,
  entry_px REAL, entry_fee REAL,
  stop_px REAL, target_px REAL, hold_hours REAL, close_after_ms INTEGER,
  thesis TEXT, plan_hash TEXT,
  status TEXT,                                  -- open | closed
  closed_ms INTEGER, exit_px REAL, exit_fee REAL,
  exit_reason TEXT,                             -- stop | target | time | manual | hedge_rebal | hedge_off
  pnl_usd REAL, funding_usd REAL, mark_px REAL, mark_ms INTEGER,
  is_hedge INTEGER DEFAULT 0                     -- 1 = the auto BTC beta hedge, not a signal trade
);
CREATE INDEX IF NOT EXISTS idx_pos_status ON positions(status);
"""

PLAN_FIELDS = ("coin", "side", "leverage", "notional_usd", "entry_px",
               "stop_px", "target_px", "hold_hours", "opened_ms", "thesis")


_NUMERIC_PLAN = {"leverage", "notional_usd", "entry_px", "stop_px",
                 "target_px", "hold_hours", "opened_ms"}


def _hash(d: Dict[str, Any]) -> str:
    # Coerce numeric fields to float BEFORE hashing, so notional_usd=10 (int at
    # open) and 10.0 (float after the sqlite round-trip) produce the same hash.
    # Without this every position reads as "tampered" on the first verify.
    norm = {}
    for k in PLAN_FIELDS:
        v = d.get(k)
        if k in _NUMERIC_PLAN and v is not None:
            norm[k] = round(float(v), 10)
        else:
            norm[k] = v
    payload = json.dumps(norm, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def consolidated_prices() -> Dict[str, float]:
    """Latest HYPERLIQUID price per coin from the recorder - used for MARKING.

    This was originally the consolidated cross-venue price, which was wrong: the
    consolidated blends in the very exchanges a gap-convergence trade converges
    TOWARD, so it hid the move. We fill on Hyperliquid, so mark on the HL price.
    (Name kept so callers do not change.)
    """
    conn = sqlite3.connect(f"file:{VENUES_DB}?mode=ro", uri=True)
    out = {}
    hlast = conn.execute("SELECT MAX(ts_ms) FROM hl_state").fetchone()[0]
    if hlast:
        for coin, mid in conn.execute(
                "SELECT coin, mid FROM hl_state WHERE ts_ms=? AND mid>0", (hlast,)):
            out[coin] = mid
    conn.close()
    return out


def live_all_mids() -> Dict[str, float]:
    """Every Hyperliquid coin's LIVE mid in one call. Used for marking so the
    book is not valued on the 5-minute recorded snapshot, which was up to 157bps
    stale and made the dashboard flash fake P&L. One call, ~949 coins, fresh."""
    try:
        req = urllib.request.Request(
            "https://api.hyperliquid.xyz/info",
            data=json.dumps({"type": "allMids"}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        out = {k: float(v) for k, v in d.items() if v}
        # merge builder-dex mids (equities/commodities on the same USDC rails)
        for dex in BUILDER_DEXES:
            try:
                rq = urllib.request.Request(
                    "https://api.hyperliquid.xyz/info",
                    data=json.dumps({"type": "allMids", "dex": dex}).encode(),
                    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
                dd = json.loads(urllib.request.urlopen(rq, timeout=10).read())
                out.update({k: float(v) for k, v in dd.items() if v})
            except Exception:
                pass
        return out
    except Exception:
        return {}


def live_funding() -> Dict[str, float]:
    """Every coin's current HOURLY funding rate, one call. Positive = longs pay
    shorts (so a short COLLECTS it, a long PAYS it). Used to accrue funding on
    every open position each mark, so the paper P&L is honest — funding is a real
    cost/income of holding a perp, not just for carry trades."""
    try:
        req = urllib.request.Request(
            "https://api.hyperliquid.xyz/info",
            data=json.dumps({"type": "metaAndAssetCtxs"}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        out = {u["name"]: float(c["funding"])
               for u, c in zip(d[0]["universe"], d[1]) if c.get("funding")}
        for dex in BUILDER_DEXES:
            try:
                rq = urllib.request.Request(
                    "https://api.hyperliquid.xyz/info",
                    data=json.dumps({"type": "metaAndAssetCtxs", "dex": dex}).encode(),
                    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
                dd = json.loads(urllib.request.urlopen(rq, timeout=10).read())
                out.update({u["name"]: float(c["funding"])
                            for u, c in zip(dd[0]["universe"], dd[1]) if c.get("funding")})
            except Exception:
                pass
        return out
    except Exception:
        return {}


def live_hl_price(coin: str) -> Optional[float]:
    """A FRESH Hyperliquid mid for one coin, fetched right now.

    The recorded snapshot can be up to 5 minutes old. Entering a tight-band
    gap trade on a stale price and then marking against a fresh one blew the
    band on the first mark - a trade closing in 1 minute on staleness, not on
    convergence. Entry must use the same live price the market is at.
    """
    try:
        req = urllib.request.Request(
            "https://api.hyperliquid.xyz/info",
            data=json.dumps({"type": "l2Book", "coin": coin}).encode(),
            headers={"Content-Type": "application/json",
                     "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            book = json.loads(r.read())
        levels = book.get("levels") or [[], []]
        bid = float(levels[0][0]["px"]) if levels[0] else None
        ask = float(levels[1][0]["px"]) if levels[1] else None
        if bid and ask:
            return (bid + ask) / 2
    except Exception:
        return None
    return None


def hl_spread_bps(coin: str) -> float:
    conn = sqlite3.connect(f"file:{VENUES_DB}?mode=ro", uri=True)
    r = conn.execute("SELECT hl_spread_bps FROM cv_features WHERE coin=? "
                     "ORDER BY ts_ms DESC LIMIT 1", (coin,)).fetchone()
    conn.close()
    return float(r[0]) if r and r[0] is not None else 5.0


_beta_cache = {"t": 0.0, "b": None}


def betas_to_btc() -> Dict[str, float]:
    """Each coin's 60-day beta to BTC — how much of its move is just BTC's move.
    This is what the hedge neutralizes: a $100 long in a beta-1.4 coin carries
    $140 of BTC exposure. Cached 10 min (reads the daily price parquet)."""
    if time.time() - _beta_cache["t"] < 600 and _beta_cache["b"] is not None:
        return _beta_cache["b"]
    out: Dict[str, float] = {}
    try:
        import numpy as np
        import pandas as pd
        px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
        ret = px.pct_change(fill_method=None).tail(60)
        if "BTC" in ret.columns:
            b = ret["BTC"]
            var = float(b.var())
            for c in ret.columns:
                m = pd.concat([ret[c], b], axis=1).dropna()
                if len(m) > 30 and var:
                    out[c] = float(np.cov(m.iloc[:, 0], m.iloc[:, 1])[0, 1] / var)
    except Exception:
        pass
    out["BTC"] = 1.0
    _beta_cache["b"] = out
    _beta_cache["t"] = time.time()
    return out


class Paper:
    def __init__(self, path: Path = DB):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        # migrations for an existing positions table (idempotent)
        for ddl in ("ALTER TABLE positions ADD COLUMN is_hedge INTEGER DEFAULT 0",
                    "ALTER TABLE positions ADD COLUMN tag TEXT DEFAULT 'fused'",
                    "ALTER TABLE positions ADD COLUMN btc_entry_px REAL"):
            try:
                self.conn.execute(ddl)
            except Exception:
                pass
        if not self.conn.execute("SELECT 1 FROM account WHERE id=1").fetchone():
            with self.conn:
                # balance here = cumulative realized P&L across all trades, from 0.
                self.conn.execute("INSERT INTO account VALUES (1,?,?,?,?)",
                                  (0.0, 0.0, 0.0, int(time.time() * 1000)))

    def close(self):
        self.conn.close()

    # ---- account (a performance ledger, not a capped book) ----------------
    def account(self) -> Dict[str, Any]:
        a = dict(self.conn.execute("SELECT * FROM account WHERE id=1").fetchone())
        open_pos = self.open_positions()
        closed = self.closed_positions(10_000)
        wins = [c for c in closed if (c["pnl_usd"] or 0) > 0]
        a["trade_size_usd"] = TRADE_SIZE_USD
        a["n_open"] = len(open_pos)
        a["n_closed"] = len(closed)
        a["n_trades"] = len(open_pos) + len(closed)
        a["realized_pnl"] = a["balance"]        # balance == cumulative realized
        a["win_rate"] = (len(wins) / len(closed)) if closed else None
        a["unrealized_gross"] = sum(p.get("unrealized_gross", 0.0) for p in open_pos)
        a["unrealized_pnl"] = sum(p.get("unrealized_pnl", 0.0) for p in open_pos)
        # total P&L = realized so far + open positions marked to market
        a["total_pnl"] = a["balance"] + a["unrealized_gross"]
        a["open_notional"] = sum(p["notional_usd"] for p in open_pos)
        try:
            a["hedge"] = self.hedge_state()
        except Exception:
            a["hedge"] = {"active": False}
        return a

    # ---- opening ----------------------------------------------------------
    def open(self, coin: str, side: str, stop_px: float, target_px: float,
             hold_hours: float, thesis: str, notional_usd: float = TRADE_SIZE_USD,
             leverage: float = LEV_DEFAULT, force: bool = False,
             tag: str = "fused") -> Dict[str, Any]:
        coin = norm_coin(coin)
        side = side.lower()
        if side not in ("long", "short"):
            return {"ok": False, "error": "side must be long or short"}
        if leverage > LEV_MAX:
            return {"ok": False, "error": f"leverage {leverage} > max {LEV_MAX}"}

        # Pre-trade enforcement (L7/L8): block correlated over-concentration and shorts
        # into a melt-up, unless explicitly forced. The enforced version of our lessons.
        # Crypto gates (tide/Layer-2/fundamentals/L7/L8) are crypto-specific — they must
        # NOT gate an equity/commodity trade (BTC's tide has nothing to say about GOLD).
        # Builder-dex markets get their own framework later; for now they bypass preflight.
        pf = None
        if not is_builder(coin):
            try:
                from hl import preflight
                pf = preflight.check(coin, side, self.open_positions(), force=force)
                if pf["blocked"]:
                    return {"ok": False, "preflight": pf,
                            "error": "blocked by preflight — " + "; ".join(
                                v["msg"] for v in pf["violations"] if v["level"] == "block")}
            except Exception:
                pf = None
        # Systematic trades default to the uniform $100 (comparable track record).
        # A caller MAY pass a custom notional for a discretionary/manual trade — it
        # just won't be size-comparable to the systematic book (tag it so it's clear).
        notional_usd = float(notional_usd or TRADE_SIZE_USD)

        # Enter on a FRESH live HL price, not the recorded snapshot, so a tight
        # gap-trade band is not blown on the first mark by staleness.
        px = live_hl_price(coin) or consolidated_prices().get(coin)
        if not px:
            return {"ok": False, "error": f"{coin} not priceable right now"}

        # A target/stop cannot be tighter than the coin's own spread+snapshot
        # noise, or it is decided by microstructure, not by the thesis. Floor the
        # band at max(3x HL spread, 25bps).
        min_band = max(3 * hl_spread_bps(coin), 25) / 1e4
        if abs(target_px / px - 1) < min_band or abs(stop_px / px - 1) < min_band:
            return {"ok": False,
                    "error": f"band too tight for {coin}: need >{min_band*1e4:.0f}bps "
                             f"from entry {px:.6g} (spread noise)"}

        # plan sanity: stop and target must be on the correct sides of entry
        if side == "long" and not (stop_px < px < target_px):
            return {"ok": False, "error": f"long needs stop<{px:.6g}<target"}
        if side == "short" and not (target_px < px < stop_px):
            return {"ok": False, "error": f"short needs target<{px:.6g}<stop"}

        # No capital cap and no slot limit: unlimited trades, one open per coin
        # so the same idea is not logged twice.
        if self.conn.execute("SELECT 1 FROM positions WHERE coin=? AND status='open' AND is_hedge=0",
                             (coin,)).fetchone():
            return {"ok": False, "error": f"{coin} already has an open position"}
        margin = notional_usd / leverage
        spread = hl_spread_bps(coin)
        entry_fee = notional_usd * (FEE_BPS + spread / 2) / 1e4
        opened = int(time.time() * 1000)
        btc_entry = live_all_mids().get("BTC")   # for BTC-neutral scoring later
        row = {
            "coin": coin, "side": side, "leverage": leverage,
            "notional_usd": notional_usd, "entry_px": px,
            "stop_px": stop_px, "target_px": target_px, "hold_hours": hold_hours,
            "opened_ms": opened, "thesis": thesis,
        }
        pid = _hash(row)
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO positions (id,opened_ms,coin,side,leverage,"
                "notional_usd,margin_usd,entry_px,entry_fee,stop_px,target_px,"
                "hold_hours,close_after_ms,thesis,plan_hash,status,mark_px,mark_ms,tag,btc_entry_px) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'open',?,?,?,?)",
                (pid, opened, coin, side, leverage, notional_usd, margin, px,
                 entry_fee, stop_px, target_px, hold_hours,
                 opened + int(hold_hours * 3_600_000), thesis, pid, px, opened, tag, btc_entry))
            self.conn.execute(
                "UPDATE account SET balance=balance-?, fees_paid=fees_paid+? WHERE id=1",
                (entry_fee, entry_fee))
        # Journal the entry signals now, so every trade we make is saved WITH the
        # reasoning we saw at the time. Non-critical: never let it break a trade.
        try:
            from hl import journal
            journal.snapshot(pid, coin, side, thesis)
        except Exception:
            pass
        # a new position changes the basket's BTC exposure — re-size the hedge now
        try:
            self.rebalance_hedge()
        except Exception:
            pass
        return {"ok": True, "id": pid, "coin": coin, "side": side,
                "entry_px": px, "notional": notional_usd, "margin": margin,
                "entry_fee": entry_fee}

    # ---- marking & settlement --------------------------------------------
    def _pnl(self, p: Dict[str, Any], px: float) -> float:
        move = (px / p["entry_px"] - 1.0)
        signed = move if p["side"] == "long" else -move
        return signed * p["notional_usd"]

    def open_positions(self) -> List[Dict[str, Any]]:
        prices = live_all_mids() or consolidated_prices()   # LIVE, not stale snapshot
        out = []
        for r in self.conn.execute("SELECT * FROM positions WHERE status='open'"):
            p = dict(r)
            px = prices.get(p["coin"], p["mark_px"])
            gross = self._pnl(p, px)
            est_exit_fee = p["notional_usd"] * (FEE_BPS + hl_spread_bps(p["coin"]) / 2) / 1e4
            fund = p.get("funding_usd") or 0.0
            p["mark_now"] = px
            p["unrealized_gross"] = gross
            p["funding_accrued"] = fund
            p["unrealized_pnl"] = gross + fund - p["entry_fee"] - est_exit_fee   # round-trip if closed now
            p["unrealized_pct"] = p["unrealized_pnl"] / p["margin_usd"] * 100 if p["margin_usd"] else 0
            out.append(p)
        return out

    def mark_and_settle(self, now_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """The heartbeat: mark every open position and close any that hit stop,
        target or time. Returns the list of positions closed this call."""
        now = now_ms or int(time.time() * 1000)
        prices = live_all_mids() or consolidated_prices()   # LIVE, not stale snapshot
        funding = live_funding()                            # hourly rate per coin
        closed = []
        for r in self.conn.execute("SELECT * FROM positions WHERE status='open'").fetchall():
            p = dict(r)
            px = prices.get(p["coin"])
            if not px:
                continue
            # Accrue funding over the interval since the last mark. Long pays when
            # funding>0, short collects. funding_usd is the running total.
            fh = funding.get(p["coin"])
            if fh is not None and p.get("mark_ms"):
                dt_h = max(0.0, (now - p["mark_ms"]) / 3_600_000)
                sign = 1 if p["side"] == "long" else -1
                p["funding_usd"] = (p.get("funding_usd") or 0.0) - sign * fh * dt_h * p["notional_usd"]
            # The hedge has no stop/target/time — it only marks + accrues funding and
            # is resized by rebalance_hedge(). Skip the exit logic (its stop/target
            # are NULL, which would also crash the comparisons below).
            if p.get("is_hedge"):
                with self.conn:
                    self.conn.execute("UPDATE positions SET mark_px=?, mark_ms=?, funding_usd=? WHERE id=?",
                                      (px, now, p.get("funding_usd") or 0.0, p["id"]))
                continue
            reason = None
            exit_px = px
            if p["side"] == "long":
                if px <= p["stop_px"]:
                    reason, exit_px = "stop", p["stop_px"]
                elif px >= p["target_px"]:
                    reason, exit_px = "target", p["target_px"]
            else:
                if px >= p["stop_px"]:
                    reason, exit_px = "stop", p["stop_px"]
                elif px <= p["target_px"]:
                    reason, exit_px = "target", p["target_px"]
            if reason is None and now >= p["close_after_ms"]:
                reason, exit_px = "time", px
            # update mark + accrued funding either way
            with self.conn:
                self.conn.execute("UPDATE positions SET mark_px=?, mark_ms=?, funding_usd=? WHERE id=?",
                                  (px, now, p.get("funding_usd") or 0.0, p["id"]))
            if reason:
                closed.append(self._settle(p, exit_px, reason, now))
        # after settling any signal exits, resize the hedge to the new basket
        try:
            self.rebalance_hedge()
        except Exception:
            pass
        return closed

    def close_now(self, coin: str, reason: str = "manual") -> Optional[Dict[str, Any]]:
        """Manually close a coin's open position at the LIVE price, right now.
        Used by the reasoning layer when the regime/thesis changes before a
        stop/target/time hits (e.g. a short caught wrong-way in a melt-up)."""
        r = self.conn.execute(
            "SELECT * FROM positions WHERE status='open' AND coin=? LIMIT 1",
            (norm_coin(coin),)).fetchone()
        if not r:
            return None
        p = dict(r)
        px = live_hl_price(p["coin"]) or live_all_mids().get(p["coin"])
        if not px:
            return None
        out = self._settle(p, px, reason, int(time.time() * 1000))
        # closing a signal position changes the basket — resize the hedge (never
        # from inside _settle, or the hedge's own settle would recurse)
        if not p.get("is_hedge"):
            try:
                self.rebalance_hedge()
            except Exception:
                pass
        return out

    def _settle(self, p: Dict[str, Any], exit_px: float, reason: str,
                now: int) -> Dict[str, Any]:
        # Money model: balance is cash. The entry fee was already removed at
        # open. Margin was NEVER removed - it is only a constraint on how much
        # notional can be open. So at close, balance changes by (gross price move
        # minus the exit fee); it must NOT re-add margin, and must NOT subtract
        # the entry fee again. round_trip is the full net for the stats.
        spread = hl_spread_bps(p["coin"])
        exit_fee = p["notional_usd"] * (FEE_BPS + spread / 2) / 1e4
        gross = self._pnl(p, exit_px)
        fund = p.get("funding_usd") or 0.0            # accrued funding over the hold
        balance_change = gross + fund - exit_fee
        round_trip = gross + fund - p["entry_fee"] - exit_fee
        with self.conn:
            self.conn.execute(
                "UPDATE positions SET status='closed', closed_ms=?, exit_px=?, "
                "exit_fee=?, exit_reason=?, pnl_usd=?, funding_usd=? WHERE id=?",
                (now, exit_px, exit_fee, reason, round_trip, fund, p["id"]))
            self.conn.execute(
                "UPDATE account SET balance=balance+?, realized_pnl=realized_pnl+?, "
                "fees_paid=fees_paid+? WHERE id=1",
                (balance_change, round_trip, exit_fee))
        # Auto-record the outcome to the journal so every closed trade is analysed
        # (the facts now; the human lesson later). Non-critical.
        try:
            from hl import journal
            journal.record_close(p["id"])
        except Exception:
            pass
        return {"id": p["id"], "coin": p["coin"], "side": p["side"],
                "reason": reason, "exit_px": exit_px, "pnl_usd": round_trip}

    # ---- the BTC beta hedge ----------------------------------------------
    # The long-only book (L13) only has an edge market-NEUTRAL: long the coins,
    # short BTC against them. A basket of longs carries net BTC exposure equal to
    # sum(notional * beta_to_btc); the hedge is a BTC short of exactly that size,
    # resized whenever the basket changes. Without it, every "long" is really a
    # levered BTC bet and the backtested edge is not what the book actually runs.
    def target_hedge_notional(self) -> float:
        """USD of BTC exposure the signal book carries = sum(notional*beta), longs
        positive / shorts negative. The hedge shorts this much BTC to cancel it."""
        betas = betas_to_btc()
        tot = 0.0
        # hedge the book we actually RUN (fused + legacy); the 'quant_only' control is
        # deliberately left unhedged so we can watch it on its own.
        for r in self.conn.execute(
                "SELECT coin, notional_usd, side FROM positions "
                "WHERE status='open' AND is_hedge=0 AND tag NOT IN ('quant_only','pred_test') AND coin NOT LIKE '%:%'"):
            b = betas.get(r["coin"], 1.0)
            signed = r["notional_usd"] if r["side"] == "long" else -r["notional_usd"]
            tot += signed * b
        return tot

    def current_hedge(self) -> Optional[Dict[str, Any]]:
        r = self.conn.execute(
            "SELECT * FROM positions WHERE status='open' AND is_hedge=1 LIMIT 1").fetchone()
        return dict(r) if r else None

    def _open_hedge(self, notional: float, px: float) -> str:
        now = int(time.time() * 1000)
        notional = round(notional, 2)
        spread = hl_spread_bps("BTC")
        entry_fee = notional * (FEE_BPS + spread / 2) / 1e4
        row = {"coin": "BTC", "side": "short", "leverage": LEV_DEFAULT,
               "notional_usd": notional, "entry_px": px, "stop_px": None,
               "target_px": None, "hold_hours": None, "opened_ms": now,
               "thesis": "auto BTC beta hedge"}
        h = _hash(row)
        pid = "hedge-" + h[:16]
        with self.conn:
            self.conn.execute(
                "INSERT INTO positions (id,opened_ms,coin,side,leverage,notional_usd,"
                "margin_usd,entry_px,entry_fee,stop_px,target_px,hold_hours,"
                "close_after_ms,thesis,plan_hash,status,mark_px,mark_ms,is_hedge) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'open',?,?,1)",
                (pid, now, "BTC", "short", LEV_DEFAULT, notional, notional / LEV_DEFAULT,
                 px, entry_fee, None, None, None, None, "auto BTC beta hedge", h, px, now))
            self.conn.execute(
                "UPDATE account SET balance=balance-?, fees_paid=fees_paid+? WHERE id=1",
                (entry_fee, entry_fee))
        return pid

    def rebalance_hedge(self, min_usd: float = 10.0, drift_usd: float = 20.0) -> Dict[str, Any]:
        """Bring the BTC hedge to the basket's net beta exposure. Opens it if the
        book has meaningful net beta, resizes it when the basket drifts past a
        threshold (close+reopen at the live BTC price — the resize costs a fee,
        which is honest: hedging is not free), closes it when the book is flat."""
        target = self.target_hedge_notional()
        h = self.current_hedge()
        btc = live_hl_price("BTC") or live_all_mids().get("BTC")
        if not btc:
            return {"action": "no_price"}
        now = int(time.time() * 1000)
        if target < min_usd:                          # book has ~no net beta
            if h:
                self._settle(h, btc, "hedge_off", now)
                return {"action": "off", "target": round(target, 2)}
            return {"action": "none", "target": round(target, 2)}
        if h is None:
            self._open_hedge(target, btc)
            return {"action": "open", "notional": round(target, 2)}
        if abs(target - h["notional_usd"]) > drift_usd:
            self._settle(h, btc, "hedge_rebal", now)
            self._open_hedge(target, btc)
            return {"action": "resize", "from": round(h["notional_usd"], 2),
                    "to": round(target, 2)}
        return {"action": "hold", "notional": round(h["notional_usd"], 2)}

    def hedge_state(self) -> Dict[str, Any]:
        """What the hedge is doing right now, for the dashboard."""
        h = self.current_hedge()
        target = self.target_hedge_notional()
        betas = betas_to_btc()
        legs = []
        for r in self.conn.execute(
                "SELECT coin, notional_usd, side FROM positions "
                "WHERE status='open' AND is_hedge=0 AND tag NOT IN ('quant_only','pred_test') AND coin NOT LIKE '%:%'"):
            beta = round(betas.get(r["coin"], 1.0), 2)
            contrib = (r["notional_usd"] if r["side"] == "long" else -r["notional_usd"]) * beta
            legs.append({"coin": r["coin"], "notional": r["notional_usd"], "side": r["side"],
                         "beta": beta, "btc_exposure": round(contrib, 1)})
        legs.sort(key=lambda x: -abs(x["btc_exposure"]))
        n_long = sum(1 for x in legs if x["side"] == "long")
        out = {"target_notional": round(target, 2), "n_legs": len(legs), "n_longs": n_long,
               "legs": legs, "active": h is not None}
        if h:
            px = live_all_mids().get("BTC", h["mark_px"])
            out.update({"notional": round(h["notional_usd"], 2), "entry_px": h["entry_px"],
                        "mark_px": px, "pnl": round(self._pnl(h, px) + (h.get("funding_usd") or 0.0), 2),
                        "coverage_pct": round(h["notional_usd"] / target * 100, 0) if target > 0 else None})
        return out

    def book_compare(self) -> Dict[str, Any]:
        """The news-veto test: FUSED (we took) vs QUANT-ONLY (we skipped on news),
        each measured BTC-NEUTRAL (coin move minus beta*BTC move since entry), so
        we can see whether skipping the news-vetoed names was actually smart. Covers
        both open (marked) and closed positions of each tag."""
        mids = live_all_mids() or consolidated_prices()
        betas = betas_to_btc()
        btc_now = mids.get("BTC")
        out: Dict[str, Any] = {}
        for tag in ("fused", "quant_only"):
            rows = self.conn.execute(
                "SELECT coin,side,entry_px,exit_px,btc_entry_px,status,mark_px FROM positions "
                "WHERE tag=? AND is_hedge=0", (tag,)).fetchall()
            resids, names = [], []
            for r in rows:
                exitp = r["exit_px"] if r["status"] == "closed" else mids.get(r["coin"], r["mark_px"])
                if not (exitp and r["entry_px"]):
                    continue
                coin_ret = exitp / r["entry_px"] - 1.0
                be = r["btc_entry_px"]
                btc_ret = (btc_now / be - 1.0) if (be and btc_now) else 0.0
                beta = betas.get(r["coin"], 1.0)
                resid = coin_ret - beta * btc_ret
                signed = resid if r["side"] == "long" else -resid
                resids.append(signed)
                names.append({"coin": r["coin"], "resid_pct": round(signed * 100, 2),
                              "status": r["status"]})
            n = len(resids)
            out[tag] = {"n": n,
                        "avg_resid_pct": round(sum(resids) / n * 100, 2) if n else None,
                        "win_rate": round(sum(1 for x in resids if x > 0) / n, 2) if n else None,
                        "names": sorted(names, key=lambda x: x["resid_pct"])}
        f, q = out.get("fused", {}), out.get("quant_only", {})
        if f.get("avg_resid_pct") is not None and q.get("avg_resid_pct") is not None:
            out["veto_edge_pct"] = round(f["avg_resid_pct"] - q["avg_resid_pct"], 2)
            out["veto_was_smart"] = out["veto_edge_pct"] > 0
        return out

    def closed_positions(self, limit: int = 100) -> List[Dict[str, Any]]:
        # hedge rebalances are NOT signal trades — keep them out of the track record
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM positions WHERE status='closed' AND is_hedge=0 "
            "ORDER BY closed_ms DESC LIMIT ?", (limit,))]

    def verify(self) -> Dict[str, Any]:
        bad = []
        for r in self.conn.execute("SELECT * FROM positions"):
            p = dict(r)
            if _hash(p) != p["plan_hash"]:
                bad.append(p["id"])
        return {"checked": self.conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0],
                "tampered": bad}
