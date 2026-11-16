# t-Diffusion display acceptance — 2026-11-16

Display-only revision; historical calculations, forecast models and raw interval values unchanged. No forecast-model code or research input was edited.

Before: browser-rendered axes were [0,50.1] for t-Declines and [0,17] for t-Growth. After: default trend mode hides interval shading, uses [0,6] and [0,8] with 1-point ticks. Monthly points, historical solid lines, forecast dashed lines and the forecast boundary remain. A visible value beyond the suggested maximum expands the axis with headroom.

Axis scaling scans only visible plotted traces within the displayed time range. The chosen indicator and chosen interval level determine which band traces exist. Hidden legend groups do not affect the range. Historical and forecast lines for each share have one legend group; each prediction band has a separate paired-boundary group.

Browser checks for t-Declines: default 0–6; count-share 80/95 bands 0–15; count-share 80 only 0–9; weight-share bands 0–49; hiding both interval legend groups restores 0–6; interval off restores 0–6. The count interval is not expanded by the undisplayed weight interval. The new 12M history + Forecast button selects 2025-11-01 through 2027-12-28 for the current vintage. Base/high/base switching preserves the trend default.

The preceding values were the local preview check. Final deployed-vintage acceptance uses the unchanged published forecast `7af1cd6a29142a838e88`: t-Declines count-share 80/95 upper limit is 17 (visible maximum 14.705882%), 80-only upper limit 9, weight-share upper limit 49 (visible maximum 43.519424%). Defaults remain 6 and 8. Low scenario expands t-Declines to 9; High scenario expands t-Growth to 10. Base restores 6/8. Actual legend-toggle pointer clicks hide paired interval traces and restore the trend scale.

Deployment: https://github.com/minzeliang42-create/cpi-inflation-lab/actions/runs/43799915276 succeeded using a display-only workflow that checks the forecast JSON hash before/after copying assets and performs no model fitting. The regular research workflow had a temporary GitHub Actions bot write-403 in run 43799420497, but subsequent full run https://github.com/minzeliang42-create/cpi-inflation-lab/actions/runs/43799915191 passed including Save data and update log and deployment. No ongoing write failure was observed in that latest run.

Final live forecast JSON SHA-256: 5d7f8d06ed93935322ebd2491016b7237571dcb1b6d34e072760524004e9b6f7. Generation timestamp remains 2026-11-16T03:14:39+00:00. Live before/after t-Declines and live after t-Growth PNGs are saved under output/readability/.

Frontend automated checks cover 6/8 defaults, future extremes, date bounds, hidden lines and intervals, and ordinary diffusion's unchanged 0–100 axes. Plotly-rendered before/after PNGs were exported from the actual browser into output/readability/ and visually inspected. The export path also verifies stable CSS-safe trace identifiers.

Controls preserve 3Y, 5Y and All History. t chart legends use shared historical/forecast entries and mobile charts have 470px total height, preserving the plotting area. All downloads retain the original interval values even when bands are hidden.

Mobile browser acceptance (390px viewport): actual graph width 339px matches container width 339px; chart height 470px; interval-mode plot height 327px; four-entry legend height 48px. A ResizeObserver and explicit render dimensions prevent stale desktop-width plots from being clipped on mobile. t-Growth defaults 0–8, count intervals 0–17, weight intervals 0–14, then restores 0–8. 3Y, 5Y and All History each recalculate the default range. All 34 Python tests and frontend tests passed.
