# Nonofficial Measures cards — 2026-11-19

Scope: two Measures cards only. No official data, six-group CSV/JSON, charts, forecasts, models or backtests are changed. Official October 2026 Headline/Core YoY remains null.

The published release contains official-status CPI-U NSA observations imported from CPI_Raw_Data.xlsx, Price_Index sheet, workbook SHA256 cbdc075fa90d99ba7f1cf9508378c875da002a6261c249e0f7408c3598c10df5. Original publication/fetch timestamps were not recorded; we preserve those empty fields rather than invent them. BLS confirms October 2025 survey-data collection was suspended and the aggregate indices were not published: https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi.htm . October 2026 release: https://www.bls.gov/news.release/archives/cpi_11102026.htm . This change uses existing provenance, not a new BLS download (the local API attempt was blocked by its proxy).

Algorithm matches forecast_models.prepare's log-linear interpolation, restricted here to a single interior missing month with immediately adjacent positive official indices. Missing October 2025 base = sqrt(September 2025 * November 2025). Estimated October 2026 YoY = 100 * (official October 2026 index / estimated base - 1). This is ex-post nonofficial interpolation, not a November forecast or a BLS annual rate.

| Series | Sep 2025 | Nov 2025 | Estimated Oct 2025 | Actual Oct 2026 | Estimated YoY % |
| --- | ---: | ---: | ---: | ---: | ---: |
| CUUR0000SA0 | 324.800 | 324.122 | 324.4608229047076 | 337.511 | 4.022111815676799 |
| CUUR0000SA0L1E | 330.804 | 330.425 | 330.61444569165457 | 339.921 | 2.814926700760423 |

Independent sqrt/product formula agrees with production exp/log formula to 11 decimal places. Card values: 4.02%, 2.81%; latest valid official September values remain 3.74%, 2.56%.

Generated dist/card_estimates.json is strictly separate from immutable official releases, with status, full-precision result, estimated denominator, source observations, input hashes, generation time and method. Both display-only deployment and normal update workflows regenerate it from the current published release. Official base/YoY arrival suppresses the estimate; missing/nonpositive/nonofficial inputs suppress it. Frontend requires matching release version and current historical month and a null official YoY. JSON fetched no-store; frontend assets versioned 2.1.3. New official history therefore takes precedence even if an old estimate remains cached.

Tests: 37 Python tests pass, including three estimate regression tests (independent arithmetic, original-input immutability, official precedence, unavailable/estimated/zero inputs). Existing frontend regression suite and new card frontend suite pass (Measures-only display, latest official secondary value, stale release rejection and official precedence). Local browser shows both requested values and explanation; Acceleration cards remain unchanged. Production acceptance is additionally performed after Pages deployment.
