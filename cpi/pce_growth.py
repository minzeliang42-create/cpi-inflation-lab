"""SF Fed published diffusion growth; separate from CPI and PCE Measures."""
import csv,hashlib,io,json,math
from datetime import datetime,timezone
from pathlib import Path
import openpyxl,requests
ROOT=Path(__file__).resolve().parents[1]
SOURCE='https://www.frbsf.org/wp-content/uploads/pce-releases.xlsx'
PAGE='https://www.frbsf.org/research-and-insights/data-and-indicators/pce-personal-consumption-expenditure-price-index-pcepi/'
HEADERS={'items_pct':'Fraction of items with price increases','weight_pct':'Share of expenditures with price increases'}
def parse(content):
    book=openpyxl.load_workbook(io.BytesIO(content),read_only=True,data_only=True)
    if 'Datasheet' not in book.sheetnames:raise ValueError('PCE Datasheet missing')
    values=iter(book['Datasheet'].values);header=list(next(values))
    if header.count('Month')!=1 or any(header.count(h)!=1 for h in HEADERS.values()):raise ValueError('PCE growth named-field schema changed')
    positions={k:header.index(v) for k,v in HEADERS.items()};datecol=header.index('Month');rows=[]
    for row in values:
        if not isinstance(row[datecol],datetime):continue
        record={'month':row[datecol].strftime('%Y-%m')}
        for field,col in positions.items():
            v=row[col]
            if isinstance(v,(int,float)) and math.isfinite(v):
                # Official binary floating-point sums can exceed 100 by ~4e-14.
                # Preserve source values exactly; reject economically invalid bounds.
                if not -1e-9<=v<=100+1e-9:raise ValueError('PCE growth share outside 0–100')
                record[field]=float(v)
            else:record[field]=None
        rows.append(record)
    if len(rows)<100 or len({r['month'] for r in rows})!=len(rows):raise ValueError('PCE growth sample/duplicate months invalid')
    return sorted(rows,key=lambda r:r['month']),{k:{'header':HEADERS[k],'excel_column_1based':col+1} for k,col in positions.items()}
def failure(error,root=ROOT):
    path=Path(root)/'web/pce_growth_status.json';path.write_text(json.dumps(dict(state='failed',checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),message=str(error),retained_last_good=(Path(root)/'web/pce_growth.json').exists())),encoding='utf-8')
def write_snapshot(content,stamp=None,last_modified=None,root=ROOT):
    stamp=stamp or datetime.now(timezone.utc).isoformat(timespec='seconds');rows,columns=parse(content);web=Path(root)/'web';target=web/'pce_growth.json'
    if target.exists() and rows[-1]['month']<json.loads(target.read_text(encoding='utf-8'))['meta']['end']:raise ValueError('PCE growth history regressed')
    meta=dict(source=SOURCE,page=PAGE,sheet='Datasheet',columns=columns,unit='percent (0–100)',publication_basis='3-month moving average, as stated in SF Fed ordinary diffusion table footnote',transformation='Published workbook values copied unchanged; no additional smoothing or CPI reconstruction',fetched_at=stamp,source_last_modified=last_modified,source_sha256=hashlib.sha256(content).hexdigest(),start=rows[0]['month'],end=rows[-1]['month'],missing={k:[r['month'] for r in rows if r[k] is None] for k in HEADERS})
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(dict(meta=meta,rows=rows),ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8');temp.replace(target)
    stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=['month',*HEADERS]);w.writeheader();w.writerows(rows);(web/'pce_growth.csv').write_text(stream.getvalue(),encoding='utf-8-sig')
    (web/'pce_growth_status.json').write_text(json.dumps(dict(state='success',checked_at=stamp,last_success=stamp)),encoding='utf-8');return dict(meta=meta,rows=rows)
def update():
    try:
        s=requests.Session()
        try:r=s.get(SOURCE,timeout=45);r.raise_for_status()
        except requests.RequestException:s.trust_env=False;r=s.get(SOURCE,timeout=45);r.raise_for_status()
        p=write_snapshot(r.content,last_modified=r.headers.get('Last-Modified'));print(json.dumps(dict(start=p['meta']['start'],end=p['meta']['end'],latest=p['rows'][-1])))
    except Exception as e:failure(e);print(json.dumps(dict(state='failed',message=str(e))))
if __name__=='__main__':update()
