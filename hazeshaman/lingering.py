"""Does a "lingering haze" rule explain closures the KPM trigger does not?   python -m hazeshaman.lingering

KPM trigger (as announced, evening before D): any school-hours reading above 180, or daily means above 150 on three consecutive days.
Lingering rule tested here: at 17:00-18:00 on D-1 some station of the state is still at API >= 150 AND the state had a school-hours
reading >= 180 within the previous 7 days (the episode has not cleared). Thresholds are KPM's own numbers, nothing was fitted.
Weekdays only; "closed" = a recorded closure for that state-day (data/closures.csv, so undocumented district closures count as 'open').
"""
from __future__ import annotations
import argparse, csv, json
import numpy as np, pandas as pd
from . import decisions as D


def panel(df, closed, days, states):
    rows = []
    for d in days:
        p = d - pd.Timedelta(days=1)
        for s in states:
            x = df[(df.state == s) & (df.datetime <= p + pd.Timedelta(hours=18)) & (df.datetime > p - pd.Timedelta(days=7))]
            if x.empty: continue
            ev = x[(x.date == p) & x.h.between(17, 18)].groupby("area").api.mean().max()
            sch = x[x.h.between(6, 14)]
            pk1 = sch[sch.date == p].api.max(); pk7 = sch.api.max()
            dm = x.groupby(["area", "date"]).api.mean().unstack(0)
            m = dm.reindex([p - pd.Timedelta(days=k) for k in range(3)])
            rows.append(dict(date=d, state=s, closed=(str(d.date()), s) in closed, evening=ev, peak1=pk1, peak7=pk7,
                             b3=bool((m > 150).all(axis=0).any()), rise=bool(((m.iloc[0] / m.iloc[1]) > 1.15).any())))
    P = pd.DataFrame(rows)
    P["a180"] = P.peak1 > 180
    P["kpm"] = P.a180 | P.b3
    P["linger"] = (P.evening >= 150) & (P.peak7 >= 180)
    P["kpm_linger"] = P.kpm | P.linger
    return P


def score(P, col):
    m = P[col]; tp = int((m & P.closed).sum()); fp = int((m & ~P.closed).sum())
    return dict(rule=col, flagged=int(m.sum()), caught=tp, closed=int(P.closed.sum()), false=fp,
                precision=round(tp / max(int(m.sum()), 1), 2), recall=round(tp / max(int(P.closed.sum()), 1), 2))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--archive", default="../booluckgmie/sharecode/data_apims/archiveAPI201707-20241103.parquet")
    ap.add_argument("--csv-dir", default="../booluckgmie/sharecode/data_apims"); ap.add_argument("--history-dir", default="data/history")
    ap.add_argument("--closures", default="data/closures.csv"); ap.add_argument("--out", default="docs/lingering.json")
    ap.add_argument("--note", default="docs/analysis/08-lingering-haze.md")
    a = ap.parse_args(argv)
    df = D.load_df(a.archive, a.csv_dir, a.history_dir); df = df[df.api.notna()]
    cl = [r for r in csv.DictReader(open(a.closures, encoding="utf-8")) if r["action"] == "closed"]
    closed = {(r["date"], r["state"]) for r in cl}
    wk = lambda a_, b_: [d for d in pd.date_range(a_, b_) if d.weekday() < 5]
    sets = {"2026": (wk("2026-10-08", "2026-10-14"), sorted(df[df.date >= "2026-10-01"].state.unique())),
            "2019": (wk("2019-09-09", "2019-10-04"), sorted(df[df.date < "2020-01-01"].state.unique()))}
    res = {}
    for k, (days, states) in sets.items():
        P = panel(df, closed, days, states)
        res[k] = dict(n=len(P), closed=int(P.closed.sum()), scores=[score(P, c) for c in ("kpm", "linger", "kpm_linger")])
        if k == "2026":
            res["2026_missed"] = [dict(date=str(r.date.date()), state=r.state, evening=round(float(r.evening)), peak7=round(float(r.peak7)),
                                       caught_by_linger=bool(r.linger), rising=bool(r.rise)) for r in P[P.closed & ~P.kpm].itertuples()]
            res["2026_late"] = [score(P[P.date >= "2026-10-12"], c) for c in ("kpm", "linger", "kpm_linger")]
    json.dump(res, open(a.out, "w"), indent=1, default=str); write_note(res, a.note)
    print(json.dumps(res["2026"]["scores"]))


