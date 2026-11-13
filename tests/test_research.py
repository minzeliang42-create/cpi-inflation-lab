"""Independent scalar reconciliation and ingestion failure cases. No network calls."""
import copy
import hashlib
import json
import math
from pathlib import Path
import statistics
import uuid
from contextlib import contextmanager
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

from cpi.model import ROOT, calculate, load_inputs, weighted_quantile
from cpi.build import validate
from cpi.update import parse_weight_table, parse_calendar, parse_api, parse_annual_table, merge_observations, run, scheduled_due


@contextmanager
def test_directory():
    import shutil
    p=ROOT/'.staging'/('test-'+uuid.uuid4().hex)
    p.mkdir(parents=True)
    try: yield p
    finally:
        if p.resolve().is_relative_to((ROOT/'.staging').resolve()): shutil.rmtree(p)


class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.obs,cls.components=load_inputs()
        cls.groups,cls.details=calculate(cls.obs,cls.components)
        cls.lookup={}
        for r in cls.obs.to_dict('records'):
            key=(r['month'],r['code'],r['kind'])
            if key not in cls.lookup or r['status']=='official': cls.lookup[key]=float(r['value'])

    def test_universe_and_quality(self):
        validate(self.groups,self.details)
        self.assertEqual(len(self.components),68)
        self.assertNotIn('SEHP',[c['code'] for c in self.components])
        self.assertNotIn('SEEA',[c['code'] for c in self.components])
        for g in self.groups.values(): self.assertTrue(g.loc[g.month<='2026-10','calculation_status'].eq('complete').all())

    def test_independent_focus_months(self):
        """Use dictionaries, math.fsum, statistics.stdev and scalar interpolation.
        This does not use pandas rolling, np.interp, or component calculated columns.
        """
        reconciliation={}
        for month in ['2024-12','2025-10','2026-09']:
            def lag(n): return str(pd.Period(month,'M')-n)
            def price(m,c): return self.lookup[(m,c,'price')]
            codes=[c['code'] for c in self.components]
            raw=[self.lookup[(month,c,'weight')] for c in codes]
            weights=[w/math.fsum(raw)*100 for w in raw]
            def inflation(m,c): return (price(m,c)/price(str(pd.Period(m,'M')-12),c)-1)*100
            ys=[inflation(month,c) for c in codes]
            acc=[inflation(month,c)-inflation(lag(12),c) for c in codes]
            zs=[]
            for c in codes:
                window=[inflation(lag(i),c) for i in range(59,-1,-1)]
                zs.append((window[-1]-statistics.mean(window))/statistics.stdev(window))
            result={}
            for key,values in [('measures',ys),('acceleration',acc)]:
                sorted_pairs=sorted(zip(values,weights))
                cumulative=[];total=0
                for _,w in sorted_pairs: total+=w/100;cumulative.append(total)
                expected=[]
                for p in [.1,.25,.5,.75,.9]:
                    k=next((i for i,v in enumerate(cumulative) if v>=p),67)
                    q=sorted_pairs[0][0] if k==0 else sorted_pairs[k-1][0]+(p-cumulative[k-1])/(cumulative[k]-cumulative[k-1])*(sorted_pairs[k][0]-sorted_pairs[k-1][0])
                    expected.append(q)
                actual=self.groups[key].set_index('month').loc[month]
                for col,q in zip(['p10','p25','p50','p75','p90'],expected): self.assertAlmostEqual(q,actual[col],places=10)
                result[key]=dict(zip(['p10','p25','p50','p75','p90'],expected))
            for key,vals,threshold,less in [('declines',ys,0,True),('growth',ys,0,False),('t_declines',zs,-2,True),('t_growth',zs,2,False)]:
                flags=[v<threshold if less else v>threshold for v in vals]
                expected=dict(count=sum(flags),items_pct=sum(flags)/68*100,weight_pct=math.fsum(w for w,f in zip(weights,flags) if f))
                actual=self.groups[key].set_index('month').loc[month]
                for col,value in expected.items(): self.assertAlmostEqual(value,actual[col],places=10)
                result[key]=expected
            for code,col in [('SA0','headline'),('SA0L1E','core')]:
                if (month,code,'price') in self.lookup and (lag(12),code,'price') in self.lookup:
                    self.assertAlmostEqual(inflation(month,code),self.groups['measures'].set_index('month').at[month,col],places=10)
            reconciliation[month]=result
        out=ROOT/'output/validation';out.mkdir(parents=True,exist_ok=True)
        (out/'independent_reconciliation.json').write_text(json.dumps(reconciliation,indent=2),encoding='utf-8')

    def test_calendar_windows(self):
        first=self.details[self.details.month=='2023-12']
        self.assertTrue(first.window_start.eq('2019-01').all())
        self.assertTrue(first.window_count.eq(60).all())
        oct26=self.details[self.details.month=='2026-10']
        official_oct=self.obs[(self.obs.kind=='weight')&(self.obs.status=='official')&(self.obs.month=='2026-10')]
        self.assertTrue(oct26.weight_status.eq('official' if len(official_oct)==68 else 'provisional').all())
        # Future official replacements are expected to remove estimated flags.
        official_keys={(r['month'],r['code']) for r in self.obs.to_dict('records') if r['status']=='official' and r['kind']=='price'}
        active_estimates=[r for r in self.obs.to_dict('records') if r['status']=='estimated' and r['kind']=='price' and (r['month'],r['code']) not in official_keys]
        self.assertEqual(bool(oct26.window_uses_estimate.any()),bool(active_estimates))
        insurance=self.details[(self.details.code=='SETE')&(self.details.month=='2025-11')]
        self.assertTrue(insurance.price_status.eq('official' if ('2025-11','SETE') in official_keys else 'estimated').all())

    def test_missing_price_not_zero_and_calendar_gap(self):
        obs=self.obs[~((self.obs.month=='2024-04')&(self.obs.code=='SEFA')&(self.obs.kind=='price'))]
        groups,d=calculate(obs,self.components)
        row=groups['t_growth'].set_index('month').loc['2026-09']
        self.assertTrue(pd.isna(row.items_pct))
        self.assertEqual(row.valid_categories,67)
        self.assertTrue(pd.isna(d[(d.month=='2024-04')&(d.code=='SEFA')].iloc[0].yoy))

    def test_weight_zero_and_quantile_endpoint(self):
        self.assertTrue(np.isnan(weighted_quantile(np.arange(68),np.zeros(68))).all())
        w=np.ones(68);w[0]=1000
        self.assertEqual(weighted_quantile(np.arange(68),w)[0],0)
        self.assertTrue(np.isnan(weighted_quantile([np.nan]*68,w)).all())

    def test_zero_standard_deviation(self):
        obs=self.obs.copy()
        obs.loc[(obs.kind=='price')&(obs.code=='SEFA'),'value']=100
        groups,d=calculate(obs,self.components)
        self.assertTrue(d.loc[(d.month>='2023-12')&(d.code=='SEFA'),'z_score'].isna().all())
        self.assertTrue(groups['t_declines'].items_pct.isna().all())

    def test_no_cross_year_extrapolation_without_new_basis(self):
        obs=self.obs[~((self.obs.month=='2026-01')&(self.obs.kind=='weight'))]
        _,d=calculate(obs,self.components)
        self.assertTrue(d[d.month=='2026-01'].normalized_weight.isna().all())
        anchor=dict(reference_month='2025-12',effective_year=2026,vintage='new',weights={c['code']:1 for c in self.components})
        _,d=calculate(obs,self.components,[anchor])
        self.assertAlmostEqual(d[d.month=='2026-01'].normalized_weight.sum(),100)

    def test_approved_estimates_only(self):
        self.assertFalse(self.obs.method.str.contains('回测',na=False).any())
        self.assertEqual(len(self.obs[(self.obs.status=='estimated')&(self.obs.kind=='price')]),69)
        self.assertEqual(len(self.obs[(self.obs.status=='estimated')&(self.obs.kind=='weight')]),136)

    def test_header_month_not_release_title(self):
        html='<h1>October 2026</h1><table><tr><th>Expenditure category</th><th>Relative importance<br>Sep.<br>2026</th></tr><tr><th>Cereals and cereal products<sup>1</sup></th><td>0.309</td></tr></table>'
        month,weights=parse_weight_table(html,self.components)
        self.assertEqual(month,'2026-09');self.assertEqual(weights,{'SEFA':.309})
        with self.assertRaises(ValueError): parse_weight_table(html.replace('Sep.<br>2026',''),self.components)

    def test_api_aspect_alignment_and_m13(self):
        ev=dict(url='https://api.bls.gov/',sha256='test',published_at=None,fetched_at='2026-11-13')
        data=dict(status='REQUEST_SUCCEEDED',Results={'series':[dict(seriesID='CUUR0000SEFA',data=[dict(year='2026',period='M10',value='290.371',aspects=[dict(name='Relative Importance',value='.309')]),dict(year='2026',period='M13',value='0')])]})
        rows=parse_api(data,ev,['CUUR0000SEFA'])
        self.assertEqual([r['month'] for r in rows],['2026-10','2026-09'])

    def test_annual_old_new_vintages(self):
        rows=''.join(f'<tr><th>{c["name"]}</th><td>1.0</td><td>9.9</td></tr>' for c in self.components)
        html='<h1>U.S. city average, December 2025</h1><table><caption>Table 1 (2024 Weights)</caption><thead><tr><th>Item</th><th>CPI-U</th><th>CPI-W</th></tr></thead>'+rows+'</table>'
        new=parse_annual_table(html,self.components,'new')
        old=parse_annual_table(html,self.components,'old')
        self.assertEqual(new['effective_year'],2026);self.assertEqual(old['effective_year'],2025)
        self.assertEqual(new['basis'],'2024');self.assertEqual(len(new['weights']),68)
        self.assertTrue(all(v==1 for v in new['weights'].values()))
        with self.assertRaises(ValueError): parse_annual_table(html.replace('2024 Weights','unknown'),self.components,'new')

    def test_calendar_dst_and_release_gate(self):
        from datetime import datetime,timezone
        html='<table><tr><td>November 2026</td><td>Dec. 10, 2026</td><td>08:30 AM</td></tr><tr><td>July 2027</td><td>Aug. 11, 2027</td><td>08:30 AM</td></tr></table>'
        releases=parse_calendar(html)
        self.assertEqual(releases[0]['release_at'],'2026-12-10T13:30:00+00:00')
        self.assertEqual(releases[1]['release_at'],'2027-08-11T12:30:00+00:00')
        with test_directory() as root:
            (root/'data/input').mkdir(parents=True)
            (root/'data/input/calendar.json').write_text(json.dumps({'releases':releases}),encoding='utf-8')
            self.assertTrue(scheduled_due(root,datetime(2026,12,10,14,40,tzinfo=timezone.utc)))
            self.assertFalse(scheduled_due(root,datetime(2026,12,11,14,40,tzinfo=timezone.utc)))

    def test_new_official_weight_replaces_estimate_and_conflict_rejected(self):
        # A complete official price snapshot and official 2025-10 weights simulate replacement.
        latest=self.obs[self.obs.kind=='price'].month.max()
        new=self.obs[(self.obs.kind=='price')&(self.obs.month==latest)&(self.obs.status=='official')].to_dict('records')
        ws=self.obs[(self.obs.kind=='weight')&(self.obs.month=='2025-10')].copy()
        ws['status']='official';ws['scale']='all_cpi_pct'
        ws['value']=ws['value']*.98
        new+=ws.to_dict('records')
        merged,changes=merge_observations(self.obs,new,self.components)
        _,d=calculate(merged,self.components)
        self.assertTrue(d[d.month=='2025-10'].weight_status.eq('official').all())
        self.assertEqual(len(changes),68)
        conflict=copy.deepcopy(new[-1]);conflict['value']+=1
        with self.assertRaises(ValueError): merge_observations(self.obs,new+[conflict],self.components)

    def test_duplicates_and_official_precedence(self):
        with self.assertRaises(ValueError): calculate(pd.concat([self.obs,self.obs.iloc[:1]]),self.components)
        extra=self.obs[(self.obs.month=='2025-10')&(self.obs.code=='SEFA')&(self.obs.kind=='price')].copy()
        extra['status']='official';extra['value']=321
        _,d=calculate(pd.concat([self.obs,extra]),self.components)
        self.assertEqual(d[(d.month=='2025-10')&(d.code=='SEFA')].iloc[0].price_index,321)

    def test_failed_update_preserves_release(self):
        import shutil
        with test_directory() as temp:
            root=Path(temp);shutil.copytree(ROOT/'data/input',root/'data/input');(root/'dist').mkdir()
            (root/'dist/current.json').write_text('{"version":"previous"}')
            before=(root/'data/input/observations.csv').read_bytes()
            with patch('cpi.update.Client.fetch',side_effect=RuntimeError('Simulated network failure')):
                self.assertEqual(run(root),1)
            self.assertEqual((root/'data/input/observations.csv').read_bytes(),before)
            self.assertEqual(json.loads((root/'dist/current.json').read_text())['version'],'previous')
            self.assertEqual(json.loads((root/'dist/status.json').read_text(encoding='utf-8'))['state'],'failed')

    def test_download_equivalence(self):
        path=ROOT/'dist/current.json'
        if not path.exists(): self.skipTest('Run build before download-equivalence test')
        manifest=json.loads(path.read_text(encoding='utf-8'))
        payload=json.loads((ROOT/'dist'/manifest['path']).read_text(encoding='utf-8'))
        bundle=ROOT/'dist/data'/manifest['version']
        import openpyxl
        wb=openpyxl.load_workbook(bundle/'cpi_history.xlsx',read_only=True,data_only=True)
        for key,rows in payload['groups'].items():
            df=pd.read_csv(bundle/f'{key}.csv')
            self.assertEqual(len(rows),len(df))
            values=list(wb[key].values);header=list(values[0])
            for i,row in enumerate(rows):
                for col,value in row.items():
                    csv=df.iloc[i][col];excel=values[i+1][header.index(col)]
                    if isinstance(value,(int,float)) and not isinstance(value,bool):
                        self.assertAlmostEqual(value,float(csv),places=9);self.assertAlmostEqual(value,float(excel),places=9)
                    elif value is None: self.assertTrue(pd.isna(csv));self.assertEqual(excel,'NA')
        wb.close()


if __name__=='__main__': unittest.main()
