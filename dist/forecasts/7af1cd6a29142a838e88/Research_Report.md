# CPI Inflation Lab V2.0 — Forecast research and validation

Research frozen as of 2026-10. Model version 2.0.0.



## Data and timing

68 fixed CPI-U NSA expenditure classes; January 2018–October 2026 initial study (106 monthly prices). Official RI through September 2026; October RI is historical provisional. Approved estimates are retained. Each t statistic uses 60 calendar YoY months including the target, sample standard deviation and strict ±2 cutoffs.

Pseudo-real-time expanding-origin backtests use the revised workbook, not archived release vintages. Origin means after that month’s price release; RI is restricted to months before the origin. October 2025 interpolated prices are unavailable until November, and motor-insurance October/November until December. Origins October/November 2025 are omitted because a complete 68-price origin information set does not exist.



## Selection and untouched test

Development origins: 2021-12, 2022-03, 2022-06, 2022-09, 2022-12, 2023-03, 2023-06, 2023-09, 2023-12, 2024-03, 2024-06, 2024-09; only target months through 2024-12 select models. Final test origins December 2024–September 2026, with target months January 2025–October 2026. Horizons 1, 2, 3, 6, 12 and 14 are evaluated wherever realized targets exist. Training expands from January 2018.

Candidate parameters are declared in forecast_models.py. Failed/non-converged fits fall back explicitly to seasonal_mean_trend and are logged. Per-class choices minimize the average of absolute log-price percentage error and absolute YoY error over development horizon cells. Coherent B policies are then ranked by an equal-six-group, flat-baseline-normalized MAE objective (0.1 pp denominator floor). No final-test error or interval coverage tunes a choice.

Selected B policy: **class_best**. Selected A comparator: **direct_flat**.

Route A directly extrapolates the indicators (persistence, damped trend and AR(1)); quantiles/shares are structurally projected. Route B forecasts 68 price indices and two companion official-index series, then recomputes all indicators. The coherent B path is published to supply auditable component prices, weights, rolling windows and scenarios. A may outperform B on individual indicators; the table below records the actual tradeoff.



|Group|B test MAE|A test MAE|Flat B MAE|

|---|---:|---:|---:|

|measures|0.5410|0.4825|1.5902|

|acceleration|0.6036|0.7124|1.5054|

|declines|4.5669|4.6264|10.0308|

|growth|6.8544|4.6264|24.0529|

|t_declines|1.1749|1.0865|10.2237|

|t_growth|1.6264|1.4651|1.7818|



Group averages combine fields/horizons equally; they are not pooled price-level errors. CSV exports contain n, horizon, field, MAE, RMSE, bias and direction accuracy. Per-class raw-index errors, percentage errors, YoY errors and origin-weighted errors are separate to avoid mixing index scales.



## Uncertainty and scenarios

22 centered, overlapping 14×70 development error blocks (origins 2022-01–2023-10) are resampled jointly, with a global random sign. All classes and all horizons within a block move together. Annual weight-shift vectors are sampled jointly at January. 400 simulated final paths pass through all six nonlinear calculations. The 80/95 labels denote empirical central quantiles, not guaranteed coverage. Overlapping origins reduce effective sample size. Held-out coverage below was measured with 120 draws per origin, using only pre-2025 weight-shift calibration.



|Horizon|Cells|Observed 80% coverage|Observed 95% coverage|

|---|---:|---:|---:|

|1|432|85.0%|95.6%|

|2|410|86.3%|96.3%|

|3|388|88.1%|95.6%|

|6|322|94.4%|99.1%|

|12|220|83.2%|95.9%|

|14|194|74.2%|85.6%|



Base is the selected point path. Low/high are two complete joint price-error paths ranked by the weighted near-term inflation change; they are sensitivity scenarios, not separate probabilities and not pointwise lower/upper indicator bounds. The separate weight-only sensitivity table applies each historical January RI regime-shift vector to the same base prices.



## Annual RI and official companions

2027 base weights assume constant expenditure quantities, updated by forecast prices and renormalized to 100%. They are Forecast, not official or provisional RI. Historical new-year extrapolation remains forbidden. A separately validated new-regime December bridge, when present, replaces the forecast regime from January; a subsequently official monthly RI anchors the next forecast vintage. Annual assumptions never overwrite historical inputs.

Headline/core price models are separate from the 68 classes. A training-only interior missing value may be interpolated using origin-known observations to fit a statistical model, but the engine retains the official historical NA denominator. October 2026 official headline/core YoY and October 2027 corresponding forecast acceleration remain NA when the official October 2025 index is absent.



