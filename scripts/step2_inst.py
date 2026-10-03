"""Step2 三大法人濾網：用結算日 D 的前一交易日(prev_date)三大法人資料決定是否進場。
用法: python3 scripts/step2_inst.py fetch   # 抓 FinMind 原始資料 (已存在則跳過, 加 --refetch 重抓)
      python3 scripts/step2_inst.py analyze # 計算指標、績效、圖
損益直接取自 results/step2_gap/trades.csv（不重算）。"""
import sys, time
from pathlib import Path
import numpy as np, pandas as pd, requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT/'data'/'finmind'/'inst'
OUT = ROOT/'results'/'step2_inst'
START, END = '2017-04-01', '2022-12-31'
DS = {'TaiwanFuturesInstitutionalInvestors': 'TX',
      'TaiwanOptionInstitutionalInvestors': 'TXO',
      'TaiwanStockTotalInstitutionalInvestors': None}

def load_env():  # 同 scripts/common.py 的 load_env（common.py 會 import shioaji，這裡不依賴）
    env = {}
    for l in (ROOT/'.env').read_text().splitlines():
        if '=' in l:
            k, v = l.split('=', 1); env[k.strip()] = v.strip().strip('"\'')
    return env

def fetch(refetch=False):
    RAW.mkdir(parents=True, exist_ok=True)
    H = {'Authorization': 'Bearer ' + load_env()['FINMIND_TOKEN']}
    for ds, did in DS.items():
        f = RAW/f'{ds}.parquet'
        if f.exists() and not refetch:
            print('skip', f.name); continue
        parts = []
        for y in range(2017, 2023):
            s = max(f'{y}-01-01', START); e = min(f'{y}-12-31', END)
            p = {'dataset': ds, 'start_date': s, 'end_date': e}
            if did: p['data_id'] = did
            for k in range(3):
                try:
                    r = requests.get('https://api.finmindtrade.com/api/v4/data', headers=H, params=p, timeout=120)
                    j = r.json()
                    if r.status_code == 200: break
                except Exception as ex:
                    j = {'msg': str(ex)}
                time.sleep(5)
            if r.status_code != 200:
                raise RuntimeError(f'{ds} {y}: {r.status_code} {j.get("msg")}')
            d = pd.DataFrame(j.get('data', []))
            print(ds, y, len(d), d['date'].min() if len(d) else None, d['date'].max() if len(d) else None)
            parts.append(d)
        df = pd.concat(parts, ignore_index=True)
        df.to_parquet(f, index=False)
        print('saved', f.name, df.shape, df.columns.tolist())

# ---------- 指標 ----------
FUT_INV = {'fut_foreign_oi_chg': '外資', 'fut_trust_oi_chg': '投信', 'fut_dealer_oi_chg': '自營商'}
OPT_INV = {'opt_foreign_dir': '外資', 'opt_dealer_dir': '自營商'}
SPOT = {'spot_foreign_net': ['Foreign_Investor'],             # 不含 Foreign_Dealer_Self
        'spot_trust_net': ['Investment_Trust'],
        'spot_dealer_net': ['Dealer_self', 'Dealer_Hedging']}  # 自行買賣 + 避險
IND = list(FUT_INV) + list(OPT_INV) + list(SPOT)

def daily_series():
    """回傳 {指標: Series(index=該資料集本身的交易日, value=當日指標值)}"""
    out = {}
    fut = pd.read_parquet(RAW/'TaiwanFuturesInstitutionalInvestors.parquet')
    fut = fut[fut.futures_id == 'TX']
    for k, inv in FUT_INV.items():
        g = fut[fut.institutional_investors == inv].set_index('date').sort_index()
        assert g.index.is_unique, k
        net = g.long_open_interest_balance_volume - g.short_open_interest_balance_volume
        allday = pd.Index(sorted(fut.date.unique()))
        out[k] = net.reindex(allday).diff()          # 以資料集自身日期序列做差
    opt = pd.read_parquet(RAW/'TaiwanOptionInstitutionalInvestors.parquet')
    opt = opt[opt.option_id == 'TXO']
    for k, inv in OPT_INV.items():
        g = opt[opt.institutional_investors == inv]
        net = (g.long_open_interest_balance_amount - g.short_open_interest_balance_amount)
        pv = pd.DataFrame({'date': g.date, 'cp': g.call_put, 'net': net}).pivot(index='date', columns='cp', values='net')
        out[k] = (pv['買權'] - pv['賣權']).sort_index()
    sp = pd.read_parquet(RAW/'TaiwanStockTotalInstitutionalInvestors.parquet')
    sp = sp.assign(net=sp.buy - sp.sell)
    for k, names in SPOT.items():
        g = sp[sp.name.isin(names)]
        cnt = g.groupby('date').name.nunique()
        s = g.groupby('date').net.sum()
        s[cnt < len(names)] = np.nan               # 自營商兩類須同時存在
        out[k] = s.sort_index()
    return out

def attach(tr, ser):
    tr = tr.copy()
    miss = []
    for k, s in ser.items():
        s = s.copy(); s.index = s.index.astype(str)
        val = tr.prev_date.map(s)
        has = tr.prev_date.isin(s.index)
        tr[k] = val
        tr[k + '_data_date'] = np.where(has, tr.prev_date, None)
        for _, r in tr[tr[k].isna()].iterrows():
            miss.append({'indicator': k, 'date': r.date, 'prev_date': r.prev_date,
                         'reason': 'prev_date 無資料' if not has[_] else '有資料但值為 NaN(資料集首日無前值/類別缺)'})
        dd = tr.loc[tr[k].notna(), k + '_data_date']
        assert (dd == tr.loc[dd.index, 'prev_date']).all(), k
        assert (dd != tr.loc[dd.index, 'date']).all(), k
    return tr, pd.DataFrame(miss)

