# 6. Were the closure decisions the best ones?

## The record
`data/closures.csv` lists dates and areas where schools closed or switched to home-based learning (PdPR), from news and education-department announcements, one row per date and area
(`date, state, area, action, pdpr, schools, students, basis, verified, source_title, source_url, note`). `python -m hazeshaman.closures` validates it and writes `docs/closures.json` for the dashboard.
It holds 63 rows; `verified = read` means the source page was opened and checked, `summary` means the row came from a news-search summary and should be opened before it is relied on.
It is **not a complete history** (closure days on record by year: 2015: 1, 2019: 5, 2026: 12) and is extended daily from the 2026 announcements.

## Method (`python -m hazeshaman.decisions`)
Trigger used: KPM rule from 9 Oct 2026 (any reading above **180**, or above **150 on three consecutive days**); **200** before 2026. "Reading" = the highest hourly value in school hours (06:00-14:00) at the matched stations.
"The evening before" uses 17:00-19:00 readings, when next-day decisions are usually announced. Stations are matched to the closed districts by name where possible, otherwise the whole state is used.

## 1. Did closures follow the readings?
45 closure state-days had DOE data (2015 and Sarawak 2019 are outside the archive; 14 Oct 2026 was unfinished). **32 of 45 (71%) met the trigger on the day or the evening before.**

| Verdict | State-days |
|---|---|
| no data | 16 |
| met the evening before only | 13 |
| met on the day only | 10 |
| met (day and evening before) | 9 |
| below trigger (150-180) | 8 |
| far below trigger (<150) | 5 |

## 2. Timing in the Oct 2026 episode
First day with a qualifying reading versus the first recorded closure (school days late):

| State | First qualifying day | First closure | School days late |
|---|---|---|---|
| Johor | 2026-10-06 | 2026-10-08 | 2 |
| Melaka | 2026-10-09 | 2026-10-09 | 0 |
| Negeri Sembilan | 2026-10-07 | 2026-10-09 | 2 |
| Pahang | 2026-10-12 | 2026-10-09 | -1 |
| Perak | 2026-10-09 | no closure on record |  |
| Selangor | 2026-10-07 | 2026-10-09 | 2 |
| WP Kuala Lumpur | 2026-10-07 | 2026-10-09 | 2 |
| WP Putrajaya | 2026-10-07 | 2026-10-09 | 2 |

Part of the early lag is the rule itself: the 180 line only began on **9 Oct** (200 before), and some closures before 8 Oct (for example Batu Pahat, Johor) are in the news but lack a verified date, so they are not in the record.

## 3. Qualifying but open, and closed without a qualifying reading (8-13 Oct, documented days)
Qualifying but no closure on record:

| Date | State | Peak (school hours) | Evening before |
|---|---|---|---|
| 2026-10-08 | Negeri Sembilan | 186.0 | 184.0 |
| 2026-10-12 | Pahang | 162.0 | 158.0 |
| 2026-10-09 | Perak | 183.0 | 160.0 |
| 2026-10-08 | Selangor | 179.0 | 188.0 |
| 2026-10-08 | WP Kuala Lumpur | 175.0 | 186.0 |
| 2026-10-08 | WP Putrajaya | 174.0 | 182.0 |

Closed although the strict trigger was not met (precaution, persistence or partial-district closures matched only at state level):

| Date | State | Peak (school hours) | Evening before |
|---|---|---|---|
| 2026-10-13 | Melaka | 161.0 | 161.0 |
| 2026-10-13 | Negeri Sembilan | 155.0 | 166.0 |
| 2026-10-09 | Pahang | 170.0 | 178.0 |
| 2026-10-12 | Selangor | 151.0 | 80.0 |
| 2026-10-13 | Selangor | 126.0 | 153.0 |
| 2026-10-12 | WP Kuala Lumpur | 129.0 | 132.0 |
| 2026-10-13 | WP Putrajaya | 146.0 | 155.0 |

With the looser reading of the three-day rule (daily peak above 150 instead of daily mean) the counts are 8 qualifying-but-open and 4 closed-without-trigger.

## 4. The dashboard's model replayed
At 18:00 on each evening 6-13 Oct 2026 (96 state-evenings), at the default 8:1 cost ratio (trigger 0.20), against whether the trigger was actually met the next day (state level):

| Decision maker | Trigger days called | Trigger days missed | Calls without a trigger | Recall | Precision |
|---|---|---|---|---|---|
| Recorded closures | 6 | 8 | 11 | 43% | 35% |
| Model | 11 | 3 | 12 | 79% | 48% |

## Verdict
Decisions were **mostly consistent with the rule**, and tended to trail it by one to two school days at the start of an episode before becoming more cautious (closing at 150-180 on persistence).
That is defensible but not the optimum the cost model suggests; the model would have flagged several states earlier. It is **not** proof of a better decision.

