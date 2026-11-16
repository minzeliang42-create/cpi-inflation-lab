# V2.0 research and release validation — 2026-11-16

Local validation: 34 Python tests passed, plus frontend range tests and JavaScript syntax checks. Historical vector-engine reconciliation: maximum absolute difference 0, with identical NA locations. The original workbook remains read-only and its hash reconciles.

Forecast coverage: every month 2026-11 through 2027-12, three coherent price-path scenarios, 68 fixed component prices/weights and two separately modeled headline/core companions. Future weights total 100%; quantiles are ordered; count partitions and own-category diffusion weights reconcile. Independent scalar checks verify future inclusive 60-month means and sample standard deviations. October 2027 headline/core acceleration remains NA because of missing October 2025 official bases.

Research selection: development target months end 2024-12; final testing targets begin 2025-01. Expanding-origin horizons 1,2,3,6,12,14. Revised workbook observations imply pseudo-real-time, not strict release-vintage testing. October/November 2025 origins are excluded until approved interpolation inputs become available. Selected bottom-up policy: class_best. Direct persistence is retained as a comparator and has lower errors for some groups; the report does not claim uniform superiority.

Intervals: 22 overlapping joint 14×70 development error blocks, 400 simulated final paths, historical annual-weight shifts and global sign resampling. Independent effective sample size is smaller. Final held-out coverage is exported by field and horizon; 14-month coverage is materially below nominal. 2027 annual weights are explicitly Forecast assumptions; historical cross-year protections remain unchanged.

Artifacts: eight requested Excel worksheets, row-level backtests, per-class model selection and parameters, interval coverage, diagnostics, CSV/JSON, and a numerical near-term research report. Tests reconcile Excel, CSV and JSON values. Failed statistical fits use an explicit recorded fallback. Forecast input/code/selection/calibration digests control immutable vintage publication. Tests cover unchanged inputs, failed publication, correlated path blocks and separate realized errors for multiple vintages.

Local browser: six forecast charts rendered through 2027-12; latest valid official headline/core cards show 2026-09 and explain October NA. Separate price-estimate, estimated-weight and provisional-weight strips are present. Online deployment and mobile acceptance are recorded after the GitHub Actions deployment; this document alone is not evidence of live deployment.

BLS source limitations remain: price/API RI channels work; some official HTML/annual-weight/calendar endpoints return 403. No unofficial substitute is labeled official. Forecasts are conditional model results, not BLS observations.
