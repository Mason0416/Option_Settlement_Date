"""Step 2c: add night-session open (first trade of same contract at/after prev_date 15:00:00, before D 08:45) to trades_night.csv.
Splits gap into: night-open gap (prev close 13:45 -> night open 15:00), night intraday (15:00 -> night close ~05:00), premarket (05:00 -> 08:45)."""
import pandas as pd, numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; FUT=ROOT/'data'/'finmind'/'fut'
n=pd.read_csv(ROOT/'results'/'step2_night'/'trades_night.csv',dtype={'fut_contract':str})
cache={}
def load(m):
    if m not in cache:
        f=FUT/f'{m}.parquet'; cache[m]=pd.read_parquet(f,columns=['contract_date','date','price','settle_date']) if f.exists() else None
    return cache[m]
out=[]
for r in n.itertuples():
    parts=[load(m) for m in sorted({r.prev_date[:7],r.date[:7]})]; parts=[p[p.settle_date==r.date] for p in parts if p is not None]
    if not parts: out.append((r.date,np.nan,pd.NaT)); continue
    f=pd.concat(parts,ignore_index=True); f['c']=f.contract_date.astype(str).str.strip(); f['t']=pd.to_datetime(f.date)
    w=f[(f.c==str(r.fut_contract).strip())&(f.t>=pd.Timestamp(f'{r.prev_date} 15:00:00'))&(f.t<pd.Timestamp(f'{r.date} 08:45:00'))].sort_values('t',kind='stable')
    out.append((r.date,float(w.price.iloc[0]) if len(w) else np.nan,w.t.iloc[0] if len(w) else pd.NaT))
o=pd.DataFrame(out,columns=['date','F_night_open','t_night_open'])
o.to_csv(ROOT/'results'/'step2_night'/'night_open.csv',index=False); print(len(o),o.F_night_open.notna().sum()); print(o.head(3)); print(pd.to_datetime(o.t_night_open).dt.strftime('%H:%M').value_counts().head())
