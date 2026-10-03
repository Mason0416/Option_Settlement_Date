import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step5_parity'
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
R=pd.read_csv(OUT/'parity.csv'); R['q']=R.groupby('slot').dev_med.transform(lambda x: pd.qcut(x,5,labels=False))+1
g=pd.read_parquet(ROOT/'results'/'step4_timefilter'/'trades.parquet')
m=g[g.level==-1.0].merge(R[['date','slot','dev_med','q']],on=['date','slot'])
tt=lambda x:x.mean()/x.std()*np.sqrt(len(x))
SL=['09:30','10:00','11:00','12:00']
fig,axs=plt.subplots(2,2,figsize=(16,10))
for ax,s in zip(axs.flat,SL):
    x=m[m.slot==s]
    rules=[('買便宜那邊（Call 便宜買 Call／Put 便宜買 Put）',pd.concat([x[(x.q==1)&(x.cp=='C')],x[(x.q==5)&(x.cp=='P')]]),'#2a78d6'),
           ('買貴那邊',pd.concat([x[(x.q==1)&(x.cp=='P')],x[(x.q==5)&(x.cp=='C')]]),'#e34948'),
           ('對照：每天都買 Call',x[x.cp=='C'],'#9a9993'),('對照：每天都買 Put',x[x.cp=='P'],'#c9c8c3')]
    for nm,d,c in rules:
        d=d.sort_values('date'); p=d.pnl_real
        ax.plot(pd.to_datetime(d.date),p.cumsum(),color=c,lw=2 if '那邊' in nm else 1.2,label=f'{nm}  n={len(p)}，每筆 {p.mean():+.1f}，t {tt(p):.1f}，總計 {p.sum():+.0f}')
    ax.axhline(0,color='#52514e',lw=0.8); ax.set_title(f'{s} 進場，價內 1%，持有到結算',loc='left',fontsize=12)
    ax.legend(fontsize=8,frameon=False,loc='lower left'); ax.grid(axis='y',color='#e6e5e1'); [ax.spines[k].set_visible(False) for k in ['top','right']]
    ax.set_ylabel('累積損益（點）')
fig.suptitle('買賣權平價濾網：選擇權隱含指數（Call − Put + 履約價）vs 現貨（in-sample 2017-05~2022-12）\n偏離最低 20% 的日子 = Call 相對便宜；最高 20% = Put 相對便宜；成本含真實半價差、手續費、期交稅',fontsize=13)
fig.tight_layout(rect=[0,0,1,0.93]); fig.savefig(OUT/'cum_parity.png',dpi=110); plt.close(fig)