## Diagnostics and limits

Median class monthly log-change sample SD: 0.939%; maximum: 5.758%. Diagnostics CSV records calendar seasonality, pandemic/recent volatility, weights and approved estimates.

- No archived BLS release vintages: not strict real-time.

- Development and calibration overlap; final test does not select models or calibrate intervals.

- Origins and 14-month error blocks overlap; effective independent sample is smaller than the path count.

- Only 35 historical t-diffusion months; short development history and sparse long-horizon tests.

- Empirical intervals are diagnostic, not guaranteed nominal coverage.

- Training-only interior interpolation for missing companion indices never fills historical official YoY bases.

- t-diffusion is discontinuous at z=±2. Small path changes may flip categories; near-threshold classes and estimated/forecast window counts accompany forecasts.

- Future shocks, structural changes and annual expenditure reweighting are not predictable from this short univariate sample. Long-horizon diffusion has lower confidence.

- Historical estimated target observations are retained in scoring and labeled in price_errors.csv; realized indicator scores use the approved reconstructed history.



## Reproducibility and cloud operation

python -m cpi.forecast creates/reuses the frozen study, publishes an immutable input/code digest vintage, and switches the pointer only after validation. No input change means no model fitting. New observations or annual anchors produce a new vintage; old paths remain available and are evaluated against realized indicators. Forecast failure retains the prior pointer. BLS channel failures and forecast status remain separate. Research is deliberately not retuned on every release; change MODEL_VERSION and explicitly rerun research to revise the validated specification.



## Method references

