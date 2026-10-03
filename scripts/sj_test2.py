# diagnostic 2: raw Ticks object vs DataFrame conversion, several contracts
import sys, platform, pandas as pd, shioaji as sj, pyarrow
from pathlib import Path
from common import login
from sj_pull import code
print('python', sys.version.split()[0], platform.machine(), '| shioaji', sj.__version__, '| pandas', pd.__version__, '| pyarrow', pyarrow.__version__)
api=login()
D=Path(__file__).resolve().parent.parent/'data'
cal=pd.read_csv(D/'settlement_calendar.csv').set_index('date')
tests=[]
for ds in ['2026-06-10','2026-06-05','2026-05-27','2026-06-12']:
    o=pd.read_parquet(D/'finmind'/'opt'/f'{ds}.parquet'); t=pd.to_datetime(o.date); o=o[(t.dt.strftime('%Y-%m-%d')==ds)&(t.dt.hour>=8)]
    top=o.groupby(['ExercisePrice','PutCall']).volume.sum().sort_values().tail(2)
    for (k,cp),v in top.items(): tests.append((code(cal.loc[ds,'contract_month'],k,cp),ds,int(v//2)))
for c,ds,fmv in tests:
    try:
        t=api.ticks(sj.Option(code=c,exchange='TAIFEX',security_type='OPT'),date=ds)
        raw_len=len(t.ts) if hasattr(t,'ts') else 'n/a'
        try: n_df=len(pd.DataFrame({**t}))
        except Exception as e: n_df='DF ERROR '+repr(e)[:150]
        print(f'{c} {ds} type={type(t).__name__} raw_ts_len={raw_len} df_rows={n_df} finmind_day_vol={fmv}')
    except Exception as e:
        print(c,ds,'EXCEPTION',type(e).__name__,str(e)[:300])
print(api.usage()); api.logout()
