#!/usr/bin/env python3
"""Load supplied 2026 research archive into the *raw inputs* expected by R.

Example (data stays Git-ignored):
    python scripts/import_project_archive.py --archive ~/Downloads/data.zip --period 2018-2019

This importer is deliberately strict: it preserves the provided identifiers and
full daily counts, never fabricates missing visits, and creates an audit trail.
"""
from __future__ import annotations
import argparse
import io
import json
import zipfile
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = {
    "2018-2019": (
        "data/extension_20261022/processed/research/attention_complete_sample.csv",
        "data/extension_20261022/processed/wikipedia/event_panel.csv",
    ),
    "2015-2017": (
        "data/processed/research/attention_complete_sample.csv",
        "data/processed/wikipedia/event_panel.csv",
    ),
}


def load_archive(path: Path, period: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    with zipfile.ZipFile(path) as arc:
        paths = MEMBERS[period]
        missing = set(paths) - set(arc.namelist())
        if missing:
            raise ValueError("Archive does not contain the expected research inputs: " + ", ".join(sorted(missing)))
        frames = [pd.read_csv(io.BytesIO(arc.read(m)), dtype={"reviewid": "string"}, low_memory=False) for m in paths]
    reviews, daily = frames
    essential = ("reviewid", "score", "pub_date", "artist")
    essential_panel = ("reviewid", "event_day", "date", "views", "observed")
    for col in essential:
        if col not in reviews: raise ValueError(f"Missing event column {col} in {period}")
    for col in essential_panel:
        if col not in daily: raise ValueError(f"Missing daily column {col} in {period}")
    if reviews.reviewid.duplicated().any(): raise ValueError("Duplicate reviewid in event table")
    if daily.duplicated(["reviewid", "event_day"]).any(): raise ValueError("Duplicate event/day in daily panel")
    reviews = reviews.copy()
    daily = daily.copy()
    daily.event_day = pd.to_numeric(daily.event_day, errors="raise").astype(int)
    daily.views = pd.to_numeric(daily.views, errors="coerce")
    daily.observed = pd.to_numeric(daily.observed, errors="coerce")
    daily["date"] = pd.to_datetime(daily["date"], errors="raise").dt.strftime("%Y-%m-%d")
    reviews["pub_date"] = pd.to_datetime(reviews["pub_date"], errors="raise").dt.strftime("%Y-%m-%d")
    window = set(range(-56,57))
    group = daily.groupby("reviewid", dropna=False)
    complete = {str(rid): (len(g) == 113 and set(g.event_day) == window
                            and g.views.notna().all() and g.observed.eq(1).all()
                            and g.views.ge(0).all()) for rid,g in group}
    ids = set(reviews.reviewid.dropna().astype(str))
    panel_ids = set(daily.reviewid.dropna().astype(str))
    # The unfiltered API event panel intentionally retains non-complete pilot events.
    # Keep only the already-adjudicated complete event cohort; preserve extra-ID count in audit.
    extra_api_events = len(panel_ids - ids)
    daily = daily[daily.reviewid.astype(str).isin(ids)].copy()
    group = daily.groupby("reviewid", dropna=False)
    complete = {str(rid): (len(g) == 113 and set(g.event_day) == window
                            and g.views.notna().all() and g.observed.eq(1).all()
                            and g.views.ge(0).all()) for rid,g in group}
    if not all(complete.values()): raise ValueError("Some selected research events have incomplete windows")
    if len(ids) != len(complete): raise ValueError("Some selected research events have no daily panel")
    year = pd.to_datetime(reviews.pub_date).dt.year
    expected = (year.ge(2018) & year.le(2019)) if period == "2018-2019" else (year.ge(2015) & year.le(2017))
    if not bool(expected.all()): raise ValueError("Review dates do not match selected cohort")
    meta = {"cohort": period, "source_zip": path.name,
            "source_reviews_member": MEMBERS[period][0], "source_panel_member": MEMBERS[period][1],
            "n_reviews": len(reviews), "n_daily": len(daily), "extra_api_events_excluded": extra_api_events,
            "n_pages_by_title": int(reviews.wiki_wikipedia_title.nunique()) if "wiki_wikipedia_title" in reviews else None,
            "all_windows_complete": True}
    return reviews, daily, meta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--period", choices=tuple(MEMBERS), default="2018-2019")
    p.add_argument("--out-dir", type=Path, default=ROOT / "data" / "processed")
    a = p.parse_args()
    reviews, daily, audit = load_archive(a.archive.expanduser(), a.period)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    reviews.to_csv(a.out_dir / "attention_complete_sample.csv", index=False)
    daily.to_csv(a.out_dir / "pageview_panel.csv", index=False)
    (a.out_dir / "archive_import_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    print("R input paths: data/processed/attention_complete_sample.csv and pageview_panel.csv")

if __name__ == "__main__": main()
