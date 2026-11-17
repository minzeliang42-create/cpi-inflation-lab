# Measures and Acceleration display revision — 2026-11-17

Scope: frontend presentation only. CPI observations, mathematical definitions, historical indicators, official headline/core series, 68-class quantiles, forecast models and raw prediction intervals are unchanged.

Cause: both charts previously opened on all history, with y ranges around −5.886…22.914% and −33.171…24.632 pp. Wide historical tails and enabled prediction bands shared the same axis. Key lines were only 2–2.5px wide and similar muted colors. These conditions compressed the recent curves.

Change: default 3Y view and no predictive shading; Auto Scale uses visible traces within the current date range, with 10% headroom. Prediction bands are optional and excluded from the automatic range unless explicitly requested. If a displayed band extends beyond the axis, an adjacent warning gives its complete numerical extent and a Show full interval button. Manual finite min/max bounds apply immediately, invalid or reversed bounds preserve the preceding valid range; Reset restores automatic point-based scaling. Manual clipping and an off-axis 0 pp reference are explicitly warned about. Acceleration auto scaling always includes zero, without enforcing symmetry.

Colors/ordering: median navy 3.4px, headline gold 3px and core red 3px with distinct monthly marker shapes. Four quantile boundary curves remain visible at 1.15px with subdued blue distribution fills. Key curves draw above all fills. Purple predictive bands remain distinct. Each field's historical/forecast traces share one legend entry; their solid/dashed distinction remains. x, y, customdata, tooltip values and downloads are not transformed.

Local browser checks: default 3Y Measures around −3.00…7.11%; Acceleration around −6.46…7.29 pp. 5Y and All History expand to include actual historical tails; 3Y restores the narrower range. Manual −1…5 works; invalid 9…5 preserves the prior range. Enabling P90 prediction bands keeps point-based ranges and shows the off-axis warning; including the full bands expands the ranges. Auto and Reset both work. At 390px viewport, both chart and container width are 339px, total height 560px, plot area 381px and legend height 67px, with no horizontal document overflow.

Validation: 34 Python tests passed. Node tests cover date bounds, hidden traces, uncertainty opt-in, zero baseline, asymmetric ranges, flat/empty data handling, manual numeric validation and exact preservation of original trace coordinates and tooltip data. Existing diffusion tests remain passing. All six display charts retain their original source data.

Deployment uses the display-only workflow. Explicit [display-only] commit tags skip research jobs on these frontend pushes; scheduled and normal backend update behavior is retained. Display deployment verifies the archived forecast JSON SHA-256 before and after copying assets and does not run model fitting.
