"""Result D across entry times: 3 premarket segments x post-open direction (08:45 -> entry), Call/Put, 09:00-13:00, realistic costs."""
import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step2_night'
s=pd.read_csv(OUT/'trades_3seg.csv')[['date','s1','s2','s3']]; s=s[(s.s1!=0)&(s.s2!=0)&(s.s3!=0)]
lab=lambda v:'漲' if v>0 else '跌'
s['k']=s.s1.map(lab)+s.s2.map(lab)+s.s3.map(lab)
g=pd.read_parquet(ROOT/'results'/'step4c_open_to_entry'/'trades.parquet'); g=g[g.level==-1.0].merge(s[['date','k']],on='date')
g['o']=g.o2e_pct.map(lab); g['key']=g.k+g.o
SL=['09:00','09:30','10:00','10:30','11:00','11:30','12:00','12:30','13:00']
# order: ③④ same dir first
keys=[a+b+c+d for c,d in [('漲','漲'),('跌','跌'),('漲','跌'),('跌','漲')] for a in '漲跌' for b in '漲跌']
tt=lambda x:x.mean()/x.std()*np.sqrt(len(x)) if len(x)>2 else np.nan
S=g.groupby(['cp','key','slot']).pnl_real.agg(n='size',mean='mean',t=tt).reset_index(); S.to_csv(OUT/'combo3_x_open_time.csv',index=False,encoding='utf-8-sig')
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]:
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
cmap=LinearSegmentedColormap.from_list('div',['#e34948','#f0efec','#2a78d6'])
fig,axs=plt.subplots(1,2,figsize=(20,11),gridspec_kw={'wspace':0.25})
for ax,(cp,nm) in zip(axs,[('C','買價內 1% Call'),('P','買價內 1% Put')]):
    q=S[S.cp==cp]; m=q.pivot(index='key',columns='slot',values='mean').reindex(index=keys,columns=SL)
    t=q.pivot(index='key',columns='slot',values='t').reindex(index=keys,columns=SL); n=q.pivot(index='key',columns='slot',values='n').reindex(index=keys,columns=SL)
    im=ax.imshow(m.values,cmap=cmap,norm=TwoSlopeNorm(0,-40,40),aspect='auto')
    for i in range(len(keys)):
        for j in range(len(SL)):
            v=m.values[i,j]
            if np.isnan(v): continue
            ax.text(j,i,f'{v:+.0f}'+('*' if abs(t.values[i,j])>=2 else '')+f'\n({n.values[i,j]:.0f})',ha='center',va='center',fontsize=7.5,fontweight='bold' if abs(t.values[i,j])>=2 else 'normal')
    for y in [3.5,7.5,11.5]: ax.axhline(y,color='#52514e',lw=1.2)
    ax.set_xticks(range(len(SL))); ax.set_xticklabels(SL); ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([f'{k[0]}／{k[1]}／{k[2]}／{k[3]}' for k in keys],fontsize=9); ax.set_xlabel('進場時間')
    ax.set_title(nm,loc='left',fontsize=13)
    for s_ in ax.spines.values(): s_.set_visible(False)
axs[0].set_ylabel('① 夜盤開盤／② 夜盤盤中／③ 盤前／④ 開盤後（08:45→進場前）')
for y,txt in [(1.5,'③漲 ④漲'),(5.5,'③跌 ④跌'),(9.5,'③漲 ④跌'),(13.5,'③跌 ④漲')]: axs[1].text(len(SL)-0.3,y,txt,va='center',fontsize=10)
cb=fig.colorbar(im,ax=axs,shrink=0.5,pad=0.04); cb.set_label('每筆平均損益（點）')
fig.suptitle('三段開盤前方向 × 開盤後方向 × 進場時間（in-sample 2017-05~2022-12，價內 1%，真實價差模型）\n每格 = 每筆平均損益（括號 = 天數）；* 與粗體 = |t| ≥ 2；④ 開盤後是 08:45 期貨開盤 → 該進場時間前最後一筆',fontsize=13)
fig.savefig(OUT/'combo3_x_open_time.png',dpi=110,bbox_inches='tight')
