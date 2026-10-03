"""Step 2：0DTE 價內 1% Call 開盤進場成本驗證（只看報價與成交價，不計算任何結算金額/損益/勝率）。

用法：
  python3 step2_spread.py            # 逐日計算（有快取，可分批重跑），再彙總與畫圖
  python3 step2_spread.py --max-days N  # 本次最多新算 N 天（分批用）
  python3 step2_spread.py --done     # 讀取驗證結果，寫 DONE.txt

慣例：
- 第一筆成交：Shioaji ts >= t_fopen + 1 秒 且 < 08:50:00（t_fopen 為 FinMind 秒級時間）。
- 時間點 T 的「當下報價」：ts <= T 的最後一筆逐筆所附 bid/ask；bid 或 ask 為 0 視為 NaN。
- K 取整：floor(x/50 + 0.5)*50（四捨五入，不用銀行家捨入）。
"""
import argparse, json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = ROOT / 'results' / 'step2_spread'
CACHE = OUT / 'cache'
MIN_DATE = '2023-01-04'
SNAPS = ['08:45:30', '08:46:00', '08:47:00', '08:50:00', '09:00:00', '10:00:00', '12:00:00']
SNAP_TAG = {s: s[:5].replace(':', '') + ('30' if s.endswith('30') else '') for s in SNAPS}
# -> 084530, 0846, 0847, 0850, 0900, 1000, 1200


def tick_size(p):
    if p is None or not np.isfinite(p):
        return np.nan
    if p < 10: return 0.1
    if p < 50: return 0.5
    if p < 500: return 1.0
    if p < 1000: return 5.0
    return 10.0


def round50(x):
    return float(np.floor(x / 50.0 + 0.5) * 50.0)


def sj_dates():
    out = []
    for p in sorted((DATA / 'shioaji' / 'opt').glob('*.parquet')):
        d = p.stem
        try:
            pd.Timestamp(d)
        except Exception:
            continue
        if len(d) == 10 and d >= MIN_DATE:
            out.append(d)
    return out


_fut_cache = {}
def fut_month(ym):
    if ym not in _fut_cache:
        f = pd.read_parquet(DATA / 'finmind' / 'fut' / f'{ym}.parquet',
                            columns=['contract_date', 'date', 'price', 'volume'])
        f['contract_date'] = f['contract_date'].astype(str)
        _fut_cache[ym] = f
    return _fut_cache[ym]


def nz(x):
    x = float(x)
    return np.nan if x == 0 or not np.isfinite(x) else x


