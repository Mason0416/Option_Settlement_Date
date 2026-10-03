"""Step 7: premarket x open-to-entry x parity. Two-segment same-direction days; Call on up-up days, Put on dn-dn days;
parity filter: side we buy is cheap (Call: dev low; Put: dev high). In-sample. Slots 09:30-12:00."""
import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step7_cross3'; OUT.mkdir(parents=True,exist_ok=True)
SL=['09:30','10:00','10:30','11:00','11:30','12:00']
R=pd.read_csv(ROOT/'results'/'step5_parity'/'parity.csv')[['date','slot','dev_med']]
R['pct']=R.groupby('slot').dev_med.rank(pct=True)
g=pd.read_parquet(ROOT/'results'/'step4d_cross'/'trades.parquet').merge(R,on=['date','slot'])
g=g[((g.grp=='盤前漲・開盤後漲')&(g.cp=='C'))|((g.grp=='盤前跌・開盤後跌')&(g.cp=='P'))].copy()
g['cheap_pct']=np.where(g.cp=='C',1-g.pct,g.pct)   # 1 = our side cheapest
g['cheap_sign']=np.where(g.cp=='C',g.dev_med<0,g.dev_med>0)
g.to_parquet(OUT/'trades.parquet',index=False)
tt=lambda p: p.mean()/p.std()*np.sqrt(len(p)) if len(p)>2 else np.nan
def st(p):
    p=p.sort_values(); n=len(p); return dict(n=n,mean=p.mean(),t=tt(p),win=(p>0).mean(),total=p.sum(),ex5=p.iloc[:-5].sum() if n>5 else np.nan)
F={'兩段同向（不加平價）':lambda d:d.index==d.index,'＋買的那邊便宜（正負號）':lambda d:d.cheap_sign,
   '＋便宜 30%':lambda d:d.cheap_pct>=0.7,'＋便宜 20%':lambda d:d.cheap_pct>=0.8,'對照：買的那邊貴（正負號）':lambda d:~d.cheap_sign}
rows=[]
for L,ln in [(-1.0,'價內1%'),(0.0,'價平')]:
  for s in SL:
    for side,sel in [('合計',None),('Call',('C')),('Put',('P'))]:
      d=g[(g.level==L)&(g.slot==s)]; d=d if sel is None else d[d.cp==sel]
      for k,f in F.items(): rows.append(dict(level=ln,slot=s,side=side,filt=k,**st(d[f(d)].pnl_real)))
T=pd.DataFrame(rows); T.to_csv(OUT/'summary.csv',index=False)
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
cmap=LinearSegmentedColormap.from_list('div',['#e34948','#f0efec','#2a78d6']); FL=list(F)
fig,axs=plt.subplots(2,1,figsize=(13,10),gridspec_kw={'hspace':0.3})
for ax,ln in zip(axs,['價內1%','價平']):
    q=T[(T.level==ln)&(T.side=='合計')]
    m=q.pivot(index='filt',columns='slot',values='mean').reindex(index=FL,columns=SL)
    t=q.pivot(index='filt',columns='slot',values='t').reindex(index=FL,columns=SL); n=q.pivot(index='filt',columns='slot',values='n').reindex(index=FL,columns=SL)
    im=ax.imshow(m.values,cmap=cmap,norm=TwoSlopeNorm(0,-30,30),aspect='auto')
    for i in range(len(FL)):
        for j in range(len(SL)):
            ax.text(j,i,f'{m.values[i,j]:+.1f}\n(t {t.values[i,j]:.1f}, n {n.values[i,j]:.0f})',ha='center',va='center',fontsize=8.5,fontweight='bold' if abs(t.values[i,j])>=2 else 'normal')
    ax.axhline(3.5,color='#52514e',lw=1)
    ax.set_xticks(range(len(SL))); ax.set_xticklabels(SL); ax.set_yticks(range(len(FL))); ax.set_yticklabels(FL,fontsize=10)
    ax.set_title(f'{ln}：兩段同向（盤前漲＋開盤後漲買 Call、兩段都跌買 Put）× 平價',loc='left',fontsize=12)
    for s_ in ax.spines.values(): s_.set_visible(False)
cb=fig.colorbar(im,ax=axs,shrink=0.5,pad=0.02); cb.set_label('每筆平均損益（點）')
fig.suptitle('盤前 × 開盤後 × 平價（in-sample 2017-05~2022-12；Call、Put 合計）\n每格 = 每筆平均損益（t、筆數）；粗體 = |t| ≥ 2；成本含真實半價差、手續費、期交稅',fontsize=13)
fig.savefig(OUT/'heatmap_cross3.png',dpi=115,bbox_inches='tight')
pd.set_option('display.width',220)
for ln in ['價內1%','價平']:
    print('==',ln); q=T[(T.level==ln)]
    print(q[q.side=='合計'].pivot(index='filt',columns='slot',values='mean').reindex(FL).round(1).to_string())
    print(q[q.side=='合計'].pivot(index='filt',columns='slot',values='t').reindex(FL).round(2).to_string())
q=T[(T.level=='價內1%')&(T.slot.isin(['09:30','10:00']))]
print(q.round(2).to_string(index=False))
