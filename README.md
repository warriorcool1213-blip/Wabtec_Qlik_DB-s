# Qlik Dashboard Monitor

## Files (put all of these in ONE folder)
`qlik_dashboard.py` · `data.py` · `config.py` · `style.py` · `run_pipeline.py` · `dashboard_status_pipeline0909_updated.py`
`Expected_sheet.xlsx` (written by the pipeline) · `Jobs_Corresponding_Developers.xlsx` (edited by you)

> The dashboard is **`qlik_dashboard.py`**. `Dashboard_qlik0930.py` is an identical duplicate - delete it so there is only one copy.

## Setup
```
pip install -r requirements.txt
```
Use **one** Python environment for everything (the same one for the scheduler and for Streamlit), and keep **one** copy of this folder.
The pipeline's default `live` mode drives a real Chrome window (Selenium), so run it on a Windows machine that has Chrome installed,
is logged in, and is on the network that can reach the Qlik AccessPoint / QMC servers.

### Credentials (do not hard-code them)
Set these once as permanent environment variables (Windows: `setx`, then open a new terminal):
```
setx QLIK_USERNAME "your.username"
setx QLIK_PASSWORD "your-password"
setx QLIK_SECURITY_ANSWER "your-security-answer"
```
`QMC_USERNAME` / `QMC_PASSWORD` default to the `QLIK_*` values; set them only if the QMC login differs.

## Run (two programs, two terminals / two services)
1. **Scheduler** (refreshes the data every 3 hours: 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00 IST):
```
python run_pipeline.py
```
   Keep it running (it prints nothing between runs - that is normal). On start it logs the hours it loaded, e.g.
   `Scheduler started. Runs at 00:00, 03:00, 06:00, ...` - check that line matches what you expect.
   To run the pipeline once right now (in a second terminal, without stopping the scheduler): `python run_pipeline.py --now`
2. **Dashboard**:
```
streamlit run qlik_dashboard.py
```
Open the URL it prints (default http://localhost:8501).

## Auto-refresh
- The open dashboard checks every **60 seconds** whether `Expected_sheet.xlsx` or `run_status.json` changed, and reloads itself if so.
- Sidebar: the **Auto-refresh** toggle must be ON; **Reload now** forces an immediate reload.

## Configure (config.py, or environment variables)
`DASHBOARD_XLSX`, `PIPELINE_MODE` (live/offline), `DASHBOARD_TZ`. (`DEV_JOBS_XLSX` and `DASHBOARD_REFRESH_SEC` only matter for the developer mapping - see below.)

## Changing the schedule
1. Edit `RUN_HOURS` in `config.py` - **the `config.py` in the folder you actually run from** (24-hour clock, hours only; every run is at minute 0).
2. Restart `run_pipeline.py` **and** the Streamlit app. A running process never re-reads `config.py`.
3. `STALE_AFTER_HOURS` (the sidebar's "data is old" warning) is derived from `RUN_HOURS` automatically - no need to edit it.

## Logs and run health
- `logs/scheduler.log` - one entry per run, with the last lines of the pipeline output.
- `logs/pipeline_YYYYMMDD_HHMMSS.log` - the full console output of each run (success or failure). They accumulate; delete old ones now and then.
- `run_status.json` - result of the last run (`ok`, duration, error, path to that run's log); shown in the dashboard sidebar.

## Jobs Corresponding Developers (not shown in the dashboard yet)
`data.py` can load `Jobs_Corresponding_Developers.xlsx` (columns `Name | Distribution Group | Developer's Names`) via `data.get_dev_jobs()`,
but the current `qlik_dashboard.py` has no tab that displays it.

## How data flows
pipeline -> `Expected_sheet.xlsx` (+ `run_status.json`) -> `qlik_dashboard.py` notices the new file (mtime/size) -> reloads -> redraws all tabs.
