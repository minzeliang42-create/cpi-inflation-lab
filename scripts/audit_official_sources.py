"""Bounded official-only connectivity audit. Does not modify the research ledger."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cpi.model import ROOT,write_json,utcnow
from cpi.update import Client,API,BULK,SCHEDULE,RI

client=Client(ROOT)
results=[]
urls=[API+'CUUR0000SEFA?startyear=2026&endyear=2026&aspects=true',
      'https://www.bls.gov/news.release/cpi.t02.htm',
      'https://data.bls.gov/cgi-bin/print.pl/news.release/cpi.t02.htm',
      BULK+'cu.aspect',RI,SCHEDULE,'https://www.bls.gov/schedule/news_release/bls.ics']
for url in urls:
    try:
        r,e=client.fetch(url)
        result=dict(url=url,http_status=r.status_code)
        if url.startswith(API):
            row=r.json()['Results']['series'][0]['data'][0]
            result['latest_observation']={k:row.get(k) for k in ['year','period','value','aspects']}
        results.append(result)
    except Exception as exc:
        results.append(dict(url=url,error=str(exc)[:220]))
write_json(ROOT/'data/updates'/'official-channel-audit-v1.1.json',dict(at=utcnow(),results=results,requests=client.events))
print(json.dumps(results,ensure_ascii=False))
