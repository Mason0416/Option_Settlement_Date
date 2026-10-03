import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step4b_premkt_time'
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
S=pd.read_csv(OUT/'summary.csv')
SLOTS=['09:00','09:30','10:00','10:30','11:00','11:30','12:00','12:30','13:00']
LV=[-1.0,-0.5,0.0,0.5,1.0,1.5,2.0,3.0]
NAME={-1.0:'價內 1%',-0.5:'價內 0.5%',0.0:'價平',0.5:'價外 0.5%',1.0:'價外 1%',1.5:'價外 1.5%',2.0:'價外 2%',3.0:'價外 3%'}
cmap=LinearSegmentedColormap.from_list('div',['#e34948','#f0efec','#2a78d6'])
fig,axs=plt.subplots(2,2,figsize=(16,11))
panels=[('盤前漲','C','盤前漲 → 買 Call（順勢）'),('盤前漲','P','盤前漲 → 買 Put（逆勢）'),('盤前跌','P','盤前跌 → 買 Put（順勢）'),('盤前跌','C','盤前跌 → 買 Call（逆勢）')]
for ax,(g,cp,title) in zip(axs.flat,panels):
    m=S[(S.grp==g)&(S.cp==cp)].pivot(index='level',columns='slot',values='mean').reindex(index=LV,columns=SLOTS)
    tt=S[(S.grp==g)&(S.cp==cp)].pivot(index='level',columns='slot',values='t').reindex(index=LV,columns=SLOTS)
    im=ax.imshow(m.values,cmap=cmap,norm=TwoSlopeNorm(0,-15,15),aspect='auto')
    for i in range(len(LV)):
        for j in range(len(SLOTS)):
            v=m.values[i,j]; t=tt.values[i,j]
            if np.isnan(v): continue
            ax.text(j,i,f'{v:+.1f}'+('*' if t>=2 else ''),ha='center',va='center',fontsize=9,color='#0b0b0b',fontweight='bold' if t>=2 else 'normal')
    ax.set_xticks(range(len(SLOTS))); ax.set_xticklabels(SLOTS,fontsize=9); ax.set_yticks(range(len(LV))); ax.set_yticklabels([NAME[l] for l in LV],fontsize=9)
    ax.set_title(title,fontsize=13,loc='left'); ax.set_xlabel('進場時間',fontsize=9)
    for s in ax.spines.values(): s.set_visible(False)
cb=fig.colorbar(im,ax=axs,shrink=0.6,pad=0.02); cb.set_label('每筆平均損益（點，1 點 = 50 元）')
fig.suptitle('結算日買選擇權持有到結算：依「盤前段」方向分組的每筆平均損益（in-sample 2017-05~2022-12）\n藍 = 賺、紅 = 虧；* = t ≥ 2；成本含真實半價差、手續費、期交稅；盤前段 = 夜盤收盤 → 08:45 期貨開盤',fontsize=13)
fig.savefig(OUT/'heatmap_premkt.png',dpi=120,bbox_inches='tight'); plt.close(fig)
# locked rule: 09:30, ITM1%, momentum
g=pd.read_parquet(OUT/'trades.parquet')
c=g[(g.slot=='09:30')&(g.level==-1.0)&(((g.grp=='盤前漲')&(g.cp=='C'))|((g.grp=='盤前跌')&(g.cp=='P')))].sort_values('date')
c['side']=np.where(c.cp=='C','Call','Put')
fig,(a1,a2)=plt.subplots(1,2,figsize=(16,5.5),gridspec_kw={'width_ratios':[2.2,1]})
a1.plot(pd.to_datetime(c.date),c.pnl_real.cumsum(),color='#2a78d6',lw=2,label=f'合計 n={len(c)}，總計 {c.pnl_real.sum():+.0f} 點')
for side,col in [('Call','#1baf7a'),('Put','#eb6834')]:
    d=c[c.side==side]; a1.plot(pd.to_datetime(d.date),d.pnl_real.cumsum(),color=col,lw=1.2,label=f'其中 {side}（盤前{"漲" if side=="Call" else "跌"}）n={len(d)}，{d.pnl_real.sum():+.0f} 點')
a1.axhline(0,color='#52514e',lw=0.8); a1.legend(frameon=False); a1.grid(axis='y',color='#e6e5e1'); [a1.spines[k].set_visible(False) for k in ['top','right']]
a1.set_ylabel('累積損益（點）'); a1.set_title('規則：09:30 依盤前方向買價內 1%（盤前漲買 Call、盤前跌買 Put），持有到結算',loc='left',fontsize=12)
y=c.assign(y=c.date.str[:4]).groupby('y').pnl_real.sum()
a2.bar(y.index,y.values,color=['#2a78d6' if v>=0 else '#e34948' for v in y.values],width=0.6)
for i,v in enumerate(y.values): a2.text(i,v,f'{v:+.0f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=9)
a2.axhline(0,color='#52514e',lw=0.8); [a2.spines[k].set_visible(False) for k in ['top','right']]; a2.set_title('各年總損益（點）',loc='left',fontsize=12)
fig.tight_layout(); fig.savefig(OUT/'rule_0930_itm1.png',dpi=120); plt.close(fig)
print(y)
