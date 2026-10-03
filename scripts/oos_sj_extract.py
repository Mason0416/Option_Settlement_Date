"""OOS: from Shioaji tick files (with bid/ask), take the first tick in [T, T+5min) per (strike, cp) for T in 09:30, 10:00.
Output results/oos/sj_entry_ticks.csv. Reads only; no PnL."""
import pandas as pd, os, sys
D='data/shioaji/opt'; OUT='results/oos/sj_entry_ticks.csv'
files=sorted(f for f in os.listdir(D) if '2023-01-01'<=f[:10]<='2026-09-18')
rows=[]
for f in files:
    ds=f[:10]; d=pd.read_parquet(f'{D}/{f}',columns=['ts','close','bid_price','ask_price','strike','cp'])
    d['t']=pd.to_datetime(d.ts); d=d.reset_index(drop=True); d['seq']=range(len(d))
    for s in ['09:30','10:00']:
        T=pd.Timestamp(f'{ds} {s}:00'); w=d[(d.t>=T)&(d.t<T+pd.Timedelta('5min'))].sort_values(['t','seq'],kind='stable')
        g=w.groupby(['strike','cp']).head(1)
        for r in g.itertuples(): rows.append((ds,s,r.strike,r.cp,r.t,r.close,r.bid_price,r.ask_price))
pd.DataFrame(rows,columns=['date','slot','strike','cp','t','close','bid','ask']).to_csv(OUT,index=False)
print(len(files),'files',len(rows),'rows')
