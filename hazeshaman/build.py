"""python -m hazeshaman.build [--raw data/raw] [--synthetic] [--test-from 2024-01-01]"""
import argparse
import datetime as dt
import json
from pathlib import Path

import numpy as np

from .features import ANNOUNCE_HOURS, FEATURES
from .loader import load_dir, to_cube
from .model import train_all
from .synth import generate


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--synthetic", action="store_true", help="use generated demo data")
    ap.add_argument("--test-from", default=None, help="hold-out start date (default: last 25%% of days)")
    ap.add_argument("--out", default="docs/model.js")
    a = ap.parse_args(argv)

    if a.synthetic:
        df = generate()
    else:
        df = load_dir(a.raw)
    days, states, cube = to_cube(df)
    test_from = a.test_from or str(days[int(len(days) * 0.75)].date())
    print(f"{len(states)} states, {len(days)} days ({days[0].date()} -> {days[-1].date()}), hold-out from {test_from}")
    models, backtest = train_all(cube, days, states, test_from)

    dm = np.nanmean(cube, axis=2)
    month = days.month.values
    clim = {s: [round(float(np.nanmean(dm[i][month == m] > 100)), 4) if (month == m).any() else 0
                for m in range(1, 13)] for i, s in enumerate(states)}
    latest = {s: [None if np.isnan(v) else int(round(v)) for v in cube[i, -1]] for i, s in enumerate(states)}
    prev = {s: [round(float(x), 1) for x in dm[i, -15:-1]] for i, s in enumerate(states)}
    prev_mean = {s: None if np.isnan(dm[i, -2]) else round(float(dm[i, -2]), 1) for i, s in enumerate(states)}
    meta = dict(synthetic=bool(a.synthetic), built=dt.date.today().isoformat(),
                start=str(days[0].date()), end=str(days[-1].date()), test_from=test_from,
                n_days=len(days), latest_date=str(days[-1].date()))
    payload = dict(meta=meta, states=states, features=FEATURES, hours=ANNOUNCE_HOURS,
                   models={str(k): v for k, v in models.items()},
                   backtest={str(k): v for k, v in backtest.items()},
                   climatology=clim, latest=latest, recent=prev, prev_mean=prev_mean)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("window.HAZE_MODEL=" + json.dumps(payload, separators=(",", ":")) + ";\n")
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