## Limits
* One dominant episode, a small and correlated sample, and an incomplete record.
* Closures are per district while DOE data is per station; partial closures are matched by name only.
* The model replay is not like-for-like: authorities also weigh health advice, the three-day rule, logistics and partial closures, and "truth" here is the state's highest station.
* Nothing here measures health outcomes, learning loss or the cost of closing.

## Closure state-days scored since Aug 2026
| Date | State | Area | Peak | Evening before | Verdict | Source checked |
|---|---|---|---|---|---|---|
| 2026-08-20 | Sarawak | Kuching, Padawan, Serian, Bau, Lundu, Samarahan | 195.0 | 166.0 | below trigger (150-180) | read |
| 2026-08-21 | Sarawak | Kuching, Padawan, Serian, Bau, Lundu, Samarahan | 242.0 | 217.0 | met (day and evening before) | read |
| 2026-09-07 | Sarawak | Kuching, Padawan, Bau, Lundu, Samarahan, Simunja | 245.0 | 214.0 | met (day and evening before) | read |
| 2026-09-08 | Sarawak | Kuching, Padawan, Bau, Lundu, Samarahan, Simunja | 305.0 | 270.0 | met (day and evening before) | read |
| 2026-09-09 | Sarawak | Kuching, Padawan, Bau, Lundu, Samarahan, Simunja | 215.0 | 248.0 | met (day and evening before) | read |
| 2026-09-10 | Sarawak | Kuching, Padawan, Bau, Lundu, Samarahan, Simunja | 191.0 | 212.0 | met the evening before only | read |
| 2026-09-11 | Sarawak | Kuching, Padawan, Bau, Lundu, Samarahan, Simunja | 214.0 | 185.0 | met on the day only | read |
| 2026-10-08 | Johor | All schools | 189.0 | 179.0 | met on the day only | read |
| 2026-10-09 | Johor | All schools | 188.0 | 191.0 | met (day and evening before) | read |
| 2026-10-09 | Melaka | As reported (scope per news-search summary; dist | 187.0 | 176.0 | met on the day only | summary |
| 2026-10-09 | Negeri Sembilan | As reported (scope per news-search summary; dist | 189.0 | 189.0 | met (day and evening before) | summary |
| 2026-10-09 | Pahang | Rompin | 170.0 | 178.0 | below trigger (150-180) | summary |
| 2026-10-09 | Selangor | As reported (scope per news-search summary; dist | 183.0 | 178.0 | met on the day only | summary |
| 2026-10-09 | WP Kuala Lumpur | As reported (scope per news-search summary; dist | 172.0 | 172.0 | met the evening before only | summary |
| 2026-10-09 | WP Putrajaya | As reported (scope per news-search summary; dist | 171.0 | 175.0 | met the evening before only | summary |
| 2026-10-12 | Johor | All schools | 173.0 | 177.0 | met the evening before only | read |
| 2026-10-12 | Selangor | Hulu Langat, Gombak, Petaling Perdana | 151.0 | 80.0 | below trigger (150-180) | read |
| 2026-10-12 | WP Kuala Lumpur | Bangsar/Pudu | 129.0 | 132.0 | far below trigger (<150) | read |
| 2026-10-13 | Johor | All schools | 181.0 | 177.0 | met on the day only | read |
| 2026-10-13 | Melaka | All MOE institutions | 161.0 | 161.0 | below trigger (150-180) | read |
| 2026-10-13 | Negeri Sembilan | All schools | 155.0 | 166.0 | below trigger (150-180) | read |
| 2026-10-13 | Pahang | Rompin, Kuantan | 162.0 | 161.0 | met the evening before only | read |
| 2026-10-13 | Selangor | Hulu Langat, Petaling Perdana, Kuala Langat, Sep | 126.0 | 153.0 | far below trigger (<150) | read |
| 2026-10-13 | WP Putrajaya | All schools | 146.0 | 155.0 | far below trigger (<150) | read |
| 2026-10-14 | Johor | All schools | – | – | no data | read |
| 2026-10-14 | Melaka | All schools | – | – | no data | read |
| 2026-10-14 | Negeri Sembilan | All schools | – | – | no data | read |
| 2026-10-14 | Pahang | Kuantan, Pekan, Rompin | – | – | no data | read |
| 2026-10-14 | Sabah | Tawau | – | – | no data | read |
| 2026-10-14 | Sarawak | Serian, Sri Aman, Lubok Antu | – | – | no data | read |
| 2026-10-14 | Selangor | Hulu Langat, Sepang | – | – | no data | read |

---
_Generated by `python -m hazeshaman.report` on 2026-10-14 from the model built 2026-10-13 (data to 2026-10-13). Decision support only: confirm with the official APIMS reading, MetMalaysia and KPM._