def series_block(sj, K, t_fopen, D, pre):
    """sj: Shioaji 當天 08:45–13:30 已排序資料。回傳某履約價 Call 的欄位 dict。"""
    r = {f'{pre}K': K}
    s = sj[(sj['strike'] == K) & (sj['cp'] == 'C')]
    t850 = pd.Timestamp(f'{D} 08:50:00')
    t845 = pd.Timestamp(f'{D} 08:45:00')
    r[f'{pre}n_ticks_day'] = len(s)
    thr = t_fopen + pd.Timedelta(seconds=1)
    first = s[(s['t'] >= thr) & (s['t'] < t850)]
    # 對照：嚴格大於 t_fopen（毫秒級）
    strict = s[(s['t'] > t_fopen) & (s['t'] < t850)]
    r[f'{pre}first_trade_strict'] = float(strict['close'].iloc[0]) if len(strict) else np.nan
    if len(first):
        f0 = first.iloc[0]
        r[f'{pre}status'] = 'traded'
        r[f'{pre}t_first'] = f0['t'].strftime('%H:%M:%S.%f')[:-3]
        r[f'{pre}sec_after_fopen'] = (f0['t'] - t_fopen).total_seconds()
        r[f'{pre}trade'] = float(f0['close'])
        r[f'{pre}bid'] = nz(f0['bid_price'])
        r[f'{pre}ask'] = nz(f0['ask_price'])
        r[f'{pre}tick_type'] = int(f0['tick_type'])
        r[f'{pre}first_vol'] = int(f0['volume'])
    else:
        r[f'{pre}status'] = 'no_trade_before_0850' if len(s) else 'no_ticks'
        for k in ['t_first', 'sec_after_fopen', 'trade', 'bid', 'ask', 'tick_type', 'first_vol']:
            r[f'{pre}{k}'] = np.nan
    tr = r[f'{pre}trade']
    tk = tick_size(tr)
    r[f'{pre}tick'] = tk
    r[f'{pre}ask_minus_trade'] = r[f'{pre}ask'] - tr
    r[f'{pre}spread_first'] = r[f'{pre}ask'] - r[f'{pre}bid']
    r[f'{pre}ask_minus_trade_ticks'] = r[f'{pre}ask_minus_trade'] / tk
    r[f'{pre}spread_first_ticks'] = r[f'{pre}spread_first'] / tk
    b_, a_ = r[f'{pre}bid'], r[f'{pre}ask']
    r[f'{pre}trade_outside_quote'] = (np.nan if (np.isnan(b_) or np.isnan(a_) or np.isnan(tr))
                                      else float(tr < b_ or tr > a_))
    for sn in SNAPS:
        T = pd.Timestamp(f'{D} {sn}')
        q = s[s['t'] <= T]
        tag = SNAP_TAG[sn]
        if len(q):
            b, a = nz(q['bid_price'].iloc[-1]), nz(q['ask_price'].iloc[-1])
            r[f'{pre}t_quote_{tag}'] = q['t'].iloc[-1].strftime('%H:%M:%S')
        else:
            b = a = np.nan
            r[f'{pre}t_quote_{tag}'] = None
        r[f'{pre}bid_{tag}'] = b
        r[f'{pre}ask_{tag}'] = a
        r[f'{pre}spread_{tag}'] = a - b
    w = s[(s['t'] >= t845) & (s['t'] < t850)]
    r[f'{pre}n_trades_0845_0850'] = len(w)
    r[f'{pre}vol_0845_0850'] = int(w['volume'].sum())
    ww = w[(w['bid_price'] > 0) & (w['ask_price'] > 0)]
    sp = ww['ask_price'] - ww['bid_price']
    r[f'{pre}spread_med_0845_0850'] = float(sp.median()) if len(sp) else np.nan
    r[f'{pre}spread_mean_0845_0850'] = float(sp.mean()) if len(sp) else np.nan
    return r


def finmind_first(D, K, t_fopen, offset_s=0):
    p = DATA / 'finmind' / 'opt' / f'{D}.parquet'
    if not p.exists():
        return np.nan, None
    o = pd.read_parquet(p, columns=['ExercisePrice', 'PutCall', 'date', 'price', 'volume'])
    o = o[(o['ExercisePrice'] == K) & (o['PutCall'] == 'C')].copy()
    o['t'] = pd.to_datetime(o['date'])
    o = o.sort_values('t', kind='stable')
    o = o[(o['t'] >= t_fopen + pd.Timedelta(seconds=offset_s)) & (o['t'] < pd.Timestamp(f'{D} 08:50:00'))]
    if not len(o):
        return np.nan, None
    return float(o['price'].iloc[0]), o['t'].iloc[0].strftime('%H:%M:%S')


