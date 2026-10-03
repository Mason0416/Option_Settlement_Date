"""Step 2: overnight gap split, ITM-1% call bought right after the 08:45 futures open, held to settlement.
In-sample 2017-05-15 .. 2022-12-31, strictly no look-ahead:
  F_prev_close = last TX(c) trade on prev_date with time <= 13:45:00 (FinMind, cached under data/finmind/fut_prev/)
  F_open       = first TX(c) trade on D with time >= 08:45:00
  gap_pct      = (F_open - F_prev_close)/F_prev_close*100
  S_est        = F_open - basis_prev ;  K = round(S_est*0.99/50)*50
  entry        = first Call(K) trade with t_fopen < t < 08:50:00, + n ticks
"""
import os, sys, time, requests, numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
D = ROOT / 'data'; FM = D / 'finmind'; PREV = FM / 'fut_prev'
OUT = ROOT / 'results' / 'step2_gap'
START, END = '2017-05-15', '2022-12-31'
FEE = 0.5; TAX_ENTRY = 0.001; TAX_SETTLE = 0.00002
T845, T850, T1345 = pd.Timedelta('08:45:00'), pd.Timedelta('08:50:00'), pd.Timedelta('13:45:00')

def tick(p):
    return np.select([p < 10, p < 50, p < 500, p < 1000], [0.1, 0.5, 1.0, 5.0], 10.0)

def load_token():
    try:
        from common import load_env
        return load_env()['FINMIND_TOKEN']
    except Exception:
        for l in (ROOT / '.env').read_text().splitlines():
            if l.startswith('FINMIND_TOKEN='): return l.split('=', 1)[1].strip().strip('"\'')

def fetch_prev(ds, tok):
    """Raw TaiwanFuturesTick TX for start_date=ds, cached."""
    f = PREV / f'{ds}.parquet'
    if f.exists(): return pd.read_parquet(f)
    U = 'https://api.finmindtrade.com/api/v4/data'; H = {'Authorization': f'Bearer {tok}'}
    for a in range(8):
        try:
            r = requests.get(U, params=dict(dataset='TaiwanFuturesTick', data_id='TX', start_date=ds), headers=H, timeout=300)
            j = r.json()
            if j.get('status') == 200 or j.get('msg') == 'success':
                df = pd.DataFrame(j.get('data', []))
                if len(df) == 0: raise RuntimeError('empty')
                df.to_parquet(f, index=False); return df
            print('api msg', ds, j.get('msg'), flush=True)
            time.sleep(600 if ('limit' in str(j.get('msg')).lower() or r.status_code == 402) else 10 * (a + 1))
        except Exception as e:
            print('err', ds, repr(e)[:120], flush=True); time.sleep(10 * (a + 1))
    raise RuntimeError(f'fetch failed {ds}')

def prep_fut(df):
    df = df.copy()
    df['contract_date'] = df.contract_date.astype(str).str.strip()
    df = df[~df.contract_date.str.contains('/')]
    df['t'] = pd.to_datetime(df.date)
    return df.sort_values('t', kind='stable')

def one(r, prev_raw):
    ds = r.date; day = pd.Timestamp(ds)
    row = dict(date=ds, kind=r.kind, contract_month=r.contract_month, fut_contract=str(r.contract), prev_date=r.prev_date,
               basis_prev=r.basis_prev, ssp=float(r.ssp), status='ok')
    o = pd.read_parquet(FM / 'opt' / f'{ds}.parquet')
    o['t'] = pd.to_datetime(o.date)
    tod = o.t - o.t.dt.normalize()
    if not ((o.t.dt.normalize() == day) & (tod >= T845) & (tod <= pd.Timedelta('13:30:00'))).any():
        row['status'] = 'skip_no_day_session_opt'; return row
    c = str(r.contract)
    # previous day close
    p = prep_fut(prev_raw); p = p[p.contract_date == c]
    ptod = p.t - p.t.dt.normalize()
    p = p[(p.t.dt.normalize() == pd.Timestamp(r.prev_date)) & (ptod <= T1345)]
    if not len(p): row['status'] = 'skip_no_prev_close'; return row
    row['F_prev_close'] = float(p.price.iloc[-1]); row['t_fprev'] = p.t.iloc[-1]
    # today's open
    f = prep_fut(pd.read_parquet(FM / 'fut' / f'{ds}.parquet')); f = f[f.contract_date == c]
    f = f[(f.t.dt.normalize() == day) & ((f.t - f.t.dt.normalize()) >= T845)]
    if not len(f): row['status'] = 'skip_no_fut_open'; return row
    row['F_open'] = float(f.price.iloc[0]); row['t_fopen'] = f.t.iloc[0]
    # assertions (no look-ahead)
    tp, tf = row['t_fprev'], row['t_fopen']
    assert tp.normalize() == pd.Timestamp(r.prev_date) and (tp - tp.normalize()) <= T1345, (ds, tp)
    assert tf.normalize() == day and (tf - tf.normalize()) >= T845, (ds, tf)
    g = (row['F_open'] - row['F_prev_close']) / row['F_prev_close'] * 100
    row['gap_pct'] = g; row['group'] = 'gap_up' if g > 0 else ('gap_down' if g < 0 else 'flat')
    S = row['F_open'] - r.basis_prev; row['S_est'] = S
    K = float(np.floor(S * 0.99 / 50 + 0.5) * 50); row['K'] = K
    c_ = o[(o.PutCall == 'C') & (o.ExercisePrice == K)].sort_values('t', kind='stable')
    c_ = c_[(c_.t > tf) & (c_.t < day + T850)]
    payoff = max(row['ssp'] - K, 0.0); row['payoff'] = payoff
    if not len(c_): row['status'] = 'no_fill'; return row
    te = c_.t.iloc[0]; px = float(c_.price.iloc[0])
    assert te > tf, (ds, te, tf)
    row['t_entry'] = te; row['trade_px'] = px
    settle = FEE + TAX_SETTLE * row['ssp'] if payoff > 0 else 0.0
    for n in (1, 2, 4):
        e = px + n * float(tick(px)); row[f'entry_{n}t'] = e
        row[f'pnl_{n}t'] = payoff - e - (FEE + TAX_ENTRY * e) - settle
    row['pnl'] = row['pnl_2t']
    return row

