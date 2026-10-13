"""Cross-check the DOE API against an independent source (Open-Meteo / CAMS) on a common AQI scale, and flag
doubtful ("insignificant") reports.

Comparator: A(t) = 24 h rolling mean of Open-Meteo's `us_aqi`. The Malaysian API is built on 24 h averages too, so
this is the like-for-like quantity. A per-station *quantile mapping* then expresses A on the DOE scale:
    E_s(t) = F_DOE,s^-1( F_A,s(A(t)) )          (fitted on hours where both exist, training period only)
Quantile mapping (not regression) keeps extremes: regression shrinks haze peaks towards the mean and would
call every real haze episode "inconsistent".

An expected range [lo, hi] around E_s comes from the empirical spread of log(DOE/E) on a hold-out period, so it is
wider where the sources genuinely disagree more (e.g. East Malaysia, coastal stations).

Flags (each with a severity and a plain reason):
  frozen      identical DOE value for >= FROZEN_H hours, or >= FROZEN_SOFT_H while Open-Meteo moved >= FROZEN_MOVE
  spike       one-hour jump far larger than the independent source and the 24 h-average nature of the index allow
  high / low  DOE above / below the expected range by a practical margin for >= RUN_H consecutive hours
  stale       no recent DOE reading (set at update time)
Decision-critical case: `high` while DOE >= 150 -> "unconfirmed closure-level reading".
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

KNOT_P = np.concatenate([np.linspace(0.01, 0.99, 50), [0.995, 0.999]])
BANDS = [0, 50, 100, 200, 300, 1e9]
FROZEN_H = 24         # identical hourly values for a full day (never seen in 4 yrs of good stations) ...
FROZEN_SOFT_H = 12    # ... or this long while the independent source moved by >= FROZEN_MOVE
FROZEN_MOVE = 25
RUN_H = 4             # sustained disagreement
MARGIN = 25           # API points: disagreement must also be practically large
BEYOND = 10           # and clearly outside the (99%) range, not just touching it
DECISION_LEVEL = 100  # 'unhealthy' and above: below this the band difference does not change any action
SPIKE_MIN = 45        # API points in one hour
HOLDOUT_FRAC = 0.30   # last 30% of overlapping hours used to measure spread (mapping fitted on the first 70%)


def aqi24(om: pd.DataFrame) -> pd.Series:
    return om["us_aqi"].rolling(24, min_periods=18).mean()


def fit_qm(a: pd.Series, y: pd.Series, min_n=800):
    """Quantile-mapping knots (x on the Open-Meteo AQI scale -> y on the DOE scale)."""
    j = pd.concat([a.rename("a"), y.rename("y")], axis=1).dropna()
    if len(j) < min_n:
        return None
    xk = np.quantile(j["a"], KNOT_P)
    yk = np.maximum.accumulate(np.quantile(j["y"], KNOT_P))
    xk, idx = np.unique(xk, return_index=True)
    return xk, yk[idx]


def apply_qm(a, xk, yk):
    a = np.asarray(a, dtype=float)
    out = np.interp(a, xk, yk)
    hi, lo = a > xk[-1], a < xk[0]
    out[hi] = yk[-1] + (a[hi] - xk[-1])          # beyond the fitted range: slope 1
    out[lo] = yk[0] + (a[lo] - xk[0])
    out[np.isnan(a)] = np.nan
    return np.clip(out, 1, 600)


def band(v):
    return int(np.digitize(v, BANDS[1:-1], right=True))


def fit_station(om: pd.DataFrame, doe: pd.Series):
    """-> dict(model, stats) or None. Mapping on the first 70% of overlapping hours, spread/stats on the last 30%."""
    a = aqi24(om.set_index("datetime") if "datetime" in om else om)
    j = pd.concat([a.rename("a"), doe.rename("y")], axis=1).dropna()
    if len(j) < 1500:
        return None
    cut = j.index[int(len(j) * (1 - HOLDOUT_FRAC))]
    qm = fit_qm(j.loc[j.index < cut, "a"], j.loc[j.index < cut, "y"])
    if qm is None:
        return None
    te = j.loc[j.index >= cut]
    e = pd.Series(apply_qm(te["a"].values, *qm), index=te.index)
    r = np.log(te["y"]) - np.log(e)
    mae = float(np.abs(te["y"] - e).mean())
    bd, be = np.digitize(te["y"], BANDS[1:-1], right=True), np.digitize(e, BANDS[1:-1], right=True)
    # refit on all overlapping hours for production use; keep the spread measured out-of-sample
    qm_all = fit_qm(j["a"], j["y"]) or qm
    stats = dict(
        n=int(len(j)), n_test=int(len(te)), first=str(j.index.min())[:10], last=str(j.index.max())[:10],
        corr=round(float(np.corrcoef(np.log(te["y"]), np.log(e.clip(lower=1)))[0, 1]), 3),
        mae=round(mae, 1), bias=round(float(r.median()), 3),
        same_band=round(float((bd == be).mean()), 3), within1=round(float((np.abs(bd - be) <= 1).mean()), 3),
        q_lo=round(float(r.quantile(0.025)), 3), q_hi=round(float(r.quantile(0.975)), 3),          # 95% range (shown)
        q_lo99=round(float(r.quantile(0.005)), 3), q_hi99=round(float(r.quantile(0.995)), 3),      # 99% range (used for flags)
        # high-end behaviour matters for closures: of hours with DOE >= 150, how many does the independent source place >= 100?
        corroborated_150=round(float(((te["y"] >= 150) & (e >= 100)).sum() / max((te["y"] >= 150).sum(), 1)), 3),
        n_150=int((te["y"] >= 150).sum()))
    return dict(model=qm_all, stats=stats)


def expected_range(e, q_lo, q_hi):
    e = np.asarray(e, dtype=float)
    return e * np.exp(q_lo), e * np.exp(q_hi)


def _runs(mask: np.ndarray, min_len: int):
    """[(start, end_inclusive)] of True runs of at least min_len."""
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            if j - i + 1 >= min_len:
                out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def detect(times, doe, e, lo, hi):
    """Flag events on aligned hourly arrays. Returns a list of dicts (times as 'YYYY-MM-DDTHH:MM')."""
    t = pd.DatetimeIndex(times)
    doe, e, lo, hi = (np.asarray(x, dtype=float) for x in (doe, e, lo, hi))
    ev = []
    fmt = lambda i: t[i].strftime("%Y-%m-%dT%H:%M")      # noqa: E731

    def add(kind, i, j, sev, msg):
        d, m = np.nanmean(doe[i:j + 1]), np.nanmean(e[i:j + 1])
        ev.append(dict(type=kind, severity=sev, start=fmt(i), end=fmt(j), hours=int(j - i + 1),
                       doe=round(float(d)), om=round(float(m)), msg=msg))

    # frozen: identical consecutive values (NaN breaks a run)
    same = np.zeros(len(doe), bool)
    same[1:] = (doe[1:] == doe[:-1]) & ~np.isnan(doe[1:])
    for i, j in _runs(same, FROZEN_SOFT_H - 1):
        n, moved = j - i + 2, float(np.nanmax(e[i - 1:j + 1]) - np.nanmin(e[i - 1:j + 1]))
        if n >= FROZEN_H or moved >= FROZEN_MOVE:
            add("frozen", i - 1, j, "warn", f"DOE reported exactly {doe[j]:.0f} for {n} hours in a row" + (f" while Open-Meteo moved {moved:.0f} points" if moved >= FROZEN_MOVE else "") + " (possible stuck sensor or repeated value)")
    # spike
    d1 = np.abs(np.diff(doe))
    for i in np.where((d1 >= np.maximum(SPIKE_MIN, 0.4 * np.nan_to_num(doe[:-1]))) & ~np.isnan(d1))[0]:
        if abs(e[i + 1] - e[i]) < 0.35 * d1[i]:
            add("spike", i + 1, i + 1, "warn", f"DOE jumped {doe[i]:.0f} -> {doe[i + 1]:.0f} in one hour while the independent source barely moved")
    # sustained, decision-relevant disagreement beyond the 99% expected range
    high = (doe > hi) & (doe - hi >= BEYOND) & (doe - e >= MARGIN) & (doe >= DECISION_LEVEL)
    low = (doe < lo) & (lo - doe >= BEYOND) & (e - doe >= MARGIN) & (e >= DECISION_LEVEL)
    for i, j in _runs(high, RUN_H):
        d, m, h = (np.nanmean(x[i:j + 1]) for x in (doe, e, hi))
        add("high", i, j, "critical" if d >= 150 else "warn",
            ("Unconfirmed closure-level reading: " if d >= 150 else "Unconfirmed high reading: ") + f"DOE {d:.0f} is above what Open-Meteo supports (≈{m:.0f}, up to {h:.0f})")
    for i, j in _runs(low, RUN_H):
        d, m = np.nanmean(doe[i:j + 1]), np.nanmean(e[i:j + 1])
        add("low", i, j, "critical" if (m >= 150 and d < 100) else "warn",
            f"DOE {d:.0f} is below what Open-Meteo supports (≈{m:.0f}): " + ("possible under-reporting during haze" if m >= 150 else "possible under-reporting or a very local effect"))
    return sorted(ev, key=lambda x: x["start"])


def grade(stats, flagged_share):
    """A / B / C reliability of a station against the independent source.

    A: agrees closely.  B: usable.  C: treat its readings with caution (any hard-fail below, or a weak score).
    Hard fails: large typical error, poor band agreement, poor correlation, many flagged hours, or high readings that the
    independent source almost never corroborates (only judged when there are >= 100 such hours).
    """
    if stats is None:
        return "?"
    hard = (stats["mae"] > 20 or stats["within1"] < 0.95 or stats["corr"] < 0.6 or flagged_share > 0.08
            or (stats["n_150"] >= 100 and stats["corroborated_150"] < 0.1))
    score = (stats["corr"] >= 0.75) + (stats["within1"] >= 0.98) + (stats["mae"] <= 12) + (flagged_share <= 0.03)
    return "C" if hard or score <= 1 else "A" if score >= 4 else "B"


def save_model(path, per_station):
    out = {k: dict(x=[round(float(v), 2) for v in m["model"][0]], y=[round(float(v), 2) for v in m["model"][1]], stats=m["stats"])
           for k, m in per_station.items()}
    Path(path).write_text(json.dumps(dict(version=1, comparator="24 h mean of Open-Meteo us_aqi, per-station quantile mapping", stations=out), separators=(",", ":")))


def load_model(path):
    d = json.loads(Path(path).read_text())
    return {k: dict(model=(np.array(v["x"]), np.array(v["y"])), stats=v["stats"]) for k, v in d["stations"].items()}


# ---------------------------------------------------------------- fit / update / CLI
def _key_path(cache_dir, key):
    return Path(cache_dir) / (key.replace("|", "__").replace(" ", "_") + ".csv.gz")


def fit_all(doe: pd.DataFrame, cache_dir="data/openmeteo", progress=print):
    """doe: long frame [datetime, area, api]. Fits every station that has a cached Open-Meteo history."""
    out = {}
    for key, g in doe.groupby("area"):
        path = _key_path(cache_dir, key)
        if not path.exists():
            continue
        om = pd.read_csv(path, parse_dates=["datetime"]).set_index("datetime")
        d = g.drop_duplicates("datetime").set_index("datetime")["api"]
        fit = fit_station(om, d)
        if fit is None:
            progress(f"skip {key}: not enough overlap"); continue
        a = aqi24(om); e = pd.Series(apply_qm(a.values, *fit["model"]), index=a.index)
        lo, hi = expected_range(e.values, fit["stats"]["q_lo99"], fit["stats"]["q_hi99"])
        dd = d.reindex(a.index); m = (dd.notna() & e.notna()).values
        ev = detect(a.index[m], dd.values[m], e.values[m], lo[m], hi[m])
        yrs = max(m.sum() / 8766, 0.1)
        st = fit["stats"]
        st["events_per_year"] = {k: round(sum(1 for x in ev if x["type"] == k) / yrs, 1) for k in ("frozen", "spike", "high", "low")}
        st["flag_share"] = round(sum(x["hours"] for x in ev if x["type"] in ("high", "low", "frozen")) / max(m.sum(), 1), 4)
        st["grade"] = grade(st, st["flag_share"])
        out[key] = fit
        progress(f"{key:34s} corr={st['corr']:.2f} mae={st['mae']:5.1f} within1={st['within1']:.3f} corr150={st['corroborated_150']:.2f} flag_share={st['flag_share']:.3f} grade={st['grade']}")
    return out


def update(live_path="docs/live.json", model_path="data/xcheck_model.json", out="docs/xcheck.json", om_frames=None):
    """Hourly: fetch the latest Open-Meteo window, express it on the DOE scale, flag doubtful reports in the live buffer."""
    from . import openmeteo
    live = json.loads(Path(live_path).read_text())
    model = load_model(model_path)
    end = pd.Timestamp(live["end"]); n = live["hours"]
    idx = pd.date_range(end=end, periods=n, freq="h")
    keys = [k for k in live["areas"] if k in model and k in live["stations"]]
    if om_frames is None:
        om_frames = openmeteo.fetch_many([(k, live["stations"][k]["lat"], live["stations"][k]["lon"]) for k in keys], past_days=7)
    stations, flags = {}, []
    for k in keys:
        om = om_frames.get(k)
        if om is None or om.empty:
            continue
        om = om.set_index("datetime")
        a = aqi24(om).reindex(idx)
        m, st = model[k]["model"], model[k]["stats"]
        e = apply_qm(a.values, *m)
        lo, hi = expected_range(e, st["q_lo"], st["q_hi"])               # 95% range, drawn on the chart
        lo99, hi99 = expected_range(e, st["q_lo99"], st["q_hi99"])       # 99% range, used for flags
        doe = np.array([np.nan if v is None else v for v in live["areas"][k]], dtype=float)
        ok = ~np.isnan(doe) & ~np.isnan(e)
        ev = detect(idx[ok], doe[ok], e[ok], lo99[ok], hi99[ok]) if ok.any() else []
        last = np.where(~np.isnan(doe))[0]
        if len(last) and (n - 1 - last[-1]) >= 3:
            ev.append(dict(type="stale", severity="warn", start=str(idx[last[-1]])[:16].replace(" ", "T"), end=str(idx[-1])[:16].replace(" ", "T"),
                           hours=int(n - 1 - last[-1]), doe=int(doe[last[-1]]), om=None,
                           msg=f"No DOE reading for {n - 1 - last[-1]} hours (last {doe[last[-1]]:.0f})"))
        r = lambda x: [None if np.isnan(v) else int(round(v)) for v in x]            # noqa: E731
        label = live["stations"][k]["label"]; state = k.split("|")[0]
        for x in ev:
            flags.append(dict(key=k, state=state, name=label, **x))
        stations[k] = dict(grade=st["grade"], stats={q: st[q] for q in ("corr", "mae", "within1", "same_band", "corroborated_150", "n_150", "first", "last", "events_per_year")},
                           om=r(e), lo=r(lo), hi=r(hi), n_flags=len(ev))
    flags.sort(key=lambda x: (x["severity"] != "critical", x["end"]), reverse=False)
    doc = dict(generated=pd.Timestamp.now('UTC').strftime("%Y-%m-%dT%H:%MZ"), end=live["end"], hours=n,
               source="Open-Meteo Air Quality API (CAMS global), CC BY 4.0", comparator=model and "24 h mean of us_aqi, quantile-mapped to the DOE scale",
               stations=stations, flags=flags,
               summary=dict(stations=len(stations), flagged=len({f["key"] for f in flags}), critical=sum(f["severity"] == "critical" for f in flags),
                            by_type={t: sum(f["type"] == t for f in flags) for t in ("high", "low", "frozen", "spike", "stale")}))
    Path(out).write_text(json.dumps(doc, separators=(",", ":")))
    return doc


def main(argv=None):
    import argparse

    from . import apims
    ap = argparse.ArgumentParser(description="fit: calibrate Open-Meteo to the DOE scale per station; update: hourly cross-check")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit"); f.add_argument("--archive"); f.add_argument("--csv-dir"); f.add_argument("--history-dir", default="data/history")
    f.add_argument("--cache", default="data/openmeteo"); f.add_argument("--out", default="data/xcheck_model.json")
    u = sub.add_parser("update"); u.add_argument("--live", default="docs/live.json"); u.add_argument("--model", default="data/xcheck_model.json"); u.add_argument("--out", default="docs/xcheck.json")
    a = ap.parse_args(argv)
    if a.cmd == "fit":
        as_of = apims.now_myt(); frames = []
        if a.archive:
            frames.append(apims.load_archive(a.archive, as_of))
        if a.csv_dir:
            frames.append(apims.load_csv_dir(a.csv_dir, as_of))
        if a.history_dir and Path(a.history_dir).exists():
            frames.append(apims.load_history_dir(a.history_dir, as_of))
        doe = apims.merge(frames)
        doe = doe[doe.datetime >= "2022-08-01"]
        res = fit_all(doe, a.cache)
        save_model(a.out, res)
        print(f"wrote {a.out}: {len(res)} stations; grades " + str(pd.Series([r['stats']['grade'] for r in res.values()]).value_counts().to_dict()))
    else:
        d = update(a.live, a.model, a.out)
        print(f"xcheck: {d['summary']} -> {a.out}")


if __name__ == "__main__":
    main()
