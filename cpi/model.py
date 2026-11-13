from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'SEHP', 'SEEA'}
QUANTILES = [.1, .25, .5, .75, .9]
GROUPS = {
    'measures': ('CPI Measures', '2019-01'),
    'acceleration': ('Acceleration', '2020-01'),
    'declines': ('Diffusion Declines', '2019-01'),
    'growth': ('Diffusion Growth', '2019-01'),
    't_declines': ('t-Diffusion Declines', '2023-12'),
    't_growth': ('t-Diffusion Growth', '2023-12'),
}


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')


def records(df):
    return json.loads(df.to_json(orient='records', date_format='iso', double_precision=15))


def numeric(v):
    return isinstance(v, (int, float)) and np.isfinite(v)


def import_workbook(source: Path, root=ROOT):
    """Read-only import. Only approved estimates fill absent official cells."""
    wb = openpyxl.load_workbook(source, data_only=True, read_only=True)
    rows = list(wb['Components'].values)
    components = [dict(code=r[2], name=r[1], series_id=r[3], major_group=r[4])
                  for r in rows if len(r) > 3 and isinstance(r[0], int) and r[2] not in EXCLUDED]
    assert len(components) == 68 and len({x['code'] for x in components}) == 68
    codes = [x['code'] for x in components]
    out = root / 'data' / 'input'
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / 'components.json', components)
    ledger = []
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    for sheet, kind in [('Price_Index', 'price'), ('Relative_Importance', 'weight')]:
        rs = list(wb[sheet].values)
        header = rs[5]
        for r in rs[6:]:
            if not r or not isinstance(r[0], datetime):
                continue
            for j, code in enumerate(header[1:], 1):
                code = {'Headline CPI': 'SA0', 'Core CPI': 'SA0L1E'}.get(code, code)
                if code not in codes + ['SA0', 'SA0L1E'] or j >= len(r) or not numeric(r[j]):
                    continue
                ledger.append(dict(month=r[0].strftime('%Y-%m'), code=code, kind=kind, value=r[j],
                                   status='official', scale='all_cpi_pct' if kind == 'weight' else 'index',
                                   source=f'workbook:{sheet}', source_hash=source_hash,
                                   published_at='', fetched_at='', basis=str(r[71]) if kind == 'weight' else '',
                                   method='Imported official observation; source workbook preserved'))
    for r in list(wb['Estimated_Data'].values)[6:]:
        if not isinstance(r[0], datetime) or r[1] not in codes or r[6] != 'Estimated' or '回测' in str(r[5]):
            continue
        for j, kind in [(3, 'price'), (4, 'weight')]:
            if numeric(r[j]):
                ledger.append(dict(month=r[0].strftime('%Y-%m'), code=r[1], kind=kind, value=r[j],
                                   status='estimated', scale='normalized_68_pct' if kind == 'weight' else 'index',
                                   source='workbook:Estimated_Data', source_hash=source_hash, published_at='', fetched_at='',
                                   basis='', method=r[5]))
    wb.close()
    df = pd.DataFrame(ledger)
    if df.duplicated(['month', 'code', 'kind', 'status']).any():
        raise ValueError('Duplicate source observations')
    df.to_csv(out / 'observations.csv', index=False, encoding='utf-8')
    write_json(out / 'source.json', {'filename': source.name, 'sha256': source_hash, 'imported_at': utcnow(),
                                  'origin': 'User-approved workbook; includes official BLS series and approved estimates',
                                  'original_modified': False, 'source_publication_time': 'Not recorded in workbook',
                                  'fetched_at': 'Original fetch time not recorded; import time is separate'})
    return len(df)


def weighted_quantile(values, weights):
    """PCE-verified CDF interpolation, endpoint-clamped; no missing-value renormalization."""
    x, w = np.asarray(values, dtype=float), np.asarray(weights, dtype=float)
    if len(x) != 68 or not np.isfinite(x).all() or not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        return np.full(5, np.nan)
    order = np.argsort(x, kind='stable')
    x, w = x[order], w[order]
    x, w = x[w > 0], w[w > 0]
    return np.interp(QUANTILES, np.cumsum(w / w.sum()), x)


