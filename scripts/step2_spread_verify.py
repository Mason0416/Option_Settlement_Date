"""step2_spread 的獨立驗證：不 import step2_spread，只用 pyarrow + csv/datetime 重算
F_open、K（ITM1%/ATM）、第一筆成交（ts >= t_fopen+1s 且 < 08:50）的時間/價格/bid/ask，與 spread_by_day.csv 比對。"""
import csv, random, math, datetime as dt
from pathlib import Path
import pyarrow.parquet as pq
import pyarrow.compute as pc

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'results' / 'step2_spread'

rows = list(csv.DictReader(open(OUT / 'spread_by_day.csv', encoding='utf-8-sig')))
rows = [r for r in rows if r['status'] == 'ok']
random.seed(20260925)
pick = random.sample(rows, 3)

basis = {r['date']: r for r in csv.DictReader(open(ROOT / 'data' / 'basis_prev.csv'))}

def r50(x):
    return math.floor(x / 50 + 0.5) * 50

def close(a, b, tol=1e-6):
    if a in ('', None) and (b is None or (isinstance(b, float) and math.isnan(b))):
        return True
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return str(a) == str(b)

out = []
for r in pick:
    D = r['date']
    b = basis[D]
    t = pq.read_table(ROOT / 'data' / 'finmind' / 'fut' / f'{D[:7]}.parquet', columns=['contract_date', 'date', 'price'])
    t = t.filter(pc.and_(pc.equal(pc.cast(t['contract_date'], 'string'), str(int(float(b['contract'])))),
                         pc.and_(pc.greater_equal(t['date'], f'{D} 08:45:00'), pc.less_equal(t['date'], f'{D} 13:45:00'))))
    dates, prices = t['date'].to_pylist(), t['price'].to_pylist()
    # 自己找最小時間的第一筆（原始順序中第一個出現最小時間者 = stable）
    mn = min(dates); j = dates.index(mn)
    F_open, t_fopen = prices[j], dt.datetime.strptime(mn, '%Y-%m-%d %H:%M:%S')
    S = F_open - float(b['basis_prev'])
    K_itm, K_atm = r50(S * 0.99), r50(S)
    sj = pq.read_table(ROOT / 'data' / 'shioaji' / 'opt' / f'{D}.parquet').to_pylist()
    res = {'date': D, 'F_open': F_open, 't_fopen': t_fopen.strftime('%H:%M:%S'), 'K_itm': K_itm, 'K_atm': K_atm}
    ok = close(r['F_open'], F_open) and r['t_fopen'] == res['t_fopen'] and close(r['itm_K'], K_itm) and close(r['atm_K'], K_atm)
    lo = t_fopen + dt.timedelta(seconds=1); hi = dt.datetime.strptime(f'{D} 08:50:00', '%Y-%m-%d %H:%M:%S')
    for pre, K in [('itm_', K_itm), ('atm_', K_atm)]:
        c = []
        for x in sj:
            if x['cp'] != 'C' or x['strike'] != K:
                continue
            tt = dt.datetime(1970, 1, 1) + dt.timedelta(microseconds=x['ts'] // 1000)
            if lo <= tt < hi:
                c.append((x['ts'], tt, x))
        c.sort(key=lambda z: z[0])
        if c:
            _, tt, x = c[0]
            bid = x['bid_price'] if x['bid_price'] > 0 else float('nan')
            ask = x['ask_price'] if x['ask_price'] > 0 else float('nan')
            v = dict(t_first=tt.strftime('%H:%M:%S.%f')[:-3], trade=x['close'], bid=bid, ask=ask)
        else:
            v = dict(t_first='', trade=float('nan'), bid=float('nan'), ask=float('nan'))
        for k, val in v.items():
            res[pre + k] = val
            ok = ok and (r[pre + k] == val if k == 't_first' else close(r[pre + k], val))
    res['all_match'] = ok
    out.append(res)
    print(res)

with open(OUT / 'verify.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader(); w.writerows(out)
