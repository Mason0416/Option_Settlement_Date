import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
OUT=Path(__file__).resolve().parent.parent/'results'/'step1'
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for _f in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(_f); plt.rcParams['font.family']=[fm.FontProperties(fname=_f).get_name()]; plt.rcParams['axes.unicode_minus']=False
POS,NEG,INK,MUTED,GRID='#2a78d6','#e34948','#0b0b0b','#52514e','#e6e5e1'
g=pd.read_parquet(OUT/'step1_trades_IS.parquet').dropna(subset=['trade_px'])
agg=g.groupby(['cp','level','slot']).agg(n=('pnl','size'),total=('pnl','sum'),mean=('pnl','mean'),median=('pnl','median'),
    std=('pnl','std'),win=('pnl',lambda x:(x>0).mean()),mean_1t=('pnl_1t','mean'),mean_4t=('pnl_4t','mean'),
    avg_prem=('entry_2t','mean'),ret=('ret','mean')).reset_index()
agg['t']=agg['mean']/agg['std']*np.sqrt(agg.n)
agg.to_csv(OUT/'step1_summary_IS.csv',index=False)
LBL={-1.0:'價內 1%',-0.5:'價內 0.5%',0.0:'價平',0.5:'價外 0.5%',1.0:'價外 1%',1.5:'價外 1.5%',2.0:'價外 2%',3.0:'價外 3%'}
slots=sorted(g.slot.unique()); x=np.arange(len(slots))
for cp,name in [('C','Call'),('P','Put')]:
    fig,axs=plt.subplots(4,2,figsize=(15,16),sharex=True)
    for ax,L in zip(axs.flat,sorted(LBL)):
        a=agg[(agg.cp==cp)&(agg.level==L)].set_index('slot').reindex(slots)
        tot=a.total.values
        ax.bar(x,tot,width=0.8,color=[POS if v>=0 else NEG for v in np.nan_to_num(tot)],edgecolor='white',linewidth=0.5)
        ax.axhline(0,color=MUTED,lw=0.8)
        ax.set_title(f'{name} {LBL[L]}   (平均 {np.nansum(tot)/max(1,a.n.sum()):+.2f} 點/筆, 勝率 {np.nansum(a.win*a.n)/max(1,a.n.sum()):.0%})',fontsize=11,color=INK,loc='left')
        best=np.nanargmax(tot); ax.annotate(f'最佳 {slots[best]}\n{tot[best]:+.0f}點',(best,tot[best]),fontsize=8,color=INK,ha='center',
            xytext=(0,6 if tot[best]>=0 else -22),textcoords='offset points')
        ax.grid(axis='y',color=GRID,lw=0.6); ax.set_axisbelow(True)
        for s in ['top','right']: ax.spines[s].set_visible(False)
        ax.tick_params(colors=MUTED,labelsize=8); ax.set_ylabel('所有結算日加總損益 (點)',fontsize=8,color=MUTED)
    for ax in axs[-1]: ax.set_xticks(x[::3]); ax.set_xticklabels(slots[::3],rotation=45)
    fig.suptitle(f'買 {name} 持有到結算：各進場時間的損益加總（in-sample 2017-05 ~ 2022-12，{g.date.nunique()} 個結算日；08:45–09:00 價外程度用台指期−前日基差估計）\n'
                 f'每根柱子 = 所有結算日在該時間進場的損益加總；1 點 = 50 元；成本：滑價 2 tick + 手續費 25 元 + 期交稅',fontsize=12,color=INK)
    fig.tight_layout(rect=[0,0,1,0.95]); fig.savefig(OUT/f'step1_{name}.png',dpi=110); plt.close(fig)
# overview: mean pnl heatmap-ish table of best cells
top=agg[agg.n>=100].sort_values('t',ascending=False).head(15)
print(top[['cp','level','slot','n','total','mean','median','win','t','mean_1t','mean_4t','avg_prem']].round(2).to_string(index=False))
print('\nworst');print(agg[agg.n>=100].sort_values('t').head(5)[['cp','level','slot','n','mean','win','t']].round(2).to_string(index=False))
print('\nper level overall mean (all slots):'); print(g.groupby(['cp','level']).pnl.agg(['size','mean','median']).round(2).unstack(0).to_string())
