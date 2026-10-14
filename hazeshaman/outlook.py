"""Seven-day outlook: per-horizon models for the daily haze level, plus the compact daily history the dashboard plots.

    python -m hazeshaman.outlook [--archive P --csv-dir D --history-dir H] [--test-from 2025-07-01]

Writes
  docs/outlook.json   coefficients, interval widths and hold-out skill for horizons 1..7 days ahead
  docs/history.json   every area's daily mean and daily school-hours peak since 2017 (integers), for the history chart

What is forecast (for each station and each horizon k = 1..7 days after the last complete day t):
  * ln of the daily mean API (ridge, Gaussian residual -> median and intervals),
  * P(daily mean > 100), P(daily mean > 150), P(highest reading 06:00-14:00 > 180)   (logistic).
Inputs: ln daily mean on t, t-1, t-2, the mean of t-3..t-6, ln peak on t, how many of the last three days averaged above 150,
season (sin/cos of day of year) and a state effect shared by its stations.  No weather forecast is used, so skill falls with the horizon;
the hold-out table (docs/analysis/07-seven-day-outlook.md) shows how fast, against persistence and a month-by-state climatology.
"""
from __future__ import annotations
import argparse, json
import numpy as np, pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from . import apims
from .histfile import daily, write as export_history_file
from .model import _design, _fit, _pack, _predict

HORIZONS = list(range(1, 8))
FEATURES = ["ln_m0", "ln_m1", "ln_m2", "ln_m3_6", "ln_peak0", "days_over150", "sin_doy", "cos_doy"]


def samples(days, M, P, area_state, k):
    """Feature rows for every (area, day t) that has the inputs, with the targets k days ahead."""
    A, D = M.shape
    lm = np.log(M); lp = np.log(P)
    doy = days.dayofyear.to_numpy(); ang = 2 * np.pi * doy / 365.25
    t = np.arange(6, D - k)
    L = lambda lag: lm[:, t - lag]
    with np.errstate(all="ignore"):
        ln3_6 = np.log(np.mean(np.stack([M[:, t - lag] for lag in (3, 4, 5, 6)]), axis=0))          # NaN if any of the four days is missing
    over = sum((M[:, t - lag] > 150).astype(float) for lag in (0, 1, 2))
    X = np.stack([L(0), L(1), L(2), ln3_6, lp[:, t], over, np.broadcast_to(np.sin(ang[t]), (A, len(t))), np.broadcast_to(np.cos(ang[t]), (A, len(t)))], axis=-1)
    y_ln = lm[:, t + k]; y_m = M[:, t + k]; y_p = P[:, t + k]
    ok = np.isfinite(X).all(axis=-1) & np.isfinite(y_ln)
    ai, ti = np.nonzero(ok)
    return dict(X=X[ai, ti], area=ai, day=t[ti], y_ln=y_ln[ai, ti], m=y_m[ai, ti], p=y_p[ai, ti], m0=M[ai, t[ti]],
                state=np.asarray(area_state)[ai], target_day=t[ti] + k)


def _rmse(a, b): return float(np.sqrt(np.mean((a - b) ** 2)))


QS = [round(q, 2) for q in np.arange(0.05, 0.96, 0.05)]          # residual quantile levels kept per level bin
EDGES = [0, 50, 65, 80, 100, 120, 140, 170, 1e9]                  # bins of the predicted daily mean, API units
MIN_BIN = 250


def resid_table(pred_ln, resid):
    """Empirical residual quantiles per level of the predicted mean: haze days are noisier and are under-predicted by a plain ridge,
    so intervals, the median and exceedance probabilities all come from this table (they are then consistent with each other)."""
    lvl = np.exp(pred_ln); edges = list(EDGES); rows = []
    i = 0
    while i < len(edges) - 1:                                       # merge thin top bins
        j = i + 1
        while True:
            m = (lvl >= edges[i]) & (lvl < edges[j])
            if m.sum() >= MIN_BIN or j == len(edges) - 1: break
            j += 1
        m = (lvl >= edges[i]) & (lvl < edges[j])
        rows.append((edges[i], edges[j], m.sum(), np.quantile(resid[m], QS) if m.sum() else np.zeros(len(QS)), float(np.exp(pred_ln[m]).mean()) if m.sum() else edges[i]))
        i = j
    if len(rows) > 1 and rows[-1][2] < MIN_BIN:                      # fold a thin last bin into the previous one
        a, b = rows[-2], rows[-1]; m = (lvl >= a[0]) & (lvl < b[1]); rows[-2:] = [(a[0], b[1], m.sum(), np.quantile(resid[m], QS), float(np.exp(pred_ln[m]).mean()))]
    return dict(edges=[round(r[0], 1) for r in rows], centers=[round(r[4], 2) for r in rows], q=[[round(float(x), 4) for x in r[3]] for r in rows], n=[int(r[2]) for r in rows])


