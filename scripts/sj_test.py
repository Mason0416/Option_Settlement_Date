# quick diagnostic: what does THIS machine get back from Shioaji?
import sys, platform, pandas as pd, shioaji as sj
from common import login
print('python', sys.version.split()[0], platform.machine(), '| shioaji', sj.__version__, '| pandas', pd.__version__)
api=login(); print(api.usage())
for c,d in [('TX244000R6','2026-06-10'),('TXV44700F6','2026-06-12'),('TXX47100I6','2026-09-18')]:
    try:
        t=api.ticks(sj.Option(code=c,exchange='TAIFEX',security_type='OPT'),date=d)
        x=pd.DataFrame({**t}); ts=pd.to_datetime(x.ts) if len(x) else None
        print(c,d,'rows',len(x), ts.min() if len(x) else '', ts.max() if len(x) else '')
    except Exception as e:
        print(c,d,'EXCEPTION',type(e).__name__, str(e)[:300])
print(api.usage()); api.logout()
