"""Step 4c: time filter x strike, split by futures move from 08:45 open to entry time (08:45 open -> last trade before slot).
Not crossed with premarket. Info known before entry -> no look-ahead. Same realistic-spread costs as step4."""
import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
ROOT=Path(__file__).resolve().parent.parent; D=ROOT/'data'; OUT=ROOT/'results'/'step4c_open_to_entry'; OUT.mkdir(parents=True,exist_ok=True)
SLOTS=['09:00','09:30','10:00','10:30','11:00','11:30','12:00','12:30','13:00']
LV=[-1.0,-0.5,0.0,0.5,1.0,1.5,2.0,3.0]
NAME={-1.0:'價內 1%',-0.5:'價內 0.5%',0.0:'價平',0.5:'價外 0.5%',1.0:'價外 1%',1.5:'價外 1.5%',2.0:'價外 2%',3.0:'價外 3%'}
g=pd.read_parquet(ROOT/'results'/'step4_timefilter'/'trades.parquet')
B=pd.read_csv(D/'basis_prev.csv',dtype={'contract':str}).set_index('date')
rows=[]
for ds in sorted(g.date.unique()):
    f=pd.read_parquet(D/'finmind'/'fut'/f'{ds}.parquet'); f['t']=pd.to_datetime(f.date)
    f['contract_date']=f.contract_date.astype(str).str.strip()
    f=f[(f.contract_date==B.loc[ds,'contract'])&(f.t>=pd.Timestamp(f'{ds} 08:45:00'))&(f.t<=pd.Timestamp(f'{ds} 13:45:00'))].sort_values('t',kind='stable')
    if f.empty: continue
    o=f.price.iloc[0]
    for s in SLOTS:
        b=f[f.t<pd.Timestamp(f'{ds} {s}:00')]
        if len(b): rows.append((ds,s,o,b.price.iloc[-1]))
M=pd.DataFrame(rows,columns=['date','slot','fut_open','fut_pre'])
M['o2e_pct']=(M.fut_pre/M.fut_open-1)*100
M.to_csv(OUT/'open_to_entry.csv',index=False)
g=g.merge(M,on=['date','slot'],how='inner'); g=g[g.o2e_pct!=0]
g['grp']=np.where(g.o2e_pct>0,'開盤後漲','開盤後跌')
g.to_parquet(OUT/'trades.parquet',index=False)
def st(s):
    s=s.dropna(); n=len(s)
    return pd.Series(dict(n=n,mean=s.mean(),t=s.mean()/s.std()*np.sqrt(n) if n>1 else np.nan,win=(s>0).mean(),
        total=s.sum(),total_ex_top5=s.sort_values().iloc[:-5].sum() if n>5 else np.nan))
S=g.groupby(['grp','cp','slot','level']).apply(lambda d: st(d.pnl_real),include_groups=False).reset_index()
S.to_csv(OUT/'summary.csv',index=False)
# index move from entry slot to SSP, by group (spot at entry from trades)
sp=g.drop_duplicates(['date','slot'])[['date','slot','grp','spot','ssp']]; sp['mv']=(sp.ssp/sp.spot-1)*100
MV=sp.groupby(['slot','grp']).mv.agg(['count','mean',lambda x:x.mean()/x.std()*np.sqrt(len(x))]).round(3); MV.columns=['n','mean%','t']
MV.to_csv(OUT/'move_to_ssp.csv')
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
cmap=LinearSegmentedColormap.from_list('div',['#e34948','#f0efec','#2a78d6'])
fig,axs=plt.subplots(2,2,figsize=(16,11))
panels=[('開盤後漲','C','開盤後漲 → 買 Call（順勢）'),('開盤後漲','P','開盤後漲 → 買 Put（逆勢）'),('開盤後跌','P','開盤後跌 → 買 Put（順勢）'),('開盤後跌','C','開盤後跌 → 買 Call（逆勢）')]
for ax,(gr,cp,title) in zip(axs.flat,panels):
    q=S[(S.grp==gr)&(S.cp==cp)]
    m=q.pivot(index='level',columns='slot',values='mean').reindex(index=LV,columns=SLOTS)
    tt=q.pivot(index='level',columns='slot',values='t').reindex(index=LV,columns=SLOTS)
    im=ax.imshow(m.values,cmap=cmap,norm=TwoSlopeNorm(0,-15,15),aspect='auto')
    for i in range(len(LV)):
        for j in range(len(SLOTS)):
            v=m.values[i,j]; t=tt.values[i,j]
            if np.isnan(v): continue
            ax.text(j,i,f'{v:+.1f}'+('*' if abs(t)>=2 else ''),ha='center',va='center',fontsize=9,color='#0b0b0b',fontweight='bold' if abs(t)>=2 else 'normal')
    ax.set_xticks(range(len(SLOTS))); ax.set_xticklabels(SLOTS,fontsize=9); ax.set_yticks(range(len(LV))); ax.set_yticklabels([NAME[l] for l in LV],fontsize=9)
    ax.set_title(title,fontsize=13,loc='left'); ax.set_xlabel('進場時間',fontsize=9)
    for s_ in ax.spines.values(): s_.set_visible(False)
cb=fig.colorbar(im,ax=axs,shrink=0.6,pad=0.02); cb.set_label('每筆平均損益（點，1 點 = 50 元）')
fig.suptitle('結算日買選擇權持有到結算：依「08:45 開盤 → 進場前」期貨方向分組的每筆平均損益（in-sample 2017-05~2022-12）\n藍 = 賺、紅 = 虧；* = |t| ≥ 2；成本含真實半價差、手續費、期交稅；每個進場時間各自用 08:45 → 該時間的走勢分組',fontsize=13)
fig.savefig(OUT/'heatmap_open2entry.png',dpi=120,bbox_inches='tight'); plt.close(fig)
print(MV.to_string())
for gr in ['開盤後漲','開盤後跌']:
    print('==',gr); print(S[S.grp==gr].pivot_table(index=['cp','level'],columns='slot',values='mean').round(1).to_string())
print(S.sort_values('t',ascending=False).head(12).round(2).to_string(index=False))
