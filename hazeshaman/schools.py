"""Schools / students per air-quality station area, from data.gov.my (OpenDOSM catalogue).

Datasets (district level, government primary + secondary only):
  schools_district            number of schools by type/stage/state/district
  enrolment_school_district   students by stage/sex/state/district
Each district is assigned to its nearest DOE station via data/district_station_map.csv
(a manual approximation: edit it to refine; a district may be split across stations by weight).
"""
import json
from pathlib import Path

import pandas as pd

from .states import normalise_state

API = "https://api.data.gov.my/data-catalogue?id={id}&limit=100000"
STAGES = {"primary", "secondary"}


def _fetch(ds_id, cache_dir):
    path = Path(cache_dir) / f"{ds_id}.json"
    try:
        import requests
        r = requests.get(API.format(id=ds_id), timeout=60)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list) or not data:
            raise ValueError("unexpected payload")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return pd.DataFrame(data), "fetched"
    except Exception as e:  # fall back to the cached copy, never to made-up numbers
        if path.exists():
            return pd.DataFrame(json.loads(path.read_text())), f"cache ({type(e).__name__})"
        raise


def build(map_csv="data/district_station_map.csv", cache_dir="data/schools"):
    """-> (by_area dict {"State|Station": {...}}, meta dict)."""
    sc, src1 = _fetch("schools_district", cache_dir)
    en, src2 = _fetch("enrolment_school_district", cache_dir)
    sc = sc[(sc.district != "All Districts") & sc.stage.isin(STAGES)]
    sc = sc[sc.date == sc.date.max()]
    en = en[(en.district != "All Districts") & en.stage.isin(STAGES) & (en.sex == "both")]
    en = en[en.date == en.date.max()]
    d = (sc.groupby(["state", "district"]).schools.sum().to_frame()
         .join(en.groupby(["state", "district"]).students.sum(), how="left").fillna(0).reset_index())
    mp = pd.read_csv(map_csv)
    j = d.merge(mp, on=["state", "district"], how="left")
    unmapped = j[j.station.isna()][["state", "district"]].values.tolist()
    j = j.dropna(subset=["station"])
    j["state"] = j.state.map(normalise_state)
    j["schools"] *= j.weight
    j["students"] *= j.weight
    g = j.groupby(["state", "station"]).agg(schools=("schools", "sum"), students=("students", "sum"),
                                              districts=("district", lambda s: sorted(set(s)))).reset_index()
    by_area = {f"{r.state}|{r.station}": dict(schools=int(round(r.schools)), students=int(round(r.students)),
                                              districts=r.districts) for r in g.itertuples()}
    tot = d[["schools", "students"]].sum()
    meta = dict(source="data.gov.my / OpenDOSM catalogue: schools_district, enrolment_school_district",
                year=str(sc.date.max())[:10], scope="government primary + secondary schools",
                total_schools=int(tot.schools), total_students=int(tot.students),
                fetched=[src1, src2], unmapped=unmapped)
    return by_area, meta
