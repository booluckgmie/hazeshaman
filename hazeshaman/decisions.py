"""Compare recorded school-closure decisions (data/closures.csv) with the DOE hourly API they were made against.

    python -m hazeshaman.decisions [--archive P] [--csv-dir D] [--history-dir H] [--out docs/decisions.json]

For every state-day with a recorded closure it asks: was the KPM trigger actually met (on the day, and by the evening before when the
announcement is made)?  For the best documented episode (8-14 Oct 2026) it also lists days where the trigger was met but schools stayed open,
and how many school days each state waited between the trigger first being met and the first closure.

Trigger used (KPM, Oct 2026): any reading above 180, or readings above 150 on three consecutive days. Before 2026 the line was 200.
"Reading" = the highest hourly value at the matched stations during school hours (06:00-14:00); "three days above 150" uses each station's daily mean.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, json
import numpy as np, pandas as pd
from . import apims

TRIG_NEW, TRIG_OLD = 180, 200
SCHOOL_H = (6, 14)
EVENING_H = (17, 19)       # when the next-day decision is usually announced


def load_df(archive, csv_dir, hist_dir):
    asof = apims.now_myt(); fr = []
    if archive: fr.append(apims.load_archive(archive, asof, {}))
    if csv_dir: fr.append(apims.load_csv_dir(csv_dir, asof, {}))
    if hist_dir: fr.append(apims.load_history_dir(hist_dir, asof, {}))
    df = apims.merge(fr); df["date"] = df.datetime.dt.normalize(); df["h"] = df.datetime.dt.hour
    return df


def match_areas(df, state, area_text):
    """stations of the state whose name appears in the closure 'area' text; all of the state's stations when none match / 'All'."""
    st = df[df.state == state].area.unique()
    toks = [t.strip().lower() for part in area_text.replace("/", ",").replace(";", ",").split(",") for t in [part] if t.strip()]
    hit = [a for a in st if any(t and (t in a.split("|")[1].lower() or a.split("|")[1].lower() in t) for t in toks)]
    return (hit or list(st)), bool(hit)


def last_full_day(df):
    """newest date with readings up to 14:00, so a half-finished day is never scored"""
    return df[df.h >= SCHOOL_H[1]].date.max()


def day_stats(df, areas, day):
    d = pd.Timestamp(day); sub = df[df.area.isin(areas)]
    if d > last_full_day(df): return dict(peak=None, eve_peak=None, streak_known=False, streak_lenient=False, n_stations=len(areas), has_data=False)
    sch = sub[(sub.date == d) & sub.h.between(*SCHOOL_H)].api
    prev = d - pd.Timedelta(days=1)
    eve = sub[(sub.date == prev) & sub.h.between(*EVENING_H)].api
    dm = sub.groupby(["area", "date"]).api.mean().unstack(0)
    streak = [(dm.reindex([d - pd.Timedelta(days=k) for k in (1, 2, 3)]) > 150).all(axis=0).any()] if len(dm) else [False]
    streak_eve = bool((dm.reindex([prev - pd.Timedelta(days=k) for k in (0, 1, 2)]) > 150).all(axis=0).any()) if len(dm) else False
    pk = sub[sub.h.between(*SCHOOL_H)].groupby(["area", "date"]).api.max().unstack(0)
    lenient_eve = bool((pk.reindex([prev - pd.Timedelta(days=k) for k in (0, 1, 2)]) > 150).all(axis=0).any()) if len(pk) else False
    return dict(peak=float(sch.max()) if len(sch) else None, eve_peak=float(eve.max()) if len(eve) else None,
                streak_known=streak_eve, streak_lenient=lenient_eve, n_stations=len(areas), has_data=bool(len(sch)))


def classify(s, trig):
    if not s["has_data"]: return "no data"
    if s["peak"] >= trig and (s["eve_peak"] or 0) >= trig: return "met (day and evening before)"
    if s["peak"] >= trig: return "met on the day only"
    if (s["eve_peak"] or 0) >= trig or s["streak_known"]: return "met the evening before only"
    if s["peak"] >= 150: return "below trigger (150-180)"
    return "far below trigger (<150)"


