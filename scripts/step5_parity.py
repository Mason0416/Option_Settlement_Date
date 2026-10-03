"""Step 5: put-call parity mispricing. Option-implied spot S* = C - P + K (same strike, last trades in [t-5m, t), |tC-tP|<=60s)
vs TAIEX at the pair time. dev = S*/spot - 1 (%). Only pre-entry info. In-sample only. Slots 09:30-13:00 (index stale near 09:00)."""
import pandas as pd, numpy as np
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
ROOT=Path(__file__).resolve().parent.parent; D=ROOT/'data'; OUT=ROOT/'results'/'step5_parity'; OUT.mkdir(parents=True,exist_ok=True)
SLOTS=['09:30','10:00','10:30','11:00','11:30','12:00','12:30','13:00']
cal=pd.read_csv(D/'settlement_calendar.csv'); cal=cal[(cal.date>='2017-05-15')&(cal.date<='2022-12-31')]
def one(a):
    ds,ssp=a
    op=D/'finmind'/'opt'/f'{ds}.parquet'; tp=D/'finmind'/'taiex5s'/f'{ds}.parquet'
    if not op.exists() or not tp.exists(): return []
    o=pd.read_parquet(op); o['t']=pd.to_datetime(o.date); o=o[(o.t>=pd.Timestamp(f'{ds} 08:45'))&(o.t<=pd.Timestamp(f'{ds} 13:30'))]
    o=o.reset_index(drop=True); o['seq']=np.arange(len(o))
    x=pd.read_parquet(tp); x['t']=pd.to_datetime(x.date); x=x[x.t>pd.Timestamp(f'{ds} 09:00:00')].sort_values('t')
    out=[]
    for s in SLOTS:
        T=pd.Timestamp(f'{ds} {s}:00'); xs=x[x.t<T]
        if xs.empty: continue
        spot_t=xs.TAIEX.iloc[-1]
        w=o[(o.t>=T-pd.Timedelta('5min'))&(o.t<T)]
        cumv=o[o.t<T].groupby('ExercisePrice').volume.sum()
        last=w.sort_values(['t','seq']).groupby(['ExercisePrice','PutCall']).tail(1).set_index(['ExercisePrice','PutCall'])
        rows=[]
        for K in w.ExercisePrice.unique():
            if abs(K/spot_t-1)>0.015 or (K,'C') not in last.index or (K,'P') not in last.index: continue
            c=last.loc[(K,'C')]; p=last.loc[(K,'P')]
            if abs((c.t-p.t).total_seconds())>60: continue
            tm=max(c.t,p.t); sp=xs[xs.t<=tm]
            if sp.empty: continue
            S=sp.TAIEX.iloc[-1]; rows.append((K,(c.price-p.price+K)/S-1,cumv.get(K,0)))
        if not rows: continue
        r=pd.DataFrame(rows,columns=['K','dev','vol'])
        out.append((ds,s,spot_t,ssp,len(r),r.dev.median()*100,r.loc[r.vol.idxmax(),'dev']*100,r.loc[r.vol.idxmax(),'K']))
    return out
if __name__=='__main__':
    with ProcessPoolExecutor(8) as ex: res=[y for z in ex.map(one,list(zip(cal.date,cal.ssp))) for y in z]
    R=pd.DataFrame(res,columns=['date','slot','spot','ssp','npairs','dev_med','dev_vmax','K_vmax'])
    R['move']=(R.ssp/R.spot-1)*100
    R.to_csv(OUT/'parity.csv',index=False)
    print(R.describe().round(3).to_string())
