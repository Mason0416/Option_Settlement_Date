"""Step 7c: fixed params (rolling 50 settlement days, 30%). Premarket x open-to-entry x parity, Call and Put separately.
Call: pre up & open up & dev <= rolling 30th pct.  Put: pre dn & open dn & dev >= rolling 70th pct. In-sample."""
import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step7_cross3'
SL=['09:30','10:00','10:30','11:00','11:30','12:00']; N=50; Q=0.3
R=pd.read_csv(ROOT/'results'/'step5_parity'/'parity.csv')[['date','slot','dev_med']].sort_values(['slot','date'])
def roll(x):
    v=x.values; lo=np.full(len(v),np.nan); hi=np.full(len(v),np.nan)
    for i in range(N,len(v)): lo[i]=np.quantile(v[i-N:i],Q); hi[i]=np.quantile(v[i-N:i],1-Q)
    return pd.DataFrame({'th_lo':lo,'th_hi':hi},index=x.index)
R=R.join(R.groupby('slot',group_keys=False).dev_med.apply(roll))
g=pd.read_parquet(ROOT/'results'/'step4d_cross'/'trades.parquet').merge(R,on=['date','slot'])
g=g[g.th_lo.notna()]
C=g[(g.grp=='盤前漲・開盤後漲')&(g.cp=='C')].copy(); C['ok']=C.dev_med<=C.th_lo
P=g[(g.grp=='盤前跌・開盤後跌')&(g.cp=='P')].copy(); P['ok']=P.dev_med>=P.th_hi
A=pd.concat([C,P]); A['side']=np.where(A.cp=='C','Call','Put'); A.to_parquet(OUT/'trades_fixed.parquet',index=False)
tt=lambda p: p.mean()/p.std()*np.sqrt(len(p)) if len(p)>2 else np.nan
def st(p):
    p=p.sort_values(); n=len(p)
    return dict(n=n,mean=round(p.mean(),1),t=round(tt(p),2),win=round((p>0).mean(),2),total=round(p.sum()),ex5=round(p.iloc[:-5].sum()) if n>5 else np.nan)
rows=[]
for L,ln in [(-1.0,'價內1%'),(0.0,'價平')]:
  for side in ['Call','Put']:
    for s in SL:
      d=A[(A.level==L)&(A.side==side)&(A.slot==s)]
      for k,c in [('兩段同向（全部）',d.ok|~d.ok),('＋平價符合',d.ok),('平價不符合',~d.ok)]:
        rows.append(dict(level=ln,side=side,slot=s,filt=k,**st(d[c].pnl_real)))
T=pd.DataFrame(rows); T.to_csv(OUT/'fixed_summary.csv',index=False)
pd.set_option('display.width',220)
print('樣本起點',A.date.min())
print(T[T.level=='價內1%'].to_string(index=False))
print(T[(T.level=='價平')&(T.slot.isin(['09:30','10:00','10:30']))].to_string(index=False))
# yearly for 09:30 / 10:00 ITM1
for s in ['09:30','10:00']:
    d=A[(A.level==-1.0)&(A.slot==s)&A.ok]; print(s,'符合 逐年', d.assign(y=d.date.str[:4]).groupby(['side','y']).pnl_real.sum().round().astype(int).unstack(0).to_dict())
# plot
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
fig,axs=plt.subplots(2,2,figsize=(16,10))
for r,s in enumerate(['09:30','10:00']):
  for c,side in enumerate(['Call','Put']):
    ax=axs[r,c]; d=A[(A.level==-1.0)&(A.slot==s)&(A.side==side)].sort_values('date')
    for nm,x,col,lw in [('兩段同向（全部）',d,'#9a9993',1.3),('＋平價符合',d[d.ok],'#2a78d6',2.2),('平價不符合',d[~d.ok],'#e34948',1.5)]:
        p=x.pnl_real; ax.plot(pd.to_datetime(x.date),p.cumsum(),color=col,lw=lw,label=f'{nm}  n={len(p)}，每筆 {p.mean():+.1f}，t {tt(p):.2f}，總計 {p.sum():+.0f}')
    ax.axhline(0,color='#52514e',lw=0.8); ax.legend(fontsize=9,frameon=False,loc='upper left'); ax.grid(axis='y',color='#e6e5e1')
    [ax.spines[k].set_visible(False) for k in ['top','right']]; ax.set_ylabel('累積損益（點）')
    cond='盤前漲＋開盤後漲，平價符合 = 偏離 ≤ 過去 50 日第 30 百分位' if side=='Call' else '盤前跌＋開盤後跌，平價符合 = 偏離 ≥ 過去 50 日第 70 百分位'
    ax.set_title(f'{s} 買價內 1% {side}\n{cond}',loc='left',fontsize=11)
fig.suptitle('盤前 × 開盤後 × 平價（參數固定：滾動 50 個結算日、30%）：Call／Put 分開（in-sample 2018-05~2022-12）',fontsize=13)
fig.tight_layout(rect=[0,0,1,0.95]); fig.savefig(OUT/'cum_fixed.png',dpi=110)