def stats(x, n_days):
    x = x.dropna(); n = len(x)
    sd = x.std()
    return dict(n_days=n_days, n_filled=n, fill_rate=n / n_days if n_days else np.nan, mean=x.mean(), median=x.median(),
                std=sd, t_stat=x.mean() / sd * np.sqrt(n) if n > 1 and sd > 0 else np.nan, win_rate=(x > 0).mean(),
                total=x.sum(), total_ex_top5=x.sort_values().iloc[:-5].sum() if n > 5 else np.nan)

if __name__ == '__main__':
    PREV.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    cal = pd.read_csv(D / 'settlement_calendar.csv')
    cal = cal[(cal.date >= START) & (cal.date <= END)]
    bas = pd.read_csv(D / 'basis_prev.csv')
    cal = cal.merge(bas, on='date', how='left')
    assert cal.contract.notna().all(), 'missing basis_prev rows'
    cal['contract'] = cal.contract.astype(int).astype(str)
    tok = load_token()
    need = sorted(set(cal.prev_date))
    with ThreadPoolExecutor(6) as ex: raws = dict(zip(need, ex.map(lambda d: fetch_prev(d, tok), need)))
    rows = [one(r, raws[r.prev_date]) for r in cal.itertuples()]
    t = pd.DataFrame(rows)
    cols = ['date', 'kind', 'contract_month', 'fut_contract', 'prev_date', 'F_prev_close', 't_fprev', 'F_open', 't_fopen', 'gap_pct',
            'group', 'basis_prev', 'S_est', 'K', 't_entry', 'trade_px', 'entry_2t', 'ssp', 'payoff', 'pnl', 'pnl_1t', 'pnl_4t', 'status']
    t = t.reindex(columns=cols)
    t.to_csv(OUT / 'trades.csv', index=False)
    v = t[~t.status.str.startswith('skip')]
    summ = []
    for gname in ['gap_up', 'gap_down', 'all']:
        gg = v if gname == 'all' else v[v.group == gname]
        s = stats(gg.pnl, len(gg)); s.update(group=gname, mean_1t=gg.pnl_1t.mean(), mean_4t=gg.pnl_4t.mean(), avg_entry=gg.entry_2t.mean())
        summ.append(s)
    summ = pd.DataFrame(summ).set_index('group'); summ.to_csv(OUT / 'summary.csv')
    fl = v[v.pnl.notna()].copy(); fl['year'] = fl.date.str[:4]
    fl2 = pd.concat([fl[fl.group.isin(['gap_up', 'gap_down'])], fl.assign(group='all')])
    by = fl2.groupby(['group', 'year']).pnl.agg(n='count', total='sum', mean='mean', win_rate=lambda x: (x > 0).mean()).reset_index()
    by.to_csv(OUT / 'by_year.csv', index=False)
    # plot
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; from matplotlib import font_manager
    fp = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp); plt.rcParams['font.family'] = font_manager.FontProperties(fname=fp).get_name()
    plt.rcParams['axes.unicode_minus'] = False
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for gname, col, lab in [('gap_up', '#2a78d6', '跳空上漲 gap_up'), ('gap_down', '#e34948', '跳空下跌 gap_down')]:
        x = fl[fl.group == gname].sort_values('date')
        ax.plot(pd.to_datetime(x.date), x.pnl.cumsum(), color=col, lw=1.8, label=f'{lab} (n={len(x)}, 總計 {x.pnl.sum():.0f} 點)')
    ax.axhline(0, color='#888', lw=0.8)
    ax.set_title('08:45 開盤後買進價內 1% 買權持有至結算：依隔夜跳空分組累積損益（2 tick 滑價，含成本）')
    ax.set_ylabel('累積損益（點，1 點 = 50 元）'); ax.set_xlabel('結算日'); ax.legend(loc='upper left'); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(OUT / 'cum_pnl.png', dpi=140)
    print(t.status.value_counts().to_string()); print(v.group.value_counts().to_string())
    print(summ.round(3).to_string()); print(by.round(2).to_string())
    print('gap_pct', v.gap_pct.describe().round(4).to_string())