def calculate(obs, components, annual_anchors=None):
    codes = [x['code'] for x in components]
    if len(codes) != 68 or len(set(codes)) != 68 or EXCLUDED & set(codes):
        raise ValueError('Universe must contain exactly the frozen 68 categories')
    if obs.duplicated(['month', 'code', 'kind', 'status']).any():
        raise ValueError('Duplicate observation')
    obs = obs.copy()
    obs['priority'] = obs.status.map({'official': 0, 'estimated': 1, 'provisional': 2})
    if obs.priority.isna().any():
        raise ValueError('Unknown or unvalidated forecast observation')
    selected = obs.sort_values('priority').drop_duplicates(['month', 'code', 'kind'])
    pxobs = selected[selected.kind == 'price']
    start, end = '2018-01', pxobs.month.max()
    months = pd.period_range(start, end, freq='M').astype(str)
    def pivot(kind, field):
        return selected[selected.kind == kind].pivot(index='month', columns='code', values=field).reindex(index=months, columns=codes)
    price = pivot('price', 'value').astype(float)
    ps = pivot('price', 'status').fillna('missing')
    weight = pivot('weight', 'value').astype(float)
    ws = pivot('weight', 'status').fillna('missing')
    scales = pivot('weight', 'scale')
    # Price updating within an expenditure-weight regime only. Never bridge Dec -> Jan.
    for k, month in enumerate(months):
        if weight.loc[month].notna().all() or k == 0:
            continue
        prev = months[k-1]
        if month[:4] != prev[:4]:
            # Only a separately published NEW-regime December bridge may seed January.
            anchor=next((a for a in (annual_anchors or []) if a.get('effective_year')==int(month[:4])
                         and a.get('reference_month')==prev and a.get('vintage')=='new'
                         and set(a.get('weights',{}))==set(codes)),None)
            if anchor is None: continue
            prior_weight=pd.Series(anchor['weights']).reindex(codes)
        else:
            if not weight.loc[prev].notna().all(): continue
            prior_weight=weight.loc[prev]
        if not (price.loc[[prev, month]].notna().all().all() and (price.loc[prev] > 0).all()):
            continue
        # A partial official row must not be mixed with estimated 68-normalized units.
        if weight.loc[month].notna().any():
            continue
        raw = prior_weight * price.loc[month] / price.loc[prev]
        weight.loc[month] = raw / raw.sum() * 100
        ws.loc[month] = 'provisional'
        scales.loc[month] = 'normalized_68_pct'
    sums = weight.sum(axis=1, min_count=68)
    norm = weight.div(sums.where(sums > 0), axis=0) * 100
    norm[(weight < 0).any(axis=1)] = np.nan
    yoy = (price / price.shift(12).where(price.shift(12) > 0) - 1) * 100
    accel = yoy - yoy.shift(12)
    mean = yoy.rolling(60, min_periods=60).mean()
    std = yoy.rolling(60, min_periods=60).std(ddof=1)
    z = (yoy - mean) / std.where(std > 0)
    # Mark provenance of all price observations used, including 12-month denominators.
    est_price = ps.isin(['estimated', 'provisional'])
    yoy_est = est_price | est_price.shift(12, fill_value=False)
    accel_est = yoy_est | yoy_est.shift(12, fill_value=False)
    z_est = yoy_est.rolling(60, min_periods=1).max().astype(bool)
    official_px = pxobs.pivot(index='month', columns='code', values='value').reindex(index=months, columns=['SA0', 'SA0L1E'])
    official_yoy = (official_px / official_px.shift(12).where(official_px.shift(12) > 0) - 1) * 100
    details, groups = [], {key: [] for key in GROUPS}
    for k, month in enumerate(months):
        w = norm.loc[month]
        ready_y = yoy.loc[month].notna().all()
        ready_w = w.notna().all()
        ready_z = z.loc[month].notna().all()
        wstatus = 'missing' if not ready_w else ('provisional' if (ws.loc[month] == 'provisional').any() else ('estimated' if (ws.loc[month] == 'estimated').any() else 'official'))
        for code, c in zip(codes, components):
            y, zz = yoy.at[month, code], z.at[month, code]
            details.append(dict(month=month, **c, price_index=price.at[month, code],
                original_weight=weight.at[month, code], weight_scale=scales.at[month, code], normalized_weight=w[code],
                yoy=y, acceleration=accel.at[month, code], mean_60=mean.at[month, code], std_60=std.at[month, code], z_score=zz,
                window_count=int(yoy[code].iloc[max(0,k-59):k+1].notna().sum()), window_start=months[max(0,k-59)],
                decline=None if pd.isna(y) else bool(y < 0), growth=None if pd.isna(y) else bool(y > 0),
                t_decline=None if pd.isna(zz) else bool(zz < -2), t_growth=None if pd.isna(zz) else bool(zz > 2),
                price_status=ps.at[month, code], weight_status=ws.at[month, code],
                yoy_uses_estimate=bool(yoy_est.at[month, code]), acceleration_uses_estimate=bool(accel_est.at[month, code]),
                window_uses_estimate=bool(z_est.at[month, code])))
        for key, (title, begin) in GROUPS.items():
            if month < begin:
                continue
            uses_est = (z_est if key.startswith('t_') else accel_est if key == 'acceleration' else yoy_est).loc[month].any()
            row = dict(month=month, weight_status=wstatus, uses_estimated_price=bool(uses_est))
            if key in ['measures', 'acceleration']:
                vals = (yoy if key == 'measures' else accel).loc[month]
                row.update(zip(['p10', 'p25', 'p50', 'p75', 'p90'], weighted_quantile(vals, w)))
                row['valid_categories'] = int(vals.notna().sum())
                if key == 'measures':
                    row.update(headline=official_yoy.at[month, 'SA0'], core=official_yoy.at[month, 'SA0L1E'])
                complete = bool(ready_w and vals.notna().all())
            else:
                v = z.loc[month] if key.startswith('t_') else yoy.loc[month]
                valid = v.notna().all()
                flag = v < (-2 if key.startswith('t_') else 0) if 'declines' in key else v > (2 if key.startswith('t_') else 0)
                row.update(count=int(flag.sum()) if valid else np.nan,
                           items_pct=float(flag.sum()/68*100) if valid else np.nan,
                           weight_pct=float(w[flag].sum()) if valid and ready_w else np.nan,
                           valid_categories=int(v.notna().sum()))
                complete = bool(valid and ready_w)
            row['calculation_status'] = 'complete' if complete else 'incomplete'
            row['data_status'] = 'missing' if not complete else ('provisional' if wstatus == 'provisional' else 'estimated' if uses_est or wstatus == 'estimated' else 'official')
            groups[key].append(row)
    return {key: pd.DataFrame(v) for key, v in groups.items()}, pd.DataFrame(details)


def load_inputs(root=ROOT):
    p = root / 'data' / 'input'
    return pd.read_csv(p / 'observations.csv', keep_default_na=False), json.loads((p / 'components.json').read_text(encoding='utf-8'))
