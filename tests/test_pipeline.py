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
    days, states, cube = to_cube(pd.concat([w, l]))
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
