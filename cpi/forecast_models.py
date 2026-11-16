"""Small, declared candidate set; no automatic search on the held-out test set."""
from __future__ import annotations
import warnings
import numpy as np

MODEL_VERSION = '2.0.0'
CANDIDATES = ('flat','trend_3','trend_6','trend_12','seasonal_naive',
              'yoy_persistence','seasonal_mean_trend','ets','arima','sarima','stl')
PARAMETERS = {
 'flat': 'P[t+h]=P[t]',
 'trend_3': 'mean last 3 monthly log changes; constant growth',
 'trend_6': 'mean last 6 monthly log changes; constant growth',
 'trend_12': 'mean last 12 monthly log changes; constant growth',
 'seasonal_naive': 'repeat last 12 monthly log changes recursively; same algebraic path as YoY persistence',
 'yoy_persistence': 'repeat last 12 monthly log changes recursively; constant YoY',
 'seasonal_mean_trend': 'calendar-month growth means, last 48 months; last-12 growth level; seasonal amplitude shrunk 0.5',
 'ets': 'log price: additive damped trend, additive seasonal 12; estimated states, optimized SSE',
 'arima': 'log price ARIMA(1,1,0), drift via demeaned monthly differences; conditional least squares',
 'sarima': 'log price SARIMA(1,1,0)(0,0,1,12), no drift; Gaussian MLE maxiter=40',
 'stl': 'log price STL(period=12, robust=True); last-12 trend regression, damped .9; repeat last seasonal year',
}


def prepare(values):
    """Training-only interpolation for state estimation, never replaces history.

    A missing *interior* official October 2025 training value can use observations
    already available at this origin. Official denominator values remain NA in
    the forecast engine, so October 2026 YoY / October 2027 acceleration stay NA.
    """
    v=np.asarray(values,float)
    good=np.flatnonzero(np.isfinite(v)&(v>0))
    if len(good)<24 or good[-1]!=len(v)-1: raise ValueError('Insufficient observed endpoint')
    return np.interp(np.arange(len(v)),good,np.log(v[good]))


def predict(values, horizon, method):
    logp=prepare(values); d=np.diff(logp); n=len(logp)
    if method=='flat': pred=np.repeat(logp[-1],horizon)
    elif method.startswith('trend_'):
        pred=logp[-1]+np.arange(1,horizon+1)*d[-int(method.split('_')[1]):].mean()
    elif method=='seasonal_naive':
        pred=logp[-1]+np.cumsum([d[-12+j%12] for j in range(horizon)])
    elif method=='yoy_persistence':
        pred=logp[-1]+np.cumsum([d[-12+j%12] for j in range(horizon)])
    elif method=='seasonal_mean_trend':
        recent=d[-48:]; indices=np.arange(n-len(recent),n)
        seasonal=np.array([recent[indices%12==i].mean() for i in range(12)])
        seasonal=.5*(seasonal-seasonal.mean())
        pred=logp[-1]+np.cumsum([d[-12:].mean()+seasonal[(n+j)%12] for j in range(horizon)])
    elif method=='arima':
        mu=d.mean(); z=d-mu
        phi=np.clip(np.dot(z[1:],z[:-1])/max(np.dot(z[:-1],z[:-1]),1e-12),-.98,.98)
        pred=logp[-1]+np.cumsum(mu+z[-1]*phi**np.arange(1,horizon+1))
    elif method=='ets':
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            fit=ExponentialSmoothing(logp,trend='add',damped_trend=True,
                seasonal='add',seasonal_periods=12,initialization_method='estimated').fit(
                optimized=True, use_brute=False, minimize_kwargs={'options':{'maxiter':100}})
            pred=np.asarray(fit.forecast(horizon))
    elif method=='sarima':
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            fit=SARIMAX(logp,order=(1,1,0),seasonal_order=(0,0,1,12),trend='n',
                        enforce_stationarity=True,enforce_invertibility=True).fit(disp=False,maxiter=40)
            if not fit.mle_retvals.get('converged',False):
                raise ValueError('SARIMA MLE did not converge')
            pred=np.asarray(fit.forecast(horizon))
    elif method=='stl':
        from statsmodels.tsa.seasonal import STL
        fit=STL(logp,period=12,robust=True).fit()
        slope=np.polyfit(np.arange(12),fit.trend[-12:],1)[0]
        pred=fit.trend[-1]+slope*np.cumsum(.9**np.arange(1,horizon+1))+np.resize(fit.seasonal[-12:],horizon)
    else: raise ValueError(method)
    if not np.isfinite(pred).all() or (np.abs(pred-logp[-1])>2).any():
        raise ValueError('Unstable candidate forecast')
    return np.exp(pred)


def predict_panel(prices,horizon,methods):
    """Failed statistical fits use explicit seasonal-mean fallback, recorded per fit."""
    out=np.empty((horizon,prices.shape[1])); failures=[]
    for k,method in enumerate(methods):
        try: out[:,k]=predict(prices[:,k],horizon,method)
        except (ValueError,np.linalg.LinAlgError,RuntimeError) as exc:
            out[:,k]=predict(prices[:,k],horizon,'seasonal_mean_trend')
            failures.append({'column':k,'requested_model':method,'fallback':'seasonal_mean_trend','reason':str(exc)})
    return out,failures
