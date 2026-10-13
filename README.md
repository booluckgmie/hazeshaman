# Hazeshaman

Probabilistic next-day school-status forecaster for Malaysian haze (DOE API / IPU), per
station and state, with a cost-optimal **announcement time** and **schools impacted**.

* `docs/index.html` - glassmorphism dashboard (Live + What-if). Serve `docs/` (GitHub Pages) over http(s).
* `docs/model.js` - trained model (coefficients, backtest, schools), rebuilt by `hazeshaman.build`.
* `docs/live.json` - rolling 120 h per-station buffer, refreshed hourly by `.github/workflows/live.yml`.

## Data sources

| Source | Used for |
|---|---|
| `booluckgmie/sharecode/data_apims/archiveAPI201707-20241103.parquet` | 2017-07 -> 2024-11 history (12 peninsular states) |
| `booluckgmie/sharecode/data_apims/20*.csv` | 2023-09 -> now (adds Sabah, Sarawak, Kelantan, Labuan) |
| `https://eqms.doe.gov.my/api3/publicportalapims/apitablehourly` | live hourly readings, 68 stations |
| `api.data.gov.my` `schools_district`, `enrolment_school_district` (OpenDOSM catalogue) | schools / students per district |
| `data/district_station_map.csv` | district -> nearest station (manual, editable, supports weights) |

Known gap: no DOE data between 2024-11-04 and 2025-06-30 in either source. Sabah, Sarawak,
Kelantan and Labuan have data only from 2023-09.

### Bad-value guard
Every source is cut at the current Malaysia hour: readings stamped after it ("hours not reached
yet"), non-numeric flags, off-the-hour stamps (e.g. `05:15AM`) and values outside 1-500 are dropped
(counts are recorded in `model.js` `meta.quality` and `live.json` `dropped`). Old collector files
(single date stamp per file) rank below the archive and the date-corrected files. The dashboard
repeats the future-hour check in the browser. Daily means need >= 18 hourly readings.

## Run

```bash
pip install -r requirements.txt
# 1. train on DOE history (clone booluckgmie/sharecode next to this repo first)
python -m hazeshaman.build --archive ../sharecode/data_apims/archiveAPI201707-20241103.parquet \
    --csv-dir ../sharecode/data_apims --test-from 2025-07-01
# 2. pre-fill the live buffer once (the API only serves 24 h); the workflow keeps it fresh afterwards
python -m hazeshaman.live --seed-csv-dir ../sharecode/data_apims
python -m pytest
```
Other inputs: `--raw data/raw` (your own hourly CSVs, see `data/raw/README.md`), `--synthetic` (demo).
The hourly workflow only runs from the default branch: merge to `main` to activate it, and re-run
`hazeshaman.build` periodically (e.g. monthly) to re-train on new data.

## Method

For each station and every hour H in 12:00-23:00, features available at H only: ln API at 8 AM,
noon, H-3 and H; ln of yesterday's mean; the streak of prior days with mean > 150; season
(sin/cos day-of-year); plus a state effect. Targets (tomorrow): 7 AM API > 100, 7 AM API > 150,
any reading > 180 during 06:00-14:00, daily mean > 150. Logistic regression for each, plus a
log-linear model with Gaussian residual for the 7 AM forecast fan. Coefficients are exported and
evaluated in the browser, so each new hourly report updates every station immediately.

**Closure risk** mirrors KPM's triggers: `P(>180) + (1-P(>180)) * [>=2 prior days >150] * P(mean>150)`.
Scenarios: Best = P(7 AM <= 100)(1-closure), Worst = closure, Base = remainder.

**Schools impacted** = government primary + secondary schools in the districts mapped to a station;
"expected" = closure probability x schools; "at risk" = stations at or above the cost-optimal trigger.

**Best announcement time**: an out-of-time hold-out (default 2025-07-01 onward) gives FN/FP counts per
probability trigger for 3-9 PM. The dashboard minimises
`(c_miss*FN + FP)/(c_miss*positives) + lateness% * (H - 3 PM)` in the browser using your cost sliders.

## Caveats
- Brier skill vs always predicting the base rate is ~66-72% on the hold-out. AUC on all days is
  inflated by easy clear days, so the dashboard also shows AUC on days already > 100. The hold-out
  covers one haze season (~415 closure station-days): treat percentages as indicative.
- District -> station assignment is an approximation; some stations (Pasir Gudang, Pengerang,
  Nilai, ...) have no district of their own, so their schools are counted under a neighbouring station.
- Government schools only (no private/religious); school counts are the latest year published.
- Hour labels use the reading at HH:00; sub-hour timing is not modelled. Inputs beyond ~4 SD of
  training data are clamped and flagged.
- No weather covariates (rainfall, wind, hotspots) yet: the largest expected accuracy gain.
- Decision support only: confirm with the official APIMS reading and MetMalaysia forecast.
