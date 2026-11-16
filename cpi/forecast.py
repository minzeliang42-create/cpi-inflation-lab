"""Versioned forecasts, research exports and realization monitoring.

Run python -m cpi.forecast after the historical update. An unchanged computational
input digest reuses the current vintage. Every successful vintage is immutable;
an error only changes forecast_status.json and preserves the last good pointer.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import uuid
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from .model import ROOT, GROUPS, records, write_json, utcnow
from .forecast_models import MODEL_VERSION, PARAMETERS
from .forecast_research import (panels,run_research,policy_fit,annual_shocks,simulate,
                                diagnostics,information_set,target_yoy)
from .forecast_engine import FIELDS, HORIZONS, indicators, weights_for_path


def input_digest(root,p):
    computational=p['obs'][['month','code','kind','value','status','scale']].sort_values(['month','code','kind','status'])
    anchors=[{k:v for k,v in a.items() if k!='source'} for a in p['anchors']]
    data=computational.to_csv(index=False).encode()+json.dumps(anchors,sort_keys=True).encode()
    for f in ('forecast.py','forecast_models.py','forecast_research.py','forecast_engine.py'):
        data+=(root/'cpi'/f).read_bytes()
    research=root/'data/forecast/research/research.json';calibration=research.parent/'calibration.npz'
    if research.exists() and calibration.exists():
        selected=json.loads(research.read_text(encoding='utf-8'))
        data+=json.dumps(dict(policy=selected['policy'],models=[(c['model'],c['second_model']) for c in selected['chosen']]),sort_keys=True).encode()
        data+=np.load(calibration,allow_pickle=False)['residuals'].tobytes()
    return hashlib.sha256(data).hexdigest()[:20]


def selected_name(research,k):
    c=research['chosen'][k];policy=research['policy']
    return c['model'] if policy=='class_best' else f"ensemble({c['model']},{c['second_model']})" if policy=='class_top2' else policy


def export_workbook(path,tables):
    """Unattended Python exporter, same build dependency as the historical site."""
    import openpyxl
    from openpyxl.styles import Font,PatternFill,Alignment
    wb=openpyxl.Workbook();wb.remove(wb.active)
    for name,df in tables.items():
        ws=wb.create_sheet(name);ws.append(df.columns.tolist())
        for r in records(df):ws.append([r.get(c) if r.get(c) is not None else 'NA' for c in df.columns])
        ws.freeze_panes='C2';ws.auto_filter.ref=ws.dimensions;ws.sheet_view.showGridLines=False
        ws.sheet_properties.pageSetUpPr.fitToPage=True
        for c in ws[1]:
            c.font=Font(name='Arial',bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='173D55')
            ws.column_dimensions[c.column_letter].width=min(43,max(15,len(str(c.value))+2))
        for row in ws.iter_rows(min_row=2):
            for c in row:
                if isinstance(c.value,float):c.number_format='0.000000'
        ws.sheet_properties.tabColor='173D55' if name=='Forecast_Summary' else 'B98C3E'
    wb.save(path)


def detail_rows(p,fp,fw,dd,months,scenario,research,asof,raw=None,price_q=None,yoy_q=None,runtime_models=None):
    rows=[];estimated=p['status'][:,:68]=='estimated';n=len(p['price'])
    all_est=np.vstack([estimated,np.zeros((len(fp),68),bool)])
    all_fc=np.vstack([np.zeros_like(estimated),np.ones((len(fp),68),bool)])
    ye=all_est.copy();yf=all_fc.copy()
    ye[12:]|=all_est[:-12];yf[12:]|=all_fc[:-12]
    for j,m in enumerate(months):
        ix=n+j;start=ix-59
        for k,c in enumerate(p['components']):
            d=dd[j];y,z=d['yoy'][k],d['z_score'][k]
            rows.append(dict(month=m,scenario=scenario,**c,price_index=float(fp[j,k]),
                original_weight=float(raw[j,k] if raw is not None else fw[j,k]),weight_scale='forecast_68_anchor_scale',normalized_weight=float(fw[j,k]),
                yoy=float(y),acceleration=float(d['acceleration'][k]),mean_60=float(d['mean_60'][k]),
                std_60=float(d['std_60'][k]),z_score=float(z),window_count=int(d['window_count'][k]),
                window_start=str(pd.Period(m,freq='M')-59),
                window_estimated_observations=int(ye[max(0,start):ix+1,k].sum()),
                window_forecast_observations=int(yf[max(0,start):ix+1,k].sum()),
                yoy_uses_estimate=bool(ye[ix,k]),
                acceleration_uses_estimate=bool(ye[ix,k] or ye[ix-12,k]),
                window_uses_estimate=bool(ye[max(0,start):ix+1,k].any()),
                decline=bool(y<0),growth=bool(y>0),t_decline=bool(z<-2) if np.isfinite(z) else None,
                t_growth=bool(z>2) if np.isfinite(z) else None,
                price_status='forecast',weight_status='forecast',data_status='forecast',
                model=runtime_models[k] if runtime_models else selected_name(research,k),model_version=MODEL_VERSION,asof=asof,
                weight_assumption='Constant expenditure quantities; no official future RI',
                annual_weight_status='Forecast annual regime scenario' if m[:4]>asof[:4] else 'Forecast price-updated weights',
                uncertainty_type='Empirical joint-path prediction interval' if scenario=='base' else 'Scenario; not a probability bound',
                **({f'{field}_{label}':float(q[qi,j,k]) for field,q in [('price_index',price_q),('yoy',yoy_q)]
                    for qi,label in enumerate(('lower95','lower80','upper80','upper95'))} if price_q is not None else {})))
    return pd.DataFrame(rows)


def group_rows(iv,months,scenario,components,quantiles,research,asof):
    groups={g:[] for g in GROUPS}
    comp=components.groupby('month')
    for j,m in enumerate(months):
        for g in groups:
            row=dict(month=m,data_status='forecast',weight_status='forecast',calculation_status='complete',
                valid_categories=68,scenario=scenario,asof=asof,model_version=MODEL_VERSION,
                model='Bottom-up / '+research['policy'],forecast_horizon=j+1,
                weight_assumption='Constant expenditure quantities; annual regime not official')
            deps=comp.get_group(m)
            flag='window_uses_estimate' if g.startswith('t_') else 'acceleration_uses_estimate' if g=='acceleration' else 'yoy_uses_estimate'
            row['uses_estimated_price']=bool(deps[flag].any())
            if g.startswith('t_'):
                row['window_forecast_observations']=int(deps.window_forecast_observations.max())
                row['window_estimated_observations']=int(deps.window_estimated_observations.max())
            for k,(gg,f) in enumerate(FIELDS):
                if gg!=g:continue
                row[f]=float(iv[j,k])
                if quantiles is not None:
                    for qi,label in enumerate(('lower95','lower80','upper80','upper95')):
                        row[f+'_'+label]=float(quantiles[qi,j,k])
            if g not in ('measures','acceleration'):row['count']=int(round(row['items_pct']*68/100))
            groups[g].append(row)
    return {g:pd.DataFrame(r) for g,r in groups.items()}


def realization_table(root,p):
    manifest=root/'data/forecast/vintages.json'
    columns=['vintage','asof','target','horizon','group','field','forecast','realized','error','realized_status','realized_asof','evaluated_at']
    if not manifest.exists():return pd.DataFrame(columns=columns)
    out=[]
    for v in json.loads(manifest.read_text(encoding='utf-8')):
        f=root/'dist'/v['path']
        if not f.exists():continue
        payload=json.loads(f.read_text(encoding='utf-8'))
        for g,rows in payload['scenarios']['base']['groups'].items():
            truth=p['groups'][g].set_index('month')
            for r in rows:
                if r['month'] not in truth.index:continue
                actual=truth.loc[r['month']]
                for gg,key in FIELDS:
                    if gg!=g or r.get(key) is None or pd.isna(actual[key]):continue
                    out.append(dict(vintage=v['version'],asof=v['asof'],target=r['month'],horizon=r['forecast_horizon'],
                        group=g,field=key,forecast=r[key],realized=float(actual[key]),error=float(r[key]-actual[key]),
                        realized_status=actual.data_status,realized_asof=p['months'][-1],evaluated_at=utcnow()))
    return pd.DataFrame(out,columns=columns)


def report_text(research,score,coverage,diag):
    selected=score[(score.split=='test')&(score.route==research['policy'])]
    baseline=score[(score.split=='test')&(score.route=='flat')]
    direct=score[(score.split=='test')&(score.route==research['direct_benchmark'])]
    lines=['# CPI Inflation Lab V2.0 — Forecast research and validation',
        f"Research frozen as of {research['asof']}. Model version {MODEL_VERSION}.",
        '', '## Data and timing',
        '68 fixed CPI-U NSA expenditure classes; January 2018–October 2026 initial study (106 monthly prices). '+
        'Official RI through September 2026; October RI is historical provisional. Approved estimates are retained. '+
        'Each t statistic uses 60 calendar YoY months including the target, sample standard deviation and strict ±2 cutoffs.',
        'Pseudo-real-time expanding-origin backtests use the revised workbook, not archived release vintages. '+
        'Origin means after that month’s price release; RI is restricted to months before the origin. '+
        'October 2025 interpolated prices are unavailable until November, and motor-insurance October/November until December. '+
        'Origins October/November 2025 are omitted because a complete 68-price origin information set does not exist.',
        '', '## Selection and untouched test',
        f"Development origins: {', '.join(research['development_origins'])}; only target months through 2024-12 select models. "+
        'Final test origins December 2024–September 2026, with target months January 2025–October 2026. '+
        'Horizons 1, 2, 3, 6, 12 and 14 are evaluated wherever realized targets exist. Training expands from January 2018.',
        'Candidate parameters are declared in forecast_models.py. Failed/non-converged fits fall back explicitly to seasonal_mean_trend and are logged. '+
        'Per-class choices minimize the average of absolute log-price percentage error and absolute YoY error over development horizon cells. '+
        'Coherent B policies are then ranked by an equal-six-group, flat-baseline-normalized MAE objective (0.1 pp denominator floor). '+
        'No final-test error or interval coverage tunes a choice.',
        f"Selected B policy: **{research['policy']}**. Selected A comparator: **{research['direct_benchmark']}**.",
        'Route A directly extrapolates the indicators (persistence, damped trend and AR(1)); quantiles/shares are structurally projected. '+
        'Route B forecasts 68 price indices and two companion official-index series, then recomputes all indicators. '+
        'The coherent B path is published to supply auditable component prices, weights, rolling windows and scenarios. '+
        'A may outperform B on individual indicators; the table below records the actual tradeoff.',
        '', '|Group|B test MAE|A test MAE|Flat B MAE|', '|---|---:|---:|---:|']
    for g in GROUPS:
        def mean(df):return df.loc[df.group==g,'mae'].mean()
        lines.append(f'|{g}|{mean(selected):.4f}|{mean(direct):.4f}|{mean(baseline):.4f}|')
    lines += ['', 'Group averages combine fields/horizons equally; they are not pooled price-level errors. '+
        'CSV exports contain n, horizon, field, MAE, RMSE, bias and direction accuracy. '+
        'Per-class raw-index errors, percentage errors, YoY errors and origin-weighted errors are separate to avoid mixing index scales.',
        '', '## Uncertainty and scenarios',
        f"{research['calibration_paths']} centered, overlapping 14×70 development error blocks (origins {research['calibration_origins'][0]}–{research['calibration_origins'][-1]}) "+
        'are resampled jointly, with a global random sign. All classes and all horizons within a block move together. '+
        'Annual weight-shift vectors are sampled jointly at January. 400 simulated final paths pass through all six nonlinear calculations. '+
        'The 80/95 labels denote empirical central quantiles, not guaranteed coverage. Overlapping origins reduce effective sample size. '+
        'Held-out coverage below was measured with 120 draws per origin, using only pre-2025 weight-shift calibration.',
        '', '|Horizon|Cells|Observed 80% coverage|Observed 95% coverage|', '|---|---:|---:|---:|']
    for h,r in coverage.groupby('horizon'):
        lines.append(f'|{h}|{int(r.n.sum())}|{np.average(r.coverage80,weights=r.n):.1%}|{np.average(r.coverage95,weights=r.n):.1%}|')
    lines += ['', 'Base is the selected point path. Low/high are two complete joint price-error paths ranked by the weighted near-term inflation change; '+
        'they are sensitivity scenarios, not separate probabilities and not pointwise lower/upper indicator bounds. '+
        'The separate weight-only sensitivity table applies each historical January RI regime-shift vector to the same base prices.',
        '', '## Annual RI and official companions',
        '2027 base weights assume constant expenditure quantities, updated by forecast prices and renormalized to 100%. '+
        'They are Forecast, not official or provisional RI. Historical new-year extrapolation remains forbidden. '+
        'A separately validated new-regime December bridge, when present, replaces the forecast regime from January; '+
        'a subsequently official monthly RI anchors the next forecast vintage. Annual assumptions never overwrite historical inputs.',
        'Headline/core price models are separate from the 68 classes. A training-only interior missing value may be interpolated using origin-known observations '+
        'to fit a statistical model, but the engine retains the official historical NA denominator. '+
        'October 2026 official headline/core YoY and October 2027 corresponding forecast acceleration remain NA when the official October 2025 index is absent.',
        '', '## Diagnostics and limits',
        f"Median class monthly log-change sample SD: {diag.monthly_log_change_std.median():.3f}%; "+
        f"maximum: {diag.monthly_log_change_std.max():.3f}%. Diagnostics CSV records calendar seasonality, pandemic/recent volatility, weights and approved estimates.",
        *['- '+s for s in research['limitations']],
        '- t-diffusion is discontinuous at z=±2. Small path changes may flip categories; near-threshold classes and estimated/forecast window counts accompany forecasts.',
        '- Future shocks, structural changes and annual expenditure reweighting are not predictable from this short univariate sample. Long-horizon diffusion has lower confidence.',
        '- Historical estimated target observations are retained in scoring and labeled in price_errors.csv; realized indicator scores use the approved reconstructed history.',
        '', '## Reproducibility and cloud operation',
        'python -m cpi.forecast creates/reuses the frozen study, publishes an immutable input/code digest vintage, and switches the pointer only after validation. '+
        'No input change means no model fitting. New observations or annual anchors produce a new vintage; old paths remain available and are evaluated against realized indicators. '+
        'Forecast failure retains the prior pointer. BLS channel failures and forecast status remain separate. '+
        'Research is deliberately not retuned on every release; change MODEL_VERSION and explicitly rerun research to revise the validated specification.',
        '', '## Method references',
        '- [Forecasting: Principles and Practice — time-series cross-validation](https://otexts.com/fpp3/tscv.html)',
        '- [statsmodels exponential smoothing](https://www.statsmodels.org/stable/examples/notebooks/generated/exponential_smoothing.html)',
        '- [statsmodels state-space forecasting](https://www.statsmodels.org/stable/examples/notebooks/generated/statespace_forecasting.html)',
        '- [statsmodels STL decomposition](https://www.statsmodels.org/stable/examples/notebooks/generated/stl_decomposition.html)',
        '- [BLS CPI relative importance](https://www.bls.gov/cpi/tables/relative-importance/)']
    return '\n\n'.join(lines)+'\n'


def run(root=ROOT,rerun_research=False):
    root=Path(root);(root/'.staging').mkdir(exist_ok=True);(root/'data/forecast').mkdir(parents=True,exist_ok=True)
    pointer=root/'dist/current_forecast.json';status_file=root/'dist/forecast_status.json'
    old=json.loads(pointer.read_text(encoding='utf-8')) if pointer.exists() else None
    stage=root/'.staging'/('forecast-'+uuid.uuid4().hex)
    try:
        p=panels(root);digest=input_digest(root,p)
        if old and old.get('input_digest')==digest and not rerun_research:
            write_json(status_file,dict(state='unchanged',checked_at=utcnow(),last_success=old['generated_at'],
                message='Inputs and model unchanged; retained validated forecast, no refit',version=old['version']))
            realization_table(root,p).to_csv(root/'dist/forecast_realizations.csv',index=False)
            return old
        rf=root/'data/forecast/research/research.json'
        research=json.loads(rf.read_text(encoding='utf-8')) if rf.exists() else None
        if rerun_research or not research or research['model_version']!=MODEL_VERSION: research=run_research(root,p)
        digest=input_digest(root,p)
        asof=p['months'][-1];end=max(pd.Period('2027-12',freq='M'),pd.Period(asof,freq='M')+12)
        months=pd.period_range(pd.Period(asof,freq='M')+1,end,freq='M').astype(str).tolist();h=len(months)
        history=p['price'];w=p['weight'][-1]
        if not np.isfinite(history[-1]).all() or not np.isfinite(history[:,:68]).all():raise ValueError('Incomplete forecast origin prices')
        if not np.isfinite(w).all():
            # Forecast-only annual scenario, no relaxation of historical guard.
            info=information_set(p,asof)
            if info is None:raise ValueError('No complete validated forecast weight anchor')
            w=info[1]
        chosen=[(c['model'],c['second_model']) for c in research['chosen']]
        base,failures=policy_fit(root,history,h,research['policy'],chosen)
        runtime_models=[selected_name(research,k) for k in range(70)]
        for failure in failures:
            k=failure['column'];runtime_models[k]+='; fallback '+failure['fallback']
        residuals=np.load(rf.parent/'calibration.npz',allow_pickle=False)['residuals']
        shifts=annual_shocks(p);shocks=np.array([s['log_shift'] for s in shifts])
        rng=np.random.default_rng(20261116)
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',message='All-NaN slice encountered')
            sims,simprices,simweights=simulate(history,base,w,residuals,shocks,months,asof,rng,n=400,
                return_paths=True,new_anchors=p['anchors'],codes=p['codes'][:68])
            quantiles=np.nanquantile(sims,[.025,.1,.9,.975],axis=0)
            price_q=np.nanquantile(simprices,[.025,.1,.9,.975],axis=0)
            yoy_q=np.nanquantile(np.array([target_yoy(history,path) for path in simprices]),[.025,.1,.9,.975],axis=0)
        ranking=np.array([np.mean((np.exp(r[:2,:68])-1)@w/100) for r in residuals])
        low=residuals[np.argsort(ranking)[int(.1*(len(ranking)-1))]]
        high=residuals[np.argsort(ranking)[int(.9*(len(ranking)-1))]]
        def resize(block):return np.vstack([block,np.repeat(block[-1:],max(0,h-len(block)),axis=0)])[:h]
        paths={'base':base,'low':base*np.exp(resize(low)),'high':base*np.exp(resize(high))}
        prices=[];weights=[];allcomp=[];allind=[];scenarios={};flat=[];weight_sensitivity=[]
        for scenario,fp in paths.items():
            fw,raw=weights_for_path(w,history[-1],fp,months=months,new_anchors=p['anchors'],codes=p['codes'][:68],anchor_month=asof,return_raw=True)
            iv,dd=indicators(history,fp,fw,return_details=True)
            yp=target_yoy(history,fp)
            comp=detail_rows(p,fp,fw,dd,months,scenario,research,asof,raw,
                price_q if scenario=='base' else None,yoy_q if scenario=='base' else None,runtime_models)
            groups=group_rows(iv,months,scenario,comp,quantiles if scenario=='base' else None,research,asof)
            scenarios[scenario]={'groups':{g:records(df) for g,df in groups.items()},'components':records(comp)}
            allcomp.append(comp)
            for g,df in groups.items():allind.append(df.assign(group=g))
            for j,m in enumerate(months):
                for k,c in enumerate(p['codes']):
                    prices.append(dict(month=m,scenario=scenario,code=c,price_index=float(fp[j,k]),yoy=float(yp[j,k]),
                        model=runtime_models[k],status='Forecast',asof=asof,model_version=MODEL_VERSION,
                        **({f'price_index_{label}':float(price_q[qi,j,k]) for qi,label in enumerate(('lower95','lower80','upper80','upper95'))} if scenario=='base' else {})))
                for k,c in enumerate(p['codes'][:68]):
                    weights.append(dict(month=m,scenario=scenario,code=c,forecast_weight=float(raw[j,k]),normalized_weight=float(fw[j,k]),
                        weight_scale='forecast_68_anchor_scale',
                        status='Forecast',asof=asof,annual_assumption='Constant expenditure quantities; future annual RI unknown'))
                for k,(g,f) in enumerate(FIELDS):
                    flat.append(dict(month=m,scenario=scenario,group=g,field=f,value=float(iv[j,k]),status='Forecast',asof=asof,
                        **({label:float(quantiles[qi,j,k]) for qi,label in enumerate(('lower95','lower80','upper80','upper95'))} if scenario=='base' else {})))
        # Historical annual shift sensitivity with the same price point path.
        for shift in shifts:
            fw=weights_for_path(w,history[-1],base,np.array(shift['log_shift']),months,anchor_month=asof,
                new_anchors=p['anchors'],codes=p['codes'][:68])
            iv=indicators(history,base,fw)
            for j,m in enumerate(months):
                if m[:4]<=asof[:4]:continue
                for k,(g,f) in enumerate(FIELDS):
                    weight_sensitivity.append(dict(month=m,scenario='weight_shift_'+str(shift['year']),group=g,field=f,
                        value=float(iv[j,k]),status='Forecast sensitivity',asof=asof))
        score=pd.read_csv(rf.parent/'indicator_scores.csv');coverage=pd.read_csv(rf.parent/'coverage.csv')
        diag=pd.read_csv(rf.parent/'diagnostics.csv')
        selection=[]
        pscores=pd.read_csv(rf.parent/'price_scores.csv')
        difficulty_cutoff=np.median([c['development_score'] for c in research['chosen']])
        for k,c in enumerate(research['chosen']):
            bs=c['candidate_scores']['flat'];ss=c['candidate_scores']['seasonal_mean_trend']
            test=pscores[(pscores.route==research['policy'])&(pscores.code==c['code'])&(pscores.horizon==1)]
            selection.append(dict(code=c['code'],selected_model=selected_name(research,k),best_model=c['model'],
                second_model=c['second_model'],development_score=c['development_score'],
                development_observations=c['development_observations'],parameters=PARAMETERS[c['model']],
                selection_target_cutoff=research['selection_cutoff'],final_test_used_for_selection=False,
                training_only_missing_companion_imputation=bool(k>=68 and np.isnan(history[:,k]).any()),
                improvement_vs_flat_pct=100*(1-c['development_score']/bs) if bs>0 else None,
                improvement_vs_seasonal_mean_pct=100*(1-c['development_score']/ss) if ss>0 else None,
                heldout_1m_yoy_mae=None if test.empty else float(test.iloc[0].yoy_mae),
                difficulty='Higher development error' if c['development_score']>difficulty_cutoff else 'Lower development error',
                selection_reason='Lowest development price/YoY loss; policy separately validated on six indicator groups'))
            selection[-1]['current_forecast_runtime_model']=runtime_models[k]
        summary=[]
        for r in flat:
            if r['scenario']!='base':continue
            j=months.index(r['month']);k=FIELDS.index((r['group'],r['field']))
            hh=min(HORIZONS,key=lambda hh:abs(hh-j-1))
            bt=score[(score.split=='test')&(score.route==research['policy'])&(score.group==r['group'])&(score.field==r['field'])&(score.horizon==hh)]
            current=p['values'][-1,k];firstcomp=allcomp[0][allcomp[0].month==r['month']]
            old=p['details'][p['details'].month==asof].set_index('code').yoy
            drive=firstcomp.copy();drive['proxy']=drive.normalized_weight/100*(drive.yoy-drive.code.map(old))
            drivers=drive.reindex(drive.proxy.abs().sort_values(ascending=False).index).head(3)
            summary.append(dict(**r,horizon=j+1,asof_historical=float(current),
                change_from_asof=float(r['value']-current),
                nearest_test_horizon=hh,test_mae=None if bt.empty else float(bt.iloc[0].mae),
                test_n=0 if bt.empty else int(bt.iloc[0].n),confidence='Limited; empirical intervals, short t history and sparse long-horizon tests',
                annual_weight_assumption='Forecast constant-expenditure-weight scenario',model_version=MODEL_VERSION,
                main_weighted_yoy_change_drivers='; '.join(f'{d.code}: {d.proxy:.4f} pp' for d in drivers.itertuples()),
                near_zero_categories=int(firstcomp.yoy.abs().lt(.25).sum()),
                near_z_minus2_categories=int(firstcomp.z_score.add(2).abs().lt(.25).sum()),
                near_z_plus2_categories=int(firstcomp.z_score.sub(2).abs().lt(.25).sum()),
                assumptions='NSA univariate models; constant expenditure quantities; annual RI unknown; approved estimates retained'))
        meta=dict(app_version='2.0',model_version=MODEL_VERSION,asof=asof,forecast_start=months[0],forecast_end=months[-1],
            generated_at=utcnow(),input_digest=digest,policy=research['policy'],training_start='2018-01',
            official_price_month=asof,official_weight_month=p['obs'][(p['obs'].kind=='weight')&(p['obs'].status=='official')].month.max(),
            weight_assumption='Forecast: constant expenditure quantities; 2027 annual RI not official',
            interval_method=research['interval_method'],calibration_paths=len(residuals),simulated_paths=400,
            data_status='Forecast',fit_failures=failures,research_frozen_asof=research['asof'],
            history_contains_approved_estimates=True,forecast_update_state='success')
        version=digest;stage.mkdir();bundle=stage/version;bundle.mkdir()
        tables={'Forecast_Summary':pd.DataFrame(summary),'Forecast_Prices':pd.DataFrame(prices),
            'Forecast_Weights':pd.DataFrame(weights),'Forecast_Components':pd.concat(allcomp,ignore_index=True),
            'Forecast_Indicators':pd.concat(allind,ignore_index=True),'Forecast_Backtest':pd.read_csv(rf.parent/'indicator_errors.csv'),
            'Forecast_Model_Selection':pd.DataFrame(selection),'Forecast_Scenarios':pd.DataFrame(flat+weight_sensitivity)}
        for name,df in tables.items():df.to_csv(bundle/(name+'.csv'),index=False,na_rep='NA',encoding='utf-8-sig')
        for g in GROUPS:
            pd.concat([pd.DataFrame(s['groups'][g]) for s in scenarios.values()],ignore_index=True).to_csv(
                bundle/(g+'_forecast.csv'),index=False,na_rep='NA',encoding='utf-8-sig')
        export_workbook(bundle/'CPI_Forecast.xlsx',tables)
        payload=dict(meta=meta,scenarios=scenarios,backtest=records(score),coverage=records(coverage),
                     model_selection=selection,summary=records(tables['Forecast_Summary']),
                     annual_weight_sensitivity=records(pd.DataFrame(weight_sensitivity)))
        write_json(bundle/'forecast.json',payload)
        focus=pd.DataFrame(summary);near=focus[focus.month.isin(months[:2])]
        report=report_text(research,score,coverage,diag)
        report+='\n## Near-term forecast results — model output, not official data\n\n'
        report+=f'Forecast as of {asof}; generated {meta["generated_at"]}. Units: % for inflation/shares; pp for acceleration.\n\n'
        report+='|Month|Group|Series|Base|Change from as-of history|80% empirical interval|Test MAE (nearest horizon)|\n|---|---|---|---:|---:|---|---:|\n'
        def val(x):return 'NA' if pd.isna(x) else f'{x:.3f}'
        for r in near.itertuples():
            report+=f'|{r.month}|{r.group}|{r.field}|{val(r.value)}|{val(r.change_from_asof)}|{val(r.lower80)}–{val(r.upper80)}|{val(r.test_mae)}|\n'
        report+='\nMissing October 2026 official YoY makes the corresponding October comparison NA; the latest valid official value is shown separately on the website.\n\n'
        for month in months[:2]:
            d=allcomp[0].query('month == @month').copy();prior=p['details'].query('month == @asof').set_index('code').yoy
            d['proxy']=d.normalized_weight/100*(d.yoy-d.code.map(prior))
            drivers=d.reindex(d.proxy.abs().sort_values(ascending=False).index).head(5)
            report+=f'### {month} drivers and threshold sensitivity\n\n'
            for r in drivers.itertuples():report+=f'- {r.name} ({r.code}): weighted YoY-change proxy {r.proxy:.4f} pp; forecast YoY {r.yoy:.3f}%; model {r.model}.\n'
            report+=f'\nClasses within 0.25 pp of zero YoY: {d.yoy.abs().lt(.25).sum()}; within 0.25 Z of −2: {d.z_score.add(2).abs().lt(.25).sum()}; of +2: {d.z_score.sub(2).abs().lt(.25).sum()}. '
            report+='One class crossing a cutoff changes count share by 100/68 = 1.470588 pp and weight share by its own weight. These are discontinuous forecasts, not smooth linear aggregates.\n\n'
        report+='## Annual weight sensitivity\n\n|Historical January shift|L1 absolute class-share change (pp)|Maximum class change (pp)|\n|---|---:|---:|\n'
        for s in shifts:report+=f'|{s["year"]}|{s["l1_share_change_pp"]:.4f}|{s["max_class_change_pp"]:.4f}|\n'
        report+='\nForecast_Scenarios contains the full impact of applying each joint historical annual shift to base prices. The base scenario uses no guessed annual shift.\n'
        (bundle/'Research_Report.md').write_text(report,encoding='utf-8')
        # Validate complete forecast grids and exact source-of-download identity.
        assert len(months)>=12 and months[-1]>='2027-12'
        assert len(tables['Forecast_Components'])==68*h*3
        assert tables['Forecast_Weights'].groupby(['month','scenario']).normalized_weight.sum().sub(100).abs().max()<1e-9
        cdf=tables['Forecast_Components']
        assert cdf[['price_index','normalized_weight','yoy','acceleration','mean_60','std_60','z_score']].notna().all().all()
        assert cdf.window_count.eq(60).all() and cdf.std_60.gt(0).all()
        for (_,month),d in cdf.groupby(['scenario','month']):
            assert int(d.decline.sum()+d.growth.sum()+d.yoy.eq(0).sum())==68
        for s in scenarios.values():
            for g in ('measures','acceleration'):
                q=pd.DataFrame(s['groups'][g])[['p10','p25','p50','p75','p90']]
                assert q.diff(axis=1).iloc[:,1:].ge(-1e-10).all().all()
        dest=root/'dist/forecasts'/version;dest.parent.mkdir(exist_ok=True)
        if not dest.exists():shutil.move(str(bundle),str(dest))
        else:meta['generated_at']=json.loads((dest/'forecast.json').read_text(encoding='utf-8'))['meta']['generated_at']
        (root/'dist/research').mkdir(exist_ok=True)
        for f in rf.parent.iterdir():
            if f.is_file():shutil.copy2(f,root/'dist/research'/f.name)
        # Archive index is append-only. Pointer is atomically replaced last.
        manifest=root/'data/forecast/vintages.json'
        vintages=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
        item=dict(version=version,path=f'forecasts/{version}/forecast.json',input_digest=digest,asof=asof,
                  generated_at=meta['generated_at'],forecast_end=months[-1])
        if not any(v['version']==version for v in vintages):vintages.append(item)
        write_json(manifest,vintages);write_json(stage/'pointer.json',item)
        realization_table(root,p).to_csv(root/'dist/forecast_realizations.csv',index=False)
        os.replace(stage/'pointer.json',pointer)
        write_json(status_file,dict(state='success',checked_at=utcnow(),last_success=meta['generated_at'],version=version,
            message='Forecast validated; immutable vintage published'))
        print(json.dumps(item));return item
    except Exception as exc:
        write_json(status_file,dict(state='failed',checked_at=utcnow(),last_success=old.get('generated_at') if old else None,
            message=str(exc),retained_version=old.get('version') if old else None))
        raise
    finally:
        if stage.exists() and stage.resolve().is_relative_to((root/'.staging').resolve()):shutil.rmtree(stage)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--research',action='store_true',help='Explicitly rerun model selection and held-out study')
    parser.add_argument('--upstream-failed',action='store_true',help='Preserve forecasts after official ingestion failed')
    args=parser.parse_args()
    if args.upstream_failed:
        path=ROOT/'dist/current_forecast.json';old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        write_json(ROOT/'dist/forecast_status.json',dict(state='failed',checked_at=utcnow(),last_success=old.get('generated_at'),
            retained_version=old.get('version'),message='Official ingestion failed; prior validated forecast retained; no refit'))
        raise SystemExit(1)
    run(rerun_research=args.research)

if __name__=='__main__':main()
