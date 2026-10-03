"""Step 5c: parity split into two rules. Call rule: buy Call only when dev low; Put rule: buy Put only when dev high. In-sample."""
import pandas as pd, numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step5_parity'
R=pd.read_csv(OUT/'parity.csv')[['date','slot','dev_med']]
R['pct']=R.groupby('slot').dev_med.rank(pct=True)
g=pd.read_parquet(ROOT/'results'/'step4_timefilter'/'trades.parquet').merge(R,on=['date','slot'])
def st(p):
    p=p.sort_values(); n=len(p)
    return dict(n=n,mean=round(p.mean(),1),t=round(p.mean()/p.std()*np.sqrt(n),2),win=round((p>0).mean(),2),total=round(p.sum()),ex5=round(p.iloc[:-5].sum()))
rows=[]
for L,ln in [(-1.0,'價內1%'),(0.0,'價平')]:
  for s in ['09:30','10:00','10:30','11:00','11:30','12:00']:
    x=g[(g.level==L)&(g.slot==s)]
    for cp in 'CP':
      y=x[x.cp==cp]
      conds={'不過濾':y.index==y.index,'正負號':(y.dev_med<0) if cp=='C' else (y.dev_med>0),
             '極端30%':(y.pct<=0.3) if cp=='C' else (y.pct>=0.7),'極端20%':(y.pct<=0.2) if cp=='C' else (y.pct>=0.8)}
      for k,c in conds.items(): rows.append(dict(level=ln,slot=s,cp='Call' if cp=='C' else 'Put',filt=k,**st(y[c].pnl_real)))
T=pd.DataFrame(rows); T.to_csv(OUT/'split.csv',index=False)
pd.set_option('display.width',200)
for ln in ['價內1%','價平']:
  for cp in ['Call','Put']:
    print('==',ln,cp); print(T[(T.level==ln)&(T.cp==cp)].pivot(index='filt',columns='slot',values='mean').reindex(['不過濾','正負號','極端30%','極端20%']).to_string())
    print(T[(T.level==ln)&(T.cp==cp)].pivot(index='filt',columns='slot',values='t').reindex(['不過濾','正負號','極端30%','極端20%']).to_string())
