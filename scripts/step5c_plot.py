import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step5_parity'
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
T=pd.read_csv(OUT/'split.csv'); F=['不過濾','正負號','極端30%','極端20%']; SL=['09:30','10:00','10:30','11:00','11:30','12:00']
LAB={'Call':{'不過濾':'不過濾（每天買）','正負號':'隱含指數 < 現貨','極端30%':'偏離最低 30%','極端20%':'偏離最低 20%'},
     'Put':{'不過濾':'不過濾（每天買）','正負號':'隱含指數 > 現貨','極端30%':'偏離最高 30%','極端20%':'偏離最高 20%'}}
cmap=LinearSegmentedColormap.from_list('div',['#e34948','#f0efec','#2a78d6'])
fig,axs=plt.subplots(2,2,figsize=(17,8.5),gridspec_kw={'wspace':0.38,'hspace':0.3})
for ax,(lv,cp) in zip(axs.flat,[('價內1%','Call'),('價內1%','Put'),('價平','Call'),('價平','Put')]):
    q=T[(T.level==lv)&(T.cp==cp)]
    m=q.pivot(index='filt',columns='slot',values='mean').reindex(index=F,columns=SL); t=q.pivot(index='filt',columns='slot',values='t').reindex(index=F,columns=SL)
    n=q.pivot(index='filt',columns='slot',values='n').reindex(index=F,columns=SL)
    im=ax.imshow(m.values,cmap=cmap,norm=TwoSlopeNorm(0,-15,15),aspect='auto')
    for i in range(len(F)):
        for j in range(len(SL)):
            ax.text(j,i,f'{m.values[i,j]:+.1f}\n(t {t.values[i,j]:.1f})',ha='center',va='center',fontsize=8.5,fontweight='bold' if abs(t.values[i,j])>=2 else 'normal')
    ax.set_xticks(range(len(SL))); ax.set_xticklabels(SL); ax.set_yticks(range(len(F))); ax.set_yticklabels([LAB[cp][f] for f in F],fontsize=9)
    ax.set_title(f'{lv} {cp}：{"算出來偏低才買" if cp=="Call" else "算出來偏高才買"}',loc='left',fontsize=12)
    for s_ in ax.spines.values(): s_.set_visible(False)
cb=fig.colorbar(im,ax=axs,shrink=0.6,pad=0.02); cb.set_label('每筆平均損益（點）')
fig.suptitle('買賣權平價拆成兩條規則：Call 規則（隱含指數偏低才買 Call）、Put 規則（偏高才買 Put）\nin-sample 2017-05~2022-12；每格 = 每筆平均損益與 t；藍賺紅賠；成本含真實半價差、手續費、期交稅',fontsize=12.5)
fig.savefig(OUT/'split_heatmap.png',dpi=120,bbox_inches='tight')
