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


def test_schools_are_attached_at_state_level():
    from pathlib import Path
    if not Path("data/schools/schools_district.json").exists():
        pytest.skip("no cached school data")
    by_state, meta = schools.build()
    assert set(by_state) == set(__import__("hazeshaman.states", fromlist=["STATES"]).STATES)       # 16 canonical states
    assert sum(v["schools"] for v in by_state.values()) == meta["total_schools"] == 10238          # reconciles with the national row
    assert by_state["Johor"]["schools"] == 1195 and by_state["Johor"]["teachers"] > 40000


def test_history_archive_is_idempotent_and_loadable(tmp_path):
    as_of = pd.Timestamp("2026-10-13 15:00")
    df, _ = apims.parse_live(_payload([(f"2026-10-13T{h:02d}:00:00", 50 + h) for h in range(10, 16)]), as_of)
    assert apims.append_history(df, tmp_path) == 6
    assert apims.append_history(df, tmp_path) == 0                       # same hours again: nothing new
    df2 = df.assign(api=999.0).iloc[:1]
    apims.append_history(df2.assign(api=77.0), tmp_path)                 # a revised value replaces the old one
    back = apims.load_history_dir(tmp_path, as_of)
    assert len(back) == 6 and (back["rank"] == 2).all() and 77.0 in back.api.values


# ---------------- Open-Meteo cross-check ----------------
from hazeshaman import crosscheck as cc  # noqa: E402


def test_quantile_mapping_preserves_extremes_and_is_monotone():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2024-01-01", periods=4000, freq="h")
    a = pd.Series(np.exp(rng.normal(4.0, 0.5, len(idx))), index=idx)          # model AQI
    y = pd.Series(0.6 * a.values + 5, index=idx)                               # station reads systematically lower
    xk, yk = cc.fit_qm(a, y)
    assert (np.diff(xk) > 0).all() and (np.diff(yk) >= 0).all()
    mapped = cc.apply_qm(a.values, xk, yk)
    assert abs(np.nanmean(mapped) - y.mean()) < 1.0                            # bias removed
    assert abs(np.percentile(mapped, 99.5) - np.percentile(y, 99.5)) < 5        # tail kept (regression would shrink it)
    assert cc.apply_qm(np.array([a.max() + 50]), xk, yk)[0] > yk[-1]           # extrapolates upwards, never clips


def _series(n=120):
    t = pd.date_range("2026-10-10", periods=n, freq="h")
    e = np.full(n, 120.0)                                                       # independent source: steady "unhealthy"
    return t, e, e * np.exp(-0.4), e * np.exp(0.4)


def test_detects_frozen_spike_high_and_low_but_not_normal_wobble():
    t, e, lo, hi = _series()
    ok = np.linspace(116, 126, len(t)) + np.sin(np.arange(len(t)))
    assert cc.detect(t, ok, e, lo, hi) == []                                    # normal agreement -> nothing
    d = ok.copy(); d[10:36] = 117.0                                             # 26 identical hours
    assert [x["type"] for x in cc.detect(t, d, e, lo, hi)] == ["frozen"]
    d = ok.copy(); d[50] = 215                                                  # one-hour jump the other source does not share
    assert "spike" in [x["type"] for x in cc.detect(t, d, e, lo, hi)]
    d = ok.copy(); d[60:70] = 230                                               # sustained, far above the range, closure level
    ev = [x for x in cc.detect(t, d, e, lo, hi) if x["type"] == "high"]
    assert len(ev) == 1 and ev[0]["severity"] == "critical" and "closure" in ev[0]["msg"]
    e1 = np.full(len(t), 70.0); d = np.full(len(t), 72.0); d[60:70] = 135       # unhealthy but below closure level, source says 70 -> warn
    assert [x["severity"] for x in cc.detect(t, d, e1, e1 * .67, e1 * 1.5) if x["type"] == "high"] == ["warn"]
    d = ok.copy(); d[80:90] = 30
    assert [x["type"] for x in cc.detect(t, d, e, lo, hi) if x["type"] == "low"] == ["low"]
    d = ok.copy(); d[60:62] = 230                                               # 2 h only: below the sustained-run threshold
    assert not [x for x in cc.detect(t, d, e, lo, hi) if x["type"] == "high"]


