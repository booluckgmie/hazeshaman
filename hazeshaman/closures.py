"""Validate data/closures.csv (school closures / PdPR taken from news and official announcements) and export docs/closures.json.

    python -m hazeshaman.closures            # validate + write docs/closures.json
"""
from __future__ import annotations
import csv, datetime as dt, json, sys

COLS = ["date", "state", "area", "action", "pdpr", "schools", "students", "basis", "verified", "source_title", "source_url", "note"]
STATES = {"Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan", "Pahang", "Perak", "Perlis", "Pulau Pinang", "Sabah", "Sarawak",
          "Selangor", "Terengganu", "WP Kuala Lumpur", "WP Labuan", "WP Putrajaya"}
ENUM = {"action": {"closed", "planned"}, "pdpr": {"yes", "no", "unstated"}, "basis": {"effective", "announced"}, "verified": {"read", "summary"}}


def load(path: str = "data/closures.csv") -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    errs = []
    for i, r in enumerate(rows, start=2):
        try: dt.date.fromisoformat(r["date"])
        except ValueError: errs.append(f"line {i}: bad date {r['date']!r}")
        if r["state"] not in STATES: errs.append(f"line {i}: unknown state {r['state']!r}")
        for k, ok in ENUM.items():
            if r[k] not in ok: errs.append(f"line {i}: {k}={r[k]!r} not in {sorted(ok)}")
        if not r["source_url"].startswith("https://"): errs.append(f"line {i}: source_url must be https")
        for k in ("schools", "students"):
            if r[k] and not r[k].isdigit(): errs.append(f"line {i}: {k} must be a number")
    if errs: raise ValueError("closures.csv: " + "; ".join(errs))
    return rows


def export(src: str = "data/closures.csv", out: str = "docs/closures.json") -> int:
    rows = load(src)
    doc = {"rows": [{k: (int(r[k]) if k in ("schools", "students") and r[k] else r[k]) for k in COLS} for r in rows],
           "n": len(rows), "first": min(r["date"] for r in rows), "last": max(r["date"] for r in rows)}
    with open(out, "w", encoding="utf-8") as f: json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    return len(rows)


if __name__ == "__main__":
    n = export(); print(f"closures: {n} rows -> docs/closures.json")
