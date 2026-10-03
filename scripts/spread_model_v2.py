"""Relative half-spread model by (half-hour bucket x moneyness level x C/P), from Shioaji 2026 quotes (quotes only, no P&L)."""
import pandas as pd, numpy as np, glob, os
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; D=ROOT/'data'
LEVELS=np.array([-1.0,-0.5,0.0,0.5,1.0,1.5,2.0,3.0])
fs=sorted(glob.glob('/mnt/user-data/uploads/選擇權_結算日/data/shioaji/opt/2026-*.parquet'))
rows=[]
for f in fs:
    ds=os.path.basename(f)[:10]; d=pd.read_parquet(f); d['t']=pd.to_datetime(d.ts).astype('datetime64[ns]')
    d=d[(d.t.dt.strftime('%Y-%m-%d')==ds)&(d.t.dt.time>=pd.Timestamp('09:00').time())&(d.t.dt.time<pd.Timestamp('13:30').time())]
    d=d[(d.bid_price>0)&(d.ask_price>0)&(d.ask_price>=d.bid_price)]
    ix=pd.read_parquet(D/'finmind'/'taiex5s'/f'{ds}.parquet'); ix['t']=pd.to_datetime(ix.date).astype('datetime64[ns]'); ix=ix[ix.t.dt.time>pd.Timestamp('09:00:00').time()].sort_values('t')
    d=d.sort_values('t'); d=pd.merge_asof(d,ix[['t','TAIEX']],on='t',direction='backward').dropna(subset=['TAIEX'])
    otm=np.where(d.cp=='C',(d.strike-d.TAIEX)/d.TAIEX*100,(d.TAIEX-d.strike)/d.TAIEX*100)
    j=np.abs(otm[:,None]-LEVELS[None,:]).argmin(1); keep=np.abs(otm-LEVELS[j])<=0.25
    d=d[keep].assign(level=LEVELS[j][keep])
    d['bucket']=d.t.dt.floor('30min').dt.strftime('%H:%M')
    mid=(d.ask_price+d.bid_price)/2
    d['rel_half']=(d.ask_price-d.bid_price)/2/mid.clip(lower=0.05)
    rows.append(d[['bucket','level','cp','rel_half','close']])
x=pd.concat(rows)
m=x.groupby(['bucket','cp','level']).agg(n=('rel_half','size'),rel_half_med=('rel_half','median'),prem_med=('close','median')).reset_index()
m.to_csv(ROOT/'results'/'spread_model_v2.csv',index=False)
print(len(fs),'days',len(x),'ticks'); print(m.pivot_table(index='bucket',columns=['cp','level'],values='rel_half_med').round(3).to_string())
