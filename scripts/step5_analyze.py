import pandas as pd, numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step5_parity'
R=pd.read_csv(OUT/'parity.csv')
g=pd.read_parquet(ROOT/'results'/'step4_timefilter'/'trades.parquet')
def tt(x): x=x.dropna(); return x.mean()/x.std()*np.sqrt(len(x)) if len(x)>2 else np.nan
print('== 相關：dev 對 進場→結算 漲跌（每個時間）')
for s,d in R.groupby('slot'):
    b=np.polyfit(d.dev_med,d.move,1)[0]; c=d[['dev_med','move']].corr().iloc[0,1]
    print(s,'n',len(d),'corr',round(c,3),'t≈',round(c*np.sqrt(len(d)-2)/np.sqrt(1-c*c),2),'slope',round(b,2))
R['q']=R.groupby('slot').dev_med.transform(lambda x: pd.qcut(x,5,labels=False))+1
Q=R.groupby('q').agg(n=('move','size'),dev=('dev_med','mean'),move=('move','mean'),move_t=('move',tt)).round(3)
print('== 全部時間合併，依 dev 五分位（各時間各自分位）'); print(Q.to_string())
m=g.merge(R[['date','slot','dev_med','q']],on=['date','slot'])
for L,nm in [(-1.0,'價內1%'),(0.0,'價平')]:
    P=m[m.level==L].groupby(['q','cp']).pnl_real.agg(['size','mean',tt]).round(2).unstack('cp')
    print('==',nm,'每筆損益 by 五分位'); print(P.to_string())
# 規則：dev 最低 20% 買 Call（Call 相對便宜），最高 20% 買 Put
for L in [-1.0,0.0]:
  for s in ['09:30','10:00','11:00','12:00']:
    x=m[(m.level==L)&(m.slot==s)]
    a=pd.concat([x[(x.q==1)&(x.cp=='C')],x[(x.q==5)&(x.cp=='P')]]).pnl_real
    b=pd.concat([x[(x.q==1)&(x.cp=='P')],x[(x.q==5)&(x.cp=='C')]]).pnl_real
    print(L,s,'買便宜那邊 n',len(a),round(a.mean(),1),'t',round(tt(a),2),'| 買貴那邊',round(b.mean(),1),'t',round(tt(b),2))