def process_day(D, basis, cal):
    rec = {'date': D, 'kind': cal.get(D)}
    if D not in basis.index:
        rec['status'] = 'no_basis'
        return rec
    b = basis.loc[D]
    contract = str(int(b['contract']))
    rec['contract'] = contract
    rec['basis_prev'] = float(b['basis_prev'])
    f = fut_month(D[:7])
    f = f[(f['contract_date'] == contract) & (f['date'] >= f'{D} 08:45:00') & (f['date'] <= f'{D} 13:45:00')]
    f = f.sort_values('date', kind='stable')
    if not len(f):
        rec['status'] = 'no_fut'
        return rec
    t_fopen = pd.Timestamp(f['date'].iloc[0])
    F_open = float(f['price'].iloc[0])
    S_est = F_open - rec['basis_prev']
    rec.update(t_fopen=t_fopen.strftime('%H:%M:%S'), F_open=F_open, S_est=S_est)
    K_itm, K_atm = round50(S_est * 0.99), round50(S_est)
    sj = pd.read_parquet(DATA / 'shioaji' / 'opt' / f'{D}.parquet',
                         columns=['ts', 'close', 'volume', 'bid_price', 'ask_price', 'tick_type', 'strike', 'cp'])
    sj = sj[(sj['cp'] == 'C') & (sj['strike'].isin([K_itm, K_atm]))].copy()
    sj['t'] = pd.to_datetime(sj['ts'])
    sj = sj[(sj['t'] >= pd.Timestamp(f'{D} 08:45:00')) & (sj['t'] <= pd.Timestamp(f'{D} 13:30:00'))]
    sj = sj.sort_values('ts', kind='stable')
    for pre, K in [('itm_', K_itm), ('atm_', K_atm)]:
        rec.update(series_block(sj, K, t_fopen, D, pre))
        fm, fmt = finmind_first(D, K, t_fopen)
        rec[f'{pre}fm_first_trade'] = fm
        rec[f'{pre}fm_t_first'] = fmt
        tr = rec[f'{pre}trade']
        rec[f'{pre}fm_match'] = (np.nan if (np.isnan(fm) or np.isnan(tr)) else float(fm == tr))
        st = rec[f'{pre}first_trade_strict']
        rec[f'{pre}fm_match_vs_strict'] = (np.nan if (np.isnan(fm) or np.isnan(st)) else float(fm == st))
        fm1, fmt1 = finmind_first(D, K, t_fopen, offset_s=1)
        rec[f'{pre}fm_first_trade_plus1s'] = fm1
        rec[f'{pre}fm_match_plus1s'] = (np.nan if (np.isnan(fm1) or np.isnan(tr)) else float(fm1 == tr))
    rec['status'] = 'ok'
    return rec