# ---------- 統計 ----------
def stats(d):
    p = d.pnl.values; n = len(p)
    if n == 0:
        return dict(n=0)
    cum = np.cumsum(p); peak = np.maximum.accumulate(np.r_[0, cum])[1:]
    sd = p.std(ddof=1) if n > 1 else np.nan
    return dict(n=n, mean=p.mean(), median=np.median(p), std=sd,
                t=p.mean()/sd*np.sqrt(n) if n > 1 and sd > 0 else np.nan,
                win_rate=(p > 0).mean(), total=p.sum(),
                total_ex_top5=p.sum() - np.sort(p)[::-1][:5].sum(),
                mean_pnl_1t=d.pnl_1t.mean(), mean_pnl_4t=d.pnl_4t.mean(),
                max_dd=(peak - cum).max())

def rules(ok):
    R = {('all', '全部進場'): ok}
    for k in IND:
        R[(k, '正才進場')] = ok[ok[k] > 0]
        R[(k, '負才進場')] = ok[ok[k] < 0]
    return R

def analyze():
    OUT.mkdir(parents=True, exist_ok=True)
    tr = pd.read_csv(ROOT/'results'/'step2_gap'/'trades.csv', dtype={'contract_month': str, 'fut_contract': str})
    tr, miss = attach(tr, daily_series())
    tr.to_csv(OUT/'trades_inst.csv', index=False)
    miss.to_csv(OUT/'missing_indicators.csv', index=False)
    ok = tr[tr.status == 'ok'].sort_values('date').reset_index(drop=True)
    ok['year'] = ok.date.str[:4].astype(int)
    rows, yrows = [], []
    for (k, rule), d in rules(ok).items():
        s = stats(d); s.update(indicator=k, rule=rule)
        if k != 'all':
            s.update(n_zero=int((ok[k] == 0).sum()), n_nan=int(ok[k].isna().sum()))
        rows.append(s)
        for y, g in d.groupby('year'):
            yrows.append(dict(indicator=k, rule=rule, year=y, n=len(g), total=g.pnl.sum(),
                              mean=g.pnl.mean(), win_rate=(g.pnl > 0).mean()))
    cols = ['indicator', 'rule', 'n', 'mean', 'median', 'std', 't', 'win_rate', 'total', 'total_ex_top5',
            'mean_pnl_1t', 'mean_pnl_4t', 'max_dd', 'n_zero', 'n_nan']
    sm = pd.DataFrame(rows)[cols].sort_values('t', ascending=False)
    sm.to_csv(OUT/'summary.csv', index=False, float_format='%.4f')
    pd.DataFrame(yrows).to_csv(OUT/'by_year.csv', index=False, float_format='%.4f')
    cr = []
    for k in IND:
        d = ok[[k, 'pnl']].dropna()
        cr.append(dict(indicator=k, n=len(d), pearson=d[k].corr(d.pnl), spearman=d[k].rank().corr(d.pnl.rank()),
                       first_date=ok.loc[ok[k].notna(), 'date'].min()))
    pd.DataFrame(cr).to_csv(OUT/'correlations.csv', index=False, float_format='%.4f')
    plot(ok)
    print(sm.to_string(index=False))
    print(pd.DataFrame(cr).to_string(index=False))

def plot(ok):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt, matplotlib.font_manager as fm, subprocess
    zh = False
    cands = ['/System/Library/Fonts/PingFang.ttc']
    try:
        fl = subprocess.run(['fc-list', ':lang=zh', 'file'], capture_output=True, text=True).stdout
        cands += sorted([l.split(':')[0] for l in fl.splitlines() if 'Noto' in l and 'CJK' in l and 'Sans' in l and 'Regular' in l]) \
                 + sorted([l.split(':')[0] for l in fl.splitlines() if 'Noto' in l and 'CJK' in l])
    except Exception:
        pass
    for f in cands:
        if Path(f).exists():
            try:
                fm.fontManager.addfont(f)
                plt.rcParams['font.family'] = fm.FontProperties(fname=f).get_name()
                plt.rcParams['axes.unicode_minus'] = False
                zh = True; break
            except Exception:
                continue
    L = ('正才進場', '負才進場', '全部進場') if zh else ('Enter if > 0', 'Enter if < 0', 'All days')
    dt = pd.to_datetime(ok.date)
    fig, axes = plt.subplots(4, 2, figsize=(14, 15), sharex=True)
    for ax, k in zip(axes.ravel(), IND):
        ax.plot(dt, ok.pnl.cumsum(), color='#8a8985', lw=0.8, label=L[2])
        for m, c, lab in [(ok[k] > 0, '#2a78d6', L[0]), (ok[k] < 0, '#e34948', L[1])]:
            d = ok[m]
            ax.plot(pd.to_datetime(d.date), d.pnl.cumsum(), color=c, lw=1.4, label=f'{lab} (n={m.sum()})')
        ax.axhline(0, color='k', lw=0.4)
        ax.set_title(k); ax.set_ylabel('累積 pnl（點）' if zh else 'cum pnl (pts)')
        ax.legend(fontsize=8, loc='upper left'); ax.grid(alpha=0.3)
    fig.suptitle('結算日買價內1% Call：前一日三大法人濾網' if zh else 'Settlement-day ITM call: prior-day institutional filters')
    fig.tight_layout(); fig.savefig(OUT/'cum_pnl.png', dpi=130)
    print('font zh =', zh)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'analyze'
    if cmd == 'fetch': fetch('--refetch' in sys.argv)
    else: analyze()
