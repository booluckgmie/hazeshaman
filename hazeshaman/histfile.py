"""Daily history file for the dashboard (docs/history.json): every area's daily mean and school-hours peak, as integers.

    python -m hazeshaman.histfile update       # fold the newest days of data/history/*.csv.gz into docs/history.json (run daily by the workflow)

Only numpy and pandas are needed, so the hourly GitHub job can run it without the model dependencies.
"""
from __future__ import annotations
import json, sys
import numpy as np, pandas as pd
from . import apims

SCHOOL = (6, 14)
MIN_HOURS = 18


def daily(df: pd.DataFrame, areas: list[str], days: pd.DatetimeIndex | None = None):
    """(days, mean[area, day], peak[area, day]); a mean needs >= 18 hourly readings, a peak needs >= 5 readings in school hours."""
    df = df[df.area.isin(areas)].copy(); df["date"] = df.datetime.dt.normalize(); df["h"] = df.datetime.dt.hour
    if days is None: days = pd.date_range(df.date.min(), df.date.max(), freq="D")
    g = df.groupby(["area", "date"]).api.agg(["mean", "count"]).reset_index()
    g.loc[g["count"] < MIN_HOURS, "mean"] = np.nan
    pk = df[df.h.between(*SCHOOL)].groupby(["area", "date"]).api.agg(["max", "count"]).reset_index()
    pk.loc[pk["count"] < 5, "max"] = np.nan
    M = g.pivot(index="area", columns="date", values="mean").reindex(index=areas, columns=days).to_numpy()
    P = pk.pivot(index="area", columns="date", values="max").reindex(index=areas, columns=days).to_numpy()
    return days, M, P


def _enc(row): return ",".join("" if not np.isfinite(v) else str(int(round(v))) for v in row)
def _dec(s): return np.array([np.nan if v == "" else float(v) for v in s.split(",")])


def write(days, M, P, areas, out="docs/history.json"):
    doc = dict(start=str(days[0].date()), end=str(days[-1].date()), n=len(days), areas={a: dict(m=_enc(M[i]), p=_enc(P[i])) for i, a in enumerate(areas)})
    with open(out, "w", encoding="utf-8") as f: json.dump(doc, f, separators=(",", ":"))
    return doc


def update(path="docs/history.json", hist_dir="data/history", days_back=21, as_of=None):
    """Re-compute the last `days_back` days (and any new ones) from the hourly archive and splice them into the file. Returns days written."""
    doc = json.load(open(path, encoding="utf-8")); areas = list(doc["areas"]); start = pd.Timestamp(doc["start"])
    old_m = {a: _dec(doc["areas"][a]["m"]) for a in areas}; old_p = {a: _dec(doc["areas"][a]["p"]) for a in areas}
    as_of = as_of or apims.now_myt()
    df = apims.load_history_dir(hist_dir, as_of, {})
    if df.empty: return 0
    last_full = (df.datetime.max() - pd.Timedelta(hours=14)).normalize()          # a day is final once its 14:00 reading is in; the mean needs 18 h anyway
    d0 = max(start, pd.Timestamp(doc["end"]) - pd.Timedelta(days=days_back)); d1 = df.datetime.dt.normalize().max()
    days, M, P = daily(df[df.datetime >= d0], areas, pd.date_range(d0, d1, freq="D"))
    n_new = (d1 - start).days + 1; n_new = max(n_new, doc["n"])
    allm = np.full((len(areas), n_new), np.nan); allp = allm.copy()
    for i, a in enumerate(areas): allm[i, :doc["n"]] = old_m[a]; allp[i, :doc["n"]] = old_p[a]
    off = (d0 - start).days
    for i in range(len(areas)):
        for j in range(len(days)):
            if np.isfinite(M[i, j]) or days[j] <= last_full: allm[i, off + j] = M[i, j]; allp[i, off + j] = P[i, j]
    full = pd.date_range(start, periods=n_new, freq="D")
    write(full, allm, allp, areas, path)
    return len(days)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "update":
        print("history.json: re-computed", update(), "days")
    else:
        print(__doc__)
