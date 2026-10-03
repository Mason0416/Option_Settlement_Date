"""prev-day basis (near-month TX futures - TAIEX) at 13:30, per settlement day. Used to estimate spot 08:45-09:00."""
import pandas as pd, numpy as np, requests, os, time
from pathlib import Path
from common import load_env
ROOT=Path(__file__).resolve().parent.parent; D=ROOT/'data'
tok=load_env()['FINMIND_TOKEN']; H={'Authorization':f'Bearer {tok}'}; U='https://api.finmindtrade.com/api/v4/data'
def q(**p):
    for a in range(5):
        try:
            j=requests.get(U,params=p,headers=H,timeout=300).json()
            if j.get('msg')=='success': return pd.DataFrame(j['data'])
        except Exception as e: pass
        time.sleep(5*(a+1))
    raise RuntimeError(p)
cal=pd.read_csv(D/'settlement_calendar.csv',parse_dates=['date']); cal=cal[(cal.date>='2017-05-15')&(cal.date<='2026-09-22')]
td=pd.to_datetime(q(dataset='TaiwanStockTradingDate',start_date='2017-01-01',end_date='2026-12-31').date).sort_values().values
def one(r):
    ds=r.date.strftime('%Y-%m-%d')
    fp=D/'finmind'/'fut'/f'{ds}.parquet'
    if fp.exists(): p=pd.read_parquet(fp)
    else: p=pd.read_parquet(D/'finmind'/'fut'/f'{ds[:7]}.parquet'); p=p[p.settle_date==ds]
    p=p.assign(t=pd.to_datetime(p.date)); p['contract_date']=p.contract_date.astype(str).str.strip()
    pre=p[(p.t.dt.strftime('%Y-%m-%d')==ds)&(p.t.dt.time>=pd.Timestamp('08:45').time())&(p.t.dt.time<pd.Timestamp('09:00').time())]
    if not len(pre): return dict(date=ds)
    c=pre.groupby('contract_date').volume.sum().idxmax()
    prev=pd.Timestamp(td[td<np.datetime64(r.date)][-1]).strftime('%Y-%m-%d')
    f=q(dataset='TaiwanFuturesTick',data_id='TX',start_date=prev); f['t']=pd.to_datetime(f.date); f['contract_date']=f.contract_date.astype(str).str.strip()
    f=f[(f.contract_date==c)&(f.t.dt.strftime('%Y-%m-%d')==prev)&(f.t.dt.time<=pd.Timestamp('13:30').time())]
    ix=pd.read_parquet(D/'finmind'/'taiex5s'/f'{ds}.parquet') if (D/'finmind'/'taiex5s'/f'{ds}.parquet').exists() else None
    if ix is None:
        y=pd.read_parquet(D/'finmind'/'taiex5s'/f'{ds[:4]}.parquet'); ix=y[y.settle_date==ds]
    ix=ix.assign(t=pd.to_datetime(ix.date)).sort_values('t')
    spot_prev=ix.TAIEX.iloc[0]   # 09:00:00 print = previous close
    return dict(date=ds,contract=c,prev_date=prev,fut_prev_1330=f.price.iloc[-1] if len(f) else np.nan,spot_prev_close=spot_prev)
from concurrent.futures import ThreadPoolExecutor
rows=[]
with ThreadPoolExecutor(6) as ex:
    for i,x in enumerate(ex.map(one, list(cal.itertuples()))):
        rows.append(x)
        if i%50==0: print(i,flush=True)
b=pd.DataFrame(rows); b['basis_prev']=b.fut_prev_1330-b.spot_prev_close
b.to_csv(D/'basis_prev.csv',index=False); print(b.describe().round(2).to_string()); print(b.isna().sum().to_dict())
