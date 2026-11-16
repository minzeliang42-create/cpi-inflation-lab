"""Compare unchanged V1 fields, retaining every focus-month result for review."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cpi.model import ROOT,load_inputs,calculate,records,write_json

o,c=load_inputs();groups,details=calculate(o,c)
baselines=sorted((ROOT/'dist/data').glob('*-6064bdf8/research.json'))
assert baselines,'V1 baseline release required'
old=json.loads(baselines[0].read_text(encoding='utf-8'))
error=0;count=0
for key,rows in old['groups'].items():
    current=groups[key].set_index('month')
    for row in rows:
        for column,value in row.items():
            if isinstance(value,(int,float)) and not isinstance(value,bool):
                error=max(error,abs(float(current.at[row['month'],column])-value));count+=1
assert error<1e-10,(count,error)
report=dict(baseline=old['meta']['version'],existing_numeric_fields=count,max_absolute_difference=error,
            input_revisions=0,focus={k:records(v[v.month.isin(['2024-12','2025-10','2026-09','2026-10'])]) for k,v in groups.items()})
write_json(ROOT/'VALIDATION_V1_1.json',report)
for month in ['2024-12','2025-10','2026-09','2026-10']:
    r=groups['acceleration'].set_index('month').loc[month]
    print(month, 'Headline/Core/Median acceleration:',r['headline'],r['core'],r['p50'])
print('Existing fields:',count,'maximum difference:',error)
