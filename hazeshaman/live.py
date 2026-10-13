"""Hourly live updater: python -m hazeshaman.live [--out docs/live.json]

Fetches the DOE hourly API, drops hours not reached yet / bad values, merges into a rolling
120-hour per-station buffer (the API itself only serves the last 24 h) and writes JSON for the
dashboard. Safe to run every hour from cron / GitHub Actions.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import apims

KEEP_H = 120


def update(out="docs/live.json", payload=None, as_of=None, seed=None):
    """seed: optional DataFrame of earlier readings (datetime, area, api) used to pre-fill the buffer."""
    as_of = as_of if as_of is not None else apims.now_myt()
    stats = {}
    df, stations = apims.parse_live(payload if payload is not None else apims.fetch_live(), as_of, stats)
    prev = {}
    if seed is not None:
        for r in seed.itertuples():
            prev[(r.area, r.datetime)] = float(r.api)
    p = Path(out)
    if p.exists():
        old = json.loads(p.read_text())
        end0 = pd.Timestamp(old["end"])
        idx0 = pd.date_range(end=end0, periods=old["hours"], freq="h")
        for a, vals in old["areas"].items():
            for t, v in zip(idx0, vals):
                if v is not None and t <= as_of:
                    prev[(a, t)] = v
    for r in df.itertuples():
        prev[(r.area, r.datetime)] = float(r.api)          # fresh readings override the buffer
    end = max(t for _, t in prev)
    idx = pd.date_range(end=end, periods=KEEP_H, freq="h")
    areas = sorted({a for a, _ in prev})
    arr = {a: [None if (a, t) not in prev else int(round(prev[(a, t)])) for t in idx] for a in areas}
    meta = stations.set_index("area")[["lat", "lon", "label", "station_id"]].round(5).to_dict("index")
    doc = dict(end=end.strftime("%Y-%m-%dT%H:%M"), hours=KEEP_H, as_of=as_of.strftime("%Y-%m-%dT%H:%M"),
               dropped=stats, stations=meta, areas=arr)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, separators=(",", ":")))
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/live.json")
    ap.add_argument("--seed-csv-dir", help="DOE history CSV folder (sharecode/data_apims) to pre-fill the buffer once")
    a = ap.parse_args(argv)
    seed = None
    if a.seed_csv_dir:
        as_of = apims.now_myt()
        since = str((as_of - pd.Timedelta(hours=KEEP_H + 48)).date())
        seed = apims.load_csv_dir(a.seed_csv_dir, as_of, since=since)
        seed = seed[seed.datetime > as_of - pd.Timedelta(hours=KEEP_H)]
    d = update(a.out, seed=seed)
    print(f"live.json: end={d['end']} as_of={d['as_of']} areas={len(d['areas'])} dropped={d['dropped']}")


if __name__ == "__main__":
    main()
