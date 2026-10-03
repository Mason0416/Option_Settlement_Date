import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'oos'
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]:
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
T=pd.read_csv(OUT/'oos_trades.csv'); T=T[T.pnl.notna()].sort_values('date')
tt=lambda p: p.mean()/p.std()*np.sqrt(len(p))
fig,axs=plt.subplots(2,2,figsize=(17,10),gridspec_kw={'width_ratios':[2.2,1]})
for r,(nm,title) in enumerate([('A','方案 A：09:30 兩段同向，買價內 1%'),('B','方案 B：09:30 Call／10:00 Put，兩段同向＋平價符合')]):
    d=T[T.plan==nm]; ax=axs[r,0]
    for lab,x,col,lw in [('合計',d,'#2a78d6',2.4),('Call',d[d.cp=='C'],'#1baf7a',1.4),('Put',d[d.cp=='P'],'#eb6834',1.4)]:
        p=x.pnl; ax.plot(pd.to_datetime(x.date),p.cumsum(),color=col,lw=lw,label=f'{lab}  n={len(p)}，每筆 {p.mean():+.1f}，t {tt(p):.2f}，總計 {p.sum():+.0f}，扣最賺 5 天 {p.sort_values().iloc[:-5].sum():+.0f}')
    ax.axhline(0,color='#52514e',lw=0.8); ax.legend(frameon=False,loc='upper left',fontsize=9.5); ax.grid(axis='y',color='#e6e5e1')
    [ax.spines[k].set_visible(False) for k in ['top','right']]; ax.set_title(title,loc='left',fontsize=12); ax.set_ylabel('累積損益（點）')
    y=d.assign(y=d.date.str[:4]).groupby('y').agg(pts=('pnl','sum'),n=('pnl','size'),bp=('pnl',lambda s:(s/d.loc[s.index,'spot']*1e4).sum()))
    ax=axs[r,1]; xs=np.arange(len(y))
    ax.bar(xs,y.pts,color=['#2a78d6' if v>=0 else '#e34948' for v in y.pts],width=0.6)
    for i,(v,n,bp) in enumerate(zip(y.pts,y.n,y.bp)): ax.text(i,v,f'{v:+.0f}\n({n} 筆, {bp:+.0f} bp)',ha='center',va='bottom' if v>=0 else 'top',fontsize=9)
    ax.set_xticks(xs); ax.set_xticklabels(y.index); ax.axhline(0,color='#52514e',lw=0.8); [ax.spines[k].set_visible(False) for k in ['top','right']]
    ax.set_title('各年總損益（點；括號 = 筆數、相對指數的 bp）',loc='left',fontsize=11); ax.set_ylim(min(0,y.pts.min())*1.3,y.pts.max()*1.35)
fig.suptitle('Out-of-sample 績效（2023-01 ~ 2026-09-18，鎖定規則後才看）\n成本：Shioaji 真實賣價＋手續費＋期交稅；1 點 = 50 元；bp = 損益 ÷ 進場時指數，排除指數變大的影響',fontsize=13)
fig.tight_layout(rect=[0,0,1,0.92]); fig.savefig(OUT/'oos_perf.png',dpi=110)
