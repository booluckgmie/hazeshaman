"""Schools / students / teachers per STATE, from data.gov.my (OpenDOSM catalogue).

The DOE API reports by state (every station carries a STATE_ID), so impact is attached to the state:
station -> state -> number of schools. No district or station mapping is needed.

Datasets (MOE administrative data, yearly, state level = the 'All Districts' rows):
  schools_district            "Public Education Institutions by District": schools by type/stage, IPTA universities
  enrolment_school_district   "Enrolment in Government Schools by District": students by stage
  teachers_district           "Teachers in Government Schools by District": teachers by stage
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


def _state_rows(df):
    """State-level rows only (district == 'All Districts', state != 'Malaysia'), latest date of this subset."""
    d = df[(df.district == "All Districts") & (df.state != "Malaysia")]
    return d[d.date == d.date.max()] if len(d) else d


def build(cache_dir="data/schools"):
    """-> (by_state {"Johor": {schools, students, teachers, post_secondary, ipta}}, meta)."""
    sc, src1 = _fetch("schools_district", cache_dir)
    en, src2 = _fetch("enrolment_school_district", cache_dir)
    te, src3 = _fetch("teachers_district", cache_dir)
    sch = _state_rows(sc[sc.stage.isin(STAGES)])
    ipta = _state_rows(sc[(sc.stage == "tertiary") & (sc.type == "IPTA")])
    enr = _state_rows(en[en.sex == "both"])
    tea = _state_rows(te[(te.sex == "both") & te.stage.isin(STAGES)])
    by = lambda d, col, stages=None: (d if stages is None else d[d.stage.isin(stages)]).groupby("state")[col].sum()  # noqa: E731
    t = pd.concat({"schools": by(sch, "schools"), "students": by(enr, "students", STAGES),
                   "post_secondary": by(enr, "students", ["post_secondary"]), "teachers": by(tea, "teachers"),
                   "ipta": by(ipta, "schools")}, axis=1).fillna(0)
    t.index = [normalise_state(s) for s in t.index]
    assert t.index.notna().all() and t.index.is_unique, "unmapped state names"
    by_state = {s: {k: int(round(v)) for k, v in row.items()} for s, row in t.iterrows()}
    nat = lambda d, col: int(d[(d.state == "Malaysia") & (d.district == "All Districts")][col].sum())  # noqa: E731
    tot = t.sum()
    meta = dict(source="data.gov.my / OpenDOSM catalogue: schools_district, enrolment_school_district, teachers_district",
                year=str(sch.date.max())[:10], level="state",
                scope="government primary + secondary schools; IPTA public universities listed separately",
                total_schools=int(tot.schools), total_students=int(tot.students), total_teachers=int(tot.teachers),
                total_ipta=int(tot.ipta), total_post_secondary=int(tot.post_secondary), fetched=[src1, src2, src3])
    return by_state, meta
