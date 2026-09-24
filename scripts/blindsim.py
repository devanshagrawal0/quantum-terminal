"""Blind judgment sim — backtest ME. Deal a random past date, anonymized coins,
past-only features, future masked. I commit picks; --reveal scores raw vs regime-
filtered (L7 gate: drop shorts in uptrend / longs in downtrend) vs market, and keeps
a running aggregate so many hands give a real read."""
import sys, json, random, argparse
from pathlib import Path
import pandas as pd, numpy as np
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/"data"/"blindsim"; D.mkdir(exist_ok=True); RES=D/"results.jsonl"; HOLD=5

def load():
    P=pd.read_parquet(ROOT/"data/carry_cache/daily_365.parquet")
    F=pd.read_parquet(ROOT/"data/carry_cache/funding_daily_365.parquet")
    good=[c for c in P.columns if P[c].notna().sum()>320 and c in F.columns]
    return P[good], F[good]

def new(seed):
    random.seed(seed*97+13); np.random.seed(seed*97+13)
    P,F=load(); N=len(P); t=random.randint(100,N-HOLD-1)
    coins=[c for c in P.columns if P[c].iloc[:t+1].notna().sum()>95 and not np.isnan(P[c].iloc[t])]
    coins=random.sample(coins,min(12,len(coins))); labs=[chr(65+i) for i in range(len(coins))]; random.shuffle(labs)
    def r(c,n):
        s=P[c].iloc[:t+1].dropna(); return float(s.iloc[-1]/s.iloc[-1-n]-1) if len(s)>n else None
    rows=[]; ans={}
    for c,lab in zip(coins,labs):
        vol=float(P[c].iloc[max(0,t-30):t+1].pct_change().std())
        fund=float(F[c].iloc[t]*365) if not np.isnan(F[c].iloc[t]) else None
        rows.append(dict(label=lab,r7=r(c,7),r30=r(c,30),r90=r(c,90),fund=fund,vol=vol))
        ans[lab]=dict(coin=c,fwd=float(P[c].iloc[t+HOLD]/P[c].iloc[t]-1))
    btc30=r('BTC',30); btc7=r('BTC',7)
    mkt=float(np.nanmean([ans[l]['fwd'] for l in ans]))
    (D/f"{seed}.json").write_text(json.dumps(dict(seed=seed,answer=ans,mkt=mkt,btc30=btc30,btc7=btc7)))
    print(f"--- HAND {seed} | regime: BTC 7d {btc7*100:+.0f}% 30d {btc30*100:+.0f}% ({'UPTREND' if btc30>0.03 else 'DOWNTREND' if btc30<-0.03 else 'CHOP'}) ---")
    print(f"{'':<4}{'7d':>7}{'30d':>7}{'90d':>7}{'fund':>7}{'vol':>6}")
    for x in sorted(rows,key=lambda z:-(z['r7'] or -9)):
        print(f"{x['label']:<4}{(x['r7'] or 0)*100:>+6.0f}%{(x['r30'] or 0)*100:>+6.0f}%{(x['r90'] or 0)*100:>+6.0f}%{(x['fund'] or 0)*100:>+6.0f}%{(x['vol'] or 0)*100:>5.1f}%")

def reveal(seed,picks):
    s=json.loads((D/f"{seed}.json").read_text()); ans=s['answer']; btc30=s['btc30']
    longs=shorts=[]
    for p in picks.replace(' ','').split(';'):
        if p.startswith('long:'): longs=[x for x in p[5:].split(',') if x]
        if p.startswith('short:'): shorts=[x for x in p[6:].split(',') if x]
    raw=[]; filt=[]
    up=btc30>0.03; dn=btc30<-0.03
    for l in longs:
        if l in ans: raw.append(ans[l]['fwd']);          filt.append(ans[l]['fwd']) if not dn else None
    for l in shorts:
        if l in ans: raw.append(-ans[l]['fwd']);         filt.append(-ans[l]['fwd']) if not up else None
    rawm=np.mean(raw) if raw else 0; filtm=np.mean(filt) if filt else s['mkt']
    rec=dict(seed=seed,raw=rawm-s['mkt'],filt=filtm-s['mkt'],mkt=s['mkt'],n_raw=len(raw),n_filt=len(filt))
    with open(RES,'a') as f: f.write(json.dumps(rec)+"\n")
    names={l:ans[l]['coin'] for l in longs+shorts if l in ans}
    print(f"H{seed}: picks {names} | raw edge {rec['raw']*100:+.1f}% | filtered {rec['filt']*100:+.1f}% | mkt {s['mkt']*100:+.1f}%")

def tally():
    if not RES.exists(): print("no results"); return
    rs=[json.loads(l) for l in RES.read_text().splitlines() if l.strip()]
    raw=np.mean([r['raw'] for r in rs]); filt=np.mean([r['filt'] for r in rs])
    print(f"\n=== AGGREGATE over {len(rs)} hands ===")
    print(f"  MY RAW judgment:        avg edge vs market {raw*100:+.2f}%  | positive hands {sum(r['raw']>0 for r in rs)}/{len(rs)}")
    print(f"  ENFORCEMENT-FILTERED:   avg edge vs market {filt*100:+.2f}%  | positive hands {sum(r['filt']>0 for r in rs)}/{len(rs)}")

ap=argparse.ArgumentParser(); ap.add_argument('--new',type=int); ap.add_argument('--reveal',type=int); ap.add_argument('--picks',default=''); ap.add_argument('--tally',action='store_true')
a=ap.parse_args()
if a.new is not None: new(a.new)
elif a.reveal is not None: reveal(a.reveal,a.picks)
elif a.tally: tally()
