"""Produce a versioned, self-contained static data release after validation."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
import pandas as pd
from .model import ROOT, GROUPS, calculate, load_inputs, records, write_json, utcnow


def validate(groups, details):
    assert details.groupby('month').size().eq(68).all()
    sums = details.groupby('month').normalized_weight.sum(min_count=68).dropna()
    assert (sums - 100).abs().max() < 1e-9
    for key in ['measures', 'acceleration']:
        q = groups[key][['p10','p25','p50','p75','p90']].dropna()
        assert q.diff(axis=1).iloc[:,1:].ge(-1e-10).all().all()
    for month, d in details.groupby('month'):
        if d.yoy.notna().all():
            assert (d.yoy.lt(0).sum() + d.yoy.gt(0).sum() + d.yoy.eq(0).sum()) == 68
        if d.z_score.notna().any():
            assert d.loc[d.z_score.notna(), 'window_count'].eq(60).all()
    return {'fixed_categories': 68, 'normalized_weight_max_error': float((sums-100).abs().max()),
            'quantile_order': True, 'count_partition': True, 't_window_months': 60}


def build(root=ROOT, observations=None, update_status=None):
    if update_status is None and (root/'dist/status.json').exists():
        update_status=json.loads((root/'dist/status.json').read_text(encoding='utf-8'))
    obs, components = load_inputs(root)
    if observations is not None:
        obs = observations
    anchor_path=root/'data/input/annual_anchors.json'
    anchors=json.loads(anchor_path.read_text(encoding='utf-8')) if anchor_path.exists() else []
    groups, details = calculate(obs, components,anchors)
    checks = validate(groups, details)
    source = json.loads((root/'data/input/source.json').read_text(encoding='utf-8'))
    anchor_values=[{k:v for k,v in a.items() if k!='source'} for a in anchors]
    digest = hashlib.sha256(obs.to_csv(index=False).encode()+json.dumps(anchor_values,sort_keys=True).encode()).hexdigest()[:16]
    # Calculation version is part of the immutable release identity.
    code_digest = hashlib.sha256((root/'cpi/model.py').read_bytes() + (root/'cpi/build.py').read_bytes()).hexdigest()[:8]
    version = f'{digest}-{code_digest}'
    dist = root / 'dist'
    dist.mkdir(exist_ok=True)
    (root/'.staging').mkdir(exist_ok=True)
    stage = root/'.staging'/('cpi-'+uuid.uuid4().hex)
    stage.mkdir()
    try:
        bundle = stage / version
        bundle.mkdir()
        for key, df in groups.items():
            df.to_csv(bundle/f'{key}.csv', index=False, na_rep='NA', encoding='utf-8-sig')
        details.to_csv(bundle/'components.csv', index=False, na_rep='NA', encoding='utf-8-sig')
        # Automated Python exporter is portable to an unattended GitHub Actions runner.
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for key, df in [*groups.items(), ('components', details)]:
            s = wb.create_sheet(key)
            s.append(list(df.columns))
            for r in records(df):
                s.append([r.get(c) if r.get(c) is not None else 'NA' for c in df.columns])
            s.freeze_panes = 'B2'
            s.auto_filter.ref = s.dimensions
            s.sheet_view.showGridLines = False
            for c in s[1]:
                c.font = Font(name='Arial', bold=True, color='FFFFFF')
                c.fill = PatternFill('solid', fgColor='173D55')
            for col in s.columns:
                s.column_dimensions[col[0].column_letter].width = min(42, max(14, len(str(col[0].value))+2))
            for row in s.iter_rows(min_row=2):
                for c in row:
                    if isinstance(c.value, float): c.number_format = '0.000000'
        s = wb.create_sheet('sources_methods')
        for row in [ ['CPI Inflation Distribution & Dispersion'], ['Release', version],
                     ['Units','YoY and shares are percent; acceleration and std are percentage points'],
                     ['Price source','CPI-U NSA, BLS official series; approved workbook estimates retained'],
                     ['Weights','Original weight scale is recorded per row. All 68 weights normalized to 100.'],
                     ['Quantiles','np.interp(p, cumsum(sorted weights/sum), sorted category values)'],
                     ['t-diffusion','60 calendar months incl. current; sample std ddof=1; strict z<-2 or z>2'],
                     ['Missing','NA is not zero. Aggregate shares are NA if any of the 68 required values is absent.'],
                     ['Estimates','Approved ex-post price interpolation is not a real-time forecast.'],
                     ['Workbook hash',source['sha256']], ['BLS','https://api.bls.gov/publicAPI/v2/timeseries/data/'],
                     ['RI','https://www.bls.gov/cpi/tables/relative-importance/'] ]: s.append(row)
        s.column_dimensions['A'].width = 24
        s.column_dimensions['B'].width = 110
        wb.save(bundle/'cpi_history.xlsx')
        latest = {}
        for key, df in groups.items():
            ok = df[df.calculation_status == 'complete']
            latest[key] = None if ok.empty else ok.month.max()
        calendar_path = root/'data/input/calendar.json'
        calendar = json.loads(calendar_path.read_text(encoding='utf-8')) if calendar_path.exists() else {}
        future = [r for r in calendar.get('releases',[]) if r['release_at'] > utcnow()]
        official_weights = obs[(obs.kind=='weight') & (obs.status=='official')].groupby('month').code.nunique()
        meta = dict(version=version, generated_at=utcnow(), latest_price_month=obs[obs.kind=='price'].month.max(),
                    latest_official_weight_month=official_weights[official_weights.eq(68)].index.max(),
                    latest_calculation_months=latest, next_release=future[0] if future else None,
                    calendar_verified_at=calendar.get('fetched_at'), source=source, checks=checks,
                    forecast_months=['2026-11','2026-12'], forecast_status='Reserved; no model or forecast values',
                    status=update_status or {'state':'historical_build','last_success':None,'message':'已由源工作簿构建；等待官方更新检查'})
        payload = dict(meta=meta, groups={k:records(v) for k,v in groups.items()}, components=records(details))
        write_json(bundle/'research.json', payload)
        focus = {k:records(v[v.month.isin(['2024-12','2025-10','2026-09'])]) for k,v in groups.items()}
        write_json(bundle/'quality.json', {'checks':checks, 'focus_months':focus,
                   'incomplete_months':{k:v.loc[v.calculation_status!='complete','month'].tolist() for k,v in groups.items()}})
        write_json(bundle/'provenance.json', records(obs.drop(columns=['priority'], errors='ignore')))
        dest = dist/'data'/version
        dest.parent.mkdir(exist_ok=True)
        if not dest.exists(): shutil.move(str(bundle), str(dest))
        for f in (root/'web').iterdir():
            if f.is_file(): shutil.copy2(f, dist/f.name)
            elif f.is_dir(): shutil.copytree(f, dist/f.name, dirs_exist_ok=True)
        write_json(stage/'current.json', {'version':version, 'path':f'data/{version}/research.json'})
        os.replace(stage/'current.json', dist/'current.json')
        return payload
    finally:
        if stage.resolve().is_relative_to((root/'.staging').resolve()):
            shutil.rmtree(stage)


def main():
    (ROOT/'.staging').mkdir(exist_ok=True)
    payload=build()
    print(json.dumps({'version':payload['meta']['version'], 'latest':payload['meta']['latest_calculation_months'],
                      'checks':payload['meta']['checks']},ensure_ascii=False))


if __name__ == '__main__': main()
