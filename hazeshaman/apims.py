"""DOE APIMS sources -> one clean long frame [datetime, state, area, api, rank].

Sources (higher `rank` wins when the same area+hour appears twice):
  0 csv format A  (old daily files: one date stamp per file, window hours after the
                   snapshot time can belong to the previous day - superseded by archive)
  1 archive parquet (2017-07 -> 2024-11, date-corrected)
  2 csv format B  (2025-07 -> now, date-corrected)
  3 live API      (https://eqms.doe.gov.my/api3/publicportalapims/apitablehourly)

Bad-value guard ("hours that have not been reached yet"): every source is cut at `as_of`
(current Malaysia hour); rows with a timestamp after it are dropped, as are non-numeric
flags, off-the-hour stamps (e.g. 05:15AM) and values outside 1..500.
"""
import glob
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .states import normalise_state

LIVE_URL = "https://eqms.doe.gov.my/api3/publicportalapims/apitablehourly"
MYT = timezone(timedelta(hours=8))
STATE_ID = {1: "Johor", 2: "Kedah", 3: "Kelantan", 4: "Melaka", 5: "Negeri Sembilan", 6: "Pahang",
            7: "Pulau Pinang", 8: "Perak", 9: "Perlis", 10: "Selangor", 11: "Terengganu", 12: "Sabah",
            13: "Sarawak", 14: "WP Kuala Lumpur", 15: "WP Labuan", 16: "WP Putrajaya"}
COLS = ["datetime", "state", "area", "api", "rank"]


def now_myt() -> pd.Timestamp:
    """Current Malaysia wall-clock hour as a naive timestamp (data are in local time)."""
    return pd.Timestamp(datetime.now(MYT).replace(tzinfo=None)).floor("h")


def area_key(state: str, location: str) -> str:
    return f"{state}|{str(location).strip()}"


def clean(df: pd.DataFrame, as_of: pd.Timestamp, stats: dict | None = None) -> pd.DataFrame:
    """Apply the bad-value guard; `stats` (optional) collects what was dropped."""
    st = stats if stats is not None else {}
    n0 = len(df)
    df = df.copy()
    df["api"] = pd.to_numeric(df["api"], errors="coerce")
    df = df.dropna(subset=["datetime", "state", "area", "api"])
    st["non_numeric"] = st.get("non_numeric", 0) + (n0 - len(df))
    off = df.datetime.dt.minute != 0
    st["off_hour"] = st.get("off_hour", 0) + int(off.sum())
    df = df[~off]
    fut = df.datetime > as_of
    st["future_hours"] = st.get("future_hours", 0) + int(fut.sum())
    df = df[~fut]
    bad = (df.api < 1) | (df.api > 500)
    st["out_of_range"] = st.get("out_of_range", 0) + int(bad.sum())
    return df[~bad]


def _hour(s: pd.Series) -> pd.DataFrame:
    t = pd.to_datetime(s.astype(str).str.strip(), format="%I:%M%p", errors="coerce")
    return pd.DataFrame({"h": t.dt.hour, "m": t.dt.minute})


def _from_hour_rows(d: pd.DataFrame, rank: int) -> pd.DataFrame:
    """Frame with State, Location, hour, index, date  ->  common schema."""
    hm = _hour(d["hour"])
    # unparseable or off-the-hour labels become NaT here and are counted by clean()
    ts = pd.to_datetime(d["date"], errors="coerce") + pd.to_timedelta(hm.h, unit="h") + pd.to_timedelta(hm.m.fillna(0), unit="m")
    state = d["State"].map(normalise_state)
    out = pd.DataFrame({"datetime": ts, "state": state, "api": d["index"]})
    out["area"] = [area_key(s, l) if isinstance(s, str) else None for s, l in zip(state, d["Location"])]
    out["rank"] = rank
    return out[COLS]


def load_archive(path, as_of, stats=None) -> pd.DataFrame:
    return clean(_from_hour_rows(pd.read_parquet(path), 1), as_of, stats)


def load_csv_dir(path, as_of, stats=None, since=None) -> pd.DataFrame:
    parts = []
    for f in sorted(glob.glob(os.path.join(path, "20*.csv"))):
        if since is not None and os.path.basename(f)[:10] < since:
            continue
        d = pd.read_csv(f)
        fmt_b = d["date"].nunique() > 1          # B stamps yesterday's hours with yesterday's date
        x = _from_hour_rows(d, 2 if fmt_b else 0)
        fdate = pd.Timestamp(os.path.basename(f)[:10])
        x = x[x.datetime.isna() | (x.datetime < fdate + pd.Timedelta(days=1))]   # no rows dated after the file day
        parts.append(x)
    return clean(pd.concat(parts, ignore_index=True), as_of, stats)


def parse_live(payload: dict, as_of: pd.Timestamp, stats=None):
    """-> (frame, stations DataFrame[area, station_id, lat, lon, label])."""
    raw = pd.DataFrame(payload["api_table_hourly"])
    state = raw.STATE_ID.map(STATE_ID)
    loc = raw.STATION_LOCATION.str.split(",").str[0].str.strip()
    df = pd.DataFrame({"datetime": pd.to_datetime(raw.DATETIME), "state": state,
                       "area": [area_key(s, l) for s, l in zip(state, loc)], "api": raw.API, "rank": 3})
    st = (pd.DataFrame({"area": df.area, "station_id": raw.STATION_ID, "lat": raw.LATITUDE, "lon": raw.LONGITUDE,
                        "label": loc}).drop_duplicates("area").reset_index(drop=True))
    return clean(df, as_of, stats), st


def fetch_live(timeout=30, retries=3) -> dict:
    import time

    import requests
    last = None
    for i in range(retries):
        try:
            r = requests.get(LIVE_URL, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 hazeshaman"})
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"DOE live API failed after {retries} tries: {last}")


def merge(frames) -> pd.DataFrame:
    """Same area+hour in several sources: keep the highest rank (later row wins ties)."""
    df = pd.concat(frames, ignore_index=True)
    df = df.reset_index().sort_values(["rank", "index"]).drop(columns="index")
    return df.drop_duplicates(["datetime", "area"], keep="last").sort_values(["area", "datetime"]).reset_index(drop=True)
