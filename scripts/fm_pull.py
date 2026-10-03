import requests, pandas as pd, os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from common import load_env
D=str(__import__('pathlib').Path(__file__).resolve().parent.parent/'data'); FM=f'{D}/finmind'
for s in ['opt','fut','taiex5s']: os.makedirs(f'{FM}/{s}',exist_ok=True)
tok=load_env()['FINMIND_TOKEN']; U='https://api.finmindtrade.com/api/v4/data'; H={'Authorization':f'Bearer {tok}'}
def q(**p):
    for a in range(6):
        try:
            r=requests.get(U,params=p,headers=H,timeout=300); j=r.json()
            if j.get('status')==200 or j.get('msg')=='success': return pd.DataFrame(j.get('data',[]))
            print('api msg',p.get('dataset'),p.get('start_date'),j.get('msg'),flush=True)
            if 'limit' in str(j.get('msg')).lower() or r.status_code==402: time.sleep(600)
            else: time.sleep(10*(a+1))
        except Exception as e: print('err',p.get('dataset'),p.get('start_date'),repr(e)[:120],flush=True); time.sleep(10*(a+1))
    raise RuntimeError(f'failed {p}')
cal=pd.read_csv(str(__import__('pathlib').Path(__file__).resolve().parent/'cal_exclude_today.csv'),parse_dates=['date'])
cal=cal[cal.date>='2011-01-01']
td=q(dataset='TaiwanStockTradingDate',start_date='2010-12-01',end_date='2026-12-31'); td=sorted(pd.to_datetime(td.date))
td=pd.Series(td)
def prev_td(d): return td[td<d].iloc[-1]
def job(row):
    d=row.date; ds=d.strftime('%Y-%m-%d'); cm=row.contract_month; out=[]
    # options: expiring series only; night part before midnight lives on previous calendar date
    f=f'{FM}/opt/{ds}.parquet'
    if not os.path.exists(f):
        parts=[]
        dates=[ds]+([prev_td(d).strftime('%Y-%m-%d')] if d>=pd.Timestamp('2017-05-15') else [])
        for x in dates:
            o=q(dataset='TaiwanOptionTick',data_id='TXO',start_date=x)
            if len(o):
                o=o[o.contract_date.astype(str).str.strip()==cm]
                if x!=ds: o=o[pd.to_datetime(o.date).dt.hour>=15]
                parts.append(o)
        o=pd.concat(parts) if parts else pd.DataFrame()
        o.to_parquet(f,index=False); out.append(f'opt {len(o)}')
    f=f'{FM}/fut/{ds}.parquet'
    if not os.path.exists(f):
        parts=[]
        dates=[ds]+([prev_td(d).strftime('%Y-%m-%d')] if d>=pd.Timestamp('2017-05-15') else [])
        for x in dates:
            o=q(dataset='TaiwanFuturesTick',data_id='TX',start_date=x)
            if len(o):
                o=o[~o.contract_date.astype(str).str.contains('/')]
                if x!=ds: o=o[pd.to_datetime(o.date).dt.hour>=15]
                parts.append(o)
        o=pd.concat(parts) if parts else pd.DataFrame(); o.to_parquet(f,index=False); out.append(f'fut {len(o)}')
    f=f'{FM}/taiex5s/{ds}.parquet'
    if not os.path.exists(f):
        o=q(dataset='TaiwanVariousIndicators5Seconds',start_date=ds); o.to_parquet(f,index=False); out.append(f'idx {len(o)}')
    return ds, cm, out
if __name__=='__main__':
    n=int(sys.argv[1]) if len(sys.argv)>1 else len(cal)
    rows=list(cal.sort_values('date',ascending=False).head(n).itertuples())
    t0=time.time(); done=0
    with ThreadPoolExecutor(int(sys.argv[2]) if len(sys.argv)>2 else 4) as ex:
        for fu in as_completed([ex.submit(job,r) for r in rows]):
            try: ds,cm,out=fu.result(); done+=1; print(f'[{done}/{len(rows)}] {ds} {cm} {out} {time.time()-t0:.0f}s',flush=True)
            except Exception as e: print('JOB FAIL',repr(e)[:200],flush=True)
    print('ALL DONE',time.time()-t0,flush=True)
