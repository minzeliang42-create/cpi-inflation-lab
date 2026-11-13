"""BLS ingestion: immutable responses, validated observations, fail-safe publication."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
import requests

from .model import ROOT, utcnow, write_json, records, load_inputs
from .build import build

API='https://api.bls.gov/publicAPI/v2/timeseries/data/'
BULK='https://download.bls.gov/pub/time.series/cu/'
SCHEDULE='https://www.bls.gov/schedule/news_release/cpi.htm'
RI='https://www.bls.gov/cpi/tables/relative-importance/'
MONTHS={m.lower():i for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'],1)}


def month_in_text(text):
    text=re.sub(r'\s+',' ',text)
    for name, num in MONTHS.items():
        match=re.search(r'\b'+name[:3]+r'(?:[a-z]*)\.?\s+(20\d{2})\b',text,re.I)
        if match: return f'{match[1]}-{num:02}'
    raise ValueError(f'No unambiguous month/year in column header: {text[:120]}')


def normalize_name(s):
    s=re.sub(r'\(\s*\d+\s*\)','',s).lower().replace('&','and')
    return re.sub(r'[^a-z0-9]','',s)


def parse_weight_table(html, components):
    soup=BeautifulSoup(html,'html.parser')
    for sup in soup.select('sup'): sup.decompose()
    for table in soup.find_all('table'):
        header=next((th for th in table.find_all(['th','td']) if 'relative importance' in th.get_text(' ',strip=True).lower()),None)
        if header is None: continue
        ref=month_in_text(header.get_text(' ',strip=True)) # Date belongs to RI column, never title.
        wanted={normalize_name(c['name']):c['code'] for c in components}
        found={}
        for row in table.find_all('tr'):
            cells=row.find_all(['th','td'],recursive=False)
            if len(cells)<2: continue
            code=wanted.get(normalize_name(cells[0].get_text(' ',strip=True)))
            if not code: continue
            val=cells[1].get_text(' ',strip=True).replace(',','')
            if re.fullmatch(r'\d+(?:\.\d+)?',val):
                if code in found: raise ValueError('Duplicate category in weight table')
                found[code]=float(val)
        if found: return ref,found
    raise ValueError('No dated relative-importance column found')


def parse_calendar(html):
    soup=BeautifulSoup(html,'html.parser')
    releases=[]
    for row in soup.select('tr'):
        cells=[c.get_text(' ',strip=True) for c in row.find_all(['th','td'])]
        if len(cells)<3: continue
        try:
            reference=month_in_text(cells[0])
            text=cells[1].replace('.','')
            date=None
            for fmt in ['%b %d, %Y','%B %d, %Y','%m/%d/%Y']:
                try: date=datetime.strptime(text,fmt);break
                except ValueError: pass
            if date is None: continue
            t=datetime.strptime(cells[2],'%I:%M %p').time()
            release=date.replace(hour=t.hour,minute=t.minute,tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)
            releases.append(dict(reference_month=reference,release_at=release.isoformat(timespec='seconds')))
        except ValueError: continue
    if not releases: raise ValueError('Official release-calendar structure not recognized')
    return sorted(releases,key=lambda r:r['release_at'])


def parse_annual_table(html,components,vintage):
    soup=BeautifulSoup(html,'html.parser')
    for sup in soup.select('sup'): sup.decompose()
    title=soup.find('h1')
    if title is None: raise ValueError('Missing annual-table title')
    ref=month_in_text(title.get_text(' ',strip=True))
    if not ref.endswith('-12'): raise ValueError('Annual table is not December reference')
    wanted={normalize_name(c['name']):c['code'] for c in components}
    for table in soup.find_all('table'):
        text=table.get_text(' ',strip=True)
        if 'CPI-U' not in text or 'CPI-W' not in text: continue
        caption=table.find('caption')
        basis=re.search(r'\(([^)]+)\s+Weights\)',caption.get_text(' ',strip=True) if caption else text[:350],re.I)
        if not basis: raise ValueError('Annual expenditure basis is not explicit')
        # This official annual table has Item/Group, CPI-U, CPI-W in that order.
        headers=[c.get_text(' ',strip=True) for c in table.select('thead th')]
        if headers and not any('CPI-U' in h for h in headers): raise ValueError('Missing CPI-U header')
        weights={}
        for tr in table.select('tr'):
            cells=tr.find_all(['td','th'],recursive=False)
            if len(cells)<3: continue
            code=wanted.get(normalize_name(cells[0].get_text(' ',strip=True)))
            if not code: continue
            val=pd.to_numeric(cells[1].get_text(' ',strip=True),errors='coerce')
            if pd.notna(val) and np.isfinite(val) and val>=0: weights[code]=float(val)
        if len(weights)!=68: raise ValueError(f'Annual table contains {len(weights)}/68 categories')
        return dict(reference_month=ref,basis=basis[1],vintage=vintage,
                    effective_year=int(ref[:4])+(1 if vintage=='new' else 0),weights=weights)
    raise ValueError('Annual CPI-U table not recognized')


class Client:
    def __init__(self, root):
        self.root=root;self.session=requests.Session()
        self.session.headers['User-Agent']='CPI-Inflation-Research/1.0 (public economic data; monthly research)'
        self.events=[];self.last_request=0
    def fetch(self,url,payload=None):
        # At most one request per second; POST body (which may contain a secret) is never logged.
        time.sleep(max(0,1-(time.monotonic()-self.last_request)))
        self.last_request=time.monotonic()
        response=self.session.post(url,json=payload,timeout=(15,90)) if payload else self.session.get(url,timeout=(15,90))
        stamp=utcnow();sha=hashlib.sha256(response.content).hexdigest()
        suffix='.json' if 'json' in response.headers.get('content-type','') else '.txt'
        folder=self.root/'data/raw'/stamp[:10]
        folder.mkdir(parents=True,exist_ok=True)
        (folder/(sha+suffix)).write_bytes(response.content)
        event=dict(url=url,http_status=response.status_code,sha256=sha,fetched_at=stamp,
                   published_at=response.headers.get('Last-Modified') or None,raw_file=str((folder/(sha+suffix)).relative_to(self.root)))
        self.events.append(event)
        response.raise_for_status()
        return response,event


def observation(month,code,kind,value,event,method,scale=None):
    return dict(month=month,code=code,kind=kind,value=value,status='official',
                scale=scale or ('index' if kind=='price' else 'all_cpi_pct'), source=event['url'],
                source_hash=event['sha256'],published_at=event['published_at'] or '',fetched_at=event['fetched_at'],basis='',method=method)


def parse_api(data,event,ids):
    if data.get('status')!='REQUEST_SUCCEEDED': raise ValueError('BLS rejected request: '+str(data.get('message')))
    series=data.get('Results',{}).get('series',[])
    if {s['seriesID'] for s in series}!=set(ids): raise ValueError('Missing/extra series in API response')
    out=[]
    for s in series:
        code=s['seriesID'][8:]
        seen=set()
        for row in s['data']:
            if not re.fullmatch(r'M(0[1-9]|1[0-2])',row['period']): continue
            month=f"{row['year']}-{row['period'][1:]}"
            if month in seen: raise ValueError('Duplicate month from BLS')
            seen.add(month)
            value=pd.to_numeric(row['value'],errors='coerce')
            if pd.notna(value) and np.isfinite(value) and value>0:
                out.append(observation(month,code,'price',float(value),event,'BLS CPI-U NSA official index'))
            if code in ['SA0','SA0L1E']: continue
            for aspect in row.get('aspects',[]):
                if aspect['name'].strip().lower()!='relative importance': continue
                value=pd.to_numeric(aspect['value'],errors='coerce')
                if pd.notna(value) and np.isfinite(value) and value>=0:
                    # BLS monthly RI refers to preceding observation month. This is independently
                    # checked against the dated news-release RI column whenever HTML is available.
                    ref=str(pd.Period(month,freq='M')-1)
                    out.append(observation(ref,code,'weight',float(value),event,
                        'BLS API Relative Importance; reference month = observation month minus 1 (verified against Table 2)'))
    if not out: raise ValueError('API returned no valid monthly observations')
    return out


def merge_observations(old,new,components):
    codes={c['code'] for c in components}|{'SA0','SA0L1E'}
    if not new: raise ValueError('No official observations downloaded')
    incoming=pd.DataFrame(new)
    if not set(incoming.code)<=codes: raise ValueError('Unknown code')
    # A complete month/series payload is required before replacing any official month.
    official_prices=incoming[incoming.kind=='price']
    latest=official_prices.month.max()
    if latest is None or official_prices[official_prices.month==latest].code.nunique()!=70:
        raise ValueError('Latest price month does not contain all 68 categories plus headline and core')
    if latest < old[old.kind=='price'].month.max(): raise ValueError('BLS response is older than current release')
    weights=incoming[incoming.kind=='weight']
    complete=weights.groupby('month').code.nunique()
    incoming=incoming[(incoming.kind!='weight')|incoming.month.isin(complete[complete.eq(68)].index)]
    # Keep one official candidate per key; reject inconsistent multiple official sources.
    for _,g in incoming.groupby(['month','code','kind']):
        if g.value.max()-g.value.min()>1e-8: raise ValueError('Conflicting official observations')
    incoming=incoming.drop_duplicates(['month','code','kind'])
    merged=old.copy()
    changes=[]
    for row in records(incoming):
        mask=(merged.month==row['month'])&(merged.code==row['code'])&(merged.kind==row['kind'])&(merged.status=='official')
        prev=merged.loc[mask]
        if not prev.empty and abs(float(prev.iloc[0].value)-row['value'])<1e-10: continue
        if not prev.empty: changes.append({'old':records(prev),'new':row})
        else: changes.append({'old':[],'new':row})
        merged=merged.loc[~mask]
        merged=pd.concat([merged,pd.DataFrame([row])],ignore_index=True)
    return merged.sort_values(['month','code','kind','status']),changes


def scheduled_due(root,now=None):
    now=now or datetime.now(timezone.utc)
    p=root/'data/input/calendar.json'
    if not p.exists(): return False
    calendar=json.loads(p.read_text(encoding='utf-8'))
    # Only extra checks on actual BLS release dates, from 08:30 to 13:30 Eastern.
    for row in calendar.get('releases',[]):
        release=datetime.fromisoformat(row['release_at'])
        if 0 <= (now-release).total_seconds() <= 5*3600: return True
    return False


def run(root=ROOT, force=False):
    (root/'.staging').mkdir(exist_ok=True)
    lock=root/'.staging/update.lock'
    try: handle=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError: raise RuntimeError('Another updater is active; remove stale lock only after verifying it stopped')
    os.close(handle)
    old_status_path=root/'dist/status.json'
    old_status=json.loads(old_status_path.read_text(encoding='utf-8')) if old_status_path.exists() else {}
    rollback_paths=[root/'dist/current.json', root/'data/input/observations.csv',root/'data/input/calendar.json',root/'data/input/annual_anchors.json']
    backups={p:p.read_bytes() if p.exists() else None for p in rollback_paths}
    client=Client(root);warnings=[];stamp=utcnow()
    try:
        old,components=load_inputs(root)
        ids=[c['series_id'] for c in components]+['CUUR0000SA0','CUUR0000SA0L1E']
        latest_year=int(old[old.kind=='price'].month.max()[:4])
        end_year=datetime.now(ZoneInfo('Asia/Shanghai')).year
        start_year=max(2018,latest_year-1)
        key=os.getenv('BLS_API_KEY','')
        new=[]
        try:
            for i in range(0,len(ids),25):
                batch=ids[i:i+25]
                payload=dict(seriesid=batch,startyear=str(start_year),endyear=str(end_year),aspects=True)
                if key: payload['registrationkey']=key
                response,event=client.fetch(API,payload)
                new.extend(parse_api(response.json(),event,batch))
        except (requests.RequestException,ValueError) as exc:
            warnings.append('API批量请求失败，尝试官方批量价格备用源：'+str(exc)[:160])
            new=[]
            response,event=client.fetch(BULK+'cu.data.0.Current')
            bulk=pd.read_csv(StringIO(response.text),sep='\t',dtype=str)
            bulk.columns=bulk.columns.str.strip()
            for col in bulk: bulk[col]=bulk[col].str.strip()
            bulk=bulk[bulk.series_id.isin(ids)&bulk.period.str.match(r'M(0[1-9]|1[0-2])$')]
            for r in bulk.to_dict('records'):
                value=float(r['value'])
                if value>0: new.append(observation(f"{r['year']}-{r['period'][1:]}",r['series_id'][8:],'price',value,event,'BLS official bulk fallback'))
        # Header-date confirmation and all-68 detailed monthly weights.
        got_header=False
        for number in ['02','01']:
            try:
                response,event=client.fetch(f'https://www.bls.gov/news.release/cpi.t{number}.htm')
                ref,weights=parse_weight_table(response.text,components)
                api_weights={r['code']:r['value'] for r in new if r['kind']=='weight' and r['month']==ref}
                if any(abs(api_weights[c]-v)>1e-6 for c,v in weights.items() if c in api_weights):
                    raise ValueError('API weight month or value disagrees with dated release header')
                got_header=True
                if len(weights)==68:
                    new.extend(observation(ref,c,'weight',v,event,'Explicit month from Relative Importance header') for c,v in weights.items())
                    break
            except (requests.RequestException,ValueError) as exc: warnings.append(f'Table {number}: '+str(exc)[:160])
        if not got_header: warnings.append('新闻稿权重表暂不可达；采用已核验的API前一月口径，保留该项检查告警')
        # Preserve annual old/new weight vintages separately. Never overwrite December's
        # current-regime weights with the new-regime December bridge column.
        try:
            response,event=client.fetch(RI)
            soup=BeautifulSoup(response.text,'html.parser')
            links=[]
            for a in soup.select('a[href]'):
                href=urljoin(RI,a['href']);text=a.get_text(' ',strip=True)
                if 'U.S. City Average' in text and '(HTML)' in text and re.search(r'20\d{2}',href):
                    links.append((href,text))
            annual=[]
            anchor_path=root/'data/input/annual_anchors.json'
            anchors=json.loads(anchor_path.read_text(encoding='utf-8')) if anchor_path.exists() else []
            for href,title in links[:2]:
                response,ev=client.fetch(href)
                anchor=parse_annual_table(response.text,components,'old' if 'old-weights' in href else 'new')
                anchor['source']=ev
                annual.append(anchor)
            if not annual: raise ValueError('Annual old/new weight links not recognized')
            write_json(root/'data/annual'/f'{stamp[:10]}.json',annual)
            for anchor in annual:
                anchors=[a for a in anchors if (a['reference_month'],a['vintage'])!=(anchor['reference_month'],anchor['vintage'])]
                anchors.append(anchor)
            write_json(anchor_path,anchors)
        except (requests.RequestException,ValueError) as exc: warnings.append('年度权重检查：'+str(exc)[:160])
        try:
            response,event=client.fetch(SCHEDULE)
            releases=parse_calendar(response.text)
            write_json(root/'data/input/calendar.json',dict(source=SCHEDULE,fetched_at=event['fetched_at'],releases=releases))
        except (requests.RequestException,ValueError) as exc: warnings.append('发布日期检查：'+str(exc)[:160])
        merged,changes=merge_observations(old,new,components)
        status=dict(state='degraded' if warnings else 'success',last_attempt=stamp,last_success=utcnow(),
                    changed_observations=len(changes),message='BLS价格及API月度权重检查成功；'+('部分官网网页受限，详见更新日志。' if warnings else '全部来源检查完成。'),warnings=warnings)
        # Validate and build all affected history before replacing the input ledger.
        payload=build(root,merged,status)
        tmp=root/'.staging/observations.csv'
        merged.to_csv(tmp,index=False,encoding='utf-8')
        os.replace(tmp,root/'data/input/observations.csv')
        write_json(root/'data/updates'/f'{stamp.replace(":","-")}.json',dict(status=status,requests=client.events,changes=changes))
        write_json(old_status_path,status)
        print(json.dumps(status,ensure_ascii=False))
        return 0
    except Exception as exc:
        # Roll back the visible pointer and input ledger if any later commit step failed.
        for path,content in backups.items():
            if content is None: path.unlink(missing_ok=True)
            else: path.write_bytes(content)
        status=dict(state='failed',last_attempt=stamp,last_success=old_status.get('last_success'),
                    message='更新失败，保留上次成功数据：'+str(exc)[:400])
        write_json(old_status_path,status)
        write_json(root/'data/updates'/f'{stamp.replace(":","-")}.json',dict(status=status,requests=client.events))
        print(json.dumps(status,ensure_ascii=False),file=sys.stderr)
        return 1
    finally: lock.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--release-window',action='store_true')
    args=p.parse_args()
    if args.release_window and not scheduled_due(ROOT):
        print('Outside official release window; no BLS requests sent.');return
    sys.exit(run())


if __name__=='__main__': main()