def compute(max_days=None, recompute=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    basis = pd.read_csv(DATA / 'basis_prev.csv', dtype={'date': str}).drop_duplicates('date').set_index('date')
    cal = pd.read_csv(DATA / 'settlement_calendar.csv', dtype={'date': str}).drop_duplicates('date').set_index('date')['kind'].to_dict()
    n = 0
    for D in sj_dates():
        cp = CACHE / f'{D}.json'
        if cp.exists() and not recompute:
            continue
        if max_days is not None and n >= max_days:
            break
        rec = process_day(D, basis, cal)
        cp.write_text(json.dumps(rec, default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else x))
        n += 1
        print(D, rec.get('status'), rec.get('itm_status'), rec.get('itm_trade'), rec.get('itm_ask'), flush=True)
    return n


def q(s, p):
    s = s.dropna()
    return float(s.quantile(p)) if len(s) else np.nan


def summarize():
    recs = [json.loads(p.read_text()) for p in sorted(CACHE.glob('*.json'))]
    df = pd.DataFrame(recs).sort_values('date')
    df = df.replace({None: np.nan})
    df.to_csv(OUT / 'spread_by_day.csv', index=False, encoding='utf-8-sig')
    ok = df[df['status'] == 'ok']
    rows = []
    for pre, name in [('itm_', 'ITM1%'), ('atm_', 'ATM')]:
        traded = ok[ok[f'{pre}status'] == 'traded']
        amt = traded[f'{pre}ask_minus_trade'].astype(float)
        amtk = traded[f'{pre}ask_minus_trade_ticks'].astype(float)
        r = {'group': name, 'n_days': len(ok), 'n_traded': len(traded),
             'n_ask_available': int(amt.notna().sum())}
        for lab, s in [('amt', amt), ('amt_ticks', amtk)]:
            r[f'{lab}_mean'] = s.mean(); r[f'{lab}_median'] = s.median()
            r[f'{lab}_p25'] = q(s, .25); r[f'{lab}_p75'] = q(s, .75); r[f'{lab}_p90'] = q(s, .90); r[f'{lab}_max'] = s.max()
        r['pct_amt_gt_2ticks'] = float((amtk.dropna() > 2).mean()) if amtk.notna().any() else np.nan
        r['pct_amt_le_0'] = float((amt.dropna() <= 0).mean()) if amt.notna().any() else np.nan
        tt = traded[f'{pre}tick_type'].astype(float).value_counts()
        for k, lab in [(1, 'buy_initiated'), (2, 'sell_initiated'), (0, 'unknown')]:
            r[f'first_tick_type_{k}_{lab}'] = int(tt.get(float(k), 0))
        r['sec_after_fopen_median'] = traded[f'{pre}sec_after_fopen'].astype(float).median()
        r['trade_price_median'] = traded[f'{pre}trade'].astype(float).median()
        sfk = traded[f'{pre}spread_first'].astype(float)
        r['spread_first_median'] = sfk.median(); r['spread_first_mean'] = sfk.mean()
        for sn in SNAPS:
            sp = ok[f'{pre}spread_{SNAP_TAG[sn]}'].astype(float)
            r[f'spread_{SNAP_TAG[sn]}_median'] = sp.median(); r[f'spread_{SNAP_TAG[sn]}_mean'] = sp.mean()
            r[f'spread_{SNAP_TAG[sn]}_n'] = int(sp.notna().sum())
        r['spread_0845_0850_daymedian_median'] = ok[f'{pre}spread_med_0845_0850'].astype(float).median()
        r['n_trades_0845_0850_median'] = ok[f'{pre}n_trades_0845_0850'].astype(float).median()
        r['vol_0845_0850_median'] = ok[f'{pre}vol_0845_0850'].astype(float).median()
        m = ok[f'{pre}fm_match'].astype(float).dropna()
        r['fm_match_n'] = len(m); r['fm_match_pct'] = m.mean() if len(m) else np.nan
        for sfx in ['vs_strict', 'plus1s']:
            m2 = ok[f'{pre}fm_match_{sfx}'].astype(float).dropna()
            r[f'fm_match_{sfx}_n'] = len(m2); r[f'fm_match_{sfx}_pct'] = m2.mean() if len(m2) else np.nan
        oq = traded[f'{pre}trade_outside_quote'].astype(float).dropna()
        r['n_trade_outside_quote'] = int(oq.sum())
        inq = traded[traded[f'{pre}trade_outside_quote'] == 0]
        r['amt_median_trade_within_quote'] = inq[f'{pre}ask_minus_trade'].astype(float).median()
        r['amt_mean_trade_within_quote'] = inq[f'{pre}ask_minus_trade'].astype(float).mean()
        r['amt_p90_trade_within_quote'] = q(inq[f'{pre}ask_minus_trade'].astype(float), .9)
        ms = (traded[f'{pre}first_trade_strict'].astype(float) == traded[f'{pre}trade'].astype(float))
        r['strict_vs_plus1s_same_price_pct'] = ms.mean() if len(ms) else np.nan
        for kd in ['W', 'F', 'M']:
            sub = traded[traded['kind'] == kd]
            r[f'amt_mean_{kd}'] = sub[f'{pre}ask_minus_trade'].astype(float).mean()
            r[f'amt_ticks_mean_{kd}'] = sub[f'{pre}ask_minus_trade_ticks'].astype(float).mean()
            r[f'n_traded_{kd}'] = len(sub)
        rows.append(r)
    summ = pd.DataFrame(rows)
    summ.T.to_csv(OUT / 'summary.csv', header=False, encoding='utf-8-sig')
    plots(ok, summ)
    return df, summ


def setup_font():
    import matplotlib.font_manager as fm, subprocess
    import matplotlib
    cands = ['/System/Library/Fonts/PingFang.ttc']
    try:
        outp = subprocess.run(['fc-list', ':lang=zh', 'file'], capture_output=True, text=True).stdout
        cands += [l.split(':')[0].strip() for l in outp.splitlines() if 'Noto' in l and 'CJK' in l]
    except Exception:
        pass
    for c in cands:
        if Path(c).exists():
            try:
                fm.fontManager.addfont(c)
                name = fm.FontProperties(fname=c).get_name()
                matplotlib.rcParams['font.family'] = name
                matplotlib.rcParams['axes.unicode_minus'] = False
                return True
            except Exception:
                continue
    return False


def plots(ok, summ):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    zh = setup_font()
    labels = ['第一筆成交' if zh else 'first trade'] + [s[:5] if not s.endswith('30') else s for s in SNAPS]
    fig, ax = plt.subplots(figsize=(9, 5))
    for pre, name, col in [('itm_', 'ITM1%', '#2a78d6'), ('atm_', 'ATM', '#eb6834')]:
        tr = ok[ok[f'{pre}status'] == 'traded']
        ys = [tr[f'{pre}spread_first'].astype(float).median()] + \
             [ok[f'{pre}spread_{SNAP_TAG[s]}'].astype(float).median() for s in SNAPS]
        ax.plot(range(len(labels)), ys, marker='o', color=col, lw=2, label=f'{name} Call')
        for i, y in enumerate(ys):
            if np.isfinite(y):
                ax.annotate(f'{y:g}', (i, y), textcoords='offset points', xytext=(0, 7), ha='center', fontsize=8, color=col)
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels)
    ax.set_ylabel('ask − bid 中位數（點）' if zh else 'median ask − bid (pts)')
    ax.set_title(('結算日 Call 買賣價差隨時間變化' if zh else 'Settlement-day call spread over time') + f'  (n={len(ok)})')
    ax.grid(alpha=.3); ax.legend(frameon=False)
    ax.set_ylim(bottom=0)
    fig.tight_layout(); fig.savefig(OUT / 'spread_over_time.png', dpi=140); plt.close(fig)

    tr = ok[ok['itm_status'] == 'traded']
    s = tr['itm_ask_minus_trade'].astype(float).dropna()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if len(s):
        cap = 500.0
        shown, n_out = s[s <= cap], int((s > cap).sum())
        ax.hist(shown, bins=np.arange(min(0, np.floor(shown.min() / 10) * 10), cap + 10, 10), color='#2a78d6', edgecolor='white')
        if n_out:
            ax.text(0.98, 0.95, (f'另有 {n_out} 天 > {cap:g} 點未顯示（最大 {s.max():g}）' if zh else f'{n_out} day(s) > {cap:g} not shown (max {s.max():g})'),
                    transform=ax.transAxes, ha='right', va='top', fontsize=9, color='#555')
        ax.axvline(s.median(), color='#333', ls='--', lw=1)
        ax.text(s.median(), ax.get_ylim()[1] * .92, (f' 中位數 {s.median():g}' if zh else f' median {s.median():g}'), fontsize=9)
    ax.set_xlabel('ask − 第一筆成交價（點）' if zh else 'ask − first trade (pts)')
    ax.set_ylabel('天數' if zh else 'days')
    ax.set_title(('ITM1% Call：第一筆成交當下 ask − 成交價' if zh else 'ITM1% call: ask − first trade') + f'  (n={len(s)})')
    ax.grid(alpha=.3, axis='y')
    fig.tight_layout(); fig.savefig(OUT / 'hist_ask_minus_trade.png', dpi=140); plt.close(fig)


