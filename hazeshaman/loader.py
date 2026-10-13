"""Load hourly API/IPU data for all states from CSVs.

Accepted layouts (any number of files, any mix), columns matched case-insensitively:
  long : datetime|date+time|date+hour, state, api|ipu|value
  wide : datetime|date(+hour) and one column per state
Hourly resolution is required (the model compares announcement hours).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from .states import normalise_state

_VAL = ("api", "ipu", "value", "index", "nilai")
_STATE = ("state", "negeri")
_DT = ("datetime", "timestamp", "date_time", "tarikh_masa")


def _read_one(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    cols = set(df.columns)
    dtc = next((c for c in _DT if c in cols), None)
    if dtc:
        ts = pd.to_datetime(df[dtc], errors="coerce")
    elif "date" in cols and "hour" in cols:
        ts = pd.to_datetime(df["date"], errors="coerce") + pd.to_timedelta(pd.to_numeric(df["hour"], errors="coerce"), unit="h")
    elif "date" in cols and "time" in cols:
        ts = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str), errors="coerce")
    elif "date" in cols:
        ts = pd.to_datetime(df["date"], errors="coerce")
    else:
        raise ValueError(f"{path.name}: no datetime/date column found")
    df = df.assign(datetime=ts)
    sc = next((c for c in _STATE if c in cols), None)
    vc = next((c for c in _VAL if c in cols), None)
    if sc and vc:
        out = df[["datetime", sc, vc]].rename(columns={sc: "state", vc: "api"})
    else:  # wide
        sc_cols = [c for c in df.columns if normalise_state(c)]
        if not sc_cols:
            raise ValueError(f"{path.name}: need state+api columns or one column per state")
        out = df.melt(id_vars="datetime", value_vars=sc_cols, var_name="state", value_name="api")
    out["state"] = out["state"].map(normalise_state)
    out["api"] = pd.to_numeric(out["api"], errors="coerce")
    return out.dropna(subset=["datetime", "state"])


def load_dir(path) -> pd.DataFrame:
    files = sorted(Path(path).glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"no CSV files in {path}")
    df = pd.concat([_read_one(f) for f in files], ignore_index=True)
    return df.groupby(["datetime", "state"], as_index=False).api.mean()


def to_cube(df: pd.DataFrame):
    """-> (days DatetimeIndex, areas list, cube[A, D, 24]; NaN gaps <=3h interpolated).

    An 'area' column ("State|Station") is used when present, otherwise the state is the area.
    """
    df = df.copy()
    if "area" not in df:
        df["area"] = df["state"]
    if df.datetime.dt.hour.nunique() < 12:
        raise ValueError("data looks daily/sparse; hourly readings (>=12 distinct hours) are required")
    df["day"] = df.datetime.dt.floor("D")
    df["hour"] = df.datetime.dt.hour
    days = pd.date_range(df.day.min(), df.day.max(), freq="D")
    areas = sorted(df.area.unique())
    cube = np.full((len(areas), len(days), 24), np.nan)
    ai = {a: i for i, a in enumerate(areas)}
    di = {d: i for i, d in enumerate(days)}
    cube[df.area.map(ai).values, df.day.map(di).values, df.hour.values] = df.api.values
    flat = pd.DataFrame(cube.reshape(len(areas), -1).T).interpolate(limit=3, limit_area="inside")
    return days, areas, flat.values.T.reshape(cube.shape)
