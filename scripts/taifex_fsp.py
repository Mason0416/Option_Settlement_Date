import requests, pandas as pd, io, re, os, time
D=os.path.expanduser('~/mnt/選擇權_結算日/data')
out=[]
for y in range(2001,2027):
    r=requests.post('https://www.taifex.com.tw/cht/5/optIndxFSP',data={'start_year':y,'start_month':'01','end_year':y,'end_month':'12','commodityIds':'2'},timeout=60)
    r.encoding='utf-8'
    try: tabs=pd.read_html(io.StringIO(r.text))
    except Exception as e: print(y,'no table'); continue
    t=[x for x in tabs if x.astype(str).apply(lambda c:c.str.contains('TXO|臺指選擇權',regex=True)).any().any() or any('臺指' in str(c) for c in x.columns)]
    t=t[0] if t else max(tabs,key=len)
    t.columns=['_'.join(map(str,c)) if isinstance(c,tuple) else str(c) for c in t.columns]
    t['q_year']=y; out.append(t); print(y,len(t)); time.sleep(0.5)
df=pd.concat(out); df.to_csv('taifex_fsp_raw.csv',index=False); print(df.columns.tolist()); print(df.head(3).to_string())