def test_low_readings_during_haze_are_critical_and_immaterial_mismatches_are_ignored():
    t, e, lo, hi = _series()
    e2 = np.full(len(t), 170.0); lo2, hi2 = e2 * np.exp(-0.4), e2 * np.exp(0.4)
    d = np.linspace(168, 172, len(t)); d[40:52] = 70                            # independent source says hazardous-ish, DOE says fine
    ev = [x for x in cc.detect(t, d, e2, lo2, hi2) if x["type"] == "low"]
    assert len(ev) == 1 and ev[0]["severity"] == "critical" and "under-reporting during haze" in ev[0]["msg"]
    e3 = np.full(len(t), 25.0); d3 = np.full(len(t), 60.0) + np.sin(np.arange(len(t)))
    assert not [x for x in cc.detect(t, d3, e3, e3 * .6, e3 * 1.5) if x["type"] in ("high", "low")]   # Good vs Moderate: not a decision matter


def test_frozen_needs_a_reason_when_short_but_a_full_day_always_counts():
    t, e, lo, hi = _series()
    base = np.linspace(116, 126, len(t))
    d = base.copy(); d[10:24] = 117.0                                           # 14 h repeat, independent source flat -> benign plateau
    assert not [x for x in cc.detect(t, d, e, lo, hi) if x["type"] == "frozen"]
    e2 = e.copy(); e2[10:24] = np.linspace(90, 150, 14)                         # same repeat while the other source moved 60 points
    assert [x["type"] for x in cc.detect(t, d, e2, e2 * .67, e2 * 1.5) if x["type"] == "frozen"] == ["frozen"]


def test_update_writes_flags_and_series(tmp_path):
    import json
    n = 120; idx = pd.date_range("2026-10-08", periods=n, freq="h")
    live = {"end": str(idx[-1])[:16].replace(" ", "T"), "hours": n,
            "areas": {"Johor|Larkin": [int(v) for v in np.r_[np.full(n - 30, 70), np.full(30, 200)]]},   # 30 h at 200 vs a calm independent source
            "stations": {"Johor|Larkin": {"lat": 1.5, "lon": 103.8, "label": "Larkin", "station_id": "CA33J"}}}
    (tmp_path / "live.json").write_text(json.dumps(live))
    xk = np.array([0., 100., 300.]); yk = np.array([0., 80., 90.])
    st = dict(corr=.8, mae=10, within1=1.0, same_band=.8, corroborated_150=.5, n_150=10, first="2023-01-01", last="2026-10-01", events_per_year={}, q_lo=-.4, q_hi=.4, q_lo99=-.6, q_hi99=.6, grade="B")
    cc.save_model(tmp_path / "m.json", {"Johor|Larkin": dict(model=(xk, yk), stats=st)})
    om = pd.DataFrame({"datetime": pd.date_range(idx[0] - pd.Timedelta(days=2), idx[-1], freq="h")}); om["us_aqi"] = 80.0
    d = cc.update(tmp_path / "live.json", tmp_path / "m.json", tmp_path / "x.json", om_frames={"Johor|Larkin": om})
    s = d["stations"]["Johor|Larkin"]
    assert len(s["om"]) == n and s["grade"] == "B"
    fl = [f for f in d["flags"] if f["type"] == "high"]
    assert fl and fl[0]["severity"] == "critical" and d["summary"]["critical"] == 1
    assert json.loads((tmp_path / "x.json").read_text())["end"] == live["end"]


def test_closures_csv_is_valid_and_exports(tmp_path):
    from hazeshaman import closures
    rows = closures.load("data/closures.csv")
    assert len(rows) > 30
    assert all(r["source_url"].startswith("https://") for r in rows)
    assert {r["verified"] for r in rows} <= {"read", "summary"}
    out = tmp_path / "c.json"
    assert closures.export("data/closures.csv", str(out)) == len(rows)
    import json
    d = json.loads(out.read_text())
    assert d["n"] == len(rows) and d["first"] <= d["last"]
