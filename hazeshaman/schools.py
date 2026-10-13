"""Schools / students per air-quality station area, from data.gov.my (OpenDOSM catalogue).

Datasets (OpenDOSM catalogue, district level, MOE administrative data):
  schools_district            "Public Education Institutions by District": schools (primary/secondary) and
                              tertiary institutions (IPTA, IPG, Politeknik, Kolej Komuniti) by type/stage/district
  enrolment_school_district   "Enrolment in Government Schools by District": students by stage/sex/district
  teachers_district           "Teachers in Government Schools by District": teachers by stage/sex/district
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


def _latest(df):
    return df[df.date == df.date.max()]


def build(map_csv="data/district_station_map.csv", cache_dir="data/schools"):
    """-> (by_area dict {"State|Station": {...}}, meta dict)."""
    sc, src1 = _fetch("schools_district", cache_dir)
    en, src2 = _fetch("enrolment_school_district", cache_dir)
    te, src3 = _fetch("teachers_district", cache_dir)
    keep = lambda d: d[d.district != "All Districts"]  # noqa: E731
    sc, en, te = keep(sc), keep(en), keep(te)
    sch = _latest(sc[sc.stage.isin(STAGES)])
    ter = _latest(sc[sc.stage == "tertiary"])
    enr = _latest(en[(en.sex == "both")])
    tea = _latest(te[(te.sex == "both") & te.stage.isin(STAGES)])
    g = lambda d, col, name, stages=None: (d if stages is None else d[d.stage.isin(stages)]).groupby(["state", "district"])[col].sum().rename(name)  # noqa: E731
    d = pd.concat([g(sch, "schools", "schools"), g(enr, "students", "students", STAGES),
                   g(enr, "students", "post_secondary", ["post_secondary"]), g(tea, "teachers", "teachers"),
                   ter.groupby(["state", "district"]).schools.sum().rename("tertiary")], axis=1).fillna(0).reset_index()
    mp = pd.read_csv(map_csv)
    j = d.merge(mp, on=["state", "district"], how="left")
    unmapped = j[j.station.isna()][["state", "district"]].values.tolist()
    j = j.dropna(subset=["station"])
    j["state"] = j.state.map(normalise_state)
    nums = ["schools", "students", "post_secondary", "teachers", "tertiary"]
    for c in nums:
        j[c] = j[c] * j.weight
    agg = {c: (c, "sum") for c in nums}
    gg = j.groupby(["state", "station"]).agg(**agg, districts=("district", lambda s: sorted(set(s)))).reset_index()
    by_area = {f"{r.state}|{r.station}": dict(schools=int(round(r.schools)), students=int(round(r.students)),
                                              teachers=int(round(r.teachers)), tertiary=int(round(r.tertiary)),
                                              post_secondary=int(round(r.post_secondary)), districts=r.districts)
               for r in gg.itertuples()}
    tot = d[nums].sum()
    meta = dict(source="data.gov.my / OpenDOSM catalogue: schools_district, enrolment_school_district, teachers_district",
                year=str(sch.date.max())[:10], scope="government primary + secondary schools (+ IPTA public universities, the only tertiary type published by district)",
                total_schools=int(tot.schools), total_students=int(tot.students), total_teachers=int(tot.teachers),
                total_tertiary=int(tot.tertiary), total_post_secondary=int(tot.post_secondary),
                fetched=[src1, src2, src3], unmapped=unmapped)
    return by_area, meta
