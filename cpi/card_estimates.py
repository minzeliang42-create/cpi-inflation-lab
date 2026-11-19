"""Isolated, nonofficial card estimates; never edits research or model inputs.

Same log-linear interpolation as forecast_models.prepare, limited to one missing
interior calendar month with adjacent positive official observations.
"""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def shift(month, offset):
    year, m = map(int, month.split('-'))
    n = year * 12 + m - 1 + offset
    return f'{n // 12:04d}-{n % 12 + 1:02d}'


def estimate_cards(history, provenance, generated_at):
    rows = history['groups']['measures']
    last = rows[-1]
    prices = {}
    for r in provenance:
        if r['kind'] == 'price' and r['status'] == 'official':
            v = r.get('value')
            if isinstance(v, (float, int)) and math.isfinite(v) and v > 0:
                prices[r['code'], r['month']] = r
    result = dict(schema_version=1, historical_version=history['meta']['version'],
                  generated_at=generated_at, scope='CPI Measures cards only', estimates={})
    for field, code in [('headline', 'SA0'), ('core', 'SA0L1E')]:
        target = last['month']
        item = dict(month=target, series_id='CUUR0000'+code, status='unavailable',
                    estimated_yoy=None, reason='Required positive official current and adjacent base-month indices unavailable')
        result['estimates'][field] = item
        base = shift(target, -12)
        if last.get(field) is not None or (code, base) in prices:
            item.update(status='official_preferred', reason='Official value/base exists; no card estimate published')
            continue
        current, left, right = [prices.get((code, m)) for m in [target, shift(base, -1), shift(base, 1)]]
        if not all([current, left, right]):
            continue
        denominator = math.exp((math.log(left['value']) + math.log(right['value'])) / 2)
        item.update(status='estimated', estimated_yoy=(current['value']/denominator-1)*100,
                    base_month=base, estimated_base_index=denominator,
                    method='log_linear_single_interior_month_v1',
                    method_reference='cpi/forecast_models.py:prepare (same log-space interpolation; no model retraining)',
                    formula='base_hat = exp((ln(P[base-1])+ln(P[base+1]))/2); yoy_hat = 100*(P[target]/base_hat-1)',
                    inputs=dict(current=current, before=left, after=right),
                    official_source='https://api.bls.gov/publicAPI/v2/timeseries/data/',
                    missing_source='https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi.htm',
                    reason='Nonofficial ex-post interpolation; official historical series remains NA')
    return result


def build(dist):
    dist = Path(dist)
    pointer = json.loads((dist/'current.json').read_text(encoding='utf-8'))
    source = dist/pointer['path']
    provenance = source.with_name('provenance.json')
    result = estimate_cards(json.loads(source.read_text(encoding='utf-8')),
                            json.loads(provenance.read_text(encoding='utf-8')),
                            datetime.now(timezone.utc).isoformat(timespec='seconds'))
    result['input_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [source, provenance]}
    dest = dist/'card_estimates.json'
    temp = dest.with_suffix('.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
    temp.replace(dest)
    return result


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[1]/'dist'), ensure_ascii=False))
