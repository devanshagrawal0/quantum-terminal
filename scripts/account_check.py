"""Read-only account view.

    set HL_ACCOUNT_ADDRESS=0xyourpublicaddress
    python scripts/account_check.py

Only ever needs your PUBLIC 0x address. This package holds no keys and cannot
sign, place or cancel anything.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl import Account  # noqa: E402


def main() -> None:
    addr = sys.argv[1] if len(sys.argv) > 1 else os.getenv("HL_ACCOUNT_ADDRESS")
    if not addr:
        print("no address. Either:\n"
              "  set HL_ACCOUNT_ADDRESS=0x...   (PowerShell: $env:HL_ACCOUNT_ADDRESS='0x...')\n"
              "  python scripts/account_check.py 0x...")
        return
    acc = Account(addr)

    print(f"\naccount {acc.address}")
    print("\n-- equity")
    for k, v in acc.equity().items():
        print(f"  {k:<28} {v}")

    print("\n-- positions")
    pos = acc.positions()
    print("  (flat)" if pos.empty else pos.to_string(index=False))

    print("\n-- open orders")
    oo = acc.open_orders()
    print("  (none)" if oo.empty else oo.to_string(index=False))

    print("\n-- last 7 days")
    for k, v in acc.pnl_summary(7).items():
        print(f"  {k:<28} {v}")

    print("\n-- api budget for this address")
    for k, v in acc.rate_limit().items():
        print(f"  {k:<28} {v}")
    print()


if __name__ == "__main__":
    main()