def analyse(df, closures, students):
    rows = [r for r in closures if r["action"] == "closed"]
    byday = {}
    for r in rows: byday.setdefault((r["date"], r["state"]), []).append(r)
    items = []
    for (d, st), rs in sorted(byday.items()):
        areas, matched = set(), False
        for r in rs:
            a, m = match_areas(df, st, r["area"]); areas |= set(a); matched |= m
        trig = TRIG_NEW if d >= "2026-10-08" else TRIG_OLD
        s = day_stats(df, sorted(areas), d); s.update(date=d, state=st, areas=rs[0]["area"][:80], station_match=matched, trigger=trig,
                                                      verdict=classify(s, trig), verified=min(x["verified"] for x in rs), pdpr=("yes" if any(x["pdpr"] == "yes" for x in rs) else "unstated"))
        items.append(s)
    return items


def episode_check(df, closures, start="2026-10-05", end=None, documented_from="2026-10-08"):
    """Oct 2026: every state, every weekday. A state counts as closed if any district was (even one); stations are matched to the
    closed districts where names allow, otherwise the whole state is used. Days before `documented_from` are used only for timing:
    the record of closures before 8 Oct is thin (e.g. Batu Pahat, Johor, was closed from about 6-7 Oct but without a verified date)."""
    rows = {}
    for r in closures:
        if r["action"] == "closed": rows.setdefault((r["date"], r["state"]), []).append(r)
    days = [d.date().isoformat() for d in pd.date_range(start, end or last_full_day(df)) if d.weekday() < 5]
    out = []
    for st in sorted(df[df.date >= start].state.unique()):
        every = list(df[df.state == st].area.unique()); first_trigger = first_closed = None
        for d in days:
            rs = rows.get((d, st)); closed = rs is not None
            areas = every
            if closed:
                sel = set()
                for r in rs: sel |= set(match_areas(df, st, r["area"])[0])
                areas = sorted(sel)
            s = day_stats(df, areas, d)
            hard = (s["peak"] or 0) >= TRIG_NEW or (s["eve_peak"] or 0) >= TRIG_NEW
            met = hard or s["streak_known"]; met_len = hard or s["streak_known"] or s["streak_lenient"]
            out.append(dict(date=d, state=st, peak=s["peak"], eve_peak=s["eve_peak"], trigger_met=bool(met), trigger_met_lenient=bool(met_len),
                            closed=closed, documented=d >= documented_from))
    return out


def summarise(items, ep):
    from collections import Counter
    c = Counter(i["verdict"] for i in items)
    justified = sum(c[k] for k in ("met (day and evening before)", "met on the day only", "met the evening before only"))
    e = pd.DataFrame(ep); doc = e[e.documented]
    missed = doc[doc.trigger_met & ~doc.closed]; over = doc[doc.closed & ~doc.trigger_met]
    over_len = doc[doc.closed & ~doc.trigger_met_lenient]; missed_len = doc[doc.trigger_met_lenient & ~doc.closed]
    lag = []
    for st, g in e.groupby("state"):
        ft = g[g.trigger_met].date.min(); fc = g[g.closed].date.min()
        if pd.notna(ft): lag.append(dict(state=st, first_trigger=ft, first_closure=fc if pd.notna(fc) else None,
                                         school_days_late=int(np.busday_count(ft, fc)) if pd.notna(fc) else None))
    cols = ["date", "state", "peak", "eve_peak"]
    return dict(by_verdict=dict(c), evaluated=sum(v for k, v in c.items() if k != "no data"), justified=justified,
                state_days_documented=int(len(doc)), state_days_closed=int(doc.closed.sum()), state_days_trigger_met=int(doc.trigger_met.sum()),
                closed_and_met=int((doc.closed & doc.trigger_met).sum()), closed_and_met_lenient=int((doc.closed & doc.trigger_met_lenient).sum()),
                missed_lenient=len(missed_len), over_cautious_lenient=len(over_len), missed=missed[cols].round(0).to_dict("records"),
                over_cautious=over[cols].round(0).to_dict("records"), lag=lag)