def write_done():
    df = pd.read_csv(OUT / 'spread_by_day.csv', dtype={'date': str})
    summ = pd.read_csv(OUT / 'summary.csv', header=None, index_col=0).T.set_index('group')
    ver = pd.read_csv(OUT / 'verify.csv', dtype={'date': str})
    ok = df[df['status'] == 'ok']
    i, a = summ.loc['ITM1%'], summ.loc['ATM']
    f = lambda x: f'{float(x):.2f}'
    pv = ver['all_match'].astype(str).str.lower().eq('true')
    lines = [
        f'Step2 開盤進場成本驗證（只看報價/成交價，無任何損益計算）。樣本 {len(ok)} 天：{ok.date.min()} → {ok.date.max()}（Shioaji 目前已下載的全部 >= 2023-01-04 檔案）。',
        f'ITM1% Call 有 08:50 前第一筆成交 {int(float(i.n_traded))} 天；ATM {int(float(a.n_traded))} 天。第一筆成交定義：ts >= t_fopen + 1 秒。',
        f'ITM1% ask − 第一筆成交：平均 {f(i.amt_mean)}、中位數 {f(i.amt_median)}、P90 {f(i.amt_p90)}、最大 {f(i.amt_max)} 點；以跳動點計 平均 {f(i.amt_ticks_mean)}、中位數 {f(i.amt_ticks_median)}、P90 {f(i.amt_ticks_p90)}。',
        f'ITM1% ask − trade > 2 跳動點比例 {float(i.pct_amt_gt_2ticks):.1%}；ATM 對照：平均 {f(a.amt_mean)} 點、中位數 {f(a.amt_median)}、>2 跳比例 {float(a.pct_amt_gt_2ticks):.1%}。',
        f'第一筆成交 tick_type（ITM1%）：外盤 {int(float(i.first_tick_type_1_buy_initiated))}、內盤 {int(float(i.first_tick_type_2_sell_initiated))}、不明 {int(float(i.first_tick_type_0_unknown))}。',
        f'ITM1% spread 中位數：第一筆 {f(i.spread_first_median)} → 08:45:30 {f(i.spread_084530_median)} → 08:47 {f(i.spread_0847_median)} → 09:00 {f(i.spread_0900_median)} → 10:00 {f(i.spread_1000_median)} → 12:00 {f(i.spread_1200_median)} 點。',
        f'ATM spread 中位數：第一筆 {f(a.spread_first_median)} → 08:45:30 {f(a.spread_084530_median)} → 09:00 {f(a.spread_0900_median)} → 12:00 {f(a.spread_1200_median)} 點。',
        f'FinMind(>=t_fopen) vs Shioaji 第一筆成交價相同：對 +1秒版 ITM1% {float(i.fm_match_pct):.1%}／ATM {float(a.fm_match_pct):.1%}；對嚴格大於(毫秒)版 ITM1% {float(i.fm_match_vs_strict_pct):.1%}／ATM {float(a.fm_match_vs_strict_pct):.1%}；兩邊都用 +1秒 ITM1% {float(i.fm_match_plus1s_pct):.1%}／ATM {float(a.fm_match_plus1s_pct):.1%}。',
        f'獨立驗證（pyarrow 重算 F_open/K/第一筆時間價格 bid/ask）抽 {len(ver)} 天 {", ".join(ver.date)}：' + ('全部一致。' if pv.all() else f'不一致 {int((~pv).sum())} 天，見 verify.csv。'),
        f'注意：bid/ask 是成交所附最佳一檔，非連續快照；ITM1% 有 {int(float(i.n_trade_outside_quote))} 天第一筆成交價落在 [bid, ask] 外（報價可能滯後），排除後 ask−trade 中位數 {f(i.amt_median_trade_within_quote)}、P90 {f(i.amt_p90_trade_within_quote)} 點。',
    ]
    (OUT / 'DONE.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-days', type=int, default=None)
    ap.add_argument('--done', action='store_true')
    ap.add_argument('--no-summary', action='store_true')
    ap.add_argument('--recompute', action='store_true', help='忽略快取並覆寫')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.done:
        write_done(); sys.exit(0)
    n = compute(a.max_days, a.recompute)
    remaining = [d for d in sj_dates() if not (CACHE / f'{d}.json').exists()]
    print(f'new={n} remaining={len(remaining)}')
    if not remaining and not a.no_summary:
        summarize(); print('summary written')
