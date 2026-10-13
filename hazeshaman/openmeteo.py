"""Open-Meteo Air Quality API (CAMS global atmospheric composition model) - an INDEPENDENT second source.

https://open-meteo.com/en/docs/air-quality-api  - free for non-commercial use, no key, data CC BY 4.0
(Copernicus Atmosphere Monitoring Service via Open-Meteo). Global hourly data starts 2022-07-29; grid ~0.25 deg
(~25 km), so it tracks regional haze well but not single-street peaks: it is a sanity check, not ground truth.

Variables: pm10 / pm2_5 (ug/m3), us_aqi / european_aqi (computed by Open-Meteo), carbon_monoxide (smoke tracer).
"""
import time
from pathlib import Path

import pandas as pd

BASE = "https://air-quality-api.open-meteo.com/v1/air-quality"
VARS = ["pm10", "pm2_5", "us_aqi", "european_aqi", "carbon_monoxide"]
GLOBAL_START = "2022-08-01"


def _get(params, retries=4, timeout=60):
    import requests
    last = None
    for i in range(retries):
        try:
            r = requests.get(BASE, params=params, timeout=timeout)
            if r.status_code == 429:                      # rate limited: back off, then retry
                time.sleep(5 * (i + 1)); continue
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e; time.sleep(2 * (i + 1))
    raise RuntimeError(f"Open-Meteo request failed: {last}")


def _frame(j):
    h = j["hourly"]
    df = pd.DataFrame({"datetime": pd.to_datetime(h["time"])})
    for v in VARS:
        df[v] = pd.to_numeric(pd.Series(h.get(v)), errors="coerce") if v in h else float("nan")
    return df


def fetch(lat, lon, start=None, end=None, past_days=None, forecast_days=1) -> pd.DataFrame:
    """Hourly Malaysia-time frame. Use start/end for history or past_days for the recent window."""
    p = dict(latitude=round(float(lat), 4), longitude=round(float(lon), 4), hourly=",".join(VARS), timezone="Asia/Kuala_Lumpur")
    if past_days is not None:
        p.update(past_days=past_days, forecast_days=forecast_days)
    else:
        p.update(start_date=start or GLOBAL_START, end_date=end)
    return _frame(_get(p))


def fetch_history_cached(key, lat, lon, cache_dir, end, start=GLOBAL_START) -> pd.DataFrame:
    """History cached per station; only the missing tail is requested on later runs."""
    path = Path(cache_dir) / (key.replace("|", "__").replace(" ", "_") + ".csv.gz")
    old = pd.read_csv(path, parse_dates=["datetime"]) if path.exists() else None
    s = start if old is None else str((old.datetime.max() - pd.Timedelta(days=2)).date())
    new = fetch(lat, lon, start=s, end=end)
    df = new if old is None else pd.concat([old, new]).drop_duplicates("datetime", keep="last").sort_values("datetime")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, compression="gzip")
    return df


def fetch_many(coords, past_days=7, forecast_days=1, chunk=25):
    """coords: [(key, lat, lon)] -> {key: DataFrame}. Uses Open-Meteo's multi-location request (one call per `chunk`)."""
    out = {}
    for i in range(0, len(coords), chunk):
        part = coords[i:i + chunk]
        j = _get(dict(latitude=",".join(str(round(float(c[1]), 4)) for c in part), longitude=",".join(str(round(float(c[2]), 4)) for c in part),
                      hourly=",".join(VARS), timezone="Asia/Kuala_Lumpur", past_days=past_days, forecast_days=forecast_days))
        for (key, _, _), jj in zip(part, j if isinstance(j, list) else [j]):
            out[key] = _frame(jj)
    return out


def main(argv=None):
    """python -m hazeshaman.openmeteo [--live docs/live.json] [--cache data/openmeteo]
    Downloads (or tops up) the hourly history of every station into the local cache used by `crosscheck fit` and `build`."""
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default="docs/live.json", help="station list with lat/lon")
    ap.add_argument("--cache", default="data/openmeteo")
    ap.add_argument("--end", default=None, help="last day (default: today, Malaysia time)")
    a = ap.parse_args(argv)
    end = a.end or str((pd.Timestamp.now("UTC") + pd.Timedelta(hours=8)).date())
    stations = json.loads(Path(a.live).read_text())["stations"]
    for i, (k, m) in enumerate(sorted(stations.items()), 1):
        try:
            df = fetch_history_cached(k, m["lat"], m["lon"], a.cache, end)
            print(f"[{i}/{len(stations)}] {k}: {len(df):,} hours to {df.datetime.max()}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(stations)}] {k}: FAILED {e}", flush=True)
        time.sleep(0.5)                                  # stay well inside the free-tier rate limit


if __name__ == "__main__":
    main()
