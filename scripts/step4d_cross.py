"""Step 4d: premarket direction (night close -> 08:45 open) x open-to-entry direction (08:45 -> entry), time x strike. In-sample only."""
import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'results'/'step4d_cross'; OUT.mkdir(parents=True,exist_ok=True)
SLOTS=['09:00','09:30','10:00','10:30','11:00','11:30','12:00','12:30','13:00']
LV=[-1.0,-0.5,0.0,0.5,1.0,1.5,2.0,3.0]
NAME={-1.0:'價內 1%',-0.5:'價內 0.5%',0.0:'價平',0.5:'價外 0.5%',1.0:'價外 1%',1.5:'價外 1.5%',2.0:'價外 2%',3.0:'價外 3%'}
g=pd.read_parquet(ROOT/'results'/'step4c_open_to_entry'/'trades.parquet')
nt=pd.read_csv(ROOT/'results'/'step2_night'/'trades_night.csv')[['date','premkt_pct']]
g=g.merge(nt,on='date',how='inner'); g=g[g.premkt_pct.notna()&(g.premkt_pct!=0)]
g['pm']=np.where(g.premkt_pct>0,'盤前漲','盤前跌'); g['oe']=np.where(g.o2e_pct>0,'開盤後漲','開盤後跌')
g['grp']=g.pm+'・'+g.oe
g.to_parquet(OUT/'trades.parquet',index=False)
def st(s):
    s=s.dropna(); n=len(s)
    return pd.Series(dict(n=n,mean=s.mean(),t=s.mean()/s.std()*np.sqrt(n) if n>1 else np.nan,win=(s>0).mean(),
        total=s.sum(),total_ex_top5=s.sort_values().iloc[:-5].sum() if n>5 else np.nan))
S=g.groupby(['grp','cp','slot','level']).apply(lambda d: st(d.pnl_real),include_groups=False).reset_index()
S.to_csv(OUT/'summary.csv',index=False)
sp=g.drop_duplicates(['date','slot'])[['date','slot','grp','spot','ssp']]; sp['mv']=(sp.ssp/sp.spot-1)*100
MV=sp.groupby(['slot','grp']).mv.agg(['count','mean',lambda x:x.mean()/x.std()*np.sqrt(len(x))]).round(3); MV.columns=['n','mean%','t']
MV.to_csv(OUT/'move_to_ssp.csv')
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams['axes.unicode_minus']=False
cmap=LinearSegmentedColormap.from_list('div',['#e34948','#f0efec','#2a78d6'])
GR=['盤前漲・開盤後漲','盤前跌・開盤後跌','盤前漲・開盤後跌','盤前跌・開盤後漲']
fig,axs=plt.subplots(4,2,figsize=(16,20))
for r,gr in enumerate(GR):
    nd=g[g.grp==gr].groupby('slot').date.nunique().median()
    for c,(cp,cn) in enumerate([('C','Call'),('P','Put')]):
        ax=axs[r,c]; q=S[(S.grp==gr)&(S.cp==cp)]
        m=q.pivot(index='level',columns='slot',values='mean').reindex(index=LV,columns=SLOTS)
        tt=q.pivot(index='level',columns='slot',values='t').reindex(index=LV,columns=SLOTS)
        im=ax.imshow(m.values,cmap=cmap,norm=TwoSlopeNorm(0,-20,20),aspect='auto')
        for i in range(len(LV)):
            for j in range(len(SLOTS)):
                v=m.values[i,j]; t=tt.values[i,j]
                if np.isnan(v): continue
                ax.text(j,i,f'{v:+.1f}'+('*' if abs(t)>=2 else ''),ha='center',va='center',fontsize=8.5,color='#0b0b0b',fontweight='bold' if abs(t)>=2 else 'normal')
        ax.set_xticks(range(len(SLOTS))); ax.set_xticklabels(SLOTS,fontsize=9); ax.set_yticks(range(len(LV))); ax.set_yticklabels([NAME[l] for l in LV],fontsize=9)
        ax.set_title(f'{gr} → 買 {cn}（約 {nd:.0f} 天）',fontsize=12,loc='left')
        for s_ in ax.spines.values(): s_.set_visible(False)
cb=fig.colorbar(im,ax=axs,shrink=0.4,pad=0.02); cb.set_label('每筆平均損益（點）')
fig.suptitle('盤前方向 × 開盤後方向（08:45 → 進場前）：每筆平均損益（in-sample 2017-05~2022-12）\n藍 = 賺、紅 = 虧；* = |t| ≥ 2；成本含真實半價差、手續費、期交稅',fontsize=14)
fig.savefig(OUT/'heatmap_cross.png',dpi=110,bbox_inches='tight'); plt.close(fig)
print(MV.unstack('grp')['mean%'].to_string()); print(MV.unstack('grp')['t'].to_string())
print(MV.unstack('grp')['n'].to_string())
print(S.sort_values('t',ascending=False).head(15).round(2).to_string(index=False))
