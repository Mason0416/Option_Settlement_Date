"""Step 8 evaluation: apply locked plans A and B to OOS candidates."""
import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'oos'
FEE=0.5; TAX_ENTRY=0.001; TAX_SETTLE=0.00002
def tick(p): return np.select([p<10,p<50,p<500,p<1000],[0.1,0.5,1.0,5.0],10.0)
g=pd.read_csv(OUT/'oos_candidates.csv')
# SJ day, trade exists but quote missing (ask==0): fall back to SJ trade price + model half-spread
SM=pd.read_csv(ROOT/'results'/'spread_model_v2.csv').set_index(['bucket','cp','level']).rel_half_med
fix=(g.src=='no_fill')&(g.sj_close>0)
rh=np.array([SM.get((s,c,-1.0),np.nan) for s,c in zip(g.slot,g.cp)])
g.loc[fix,'entry']=g.sj_close[fix]+np.maximum(rh[fix]*g.sj_close[fix],tick(g.sj_close[fix]))
g.loc[fix,'src']='sj_trade_model'
settle=np.where(g.payoff>0,FEE+TAX_SETTLE*g.ssp,0.0)
g['pnl']=g.payoff-g.entry-(FEE+TAX_ENTRY*g.entry)-settle
# rolling parity thresholds: history = in-sample parity.csv + OOS devs, same slot, previous 50 non-missing
P=pd.read_csv(ROOT/'results'/'step5_parity'/'parity.csv')[['date','slot','dev_med']].rename(columns={'dev_med':'dev'})
O=g.drop_duplicates(['date','slot'])[['date','slot','dev']]
H=pd.concat([P[P.slot.isin(['09:30','10:00'])],O]).dropna().sort_values(['slot','date']).drop_duplicates(['date','slot'])
th=[]
for s,h in H.groupby('slot'):
    v=h.dev.values; d=h.date.values
    for i in range(50,len(v)): th.append((d[i],s,np.quantile(v[i-50:i],0.3),np.quantile(v[i-50:i],0.7)))
TH=pd.DataFrame(th,columns=['date','slot','th_lo','th_hi'])
g=g.merge(TH,on=['date','slot'],how='left')
up=(g.premkt_pct>0)&(g.o2e_pct>0); dn=(g.premkt_pct<0)&(g.o2e_pct<0)
A=g[(g.slot=='09:30')&((up&(g.cp=='C'))|(dn&(g.cp=='P')))].copy()
B=g[((g.slot=='09:30')&up&(g.cp=='C')&(g.dev<=g.th_lo))|((g.slot=='10:00')&dn&(g.cp=='P')&(g.dev>=g.th_hi))].copy()
A['plan']='A'; B['plan']='B'; T=pd.concat([A,B]); T.to_csv(OUT/'oos_trades.csv',index=False)
tt=lambda p: p.mean()/p.std()*np.sqrt(len(p)) if len(p)>2 else np.nan
def st(d,col='pnl'):
    d=d[d[col].notna()].sort_values('date'); p=d[col]; cs=p.cumsum(); n=len(p)
    return dict(n=n,mean=round(p.mean(),1),t=round(tt(p),2),win=round((p>0).mean(),2),total=round(p.sum()),ex5=round(p.sort_values().iloc[:-5].sum()) if n>5 else np.nan,maxdd=round((cs.cummax()-cs).max()) if n else np.nan)
rows=[]
for nm,d in [('A',A),('B',B)]:
    rows.append(dict(plan=nm,part='全部',**st(d)))
    for side in 'CP': rows.append(dict(plan=nm,part='Call' if side=='C' else 'Put',**st(d[d.cp==side])))
    for y in sorted(d.date.str[:4].unique()): rows.append(dict(plan=nm,part=y,**st(d[d.date.str[:4]==y])))
    rows.append(dict(plan=nm,part='全部用FinMind+模型',**st(d,'pnl_fm')))
    rows.append(dict(plan=nm,part='只算Shioaji賣價那幾筆',**st(d[d.src=='sj_ask'])))
S=pd.DataFrame(rows); S.to_csv(OUT/'oos_summary.csv',index=False)
pd.set_option('display.width',200); print(S.to_string(index=False))
for nm,d in [('A',A),('B',B)]: print(nm,'訊號',len(d),'成交',d.pnl.notna().sum(),'未成交',d.pnl.isna().sum(),d.src.value_counts().to_dict())
# plot: IS (rolling sample 2018-05+) + OOS cumulative
I=pd.read_parquet(ROOT/'results'/'step7_cross3'/'trades_fixed.parquet'); I=I[I.level==-1.0]
IA=I[I.slot=='09:30']; IB=pd.concat([I[(I.slot=='09:30')&(I.side=='Call')&I.ok],I[(I.slot=='10:00')&(I.side=='Put')&I.ok]])
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]:
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
fig,axs=plt.subplots(1,2,figsize=(17,6))
for ax,(nm,i,o,col) in zip(axs,[('方案 A：09:30 兩段同向買價內 1%',IA,A,'#2a78d6'),('方案 B：09:30 Call／10:00 Put，兩段同向＋平價符合',IB,B,'#eb6834')]):
    i=i.sort_values('date'); o=o[o.pnl.notna()].sort_values('date')
    ci=i.pnl_real.cumsum(); co=o.pnl.cumsum()+(ci.iloc[-1] if len(ci) else 0)
    ax.plot(pd.to_datetime(i.date),ci,color='#9a9993',lw=1.6,label=f'in-sample  n={len(i)}，每筆 {i.pnl_real.mean():+.1f}，t {tt(i.pnl_real):.2f}')
    ax.plot(pd.to_datetime(o.date),co,color=col,lw=2.2,label=f'out-of-sample  n={len(o)}，每筆 {o.pnl.mean():+.1f}，t {tt(o.pnl):.2f}，總計 {o.pnl.sum():+.0f}')
    ax.axvline(pd.Timestamp('2023-01-01'),color='#52514e',lw=0.8,ls='--'); ax.grid(axis='y',color='#e6e5e1')
    [ax.spines[k].set_visible(False) for k in ['top','right']]; ax.legend(frameon=False,loc='upper left',fontsize=10); ax.set_title(nm,loc='left',fontsize=12); ax.set_ylabel('累積損益（點）')
fig.suptitle('Out-of-sample 驗證（2023-01 ~ 2026-09-18）：虛線右邊是規則鎖定後才看的資料\n成本：Shioaji 真實賣價（無報價時用成交價＋價差模型）＋手續費＋期交稅；價內 1%，持有到結算',fontsize=13)
fig.tight_layout(rect=[0,0,1,0.9]); fig.savefig(OUT/'oos_cum.png',dpi=110)
