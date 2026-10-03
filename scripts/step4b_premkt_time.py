"""Step 4b: time filter x strike, split by premarket segment (night close -> 08:45 futures open) up / down.
Premarket is known at 08:45; earliest entry 09:00 -> no look-ahead. Same realistic-spread costs as step4."""
import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step4b_premkt_time'; OUT.mkdir(parents=True,exist_ok=True)
SLOTS=['09:00','09:30','10:00','10:30','11:00','11:30','12:00','12:30','13:00']
LV=[-1.0,-0.5,0.0,0.5,1.0,1.5,2.0,3.0]
NAME={-1.0:'價內1%',-0.5:'價內0.5%',0.0:'價平',0.5:'價外0.5%',1.0:'價外1%',1.5:'價外1.5%',2.0:'價外2%',3.0:'價外3%'}
COL=['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4','#008300','#4a3aa7','#e34948']
g=pd.read_parquet(ROOT/'results'/'step4_timefilter'/'trades.parquet')
nt=pd.read_csv(ROOT/'results'/'step2_night'/'trades_night.csv')[['date','premkt_pct','night_status']]
g=g.merge(nt,on='date',how='left'); g=g[g.premkt_pct.notna()&(g.premkt_pct!=0)]
g['grp']=np.where(g.premkt_pct>0,'盤前漲','盤前跌')
g.to_parquet(OUT/'trades.parquet',index=False)
def st(s):
    s=s.dropna(); n=len(s); cs=s.cumsum()
    return pd.Series(dict(n=n,mean=s.mean(),median=s.median(),t=s.mean()/s.std()*np.sqrt(n) if n>1 else np.nan,win=(s>0).mean(),
        total=s.sum(),total_ex_top5=s.sort_values().iloc[:-5].sum() if n>5 else np.nan,max_dd=(cs.cummax()-cs).max()))
S=g.sort_values('date').groupby(['grp','cp','slot','level']).apply(lambda d: st(d.pnl_real),include_groups=False).reset_index()
S.to_csv(OUT/'summary.csv',index=False)
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
for grp in ['盤前漲','盤前跌']:
  nd=g[g.grp==grp].date.nunique()
  for cp,cname in [('C','Call'),('P','Put')]:
    fig,axs=plt.subplots(3,3,figsize=(17,13),sharex=True)
    for ax,s in zip(axs.flat,SLOTS):
        for L,c in zip(LV,COL):
            d=g[(g.grp==grp)&(g.cp==cp)&(g.slot==s)&(g.level==L)].sort_values('date')
            if len(d): ax.plot(pd.to_datetime(d.date),d.pnl_real.cumsum(),color=c,lw=1.4,label=f'{NAME[L]} {d.pnl_real.sum():+.0f}')
        ax.axhline(0,color='#52514e',lw=0.8); ax.set_title(f'{s} 進場',loc='left',fontsize=12)
        ax.grid(axis='y',color='#e6e5e1'); [ax.spines[k].set_visible(False) for k in ['top','right']]
        ax.legend(fontsize=7,frameon=False,loc='lower left',ncol=2); ax.tick_params(labelsize=8)
    fig.suptitle(f'【{grp}】買 {cname} 持有到結算：固定進場時間 × 履約價（累積損益，點；in-sample，{nd} 天）\n盤前段 = 夜盤收盤 → 08:45 期貨開盤；成本：5 分鐘內第一筆成交 + 真實半價差 + 手續費 + 期交稅',fontsize=13)
    fig.tight_layout(rect=[0,0,1,0.95]); fig.savefig(OUT/f'cum_{"up" if grp=="盤前漲" else "dn"}_{cname}.png',dpi=110); plt.close(fig)
for grp in ['盤前漲','盤前跌']:
    print('==',grp, g[g.grp==grp].date.nunique(),'days')
    print(S[S.grp==grp].pivot_table(index=['cp','level'],columns='slot',values='mean').round(1).to_string())
print(S.sort_values('t',ascending=False).head(10)[['grp','cp','slot','level','n','mean','median','t','win','total','total_ex_top5']].round(2).to_string(index=False))
