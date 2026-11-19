import copy
import math
import unittest
from cpi.card_estimates import estimate_cards


class CardEstimatesTest(unittest.TestCase):
    def fixture(self):
        h = {'meta': {'version': 'test'}, 'groups': {'measures': [{'month': '2026-10', 'headline': None, 'core': None}]}}
        p = [dict(kind='price', status='official', code=code, month=m, value=v, source='fixture')
             for code, values in [('SA0', [324.8, 324.122, 337.511]), ('SA0L1E', [330.804, 330.425, 339.921])]
             for m, v in zip(['2025-09', '2025-11', '2026-10'], values)]
        return h, p

    def test_independent_formula_and_immutability(self):
        h, p = self.fixture()
        before = copy.deepcopy((h, p))
        out = estimate_cards(h, p, 'fixed')
        for f, a, b, c in [('headline', 324.8, 324.122, 337.511), ('core', 330.804, 330.425, 339.921)]:
            r = out['estimates'][f]
            self.assertAlmostEqual(r['estimated_base_index'], math.sqrt(a*b), places=11)
            self.assertAlmostEqual(r['estimated_yoy'], (c/math.sqrt(a*b)-1)*100, places=11)
            self.assertEqual(r['status'], 'estimated')
        self.assertEqual((h, p), before)

    def test_official_supersedes(self):
        h, p = self.fixture()
        p.append(dict(kind='price', status='official', code='SA0', month='2025-10', value=325))
        self.assertEqual(estimate_cards(h, p, 'fixed')['estimates']['headline']['status'], 'official_preferred')
        h['groups']['measures'][-1]['core'] = 3
        self.assertIsNone(estimate_cards(h, p, 'fixed')['estimates']['core']['estimated_yoy'])

    def test_missing_or_estimated_input_no_extrapolation(self):
        for change in ['missing', 'estimated', 'zero']:
            h, p = self.fixture()
            if change == 'missing': p.pop(1)
            elif change == 'estimated': p[1]['status'] = 'estimated'
            else: p[1]['value'] = 0
            self.assertEqual(estimate_cards(h, p, 'fixed')['estimates']['headline']['status'], 'unavailable')
