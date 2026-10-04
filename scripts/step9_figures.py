"""Figures for research.md (Step 2 B/C/D and rule-decision section). In-sample only."""
import pandas as pd, numpy as np, matplotlib, glob
from pathlib import Path
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
ROOT=Path(__file__).resolve().parent.parent; R=ROOT/'results'; OUT=R/'figures'; OUT.mkdir(exist_ok=True)
for fp in glob.glob('/usr/share/fonts/**/NotoSansCJK*.ttc',recursive=True)[:1]+glob.glob('/System/Library/Fonts/PingFang.ttc'):
    fm.fontManager.addfont(fp); plt.rcParams['font.family']=[fm.FontProperties(fname=fp).get_name()]
plt.rcParams.update({'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#8a8984','axes.labelcolor':'#3b3a37','xtick.color':'#52514e','ytick.color':'#52514e'})
BLUE,RED,ORANGE,GRAY,INK='#2a78d6','#e34948','#eb6834','#9a9993','#2b2a27'
tt=lambda x:x.mean()/x.std()*np.sqrt(len(x)) if len(x)>2 else np.nan
def grid(ax): ax.grid(axis='y',color='#e6e5e1',lw=0.8); ax.set_axisbelow(True); ax.axhline(0,color='#52514e',lw=0.8)

# ---------- 1. Result B: each segment alone ----------
d=pd.read_csv(R/'step2_night'/'trades_3seg.csv')
segs=[('s1','夜盤開盤跳空\n13:45→15:00'),('s2','夜盤盤中\n15:00→05:00'),('s3','盤前段\n05:00→08:45')]
fig,ax=plt.subplots(figsize=(10,5.2)); w=0.36
for i,(c,nm) in enumerate(segs):
    for j,(lab,m,col) in enumerate([('漲',d[c]>0,BLUE),('跌',d[c]<0,RED)]):
        x=d[m].pnl; v=x.mean(); xpos=i+(j-0.5)*w
        ax.bar(xpos,v,w*0.92,color=col,label=lab if i==0 else None)
        ax.text(xpos,v+(0.6 if v>=0 else -0.6),f'{v:+.1f}\nt {tt(x):.2f}\n{len(x)} 天',ha='center',va='bottom' if v>=0 else 'top',fontsize=9,color=INK)
ax.set_xticks(range(3)); ax.set_xticklabels([s[1] for s in segs],fontsize=10); grid(ax); ax.set_ylim(-14,18)
ax.set_ylabel('08:45 價內 1% Call 每筆平均損益（點）'); ax.legend(title='該段方向',frameon=False,loc='upper left')
ax.set_title('附錄：開盤前三段各自分組（in-sample，271 天）——只有盤前段區分得出好壞',loc='left',fontsize=12)
fig.tight_layout(); fig.savefig(OUT/'step2_B_segments.png',dpi=120); plt.close(fig)

# ---------- 2. Result C: 8 combos ----------
C=pd.read_csv(R/'step2_night'/'combo3_perf.csv')
C['p3']=C.組合.str[-1]; C=pd.concat([C[C.p3=='漲'],C[C.p3=='跌']])
fig,ax=plt.subplots(figsize=(12,5.4)); x=np.arange(len(C)); w=0.38
ax.bar(x-w/2,C.Call每筆,w*0.92,color=BLUE,label='09:30 買 Call')
ax.bar(x+w/2,C.Put每筆,w*0.92,color=ORANGE,label='09:30 買 Put')
for i,r in enumerate(C.itertuples()):
    for off,v,t in [(-w/2,r.Call每筆,r.Call_t),(w/2,r.Put每筆,r.Put_t)]:
        ax.text(i+off,v+(0.8 if v>=0 else -0.8),f'{v:+.0f}'+('*' if abs(t)>=2 else ''),ha='center',va='bottom' if v>=0 else 'top',fontsize=8.5,color=INK)
