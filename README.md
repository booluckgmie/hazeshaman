# Hazeshaman

Probabilistic next-day school-status forecaster for Malaysian haze (API / IPU), with a
cost-optimal **announcement time**, for all states.

> **Status:** `docs/model.js` currently ships a model trained on **synthetic demo data**
> (the dashboard shows a warning badge). Drop your multi-year hourly IPU CSVs into
> `data/raw/` and rebuild to get real numbers.

## Quick start

```bash
pip install -r requirements.txt
python -m hazeshaman.build                 # trains on data/raw/*.csv -> docs/model.js
python -m hazeshaman.build --synthetic     # demo data instead
python -m pytest
open docs/index.html                       # or serve docs/ with GitHub Pages
```

Data format: see `data/raw/README.md`.

## Method

For each announcement hour H in 3 PM-9 PM and every state, features come from information
available at H only: ln API at 8 AM, noon, H-3 and H, yesterday's mean, the streak of prior
days with mean > 150, season (sin/cos day-of-year) and a state effect.

Targets (tomorrow): 7 AM API > 100, 7 AM API > 150, any reading > 180 during 06:00-14:00,
mean > 150. Logistic regression for each, plus a log-linear model with Gaussian residual for the
7 AM forecast fan.

**Closure risk** mirrors KPM's triggers: `P(>180) + (1 - P(>180)) * [>=2 prior days >150] * P(mean>150)`.
Scenarios: Best = P(7 AM <= 100)(1-closure), Worst = closure, Base = remainder.

**Best announcement time**: hold-out backtest (last 25% of days by default) gives FN/FP counts per
probability trigger per hour. The dashboard minimises
`(c_miss*FN + FP)/(c_miss*positives) + lateness% * (H - 3 PM)` in the browser, so the
recommendation reacts to your cost sliders. Model coefficients are exported as JSON and
evaluated client-side, so sliders update probabilities instantly with no backend.

## Caveats

- Hour labels use the reading at HH:00 (e.g. "7 PM ~ 7:30"); sub-hour timing is not modelled.
- Inputs beyond ~4 SD of training data are clamped and flagged as out of range.
- Official decisions need the live APIMS reading and MetMalaysia forecast. This is decision support.
- Weather covariates (rainfall, wind, hotspot counts) are not used yet; adding them is the largest
  expected accuracy gain on real data.
