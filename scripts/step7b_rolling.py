"""Step 7b: Step 7 with rolling percentile (past N settlement days only, same slot) instead of full-sample percentile."""
import pandas as pd, numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step7_cross3'
SL=['09:30','10:00','10:30','11:00','11:30','12:00']
R=pd.read_csv(ROOT/'results'/'step5_parity'/'parity.csv')[['date','slot','dev_med']].sort_values(['slot','date'])
def roll(x,N):
    v=x.values; out=np.full(len(v),np.nan)
    for i in range(N,len(v)): out[i]=(v[i-N:i]<v[i]).mean()+0.5*(v[i-N:i]==v[i]).mean()
    return pd.Series(out,index=x.index)
for N in [50,100]: R[f'r{N}']=R.groupby('slot').dev_med.transform(lambda x: roll(x,N))
R['full']=R.groupby('slot').dev_med.rank(pct=True)
g=pd.read_parquet(ROOT/'results'/'step4d_cross'/'trades.parquet').merge(R,on=['date','slot'])
g=g[((g.grp=='盤前漲・開盤後漲')&(g.cp=='C'))|((g.grp=='盤前跌・開盤後跌')&(g.cp=='P'))].copy()
tt=lambda p: p.mean()/p.std()*np.sqrt(len(p)) if len(p)>2 else np.nan
def st(p):
    p=p.sort_values(); n=len(p); return dict(n=n,mean=round(p.mean(),1),t=round(tt(p),2),total=round(p.sum()),ex5=round(p.iloc[:-5].sum()) if n>5 else np.nan)
rows=[]
for N in [50,100]:
  d0=g[g[f'r{N}'].notna()]   # same sample for all methods
  for L,ln in [(-1.0,'價內1%'),(0.0,'價平')]:
    for s in SL:
      d=d0[(d0.level==L)&(d0.slot==s)]
      for meth in ['full',f'r{N}']:
        cheap=np.where(d.cp=='C',1-d[meth],d[meth])
        for k,c in [('不加平價',cheap>=0),('便宜30%',cheap>=0.7),('便宜20%',cheap>=0.8),('貴30%',cheap<=0.3)]:
          rows.append(dict(window=N,level=ln,slot=s,method='全樣本百分位' if meth=='full' else f'滾動{N}日',filt=k,**st(d[c].pnl_real)))
T=pd.DataFrame(rows); T.to_csv(OUT/'rolling.csv',index=False)
pd.set_option('display.width',220)
for N in [50,100]:
  for ln in ['價內1%','價平']:
    q=T[(T.window==N)&(T.level==ln)&(T.slot.isin(['09:30','10:00','10:30']))]
    print(f'==== 窗口 {N}，{ln}（樣本起點 {g[g[f"r{N}"].notna()].date.min()}）')
    print(q.pivot_table(index=['filt','method'],columns='slot',values=['mean','t','n'],aggfunc='first').round(2).to_string())
