"""Step 6: abnormal basis = (near-month futures last trade before T - TAIEX last print before T) - prev-day 13:30 basis.
Split Call/Put rules, both directions. In-sample. Slots 09:30-12:00."""
import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
ROOT=Path(__file__).resolve().parent.parent; D=ROOT/'data'; OUT=ROOT/'results'/'step6_basis'; OUT.mkdir(parents=True,exist_ok=True)
SL=['09:30','10:00','10:30','11:00','11:30','12:00']
B=pd.read_csv(D/'basis_prev.csv',dtype={'contract':str}).set_index('date')
g=pd.read_parquet(ROOT/'results'/'step4_timefilter'/'trades.parquet')
rows=[]
for ds in sorted(g.date.unique()):
    if ds not in B.index: continue
    f=pd.read_parquet(D/'finmind'/'fut'/f'{ds}.parquet'); f['t']=pd.to_datetime(f.date); f['contract_date']=f.contract_date.astype(str).str.strip()
    f=f[(f.contract_date==B.loc[ds,'contract'])&(f.t>=pd.Timestamp(f'{ds} 08:45'))&(f.t<=pd.Timestamp(f'{ds} 13:45'))].reset_index(drop=True)
    x=pd.read_parquet(D/'finmind'/'taiex5s'/f'{ds}.parquet'); x['t']=pd.to_datetime(x.date); x=x[x.t>pd.Timestamp(f'{ds} 09:00:00')].sort_values('t')
    for s in SL:
        T=pd.Timestamp(f'{ds} {s}:00'); fs=f[f.t<T]; xs=x[x.t<T]
        if fs.empty or xs.empty: continue
        fut=fs.price.iloc[-1]; spot=xs.TAIEX.iloc[-1]
        rows.append((ds,s,fut,spot,fut-spot,B.loc[ds,'basis_prev']))
M=pd.DataFrame(rows,columns=['date','slot','fut','spot','basis','basis_prev'])
M['abn']=M.basis-M.basis_prev; M['abn_pct']=M.abn/M.spot*100; M['pct']=M.groupby('slot').abn_pct.rank(pct=True)
M.to_csv(OUT/'basis.csv',index=False)
m=g.merge(M[['date','slot','abn','abn_pct','pct']],on=['date','slot']); m['move']=(m.ssp/m.spot-1)*100
tt=lambda p: p.mean()/p.std()*np.sqrt(len(p))
print('== 異常基差分布（點）'); print(M.abn.describe().round(1).to_string())
print('== 異常基差對 進場→結算 大盤漲跌 的相關')
u=m.drop_duplicates(['date','slot'])
for s,d in u.groupby('slot'):
    c=d[['abn_pct','move']].corr().iloc[0,1]; print(s,'corr',round(c,3),'t≈',round(c*np.sqrt(len(d)-2)/np.sqrt(1-c*c),2))
def st(p):
    p=p.sort_values(); n=len(p); return dict(n=n,mean=round(p.mean(),1),t=round(tt(p),2),total=round(p.sum()),ex5=round(p.iloc[:-5].sum()))
rows=[]
for L,ln in [(-1.0,'價內1%'),(0.0,'價平')]:
  for s in SL:
    for cp in 'CP':
      y=m[(m.level==L)&(m.slot==s)&(m.cp==cp)]
      conds={'不過濾':y.pct>=0,'基差>0':y.abn>0,'基差<0':y.abn<0,'最高30%':y.pct>=0.7,'最低30%':y.pct<=0.3,'最高20%':y.pct>=0.8,'最低20%':y.pct<=0.2}
      for k,c in conds.items(): rows.append(dict(level=ln,slot=s,cp='Call' if cp=='C' else 'Put',filt=k,**st(y[c].pnl_real)))
T=pd.DataFrame(rows); T.to_csv(OUT/'split.csv',index=False)
F=['不過濾','基差>0','最高30%','最高20%','基差<0','最低30%','最低20%']
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
LAB={'不過濾':'不過濾（每天買）','基差>0':'異常基差 > 0（期貨偏貴）','最高30%':'異常基差最高 30%','最高20%':'異常基差最高 20%','基差<0':'異常基差 < 0（期貨偏便宜）','最低30%':'異常基差最低 30%','最低20%':'異常基差最低 20%'}
cmap=LinearSegmentedColormap.from_list('div',['#e34948','#f0efec','#2a78d6'])
fig,axs=plt.subplots(2,2,figsize=(17,11),gridspec_kw={'wspace':0.45,'hspace':0.25})
for ax,(lv,cp) in zip(axs.flat,[('價內1%','Call'),('價內1%','Put'),('價平','Call'),('價平','Put')]):
    q=T[(T.level==lv)&(T.cp==cp)]
    mm=q.pivot(index='filt',columns='slot',values='mean').reindex(index=F,columns=SL); t=q.pivot(index='filt',columns='slot',values='t').reindex(index=F,columns=SL)
    im=ax.imshow(mm.values,cmap=cmap,norm=TwoSlopeNorm(0,-15,15),aspect='auto')
    for i in range(len(F)):
        for j in range(len(SL)):
            ax.text(j,i,f'{mm.values[i,j]:+.1f}\n(t {t.values[i,j]:.1f})',ha='center',va='center',fontsize=8.5,fontweight='bold' if abs(t.values[i,j])>=2 else 'normal')
    ax.axhline(3.5,color='#52514e',lw=1)
    ax.set_xticks(range(len(SL))); ax.set_xticklabels(SL); ax.set_yticks(range(len(F))); ax.set_yticklabels([LAB[f] for f in F],fontsize=9)
    ax.set_title(f'{lv} 買 {cp}',loc='left',fontsize=12)
    for s_ in ax.spines.values(): s_.set_visible(False)
cb=fig.colorbar(im,ax=axs,shrink=0.5,pad=0.02); cb.set_label('每筆平均損益（點）')
fig.suptitle('異常基差濾網：（期貨 − 現貨）− 前一日 13:30 基差，進場前計算\nin-sample 2017-05~2022-12；每格 = 每筆平均損益與 t；藍賺紅賠；粗體 = |t| ≥ 2',fontsize=13)
fig.savefig(OUT/'split_heatmap.png',dpi=115,bbox_inches='tight')
for ln in ['價內1%','價平']:
  for cp in ['Call','Put']:
    q=T[(T.level==ln)&(T.cp==cp)]
    print('==',ln,cp); print(q.pivot(index='filt',columns='slot',values='mean').reindex(F).to_string()); print(q.pivot(index='filt',columns='slot',values='t').reindex(F).to_string())
