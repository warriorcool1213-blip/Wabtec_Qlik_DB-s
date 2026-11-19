"""Qlik Dashboard Monitor — reads the workbook produced by
dashboard_status_pipeline0909_updated.py and presents every sheet as a
dedicated, color-coded tab.

Run:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
import data
from style import (badge, badge_html_col, color_for, empty_state, fmt_dt,
                    inject_css, render_pills)

st.set_page_config(page_title="Qlik Dashboard Monitor", page_icon="📊", layout="wide")
inject_css()
px.defaults.template = "plotly_white"

# ============================================================ auto-refresh
@st.fragment(run_every=config.REFRESH_SECONDS)
def _watch_for_new_data():
    """Runs every REFRESH_SECONDS (5 min) in the background; reruns the whole
    app the moment the pipeline writes a fresh workbook."""
    cur = data.signature()
    # _rerun_for guard: never request the same rerun twice, so a mismatch can
    # never turn into an endless rerun loop.
    if st.session_state.get("sig") not in (None, cur) and st.session_state.get("_rerun_for") != cur:
        st.session_state["_rerun_for"] = cur
        st.cache_data.clear()
        st.rerun(scope="app")


# ============================================================ load data
d, info = data.get_data()
# Signature of the exact file version just loaded (not a fresh stat), so a
# save landing mid-run is still detected on the next check.
st.session_state["sig"] = info["sig"] if info else data.signature()

# IMPORTANT: start the watcher only AFTER "sig" is recorded above. Calling it
# earlier made every rerun see "old sig != new file" and rerun again forever,
# so edits never appeared and Reload now seemed dead.
st.session_state.setdefault("autorefresh", True)
if st.session_state["autorefresh"]:
    _watch_for_new_data()

st.markdown('<p class="app-title">📊 Qlik Dashboard Monitor</p>', unsafe_allow_html=True)
st.markdown('<p class="app-sub">Live status across dashboards, alerts, shift timings and QMC jobs</p>',
            unsafe_allow_html=True)

if d is None:
    empty_state(f"No workbook found yet. Expected at `{config.DATA_FILE}` — "
                f"it will appear here automatically once the pipeline finishes its first run.")
    st.stop()

# ---- sidebar --------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Status")
    if info["sample"]:
        st.warning("Showing **sample data** — your pipeline hasn't written "
                    f"`{config.DATA_FILE.name}` yet.", icon="⚠️")

    freshest = max(info["as_of"], info["saved_at"])
    age_hours = (data.now_ist() - freshest).total_seconds() / 3600
    st.metric("Data as of", info["as_of"].strftime("%d %b, %I:%M %p"))
    st.caption(f"💾 Workbook file saved: {info['saved_at'].strftime('%d %b, %I:%M %p')}")
    if (info["saved_at"] - info["as_of"]).total_seconds() > 1800:
        st.warning("The workbook was saved more recently than its Summary "
                   "'Generated' time — the pipeline saved the file but did not "
                   "refresh the Summary sheet.", icon="⚠️")
    if age_hours > config.STALE_AFTER_HOURS:
        st.error(f"⏱️ {age_hours:.1f}h old — older than expected for the scheduled runs. "
                  "Check the scheduler.", icon="🚨")
    else:
        st.caption(f"🟢 Fresh — {age_hours:.1f}h ago")
    st.caption(f"📄 Reading: `{info['path']}`")
    st.caption(f"⏭️ Next scheduled run: **{data.next_run().strftime('%d %b, %I:%M %p')}**")

    run_status = data.read_run_status()
    if run_status:
        icon = "✅" if run_status.get("ok") else "❌"
        st.caption(f"{icon} Last pipeline run: {run_status.get('finished_at', '—')} "
                    f"({run_status.get('duration_sec', '?')}s)")
        if not run_status.get("ok"):
            with st.expander("Last run error"):
                st.code(run_status.get("error", "unknown error"))

    st.toggle(f"Auto-refresh (every {config.REFRESH_SECONDS // 60} min)", key="autorefresh")
    if st.button("🔄 Reload now", width='stretch'):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.header("🗺️ Navigate")
    st.caption("Overview · Dashboard Status · Alerts · Shift Timings · "
               "Job Monitor · Priority Jobs · Jobs Corresponding Developers")
    if d["missing"]:
        st.caption(f"Sheets not found in workbook: {', '.join(d['missing'])}")

# ============================================================ tabs
tab_overview, tab_status, tab_alerts, tab_shift, tab_jobs, tab_priority, tab_devs = st.tabs(
    ["🏠 Overview", "🖥️ Dashboard Status", "🚨 Alerts", "🕒 Shift Timings",
     "⚙️ Job Monitor", "⭐ Priority BI Jobs", "👨‍💻 Jobs Corresponding Developers"]
)

# ------------------------------------------------------------------ Overview
with tab_overview:
    s = d["summary"]
    kv = s["kv"]
    # DnA / BI counts come from the Dashboard_status sheet itself (Team column);
    # fall back to the Summary sheet's figures if that column is empty.
    team = d["status"]["Team"].astype(str).str.strip().str.casefold() if not d["status"].empty else pd.Series(dtype=str)
    n_dna = int((team == "dna").sum()) if len(team) else 0
    n_bi = int((team == "bi").sum()) if len(team) else 0
    if not (n_dna or n_bi):
        n_dna = kv.get("DnA Dashboards", "—")
        n_bi = kv.get("BI Dashboards", "—")

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Total Dashboards", kv.get("Total Dashboards", len(d["status"])))
    c2.metric("DnA Dashboards", n_dna)
    c3.metric("BI Dashboards", n_bi)
    c4.metric("Up to date", kv.get("Up To Date (Business Date = Today)", "—"))
    c5.metric("Stale (2+ days)", kv.get("Genuinely Stale (2+ days old)", "—"))
    c6.metric("Total Jobs", kv.get("Total Jobs", len(d["jobs"])))
    c7.metric("Open Alerts", len(d["alerts"]))

    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("QMC Job Status")
        js = s["job_status"]
        if js.empty:
            empty_state("No job-status summary in this workbook.")
        else:
            fig = go.Figure(go.Pie(
                labels=js["Status"], values=js["Count"], hole=0.55,
                marker_colors=[color_for(x) for x in js["Status"]], sort=False,
            ))
            fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10),
                               legend=dict(orientation="h", y=-0.1))
            st.plotly_chart(fig, width='stretch')
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Dashboard Status by Team")
        st_df = d["status"]
        if st_df.empty:
            empty_state("No dashboard-status data.")
        else:
            ct = st_df.groupby(["Team", "Status"]).size().reset_index(name="Count")
            fig = px.bar(ct, x="Team", y="Count", color="Status", barmode="stack",
                         color_discrete_map=color_for and {s_: color_for(s_) for s_ in ct["Status"].unique()})
            fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10),
                               legend=dict(orientation="h", y=-0.25))
            st.plotly_chart(fig, width='stretch')
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("⚠️ Needs attention")
    a1, a2 = st.columns(2)
    with a1:
        st.caption("Failed dashboards")
        if s["failed"].empty:
            st.success("No failed dashboards 🎉")
        else:
            st.dataframe(s["failed"], width='stretch', hide_index=True)
    with a2:
        st.caption(f"Stale dashboards ({len(s['stale'])})")
        if s["stale"].empty:
            st.success("Nothing stale 🎉")
        else:
            st.dataframe(s["stale"], width='stretch', hide_index=True, height=240)
    for note in s["notes"]:
        st.info(note, icon="📝")
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ Dashboard Status
def _color_status(frame: pd.DataFrame, col: str):
    """Colour the status cells (same palette as the old badges) on a st.dataframe."""
    def _c(v):
        return f"background-color: {color_for(v)}; color: white; font-weight: 600;"
    sty = frame.style
    apply_fn = getattr(sty, "map", None) or sty.applymap   # pandas >=2.1 / older
    return apply_fn(_c, subset=[col])


@st.dialog("QVW jobs behind this dashboard", width="large")
def show_qvw_jobs(dash_name: str, status: str, reason: str):
    """Popup opened when a dashboard row is clicked."""
    st.markdown(f"**{dash_name}**")
    st.markdown(badge(status), unsafe_allow_html=True)
    if reason and reason != "nan":
        st.caption(reason)
    qvw = d["qvw"][d["qvw"]["Dashboard"] == dash_name].copy()
    if qvw.empty:
        st.info("No individual QVW jobs listed for this dashboard.")
        return
    qvw["QVW Refresh (IST)"] = qvw["QVW Refresh (IST)"].map(fmt_dt)
    qvw = qvw.drop(columns="Dashboard").reset_index(drop=True)
    st.caption(f"{len(qvw)} QVW job(s)")
    st.dataframe(_color_status(qvw, "QVW Job Status"), width="stretch", hide_index=True)


with tab_status:
    df = d["status"]
    if df.empty:
        empty_state("`Dashboard_status` sheet is empty or missing.")
    else:
        f1, f2, f3, f4 = st.columns(4)
        teams = f1.multiselect("Team", sorted(df["Team"].unique()))
        statuses = f2.multiselect("Status", sorted(df["Status"].unique()))
        periods = f3.multiselect("Periodicity", sorted(df["Periodicity"].unique()))
        search = f4.text_input("Search dashboard name")

        view = df.copy()
        if teams:
            view = view[view["Team"].isin(teams)]
        if statuses:
            view = view[view["Status"].isin(statuses)]
        if periods:
            view = view[view["Periodicity"].isin(periods)]
        if search:
            view = view[view["Dashboard"].str.contains(search, case=False, na=False)]

        render_pills(df["Status"].value_counts().to_dict())
        st.caption(f"Showing {len(view)} of {len(df)} dashboards")

        show = view[["Dashboard", "Team", "Status", "Schedule (IST)", "Refresh Time (IST)",
                     "QVW Jobs", "Periodicity", "Business Date", "Validation Reason"]].copy()
        show["Refresh Time (IST)"] = show["Refresh Time (IST)"].map(fmt_dt)
        show["Business Date"] = show["Business Date"].map(lambda v: fmt_dt(v, "%d %b %Y"))
        show = show.reset_index(drop=True)
        st.caption("Tick the box at the start of a row to see the QVW jobs behind that dashboard.")
        event = st.dataframe(
            _color_status(show, "Status"),
            width="stretch", hide_index=True, height=560,
            on_select="rerun", selection_mode="single-row",
            column_config={
                "Dashboard": st.column_config.TextColumn(width="medium"),
                "QVW Jobs": st.column_config.NumberColumn(width="small"),
                "Validation Reason": st.column_config.TextColumn(width="large"),
            },
        )
        rows = event.selection.rows
        if rows and rows[0] < len(show):
            picked = show.iloc[rows[0]]
            # open the popup only when the selection CHANGED, so it does not
            # pop up again on every unrelated rerun (filters, auto-refresh...)
            if st.session_state.get("_qvw_popup_for") != picked["Dashboard"]:
                st.session_state["_qvw_popup_for"] = picked["Dashboard"]
                show_qvw_jobs(picked["Dashboard"], str(picked["Status"]), str(picked["Validation Reason"]))
        else:
            st.session_state["_qvw_popup_for"] = None

        with st.expander("🔍 Inspect QVW jobs behind a dashboard"):
            pick = st.selectbox("Dashboard", sorted(df["Dashboard"].unique()))
            qvw = d["qvw"][d["qvw"]["Dashboard"] == pick].copy()
            if qvw.empty:
                st.caption("No individual QVW jobs listed for this dashboard.")
            else:
                qvw["QVW Refresh (IST)"] = qvw["QVW Refresh (IST)"].map(fmt_dt)
                st.dataframe(qvw.drop(columns="Dashboard"), width='stretch', hide_index=True)
													 


# ------------------------------------------------------------------ Alerts
with tab_alerts:
    al = d["alerts"]
    if al.empty:
        st.success("No active alerts 🎉", icon="✅")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Alerts", len(al))
        c2.metric("High Severity", int((al["Severity"] == "High").sum()))
        c3.metric("Medium Severity", int((al["Severity"] == "Medium").sum()))
        c4.metric("Not Notified", int((al["Notified (Y/N)"] != "Y").sum()))

        fsev = st.multiselect("Severity", sorted(al["Severity"].unique()), key="al_sev")
        view = al[al["Severity"].isin(fsev)] if fsev else al

        left, right = st.columns([2, 1])
        with left:
            show = view[["Dashboard Name", "Severity", "Status", "Failure Reason",
                         "Owner", "Alert Timestamp", "Notified (Y/N)"]].copy()
            show["Alert Timestamp"] = show["Alert Timestamp"].map(fmt_dt)
            show["Severity"] = badge_html_col(show, "Severity")
            st.write(show.to_html(escape=False, index=False, classes="styled-table"),
                     unsafe_allow_html=True)
        with right:
            fig = px.pie(view, names="Severity", hole=0.5,
                         color="Severity", color_discrete_map={
                             k: color_for(k) for k in view["Severity"].unique()})
            fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, width='stretch')

# ------------------------------------------------------------------ Shift Timings
with tab_shift:
    sh = d["shifts"]
    if sh.empty:
        empty_state("`DB Timings` sheet is empty or missing.")
    else:
        shifts = [s for s in ["Morning", "Afternoon", "Night"] if s in sh["Shift"].unique()] \
            or sorted(sh["Shift"].unique())
        shift_tabs = st.tabs([f"🕘 {s}" for s in shifts])
        for name, stab in zip(shifts, shift_tabs):
            with stab:
                sub = sh[sh["Shift"] == name]
                counts = sub["Outcome"].value_counts().to_dict()
                render_pills(counts, ["Updated", "Not updated", "N/A"])
                cL, cR = st.columns([2, 1])
                with cL:
                    show = sub[["Dashboard", "Trigger", "Present Time", "Outcome"]].copy()
                    show["Present Time"] = show["Present Time"].map(fmt_dt)
                    show["Outcome"] = badge_html_col(show, "Outcome")
                    st.write(show.to_html(escape=False, index=False, classes="styled-table"),
                             unsafe_allow_html=True)
                with cR:
                    fig = px.pie(sub, names="Outcome", hole=0.5,
                                 color="Outcome", color_discrete_map={
                                     k: color_for(k) for k in sub["Outcome"].unique()})
                    fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
                    st.plotly_chart(fig, width='stretch')

# ------------------------------------------------------------------ Job Monitor
with tab_jobs:
    sub_names = ["All Jobs", "Disabled", "Waiting", "Running", "Failed"]
    keys = ["jobs", "disabled", "waiting", "running", "failed"]
    subtabs = st.tabs(sub_names)
    for name, key, stab in zip(sub_names, keys, subtabs):
        with stab:
            jdf = d[key]
            if jdf.empty:
                empty_state(f"No rows in the `{data.SHEET[key]}` sheet.")
                continue
            c1, c2, c3 = st.columns(3)
            c1.metric("Jobs", len(jdf))
            c2.metric("Projects", jdf["Project"].nunique())
            c3.metric("Distribution groups", (jdf["Distribution Group"] != "—").sum())

            if key == "jobs":
                fig = px.bar(jdf["Schedule Type"].value_counts().reset_index(),
                             x="Schedule Type", y="count", color="Schedule Type",
                             color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_layout(height=280, showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig, width='stretch')

            proj = st.multiselect("Project", sorted(jdf["Project"].unique()), key=f"proj_{key}")
            view = jdf[jdf["Project"].isin(proj)] if proj else jdf
            show = view[["Project", "Task", "Status", "Schedule Type", "Distribution Group",
                         "Last Execution"]].head(1000).copy()
            st.dataframe(show, width='stretch', hide_index=True, height=420)
            if len(view) > 1000:
                st.caption(f"Showing first 1,000 of {len(view)} rows — narrow with the Project filter.")

# ------------------------------------------------------------------ Priority BI Jobs
with tab_priority:
    pr = d["priority"]
    if pr.empty:
        empty_state("`Priority BI Jobs` sheet is empty or missing.")
    else:
        render_pills(pr["Status"].value_counts().to_dict())
        c1, c2 = st.columns([2, 1])
        with c1:
            show = pr.copy()
            show["Last Execution"] = show["Last Execution"].map(fmt_dt)
            show["Status"] = badge_html_col(show, "Status")
            st.write(show.to_html(escape=False, index=False, classes="styled-table"),
                     unsafe_allow_html=True)
        with c2:
            fig = px.pie(pr, names="Status", hole=0.5,
                         color="Status", color_discrete_map={k: color_for(k) for k in pr["Status"].unique()})
            fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, width='stretch')

# ------------------------------------------------------------------ Jobs Corresponding Developers
with tab_devs:
    dv = data.get_dev_jobs()
    if dv is None:
        empty_state(f"Put `{config.DEV_FILE.name}` in the app folder (`{config.DEV_FILE.parent}`) "
                    "with columns **Name | Distribution Group | Developer's Names**. It loads automatically.")
    elif "error" in dv:
        st.error(f"Could not read `{config.DEV_FILE.name}`: {dv['error']}")
    else:
        dj = dv["df"].copy()
        # attach live QMC status/last run (matched on the full job name) when available
        live = d["jobs"][["Name", "Status", "Last Run (ET)"]].drop_duplicates("Name") if not d["jobs"].empty else None
        if live is not None:
            dj = dj.merge(live.rename(columns={"Name": "Job"}), on="Job", how="left")
            dj["Status"] = dj["Status"].fillna("—")
        else:
            dj["Status"], dj["Last Run (ET)"] = "—", pd.NaT

        long = dj.explode("_devs").rename(columns={"_devs": "Developer"})
        long = long[long["Developer"].notna()]
        n_unassigned = int((dj["_devs"].map(len) == 0).sum())

        st.caption(f"Source: `{config.DEV_FILE.name}` · sheet “{dv['sheet']}” · saved "
                   f"{dv['mtime'].strftime('%d %b, %I:%M %p')} — edit the Excel and the dashboard reloads it automatically.")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Jobs in sheet", len(dj))
        m2.metric("Developers", long["Developer"].nunique())
        m3.metric("Jobs with developer", len(dj) - n_unassigned)
        m4.metric("Unassigned jobs", n_unassigned)

        c1, c2, c3 = st.columns([1, 3, 2])
        mode = c1.radio("Search by", ["Developer", "Job"], horizontal=True)
        q = c2.text_input("Search", placeholder="Type a developer name…" if mode == "Developer" else "Type part of a job name…")
        groups = sorted(dj["Distribution Group"].unique())
        grp = c3.multiselect("Distribution Group", groups)
        if grp:
            dj = dj[dj["Distribution Group"].isin(grp)]
            long = long[long["Distribution Group"].isin(grp)]

        def _tokens_match(series, text):
            toks = text.casefold().split()
            s_ = series.fillna("").astype(str).str.casefold()
            ok = pd.Series(True, index=series.index)
            for t in toks:
                ok &= s_.str.contains(t, regex=False)
            return ok

        job_cols = ["Job", "Project", "Distribution Group", "Status"]
        cfg = {"Job": st.column_config.TextColumn(width="large")}

        if mode == "Developer":
            if not q.strip():
                summ = (long.groupby("Developer")
                        .agg(Jobs=("Job", "nunique"),
                             BI=("Distribution Group", lambda x: (x == "BI").sum()),
                             DnA=("Distribution Group", lambda x: (x == "DnA").sum()))
                        .reset_index().sort_values("Jobs", ascending=False))
                if summ.empty:
                    st.info("No developers filled in yet — add names in the “Developer's Names” column "
                            "of the Excel (separate several with commas) and save.", icon="📝")
                else:
                    st.caption("All developers and how many jobs each owns — type a name above to see their jobs.")
                    st.dataframe(summ, width='stretch', hide_index=True, height=420)
            else:
                hit = long[_tokens_match(long["Developer"], q)]
                if hit.empty:
                    st.warning(f"No developer matching “{q}”.")
                else:
                    for name, grp_df in hit.groupby("Developer", sort=True):
                        with st.expander(f"👤 {name} — {grp_df['Job'].nunique()} job(s)", expanded=hit["Developer"].nunique() <= 3):
                            show = grp_df[job_cols + ["Last Run (ET)"]].copy()
                            show["Last Run (ET)"] = show["Last Run (ET)"].map(fmt_dt)
                            st.dataframe(show, width='stretch', hide_index=True,
                                         column_config=cfg, height=min(420, 40 + 35 * len(show)))
        else:
            if not q.strip():
                st.caption("Type part of a job / project name to see who developed it.")
            else:
                hit = dj[_tokens_match(dj["Job"], q)]
                if hit.empty:
                    st.warning(f"No job matching “{q}”.")
                else:
                    st.caption(f"{len(hit)} job(s) found")
                    show = hit[["Job", "Project", "Distribution Group", "Developer(s)", "Status", "Last Run (ET)"]].copy()
                    show["Last Run (ET)"] = show["Last Run (ET)"].map(fmt_dt)
                    st.dataframe(show, width='stretch', hide_index=True, column_config=cfg, height=460)

        if n_unassigned:
            with st.expander(f"Jobs with no developer assigned ({n_unassigned})"):
                st.dataframe(dj[dj["_devs"].map(len) == 0][["Job", "Project", "Distribution Group"]],
                             width='stretch', hide_index=True, column_config=cfg, height=320)

# ------------------------------------------------------------------ table styling (once, at bottom)
st.markdown("""
<style>
.styled-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.styled-table th { background:#F4F6FB; text-align:left; padding:8px 10px; border-bottom:2px solid #E7E9F3;}
.styled-table td { padding:7px 10px; border-bottom:1px solid #F0F1F6; }
.styled-table tr:hover td { background:#FAFBFF; }
</style>
""", unsafe_allow_html=True)