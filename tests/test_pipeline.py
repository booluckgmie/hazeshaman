import numpy as np
import pandas as pd
import pytest

from hazeshaman.features import ANNOUNCE_HOURS, FEATURES, build, close_prob, close_truth
from hazeshaman.loader import _read_one, to_cube
from hazeshaman.states import normalise_state
from hazeshaman.synth import generate


@pytest.fixture(scope="module")
def cube():
    df = generate(start="2023-01-01", end="2023-06-30", seed=1)
    return to_cube(df)


def test_state_aliases():
    assert normalise_state("Penang") == "Pulau Pinang"
    assert normalise_state("N. Sembilan") == "Negeri Sembilan"
    assert normalise_state("selangor") == "Selangor"
    assert normalise_state("Atlantis") is None


def test_loader_wide_and_long(tmp_path):
    ts = pd.date_range("2024-01-01", periods=48, freq="h")
    pd.DataFrame({"datetime": ts, "Selangor": 50, "Penang": 60}).to_csv(tmp_path / "w.csv", index=False)
    pd.DataFrame({"date": ts.date, "hour": ts.hour, "negeri": "Johor", "ipu": 70}).to_csv(tmp_path / "l.csv", index=False)
    w, l = _read_one(tmp_path / "w.csv"), _read_one(tmp_path / "l.csv")
    assert set(w.state) == {"Selangor", "Pulau Pinang"} and set(l.state) == {"Johor"}
    days, areas, cube = to_cube(pd.concat([w, l]))
    assert cube.shape == (3, 2, 24) and not np.isnan(cube).any()


def test_daily_data_rejected():
    df = pd.DataFrame({"datetime": pd.date_range("2024-01-01", periods=10), "state": "Johor", "api": 50})
    with pytest.raises(ValueError):
        to_cube(df)


def test_targets_use_next_day_only(cube):
    days, states, c = cube
    H = ANNOUNCE_HOURS[0]
    X, ex, T, s_idx, d_idx = build(c, days, H)
    assert X.shape[1] == len(FEATURES)
    i = 10
    s, d = s_idx[i], d_idx[i]
    assert T["y100"][i] == (c[s, d + 1, 7] > 100)
    assert T["y180"][i] == (c[s, d + 1, 6:15].max() > 180)
    # features must not depend on tomorrow: perturbing tomorrow leaves X unchanged
    c2 = c.copy(); c2[:, d + 1:, :] *= 3
    X2, *_ = build(c2, days, H)
    assert np.allclose(X[i], X2[np.where((s_idx == s) & (d_idx == d))[0][0]])


def test_close_prob_rule():
    p = close_prob(np.array([.1, .1]), np.array([.5, .5]), np.array([1, 2]))
    assert p[0] == pytest.approx(.1) and p[1] == pytest.approx(.1 + .9 * .5)
    T = {"y180": np.array([False, False, True]), "ymean150": np.array([True, True, False])}
    out = close_truth(T, {"days_over": np.array([1, 2, 0])})
    assert out.tolist() == [False, True, True]


# ---------------- DOE sources, guard, live buffer, schools ----------------
from hazeshaman import apims, live, schools  # noqa: E402


def _payload(rows):
    return {"api_table_hourly": [dict(STATION_ID="CA01R", STATE_ID=9, STATION_LOCATION="Kangar, PERLIS",
                                      LATITUDE=6.4, LONGITUDE=100.2, DATETIME=t, API=v) for t, v in rows]}


def test_guard_drops_future_and_bad_values():
    as_of = pd.Timestamp("2026-10-13 20:00")
    rows = [("2026-10-13T19:00:00", 80), ("2026-10-13T20:00:00", 81), ("2026-10-13T21:00:00", 400),
            ("2026-10-13T20:15:00", 90), ("2026-10-13T18:00:00", -1), ("2026-10-13T17:00:00", 900)]
    st = {}
    df, stations = apims.parse_live(_payload(rows), as_of, st)
    assert df.datetime.max() == as_of and len(df) == 2
    assert st["future_hours"] == 1 and st["off_hour"] == 1 and st["out_of_range"] == 2
    assert stations.label.iloc[0] == "Kangar"


def test_archive_hour_labels_and_priority():
    d = pd.DataFrame({"State": ["PERLIS"] * 3, "Location": ["Kangar"] * 3, "hour": ["12:00AM", "11:00PM", "05:15AM"],
                      "index": [41, 44, 50], "date": ["2017-07-31", "2017-07-30", "2017-07-31"]})
    f = apims.clean(apims._from_hour_rows(d, 1), pd.Timestamp("2030-01-01"))
    assert sorted(f.datetime.dt.strftime("%m-%d %H")) == ["07-30 23", "07-31 00"]   # 05:15 dropped
    a = f.assign(rank=0, api=1.0)
    m = apims.merge([a, f])
    assert (m.api > 1).all() and len(m) == 2            # higher rank wins


def test_live_buffer_rolls_and_ignores_future(tmp_path):
    out = tmp_path / "live.json"
    t = lambda h: f"2026-10-13T{h:02d}:00:00"   # noqa: E731
    live.update(out, _payload([(t(h), 50 + h) for h in range(10, 15)]), pd.Timestamp("2026-10-13 14:00"))
    d = live.update(out, _payload([(t(14), 99), (t(15), 70), (t(16), 71)]), pd.Timestamp("2026-10-13 15:00"))
    a = d["areas"]["Perlis|Kangar"]
    assert d["end"] == "2026-10-13T15:00" and a[-1] == 70 and a[-2] == 99 and a[-6] == 60   # 10:00 kept, 14:00 revised
    assert 71 not in a                                    # 16:00 is in the future


def test_school_mapping_covers_everything():
    mp = pd.read_csv("data/district_station_map.csv")
    w = mp.groupby(["state", "district"]).weight.sum()
    assert np.allclose(w, 1.0)
    cached = __import__("pathlib").Path("data/schools/schools_district.json")
    if cached.exists():
        by_area, meta = schools.build()
        assert meta["unmapped"] == []
        assert sum(v["schools"] for v in by_area.values()) == meta["total_schools"]
