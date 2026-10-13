"""Feature engineering at an announcement hour, plus the three target events."""
import warnings

import numpy as np

FEATURES = ["l_now", "l_am", "l_noon", "d3", "l_prev", "streak", "sin_doy", "cos_doy"]
HOURS = list(range(12, 24))            # model available once the HH:00 reading is in (noon..23:00)
ANNOUNCE_HOURS = [15, 16, 17, 18, 19, 20, 21]   # candidate announcement times compared in the backtest


def daily_mean(cube, min_hours=18):
    """Daily mean, NaN when fewer than `min_hours` readings exist (partial days are not trusted)."""
    n = np.sum(~np.isnan(cube), axis=2)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.where(n >= min_hours, np.nanmean(cube, axis=2), np.nan)


def day_flags(cube):
    dm = daily_mean(cube)                        # [S, D]
    return dm, np.nan_to_num(dm, nan=0.0) > 150


def _streak(over):
    S, D = over.shape
    out, run = np.zeros((S, D)), np.zeros(S)
    for d in range(D):
        out[:, d] = np.minimum(run, 3)
        run = np.where(over[:, d], run + 1, 0)
    return out


def build(cube, days, H, truth=None):
    """Return X[N,8], extras dict, targets dict, index arrays (s, d) for rows with full data.

    streak = consecutive prior days (up to 3) with daily mean > 150.
    """
    S, D, _ = cube.shape
    dm, over = day_flags(cube)
    streak = _streak(over)
    tc = cube if truth is None else truth                       # truth cube = what really happened (DOE); features may come from another source
    tdm, tover = day_flags(tc)
    tstreak = _streak(tover)
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
    nxt7[:, :-1] = tc[:, 1:, 7]
    nxtmax = np.full((S, D), np.nan)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        nxtmax[:, :-1] = np.where(np.sum(~np.isnan(tc[:, 1:, 6:15]), axis=2) >= 7, np.nanmax(tc[:, 1:, 6:15], axis=2), np.nan)
    nxtmean = np.full((S, D), np.nan)
    nxtmean[:, :-1] = tdm[:, 1:]
    avg3 = np.exp((now + am + noon) / 3)
    ok = ~(np.isnan(X).any(axis=2) | np.isnan(nxt7) | np.isnan(nxtmax) | np.isnan(nxtmean))
    s_idx, d_idx = np.where(ok)
    T = {
        "y100": (nxt7 > 100)[ok], "y150": (nxt7 > 150)[ok], "y180": (nxtmax > 180)[ok],
        "ymean150": (nxtmean > 150)[ok], "l7": np.log(np.maximum(nxt7, 1))[ok],
    }
    days_over = streak[ok] + (avg3[ok] > 150)
    tavg3 = np.exp((np.log(np.maximum(tc[:, :, H], 1)) + np.log(np.maximum(tc[:, :, 8], 1)) + np.log(np.maximum(tc[:, :, 12], 1))) / 3)
    days_over_true = tstreak[ok] + (tavg3[ok] > 150)
    return X[ok], dict(days_over=days_over, days_over_true=days_over_true), T, s_idx, d_idx


def close_prob(p180, pmean150, days_over):
    """P(close tomorrow) = P(API>180 in school hours) or (>=2 prior over-150 days and tomorrow mean >150)."""
    persist = (days_over >= 2) * pmean150
    return p180 + (1 - p180) * persist


def close_truth(T, extras):
    """What actually happened (uses the DOE-based streak even when the model inputs come from another source)."""
    return T["y180"] | ((extras.get("days_over_true", extras["days_over"]) >= 2) & T["ymean150"])