- [Forecasting: Principles and Practice — time-series cross-validation](https://otexts.com/fpp3/tscv.html)

- [statsmodels exponential smoothing](https://www.statsmodels.org/stable/examples/notebooks/generated/exponential_smoothing.html)

- [statsmodels state-space forecasting](https://www.statsmodels.org/stable/examples/notebooks/generated/statespace_forecasting.html)

- [statsmodels STL decomposition](https://www.statsmodels.org/stable/examples/notebooks/generated/stl_decomposition.html)

- [BLS CPI relative importance](https://www.bls.gov/cpi/tables/relative-importance/)

## Near-term forecast results — model output, not official data

Forecast as of 2026-10; generated 2026-11-16T03:14:39+00:00. Units: % for inflation/shares; pp for acceleration.

|Month|Group|Series|Base|Change from as-of history|80% empirical interval|Test MAE (nearest horizon)|
|---|---|---|---:|---:|---|---:|
|2026-11|measures|p10|-0.622|0.408|-2.173–0.249|0.469|
|2026-11|measures|p25|3.021|0.356|2.102–3.061|0.272|
|2026-11|measures|p50|3.464|0.059|3.463–3.652|0.121|
|2026-11|measures|p75|3.912|0.111|3.698–4.258|0.117|
|2026-11|measures|p90|5.686|-0.010|5.415–6.798|0.381|
|2026-11|measures|headline|4.368|NA|3.818–4.921|0.217|
|2026-11|measures|core|2.997|NA|2.794–3.194|0.090|
|2026-11|acceleration|p10|-3.559|-0.529|-4.266–-1.866|0.355|
|2026-11|acceleration|p25|-0.329|-0.034|-0.770–-0.001|0.148|
|2026-11|acceleration|p50|0.222|0.301|0.085–0.289|0.121|
|2026-11|acceleration|p75|0.925|-0.033|0.846–1.423|0.191|
|2026-11|acceleration|p90|4.516|-0.559|3.934–5.576|0.616|
|2026-11|acceleration|headline|1.633|NA|1.083–2.186|0.217|
|2026-11|acceleration|core|0.364|NA|0.160–0.560|0.090|
|2026-11|declines|items_pct|17.647|-1.471|14.706–20.588|2.500|
|2026-11|declines|weight_pct|15.272|-0.356|8.270–16.608|2.496|
|2026-11|growth|items_pct|82.353|1.471|79.412–85.294|2.500|
|2026-11|growth|weight_pct|84.728|0.356|83.392–91.730|2.496|
|2026-11|t_declines|items_pct|1.471|0.000|1.471–2.941|0.588|
|2026-11|t_declines|weight_pct|1.260|-0.004|1.254–1.717|0.460|
|2026-11|t_growth|items_pct|4.412|0.000|2.941–7.353|1.103|
|2026-11|t_growth|weight_pct|0.593|-0.000|0.519–6.314|0.525|
|2026-12|measures|p10|0.279|1.309|-2.339–0.693|0.647|
|2026-12|measures|p25|2.286|-0.379|1.281–2.849|0.500|
|2026-12|measures|p50|3.570|0.166|3.297–3.732|0.198|
|2026-12|measures|p75|3.731|-0.070|3.528–4.344|0.169|
|2026-12|measures|p90|5.355|-0.341|5.403–7.200|0.432|
|2026-12|measures|headline|4.661|NA|3.524–5.809|0.484|
|2026-12|measures|core|3.114|NA|2.702–3.465|0.174|
|2026-12|acceleration|p10|-4.839|-1.809|-5.746–-2.186|0.480|
|2026-12|acceleration|p25|-0.341|-0.045|-1.245–-0.080|0.134|
|2026-12|acceleration|p50|0.093|0.172|-0.084–0.434|0.211|
|2026-12|acceleration|p75|0.828|-0.130|0.357–1.814|0.286|
|2026-12|acceleration|p90|4.109|-0.966|3.169–6.794|1.011|
|2026-12|acceleration|headline|1.984|NA|0.847–3.132|0.484|
|2026-12|acceleration|core|0.475|NA|0.063–0.825|0.174|
|2026-12|declines|items_pct|13.235|-5.882|11.765–26.471|3.793|
|2026-12|declines|weight_pct|7.744|-7.884|7.550–18.896|3.332|
|2026-12|growth|items_pct|86.765|5.882|73.529–88.235|3.793|
|2026-12|growth|weight_pct|92.256|7.884|81.104–92.450|3.332|
|2026-12|t_declines|items_pct|1.471|0.000|1.471–2.941|1.006|
|2026-12|t_declines|weight_pct|1.255|-0.009|1.248–1.686|0.954|
|2026-12|t_growth|items_pct|5.882|1.471|4.412–10.294|1.393|
|2026-12|t_growth|weight_pct|2.082|1.489|1.978–9.689|0.818|

Missing October 2026 official YoY makes the corresponding October comparison NA; the latest valid official value is shown separately on the website.

### 2026-11 drivers and threshold sensitivity

- Motor fuel (SETB): weighted YoY-change proxy 0.0941 pp; forecast YoY 38.524%; model flat.
- Public transportation (SETG): weighted YoY-change proxy 0.0486 pp; forecast YoY 23.326%; model ets.
- Owners' equivalent rent of residences (SEHC): weighted YoY-change proxy 0.0412 pp; forecast YoY 3.590%; model trend_3.
- Other recreation services (SERF): weighted YoY-change proxy 0.0150 pp; forecast YoY 3.833%; model trend_12.
- Food away from home (SEFV): weighted YoY-change proxy 0.0132 pp; forecast YoY 4.006%; model arima.

Classes within 0.25 pp of zero YoY: 0; within 0.25 Z of −2: 0; of +2: 2. One class crossing a cutoff changes count share by 100/68 = 1.470588 pp and weight share by its own weight. These are discontinuous forecasts, not smooth linear aggregates.

### 2026-12 drivers and threshold sensitivity

- Motor fuel (SETB): weighted YoY-change proxy 0.4187 pp; forecast YoY 46.224%; model flat.
- New and used motor vehicles (SETA): weighted YoY-change proxy 0.0675 pp; forecast YoY 0.299%; model flat.
- Owners' equivalent rent of residences (SEHC): weighted YoY-change proxy 0.0387 pp; forecast YoY 3.580%; model trend_3.
- Telephone services (SEED): weighted YoY-change proxy 0.0362 pp; forecast YoY 5.017%; model flat.
- Energy services (SEHF): weighted YoY-change proxy -0.0361 pp; forecast YoY 2.843%; model flat.

Classes within 0.25 pp of zero YoY: 2; within 0.25 Z of −2: 0; of +2: 3. One class crossing a cutoff changes count share by 100/68 = 1.470588 pp and weight share by its own weight. These are discontinuous forecasts, not smooth linear aggregates.

## Annual weight sensitivity

|Historical January shift|L1 absolute class-share change (pp)|Maximum class change (pp)|
|---|---:|---:|
|2019|0.0220|0.0009|
|2020|0.0232|0.0009|
|2021|0.0207|0.0010|
|2022|0.0246|0.0009|
|2023|0.0248|0.0009|
|2024|0.0263|0.0022|
|2025|0.0240|0.0010|
|2026|0.0222|0.0009|

Forecast_Scenarios contains the full impact of applying each joint historical annual shift to base prices. The base scenario uses no guessed annual shift.
