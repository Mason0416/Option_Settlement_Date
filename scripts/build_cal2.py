import pandas as pd, os
D=os.path.expanduser('~/mnt/選擇權_結算日/data')
t=pd.read_csv('taifex_fsp_raw.csv')
t.columns=['date','contract_month','q_year','ssp']
t['date']=pd.to_datetime(t.date); t['contract_month']=t.contract_month.astype(str).str.strip()
t=t.drop(columns='q_year').drop_duplicates().sort_values('date').reset_index(drop=True)
t['kind']=t.contract_month.str[6:7].replace('', 'M')
t['week']=pd.to_numeric(t.contract_month.str[7:],errors='coerce')
t['weekday']=t.date.dt.day_name().str[:3]
t.to_csv(f'{D}/settlement_calendar.csv',index=False)
print(len(t)); print(t.groupby('kind').date.agg(['min','max','count'])); print(t.weekday.value_counts().to_dict())
f=pd.read_csv('fsp_all.csv'); f['date']=pd.to_datetime(f.date)
m=t.merge(f[['date','contract_month','settlement_price']],on=['date','contract_month'],how='outer',indicator=True)
print(m._merge.value_counts().to_dict()); both=m[m._merge=='both']; print('ssp mismatch',(both.ssp!=both.settlement_price).sum())
print(m[m._merge!='both'].groupby([m.date.dt.year,'_merge']).size().to_dict())
print(t[(t.kind=='W')].date.min(), t[t.kind=='F'].date.min())
