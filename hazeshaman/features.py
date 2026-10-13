"""Feature engineering at an announcement hour, plus the three target events."""
import numpy as np

FEATURES = ["l_now", "l_am", "l_noon", "d3", "l_prev", "streak", "sin_doy", "cos_doy"]
ANNOUNCE_HOURS = [15, 16, 17, 18, 19, 20, 21]   # readings available up to HH:00 same day


def day_flags(cube):
    dm = cube.mean(axis=2)                       # [S, D]
    return dm, dm > 150


def build(cube, days, H, rows=None):
    """Return X[N,8], extras dict, targets dict, index arrays (s, d) for rows with full data.

    streak = consecutive prior days (up to 3) with daily mean > 150.
    """
    S, D, _ = cube.shape
    dm, over = day_flags(cube)
    streak = np.zeros((S, D))
    run = np.zeros(S)
    for d in range(D):
        streak[:, d] = np.minimum(run, 3)
        run = np.where(over[:, d], run + 1, 0)
    L = np.log(np.maximum(cube, 1))
    now, am, noon = L[:, :, H], L[:, :, 8], L[:, :, 12]
    d3 = now - L[:, :, H - 3]
    prev = np.full((S, D), np.nan)
    prev[:, 1:] = np.log(np.maximum(dm[:, :-1], 1))
    doy = days.dayofyear.values
    ang = 2 * np.pi * doy / 365.25
    sin = np.broadcast_to(np.sin(ang), (S, D))
    cos = np.broadcast_to(np.cos(ang), (S, D))
    X = np.stack([now, am, noon, d3, prev, streak, sin, cos], axis=2)
    nxt7 = np.full((S, D), np.nan)
    nxt7[:, :-1] = cube[:, 1:, 7]
    nxtmax = np.full((S, D), np.nan)
    nxtmax[:, :-1] = cube[:, 1:, 6:15].max(axis=2)
    nxtmean = np.full((S, D), np.nan)
    nxtmean[:, :-1] = dm[:, 1:]
    avg3 = np.exp((now + am + noon) / 3)
    ok = ~(np.isnan(X).any(axis=2) | np.isnan(nxt7) | np.isnan(nxtmax) | np.isnan(nxtmean))
    s_idx, d_idx = np.where(ok)
    T = {
        "y100": (nxt7 > 100)[ok], "y150": (nxt7 > 150)[ok], "y180": (nxtmax > 180)[ok],
        "ymean150": (nxtmean > 150)[ok], "l7": np.log(np.maximum(nxt7, 1))[ok],
    }
    days_over = streak[ok] + (avg3[ok] > 150)
    return X[ok], dict(days_over=days_over), T, s_idx, d_idx


def close_prob(p180, pmean150, days_over):
    """P(close tomorrow) = P(API>180 in school hours) or (>=2 prior over-150 days and tomorrow mean >150)."""
    persist = (days_over >= 2) * pmean150
    return p180 + (1 - p180) * persist


def close_truth(T, extras):
    return T["y180"] | ((extras["days_over"] >= 2) & T["ymean150"])