ax.axvline(3.5,color='#52514e',lw=1,ls='--'); ax.text(1.5,30,'盤前漲 → Call 賺、Put 賠',ha='center',fontsize=10.5,color=INK); ax.text(5.5,30,'盤前跌 → Put 賺、Call 賠',ha='center',fontsize=10.5,color=INK)
ax.set_xticks(x); ax.set_xticklabels([f'{k}\n{n} 天' for k,n in zip(C.組合,C.天數)],fontsize=9.5); grid(ax); ax.set_ylim(-34,36)
ax.set_xlabel('夜盤開盤跳空／夜盤盤中／盤前段 的方向'); ax.set_ylabel('每筆平均損益（點）'); ax.legend(frameon=False,loc='lower left')
ax.set_title('附錄：三段方向 8 種組合（in-sample，09:30 進場，價內 1%，真實價差模型；* = |t| ≥ 2）',loc='left',fontsize=12)
fig.tight_layout(); fig.savefig(OUT/'step2_C_combo8.png',dpi=120); plt.close(fig)

# ---------- 3. Result D: 16 combos x Call/Put heatmap ----------
X=pd.read_csv(R/'step2_night'/'combo3_x_open.csv'); X['k']=X.三段+'／'+X.開盤後
order=[]
for p3,o in [('漲','漲'),('跌','跌'),('漲','跌'),('跌','漲')]:
    order+=[f'{a}／{b}／{p3}／{o}' for a in '漲跌' for b in '漲跌']
X=X.set_index('k').loc[order]
cmap=LinearSegmentedColormap.from_list('div',[RED,'#f0efec',BLUE])
fig,ax=plt.subplots(figsize=(9,10)); M=X[['Call','Put']].values; T=X[['Ct','Pt']].values
im=ax.imshow(M,cmap=cmap,norm=TwoSlopeNorm(0,-40,40),aspect='auto')
for i in range(len(X)):
    for j in range(2):
        ax.text(j,i,f'{M[i,j]:+.1f}'+('*' if abs(T[i,j])>=2 else ''),ha='center',va='center',fontsize=10,color=INK,fontweight='bold' if abs(T[i,j])>=2 else 'normal')
for y in [3.5,7.5,11.5]: ax.axhline(y,color='#52514e',lw=1.2)
ax.set_xticks([0,1]); ax.set_xticklabels(['買 Call','買 Put'],fontsize=11); ax.xaxis.tick_top()
ax.set_yticks(range(len(X))); ax.set_yticklabels([f'{k}（{n} 天）' for k,n in zip(X.index,X.天數)],fontsize=9.5)
for y,t in [(1.5,'盤前、開盤後都漲'),(5.5,'盤前、開盤後都跌'),(9.5,'盤前漲、開盤後跌'),(13.5,'盤前跌、開盤後漲')]: ax.text(1.6,y,t,va='center',fontsize=9.5)
for s_ in ax.spines.values(): s_.set_visible(False)
cb=fig.colorbar(im,ax=ax,shrink=0.5,pad=0.38); cb.set_label('每筆平均損益（點）')
ax.set_title('附錄：夜盤兩段 × 盤前 × 開盤後方向（09:30，價內 1%）\n列 = 夜盤開盤跳空／夜盤盤中／盤前／開盤後；* 與粗體 = |t| ≥ 2',loc='left',fontsize=11.5,pad=28)
fig.tight_layout(); fig.savefig(OUT/'step2_D_combo16.png',dpi=120,bbox_inches='tight'); plt.close(fig)

