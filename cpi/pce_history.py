"""Independent SF Fed PCE history. Never touches CPI or forecast inputs."""
import csv,hashlib,io,json,math,re
from datetime import datetime,timezone
from pathlib import Path
import requests,openpyxl
ROOT=Path(__file__).resolve().parents[1]
SOURCE='https://www.frbsf.org/wp-content/uploads/pce-releases.xlsx'
PAGE='https://www.frbsf.org/research-and-insights/data-and-indicators/pce-personal-consumption-expenditure-price-index-pcepi/'
FIELDS=['headline','core','p10','p25','p50','p75','p90']
HEADERS=['Month','PCE total','PCE core','PCE 10th percentile','PCE 25th percentile','PCE median','PCE 75th percentile','PCE 90th percentile']
def parse(content):
    ws=openpyxl.load_workbook(io.BytesIO(content),data_only=True,read_only=True)['Datasheet']
    values=iter(ws.values)
    if list(next(values))[:8]!=HEADERS: raise ValueError('PCE workbook schema changed')
    rows=[]
    for row in values:
        if not isinstance(row[0],datetime): continue
        record={'month':row[0].strftime('%Y-%m')}
        for field,v in zip(FIELDS,row[1:8]): record[field]=float(v) if isinstance(v,(int,float)) and math.isfinite(v) else None
        q=[record[k] for k in ['p10','p25','p50','p75','p90']]
        if all(v is not None for v in q) and q!=sorted(q): raise ValueError('Unordered PCE quantiles')
        rows.append(record)
    if len(rows)<100 or len(set(r['month'] for r in rows))!=len(rows): raise ValueError('Invalid PCE month sample')
    return sorted(rows,key=lambda r:r['month'])
def update():
    stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
    target=ROOT/'web/pce.json';status=ROOT/'web/pce_status.json'
    try:
        session=requests.Session()
        # Local proxy configuration may be unavailable; no authentication bypass.
        try: r=session.get(SOURCE,timeout=45);r.raise_for_status()
        except requests.RequestException:
            session.trust_env=False;r=session.get(SOURCE,timeout=45);r.raise_for_status()
        rows=parse(r.content)
        metadata=dict(source=SOURCE,page=PAGE,fetched_at=stamp,source_last_modified=r.headers.get('Last-Modified'),sha256=hashlib.sha256(r.content).hexdigest(),
                      start=rows[0]['month'],end=rows[-1]['month'],unit='12-month percent change',method='SF Fed published Level 4 PCE aggregates; BEA underlying PCE; copied without recalculation',
                      missing={k:[v['month'] for v in rows if v[k] is None] for k in FIELDS})
        if target.exists() and rows[-1]['month']<json.loads(target.read_text(encoding='utf-8'))['meta']['end']:raise ValueError('PCE source regressed; retain last good')
        text=json.dumps(dict(meta=metadata,rows=rows),ensure_ascii=False,separators=(',',':'),allow_nan=False)
        temp=target.with_suffix('.tmp');temp.write_text(text,encoding='utf-8');temp.replace(target)
        stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=['month']+FIELDS);writer.writeheader();writer.writerows(rows)
        (ROOT/'web/pce.csv').write_text(stream.getvalue(),encoding='utf-8-sig')
        try:
            from .pce_growth import write_snapshot
            write_snapshot(r.content,stamp,r.headers.get('Last-Modified'))
        except Exception as growth_error:
            from .pce_growth import failure
            failure(growth_error)
        outcome=dict(state='success',checked_at=stamp,last_success=stamp,message='SF Fed official history retrieved')
    except Exception as e:
        from .pce_growth import failure
        failure(e)
        outcome=dict(state='failed',checked_at=stamp,message=str(e),retained_last_good=target.exists())
    status.write_text(json.dumps(outcome,ensure_ascii=False),encoding='utf-8');print(json.dumps(outcome))
if __name__=='__main__':update()
