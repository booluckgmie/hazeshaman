"""Synthetic hourly API generator. DEMO ONLY - replace with real data in data/raw/.

Latent daily log-level = state base + seasonal haze bump (Jun-Oct) + regional AR(1)
+ state AR(1) + decaying episode shocks. Hourly values interpolate between daily
noon knots (so afternoon trend carries into the next morning) plus a diurnal cycle.
"""
import numpy as np
import pandas as pd

from .states import STATES

_BASE = dict(zip(STATES, [52, 48, 40, 53, 50, 46, 50, 47, 52, 38, 42, 56, 40, 55, 54, 44]))
_SENS = dict(zip(STATES, [1.0, 0.9, 0.5, 1.1, 1.0, 0.8, 1.0, 0.9, 1.0, 0.6, 1.2, 1.3, 0.5, 1.2, 1.2, 0.8]))


def generate(start="2018-01-01", end="2025-12-31", seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end, freq="D")
    D, S = len(days), len(STATES)
    doy = days.dayofyear.values
    year_int = {y: rng.lognormal(0, 0.45) for y in days.year.unique()}
    intensity = np.array([year_int[y] for y in days.year])
    season = np.exp(-0.5 * ((doy - 235) / 38.0) ** 2) * intensity

    def ar1(phi, sigma, shape):
        x = np.zeros(shape)
        e = rng.normal(0, sigma, shape)
        for t in range(1, shape[0]):
            x[t] = phi * x[t - 1] + e[t]
        return x

    reg = ar1(0.93, 0.10, (D,))
    st = ar1(0.88, 0.09, (D, S))
    # episodic shocks: more likely in the haze season, decay over ~4 days
    shock = np.zeros((D, S))
    for t in range(D):
        p = 0.003 + 0.022 * season[t]
        if rng.random() < p:
            amp = rng.lognormal(np.log(0.36), 0.35)
            reach = rng.random(S) < 0.55
            shock[t] += amp * reach * np.array([_SENS[s] for s in STATES])
    # decay pass
    for t in range(1, D):
        shock[t] += 0.80 * shock[t - 1]
    sens = np.array([_SENS[s] for s in STATES])
    base = np.log([_BASE[s] for s in STATES])
    daily = base[None, :] + 0.55 * season[:, None] * sens[None, :] + reg[:, None] + st + shock

    # hourly: interpolate noon knots, add diurnal cycle + hourly noise
    H = D * 24
    t_h = np.arange(H) / 24.0
    knots = np.arange(D) + 0.5
    out = np.empty((H, S))
    h = np.arange(H) % 24
    diurnal = 0.07 * np.cos(2 * np.pi * (h - 8) / 24) + 0.04 * np.cos(2 * np.pi * (h - 21) / 12)
    # unpredictable overnight shock: held 06:00-18:00, then ramps to next night's value by 06:00
    T = np.arange(H) - 6.0
    k = np.floor(T / 24).astype(int)
    frac = T - 24 * k
    ramp = np.clip((frac - 12) / 12, 0, 1)
    k0, k1 = np.clip(k, 0, D - 1), np.clip(k + 1, 0, D - 1)
    eps = rng.normal(0, 0.22, (D, S))
    for j in range(S):
        base_h = np.interp(t_h, knots, daily[:, j]) + eps[k0, j] + (eps[k1, j] - eps[k0, j]) * ramp
        noise = ar1(0.85, 0.025, (H,))
        out[:, j] = np.exp(base_h + diurnal + noise)
    out = np.clip(np.round(out), 5, 500)
    idx = pd.date_range(start, periods=H, freq="h")
    df = pd.DataFrame(out, index=idx, columns=STATES).rename_axis("datetime").reset_index()
    return df.melt(id_vars="datetime", var_name="state", value_name="api")