# ---------- 4. Rule decision: entry time ----------
A=pd.read_csv(R/'step4d_cross'/'a_by_time.csv')
fig,ax=plt.subplots(figsize=(10,5.2))
for side,col,mk in [('Call',BLUE,'o'),('Put',ORANGE,'s')]:
    q=A[A.side==side]; xs=np.arange(len(q))
    ax.plot(xs,q['mean'],color=col,lw=2,label=f'{side}（{"盤前漲＋開盤後漲" if side=="Call" else "盤前跌＋開盤後跌"}）')
    for x_,v,t in zip(xs,q['mean'],q.t):
        ax.scatter(x_,v,s=60,marker=mk,color=col if t>=2 else 'white',edgecolor=col,lw=2,zorder=3)
        other=A[(A.side!=side)].reset_index(drop=True)['mean'][x_]; up=v>=other
        ax.text(x_,v+(1.6 if up else -2.0),f'{v:+.1f}',ha='center',va='bottom' if up else 'top',fontsize=8.5,color=INK)
ax.set_xticks(np.arange(len(A[A.side=='Call']))); ax.set_xticklabels(A[A.side=='Call'].slot); grid(ax)
ax.axvspan(0.6,1.4,color='#e6e5e1',alpha=0.6,zorder=0); ax.text(1,44,'選定 09:30',ha='center',fontsize=10,color=INK)
ax.set_ylim(-6,48); ax.set_xlabel('進場時間'); ax.set_ylabel('每筆平均損益（點）')
ax.legend(frameon=False,loc='upper right',title='實心 = t ≥ 2；空心 = t < 2',title_fontsize=9)
ax.set_title('規則決定：兩段同向在各進場時間的績效（in-sample，價內 1%，真實價差模型）',loc='left',fontsize=12)
fig.tight_layout(); fig.savefig(OUT/'rule_entry_time.png',dpi=120); plt.close(fig)

# ---------- 5. Final rules: cumulative + yearly ----------
I=pd.read_parquet(R/'step7_cross3'/'trades_fixed.parquet'); I=I[I.level==-1.0]
base=I[I.slot=='09:30'].sort_values('date'); enh=pd.concat([I[(I.slot=='09:30')&(I.side=='Call')&I.ok],I[(I.slot=='10:00')&(I.side=='Put')&I.ok]]).sort_values('date')
fig,(a1,a2)=plt.subplots(1,2,figsize=(15,5.4),gridspec_kw={'width_ratios':[2.1,1]})
for nm,dd,col in [('基本版',base,BLUE),('加強版（＋平價）',enh,ORANGE)]:
    p=dd.pnl_real; a1.plot(pd.to_datetime(dd.date),p.cumsum(),color=col,lw=2.2,label=f'{nm}  {len(p)} 筆，每筆 {p.mean():+.1f}，t {tt(p):.2f}，扣最賺 5 天 {p.sort_values().iloc[:-5].sum():+.0f}')
grid(a1); a1.legend(frameon=False,loc='upper left'); a1.set_ylabel('累積損益（點）')
a1.set_title('最終規則：累積損益（in-sample 2018-05 ～ 2022-12）',loc='left',fontsize=12)
yb=base.assign(y=base.date.str[:4]).groupby('y').pnl_real.sum(); ye=enh.assign(y=enh.date.str[:4]).groupby('y').pnl_real.sum().reindex(yb.index,fill_value=0)
xs=np.arange(len(yb)); w=0.38
a2.bar(xs-w/2,yb.values,w*0.92,color=BLUE,label='基本版'); a2.bar(xs+w/2,ye.values,w*0.92,color=ORANGE,label='加強版')
for i,(u,v) in enumerate(zip(yb.values,ye.values)):
    a2.text(i-w/2,u,f'{u:+.0f}',ha='center',va='bottom' if u>=0 else 'top',fontsize=8.5); a2.text(i+w/2,v,f'{v:+.0f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=8.5)
a2.set_xticks(xs); a2.set_xticklabels(yb.index); grid(a2); a2.legend(frameon=False,loc='upper left'); a2.set_title('各年總損益（點）',loc='left',fontsize=12)
fig.tight_layout(); fig.savefig(OUT/'rule_final.png',dpi=120); plt.close(fig)
print('ok')
