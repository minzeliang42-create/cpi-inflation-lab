# Full history / point visibility correction — 2026-11-17

Investigation of 134c935 and 3ba4682: numeric arrays were intact. Measures had 94 historical months; its five quantiles had 94 valid observations each, headline/core 92 each. Acceleration had 82 historical months; quantiles had 82 valid observations each, headline/core 80 each. The default 3Y range excluded early years. Thin marker-free quantiles and fill chains could make points hard to distinguish. No missing numeric point was repaired by manufacturing data.

Actual missing historical headline/core dates in both groups: 2025-10 and 2026-10. Official October 2025 indices were not published, so both its own YoY and the next October's YoY remain NA; corresponding acceleration also remains NA. Forecast headline/core acceleration in 2027-10 is additionally NA because its lagged official YoY is absent. Median and the other quantile histories have no missing values.

Corrections: default All History with explicit first historical month through last forecast month-end; 3Y/5Y are inclusive 36/60-month windows ending in the displayed final month. Window state survives scenario and interval rerenders, and serialized forecast renders prevent overlapping Plotly.react operations. Seven independent field legend groups retain intended historical/forecast visibility. All seven have monthly markers; primary series are stronger. Blue fills use independent paired traces behind every point curve, avoiding tonexty coupling between unrelated curves. Shade traces do not affect automatic y extents.

Missing historical forecast anchors are omitted from the forecast trace's boundary only; the first real forecast month remains plotted with its marker. connectgaps=false remains. No gap is bridged or filled. A visible missing-data note enumerates missing months and hover metadata also identifies absent official series. Auto/Manual/Reset, interval-outside-axis warnings and zero pp reference remain.

Local actual-browser checks passed: All History, 3Y, 5Y, All History; no visible finite point outside Auto y range; complete original y arrays including NA; first forecast headline/core at 2026-11-01; sequential high/low/base rendering without window reset. 34 Python tests passed. Node regression checks cover time bounds, isolated fill layers, seven marker series and no invented historical-to-forecast connection.

Baseline public artifacts (SHA-256) before the correction:
- measures.csv: 3159f6611149dc950e7ebae67f132a0ab9434905175aac9abba4578119de7964
- acceleration.csv: b29bdb254d660965e4e2defb59f5d6b953e9fc749a38d4b5d29726bce90ced93
- historical research.json: bebc6d431710165c32f3e3c631f35d23f0afdc6f0089cb90771e8e789f02056d
- forecast.json: 5d7f8d06ed93935322ebd2491016b7237571dcb1b6d34e072760524004e9b6f7

Deployment is display-only. No input, CPI formula, historical calculation or forecast-model file is changed.
