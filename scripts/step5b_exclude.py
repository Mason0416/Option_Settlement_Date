"""Step 5b: parity as an exclusion filter. exp = how expensive the side we buy is (Call: dev, Put: -dev, in %).
Skip trade if exp > threshold. Applied to: two-segment rule, premarket-only rule, unconditional. In-sample, ITM1%."""
import pandas as pd, numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step5_parity'
R=pd.read_csv(OUT/'parity.csv')[['date','slot','dev_med']]
g=pd.read_parquet(ROOT/'results'/'step4d_cross'/'trades.parquet'); g=g[g.level==-1.0].merge(R,on=['date','slot'],how='left')
g['exp']=np.where(g.cp=='C',g.dev_med,-g.dev_med)
TH=[None,0.10,0.08,0.06,0.04,0.02,0.0,-0.02]
def st(p):
    p=p.sort_values(); n=len(p)
    return dict(n=n,mean=p.mean(),t=p.mean()/p.std()*np.sqrt(n),win=(p>0).mean(),total=p.sum(),ex5=p.iloc[:-5].sum())
rows=[]
for s in ['09:30','10:00']:
    x=g[g.slot==s]
    bases={'兩段同向':x[((x.grp=='盤前漲・開盤後漲')&(x.cp=='C'))|((x.grp=='盤前跌・開盤後跌')&(x.cp=='P'))],
           '只看盤前':x[((x.pm=='盤前漲')&(x.cp=='C'))|((x.pm=='盤前跌')&(x.cp=='P'))],
           '每天買Call':x[x.cp=='C'],'每天買Put':x[x.cp=='P']}
    for b,d in bases.items():
        for th in TH:
            k=d if th is None else d[d.exp.notna()&(d.exp<=th)]
            rows.append(dict(slot=s,base=b,th='不過濾' if th is None else f'貴>{th:+.2f}%不買',**st(k.pnl_real)))
T=pd.DataFrame(rows); T.to_csv(OUT/'exclude.csv',index=False)
pd.set_option('display.width',200); print(T.round(2).to_string(index=False))
print('exp 分位數', g[g.slot=='09:30'].exp.quantile([.5,.6,.7,.8,.9]).round(3).to_dict())
