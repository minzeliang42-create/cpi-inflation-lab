"""Forecast-only numerical engine. Historical observations are never imputed here.

The vector engine is independently reconciled to model.calculate in tests. Prices
are levels; shares are percentages, acceleration is percentage points. This module
does not relax the historical December/January weight guard in model.py.
"""
from __future__ import annotations
import numpy as np
from .model import weighted_quantile

FIELDS = [(g, k) for g in ('measures', 'acceleration')
          for k in ('p10','p25','p50','p75','p90','headline','core')]
FIELDS += [(g, k) for g in ('declines','growth','t_declines','t_growth')
           for k in ('items_pct','weight_pct')]
HORIZONS = (1,2,3,6,12,14)


def weights_for_path(anchor_weight, anchor_price, future_price, annual_shock=None,
                     months=None, new_anchors=None, codes=None, anchor_month=None, return_raw=False):
    """Constant expenditure quantities within a forecast scenario, not official RI.

    An explicit new-regime December official anchor overrides the scenario from
    January. No guessed annual weight is written back to the historical ledger.
    """
    raw = np.asarray(anchor_weight) * future_price[:, :68] / anchor_price[:68]
    if annual_shock is not None and months is not None:
        for j, m in enumerate(months):
            if m[:4] > (anchor_month or months[0])[:4]: raw[j] *= np.exp(annual_shock)
    for a in new_anchors or []:
        year = str(a.get('effective_year'))
        ref = a.get('reference_month')
        if a.get('vintage') != 'new' or set(a.get('weights', {})) != set(codes or []):
            continue
        if months is None or (ref not in months and ref!=anchor_month): continue
        reference_price=anchor_price[:68] if ref==anchor_month else future_price[months.index(ref),:68]
        aw = np.array([a['weights'][c] for c in codes], float)
        for j, m in enumerate(months):
            if m[:4] == year:
                raw[j] = aw * future_price[j,:68] / reference_price
    if not np.isfinite(raw).all() or (raw < 0).any() or (raw.sum(axis=1) <= 0).any():
        raise ValueError('Invalid forecast weight path')
    norm=raw / raw.sum(axis=1, keepdims=True) * 100
    return (norm,raw) if return_raw else norm


def indicators(history, future, weights, return_details=False):
    """Evaluate each joint future price/weight path with inclusive 60-month windows."""
    p = np.vstack([history, future])
    y = np.full_like(p, np.nan)
    y[12:] = (p[12:] / p[:-12] - 1) * 100
    a = np.full_like(y, np.nan)
    a[12:] = y[12:] - y[:-12]
    out = np.full((len(future), len(FIELDS)), np.nan)
    detail = []
    for j, ix in enumerate(range(len(history), len(p))):
        yy, aa, w = y[ix,:68], a[ix,:68], weights[j]
        window = y[max(0,ix-59):ix+1,:68]
        if len(window) == 60 and np.isfinite(window).all():
            mean, std = window.mean(axis=0), window.std(axis=0, ddof=1)
            z = np.divide(yy-mean, std, out=np.full(68,np.nan), where=std>0)
        else:
            mean = std = z = np.full(68,np.nan)
        out[j,:5] = weighted_quantile(yy, w)
        out[j,5:7] = y[ix,68:70]
        out[j,7:12] = weighted_quantile(aa, w)
        out[j,12:14] = a[ix,68:70]
        for k, (v, threshold, lower) in enumerate(((yy,0,True),(yy,0,False),(z,-2,True),(z,2,False))):
            if np.isfinite(v).all():
                flag = v < threshold if lower else v > threshold
                out[j,14+k*2:16+k*2] = [flag.sum()/68*100, w[flag].sum()]
        if return_details:
            detail.append(dict(yoy=yy,acceleration=aa,mean_60=mean,std_60=std,
                               z_score=z,window_count=np.isfinite(window).sum(axis=0)))
    return (out, detail) if return_details else out


def direct_forecast(values, horizon, method):
    """Route A: simple per-indicator benchmarks with structural projections.

    These are comparisons, not substitutes for official historical headline/core.
    Missing official bases are masked by the caller after forecasting.
    """
    ans = np.full((horizon,values.shape[1]),np.nan)
    for k in range(values.shape[1]):
        v = values[:,k]
        good = np.flatnonzero(np.isfinite(v))
        if len(good) < 3: continue
        last = good[-1]
        if method == 'direct_flat': ans[:,k] = v[last]
        elif method == 'direct_trend':
            t = good[-12:]; slope = np.polyfit(t, v[t], 1)[0]
            # Damped trend estimated exclusively at the origin.
            ans[:,k] = v[last] + slope * np.cumsum(.9**np.arange(1,horizon+1))
        elif method == 'direct_ar':
            pairs = np.flatnonzero(np.isfinite(v[1:]) & np.isfinite(v[:-1]))
            if len(pairs) < 12: ans[:,k] = v[last]; continue
            x = np.column_stack([np.ones(len(pairs)),v[pairs]])
            coef = np.linalg.lstsq(x,v[pairs+1],rcond=None)[0]
            coef[1] = np.clip(coef[1],-.98,.98)
            xlast = v[last]
            for j in range(horizon):
                xlast = coef[0]+coef[1]*xlast; ans[j,k] = xlast
    for start in (0,7):
        ans[:,start:start+5] = np.sort(ans[:,start:start+5],axis=1)
    ans[:,14:] = np.clip(ans[:,14:],0,100)
    # Ordinary growth and decline shares leave nonnegative room for exact zeros.
    for offset in (0,1):
        pair=ans[:,[14+offset,16+offset]]
        total=pair.sum(axis=1)
        ans[:,[14+offset,16+offset]]=pair/np.maximum(1,total[:,None]/100)
        pair=ans[:,[18+offset,20+offset]]
        total=pair.sum(axis=1)
        ans[:,[18+offset,20+offset]]=pair/np.maximum(1,total[:,None]/100)
    for k in (14,16,18,20): ans[:,k]=np.round(ans[:,k]*68/100)/68*100
    return ans
