"""Step 2b: split the overnight gap into night-session move and pre-market (night close -> 08:45 open) move.
Strictly no look-ahead:
  F_night_close = last TX(c) trade with prev_date 15:00:00 < t < D 08:45:00 (data/finmind/fut/YYYY-MM.parquet, settle_date==D)
  night_pct  = (F_night_close - F_prev_close)/F_prev_close*100
  premkt_pct = (F_open - F_night_close)/F_night_close*100
PnL columns are taken as-is from results/step2_gap/trades.csv (not recomputed).
"""
import sys, numpy as np, pandas as pd
from pathlib import Path
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parent.parent
FUT = ROOT / 'data' / 'finmind' / 'fut'
OUT = ROOT / 'results' / 'step2_night'
GROUPS = ['night_up_pre_up', 'night_up_pre_dn', 'night_dn_pre_up', 'night_dn_pre_dn']
COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#e34948']

def load_settle(D, months, cache={}):
    parts = []
    for m in months:
        if m not in cache:
            f = FUT / f'{m}.parquet'
            cache.clear() if len(cache) > 3 else None
            cache[m] = pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=['contract_date','date','price','settle_date'])
        x = cache[m]; parts.append(x[x.settle_date == D])
    df = pd.concat(parts, ignore_index=True)  # keep original file order
    df['contract_date'] = df.contract_date.astype(str).str.strip()
    df['t'] = pd.to_datetime(df.date)
    return df.sort_values('t', kind='stable')

def night_close(row):
    D, pdate, c = row.date, row.prev_date, str(row.fut_contract).strip()
    months = sorted({pdate[:7], D[:7]})
    f = load_settle(D, months)
    lo, hi = pd.Timestamp(f'{pdate} 15:00:00'), pd.Timestamp(f'{D} 08:45:00')
    w = f[(f.contract_date == c) & (f.t > lo) & (f.t < hi)]
    if w.empty: return np.nan, pd.NaT, 'missing'
    last = w.iloc[-1]
    return float(last.price), last.t, 'ok'

def stats(x1, x4, x):
    n = len(x); sd = x.std(ddof=1) if n > 1 else np.nan
    return dict(n=n, mean=x.mean(), median=x.median(), std=sd,
                t=x.mean() / sd * np.sqrt(n) if n > 1 and sd > 0 else np.nan,
                win_rate=(x > 0).mean() if n else np.nan, total=x.sum(),
                total_ex_top5=x.sort_values().iloc[:-5].sum() if n > 5 else np.nan,
                mean_pnl_1t=x1.mean(), mean_pnl_4t=x4.mean())

def summarize(df, col, order):
    rows = []
    for g in order:
        s = df[df[col] == g]
        rows.append(dict(group=g, **stats(s.pnl_1t, s.pnl_4t, s.pnl)))
    rows.append(dict(group='ALL', **stats(df.pnl_1t, df.pnl_4t, df.pnl)))
    return pd.DataFrame(rows)

def spearman(a, b):
    m = a.notna() & b.notna()
    return a[m].rank().corr(b[m].rank())

