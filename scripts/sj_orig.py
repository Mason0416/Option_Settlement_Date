# 最原始版本：登入 -> api.ticks(contract, date)。不做任何額度判斷或檢查。
import shioaji as sj, pandas as pd
from pathlib import Path
env={}
for l in (Path(__file__).resolve().parent.parent/'.env').read_text().splitlines():
    if '=' in l: k,v=l.split('=',1); env[k.strip()]=v.strip().strip('"\'')
api=sj.Shioaji()
api.login(api_key=env['SJ_API_KEY'], secret_key=env['SJ_SEC_KEY'])
print(api.usage())
for code,date in [('TX244000R6','2026-06-10'),('TX243500R6','2026-06-10'),('TXV44700F6','2026-06-12'),('TXX47100I6','2026-09-18')]:
    contract=sj.Option(code=code, exchange='TAIFEX', security_type='OPT')
    ticks=api.ticks(contract, date)
    df=pd.DataFrame({**ticks})
    print(code, date, 'rows', len(df))
print(api.usage())
api.logout()
