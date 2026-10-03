import pandas as pd, numpy as np
from pathlib import Path
D=Path('/home/claude/opt0dte/data'); b=pd.read_csv(D/'basis_prev.csv')
rows=[]
for r in b.itertuples():
    p=pd.read_parquet(D/'finmind'/'fut'/f'{r.date}.parquet'); p['t']=pd.to_datetime(p.date); p['contract_date']=p.contract_date.astype(str).str.strip()
    p=p[(p.contract_date==str(r.contract))&(p.t.dt.strftime('%Y-%m-%d')==r.date)].sort_values('t')
    ix=pd.read_parquet(D/'finmind'/'taiex5s'/f'{r.date}.parquet'); ix['t']=pd.to_datetime(ix.date); ix=ix.sort_values('t')
    for hhmm in ['09:00:05','09:05:00','09:30:00']:
        t=pd.Timestamp(f'{r.date} {hhmm}')
        f=p[p.t<=t].price.iloc[-1]; s=ix[ix.t<=t].TAIEX.iloc[-1]
        rows.append(dict(date=r.date,time=hhmm,est=f-r.basis_prev,spot=s,basis_now=f-s,basis_prev=r.basis_prev))
x=pd.DataFrame(rows); x['err_pts']=x.est-x.spot; x['err_pct']=x.err_pts/x.spot*100
x['is']=x.date<'2023-01-01'
print(x.groupby('time').err_pct.describe(percentiles=[.05,.25,.5,.75,.95]).round(3).to_string())
a=x[x.time=='09:00:05']; print('\n|err|<0.1%:',(a.err_pct.abs()<0.1).mean().round(3),' <0.2%:',(a.err_pct.abs()<0.2).mean().round(3))
print(a.reindex(a.err_pct.abs().sort_values(ascending=False).index).head(8)[['date','est','spot','err_pts','err_pct','basis_prev','basis_now']].round(2).to_string(index=False))
x.to_csv(D/'basis_check.csv',index=False)
