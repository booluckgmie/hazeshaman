# 4. Second source: Open-Meteo cross-check

One feed is a single point of failure, above all for **Sabah and Sarawak**, which have DOE history only since 2023-09. Hazeshaman therefore compares every DOE station with the
**Open-Meteo Air Quality API** (Copernicus CAMS global model, ~25 km grid, hourly from 2022-07-29; CC BY 4.0, free for non-commercial use) and flags reports the independent source does not support.

## Method
* **Comparator:** the 24-hour rolling mean of Open-Meteo `us_aqi`, mapped onto each station's own DOE scale by **quantile mapping** (this keeps the extremes, which a regression would shrink).
* **Expected range:** from history, the distribution of log(DOE / Open-Meteo) per station (95% shown in the chart, 99% used for flags).
* **Flags** are raised only when they matter for a closure decision:
  `high` (DOE at or above 100 but far above the range), `low` (possible under-reporting: Open-Meteo at or above 100 while DOE is far below), `frozen` (the same value for 24 h, or 12 h while Open-Meteo moves 25 points), `spike`, `stale`.
  Severity is *critical* when a closure-level reading is unconfirmed.
* **Grades:** **A** agrees closely, **B** usable, **C** verify before acting (large typical gap, poor band agreement, or high readings rarely corroborated).
* **Second opinion:** the already-trained DOE model is fed with features derived from Open-Meteo and scored against DOE truth (a transfer test; a model trained on Open-Meteo alone had too few closure cases in the overlap period).

"Unconfirmed" is **not** "wrong": a 25 km model cannot see a single chimney or burning site, so local sources look unconfirmed. Use the flags to decide what to verify, not what to discard.

## Is Sabah and Sarawak's DOE data credible?
Median correlation with Open-Meteo: **Sarawak 0.87**, **Sabah 0.78**, peninsula 0.76 (all stations 0.78). The East Malaysia feed is generally corroborated.
The exceptions are the grade C stations: IPD Serian, JOHAN SETIA, Kimanis, Kota Bharu, Miri, Pengerang, Politeknik Kota Kinabalu, Tanah Merah.

| State | Stations | Median correlation | Median gap (points) | Within one band | Grades A / B / C |
|---|---|---|---|---|---|
| Johor | 8 | 0.85 | 11.2 | 100.0% | 4 / 3 / 1 |
| Kedah | 4 | 0.71 | 10.2 | 100.0% | 1 / 3 / 0 |
| Kelantan | 2 | 0.52 | 12.7 | 100.0% | 0 / 0 / 2 |
| Melaka | 3 | 0.78 | 11.0 | 100.0% | 2 / 1 / 0 |
| Negeri Sembilan | 3 | 0.81 | 9.7 | 100.0% | 2 / 1 / 0 |
| Pahang | 5 | 0.71 | 12.1 | 100.0% | 0 / 5 / 0 |
| Perak | 5 | 0.77 | 9.2 | 100.0% | 5 / 0 / 0 |
| Perlis | 1 | 0.70 | 9.1 | 100.0% | 0 / 1 / 0 |
| Pulau Pinang | 4 | 0.77 | 9.7 | 100.0% | 3 / 1 / 0 |
| Sabah | 6 | 0.78 | 10.4 | 100.0% | 2 / 2 / 2 |
| Sarawak | 13 | 0.87 | 15.3 | 99.9% | 3 / 8 / 2 |
| Selangor | 6 | 0.75 | 10.3 | 100.0% | 3 / 2 / 1 |
| Terengganu | 4 | 0.68 | 10.3 | 100.0% | 1 / 3 / 0 |
| WP Kuala Lumpur | 2 | 0.73 | 11.2 | 100.0% | 1 / 1 / 0 |
| WP Labuan | 1 | 0.78 | 10.8 | 100.0% | 1 / 0 / 0 |
| WP Putrajaya | 1 | 0.62 | 16.6 | 100.0% | 0 / 1 / 0 |

## Flagged reports (last 120 h to 2026-10-24 20:00)
| Station | State | Type | Severity | From | To | Hours | Detail |
|---|---|---|---|---|---|---|---|
| JOHAN SETIA | Selangor | Possible under-reporting | critical | 2026-10-24 06:00 | 2026-10-24 20:00 | 15 | DOE 96 vs ≈161 |
| Petaling Jaya | Selangor | Unconfirmed high reading | critical | 2026-10-23 01:00 | 2026-10-23 16:00 | 16 | DOE 156 vs ≈71 |
| Seremban | Negeri Sembilan | Unconfirmed high reading | critical | 2026-10-22 19:00 | 2026-10-23 09:00 | 15 | DOE 159 vs ≈70 |
| Tangkak | Johor | Unconfirmed high reading | critical | 2026-10-22 13:00 | 2026-10-22 19:00 | 7 | DOE 151 vs ≈82 |
| Port Dickson | Negeri Sembilan | Repeated / stuck value | warn | 2026-10-21 20:00 | 2026-10-22 07:00 | 12 | DOE 152 vs ≈134 |
| Banting | Selangor | Repeated / stuck value | warn | 2026-10-20 12:00 | 2026-10-21 00:00 | 13 | DOE 162 vs ≈102 |

Summary: 6 stations flagged, 4 critical; by type {'high': 3, 'low': 1, 'frozen': 2, 'spike': 0, 'stale': 0}.

## Second opinion: how good is Open-Meteo alone?
Skill versus the base rate for the closure target, same hold-out:

| Decision hour | DOE feed skill | Open-Meteo-only skill | DOE AUC (days > 100) | Open-Meteo AUC (days > 100) |
|---|---|---|---|---|
| 3 PM | 64% | 50% | 0.92 | 0.87 |
| 4 PM | 66% | 51% | 0.93 | 0.87 |
| 5 PM | 65% | 51% | 0.93 | 0.87 |
| 6 PM | 64% | 51% | 0.94 | 0.86 |
| 7 PM | 68% | 52% | 0.94 | 0.86 |
| 8 PM | 68% | 53% | 0.94 | 0.87 |
| 9 PM | 70% | 53% | 0.95 | 0.86 |

Open-Meteo alone is clearly weaker, which is why it is a **sanity check, not a replacement**: when the two closure chances sit on the same side of the trigger the dashboard shows green, when they disagree it shows amber ("verify").

## Files and refresh
`hazeshaman/openmeteo.py`, `hazeshaman/crosscheck.py`, `data/xcheck_model.json`, `docs/xcheck.json` (refreshed hourly by the workflow), `api/xcheck.js`.
Refit: `python -m hazeshaman.openmeteo --cache data/openmeteo` then `python -m hazeshaman.crosscheck fit`; update: `python -m hazeshaman.crosscheck update`.
Attribution: contains modified Copernicus Atmosphere Monitoring Service information, via Open-Meteo.com (CC BY 4.0).

---
_Generated by `python -m hazeshaman.report` on 2026-10-24 from the model built 2026-10-24 (data to 2026-10-24). Decision support only: confirm with the official APIMS reading, MetMalaysia and KPM._
