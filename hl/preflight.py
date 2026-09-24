"""Pre-trade enforcement — the checks that STOP us repeating the logged mistakes.

The dossier proved two failures cost us real money:
  * L8 concentration — 9 correlated longs were one bet; a pullback hit them together.
  * L7 fighting the regime — every short into the melt-up (0/4) got run over.

Phases 1-4 made those visible. This makes them ENFORCED at `open()`: a proposed trade
is checked against the live book + regime, and a hard violation is BLOCKED unless the
caller passes force=True (a deliberate override, logged).

Crucially the concentration check uses MEASURED correlation to the actual book (daily
returns), not a hardcoded sector keyword map — the correlation is the real thing we care
about, and it needs no brittle "if name contains X" classification.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
_corr_cache: Dict[str, Any] = {"t": 0.0, "m": None}

CORR_THRESHOLD = 0.7      # |corr| above this = "moves together"
MAX_CLUSTER = 3           # block the 4th position that correlates with >=3 holdings
MAX_SAME_SIDE = 7         # block the 8th position on one side (all-one-side = one bet)


def _corr_matrix():
    """90-day daily-return correlation matrix, cached 10 min."""
    import time
    if time.time() - _corr_cache["t"] < 600 and _corr_cache["m"] is not None:
        return _corr_cache["m"]
    try:
        import pandas as pd
        px = pd.read_parquet(ROOT / "data" / "carry_cache" / "daily_365.parquet")
        ret = px.pct_change(fill_method=None).tail(90)
        m = ret.corr()
        _corr_cache["m"] = m
        _corr_cache["t"] = time.time()
        return m
    except Exception:
        return None


def _corr(a: str, b: str) -> Optional[float]:
    m = _corr_matrix()
    try:
        if m is not None and a in m.columns and b in m.columns:
            v = m.loc[a, b]
            return None if v != v else float(v)   # NaN guard
    except Exception:
        pass
    return None


def check(coin: str, side: str, book: List[Dict[str, Any]],
          force: bool = False) -> Dict[str, Any]:
    """Return {ok, blocked, violations:[{level,msg}], correlated_with, regime}."""
    coin = coin.upper(); side = side.lower()
    book_coins = [p["coin"] for p in book if p["coin"] != coin]
    book_sides = [p["side"] for p in book]
    violations: List[Dict[str, str]] = []

    # 1) correlation / concentration cap (L8) — MEASURED, not a sector keyword map
    corrs = [(c, _corr(coin, c)) for c in book_coins]
    high = [(c, r) for c, r in corrs if r is not None and abs(r) >= CORR_THRESHOLD]
    if len(high) >= MAX_CLUSTER:
        violations.append({"level": "block",
                           "msg": f"correlated (|r|≥{CORR_THRESHOLD}) with {len(high)} holdings "
                                  f"({', '.join(f'{c} {r:+.2f}' for c, r in high)}) — a concentrated "
                                  f"cluster; L8 says this becomes one bet."})

    # 2) direction cap (L8) — all-one-side book is a single leveraged bet
    same = sum(1 for s in book_sides if s == side)
    if same >= MAX_SAME_SIDE:
        violations.append({"level": "block",
                           "msg": f"{same} positions already {side.upper()}; L8 caps one-side exposure "
                                  f"(all-one-side = one bet regardless of ticker count)."})
    elif same >= MAX_SAME_SIDE - 2:
        violations.append({"level": "warn",
                           "msg": f"{same} positions already {side.upper()} — book getting one-directional."})

    # 3) regime gate (L7) — do not short a melt-up / do not fight the tape
    reg = None
    try:
        from hl import regime
        reg = regime.read()
        b7 = reg.get("breadth_7d")
        bullish = reg.get("regime") in ("bitcoin-season", "early-rotation", "altseason")
        if side == "short" and bullish and b7 is not None and b7 >= 0.6:
            violations.append({"level": "block",
                               "msg": f"SHORT into {reg['regime']} ({b7*100:.0f}% green 7d) — "
                                      f"shorts into a melt-up are 0/4, −$11.86 (L7)."})
        if side == "long" and reg.get("regime") == "risk-off":
            violations.append({"level": "warn",
                               "msg": "LONG in a risk-off regime — alts are not a haven; size down."})
    except Exception:
        pass

    # 4) macro TIDE gate (Layer 1, VALIDATED) — step aside from new LONGS in RISK-OFF.
    # Validated point-in-time over 9yr: stepping aside in risk-off cut max drawdown
    # −77%→−58% and lifted Sharpe 0.42→0.60. So a new long into a RISK-OFF tide is
    # blocked (unless forced); NEUTRAL warns. This is the tide actually governing the book.
    tide = None
    try:
        from hl import macro_regime
        tide = macro_regime.read()
        if side == "long" and tide.get("label") == "RISK-OFF":
            violations.append({"level": "block",
                               "msg": f"macro TIDE is RISK-OFF (score {tide.get('score')}) — Layer-1 says "
                                      f"step aside from new longs (validated: maxDD −77%→−58%)."})
        elif side == "long" and tide.get("label") == "NEUTRAL":
            violations.append({"level": "warn",
                               "msg": f"macro TIDE NEUTRAL (score {tide.get('score')}) — mixed tape, "
                                      f"lower conviction on new longs."})
    except Exception:
        pass

    # 5) Layer-2 selection gate — once the tide allows a long, only take LEADERS.
    # Buying a coin that is LAGGING the tide (residual weakness + crowded funding) is
    # the wrong side of the one edge Layer 2 has. Block a new long into a LAGGARD;
    # warn on a 'tracks' (mediocre) name; clean pass for a LEADER.
    l2 = None
    try:
        from hl import layer2
        l2 = layer2.coin_verdict(coin)
        if side == "long" and l2.get("verdict") == "LAGS":
            violations.append({"level": "block",
                               "msg": f"{coin} is a Layer-2 LAGGARD (score {l2.get('score')}) — lagging the "
                                      f"tide (residual weakness); don't buy laggards."})
        elif side == "long" and l2.get("verdict") == "tracks":
            violations.append({"level": "warn",
                               "msg": f"{coin} only TRACKS the tide (Layer-2 score {l2.get('score')}) — "
                                      f"no relative-strength edge; prefer a LEADER."})
    except Exception:
        pass

    # 6) fundamentals gate (Layer-2 other half) — don't OVERPAY, and beware unlocks.
    # Real cash-flow is crypto's only true base. Block a long into a coin that is
    # richly/expensively valued vs its fees AND has a supply flood coming (FDV≫mcap) —
    # overpaying right into dilution is the worst fundamental setup. Warn on rich alone,
    # or on a narrative-only name (no base — pure momentum). Cheap/fair real businesses
    # and L1s pass clean. (A cheap coin passes even with an unlock — it's cheap anyway.)
    fnd = None
    try:
        from hl import fundamentals
        fnd = fundamentals.coin(coin)
        val = fnd.get("valuation")
        if side == "long" and val in ("rich", "expensive") and fnd.get("unlock_overhang"):
            violations.append({"level": "block",
                               "msg": f"{coin} is {val} vs its fees (P/F {fnd.get('pf')}x, "
                                      f"{fnd.get('pf_fdv')}x fully-diluted) — overpaying into an unlock overhang."})
        elif side == "long" and val == "expensive":
            violations.append({"level": "block",
                               "msg": f"{coin} is EXPENSIVE vs its fees (P/F {fnd.get('pf')}x) — overpaying for the cash flow."})
        elif side == "long" and val == "rich":
            violations.append({"level": "warn",
                               "msg": f"{coin} is richly valued (P/F {fnd.get('pf')}x) — paying up for the fees."})
        elif side == "long" and fnd.get("kind") == "narrative":
            violations.append({"level": "warn",
                               "msg": f"{coin} has no cash-flow base — pure narrative/positioning (momentum only)."})
    except Exception:
        pass

    blocked = any(v["level"] == "block" for v in violations) and not force
    return {"ok": not blocked, "blocked": blocked, "force": force,
            "violations": violations,
            "correlated_with": [{"coin": c, "corr": round(r, 2)} for c, r in high],
            "regime": reg.get("regime") if reg else None,
            "tide": tide.get("label") if tide else None,
            "layer2": l2.get("verdict") if l2 else None,
            "fundamentals": (fnd.get("valuation") or fnd.get("kind")) if fnd else None}
