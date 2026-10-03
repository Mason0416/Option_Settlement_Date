"""獨立驗證：隨機抽 3 個結算日，只用原始 parquet（逐列字典運算，不共用 step2_inst.py 程式）重算 8 指標，與 trades_inst.csv 比對。"""
import random, math, sys
from pathlib import Path
import pyarrow.parquet as pq
import csv
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT/'data'/'finmind'/'inst'
rows = lambda n: pq.read_table(RAW/f'{n}.parquet').to_pylist()

fut = [r for r in rows('TaiwanFuturesInstitutionalInvestors') if r['futures_id'] == 'TX']
fdates = sorted({r['date'] for r in fut})
fnet = {(r['date'], r['institutional_investors']): r['long_open_interest_balance_volume'] - r['short_open_interest_balance_volume'] for r in fut}
opt = [r for r in rows('TaiwanOptionInstitutionalInvestors') if r['option_id'] == 'TXO']
onet = {(r['date'], r['call_put'], r['institutional_investors']): r['long_open_interest_balance_amount'] - r['short_open_interest_balance_amount'] for r in opt}
spot = {}
for r in rows('TaiwanStockTotalInstitutionalInvestors'):
    spot[(r['date'], r['name'])] = r['buy'] - r['sell']

def calc(pd_):
    out = {}
    i = fdates.index(pd_) if pd_ in fdates else None
    for k, inv in [('fut_foreign_oi_chg', '外資'), ('fut_trust_oi_chg', '投信'), ('fut_dealer_oi_chg', '自營商')]:
        out[k] = fnet[(pd_, inv)] - fnet[(fdates[i-1], inv)] if i else float('nan')
    for k, inv in [('opt_foreign_dir', '外資'), ('opt_dealer_dir', '自營商')]:
        out[k] = onet[(pd_, '買權', inv)] - onet[(pd_, '賣權', inv)] if (pd_, '買權', inv) in onet else float('nan')
    out['spot_foreign_net'] = spot[(pd_, 'Foreign_Investor')]
    out['spot_trust_net'] = spot[(pd_, 'Investment_Trust')]
    out['spot_dealer_net'] = spot[(pd_, 'Dealer_self')] + spot[(pd_, 'Dealer_Hedging')]
    return out

tr = [r for r in csv.DictReader(open(ROOT/'results'/'step2_inst'/'trades_inst.csv')) if r['status'] == 'ok']
cand = [r for r in tr if r['fut_foreign_oi_chg'] != '']
random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 20260925)
pick = random.sample(cand, 2) + random.sample([r for r in tr if r['fut_foreign_oi_chg'] == ''], 1)
allok = True
for r in sorted(pick, key=lambda x: x['date']):
    v = calc(r['prev_date'])
    bad = []
    for k, x in v.items():
        y = float(r[k]) if r[k] != '' else float('nan')
        same = (math.isnan(x) and math.isnan(y)) or abs(x - y) < 1e-6
        if not same: bad.append((k, x, y))
        if r[k] != '': assert r[k + '_data_date'] == r['prev_date'] != r['date']
    allok &= not bad
    print(r['date'], 'prev', r['prev_date'], 'OK' if not bad else f'MISMATCH {bad}', {k: v[k] for k in v})
print('ALL_MATCH' if allok else 'FAIL')
