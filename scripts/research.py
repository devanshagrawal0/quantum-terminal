"""Deep-research CLI: prep a coin's packet, or store/read research notes.

    python scripts/research.py ETH            # print the internal packet (context to web-research)
    python scripts/research.py --notes        # list stored research notes
    python scripts/research.py --note ETH ... # (used programmatically to log a finding)
"""
import argparse, sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hl import research


def show_packet(coin):
    p = research.packet(coin)
    print(f"=== {p['coin']} — internal packet (context BEFORE web research) ===")
    def g(k, f="{}"):
        return f.format(p[k]) if p.get(k) is not None else "n/a"
    print(f"  price {g('price')}  |  24h vol ${(p.get('credible_vol_usd') or 0)/1e6:.0f}m")
    print(f"  returns: 1d {g('ret_1d','{:+.1%}')}  7d {g('ret_7d','{:+.1%}')}  30d {g('ret_30d','{:+.1%}')}")
    print(f"  funding APR {g('funding_apr','{:+.0%}')}  |  perp-spot basis {g('perp_spot_basis_bps','{:+.0f}')}bps"
          f"  |  Korea premium {g('premium_krw_bps','{:+.0f}')}bps")
    ms = p.get('our_social_mentions') or []
    print(f"  our social mentions ({len(ms)}):")
    for m in ms[:3]:
        print(f"    [{m['source']}] {m['text']}")
    pr = p.get('prior_research')
    if pr:
        print(f"  PRIOR RESEARCH ({pr['age_hours']:.0f}h ago): {pr['verdict']} — {pr['headline']}")
    else:
        print("  no prior research on file — do a full deep dive")
    print("\n  -> now web-search this coin: what it is, sector heat, catalysts, dev activity, what people say.")


def list_notes():
    ns = research.all_notes()
    if not ns:
        print("no research notes yet")
        return
    print(f"{len(ns)} research notes:\n")
    for n in ns:
        t = time.strftime("%m-%d %H:%M", time.localtime(n['created_ms']/1000))
        print(f"  {t}  {n['coin']:<8}{n['verdict']:<7}conf {n['confidence']:.2f}  {n['headline']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("coin", nargs="?")
    ap.add_argument("--notes", action="store_true")
    args = ap.parse_args()
    if args.notes:
        list_notes()
    elif args.coin:
        show_packet(args.coin)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
