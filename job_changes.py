"""Detects QMC jobs that were ADDED or DELETED between two pipeline runs.

How it works
------------
* After every successful pipeline run, run_pipeline.py calls update().
* update() reads the "Jobs" sheet of the workbook, compares it with the job list
  saved after the previous run (qmc_jobs_snapshot.json) and appends every
  difference to qmc_job_changes.csv (one row per added / deleted job).
* The Streamlit Overview tab reads that CSV and shows the changes.

Run it by hand any time (e.g. to take the starting snapshot right now):
    python job_changes.py
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import pandas as pd

import config

log = logging.getLogger("job_changes")

JOBS_SHEET = "Jobs"
LOG_COLS = ["Detected At", "Change", "Task", "Project", "Distribution Group",
            "Status", "Schedule", "Job Name"]
_DISABLED = re.compile(r"\s*\(work disabled\)\s*$", re.I)


def job_key(name) -> str:
    """Identity of a job. The '(work disabled)' suffix is ignored so that
    disabling / re-enabling a job is NOT reported as a delete + add."""
    return re.sub(r"\s+", " ", _DISABLED.sub("", str(name))).strip().lower()


def split_name(name) -> tuple[str, str]:
    parts = [p for p in str(name).split("\\") if p]
    if parts and parts[0].upper().startswith("QDS@"):
        parts = parts[1:]
    project = parts[0] if len(parts) > 1 else "—"
    task = parts[-1] if parts else str(name)
    return project, task


def _now() -> pd.Timestamp:
    return pd.Timestamp.now(tz=config.TIMEZONE).tz_localize(None)


def read_jobs(xlsx: Path) -> dict[str, dict]:
    raw = pd.read_excel(xlsx, sheet_name=JOBS_SHEET, header=None, dtype=object, engine="openpyxl")
    if raw.empty:
        return {}
    hdr = next((i for i in range(min(15, len(raw))) if str(raw.iat[i, 0]).strip().lower() == "name"), 0)
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[hdr]]
    df = df[df["Name"].notna()]
    jobs: dict[str, dict] = {}
    for _, r in df.iterrows():
        name = _DISABLED.sub("", str(r["Name"])).strip()
        jobs[job_key(name)] = {
            "name": name,
            "group": str(r.get("Distribution Group") or "—"),
            "status": str(r.get("Status") or "—"),
            "schedule": str(r.get("Started/Scheduled") or "—"),
        }
    return jobs


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def update(xlsx: Path | None = None) -> dict:
    """Compare the workbook's Jobs sheet with the previous snapshot.
    Returns a small summary dict (also useful for logging)."""
    xlsx = Path(xlsx or config.DATA_FILE)
    snap_path, log_path = config.JOB_SNAPSHOT_FILE, config.JOB_CHANGES_FILE
    now = _now()
    stamp = now.strftime("%Y-%m-%d %H:%M")

    new = read_jobs(xlsx)
    if not new:
        return {"skipped": "no jobs found in the Jobs sheet - snapshot left untouched"}

    if not snap_path.exists():                       # very first run -> baseline only
        _write_json(snap_path, {"baseline_at": stamp, "taken_at": stamp, "count": len(new), "jobs": new})
        return {"baseline": True, "count": len(new)}

    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    old = snap.get("jobs", {})
    # Safety net: a half-finished scrape would otherwise look like hundreds of deletions
    # (and the same jobs would then be reported as "added" on the next good run).
    if old and len(new) < config.JOB_CHANGE_MIN_RATIO * len(old):
        return {"skipped": f"only {len(new)} jobs found vs {len(old)} last time - looks like a partial scrape; "
                           f"nothing logged, snapshot left untouched"}

    rows = []
    for change, keys, src in (("Added", new.keys() - old.keys(), new),
                              ("Deleted", old.keys() - new.keys(), old)):
        for k in sorted(keys):
            j = src[k]
            project, task = split_name(j["name"])
            rows.append({"Detected At": stamp, "Change": change, "Task": task, "Project": project,
                         "Distribution Group": j["group"], "Status": j["status"],
                         "Schedule": j["schedule"], "Job Name": j["name"]})
    if rows:
        pd.DataFrame(rows, columns=LOG_COLS).to_csv(
            log_path, mode="a", header=not log_path.exists(), index=False, encoding="utf-8")
    _write_json(snap_path, {"baseline_at": snap.get("baseline_at", stamp), "taken_at": stamp,
                            "count": len(new), "jobs": new})
    return {"added": sum(r["Change"] == "Added" for r in rows),
            "deleted": sum(r["Change"] == "Deleted" for r in rows), "count": len(new)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(update())
