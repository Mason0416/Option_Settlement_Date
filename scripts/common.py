import os, shioaji as sj
from pathlib import Path
def load_env():
    env={}
    for l in Path(str(Path(__file__).resolve().parent.parent/'.env')).read_text().splitlines():
        if '=' in l: k,v=l.split('=',1); env[k.strip()]=v.strip().strip('"\'')
    return env
def login():
    env=load_env(); api=sj.Shioaji()
    api.login(api_key=env['SJ_API_KEY'], secret_key=env['SJ_SEC_KEY'], subscribe_trade=False, force_refresh=True)
    return api
