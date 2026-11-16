import json
import math
import statistics
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import openpyxl
from cpi.model import ROOT
from cpi.forecast_engine import FIELDS,indicators,weights_for_path,direct_forecast
from cpi.forecast_research import panels,information_set,simulate
from cpi.forecast import run,input_digest,realization_table
from test_research import test_directory


class ForecastEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.p=panels(ROOT)

    def test_vector_engine_exactly_reconciles_history(self):
        p=self.p
        actual=indicators(p['price'][:24],p['price'][24:],p['weight'][24:])
        np.testing.assert_allclose(actual,p['values'][24:],rtol=0,atol=1e-10,equal_nan=True)

    def test_expost_interpolation_availability(self):
        self.assertIsNone(information_set(self.p,'2025-10'))
        self.assertIsNone(information_set(self.p,'2025-11'))
        self.assertIsNotNone(information_set(self.p,'2025-09'))
        self.assertIsNotNone(information_set(self.p,'2025-12'))

    def test_no_future_price_or_weight_can_enter_origin(self):
        p=self.p;origin='2024-12';t=p['months'].index(origin)
        a=information_set(p,origin);changed=dict(p)
        changed['price']=p['price'].copy();changed['price'][t+1:]*=100
        changed['obs']=p['obs'].copy()
        changed['obs'].loc[(changed['obs'].kind=='weight')&(changed['obs'].month>=origin),'value']=999999
        b=information_set(changed,origin)
        np.testing.assert_array_equal(a[0],b[0]);np.testing.assert_array_equal(a[1],b[1])
        self.assertLess(a[2],origin)

    def test_official_new_year_bridge_overrides_forecast_assumption(self):
        codes=self.p['codes'][:68];anchor=np.arange(1,69,dtype=float);anchor/=anchor.sum();anchor*=100
        prices=np.ones((2,70))*100;weights=np.ones(68)*100/68
        new=dict(reference_month='2026-12',effective_year=2027,vintage='new',weights=dict(zip(codes,anchor)))
        out=weights_for_path(weights,np.ones(70)*100,prices,months=['2027-01','2027-02'],
            new_anchors=[new],codes=codes,anchor_month='2026-12')
        np.testing.assert_allclose(out[0],anchor);np.testing.assert_allclose(out[1],anchor)
        # This is a forecast-only helper; historical guard is separately tested.

    def test_bootstrap_draws_whole_correlated_paths(self):
        history=self.p['price'];base=np.tile(history[-1],(14,1));w=self.p['weight'][-1]
        residual=np.arange(14*70).reshape(14,70)/100000
        blocks=np.array([residual,-residual])
        _,paths,_=simulate(history,base,w,blocks,[],[str(pd.Period('2026-11')+j) for j in range(14)],
            '2026-10',np.random.default_rng(7),n=4,return_paths=True)
        for path in paths:
            error=np.log(path/base)
            self.assertTrue(np.allclose(error,residual) or np.allclose(error,-residual))

    def test_unchanged_inputs_do_not_fit_models(self):
        with test_directory() as root:
            (root/'dist').mkdir();(root/'data/forecast').mkdir(parents=True)
            old=dict(input_digest='same',version='good',generated_at='2026-11-16T00:00:00Z')
            (root/'dist/current_forecast.json').write_text(json.dumps(old))
            with patch('cpi.forecast.panels',return_value={}),patch('cpi.forecast.input_digest',return_value='same'),\
                 patch('cpi.forecast.realization_table',return_value=pd.DataFrame()),patch('cpi.forecast.policy_fit') as fit:
                self.assertEqual(run(root),old);fit.assert_not_called()
            self.assertEqual(json.loads((root/'dist/forecast_status.json').read_text())['state'],'unchanged')

    def test_failed_forecast_retains_prior_pointer(self):
        with test_directory() as root:
            (root/'dist').mkdir();old='{"version":"good","generated_at":"previous"}'
            pointer=root/'dist/current_forecast.json';pointer.write_text(old)
            with patch('cpi.forecast.panels',side_effect=ValueError('Incomplete new data')):
                with self.assertRaises(ValueError):run(root)
            self.assertEqual(pointer.read_text(),old)
            status=json.loads((root/'dist/forecast_status.json').read_text())
            self.assertEqual(status['state'],'failed');self.assertEqual(status['retained_version'],'good')

    def test_two_issued_vintages_remain_separate_when_realized(self):
        with test_directory() as root:
            (root/'dist').mkdir();(root/'data/forecast').mkdir(parents=True)
            manifest=[]
            for version,value in [('first',3.0),('second',4.0)]:
                filename=f'{version}.json';manifest.append(dict(version=version,asof='2026-10',path=filename))
                row=dict(month='2026-11',forecast_horizon=1,p50=value)
                (root/'dist'/filename).write_text(json.dumps({'scenarios':{'base':{'groups':{'measures':[row]}}}}))
            (root/'data/forecast/vintages.json').write_text(json.dumps(manifest))
            truth=pd.DataFrame([dict(month='2026-11',p50=3.5,data_status='official')])
            p={'groups':{'measures':truth},'months':['2026-11']}
            realized=realization_table(root,p)
            self.assertEqual(realized.vintage.tolist(),['first','second'])
            self.assertEqual(realized.error.tolist(),[-.5,.5])
            self.assertEqual(json.loads((root/'dist/first.json').read_text())['scenarios']['base']['groups']['measures'][0]['p50'],3.0)


class ForecastReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pointer=ROOT/'dist/current_forecast.json'
        if not pointer.exists():raise unittest.SkipTest('Forecast built after the pre-update historical checks')
        manifest=json.loads(pointer.read_text(encoding='utf-8'));cls.folder=ROOT/'dist'/Path(manifest['path']).parent
        cls.data=json.loads((ROOT/'dist'/manifest['path']).read_text(encoding='utf-8'))
        cls.p=panels(ROOT)

    def test_complete_grids_weights_partitions_and_own_weights(self):
        data=self.data
        for name,s in data['scenarios'].items():
            df=pd.DataFrame(s['components']);h=df.month.nunique()
            self.assertGreaterEqual(h,12);self.assertEqual(len(df),68*h)
            self.assertEqual(df.month.min(),data['meta']['forecast_start'])
            self.assertGreaterEqual(df.month.max(),'2027-12')
            self.assertTrue(df.price_index.gt(0).all());self.assertTrue(df.price_status.eq('forecast').all())
            self.assertTrue(df.weight_status.eq('forecast').all())
            for m,d in df.groupby('month'):
                self.assertAlmostEqual(math.fsum(d.normalized_weight),100,10)
                self.assertEqual(int(d.decline.sum()+d.growth.sum()+d.yoy.eq(0).sum()),68)
                for g,col in [('declines','decline'),('growth','growth'),('t_declines','t_decline'),('t_growth','t_growth')]:
                    row=next(r for r in s['groups'][g] if r['month']==m)
                    self.assertEqual(row['count'],int(d[col].sum()))
                    self.assertAlmostEqual(row['weight_pct'],math.fsum(d.loc[d[col],'normalized_weight']),10)
            for g in ('measures','acceleration'):
                q=pd.DataFrame(s['groups'][g])[['p10','p25','p50','p75','p90']]
                self.assertTrue(q.diff(axis=1).iloc[:,1:].ge(-1e-10).all().all())

    def test_rolling_windows_independent_scalar_recalculation(self):
        s=self.data['scenarios']['base'];df=pd.DataFrame(s['components']);p=self.p
        for code in ('SEFA','SETE',p['codes'][40]):
            k=p['codes'].index(code);future=df[df.code==code].sort_values('month')
            prices=p['price'][:,k].tolist()+future.price_index.tolist()
            yoy=[None]*12+[(prices[i]/prices[i-12]-1)*100 for i in range(12,len(prices))]
            for j in (0,1,len(future)-1):
                ix=len(p['price'])+j;window=yoy[ix-59:ix+1];r=future.iloc[j]
                self.assertEqual(len(window),60)
                self.assertAlmostEqual(r.mean_60,statistics.mean(window),10)
                self.assertAlmostEqual(r.std_60,statistics.stdev(window),10)
                self.assertAlmostEqual(r.z_score,(window[-1]-statistics.mean(window))/statistics.stdev(window),10)
                self.assertEqual(r.window_forecast_observations,j+1)
                self.assertEqual(r.window_start,str(pd.Period(r.month)-59))

    def test_missing_official_companions_are_not_replaced(self):
        missing=self.p['price'][self.p['months'].index('2025-10'),68:70]
        for s in self.data['scenarios'].values():
            row=next((r for r in s['groups']['acceleration'] if r['month']=='2027-10'),None)
            if row:
                for k,f in enumerate(('headline','core')):
                    if np.isnan(missing[k]):self.assertIsNone(row[f])

    def test_workbook_csv_json_and_backtest_identity(self):
        wb=openpyxl.load_workbook(self.folder/'CPI_Forecast.xlsx',data_only=True,read_only=True)
        expected={'Forecast_Prices','Forecast_Weights','Forecast_Components','Forecast_Indicators',
                  'Forecast_Backtest','Forecast_Model_Selection','Forecast_Scenarios','Forecast_Summary'}
        self.assertEqual(set(wb.sheetnames),expected)
        rows=wb['Forecast_Indicators'].values;header=next(rows)
        excel={(r[header.index('scenario')],r[header.index('group')],r[header.index('month')]):dict(zip(header,r)) for r in rows}
        for scenario,s in self.data['scenarios'].items():
            for g,rlist in s['groups'].items():
                csv=pd.read_csv(self.folder/(g+'_forecast.csv')).query('scenario == @scenario').set_index('month')
                for r in rlist:
                    for gg,f in FIELDS:
                        if gg!=g:continue
                        e=excel[(scenario,g,r['month'])][f];c=csv.loc[r['month'],f]
                        if r[f] is None:self.assertEqual(e,'NA');self.assertTrue(pd.isna(c))
                        else:self.assertAlmostEqual(r[f],e,10);self.assertAlmostEqual(r[f],c,10)
        rows=wb['Forecast_Backtest'].values;header=next(rows)
        self.assertTrue({'origin','horizon','actual','predicted','error','split','route'}.issubset(header))
        for r in rows:
            d=dict(zip(header,r));self.assertAlmostEqual(d['predicted']-d['actual'],d['error'],9)
            if d['split']=='selection':self.assertLessEqual(str(pd.Period(d['origin'])+d['horizon']),'2024-12')
        wb.close()

    def test_intervals_ordered_and_test_horizons_real(self):
        s=pd.DataFrame(self.data['summary'])
        valid=s.dropna(subset=['lower95','lower80','upper80','upper95'])
        self.assertTrue(valid[['lower95','lower80','upper80','upper95']].diff(axis=1).iloc[:,1:].ge(-1e-10).all().all())
        cov=pd.DataFrame(self.data['coverage'])
        self.assertEqual(set(cov.horizon),{1,2,3,6,12,14});self.assertTrue(cov.n.gt(0).all())
        self.assertTrue(cov.coverage95.between(0,1).all())


if __name__=='__main__':unittest.main()
