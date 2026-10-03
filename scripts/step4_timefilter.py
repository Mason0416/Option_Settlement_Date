"""Step 4: time filter. Fixed entry time (every 30 min 09:00..13:00); one cumulative-PnL line per strike level.
Entry = first trade in [t, t+5min) + realistic half-spread (relative, by half-hour bucket x level x C/P, from 2026 quotes; floor 1 tick).
Costs as before. In-sample 2017-05 ~ 2022-12. Source rows: results/step1/step1_trades_IS.parquet (verified)."""
import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step4_timefilter'; OUT.mkdir(parents=True,exist_ok=True)
FEE=0.5; TAX_ENTRY=0.001; TAX_SETTLE=0.00002
def tick(p): return np.select([p<10,p<50,p<500,p<1000],[0.1,0.5,1.0,5.0],10.0)
SLOTS=['09:00','09:30','10:00','10:30','11:00','11:30','12:00','12:30','13:00']
LV=[-1.0,-0.5,0.0,0.5,1.0,1.5,2.0,3.0]
NAME={-1.0:'價內1%',-0.5:'價內0.5%',0.0:'價平',0.5:'價外0.5%',1.0:'價外1%',1.5:'價外1.5%',2.0:'價外2%',3.0:'價外3%'}
COL=['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4','#008300','#4a3aa7','#e34948']
g=pd.read_parquet(ROOT/'results'/'step1'/'step1_trades_IS.parquet').dropna(subset=['trade_px'])
g=g[g.slot.isin(SLOTS)].copy()
m=pd.read_csv(ROOT/'results'/'spread_model_v2.csv').rename(columns={'bucket':'slot'})
g=g.merge(m[['slot','cp','level','rel_half_med']],on=['slot','cp','level'],how='left')
g['half']=np.maximum(g.rel_half_med*g.trade_px, tick(g.trade_px))
g['entry_real']=g.trade_px+g.half
settle=np.where(g.payoff>0,FEE+TAX_SETTLE*g.ssp,0.0)
g['pnl_real']=g.payoff-g.entry_real-(FEE+TAX_ENTRY*g.entry_real)-settle
g.to_parquet(OUT/'trades.parquet',index=False)
def st(s):
    s=s.dropna(); n=len(s); cs=s.cumsum()
    return pd.Series(dict(n=n,mean=s.mean(),median=s.median(),t=s.mean()/s.std()*np.sqrt(n) if n>1 else np.nan,win=(s>0).mean(),
        total=s.sum(),total_ex_top5=s.sort_values().iloc[:-5].sum() if n>5 else np.nan,max_dd=(cs.cummax()-cs).max(),avg_entry=np.nan))
S=g.sort_values('date').groupby(['cp','slot','level']).apply(lambda d: st(d.pnl_real).fillna({'avg_entry':d.entry_real.mean()}),include_groups=False).reset_index()
S['avg_entry']=g.groupby(['cp','slot','level']).entry_real.mean().values
S['avg_half_spread']=g.groupby(['cp','slot','level']).half.mean().values
S.to_csv(OUT/'summary.csv',index=False)
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
for cp,cname in [('C','Call'),('P','Put')]:
    fig,axs=plt.subplots(3,3,figsize=(17,13),sharex=True)
    for ax,s in zip(axs.flat,SLOTS):
        for L,c in zip(LV,COL):
            d=g[(g.cp==cp)&(g.slot==s)&(g.level==L)].sort_values('date')
            if len(d): ax.plot(pd.to_datetime(d.date),d.pnl_real.cumsum(),color=c,lw=1.4,label=f'{NAME[L]} {d.pnl_real.sum():+.0f}')
        ax.axhline(0,color='#52514e',lw=0.8); ax.set_title(f'{s} 進場',loc='left',fontsize=12)
        ax.grid(axis='y',color='#e6e5e1'); [ax.spines[k].set_visible(False) for k in ['top','right']]
        ax.legend(fontsize=7,frameon=False,loc='lower left',ncol=2); ax.tick_params(labelsize=8)
    fig.suptitle(f'買 {cname} 持有到結算：固定進場時間 × 履約價（累積損益，點；in-sample 2017-05~2022-12）\n成本：5 分鐘內第一筆成交 + 真實半價差（依時間×價位，至少 1 tick）+ 手續費 25 元 + 期交稅',fontsize=13)
    fig.tight_layout(rect=[0,0,1,0.95]); fig.savefig(OUT/f'cum_{cname}.png',dpi=110); plt.close(fig)
pv=S.pivot_table(index=['cp','level'],columns='slot',values='mean').round(2); print(pv.to_string())
print(S.sort_values('t',ascending=False).head(8)[['cp','slot','level','n','mean','median','t','win','total','total_ex_top5']].round(2).to_string(index=False))