def _qrow(tab, level):
    """quantile row for a predicted level, interpolated between neighbouring bins (centre to centre)."""
    c = np.asarray(tab["centers"]); q = np.asarray(tab["q"])
    if level <= c[0]: return q[0]
    if level >= c[-1]: return q[-1]
    j = np.searchsorted(c, level) - 1; f = (np.log(level) - np.log(c[j])) / (np.log(c[j + 1]) - np.log(c[j]))
    return q[j] * (1 - f) + q[j + 1] * f


def prob_over(pred_ln, thr, tab):
    """P(daily mean > thr) from the residual quantiles (piecewise-linear CDF)."""
    out = np.empty(len(pred_ln))
    qs = np.asarray([0.0] + QS + [1.0])
    for i, pl in enumerate(pred_ln):
        row = _qrow(tab, float(np.exp(pl))); r = np.log(thr) - pl
        xs = np.r_[row[0] - 0.25, row, row[-1] + 0.25]
        out[i] = 1 - float(np.interp(r, xs, qs))
    return out


def train(df, areas, area_state, n_states, test_from, progress=print):
    days, M, P = daily(df, areas)
    tf = np.searchsorted(days.values, np.datetime64(test_from))
    models, skill = {}, {}
    month = days.month.to_numpy()
    for k in HORIZONS:
        S = samples(days, M, P, area_state, k)
        tr = S["day"] + k < tf; te = ~tr & (S["day"] >= tf)
        mu = S["X"][tr].mean(0); sd = S["X"][tr].std(0) + 1e-9
        Xd = _design(S["X"], S["state"], n_states, mu, sd)
        reg = _fit(Xd[tr], S["y_ln"][tr], len(FEATURES), "reg")
        pred_tr = _predict(reg, Xd[tr]); resid = S["y_ln"][tr] - pred_tr; sigma = float(resid.std())
        tab = resid_table(pred_tr, resid)
        clf = {}
        # P(highest reading 06:00-14:00 > 180): monotone in the predicted daily mean, so it can never contradict the chart
        yp = np.isfinite(S["p"]); iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(np.exp(pred_tr[yp[tr]]), (S["p"] > 180)[tr & yp])
        xs_ = np.unique(np.round(np.exp(np.linspace(np.log(20), np.log(400), 60)), 1)); ys_ = iso.predict(xs_)
        clf["y180"] = dict(x=[float(v) for v in xs_], y=[round(float(v), 4) for v in ys_])
        models[str(k)] = dict(reg=_pack(reg, len(FEATURES)), sigma=round(sigma, 4), rq=tab, clf=clf, mu=[round(float(x), 5) for x in mu], sd=[round(float(x), 5) for x in sd])
        # ---- hold-out skill
        pred = _predict(reg, Xd[te]); y = S["y_ln"][te]
        persist = np.log(np.maximum(S["m0"][te], 1))
        clim = {}                                                    # month-by-state climatology of ln daily mean, from the training years
        key = (month[S["target_day"]] - 1) * n_states + S["state"]
        for kk in np.unique(key[tr]): clim[kk] = S["y_ln"][tr][key[tr] == kk].mean()
        cl = np.array([clim.get(kk, S["y_ln"][tr].mean()) for kk in key[te]])
        out = dict(n=int(te.sum()), rmse=round(_rmse(pred, y), 4), rmse_persistence=round(_rmse(persist, y), 4), rmse_climatology=round(_rmse(cl, y), 4))
        out["skill_vs_persistence"] = round(1 - out["rmse"] ** 2 / out["rmse_persistence"] ** 2, 4)
        out["skill_vs_climatology"] = round(1 - out["rmse"] ** 2 / out["rmse_climatology"] ** 2, 4)
        rows = np.array([_qrow(tab, float(np.exp(v))) for v in pred]); ix = lambda q: QS.index(q)
        out["coverage80"] = round(float(np.mean((y - pred >= rows[:, ix(0.1)]) & (y - pred <= rows[:, ix(0.9)]))), 3)
        out["coverage50"] = round(float(np.mean((y - pred >= rows[:, ix(0.25)]) & (y - pred <= rows[:, ix(0.75)]))), 3)
        out["rmse_median"] = round(_rmse(pred + rows[:, ix(0.5)], y), 4)
        for name, yy, base_rate_tr in (("y150", S["m"] > 150, None), ("y180", (S["p"] > 180), None)):
            msk = te & (np.isfinite(S["p"]) if name == "y180" else True)
            if name == "y150":
                if yy[msk].sum() < 5: continue
                p_ = prob_over(_predict(reg, Xd[msk]), 150.0, tab)
            else:
                if yy[msk].sum() < 5: continue
                p_ = np.interp(np.exp(_predict(reg, Xd[msk])), clf["y180"]["x"], clf["y180"]["y"])
            base = yy[tr & (np.isfinite(S["p"]) if name == "y180" else True)].mean()
            out[name] = dict(pos=int(yy[msk].sum()), n=int(msk.sum()), brier=round(float(brier_score_loss(yy[msk], p_)), 5), base=round(float(base), 5),
                             bss=round(float(1 - brier_score_loss(yy[msk], p_) / brier_score_loss(yy[msk], np.full(msk.sum(), base))), 4), auc=round(float(roc_auc_score(yy[msk], p_)), 4))
        skill[str(k)] = out
        progress(f"k={k}: n_test={out['n']} rmse={out['rmse']:.3f} (persist {out['rmse_persistence']:.3f}, clim {out['rmse_climatology']:.3f}) "
                 f"cov80 {out['coverage80']:.2f} cov50 {out['coverage50']:.2f}  skill vs clim {out['skill_vs_climatology']:+.2f}  y150 bss {out.get('y150', {}).get('bss')}  y180 bss {out.get('y180', {}).get('bss')}")
    # month-by-state climatology of ln daily mean (all years) for the "typical" reference line
    states_idx = np.asarray(area_state)
    clim_tbl = []
    for s in range(n_states):
        rows = np.where(states_idx == s)[0]
        clim_tbl.append([round(float(np.nanmean(np.log(M[rows][:, month == m])) if np.isfinite(M[rows][:, month == m]).any() else float("nan")), 4) for m in range(1, 13)])
    return days, M, P, models, skill, clim_tbl


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--archive", default="../booluckgmie/sharecode/data_apims/archiveAPI201707-20241103.parquet")
    ap.add_argument("--csv-dir", default="../booluckgmie/sharecode/data_apims"); ap.add_argument("--history-dir", default="data/history")
    ap.add_argument("--test-from", default="2025-07-01"); ap.add_argument("--model", default="docs/model.js")
    ap.add_argument("--out", default="docs/outlook.json"); ap.add_argument("--history-out", default="docs/history.json")
    a = ap.parse_args(argv)
    from .decisions import load_df
    df = load_df(a.archive, a.csv_dir, a.history_dir)
    m = json.loads(open(a.model, encoding="utf-8").read().split("=", 1)[1].rstrip().rstrip(";"))
    areas = [x["key"] for x in m["areas"]]; states = m["states"]; area_state = [states.index(x["state"]) for x in m["areas"]]
    days, M, P, models, skill, clim = train(df, areas, area_state, len(states), a.test_from)
    doc = dict(horizons=HORIZONS, features=FEATURES, states=states, models=models, skill=skill, climatology=clim, test_from=a.test_from,
               data_end=str(days[-1].date()), note="No weather forecast is used: skill falls with the horizon (see skill_vs_climatology).")
    json.dump(doc, open(a.out, "w", encoding="utf-8"), separators=(",", ":"))
    h = export_history_file(days, M, P, areas, a.history_out)
    import os
    print(f"wrote {a.out} ({os.path.getsize(a.out) // 1024} KB) and {a.history_out} ({os.path.getsize(a.history_out) // 1024} KB, {len(areas)} areas x {h['n']} days)")


if __name__ == "__main__":
    main()
