"""Read-only deployed artifact reconciliation; no GitHub credentials required."""
from pathlib import Path
import json,io
import pandas as pd
import requests
from cpi.forecast_engine import FIELDS
base='https://minzeliang42-create.github.io/cpi-inflation-lab/'
def fetch(path):
    r=requests.get(base+path,timeout=60);r.raise_for_status();return r
pointer=fetch('current_forecast.json').json();data=fetch(pointer['path']).json()
folder=pointer['path'].replace('forecast.json','')
xlsx=fetch(folder+'CPI_Forecast.xlsx').content
out=Path('output');out.mkdir(exist_ok=True);(out/'CPI_Forecast.xlsx').write_bytes(xlsx)
(out/'Forecast_Research_Report.md').write_bytes(fetch(folder+'Research_Report.md').content)
excel=pd.read_excel(io.BytesIO(xlsx),sheet_name='Forecast_Indicators').set_index(['scenario','group','month'])
checked=0
for scenario,s in data['scenarios'].items():
    for group,rows in s['groups'].items():
        csv=pd.read_csv(io.StringIO(fetch(folder+group+'_forecast.csv').text.lstrip('\ufeff'))).set_index(['scenario','month'])
        for r in rows:
            for g,f in FIELDS:
                if g!=group:continue
                e=excel.loc[(scenario,group,r['month']),f];c=csv.loc[(scenario,r['month']),f]
                if r[f] is None:assert pd.isna(e) and pd.isna(c)
                else:assert abs(r[f]-e)<1e-10 and abs(r[f]-c)<1e-10
                checked+=1
result=dict(url=base,version=pointer['version'],forecast_asof=data['meta']['asof'],
    end=data['meta']['forecast_end'],xlsx_bytes=len(xlsx),matched_values=checked,
    status=fetch('forecast_status.json').json(),official_update=fetch('status.json').json()['state'])
(out/'V2_LIVE_VALIDATION.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
