"""Train and export docs/model.js.

  python -m hazeshaman.build --archive PARQUET --csv-dir DIR      # DOE history (sharecode repo layout)
  python -m hazeshaman.build --raw data/raw                       # your own hourly CSVs (state or area level)
  python -m hazeshaman.build --synthetic                          # demo data

Add --no-live to skip merging the latest DOE API hours. Schools/students per area come from data.gov.my.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import apims, schools
from .features import ANNOUNCE_HOURS, FEATURES, HOURS, daily_mean
from .loader import load_dir, to_cube
from .model import train_all
from .states import STATES
from .synth import generate


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive")
    ap.add_argument("--csv-dir")
    ap.add_argument("--raw", default=None)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--no-live", action="store_true")
    ap.add_argument("--test-from", default=None, help="hold-out start (default: last 25%% of days)")
    ap.add_argument("--out", default="docs/model.js")
    a = ap.parse_args(argv)

    as_of = apims.now_myt()
    quality, stations, live_end = {}, None, None
    if a.synthetic:
        df = generate()
    elif a.archive or a.csv_dir:
        frames = []
        if a.archive:
            quality["archive"] = {}
            frames.append(apims.load_archive(a.archive, as_of, quality["archive"]))
        if a.csv_dir:
            quality["csv"] = {}
            frames.append(apims.load_csv_dir(a.csv_dir, as_of, quality["csv"]))
        if not a.no_live:
            quality["live"] = {}
            lv, stations = apims.parse_live(apims.fetch_live(), as_of, quality["live"])
            frames.append(lv)
            live_end = str(lv.datetime.max())
        df = apims.merge(frames)
    else:
        df = load_dir(a.raw or "data/raw")
    days, areas, cube = to_cube(df)
    area_states = [x.split("|")[0] for x in areas]
    states = [s for s in STATES if s in set(area_states)]
    area_state = [states.index(s) for s in area_states]
    test_from = a.test_from or str(days[int(len(days) * 0.75)].date())
    print(f"{len(areas)} areas / {len(states)} states, {len(days)} days "
          f"({days[0].date()} -> {days[-1].date()}), hold-out from {test_from}")
    models, backtest = train_all(cube, days, area_state, len(states), test_from)

    dm = daily_mean(cube)
    month = days.month.values
    clim = {}
    for s in states:
        rows = [i for i, st in enumerate(area_states) if st == s]
        v = dm[rows]
        clim[s] = [round(float(np.nanmean(v[:, month == m] > 100)), 4) if np.isfinite(v[:, month == m]).any() else 0
                   for m in range(1, 13)]
    try:
        by_area, smeta = schools.build()
    except Exception as e:  # noqa: BLE001 - dashboard degrades gracefully without schools
        print("WARNING: schools data unavailable:", e)
        by_area, smeta = {}, None
    coords = {} if stations is None else stations.set_index("area")[["lat", "lon"]].round(5).to_dict("index")
    area_meta = []
    for i, k in enumerate(areas):
        st, loc = (k.split("|") + [k])[:2]
        sc = by_area.get(k, {})
        ok = np.isfinite(dm[i])
        area_meta.append(dict(key=k, state=st, name=loc, schools=sc.get("schools", 0), students=sc.get("students", 0),
                              districts=sc.get("districts", []), days=int(ok.sum()),
                              first=str(days[ok][0].date()) if ok.any() else None,
                              last=str(days[ok][-1].date()) if ok.any() else None, **coords.get(k, {})))
    meta = dict(synthetic=bool(a.synthetic), built=dt.date.today().isoformat(), start=str(days[0].date()),
                end=str(days[-1].date()), test_from=test_from, n_days=len(days), live_end=live_end,
                quality=quality, schools=smeta, features=FEATURES)
    payload = dict(meta=meta, states=states, areas=area_meta, hours=HOURS, announce_hours=ANNOUNCE_HOURS,
                   models={str(k): v for k, v in models.items()}, backtest={str(k): v for k, v in backtest.items()},
                   climatology=clim)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("window.HAZE_MODEL=" + json.dumps(payload, separators=(",", ":")) + ";\n")
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