def cjk_font():
    cands = ['/System/Library/Fonts/PingFang.ttc']
    try:
        import subprocess
        out = subprocess.run(['fc-list', ':lang=zh', 'file'], capture_output=True, text=True).stdout
        fs = [l.split(':')[0].strip() for l in out.splitlines() if l.strip()]
        cands += sorted(fs, key=lambda p: (('Sans' not in p), ('Regular' not in p), ('CJK' not in p)))
    except Exception: pass
    for p in cands:
        if Path(p).exists():
            try:
                font_manager.fontManager.addfont(p)
                name = font_manager.FontProperties(fname=p).get_name()
                plt.rcParams['font.family'] = name; plt.rcParams['axes.unicode_minus'] = False
                return True
            except Exception: continue
    return False

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tr = pd.read_csv(ROOT / 'results' / 'step2_gap' / 'trades.csv', dtype={'fut_contract': str, 'contract_month': str})
    tr['fut_contract'] = tr.fut_contract.astype(str).str.strip()
    res = [night_close(r) for r in tr.itertuples(index=False)]
    tr['F_night_close'] = [a for a, _, _ in res]
    tr['t_night_close'] = [b for _, b, _ in res]
    tr['night_status'] = [s for _, _, s in res]
    tr['night_pct'] = (tr.F_night_close - tr.F_prev_close) / tr.F_prev_close * 100
    tr['premkt_pct'] = (tr.F_open - tr.F_night_close) / tr.F_night_close * 100

    ok = tr.night_status == 'ok'
    tno, tfo = pd.to_datetime(tr.t_night_close), pd.to_datetime(tr.t_fopen)
    hasopen = ok & tfo.notna()
    assert (tno[hasopen] < tfo[hasopen]).all(), 't_night_close >= t_fopen'
    assert (tno[ok] < pd.to_datetime(tr.date[ok] + ' 08:45:00')).all(), 't_night_close >= D 08:45'
    assert (tno[ok] > pd.to_datetime(tr.prev_date[ok] + ' 15:00:00')).all(), 't_night_close <= prev 15:00'
    comb = ((1 + tr.night_pct / 100) * (1 + tr.premkt_pct / 100) - 1) * 100
    err = (comb - tr.gap_pct).abs()
    print('max |combined - gap_pct| =', err[ok].max(), 'rows checked', err[ok].notna().sum())

    g4 = np.where(tr.night_pct > 0, 'night_up', np.where(tr.night_pct < 0, 'night_dn', 'night_zero'))
    p4 = np.where(tr.premkt_pct > 0, 'pre_up', np.where(tr.premkt_pct < 0, 'pre_dn', 'pre_zero'))
    tr['group4'] = [f'{a}_{b}' if 'zero' not in a + b else 'zero' for a, b in zip(g4, p4)]
    tr.loc[ok & (tr.night_pct.isna() | tr.premkt_pct.isna()), 'group4'] = 'na'
    tr.loc[~ok, 'group4'] = 'missing'
    # night session whose 00:00-05:00 part falls on a non-D calendar day (holiday/weekend) is not in the bundle
    tr['night_truncated'] = ok & (tno.dt.strftime('%Y-%m-%d') != tr.date)
    tr['t_night_close'] = tno.dt.strftime('%Y-%m-%d %H:%M:%S')
    tr.to_csv(OUT / 'trades_night.csv', index=False)

    base = tr[(tr.status == 'ok') & ok].copy()
    base['night2'] = np.where(base.night_pct > 0, 'night_up', np.where(base.night_pct < 0, 'night_dn', 'zero'))
    base['premkt2'] = np.where(base.premkt_pct > 0, 'pre_up', np.where(base.premkt_pct < 0, 'pre_dn', 'zero'))
    s4 = summarize(base[base.group4 != 'zero'], 'group4', GROUPS)
    s4.to_csv(OUT / 'summary_4groups.csv', index=False)
    b2 = base[(base.group4 != 'zero') & ~base.night_truncated]
    summarize(b2, 'group4', GROUPS).to_csv(OUT / 'summary_4groups_excl_truncated.csv', index=False)
    summarize(base[base.night2 != 'zero'], 'night2', ['night_up', 'night_dn']).to_csv(OUT / 'summary_night2.csv', index=False)
    summarize(base[base.premkt2 != 'zero'], 'premkt2', ['pre_up', 'pre_dn']).to_csv(OUT / 'summary_premkt2.csv', index=False)

    cr = []
    for v in ['night_pct', 'premkt_pct', 'gap_pct']:
        cr.append(dict(x=v, y='pnl', n=len(base), pearson=base.pnl.corr(base[v]), spearman=spearman(base.pnl, base[v])))
    cr.append(dict(x='night_pct', y='premkt_pct', n=len(base), pearson=base.night_pct.corr(base.premkt_pct),
                   spearman=spearman(base.night_pct, base.premkt_pct)))
    cr = pd.DataFrame(cr); cr.to_csv(OUT / 'correlations.csv', index=False)

    base['year'] = base.date.str[:4].astype(int)
    by = base[base.group4 != 'zero'].groupby(['year', 'group4']).pnl.agg(
        n='size', total='sum', mean='mean', win_rate=lambda x: (x > 0).mean()).reset_index()
    by.to_csv(OUT / 'by_year.csv', index=False)

    ds = base[['night_pct', 'premkt_pct', 'gap_pct']].describe(percentiles=[.05, .1, .25, .5, .75, .9, .95]).T
    ds['abs_mean'] = base[['night_pct', 'premkt_pct', 'gap_pct']].abs().mean()
    ds.index.name = 'component'; ds.to_csv(OUT / 'components_describe.csv')

    zh = cjk_font()
    lab = dict(zip(GROUPS, ['夜盤漲・盤前漲', '夜盤漲・盤前跌', '夜盤跌・盤前漲', '夜盤跌・盤前跌'] if zh else
                   ['night up / pre up', 'night up / pre down', 'night down / pre up', 'night down / pre down']))
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for g, col in zip(GROUPS, COLORS):
        x = base[base.group4 == g].sort_values('date')
        ax.plot(pd.to_datetime(x.date), x.pnl.cumsum(), color=col, lw=1.8, label=f'{lab[g]} (n={len(x)})')
    ax.axhline(0, color='#888', lw=0.8)
    ax.set_ylabel('累積損益（點）' if zh else 'Cumulative PnL (pts)')
    ax.set_title('結算日 ITM1% Call：夜盤 × 盤前 四組累積損益' if zh else 'Settlement-day ITM1% call: cum PnL by night x pre-market')
    ax.legend(loc='upper left', frameon=False); ax.grid(alpha=.25)
    fig.tight_layout(); fig.savefig(OUT / 'cum_pnl_4groups.png', dpi=140); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for a, v, ttl in zip(axs, ['night_pct', 'premkt_pct'], ['夜盤漲跌 %' if zh else 'night_pct (%)', '盤前漲跌 %' if zh else 'premkt_pct (%)']):
        a.scatter(base[v], base.pnl, s=14, alpha=.6, color='#2a78d6')
        a.axhline(0, color='#888', lw=.8); a.axvline(0, color='#888', lw=.8)
        r = cr[cr.y == 'pnl'].set_index('x').loc[v]
        a.set_title(f'{ttl}  (Pearson {r.pearson:.2f}, Spearman {r.spearman:.2f})'); a.set_xlabel(ttl); a.grid(alpha=.25)
    axs[0].set_ylabel('pnl（點）' if zh else 'pnl (pts)')
    fig.tight_layout(); fig.savefig(OUT / 'scatter.png', dpi=140); plt.close(fig)

    print('missing:', tr.loc[~ok, ['date', 'prev_date', 'fut_contract', 'status']].to_string())
    print('truncated:', tr.loc[tr.night_truncated, 'date'].tolist())
    print('zero rows:', (base.group4 == 'zero').sum())
    print(s4.to_string()); print(cr.to_string())
    print('max_err', err[ok].max(), 'cjk_font', zh)

if __name__ == '__main__':
    main()
