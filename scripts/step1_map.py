"""Step 1 map (in-sample 2017-05 ~ 2022-12)
For every settlement day, every entry slot (09:00..13:25, 5-min) and every target moneyness level,
buy the listed strike closest to the target (% from spot, OTM positive), hold to TAIFEX final settlement price.
Entry = first trade in [t, t+5min) + slippage (ticks). No fill in 5 min -> no trade.
Costs: entry fee 0.5pt (25 NTD) + tax 0.1% of premium; if ITM at settlement: 0.5pt fee + tax 2e-5 * SSP.
"""
import pandas as pd, numpy as np, os, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
D=os.environ.get('OPT_DATA',str(ROOT/'data'))
OUT=ROOT/'results'/'step1'
START,END='2017-05-15','2022-12-31'
LEVELS=[-1.0,-0.5,0.0,0.5,1.0,1.5,2.0,3.0]         # % OTM (negative = ITM)
SLOTS=pd.date_range('08:45','13:25',freq='5min').time
EST_UNTIL=pd.Timestamp('09:00').time()   # slots <= 09:00 use futures - prev-day basis (index not open / stale)
FEE=0.5; TAX_ENTRY=0.001; TAX_SETTLE=0.00002
def tick(p):  # TXO tick size by premium
    return np.select([p<10,p<50,p<500,p<1000],[0.1,0.5,1.0,5.0],10.0)
cal=pd.read_csv(f'{D}/settlement_calendar.csv',parse_dates=['date'])
cal=cal[(cal.date>=START)&(cal.date<=END)]
BASIS=pd.read_csv(f'{D}/basis_prev.csv').set_index('date')
def one(args):
    ds,kind,cm,ssp=args
    o=pd.read_parquet(f'{D}/finmind/opt/{ds}.parquet')
    if not len(o): return None
    o['t']=pd.to_datetime(o.date); o=o[(o.t.dt.strftime('%Y-%m-%d')==ds)&(o.t.dt.hour>=8)]
    if not len(o): return None
    ix=pd.read_parquet(f'{D}/finmind/taiex5s/{ds}.parquet'); ix['t']=pd.to_datetime(ix.date); ix=ix.sort_values('t')
    ix=ix[ix.t.dt.time>pd.Timestamp('09:00:00').time()]   # 09:00:00 print = previous close (stale) -> first real print is 09:00:05
    day=pd.Timestamp(ds).date()
    slot_ts=np.array([pd.Timestamp.combine(day,s) for s in SLOTS],dtype='datetime64[ns]')
    spot=ix.TAIEX.values[np.clip(np.searchsorted(ix.t.values,slot_ts,side='right')-1,0,None)].astype(float)
    src=np.array(['index']*len(SLOTS),dtype=object)
    # early slots: estimated spot = near-month futures (day session) - previous-day 13:30 basis
    fp=f'{D}/finmind/fut/{ds}.parquet'
    if os.path.exists(fp) and ds in BASIS.index and not pd.isna(BASIS.loc[ds,'basis_prev']):
        f=pd.read_parquet(fp); f['t']=pd.to_datetime(f.date); f['contract_date']=f.contract_date.astype(str).str.strip()
        f=f[(f.contract_date==str(BASIS.loc[ds,'contract']))&(f.t>=pd.Timestamp(f'{ds} 08:45:00'))].sort_values('t')
        for j,s_ in enumerate(SLOTS):
            if s_<=EST_UNTIL and len(f):
                tt=pd.Timestamp.combine(day,s_); before=f[f.t<=tt]
                fpx=before.price.iloc[-1] if len(before) else f.price.iloc[0]
                spot[j]=fpx-BASIS.loc[ds,'basis_prev']; src[j]='fut-basis'
            elif s_<=EST_UNTIL: spot[j]=np.nan
    book={}
    for (k,cp),g in o.groupby(['ExercisePrice','PutCall']):
        g=g.sort_values('t',kind='stable'); book[(k,cp)]=(g.t.values,g.price.values)
    strikes={cp:np.array(sorted(k for (k,c) in book if c==cp)) for cp in 'CP'}
    out=[]
    for j,s in enumerate(SLOTS):
        S=spot[j]; t0=slot_ts[j]; t1=t0+np.timedelta64(5,'m')
        if np.isnan(S): continue
        for cp in 'CP':
            ks=strikes[cp]
            if not len(ks): continue
            for L in LEVELS:
                target=S*(1+L/100) if cp=='C' else S*(1-L/100)
                k=ks[np.abs(ks-target).argmin()]
                tv,pv=book[(k,cp)]; i=np.searchsorted(tv,t0,side='left')
                filled=i<len(tv) and tv[i]<t1
                px=pv[i] if filled else np.nan
                otm=(k-S)/S*100 if cp=='C' else (S-k)/S*100
                out.append((ds,kind,cm,s.strftime('%H:%M'),cp,L,k,S,src[j],otm,px,ssp))
    return pd.DataFrame(out,columns=['date','kind','contract','slot','cp','level','strike','spot','spot_src','otm_pct','trade_px','ssp'])
def add_pnl(g):
    payoff=np.where(g.cp=='C',np.maximum(g.ssp-g.strike,0),np.maximum(g.strike-g.ssp,0))
    g['payoff']=payoff
    settle_cost=np.where(payoff>0,FEE+TAX_SETTLE*g.ssp,0.0)
    for n in [1,2,4]:
        entry=g.trade_px+n*tick(g.trade_px)
        g[f'entry_{n}t']=entry
        g[f'pnl_{n}t']=payoff-entry-(FEE+TAX_ENTRY*entry)-settle_cost
    g['pnl']=g['pnl_2t']; g['cost_basis']=g['entry_2t']+FEE+TAX_ENTRY*g['entry_2t']
    g['ret']=g.pnl/g.cost_basis
    return g
if __name__=='__main__':
    args=[(d.strftime('%Y-%m-%d'),k,c,s) for d,k,c,s in zip(cal.date,cal.kind,cal.contract_month,cal.ssp)]
    with ProcessPoolExecutor(os.cpu_count()) as ex: res=[x for x in ex.map(one,args,chunksize=4) if x is not None]
    g=pd.concat(res,ignore_index=True)
    g=add_pnl(g)
    OUT.mkdir(parents=True,exist_ok=True); g.to_parquet(OUT/'step1_trades_IS.parquet',index=False)
    print('days in calendar',len(args),'days with data',g.date.nunique(),'rows',len(g),'filled',g.trade_px.notna().mean().round(3))
