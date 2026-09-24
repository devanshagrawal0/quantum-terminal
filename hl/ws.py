"""Threaded websocket client for live Hyperliquid data.

Handles the three things that break naive clients:
  1. keepalive - the server drops a connection that goes ~60s without traffic,
     so we send {"method": "ping"} every 30s,
  2. reconnect - on any drop we reopen and replay every subscription,
  3. dispatch  - messages carry a channel plus a coin/user, so callbacks are
     keyed on the same tuple the subscription was made with.

Also supports info requests over the socket (method "post"), which is cheaper
than HTTP when a connection is already open.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import websocket  # websocket-client

from .constants import MAINNET_WS, TESTNET_WS, WS_PING_SECONDS
from .errors import WsError

Callback = Callable[[Any], None]


def sub_key(sub: Dict[str, Any]) -> str:
    """Stable identity for a subscription, matched against inbound messages."""
    t = sub["type"]
    parts: List[str] = [t]
    if "coin" in sub:
        parts.append(str(sub["coin"]))
    if "interval" in sub:
        parts.append(str(sub["interval"]))
    if "user" in sub:
        parts.append(str(sub["user"]).lower())
    return ":".join(parts)


def _message_keys(channel: str, data: Any) -> List[str]:
    """Candidate keys for an inbound message, most specific first."""
    keys: List[str] = []
    if isinstance(data, dict):
        coin = data.get("coin") or data.get("s")
        user = data.get("user")
        if coin and data.get("i"):
            keys.append(f"{channel}:{coin}:{data['i']}")
        if coin:
            keys.append(f"{channel}:{coin}")
        if user:
            keys.append(f"{channel}:{str(user).lower()}")
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        coin = data[0].get("coin") or data[0].get("s")
        if coin and data[0].get("i"):
            keys.append(f"{channel}:{coin}:{data[0]['i']}")
        if coin:
            keys.append(f"{channel}:{coin}")
    keys.append(channel)
    return keys


class HLWebsocket:
    def __init__(self, testnet: bool = False,
                 on_error: Optional[Callable[[Exception], None]] = None,
                 reconnect_seconds: float = 2.0):
        self.url = TESTNET_WS if testnet else MAINNET_WS
        self.on_error = on_error
        self.reconnect_seconds = reconnect_seconds

        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._ping_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._open = threading.Event()
        self._stopping = False

        self._subs: Dict[str, Dict[str, Any]] = {}      # key -> subscription
        self._callbacks: Dict[str, List[Callback]] = {}
        self._post_id = 0
        self._posts: Dict[int, Dict[str, Any]] = {}     # id -> {event, result}

        self.messages_received = 0
        self.last_message_ms = 0
        self.reconnects = 0

    # ---- lifecycle ---------------------------------------------------------
    def start(self, timeout: float = 10.0) -> "HLWebsocket":
        self._stopping = False
        self._connect()
        if not self._open.wait(timeout):
            raise WsError(f"websocket did not open within {timeout}s")
        if self._ping_thread is None:
            self._ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
            self._ping_thread.start()
        return self

    def _connect(self) -> None:
        self._open.clear()
        self._ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_ws_error,
            on_close=self._on_close,
        )
        self._thread = threading.Thread(
            target=self._ws.run_forever,
            kwargs={"ping_interval": 0},   # we do our own application ping
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopping = True
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
        self._open.clear()

    @property
    def connected(self) -> bool:
        return self._open.is_set()

    # ---- socket callbacks --------------------------------------------------
    def _on_open(self, _ws) -> None:
        self._open.set()
        with self._lock:
            subs = list(self._subs.values())
        for sub in subs:                                   # replay after reconnect
            self._send({"method": "subscribe", "subscription": sub})

    def _on_close(self, _ws, *_args) -> None:
        self._open.clear()
        if self._stopping:
            return
        self.reconnects += 1
        time.sleep(self.reconnect_seconds)
        self._connect()

    def _on_ws_error(self, _ws, err) -> None:
        if self.on_error:
            self.on_error(err if isinstance(err, Exception) else WsError(str(err)))

    def _on_message(self, _ws, raw: str) -> None:
        self.messages_received += 1
        self.last_message_ms = int(time.time() * 1000)
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        channel = msg.get("channel")
        data = msg.get("data")
        if channel in (None, "pong", "subscriptionResponse"):
            return
        if channel == "post":
            self._resolve_post(data)
            return
        if channel == "error":
            if self.on_error:
                self.on_error(WsError(str(data)))
            return

        with self._lock:
            targets: List[Callback] = []
            seen = set()
            for key in _message_keys(channel, data):
                for cb in self._callbacks.get(key, []):
                    if id(cb) not in seen:
                        seen.add(id(cb))
                        targets.append(cb)
        for cb in targets:
            try:
                cb(data)
            except Exception as exc:                        # never kill the reader
                if self.on_error:
                    self.on_error(exc)

    # ---- sending -----------------------------------------------------------
    def _send(self, obj: Dict[str, Any]) -> None:
        if self._ws is None:
            raise WsError("websocket not started")
        self._ws.send(json.dumps(obj))

    def _ping_loop(self) -> None:
        while not self._stopping:
            time.sleep(WS_PING_SECONDS)
            if self._open.is_set():
                try:
                    self._send({"method": "ping"})
                except Exception:
                    pass

    # ---- subscriptions -----------------------------------------------------
    def subscribe(self, subscription: Dict[str, Any], callback: Callback) -> str:
        key = sub_key(subscription)
        with self._lock:
            first = key not in self._subs
            self._subs[key] = subscription
            self._callbacks.setdefault(key, []).append(callback)
        if first and self._open.is_set():
            self._send({"method": "subscribe", "subscription": subscription})
        return key

    def unsubscribe(self, key_or_sub: Any) -> None:
        key = key_or_sub if isinstance(key_or_sub, str) else sub_key(key_or_sub)
        with self._lock:
            sub = self._subs.pop(key, None)
            self._callbacks.pop(key, None)
        if sub and self._open.is_set():
            self._send({"method": "unsubscribe", "subscription": sub})

    # convenience wrappers -------------------------------------------------
    def on_l2_book(self, coin: str, cb: Callback, n_sig_figs: Optional[int] = None) -> str:
        sub: Dict[str, Any] = {"type": "l2Book", "coin": coin}
        if n_sig_figs is not None:
            sub["nSigFigs"] = n_sig_figs
        return self.subscribe(sub, cb)

    def on_bbo(self, coin: str, cb: Callback) -> str:
        return self.subscribe({"type": "bbo", "coin": coin}, cb)

    def on_trades(self, coin: str, cb: Callback) -> str:
        return self.subscribe({"type": "trades", "coin": coin}, cb)

    def on_candle(self, coin: str, interval: str, cb: Callback) -> str:
        return self.subscribe({"type": "candle", "coin": coin, "interval": interval}, cb)

    def on_all_mids(self, cb: Callback, dex: str = "") -> str:
        return self.subscribe({"type": "allMids", "dex": dex}, cb)

    def on_active_asset_ctx(self, coin: str, cb: Callback) -> str:
        return self.subscribe({"type": "activeAssetCtx", "coin": coin}, cb)

    def on_user_fills(self, user: str, cb: Callback) -> str:
        return self.subscribe({"type": "userFills", "user": user}, cb)

    def on_user_events(self, user: str, cb: Callback) -> str:
        return self.subscribe({"type": "userEvents", "user": user}, cb)

    def on_order_updates(self, user: str, cb: Callback) -> str:
        return self.subscribe({"type": "orderUpdates", "user": user}, cb)

    def on_user_fundings(self, user: str, cb: Callback) -> str:
        return self.subscribe({"type": "userFundings", "user": user}, cb)

    # ---- info request over the socket -------------------------------------
    def post_info(self, payload: Dict[str, Any], timeout: float = 10.0) -> Any:
        with self._lock:
            self._post_id += 1
            pid = self._post_id
            slot = {"event": threading.Event(), "result": None}
            self._posts[pid] = slot
        self._send({"method": "post", "id": pid,
                    "request": {"type": "info", "payload": payload}})
        if not slot["event"].wait(timeout):
            with self._lock:
                self._posts.pop(pid, None)
            raise WsError(f"ws post {pid} timed out after {timeout}s")
        res = slot["result"]
        if isinstance(res, dict) and res.get("type") == "error":
            raise WsError(str(res.get("payload")))
        if isinstance(res, dict):
            payload_out = res.get("payload")
            if isinstance(payload_out, dict) and "data" in payload_out:
                return payload_out["data"]
            return payload_out
        return res

    def _resolve_post(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        pid = data.get("id")
        with self._lock:
            slot = self._posts.pop(pid, None)
        if slot:
            slot["result"] = data.get("response")
            slot["event"].set()