def _tbl(sc):
    nm = dict(kpm="KPM trigger", linger="Lingering rule alone", kpm_linger="KPM or lingering")
    return "\n".join(["| Rule | Flagged | Closures caught | False alarms | Precision | Recall |", "|---|---|---|---|---|---|"] +
                     [f"| {nm[s['rule']]} | {s['flagged']} | {s['caught']} of {s['closed']} | {s['false']} | {s['precision']:.0%} | {s['recall']:.0%} |" for s in sc])


def write_note(r, path):
    miss = r["2026_missed"]
    lines = "\n".join(f"| {m['date']} | {m['state']} | {m['evening']} | {m['peak7']} | {'yes' if m['caught_by_linger'] else 'no'} | {'yes' if m['rising'] else 'no'} |" for m in miss)
    open(path, "w", encoding="utf-8").write(f"""# 8. Does a "lingering haze" rule explain closures the KPM trigger misses?

**Question.** KPM's trigger (a school-hours reading above 180, or three straight days above 150) did not flag {len(miss)} of the {r['2026']['closed']} recorded closure state-days on weekdays in 8-14 Oct 2026.
Do slow clearing and rebounds after a bad spell explain them, and would a rule that remembers the episode have caught them?

## Rule tested
**Lingering:** at 17:00-18:00 the evening before, some station in the state is still at API 150 or more, and the state had a school-hours reading of 180 or more in the previous 7 days.
Both numbers are KPM's own; nothing was tuned. The idea is that an episode that has not cleared is not over because one afternoon dipped.

## Result, 8-14 Oct 2026 (weekdays, {r['2026']['n']} state-days, {r['2026']['closed']} with a recorded closure)
{_tbl(r['2026']['scores'])}

Last three school days only (12-14 Oct, after the first closures, when the trigger lagged):

{_tbl(r['2026_late'])}

## Closures the KPM trigger did not flag
| Date | State | API at 17-18h the evening before | Highest school-hours reading in previous 7 days | Caught by lingering rule | Day-before mean up 15%+ |
|---|---|---|---|---|---|
{lines}

Reading: {sum(m['rising'] for m in miss)} of the {len(miss)} misses had a day-before mean 15% or more above the day before that, so they are **rebounds** after the one-day dip on Sunday 11 Oct, not slow clearing; only a few (Negeri Sembilan on 14 Oct) were genuinely lingering. The lingering rule catches both kinds because it keys on "still at 150 or more and the episode has not ended", not on the shape of the decline. A pure "slow reduction" rule would have caught very few of these closures.

## Out-of-sample check, 9 Sep - 4 Oct 2019 (peninsula, trigger then 200)
{_tbl(r['2019']['scores'])}

Here the lingering rule flags far more state-days than were recorded as closed and precision drops. That is partly expected (the 2019 list is five days long and probably incomplete, and the line was 200, not 180), but it means **the rule is not validated**: it was chosen after seeing the misses in the same Oct 2026 window.

## What I would and would not claim
* Supported: closures in this episode were driven by "has the haze cleared?" as much as by the 180/150 numbers; a persistence term explains most of the misses.
* Not supported: that the lingering rule is the right policy, or that its thresholds are optimal. The sample is {r['2026']['n']} state-days in one episode, and the closure record only lists decisions found in news, so some "false alarms" may be real undocumented district closures.
* Next test: apply it to the next episode before looking at the outcome, and add the cost view (a false closure costs a school day; a miss costs exposure).

_Generated by `python -m hazeshaman.lingering`. Decision support only._
""")


if __name__ == "__main__": main()
