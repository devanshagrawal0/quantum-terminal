"""Fear & Greed index — the market's mood, free and with real history.

One global number (0 = extreme fear, 100 = extreme greed) from alternative.me. It
cannot pick coins (it's market-wide), so it is a TIMING/exposure gate, not a
cross-sectional factor: the honest question is whether our score's edge changes with
the mood — e.g. do long picks die in extreme greed (crowded top), do shorts die in
extreme fear (oversold bounce). Cached to parquet so the backtest can join it
point-in-time and the live UI can show today's reading.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "carry_cache" / "fng_daily.parquet"
_live = {"t": 0.0, "v": None}


def refresh() -> int:
    """Pull full daily history, store {ts_ms, value, label} to parquet. Returns rows."""
    import datetime as dt
    import pandas as pd
    d = json.loads(urllib.request.urlopen(
        "https://api.alternative.me/fng/?limit=0&format=json", timeout=30).read())
    rows = []
    for r in d["data"]:
        ts = int(r["timestamp"])
        rows.append({"ts_ms": ts * 1000, "value": int(r["value"]),
                     "label": r.get("value_classification", "")})
    df = pd.DataFrame(rows).sort_values("ts_ms").reset_index(drop=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE)
    return len(df)


def series():
    """Daily F&G as a pandas Series indexed by epoch-ms (matches price parquet index)."""
    import pandas as pd
    if not CACHE.exists():
        refresh()
    df = pd.read_parquet(CACHE)
    return pd.Series(df["value"].values, index=df["ts_ms"].values)


def as_of(ts_ms: int) -> Optional[int]:
    """The F&G reading on/just before a given epoch-ms day."""
    s = series()
    prior = s[s.index <= ts_ms]
    return int(prior.iloc[-1]) if len(prior) else None


def live() -> Dict[str, Any]:
    """Today's reading (cached 1h) for the live UI."""
    if time.time() - _live["t"] < 3600 and _live["v"] is not None:
        return _live["v"]
    try:
        d = json.loads(urllib.request.urlopen(
            "https://api.alternative.me/fng/?limit=1&format=json", timeout=15).read())
        r = d["data"][0]
        _live["v"] = {"value": int(r["value"]), "label": r.get("value_classification", "")}
    except Exception as e:
        _live["v"] = {"value": None, "label": "", "error": str(e)}
    _live["t"] = time.time()
    return _live["v"]
