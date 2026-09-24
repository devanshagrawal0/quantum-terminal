"""Print the assembled situation for one or more coins.

    python scripts/dossier.py REZ
    python scripts/dossier.py BTC ETH HYPE
    python scripts/dossier.py --scan     # rank the whole universe by funding
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hl import dossier


def scan():
    fu = dossier.funding_state
    import sqlite3
    conn = sqlite3.connect(f"file:{dossier.VENUES_DB}?mode=ro", uri=True)
    last = conn.execute("SELECT MAX(ts_ms) FROM hl_state").fetchone()[0]
    rows = conn.execute("SELECT coin, funding_hourly FROM hl_state WHERE ts_ms=? "
                        "AND funding_hourly IS NOT NULL", (last,)).fetchall()
    conn.close()
    ranked = sorted(rows, key=lambda r: -(r[1] or 0))
    print(f"\nfunding leaders (top-decile = measured short-carry candidates), {len(ranked)} coins")
    print(f"  {'coin':<10}{'funding/hr':>13}{'APR':>10}")
    for coin, f in ranked[:12]:
        print(f"  {coin:<10}{f:>+13.6f}{f*24*365:>+10.1%}")
    print("  ...")
    for coin, f in ranked[-4:]:
        print(f"  {coin:<10}{f:>+13.6f}{f*24*365:>+10.1%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("coins", nargs="*")
    ap.add_argument("--scan", action="store_true")
    args = ap.parse_args()
    if args.scan:
        scan()
        return
    for c in (args.coins or ["BTC"]):
        print(dossier.render(dossier.build(c)))
        print()


if __name__ == "__main__":
    main()
