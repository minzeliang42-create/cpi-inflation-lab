import unittest
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from cpi.model import ROOT, load_inputs, calculate, import_workbook
from test_research import test_directory
from cpi.update import Client,verify_api_weights,WeightReferenceMismatch,parse_api
from unittest.mock import patch
import requests


class V11Tests(unittest.TestCase):
    def test_weight_header_mismatch_is_fatal(self):
        rows=[dict(kind='weight',month='2026-09',code='SEFA',value=.309)]
        verify_api_weights(rows,'2026-09',{'SEFA':.309})
        with self.assertRaises(WeightReferenceMismatch): verify_api_weights(rows,'2026-09',{'SEFA':.708})

    def test_timeout_is_logged(self):
        client=Client(ROOT)
        with patch.object(client.session,'get',side_effect=requests.Timeout('Test timeout')):
            with self.assertRaises(requests.Timeout): client.fetch('https://www.bls.gov/news.release/cpi.t02.htm')
        self.assertEqual(client.events[-1]['error'],'Timeout')
        self.assertIsNone(client.events[-1]['http_status'])

    def test_original_workbook_reconciliation(self):
        source=Path(r'D:\我的文档\Desktop\CPI原始数据_20261112\CPI_Raw_Data.xlsx')
        if not source.exists(): self.skipTest('Original private Excel is verified locally; not uploaded to public CI')
        before=hashlib.sha256(source.read_bytes()).hexdigest()
        current,c=load_inputs()
        with test_directory() as temp:
            import_workbook(source,temp)
            seed,_=load_inputs(temp)
            a=seed.set_index(['month','code','kind','status']).value.sort_index()
            b=current.set_index(['month','code','kind','status']).value.reindex(a.index)
            np.testing.assert_allclose(a,b,rtol=0,atol=1e-10)
        self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())

    def test_official_acceleration_missing_and_no_substitution(self):
        o,c=load_inputs();g,_=calculate(o,c)
        self.assertTrue(pd.isna(g['acceleration'].set_index('month').at['2026-10','headline']))
        modified=o[~((o.month=='2023-12')&(o.code=='SA0')&(o.kind=='price'))]
        actual,_=calculate(modified,c)
        self.assertTrue(pd.isna(actual['acceleration'].set_index('month').at['2025-12','headline']))
        # An unapproved headline estimate must never enter the official line.
        fake=o[(o.month=='2026-10')&(o.code=='SA0')&(o.kind=='price')].copy()
        official=o[~((o.month=='2026-10')&(o.code=='SA0')&(o.kind=='price'))]
        fake['status']='estimated'
        actual,_=calculate(pd.concat([official,fake]),c)
        self.assertTrue(pd.isna(actual['measures'].set_index('month').at['2026-10','headline']))

    def test_estimation_flags_are_separate_from_provisional(self):
        o,c=load_inputs();g,_=calculate(o,c)
        for key,df in g.items():
            row=df.set_index('month').loc['2026-10']
            self.assertEqual(row.weight_status,'provisional')
            self.assertTrue(row.uses_estimated_price)
        self.assertTrue(g['t_growth'].set_index('month').at['2026-09','uses_estimated_price'])


if __name__=='__main__': unittest.main()
