import os, time, pandas as pd, sj_pull
from pathlib import Path
HERE=Path(__file__).resolve().parent
cal=pd.read_csv(HERE/'cal_exclude_today.csv',parse_dates=['date'])
# main set: 2023+ (bid/ask era)
main_dates=cal[cal.date>='2023-01-01'].date.dt.strftime('%Y-%m-%d').tolist()
# fill set: 2020-03+ settlement days where FinMind has no day-session option trades
FILL=['2020-05-20','2020-06-17','2020-07-22','2020-07-29','2020-08-05','2020-08-12','2020-08-19','2020-08-26',
      '2020-09-02','2020-09-09','2020-09-23','2020-12-23','2021-01-06','2021-02-24','2021-05-05']
want=main_dates+FILL
# cleanup: remove files saved empty / incomplete by the old version (quota exhausted -> 'not found')
REDO={'2026-06-12'}
for d in want:
    p=f'{sj_pull.OUT}/{d}.parquet'
    if os.path.exists(p):
        try: n=len(pd.read_parquet(p,columns=['ts']))
        except Exception: n=0
        if n==0 or d in REDO:
            os.remove(p); sj_pull.log('removed bad file',d,'rows',n)
while True:
    miss=[d for d in want if not os.path.exists(f'{sj_pull.OUT}/{d}.parquet')]
    if not miss: sj_pull.log('SJ COMPLETE'); break
    sj_pull.log('missing',len(miss))
    try: sj_pull.main('2000-01-01','2099-12-31',dates=miss)
    except Exception as e: sj_pull.log('main crashed',repr(e)[:200])
    time.sleep(60)
