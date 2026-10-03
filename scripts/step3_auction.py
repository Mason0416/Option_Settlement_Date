"""Step 3: buy ITM1% Call in the 08:45 opening auction (no bid-ask spread), hold to TAIFEX SSP.
Assumption: the 08:44 futures pre-open (試撮) price ~= 08:45 futures open, so the premarket segment and strike K
(both computed from the futures open) are treated as known just before the auction.  In-sample 2017-05 ~ 2022-12.
"""
import pandas as pd, numpy as np, matplotlib
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import glob
ROOT=Path(__file__).resolve().parent.parent; D=ROOT/'data'; OUT=ROOT/'results'/'step3_auction'; OUT.mkdir(parents=True,exist_ok=True)
FEE=0.5; TAX_ENTRY=0.001; TAX_SETTLE=0.00002
def tick(p): return np.select([p<10,p<50,p<500,p<1000],[0.1,0.5,1.0,5.0],10.0)
def opt_day(ds):
    p=D/'finmind'/'opt'/f'{ds}.parquet'
    return pd.read_parquet(p)
t=pd.read_csv(ROOT/'results'/'step2_gap'/'trades.csv')
nt=pd.read_csv(ROOT/'results'/'step2_night'/'trades_night.csv')[['date','night_pct','premkt_pct','night_status','night_truncated']]
t=t.merge(nt,on='date',how='left')
t=t[t.status.isin(['ok','no_fill'])].copy()
rows=[]
for r in t.itertuples():
    o=opt_day(r.date); o['t']=pd.to_datetime(o.date)
    x=o[(o.ExercisePrice==r.K)&(o.PutCall=='C')&(o.t==pd.Timestamp(f'{r.date} 08:45:00'))]   # file order kept (stable)
    auc=x.price.iloc[0] if len(x) else np.nan
    rows.append(dict(date=r.date,auction_px=auc,auction_vol=(x.volume.iloc[0]/2 if len(x) else np.nan)))
a=t.merge(pd.DataFrame(rows),on='date')
a['payoff']=np.maximum(a.ssp-a.K,0.0)
settle=np.where(a.payoff>0,FEE+TAX_SETTLE*a.ssp,0.0)
for n,name in [(0,'pnl_auc'),(1,'pnl_auc_1t')]:
    e=a.auction_px+n*tick(a.auction_px)
    a[name]=a.payoff-e-(FEE+TAX_ENTRY*e)-settle
a['auc_status']=np.where(a.auction_px.notna(),'ok','no_auction_print')
a.to_csv(OUT/'trades_auction.csv',index=False)
f=a[a.auc_status=='ok'].copy()
def stats(s):
    s=s.dropna(); n=len(s); cum=s.cumsum(); dd=(cum.cummax()-cum).max() if n else np.nan
    return dict(n=n,mean=s.mean(),median=s.median(),std=s.std(),t=s.mean()/s.std()*np.sqrt(n) if n>1 else np.nan,
                win=(s>0).mean(),total=s.sum(),total_ex_top5=s.sort_values().iloc[:-5].sum() if n>5 else np.nan,max_dd=dd)
groups={'全部進場':f,'盤前漲才進場':f[f.premkt_pct>0],'盤前跌才進場':f[f.premkt_pct<0]}
res=[]
for g,d in groups.items():
    s=stats(d.sort_values('date').pnl_auc); s.update(group=g,mean_1t=d.pnl_auc_1t.mean(),avg_entry=d.auction_px.mean())
    # same days, old rule (first continuous trade +2 ticks) for comparison
    s['old_rule_mean_same_days']=d.pnl.mean()
    res.append(s)
S=pd.DataFrame(res)[['group','n','mean','median','std','t','win','total','total_ex_top5','max_dd','mean_1t','avg_entry','old_rule_mean_same_days']]
S.to_csv(OUT/'summary.csv',index=False)
f['year']=f.date.str[:4]; f['pre']=np.where(f.premkt_pct>0,'盤前漲',np.where(f.premkt_pct<0,'盤前跌','NA'))
by=f.groupby(['pre','year']).pnl_auc.agg(n='size',total='sum',mean='mean',win=lambda x:(x>0).mean()).reset_index(); by.to_csv(OUT/'by_year.csv',index=False)
# plot
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
fig,ax=plt.subplots(figsize=(11,5.5))
for (g,d),c in zip(groups.items(),['#8a8985','#2a78d6','#e34948']):
    d=d.sort_values('date'); ax.plot(pd.to_datetime(d.date),d.pnl_auc.cumsum(),color=c,lw=1.8 if g!='全部進場' else 1.2,label=f'{g} (n={len(d)}, 總計 {d.pnl_auc.sum():+.0f} 點)')
ax.axhline(0,color='#52514e',lw=0.8); ax.legend(frameon=False); ax.grid(axis='y',color='#e6e5e1')
for s in ['top','right']: ax.spines[s].set_visible(False)
ax.set_ylabel('累積損益（點，1 點 = 50 元）'); ax.set_title('08:45 開盤集合競價買價內 1% Call 持有到結算（in-sample，無滑價、含手續費與稅）')
fig.tight_layout(); fig.savefig(OUT/'cum_pnl.png',dpi=130)
print(S.round(2).to_string(index=False)); print(by.round(1).to_string(index=False))
print('auction print availability:', (a.auc_status=='ok').mean().round(3), 'days',len(a))
