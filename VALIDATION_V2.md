# V2.0 research and release validation — 2026-11-16

Local validation: 34 Python tests passed, plus frontend range tests and JavaScript syntax checks. Historical vector-engine reconciliation: maximum absolute difference 0, with identical NA locations. The original workbook remains read-only and its hash reconciles.

Forecast coverage: every month 2026-11 through 2027-12, three coherent price-path scenarios, 68 fixed component prices/weights and two separately modeled headline/core companions. Future weights total 100%; quantiles are ordered; count partitions and own-category diffusion weights reconcile. Independent scalar checks verify future inclusive 60-month means and sample standard deviations. October 2027 headline/core acceleration remains NA because of missing October 2025 official bases.

Research selection: development target months end 2024-12; final testing targets begin 2025-01. Expanding-origin horizons 1,2,3,6,12,14. Revised workbook observations imply pseudo-real-time, not strict release-vintage testing. October/November 2025 origins are excluded until approved interpolation inputs become available. Selected bottom-up policy: class_best. Direct persistence is retained as a comparator and has lower errors for some groups; the report does not claim uniform superiority.

Intervals: 22 overlapping joint 14×70 development error blocks, 400 simulated final paths, historical annual-weight shifts and global sign resampling. Independent effective sample size is smaller. Final held-out coverage is exported by field and horizon; 14-month coverage is materially below nominal. 2027 annual weights are explicitly Forecast assumptions; historical cross-year protections remain unchanged.

Artifacts: eight requested Excel worksheets, row-level backtests, per-class model selection and parameters, interval coverage, diagnostics, CSV/JSON, and a numerical near-term research report. Tests reconcile Excel, CSV and JSON values. Failed statistical fits use an explicit recorded fallback. Forecast input/code/selection/calibration digests control immutable vintage publication. Tests cover unchanged inputs, failed publication, correlated path blocks and separate realized errors for multiple vintages.

Local browser: six forecast charts rendered through 2027-12; latest valid official headline/core cards show 2026-09 and explain October NA. Separate price-estimate, estimated-weight and provisional-weight strips are present. Online deployment and mobile acceptance are recorded after the GitHub Actions deployment; this document alone is not evidence of live deployment.

Cloud run [43796842511](https://github.com/minzeliang42-create/cpi-inflation-lab/actions/runs/43796842511) completed research and Pages deployment successfully. Both pre-update and post-forecast test stages passed. Actual site opened at https://minzeliang42-create.github.io/cpi-inflation-lab/ . Browser checks at 1342px and 390px verified six charts through December 2027, no document horizontal overflow, high-scenario switching, 68 future component rows and 100% weights. CSV/Excel/JSON numerical identity was tested locally. Screenshot capture in the browser connector timed out; responsive geometry and rendered DOM were inspected directly.

BLS source limitations remain: price/API RI channels work; some official HTML/annual-weight/calendar endpoints return 403. No unofficial substitute is labeled official. Forecasts are conditional model results, not BLS observations.

Deployed downloads were actually downloaded and read with pandas/openpyxl: 924 forecast indicator values across all scenarios matched the deployed CSV and JSON within 1e-10; Excel size 4,953,594 bytes. The verification program is scripts/verify_live_v2.py.

Second cloud run [43797270739](https://github.com/minzeliang42-create/cpi-inflation-lab/actions/runs/43797270739) passed the research job and confirmed forecast state `unchanged`, version `7af1cd6a29142a838e88`, with original generation timestamp `2026-11-16T03:14:39+00:00` retained. No model refit occurred. Website interaction checks include both low/high scenario switches, all six curves through 2027-12, future 68-class queries and desktop/mobile geometry.

Research limitation of particular importance: t-Growth weight-share 95% empirical coverage was only 60% at 12 months (n=10) and 55.6% at 14 months (n=9). These intervals are not calibrated guarantees; long-horizon t-diffusion should be treated as a scenario. Complete per-indicator coverage remains visible on the site and in coverage.csv.
