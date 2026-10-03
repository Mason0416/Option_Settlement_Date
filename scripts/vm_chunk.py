# run inside the Cowork VM in <=3-minute chunks: worker w of n pulls missing dates until time budget is used
import os, sys, time
import sj_pull, pandas as pd
from pathlib import Path
w,n,budget=int(sys.argv[1]),int(sys.argv[2]),float(sys.argv[3])
HERE=Path(__file__).resolve().parent
cal=pd.read_csv(HERE/'cal_exclude_today.csv',parse_dates=['date'])
want=cal[cal.date>='2023-01-01'].date.dt.strftime('%Y-%m-%d').tolist()+['2020-05-20','2020-06-17','2020-07-22','2020-07-29','2020-08-05','2020-08-12','2020-08-19','2020-08-26','2020-09-02','2020-09-09','2020-09-23','2020-12-23','2021-01-06','2021-02-24','2021-05-05']
miss=sorted([d for d in want if not os.path.exists(f'{sj_pull.OUT}/{d}.parquet')],reverse=True)
mine=miss[w::n]
t0=time.time()
for d in mine:
    if time.time()-t0>budget: break
    sj_pull.main('2000-01-01','2099-12-31',dates=[d])
if w==0: print('REMAINING', len([d for d in want if not os.path.exists(f'{sj_pull.OUT}/{d}.parquet')]))
