"""Expanding-origin, vintage-gated pseudo-real-time forecast research.

Selection targets end in 2024-12; the frozen choices are assessed on targets
2025-01 onward. No release-vintage database is available: revised workbook
observations are used, so this is NOT a strict real-time backtest.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .model import calculate, load_inputs, records, write_json, utcnow
from .forecast_engine import FIELDS, HORIZONS, indicators, weights_for_path, direct_forecast
from .forecast_models import CANDIDATES, PARAMETERS, MODEL_VERSION, predict_panel


def panels(root):
    obs, components=load_inputs(root)
    ap=root/'data/input/annual_anchors.json'
    anchors=json.loads(ap.read_text(encoding='utf-8')) if ap.exists() else []
    groups,details=calculate(obs,components,anchors)
    codes=[c['code'] for c in components]+['SA0','SA0L1E']
    months=pd.period_range('2018-01',obs[obs.kind=='price'].month.max(),freq='M').astype(str).tolist()
    selected=obs.assign(rank=obs.status.map({'official':0,'estimated':1,'provisional':2})).sort_values('rank').drop_duplicates(['month','kind','code'])
    price=selected[selected.kind=='price'].pivot(index='month',columns='code',values='value').reindex(index=months,columns=codes).to_numpy(float).copy()
    # Companions use official history only, even if future imports contain estimates.
    for k in (68,69):
        official=selected[(selected.kind=='price')&(selected.code==codes[k])&(selected.status=='official')].set_index('month').value
        price[:,k]=official.reindex(months).to_numpy(float)
    weight=details.pivot(index='month',columns='code',values='normalized_weight').reindex(index=months,columns=codes[:68]).to_numpy(float)
    status=selected[selected.kind=='price'].pivot(index='month',columns='code',values='status').reindex(index=months,columns=codes).fillna('missing').to_numpy()
    values=np.column_stack([groups[g].set_index('month')[f].reindex(months) for g,f in FIELDS])
    return dict(obs=obs,components=components,codes=codes,months=months,price=price,weight=weight,
                status=status,values=values,groups=groups,details=details,anchors=anchors)


def information_set(p,origin):
    """As of after origin-month prices: RI available through origin minus one.

    Workbook publication timestamps are unavailable. Approved ex-post interpolation
    is conservatively gated by its *last input month*: Nov 2025 except motor
    insurance Oct/Nov, which needs Dec 2025. October estimated weights need Dec.
    """
    t=p['months'].index(origin)
    history=p['price'][:t+1].copy()
    for m,code,available in [('2025-10',c,'2025-12' if c=='SETE' else '2025-11') for c in p['codes'][:68]]+[
            ('2025-11','SETE','2025-12')]:
        if m<=origin<available and m in p['months']:
            i,j=p['months'].index(m),p['codes'].index(code)
            if p['status'][i,j]=='estimated': history[i,j]=np.nan
    if not np.isfinite(history[:,:68]).all(): return None
    # Weight availability is a conservative month lag, including annual changes.
    selected=p['obs'][p['obs'].kind=='weight'].copy()
    selected=selected[selected.month<origin]
    selected=selected[~((selected.month=='2025-10')&(selected.status=='estimated')&(origin<'2025-12'))]
    selected=selected.assign(rank=selected.status.map({'official':0,'estimated':1,'provisional':2})).sort_values('rank').drop_duplicates(['month','code'])
    counts=selected.groupby('month').code.nunique()
    eligible=counts[counts==68].index.tolist()
    if not eligible: return None
    wm=max(eligible); wr=selected[selected.month==wm].set_index('code').value.reindex(p['codes'][:68]).to_numpy(float)
    wi=p['months'].index(wm)
    raw=wr*history[-1,:68]/history[wi,:68]
    currentw=raw/raw.sum()*100
    return history,currentw,wm


def fit_cached(root,history,horizon,methods):
    fingerprint=hashlib.sha256(history.tobytes()+json.dumps(methods).encode()+
              (root/'cpi/forecast_models.py').read_bytes()).hexdigest()[:24]
    folder=root/'.staging/forecast-fits';folder.mkdir(parents=True,exist_ok=True)
    file=folder/(fingerprint+'.npz')
    if file.exists():
        with np.load(file,allow_pickle=False) as z:
            if len(z['price'])>=horizon: return z['price'][:horizon],json.loads(str(z['failures']))
    forecast,failures=predict_panel(history,max(14,horizon),methods)
    np.savez_compressed(file,price=forecast,failures=json.dumps(failures))
    return forecast[:horizon],failures


def annual_shocks(p):
    rows=[]
    for year in range(2019,int(p['months'][-1][:4])+1):
        jan=f'{year}-01';dec=f'{year-1}-12'
        if jan not in p['months']: continue
        j,d=p['months'].index(jan),p['months'].index(dec)
        prior=p['weight'][d]*p['price'][j,:68]/p['price'][d,:68]
        predicted=prior/prior.sum()*100
        actual=p['weight'][j]
        if (actual>0).all() and (predicted>0).all():
            rows.append(dict(year=year,log_shift=np.log(actual/predicted).tolist(),
                             l1_share_change_pp=float(np.abs(actual-predicted).sum()),
                             max_class_change_pp=float(np.abs(actual-predicted).max())))
    return rows


def diagnostics(p):
    rows=[];n=len(p['months']);lp=np.log(p['price'][:,:68]);d=np.diff(lp,axis=0)*100
    for k,c in enumerate(p['components']):
        monthly=d[:,k];season=[monthly[np.arange(1,n)%12==m].mean() for m in range(12)]
        fitted=np.array([season[i%12] for i in range(1,n)])
        rows.append(dict(**c,months=n,missing_price=int(np.isnan(lp[:,k]).sum()),
            estimated_price_months=int((p['status'][:,k]=='estimated').sum()),
            mean_monthly_log_change=float(np.mean(monthly)),
            last_24m_annualized_log_trend=float(np.mean(monthly[-24:])*12),
            latest_yoy=float((p['price'][-1,k]/p['price'][-13,k]-1)*100),
            mean_yoy=float(np.mean((p['price'][12:,k]/p['price'][:-12,k]-1)*100)),
            monthly_log_change_std=float(np.std(monthly,ddof=1)),
            seasonal_variance_share=float(max(0,1-np.var(monthly-fitted)/max(np.var(monthly),1e-12))),
            pandemic_2020_2022_std=float(np.std(monthly[23:59],ddof=1)),
            recent_24m_std=float(np.std(monthly[-24:],ddof=1)),latest_weight=float(p['weight'][-1,k]),
            large_change_months=int((np.abs(monthly-np.median(monthly))>3*max(np.std(monthly,ddof=1),1e-9)).sum())))
    return pd.DataFrame(rows)


def target_yoy(history,future):
    p=np.vstack([history,future]);t=len(history)
    return (p[t:]/p[t-12:len(p)-12]-1)*100


def truth_for(p,t,h):
    return p['values'][t+1:t+1+h]


def metric_rows(pred,actual,origin_values,route,origin,split):
    out=[]
    for h in HORIZONS:
        if h>len(pred):continue
        for k,(g,f) in enumerate(FIELDS):
            x,y=pred[h-1,k],actual[h-1,k]
            if np.isfinite(x) and np.isfinite(y):
                out.append(dict(split=split,route=route,origin=origin,horizon=h,group=g,field=f,
                    predicted=float(x),actual=float(y),error=float(x-y),
                    direction_correct=None if not np.isfinite(origin_values[k]) else bool(np.sign(x-origin_values[k])==np.sign(y-origin_values[k]))))
    return out


def aggregate(rows):
    df=pd.DataFrame(rows)
    if df.empty:return df
    return df.groupby(['split','route','horizon','group','field'],dropna=False).agg(
        n=('error','size'),mae=('error',lambda x:float(np.mean(np.abs(x)))),
        rmse=('error',lambda x:float(np.sqrt(np.mean(x*x)))),bias=('error','mean'),
        direction_accuracy=('direction_correct','mean')).reset_index()


def policy_path(allpaths,policy,chosen):
    if policy=='class_best':return np.column_stack([allpaths[m][:,k] for k,(m,_) in enumerate(chosen)])
    if policy=='class_top2':return np.column_stack([np.sqrt(allpaths[m][:,k]*allpaths[n][:,k]) for k,(m,n) in enumerate(chosen)])
    return allpaths[policy]


def policy_fit(root,history,h,policy,chosen):
    if policy in ('class_best','class_top2'):
        a,fa=fit_cached(root,history,h,[m for m,_ in chosen])
        if policy=='class_best':return a,fa
        b,fb=fit_cached(root,history,h,[n for _,n in chosen]);return np.sqrt(a*b),fa+fb
    return fit_cached(root,history,h,[policy]*70)


def run_research(root,p):
    folder=root/'data/forecast/research';folder.mkdir(parents=True,exist_ok=True)
    selection_cutoff='2024-12';test_start='2025-01'
    dev_origins=pd.period_range('2021-12','2024-09',freq='3M').astype(str).tolist()
    dev={};price_losses=np.zeros((len(CANDIDATES),70));price_counts=np.zeros_like(price_losses)
    failures=[];price_rows=[];skipped=[]
    for oi,origin in enumerate(dev_origins):
        info=information_set(p,origin)
        if info is None:skipped.append(origin);continue
        history,w,wm=info;t=p['months'].index(origin)
        h=min(14,p['months'].index(selection_cutoff)-t)
        allpaths={}
        for mi,method in enumerate(CANDIDATES):
            future,ff=fit_cached(root,history,14,[method]*70);allpaths[method]=future
            failures.extend(dict(origin=origin,code=p['codes'][f.pop('column')],**f) for f in [dict(x) for x in ff])
            actual=p['price'][t+1:t+1+h];yp=target_yoy(history,future)[:h]
            ya=(p['price'][t+1:t+1+h]/p['price'][t-11:t-11+h]-1)*100
            for hh in HORIZONS:
                if hh>h:continue
                e=np.abs(np.log(future[hh-1]/actual[hh-1]))*100
                ye=np.abs(yp[hh-1]-ya[hh-1])
                loss=(e+ye)/2;valid=np.isfinite(loss)
                price_losses[mi,valid]+=loss[valid];price_counts[mi,valid]+=1
        dev[origin]=(history,w,allpaths,h,wm)
        print(f'Research selection {oi+1}/{len(dev_origins)} {origin}',flush=True)
    scores=price_losses/np.maximum(price_counts,1)
    order=np.argsort(scores,axis=0)
    chosen=[(CANDIDATES[order[0,k]],CANDIDATES[order[1,k]]) for k in range(70)]
    selection=[dict(code=c,model=chosen[k][0],second_model=chosen[k][1],
        development_score=float(scores[order[0,k],k]),development_observations=int(price_counts[order[0,k],k]),
        candidate_scores={m:float(scores[i,k]) for i,m in enumerate(CANDIDATES)}) for k,c in enumerate(p['codes'])]
    rows=[];policies=['class_best','class_top2',*CANDIDATES]
    for origin,(history,w,paths,h,wm) in dev.items():
        t=p['months'].index(origin);actual=truth_for(p,t,h)
        for policy in policies:
            fp=policy_path(paths,policy,chosen)[:h]
            fw=weights_for_path(w,history[-1],fp)
            iv=indicators(history,fp,fw)
            rows+=metric_rows(iv,actual,p['values'][t],policy,origin,'selection')
        # Direct route receives origin-known indicator history recomputed with
        # gated prices and lagged RI, not finalized future weights.
        direct_values=known_indicator_history(p,history,t,w)
        for route in ('direct_flat','direct_trend','direct_ar'):
            iv=direct_forecast(direct_values,h,route)
            mask_companions(iv,history,t,h)
            rows+=metric_rows(iv,actual,p['values'][t],route,origin,'selection')
    ag=aggregate(rows)
    # Equal six-group weighting of per-field MAE relative to the flat B baseline.
    # Identical origin/field/horizon cells for each route; denominator floor .1 pp.
    base=ag[ag.route=='flat'].set_index(['horizon','group','field']).mae
    objectives={}
    for route,r in ag.groupby('route'):
        r=r.copy();r['ratio']=[x/max(.1,base.loc[(h,g,f)]) for x,h,g,f in zip(r.mae,r.horizon,r.group,r.field)]
        objectives[route]=float(r.groupby('group').ratio.mean().mean())
    policy=min(policies,key=lambda k:objectives[k]);direct=min(('direct_flat','direct_trend','direct_ar'),key=lambda k:objectives[k])
    print(f'Frozen policy: {policy}; direct benchmark: {direct}',flush=True)
    # Calibration dates are strictly before the final test. Models/family choices
    # frozen above. Whole 14x70 error matrices retain cross-series/time dependence.
    residuals=[];calibration_origins=[]
    for origin in pd.period_range('2022-01','2023-10',freq='M').astype(str):
        history,w,wm=information_set(p,origin);t=p['months'].index(origin)
        fp,ff=policy_fit(root,history,14,policy,chosen)
        failures.extend(dict(phase='calibration',origin=origin,route=policy,code=p['codes'][f.pop('column')],**f) for f in [dict(x) for x in ff])
        actual=p['price'][t+1:t+15]
        if np.isfinite(actual).all():
            residuals.append(np.log(actual/fp));calibration_origins.append(origin)
    residuals=np.array(residuals);residuals-=residuals.mean(axis=0,keepdims=True)
    # Test-period price/indicator errors, and interval coverage. Nothing below
    # changes the selected policy, parameters, or residual calibration.
    coverage=[];shocks=annual_shocks(p)
    pretest_shocks=np.array([s['log_shift'] for s in shocks if s['year']<=2024])
    test_origins=pd.period_range('2024-12',p['months'][-2],freq='M').astype(str).tolist()
    rng=np.random.default_rng(20261116)
    for oi,origin in enumerate(test_origins):
        info=information_set(p,origin)
        if info is None: skipped.append(origin);continue
        history,w,wm=info;t=p['months'].index(origin);h=min(14,len(p['months'])-t-1)
        paths={}
        for route in dict.fromkeys([policy,'class_top2','flat','trend_3','trend_6','trend_12','seasonal_naive','yoy_persistence','seasonal_mean_trend']):
            fp,ff=policy_fit(root,history,h,route,chosen);paths[route]=fp
            failures.extend(dict(phase='test',origin=origin,route=route,code=p['codes'][f.pop('column')],**f) for f in [dict(x) for x in ff])
            fw=weights_for_path(w,history[-1],fp)
            iv=indicators(history,fp,fw)
            rows+=metric_rows(iv,truth_for(p,t,h),p['values'][t],route,origin,'test')
            # Per-class price errors and YoY errors with origin-specific weights.
            yp=target_yoy(history,fp);actual=p['price'][t+1:t+1+h]
            ya=(actual/p['price'][t-11:t-11+h]-1)*100
            for hh in HORIZONS:
                if hh>h:continue
                for k,c in enumerate(p['codes']):
                    if not np.isfinite(actual[hh-1,k]):continue
                    price_rows.append(dict(route=route,origin=origin,horizon=hh,code=c,
                        price_error=float(fp[hh-1,k]-actual[hh-1,k]),
                        price_pct_error=float((fp[hh-1,k]/actual[hh-1,k]-1)*100),
                        yoy_error=float(yp[hh-1,k]-ya[hh-1,k]) if np.isfinite(yp[hh-1,k]-ya[hh-1,k]) else None,
                        weight=float(w[k]/100) if k<68 else None,
                        target_status=str(p['status'][t+hh,k])))
        dv=known_indicator_history(p,history,t,w)
        for route in ('direct_flat','direct_trend','direct_ar'):
            iv=direct_forecast(dv,h,route);mask_companions(iv,history,t,h)
            rows+=metric_rows(iv,truth_for(p,t,h),p['values'][t],route,origin,'test')
        fp=paths[policy]
        sims=simulate(history,fp,w,residuals,pretest_shocks,
                      p['months'][t+1:t+1+h],origin,rng,n=120)
        q=np.nanquantile(sims,[.025,.1,.9,.975],axis=0)
        actual=truth_for(p,t,h)
        for hh in HORIZONS:
            if hh>h:continue
            for k,(g,f) in enumerate(FIELDS):
                a=actual[hh-1,k]
                if not np.isfinite(a) or not np.isfinite(q[:,hh-1,k]).all():continue
                coverage.append(dict(origin=origin,horizon=hh,group=g,field=f,
                    covered80=bool(q[1,hh-1,k]<=a<=q[2,hh-1,k]),
                    covered95=bool(q[0,hh-1,k]<=a<=q[3,hh-1,k]),
                    width80=float(q[2,hh-1,k]-q[1,hh-1,k]),width95=float(q[3,hh-1,k]-q[0,hh-1,k])))
        print(f'Final test {oi+1}/{len(test_origins)} {origin}',flush=True)
    target_lookup={g:df.set_index('month') for g,df in p['groups'].items()}
    for r in rows:
        month=str(pd.Period(r['origin'],freq='M')+r['horizon']);actual=target_lookup[r['group']].loc[month]
        r.update(target_month=month,target_status=actual.data_status,
                 target_uses_estimated_price=bool(actual.uses_estimated_price),target_weight_status=actual.weight_status)
    agg=aggregate(rows);agg.to_csv(folder/'indicator_scores.csv',index=False)
    pd.DataFrame(rows).to_csv(folder/'indicator_errors.csv',index=False)
    pdf=pd.DataFrame(price_rows);pdf.to_csv(folder/'price_errors.csv',index=False)
    pg=pdf.groupby(['route','horizon','code']).agg(n=('price_error','size'),
        price_mae=('price_error',lambda x:np.abs(x).mean()),price_rmse=('price_error',lambda x:np.sqrt((x*x).mean())),
        price_pct_mae=('price_pct_error',lambda x:np.abs(x).mean()),
        price_pct_rmse=('price_pct_error',lambda x:np.sqrt((x*x).mean())),
        yoy_mae=('yoy_error',lambda x:np.abs(x).mean()),yoy_rmse=('yoy_error',lambda x:np.sqrt((x*x).mean()))).reset_index()
    pg.to_csv(folder/'price_scores.csv',index=False)
    weighted=pdf[pdf.weight.notna()].copy()
    weighted['weighted_abs_error']=weighted.weight*weighted.price_pct_error.abs()
    weighted['weighted_sq_error']=weighted.weight*weighted.price_pct_error**2
    weighted['weighted_yoy_error']=weighted.weight*weighted.yoy_error.abs()
    wg=weighted.groupby(['route','origin','horizon']).agg(weighted_price_mae=('weighted_abs_error','sum'),
        weighted_price_mse=('weighted_sq_error','sum'),weighted_yoy_mae=('weighted_yoy_error','sum')).reset_index()
    wg['weighted_price_rmse']=np.sqrt(wg.weighted_price_mse);wg.to_csv(folder/'weighted_scores.csv',index=False)
    cov=pd.DataFrame(coverage).groupby(['horizon','group','field']).agg(n=('covered80','size'),
        coverage80=('covered80','mean'),coverage95=('covered95','mean'),width80=('width80','mean'),width95=('width95','mean')).reset_index()
    cov.to_csv(folder/'coverage.csv',index=False)
    diagnostics(p).to_csv(folder/'diagnostics.csv',index=False)
    pd.DataFrame(failures).to_csv(folder/'fit_failures.csv',index=False)
    np.savez_compressed(folder/'calibration.npz',residuals=residuals)
    summary=dict(model_version=MODEL_VERSION,created_at=utcnow(),asof=p['months'][-1],policy=policy,
        direct_benchmark=direct,chosen=selection,selection_cutoff=selection_cutoff,test_start=test_start,
        development_origins=dev_origins,test_origins=test_origins,skipped_origins=skipped,
        objectives=objectives,parameters=PARAMETERS,calibration_origins=calibration_origins,
        calibration_paths=len(residuals),annual_weight_shifts=shocks,
        source_input_sha256=hashlib.sha256(p['obs'].to_csv(index=False).encode()).hexdigest(),
        method='Expanding-origin pseudo-real-time; revised workbook, conservative one-month RI lag; ex-post estimates gated by input availability',
        interval_method='Centered 14x70 log-price error blocks; whole-block resampling plus global random sign; historical annual RI-shift vector at January; no per-class bound substitution',
        limitations=['No archived BLS release vintages: not strict real-time.',
                    'Development and calibration overlap; final test does not select models or calibrate intervals.',
                    'Origins and 14-month error blocks overlap; effective independent sample is smaller than the path count.',
                    'Only 35 historical t-diffusion months; short development history and sparse long-horizon tests.',
                    'Empirical intervals are diagnostic, not guaranteed nominal coverage.',
                    'Training-only interior interpolation for missing companion indices never fills historical official YoY bases.'],
        final_test_does_not_tune=True)
    write_json(folder/'research.json',summary)
    return summary


def known_indicator_history(p,history,t,current_weight):
    """Every historical indicator used by route A has an origin-known price basis.

    Past RI is lagged one month; the current month uses the same price-updated
    anchor as route B. Historical finalized weights later than the origin are not
    read. Past weights already known at the origin may be revised (pseudo RT).
    """
    n=len(history);w=p['weight'][:n].copy();w[-1]=current_weight
    # Compute as a single path to reuse the exact six-indicator definitions.
    return indicators(history[:24],history[24:],w[24:]) if n>24 else np.empty((0,len(FIELDS)))


def mask_companions(values,history,t,h):
    # A direct indicator prediction must not fabricate an official missing base.
    for j in range(h):
        ix=len(history)+j
        for k,c in ((5,68),(6,69)):
            base=ix-12
            if base<len(history) and not np.isfinite(history[base,c]):values[j,k]=np.nan
            # Acceleration also needs the known YoY from twelve months earlier.
            if ix-24<len(history) and (not np.isfinite(history[ix-24,c]) or
                (base<len(history) and not np.isfinite(history[base,c]))):values[j,k+7]=np.nan


def simulate(history,base,w,residuals,shocks,months,origin,rng,n=300,return_paths=False,new_anchors=None,codes=None):
    result=[];price_paths=[];weight_paths=[];h=len(base)
    for i in range(n):
        block=residuals[rng.integers(len(residuals))]
        block=np.vstack([block, np.repeat(block[-1:],max(0,h-len(block)),axis=0)])[:h]
        future=base*np.exp(block*rng.choice([-1,1]))
        shock=None if len(shocks)==0 else shocks[rng.integers(len(shocks))]
        fw=weights_for_path(w,history[-1],future,shock,months,anchor_month=origin,new_anchors=new_anchors,codes=codes)
        result.append(indicators(history,future,fw))
        if return_paths:price_paths.append(future);weight_paths.append(fw)
    return (np.array(result),np.array(price_paths),np.array(weight_paths)) if return_paths else np.array(result)
