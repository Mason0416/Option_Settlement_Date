"""Step 8: out-of-sample test of locked plans A and B (2023-01 ~ 2026-09-18).
Features recomputed with the same logic as in-sample (premarket: step2_night; open-to-entry: step4c; parity: step5; strike/spot: step1).
Entry: Shioaji ask of first tick in [T,T+5m) when available, else FinMind first trade in [T,T+5m) + half-spread model (min 1 tick).
Mode 'IS' reruns the pipeline on in-sample dates (FinMind+model) to verify it reproduces in-sample trades."""
import pandas as pd, numpy as np, sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
ROOT=Path(__file__).resolve().parent.parent; D=ROOT/'data'; OUT=ROOT/'results'/'oos'; OUT.mkdir(exist_ok=True)
FEE=0.5; TAX_ENTRY=0.001; TAX_SETTLE=0.00002
def tick(p): return np.select([p<10,p<50,p<500,p<1000],[0.1,0.5,1.0,5.0],10.0)
SLOTS=['09:30','10:00']
B=pd.read_csv(D/'basis_prev.csv',dtype={'contract':str}).set_index('date')
SM=pd.read_csv(ROOT/'results'/'spread_model_v2.csv').set_index(['bucket','cp','level']).rel_half_med
def one(a):
    ds,ssp=a
    try:
        o=pd.read_parquet(D/'finmind'/'opt'/f'{ds}.parquet'); f=pd.read_parquet(D/'finmind'/'fut'/f'{ds}.parquet'); x=pd.read_parquet(D/'finmind'/'taiex5s'/f'{ds}.parquet')
    except Exception as e: return []
    c=B.loc[ds,'contract']; pdate=B.loc[ds,'prev_date']
    f['t']=pd.to_datetime(f.date); f['contract_date']=f.contract_date.astype(str).str.strip(); f=f[f.contract_date==c].sort_values('t',kind='stable')
    nc=f[(f.t>pd.Timestamp(f'{pdate} 15:00:00'))&(f.t<pd.Timestamp(f'{ds} 08:45:00'))]
    day=f[(f.t>=pd.Timestamp(f'{ds} 08:45:00'))&(f.t<=pd.Timestamp(f'{ds} 13:45:00'))]
    if nc.empty or day.empty: return []
    F_nc=nc.price.iloc[-1]; F_open=day.price.iloc[0]; premkt=(F_open/F_nc-1)*100
    x['t']=pd.to_datetime(x.date); x=x[x.t>pd.Timestamp(f'{ds} 09:00:00')].sort_values('t')
    o['t']=pd.to_datetime(o.date); o=o[(o.t>=pd.Timestamp(f'{ds} 08:45'))&(o.t<=pd.Timestamp(f'{ds} 13:30'))].reset_index(drop=True); o['seq']=np.arange(len(o))
    out=[]
    for s in SLOTS:
        T=pd.Timestamp(f'{ds} {s}:00'); xs=x[x.t<=T]; fb=day[day.t<T]
        if xs.empty or fb.empty: continue
        S=xs.TAIEX.iloc[-1]; o2e=(fb.price.iloc[-1]/F_open-1)*100
        # parity (step5): last trades in [T-5m,T), same strike C&P within 60s, |K/S-1|<=1.5%, spot = last print <= pair time, among prints < T
        xp=x[x.t<T]; spot_t=xp.TAIEX.iloc[-1] if len(xp) else np.nan
        w=o[(o.t>=T-pd.Timedelta('5min'))&(o.t<T)]
        last=w.sort_values(['t','seq']).groupby(['ExercisePrice','PutCall']).tail(1).set_index(['ExercisePrice','PutCall'])
        devs=[]
        for K in w.ExercisePrice.unique():
            if abs(K/spot_t-1)>0.015 or (K,'C') not in last.index or (K,'P') not in last.index: continue
            cc=last.loc[(K,'C')]; pp=last.loc[(K,'P')]
            if abs((cc.t-pp.t).total_seconds())>60: continue
            sp=xp[xp.t<=max(cc.t,pp.t)]
            if sp.empty: continue
            devs.append((cc.price-pp.price+K)/sp.TAIEX.iloc[-1]-1)
        dev=np.median(devs)*100 if devs else np.nan
        for cp in 'CP':
            ks=np.array(sorted(o[o.PutCall==cp].ExercisePrice.unique()))
            if not len(ks): continue
            K=ks[np.abs(ks-(S*0.99 if cp=='C' else S*1.01)).argmin()]
            g=o[(o.ExercisePrice==K)&(o.PutCall==cp)&(o.t>=T)&(o.t<T+pd.Timedelta('5min'))].sort_values(['t','seq'])
            px=g.price.iloc[0] if len(g) else np.nan
            out.append((ds,s,cp,K,S,ssp,premkt,o2e,dev,len(devs),px))
    return out
def build(dates_ssp):
    with ProcessPoolExecutor(8) as ex: r=[y for z in ex.map(one,dates_ssp) for y in z]
    g=pd.DataFrame(r,columns=['date','slot','cp','strike','spot','ssp','premkt_pct','o2e_pct','dev','npairs','fm_px'])
    g['payoff']=np.where(g.cp=='C',np.maximum(g.ssp-g.strike,0),np.maximum(g.strike-g.ssp,0))
    rh=np.array([SM.get((s,c,-1.0),np.nan) for s,c in zip(g.slot,g.cp)])
    g['fm_entry']=g.fm_px+np.maximum(rh*g.fm_px,tick(g.fm_px))
    return g
def pnl(g,col):
    e=g[col]; settle=np.where(g.payoff>0,FEE+TAX_SETTLE*g.ssp,0.0)
    return g.payoff-e-(FEE+TAX_ENTRY*e)-settle
cal=pd.read_csv(D/'settlement_calendar.csv')
if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'OOS'
    if mode=='IS':
        c=cal[(cal.date>='2017-05-15')&(cal.date<='2022-12-31')]
        g=build(list(zip(c.date,c.ssp))); g['pnl_fm']=pnl(g,'fm_entry'); g.to_csv(OUT/'is_rebuild.csv',index=False); print('IS rows',len(g)); sys.exit()
    c=cal[(cal.date>='2023-01-01')&(cal.date<='2026-09-18')]
    g=build(list(zip(c.date,c.ssp)))
    sj=pd.read_csv(OUT/'sj_entry_ticks.csv')
    g=g.merge(sj.rename(columns={'t':'sj_t','close':'sj_close','bid':'sj_bid','ask':'sj_ask'}),on=['date','slot','strike','cp'],how='left')
    sjdays=set(sj.date)
    g['sj_day']=g.date.isin(sjdays)
    g['entry']=np.where(g.sj_ask>0,g.sj_ask,np.where(g.sj_day,np.nan,g.fm_entry))  # SJ day but no valid ask in 5 min -> no fill
    g['src']=np.where(g.sj_ask>0,'sj_ask',np.where(g.sj_day,'no_fill','fm_model'))
    g['pnl']=pnl(g,'entry'); g['pnl_fm']=pnl(g,'fm_entry')
    g.to_csv(OUT/'oos_candidates.csv',index=False); print('OOS rows',len(g),'days',g.date.nunique()); print(g.src.value_counts())
