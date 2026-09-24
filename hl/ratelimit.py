"""Sliding-window weight budget so we never trip Hyperliquid's 1200/min IP cap."""
import threading
import time
from collections import deque

from .constants import (DEFAULT_WEIGHT, EXTRA_WEIGHT_PER_20,
                        EXTRA_WEIGHT_PER_60, IP_WEIGHT_PER_MIN, WEIGHT_2,
                        WEIGHT_60)


def base_weight(req_type: str) -> int:
    if req_type in WEIGHT_2:
        return 2
    if req_type in WEIGHT_60:
        return 60
    return DEFAULT_WEIGHT


def extra_weight(req_type: str, n_items: int) -> int:
    """Weight charged after the fact for paged responses."""
    if req_type in EXTRA_WEIGHT_PER_20:
        return n_items // 20
    if req_type in EXTRA_WEIGHT_PER_60:
        return n_items // 60
    return 0


class WeightLimiter:
    """Blocks the caller until the last 60s of spent weight leaves room."""

    def __init__(self, budget_per_min: int = IP_WEIGHT_PER_MIN, safety: float = 0.9):
        self.budget = int(budget_per_min * safety)
        self._events: deque = deque()      # (timestamp, weight)
        self._lock = threading.Lock()

    def _trim(self, now: float) -> None:
        while self._events and now - self._events[0][0] > 60.0:
            self._events.popleft()

    def spent(self) -> int:
        with self._lock:
            self._trim(time.time())
            return sum(w for _, w in self._events)

    def acquire(self, weight: int) -> None:
        while True:
            with self._lock:
                now = time.time()
                self._trim(now)
                used = sum(w for _, w in self._events)
                if used + weight <= self.budget:
                    self._events.append((now, weight))
                    return
                wait = 60.0 - (now - self._events[0][0]) + 0.01
            time.sleep(max(wait, 0.01))

    def charge(self, weight: int) -> None:
        """Record weight discovered only after the response arrived."""
        if weight <= 0:
            return
        with self._lock:
            self._events.append((time.time(), weight))
