"""Train per-announcement-hour logistic + log-linear models and a backtest summary."""
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, roc_auc_score

from .features import ANNOUNCE_HOURS, FEATURES, build, close_prob, close_truth

CLASSIFIERS = ["y100", "y150", "y180", "ymean150"]
THRESH = [round(t, 2) for t in np.arange(0.05, 0.96, 0.05)]


def _design(X, s_idx, n_states, mu, sd):
    Z = (X - mu) / sd
    oh = np.zeros((len(X), n_states))
    oh[np.arange(len(X)), s_idx] = 1
    return np.hstack([Z, oh])


def _fit(Xd, y, n_feat, cls_kind):
    if cls_kind == "clf":
        if y.sum() < 5 or (~y).sum() < 5:
            return None
        m = LogisticRegression(C=1.0, max_iter=500).fit(Xd, y)
        return m.intercept_[0], m.coef_[0]
    m = Ridge(alpha=1.0).fit(Xd, y)
    return m.intercept_, m.coef_


def _pack(res, n_feat):
    if res is None:
        return None
    b, w = res
    return dict(b=float(b), w=[round(float(x), 5) for x in w[:n_feat]],
                state=[round(float(x), 5) for x in w[n_feat:]])


def _predict(res, Xd):
    b, w = res
    z = Xd @ w + b
    return z


def train_all(cube, days, states, test_from, progress=print):
    n_s = len(states)
    nf = len(FEATURES)
    day_year = days.year.values
    models, backtest = {}, {}
    for H in ANNOUNCE_HOURS:
        X, ex, T, s_idx, d_idx = build(cube, days, H)
        test = days[d_idx] >= np.datetime64(test_from)
        mu, sd = X[~test].mean(0), X[~test].std(0) + 1e-9
        Xd = _design(X, s_idx, n_s, mu, sd)
        fitted_tr, fitted_all = {}, {}
        for name in CLASSIFIERS:
            fitted_tr[name] = _fit(Xd[~test], T[name][~test], nf, "clf")
            fitted_all[name] = _fit(Xd, T[name], nf, "clf")
        reg_tr = _fit(Xd[~test], T["l7"][~test], nf, "reg")
        reg_all = _fit(Xd, T["l7"], nf, "reg")
        resid = T["l7"][~test] - _predict(reg_tr, Xd[~test])
        sig = float(resid.std())
        # ---- backtest on held-out period
        def prob(fit, mask):
            return 1 / (1 + np.exp(-_predict(fit, Xd[mask])))
        p180 = prob(fitted_tr["y180"], test)
        pm = prob(fitted_tr["ymean150"], test)
        pc = close_prob(p180, pm, ex["days_over"][test])
        yc = close_truth(T, ex)[test]
        metrics = {}
        for name in CLASSIFIERS:
            p, y = prob(fitted_tr[name], test), T[name][test]
            metrics[name] = dict(
                auc=float(roc_auc_score(y, p)), brier=float(brier_score_loss(y, p)), base=float(y.mean()))
        metrics["close"] = dict(auc=float(roc_auc_score(yc, pc)), brier=float(brier_score_loss(yc, pc)),
                                base=float(yc.mean()))
        rmse = float(np.sqrt(np.mean((T["l7"][test] - _predict(reg_tr, Xd[test])) ** 2)))
        metrics["l7_rmse"] = rmse
        grid = [dict(t=t, fn=int(((pc < t) & yc).sum()), fp=int(((pc >= t) & ~yc).sum())) for t in THRESH]
        backtest[H] = dict(n=int(test.sum()), pos=int(yc.sum()), grid=grid, metrics=metrics)
        # reliability bins for close prob
        bins = np.linspace(0, 1, 11)
        rel = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            m = (pc >= lo) & (pc < hi + (hi == 1))
            if m.sum() >= 20:
                rel.append(dict(p=float(pc[m].mean()), f=float(yc[m].mean()), n=int(m.sum())))
        backtest[H]["rel"] = rel
        models[H] = dict(
            mu=[round(float(x), 5) for x in mu], sd=[round(float(x), 5) for x in sd],
            clf={k: _pack(v, nf) for k, v in fitted_all.items()},
            reg=_pack(reg_all, nf), sigma=round(sig, 4))
        progress(f"H={H:02d} n_test={test.sum():6d} close_base={yc.mean():.4f} "
                 f"AUC(close)={metrics['close']['auc']:.3f} Brier={metrics['close']['brier']:.4f} "
                 f"AUC(y150)={metrics['y150']['auc']:.3f}")
    return models, backtest