def model_replay(df, closures, models_js="docs/model.js", H=18, cfn=8.0, start="2026-10-05", end=None):
    """Run the dashboard's own model (exported coefficients) on the evening of each day at hour H and compare with what was decided for the next day."""
    m = json.loads(open(models_js).read().split("=", 1)[1].rstrip().rstrip(";"))
    mod = m["models"][str(H)]; states = m["states"]
    b = m["backtest"][str(H)]; pos = b["pos"]; n = b["n"]
    cands = [{"t": 0, "fn": 0, "fp": n - pos}, *b["grid"], {"t": 1.01, "fn": pos, "fp": 0}]
    thr = min(cands, key=lambda c: (cfn * c["fn"] + c["fp"]) / (cfn * pos))["t"]
    thr = thr if 0 < thr <= 1 else 0.5
    sig = lambda z: 1 / (1 + np.exp(-z))
    def lin(fit, z, si): return fit["b"] + float(np.dot(fit["w"], z)) + fit["state"][si]
    closed = {(r["date"], r["state"]) for r in closures if r["action"] == "closed"}
    piv = df.pivot_table(index="datetime", columns="area", values="api"); dmean = piv.resample("D").mean()
    out = []
    for d in pd.date_range(start, last_full_day(df) - pd.Timedelta(days=1) if end is None else end):
        nxt = d + pd.Timedelta(days=1)
        if nxt.weekday() >= 5: continue
        per = {}
        for area in piv.columns:
            st = area.split("|")[0]
            if st not in states: continue
            def v(h):
                for dd in (0, -1, 1, -2, 2):
                    t = d + pd.Timedelta(hours=h + dd)
                    if t in piv.index and np.isfinite(piv.at[t, area]): return float(piv.at[t, area])
                return None
            now, am, noon, a3 = v(H), v(8), v(12), v(H - 3)
            prev = dmean.at[d - pd.Timedelta(days=1), area] if (d - pd.Timedelta(days=1)) in dmean.index else None
            if None in (now, am, noon, a3) or prev is None or not np.isfinite(prev): continue
            streak = 0
            for k in (1, 2, 3):
                x = dmean.at[d - pd.Timedelta(days=k), area] if (d - pd.Timedelta(days=k)) in dmean.index else np.nan
                if np.isfinite(x) and x > 150: streak += 1
                else: break
            doy = d.dayofyear; ang = 2 * np.pi * doy / 365.25
            x = np.array([np.log(now), np.log(am), np.log(noon), np.log(now) - np.log(a3), np.log(prev), streak, np.sin(ang), np.cos(ang)])
            z = np.clip((x - np.array(mod["mu"])) / np.array(mod["sd"]), -4, 4); si = states.index(st)
            y180 = sig(lin(mod["clf"]["y180"], z, si)); ym = sig(lin(mod["clf"]["ymean150"], z, si))
            avg3 = np.exp((x[0] + x[1] + x[2]) / 3); days_over = streak + (1 if avg3 > 150 else 0)
            per.setdefault(st, []).append(y180 + (1 - y180) * (ym if days_over >= 2 else 0))
        for st, ps in per.items():
            pk = df[(df.state == st) & (df.date == nxt) & df.h.between(*SCHOOL_H)].api
            out.append(dict(decision_evening=d.date().isoformat(), for_day=nxt.date().isoformat(), state=st, p_close=round(float(max(ps)), 3),
                            model_says_close=bool(max(ps) >= thr), authorities_closed=(nxt.date().isoformat(), st) in closed,
                            next_day_peak=float(pk.max()) if len(pk) else None, trigger_met_next_day=bool(len(pk) and pk.max() >= TRIG_NEW)))
    return dict(hour=H, threshold=round(float(thr), 3), cfn=cfn, rows=out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--archive", default="../booluckgmie/sharecode/data_apims/archiveAPI201707-20241103.parquet")
    ap.add_argument("--csv-dir", default="../booluckgmie/sharecode/data_apims"); ap.add_argument("--history-dir", default="data/history")
    ap.add_argument("--closures", default="data/closures.csv"); ap.add_argument("--out", default="docs/decisions.json")
    a = ap.parse_args(argv)
    df = load_df(a.archive, a.csv_dir, a.history_dir)
    with open(a.closures, newline="", encoding="utf-8") as f: cl = list(csv.DictReader(f))
    sch = json.load(open("data/schools/by_state.json")) if False else {}
    try:
        from . import schools
        sch = {k: v["students"] for k, v in schools.build()[0].items()}
    except Exception: pass
    items = analyse(df, cl, sch); ep = episode_check(df, cl); rp = model_replay(df, cl)
    res = dict(trigger=dict(new=TRIG_NEW, old=TRIG_OLD), items=items, episode=ep, summary=summarise(items, ep), replay=rp, data_end=str(df.datetime.max()))
    json.dump(res, open(a.out, "w"), default=lambda o: None if o != o else o, separators=(",", ":"))
    print(json.dumps(res["summary"], indent=1)[:4000])


if __name__ == "__main__":
    main()
