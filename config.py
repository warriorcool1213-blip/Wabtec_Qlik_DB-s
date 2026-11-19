"""Central settings - edit here (or override with environment variables)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Workbook produced by your pipeline (the same file you pass as --excel).
DATA_FILE = Path(os.getenv("DASHBOARD_XLSX", BASE_DIR / "Expected_sheet.xlsx"))
# Shown (with a banner) only when DATA_FILE does not exist yet.
SAMPLE_FILE = BASE_DIR / "sample_data" / "Sample_Output_Dashboard_Alerts.xlsx"

# Developer mapping workbook (Name | Distribution Group | Developer's Names).
# Keep it next to the code; edit & save it any time - the dashboard picks it up.
DEV_FILE = Path(os.getenv("DEV_JOBS_XLSX", BASE_DIR / "Jobs_Corresponding_Developers.xlsx"))

# Pipeline runner
PIPELINE_SCRIPT = Path(os.getenv("PIPELINE_SCRIPT", BASE_DIR / "dashboard_status_pipeline0909_updated.py"))
PIPELINE_MODE = os.getenv("PIPELINE_MODE", "live")        # "live" (scrape) or "offline"
PIPELINE_TIMEOUT_MIN = int(os.getenv("PIPELINE_TIMEOUT_MIN", "90"))

# Schedule: the pipeline runs at the top of each of these hours (24h clock), in TIMEZONE below.
# Currently every 3 hours: 12 AM, 3 AM, 6 AM, 9 AM, 12 PM, 3 PM, 6 PM, 9 PM.
# After editing, restart BOTH run_pipeline.py and the Streamlit app.
RUN_HOURS = (0, 3, 6, 9, 12, 15, 18, 21)
TIMEZONE = os.getenv("DASHBOARD_TZ", "Asia/Kolkata")

# Written by run_pipeline.py, shown in the dashboard sidebar
STATUS_FILE = DATA_FILE.with_name("run_status.json")
LOG_DIR = BASE_DIR / "logs"

def _longest_gap_hours(hours) -> int:
    """Longest wait between two consecutive runs (wraps past midnight)."""
    hs = sorted(set(hours))
    return max(((hs[(i + 1) % len(hs)] - h) % 24) or 24 for i, h in enumerate(hs))


# Longest wait between two scheduled runs, derived from RUN_HOURS (3 for every-3-hours).
MAX_RUN_GAP_HOURS = _longest_gap_hours(RUN_HOURS)

# Data older than this (hours) is flagged as "stale" in the sidebar:
# the longest gap between runs + 1h of slack, so it follows the schedule automatically.
STALE_AFTER_HOURS = MAX_RUN_GAP_HOURS + 1

# How often the open dashboard checks for a new workbook (seconds). 300 = 5 min.
REFRESH_SECONDS = int(os.getenv("DASHBOARD_REFRESH_SEC", "300"))

# ---- QMC job-change tracking (jobs ADDED / DELETED between pipeline runs) ----
JOB_SNAPSHOT_FILE = DATA_FILE.with_name("qmc_jobs_snapshot.json")   # job list seen on the last run
JOB_CHANGES_FILE = DATA_FILE.with_name("qmc_job_changes.csv")      # running log of added / deleted jobs
# A run that finds fewer than this share of the previous job count is treated as a
# partial / failed scrape: nothing is logged and the snapshot is left untouched.
JOB_CHANGE_MIN_RATIO = float(os.getenv("JOB_CHANGE_MIN_RATIO", "0.8"))
