import shioaji as sj, pandas as pd, os, sys, time, datetime as dt
from zoneinfo import ZoneInfo
TW=ZoneInfo('Asia/Taipei')
from common import login
D=str(__import__('pathlib').Path(__file__).resolve().parent.parent/'data'); OUT=f'{D}/shioaji/opt'; os.makedirs(OUT,exist_ok=True)
ROOT={'W1':'TX1','W2':'TX2','W4':'TX4','W5':'TX5','F1':'TXU','F2':'TXV','F3':'TXX','F4':'TXY','F5':'TXZ'}
L='ABCDEFGHIJKL'; LP='MNOPQRSTUVWX'
def code(cm, strike, cp):
    k=cm[6:]; root='TXO' if k=='' else ROOT[k]; m=int(cm[4:6]); y=int(cm[3])
    return f'{root}{int(strike)}{(L if cp=="C" else LP)[m-1]}{y}'
def log(*a): print(dt.datetime.now(TW).strftime('%m-%d %H:%M:%S'),*a,flush=True)
def wait_reset():
    now=dt.datetime.now(TW); nxt=(now+dt.timedelta(days=1)).replace(hour=8,minute=10,second=0) if now.hour>=8 else now.replace(hour=8,minute=10,second=0)
    log('quota exhausted, sleep until',nxt); time.sleep((nxt-now).total_seconds())
SANITY_FAILS={}
def day_vol(df, ds, tcol):
    t=pd.to_datetime(df[tcol]); m=(t.dt.strftime('%Y-%m-%d')==ds)&(t.dt.hour>=8)&(t.dt.hour<14)
    return df.loc[m,'volume'].sum()
def check(out, fm_day, ds):
    """return reason string if the pulled day looks incomplete"""
    if len(out)==0: return 'zero rows'
    v=day_vol(out,ds,'ts')
    if v==0: return 'zero day-session volume'
    if len(fm_day):
        fv=fm_day.volume.sum()   # FinMind volume is B+S -> expect ratio ~0.5
        if fv>0 and v/fv<0.47: return f'volume ratio vs FinMind {v/fv:.3f} < 0.47'
    return None
def relogin(api):
    for a in range(20):
        try:
            try: api.logout()
            except Exception: pass
            api2=login(); log('re-login ok'); return api2
        except Exception as e:
            log('re-login failed',repr(e)[:120]); time.sleep(min(300,30*(a+1)))
    raise RuntimeError('cannot re-login')
def main(start='2023-01-01', end='2026-09-22', maxdates=10**6, dates=None):
    cal=pd.read_csv(f'{D}/settlement_calendar.csv',parse_dates=['date'])
    cal=cal[(cal.date>=start)&(cal.date<=end)] if dates is None else cal[cal.date.dt.strftime('%Y-%m-%d').isin(dates)]
    cal=cal.sort_values('date',ascending=False)
    api=login(); n=0
    for r in cal.itertuples():
        ds=r.date.strftime('%Y-%m-%d'); f=f'{OUT}/{ds}.parquet'
        if os.path.exists(f): continue
        fm=f'{D}/finmind/opt/{ds}.parquet'
        o=pd.DataFrame()
        if os.path.exists(fm):
            o=pd.read_parquet(fm)
            if len(o): t=pd.to_datetime(o.date); o=o[(t.dt.date==r.date.date())&(t.dt.hour>=8)]
        if len(o):
            ks=o.groupby(['ExercisePrice','PutCall']).size().reset_index()
        else:  # no FinMind file: SSP +-10% grid, 50-pt step (empty contracts return 404 and cost ~nothing)
            lo=int(r.ssp*0.90//50*50); hi=int(r.ssp*1.10//50*50)
            ks=pd.DataFrame([(float(k),cp,0) for k in range(lo,hi+50,50) for cp in 'CP'],columns=['ExercisePrice','PutCall',0])
        u0=api.usage().bytes; parts=[]; t0=time.time(); failed=[]
        restart=False
        for i,(s,cp,_) in enumerate(ks.itertuples(index=False)):
            if i%10==0:
                try: rem=api.usage().remaining_bytes
                except Exception: rem=10**9
                if rem<5e6:   # quota (nearly) gone: server then answers 'not found' for everything -> never trust it
                    wait_reset(); api=relogin(api); restart=True; break
            c=code(r.contract_month,s,cp); df=None
            for a in range(6):
                try:
                    # RangeTime full-day: identical data to the default query, but a different request key -> avoids
                    # server-side cached empty answers from the 2026-09-23 quota overrun
                    df=pd.DataFrame({**api.ticks(sj.Option(code=c,exchange='TAIFEX',security_type='OPT'),date=ds,
                        query_type=sj.TicksQueryType.RangeTime,time_start='00:00:00',time_end='23:59:59')}); break
                except Exception as e:
                    msg=repr(e)
                    if 'UsageLimit' in msg or ('usage' in msg.lower() and 'limit' in msg.lower()):
                        wait_reset(); api=relogin(api); continue
                    if 'not found' in msg.lower() or '404' in msg: df=pd.DataFrame(); break
                    log('err',c,msg[:150], 'retry',a+1)
                    time.sleep(min(60,10*(a+1)))
                    if a>=1: api=relogin(api)   # connection/timeout: re-login before next try
            if df is None: failed.append(c); continue
            if len(df): df['code']=c; df['strike']=s; df['cp']=cp; parts.append(df)
            time.sleep(0.12)
        if restart:
            log('quota hit mid-date, will redo',ds); continue
        if failed:
            log('DATE FAILED, not saved (will retry):',ds,len(failed),'contracts e.g.',failed[:3]); continue
        out=pd.concat(parts) if parts else pd.DataFrame()
        bad=check(out, o, ds)
        if bad:
            SANITY_FAILS[ds]=SANITY_FAILS.get(ds,0)+1
            if True:   # never save a day that fails the check (server may serve cached empty answers)
                log('SANITY FAIL, not saved (will retry):',ds,bad); time.sleep(30); continue
            log('SAVED WITH WARNING after 3 tries:',ds,bad)
            open(f'{OUT}/_warnings.txt','a').write(f'{ds}\t{bad}\n')
        out.to_parquet(f+'.tmp',index=False); os.replace(f+'.tmp',f); n+=1
        time.sleep(2); u1=api.usage()
        log(ds,r.contract_month,'contracts',len(ks),'rows',len(out),'MB',round((u1.bytes-u0)/1e6,2),'remain MB',round(u1.remaining_bytes/1e6,1),f'{time.time()-t0:.0f}s')
        if n>=maxdates: break
    log('ALL DONE')
if __name__=='__main__':
    a=sys.argv; main(*(a[1:3] if len(a)>2 else []), **({'maxdates':int(a[3])} if len(a)>3 else {}))
