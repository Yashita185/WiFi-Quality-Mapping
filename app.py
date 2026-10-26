from pathlib import Path
from datetime import datetime
import subprocess, platform, re, io
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from analysis_core import clean_measurements, summarize_locations, classify_signal, idw_grid

st.set_page_config(page_title="Wi-Fi Quality Mapping", page_icon="📶", layout="wide", initial_sidebar_state="expanded")
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CSV = DATA / "wifi_measurements.csv"
DATA.mkdir(exist_ok=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root{--bg:#070d18;--panel:#101a2b;--panel2:#142238;--ink:#edf4ff;--muted:#9aabc4;--teal:#55e0d0;--line:#263650;}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;color:var(--ink)}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:#070d18;color:var(--ink)}
[data-testid="stHeader"]{background:rgba(7,13,24,.92)}
[data-testid="stSidebar"],section[data-testid="stSidebar"]>div{background:#0b1423;color:var(--ink);border-right:1px solid #1f3049}
.block-container{padding-top:1.35rem;padding-bottom:2.4rem;max-width:1600px}
h1,h2,h3,h4,p,li,label,.stMarkdown{color:var(--ink)}
small,.stCaption,[data-testid="stCaptionContainer"]{color:#9aabc4!important}
.hero{background:radial-gradient(circle at 85% 10%,#155e75 0%,transparent 33%),linear-gradient(120deg,#111a2d 0%,#132b45 55%,#075b63 100%);border:1px solid #29415c;border-radius:22px;padding:30px 34px;color:#fff;margin-bottom:20px;position:relative;overflow:hidden;box-shadow:0 18px 50px #0005}
.hero h1{color:white;font-size:2.15rem;margin:0 0 8px 0;letter-spacing:-.04em}.hero p{color:#c4d8ed;margin:0;font-size:1rem;max-width:850px}
.eyebrow{font-size:.72rem;text-transform:uppercase;letter-spacing:.16em;font-weight:700;color:#72f1df;margin-bottom:8px}
.pill{display:inline-block;border:1px solid #5b8295;border-radius:99px;padding:6px 11px;margin-top:18px;font-size:.78rem;color:#e6f5f8;background:#ffffff08}
.section-kicker{font-size:.75rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#63dfd0;margin-bottom:4px}
[data-testid="stMetric"]{background:linear-gradient(145deg,#111d30,#0d1727);border:1px solid #263850;border-radius:15px;padding:15px 16px;box-shadow:0 8px 22px #0002}
[data-testid="stMetricLabel"]{color:#a8bad1;font-weight:600}[data-testid="stMetricValue"]{color:#f2f7ff;font-family:'Space Grotesk',sans-serif}[data-testid="stMetricDelta"]{color:#63dfd0}
[data-testid="stTabs"]{background:transparent}[data-testid="stTabs"] button{font-weight:600;color:#9eafc7}[data-testid="stTabs"] button[aria-selected="true"]{color:#72f1df;border-bottom-color:#55e0d0}
[data-testid="stDataFrame"]{border:1px solid #263850;border-radius:12px;overflow:hidden}
.note{background:#102638;border:1px solid #245064;border-left:3px solid #55e0d0;padding:13px 15px;border-radius:8px;color:#d6e8f6;font-size:.9rem;line-height:1.55}
.guide-card{background:linear-gradient(120deg,#101d30,#102637);border:1px solid #29415b;border-radius:14px;padding:16px 18px;margin:10px 0 18px;color:#dce9f7;line-height:1.6}
.guide-card b{color:#73e9da}.mini-label{color:#8ea5c1;text-transform:uppercase;letter-spacing:.1em;font-size:.68rem;font-weight:700}
div[data-testid="stExpander"]{border:1px solid #263850;border-radius:12px;background:#0c1626}
div[data-testid="stExpander"] summary{color:#e8f1ff}
.stButton>button,.stDownloadButton>button{border-radius:9px;border:1px solid #35516c;background:#14283e;color:#eaf6ff;font-weight:600}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{background:#0e766f;border-color:#1ca99e;color:white}
.stTextInput input,.stNumberInput input,.stSelectbox div[data-baseweb="select"],.stMultiSelect div[data-baseweb="select"],.stTextArea textarea{background:#0c1727!important;color:#eef6ff!important;border-color:#2a405b!important}
[data-baseweb="popover"]{background:#101a2b}
hr{border-color:#263850!important}
</style>
""", unsafe_allow_html=True)


def scan_wifi():
    if platform.system() != "Windows": raise RuntimeError("Live Wi-Fi scan is supported on Windows using netsh.")
    res = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
    out = res.stdout
    def get(pattern):
        m = re.search(pattern, out, re.I | re.M); return m.group(1).strip() if m else ""
    ssid = get(r"^\s*SSID\s*:\s*(.+)$"); signal = get(r"^\s*Signal\s*:\s*(\d+)\s*%")
    channel = get(r"^\s*Channel\s*:\s*(\d+)"); state = get(r"^\s*State\s*:\s*(.+)$")
    rx = get(r"^\s*Receive rate \(Mbps\)\s*:\s*([\d.]+)"); tx = get(r"^\s*Transmit rate \(Mbps\)\s*:\s*([\d.]+)")
    radio = get(r"^\s*Radio type\s*:\s*(.+)$")
    if res.returncode or not ssid or state.lower() == "disconnected": raise RuntimeError("No connected Wi-Fi interface was found. Connect to Wi-Fi and retry.")
    pct = int(signal) if signal else None; ch = int(channel) if channel else None
    # This estimate is illustrative only; Windows signal percentage is not raw RSSI.
    est = round(pct / 2 - 100) if pct is not None else -60
    return {"ssid":ssid,"signal_percent":pct,"channel":ch,"band":"2.4 GHz" if ch and ch <= 14 else ("5 GHz" if ch else "Unknown"),"receive_rate_mbps":float(rx) if rx else None,"transmit_rate_mbps":float(tx) if tx else None,"radio_type":radio,"estimated_rssi":est}


def load_data():
    if not CSV.exists():
        pd.DataFrame(columns=["timestamp","location_id","x_m","y_m","ssid","rssi_dbm","signal_percent","band","channel","receive_rate_mbps","transmit_rate_mbps"]).to_csv(CSV,index=False)
    raw = pd.read_csv(CSV)
    return raw, clean_measurements(raw)

raw, measurements = load_data()
threshold = -80  # Default threshold; adjustable in the sidebar.
summary = summarize_locations(measurements, threshold)

st.markdown("""<div class="hero"><div class="eyebrow">WIRELESS NETWORK INTELLIGENCE</div><h1>Wi-Fi Quality Mapping</h1><p>Map signal quality. Diagnose weak coverage. Turn measurements into network decisions.</p><span class="pill">● LOCAL ANALYSIS &nbsp;·&nbsp; RSSI-BASED DIAGNOSTICS &nbsp;·&nbsp; CSV EXPORT</span></div>""", unsafe_allow_html=True)
with st.expander("How to explain Wi-Fi Quality Mapping during your project review", expanded=False):
    st.markdown("""<div class="guide-card"><div class="mini-label">Project in one sentence</div><b>Wi-Fi Quality Mapping turns signal measurements at known positions into a coverage view and clear weak-signal diagnostics.</b><br><br><b>1 · Measure:</b> readings are associated with a location ID and X/Y coordinates in metres.<br><b>2 · Summarize:</b> the app calculates mean, minimum, maximum and standard deviation of RSSI per location.<br><b>3 · Diagnose:</b> adjust the threshold in the sidebar; a location is flagged when its mean RSSI is below the selected value.<br><b>4 · Visualize:</b> markers show measured locations; the shaded surface estimates values between them and is not extra measured data.<br><b>5 · Act:</b> use the flags to decide where to repeat measurements or investigate access-point placement and obstructions.</div>""", unsafe_allow_html=True)
    st.info("Important limitation to state clearly: RSSI indicates received signal power, not internet speed or guaranteed connectivity. The built-in Windows scan reports signal percentage; its converted dBm value is an estimate. The map is only as reliable as the number and placement of measured points.")

with st.sidebar:
    st.markdown("### Workspace")
    st.caption("Coverage analysis console")
    st.markdown("**Dead-zone detection**")
    threshold = st.slider("Weak-signal threshold (dBm)", min_value=-95, max_value=-55, value=-80, step=1, help="Locations with an average RSSI below this value are flagged as potential dead zones. A threshold closer to 0 is stricter and flags more locations; a more negative threshold flags fewer.")
    st.caption(f"Selected threshold: {threshold} dBm. Locations averaging below this level are flagged for review.")
    st.divider()
    all_locs = sorted(summary.location_id.astype(str).unique().tolist()) if not summary.empty else []
    selected = st.multiselect("Locations in view", all_locs, default=all_locs)
    show_interpolation = st.toggle("Show estimated coverage surface", value=True, help="Interpolated surface is a visual estimate between measurement points, not additional measured data.")
    st.divider()
    st.markdown("**Signal guide**")
    st.markdown("🟢 Excellent / Good · −60 dBm and above  \n🟡 Fair · −61 to −67 dBm  \n🟠 Weak · −68 to −75 dBm  \n🔴 Very weak · below −75 dBm")

summary = summarize_locations(measurements, threshold)
view = summary[summary.location_id.isin(selected)].copy() if selected else summary.iloc[0:0]

# Add reading form
with st.expander("＋ Add a measurement", expanded=False):
    st.caption("Scan retrieves Windows-reported details. The RSSI populated from signal percentage is only an estimate; manually measured values can be entered instead.")
    if st.button("Scan connected Wi-Fi", type="secondary"):
        try: st.session_state["wifi_scan"] = scan_wifi(); st.session_state.pop("wifi_scan_error",None)
        except Exception as e: st.session_state["wifi_scan_error"] = str(e)
    if st.session_state.get("wifi_scan_error"): st.error(st.session_state["wifi_scan_error"])
    scan = st.session_state.get("wifi_scan", {})
    if scan: st.info(f"Network: {scan['ssid']} · Signal: {scan['signal_percent']}% · Channel: {scan['channel']} · Band: {scan['band']} · Estimated RSSI: {scan['estimated_rssi']} dBm")
    with st.form("measurement_form", clear_on_submit=True):
        a,b,c = st.columns(3)
        loc = a.text_input("Location ID", placeholder="e.g. LAB-06")
        x = b.number_input("X position (m)", value=0.0, step=.5)
        y = c.number_input("Y position (m)", value=0.0, step=.5)
        d,e,f = st.columns(3)
        rssi = d.number_input("RSSI (dBm)", min_value=-127, max_value=0, value=int(scan.get("estimated_rssi",-60)), step=1)
        ssid = e.text_input("SSID", value=scan.get("ssid",""))
        band = f.selectbox("Band", ["2.4 GHz","5 GHz","6 GHz","Unknown"], index=["2.4 GHz","5 GHz","6 GHz","Unknown"].index(scan.get("band","Unknown")))
        g,h,i = st.columns(3)
        channel = g.number_input("Channel", min_value=0,max_value=233,value=int(scan.get("channel") or 0),step=1)
        pct = h.number_input("Signal (%)",min_value=0,max_value=100,value=int(scan.get("signal_percent") or 0),step=1)
        rx = i.number_input("Receive rate (Mbps)",min_value=0.0,value=float(scan.get("receive_rate_mbps") or 0),step=1.0)
        save = st.form_submit_button("Save measurement", type="primary")
    if save:
        if not loc.strip(): st.error("Enter a location ID.")
        else:
            record = {"timestamp":datetime.now().astimezone().isoformat(timespec="seconds"),"location_id":loc.strip().upper(),"x_m":x,"y_m":y,"ssid":ssid,"rssi_dbm":rssi,"signal_percent":pct or pd.NA,"band":band,"channel":channel or pd.NA,"receive_rate_mbps":rx or pd.NA,"transmit_rate_mbps":scan.get("transmit_rate_mbps") or pd.NA}
            combined = pd.concat([raw,pd.DataFrame([record])],ignore_index=True); combined.to_csv(CSV,index=False)
            st.success("Measurement saved. The dashboard will refresh."); st.rerun()

if measurements.empty:
    st.warning("No valid measurements yet. Add a measurement or check data/wifi_measurements.csv.")
    st.stop()

# KPIs
loc_count = len(view); count = int(view.readings.sum()) if loc_count else 0
avg = view.mean_rssi_dbm.mean() if loc_count else float("nan")
weak_count = int((view.mean_rssi_dbm < -67).sum()) if loc_count else 0
dead_count = int((view.mean_rssi_dbm < threshold).sum()) if loc_count else 0
strongest = view.loc[view.mean_rssi_dbm.idxmax()] if loc_count else None
k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Mapped locations",f"{loc_count}",help="Unique location IDs in current filter")
k2.metric("Valid readings",f"{count}")
k3.metric("Mean signal",f"{avg:.1f} dBm" if loc_count else "—")
k4.metric("Weak locations",f"{weak_count}",help="Mean RSSI below −67 dBm")
k5.metric("Potential dead zones",f"{dead_count}",help=f"Mean RSSI below selected threshold ({threshold} dBm)")

st.markdown("<div style='height:8px'></div>",unsafe_allow_html=True)
tab_map, tab_diag, tab_data, tab_report = st.tabs(["🗺 Coverage map","◈ Diagnostics","▤ Measurements","⇩ Reports & methodology"])

with tab_map:
    st.markdown("<div class='guide-card'><b>How to read this map:</b> each labeled circle is a measured location. Hover to inspect its mean RSSI and sample count. The color surface is an inverse-distance-weighted estimate between points, so it is a visual guide rather than a direct measurement.</div>", unsafe_allow_html=True)
    left,right = st.columns([1.65,1],gap="large")
    with left:
        st.markdown('<div class="section-kicker">Spatial intelligence</div><h3>Signal coverage plane</h3>',unsafe_allow_html=True)
        fig = go.Figure()
        if show_interpolation:
            grid = idw_grid(view, 65) if len(view) >= 3 else None
            if grid:
                gx,gy,z = grid
                fig.add_trace(go.Heatmap(x=gx,y=gy,z=z,colorscale=[[0,"#b91c1c"],[.25,"#f97316"],[.5,"#facc15"],[.75,"#34d399"],[1,"#047857"]],zmin=-85,zmax=-45,opacity=.62,colorbar=dict(title="Estimated<br>dBm",thickness=12),hovertemplate="X %{x:.1f} m<br>Y %{y:.1f} m<br>Interpolated %{z:.1f} dBm<extra></extra>"))
        color_map = {"Excellent":"#047857","Good":"#10b981","Fair":"#facc15","Weak":"#f97316","Very weak":"#b91c1c","Insufficient data":"#64748b"}
        if not view.empty:
            for _, row in view.iterrows():
                fig.add_trace(go.Scatter(x=[row.x_m],y=[row.y_m],mode="markers+text",text=[str(row.location_id)],textposition="top center",name=str(row.location_id),marker=dict(size=17,line=dict(width=2,color="white"),color=color_map.get(row.signal_quality,"#64748b")),customdata=[[row.mean_rssi_dbm,row.signal_quality,int(row.readings),row.status,row.min_rssi_dbm,row.max_rssi_dbm]],hovertemplate="<b>%{text}</b><br>X: %{x:.2f} m<br>Y: %{y:.2f} m<br>Mean: %{customdata[0]:.1f} dBm<br>Quality: %{customdata[1]}<br>Readings: %{customdata[2]}<br>Status: %{customdata[3]}<br>Range: %{customdata[4]:.0f} to %{customdata[5]:.0f} dBm<extra></extra>"))
        fig.update_layout(height=510,margin=dict(l=10,r=10,t=10,b=10),paper_bgcolor="#0d1727",plot_bgcolor="#0d1727",legend=dict(orientation="h",y=-.12),xaxis_title="X position (metres)",yaxis_title="Y position (metres)",yaxis=dict(scaleanchor="x",scaleratio=1,gridcolor="#263850",zerolinecolor="#263850"),xaxis=dict(gridcolor="#263850",zerolinecolor="#263850"),font=dict(family="DM Sans",color="#d9e7f7"))
        st.plotly_chart(fig,use_container_width=True)
        st.caption("Measured points are shown as markers. The colored surface is inverse-distance-weighted interpolation between locations and must not be interpreted as additional measurements.")
    with right:
        st.markdown('<div class="section-kicker">Coverage ranking</div><h3>Location performance</h3>',unsafe_allow_html=True)
        rank = view.sort_values("mean_rssi_dbm",ascending=True)
        bar = px.bar(rank,x="mean_rssi_dbm",y="location_id",orientation="h",color="mean_rssi_dbm",range_color=[-85,-45],color_continuous_scale=["#b91c1c","#f97316","#facc15","#10b981","#047857"],labels={"mean_rssi_dbm":"Mean RSSI (dBm)","location_id":"Location"},hover_data={"readings":True,"std_dev_db":":.2f"})
        bar.add_vline(x=threshold,line_dash="dash",line_color="#b91c1c",annotation_text=f"Threshold {threshold} dBm")
        bar.update_layout(height=380,margin=dict(l=5,r=5,t=10,b=10),coloraxis_showscale=False,showlegend=False,paper_bgcolor="#0d1727",plot_bgcolor="#0d1727",font=dict(family="DM Sans",color="#d9e7f7"),xaxis=dict(gridcolor="#263850",zerolinecolor="#263850",color="#d9e7f7"),yaxis=dict(color="#d9e7f7"))
        st.plotly_chart(bar,use_container_width=True)
        if strongest is not None: st.markdown(f"<div class='note'><b>Best measured location: {strongest.location_id}</b><br>{strongest.mean_rssi_dbm:.1f} dBm mean RSSI across {int(strongest.readings)} reading(s). This is the strongest location in the current filtered dataset.</div>",unsafe_allow_html=True)
    st.markdown("### Quality distribution")
    quality_counts = view.signal_quality.value_counts().reindex(["Excellent","Good","Fair","Weak","Very weak"],fill_value=0).reset_index()
    quality_counts.columns=["Signal quality","Locations"]
    qfig=px.bar(quality_counts,x="Signal quality",y="Locations",color="Signal quality",color_discrete_map={"Excellent":"#047857","Good":"#10b981","Fair":"#facc15","Weak":"#f97316","Very weak":"#b91c1c"})
    qfig.update_layout(height=260,margin=dict(l=5,r=5,t=10,b=5),showlegend=False,paper_bgcolor="#0d1727",plot_bgcolor="#0d1727",font=dict(family="DM Sans",color="#d9e7f7"),xaxis=dict(gridcolor="#263850",color="#d9e7f7"),yaxis=dict(gridcolor="#263850",color="#d9e7f7"))
    st.plotly_chart(qfig,use_container_width=True)

with tab_diag:
    st.markdown("<div class='guide-card'><b>What this page proves:</b> it compares a threshold rule with observed variation. Mean RSSI reduces the influence of one unusually low sample, while the minimum reading helps reveal intermittent drops. Treat flags as investigation prompts, not proof of zero connectivity.</div>", unsafe_allow_html=True)
    st.markdown('<div class="section-kicker">Decision support</div><h3>Coverage diagnostics</h3>',unsafe_allow_html=True)
    st.caption(f"Classification uses mean RSSI. Potential dead-zone threshold is currently {threshold} dBm. These flags indicate weak measured signal, not proof of no connectivity.")
    diag=view.copy()
    if diag.empty: st.info("No locations selected.")
    else:
        diag["status"] = diag.mean_rssi_dbm.apply(lambda v:"Potential dead zone" if v < threshold else ("Weak coverage" if v < -67 else "Coverage acceptable"))
        diag["Recommendation"] = diag.apply(lambda r: "Repeat measurements; verify connectivity and consider AP placement" if r.mean_rssi_dbm < threshold else ("Check obstruction and compare at different times" if r.mean_rssi_dbm < -67 else "No signal-strength action indicated by this threshold"),axis=1)
        show=diag[["location_id","mean_rssi_dbm","min_rssi_dbm","max_rssi_dbm","std_dev_db","readings","weak_reading_pct","signal_quality","status","Recommendation"]].copy()
        show.columns=["Location","Mean (dBm)","Minimum (dBm)","Maximum (dBm)","Std dev (dB)","Readings","Readings below −67 dBm (%)","Quality","Status","Suggested next step"]
        st.dataframe(show.round(2),use_container_width=True,hide_index=True)
        unstable=diag[diag.std_dev_db >= 8]
        if not unstable.empty: st.warning("High variation detected at: " + ", ".join(unstable.location_id.astype(str)) + ". Consider collecting additional readings at consistent intervals.")
        else: st.success("No location has standard deviation ≥ 8 dB in the current filtered dataset.")
        st.markdown("#### Method comparison")
        st.write("The single-reading baseline flags a location if any reading falls below the threshold. The mean-based method flags it only when the average is below the threshold. The mean-based method is less sensitive to isolated outliers, but can hide intermittent drops; both views are useful.")
        base=measurements[measurements.location_id.isin(selected)].groupby("location_id").agg(mean_rssi=("rssi_dbm","mean"),min_rssi=("rssi_dbm","min"),readings=("rssi_dbm","size")).reset_index()
        base["Any reading below threshold"] = base.min_rssi < threshold
        base["Mean below threshold"] = base.mean_rssi < threshold
        st.dataframe(base.rename(columns={"location_id":"Location","mean_rssi":"Mean RSSI","min_rssi":"Minimum RSSI","readings":"Samples"}),use_container_width=True,hide_index=True)

with tab_data:
    st.markdown("<div class='guide-card'><b>Why this matters:</b> this is the audit trail behind every chart. Filter by location or SSID, check how many rows passed validation, and export the readings so results can be reproduced.</div>", unsafe_allow_html=True)
    st.markdown('<div class="section-kicker">Data explorer</div><h3>Measurement ledger</h3>',unsafe_allow_html=True)
    search=st.text_input("Filter by location ID or SSID",placeholder="Type a location or network name")
    filtered=measurements.copy()
    if search:
        mask=filtered.location_id.astype(str).str.contains(search,case=False,na=False)|filtered.ssid.astype(str).str.contains(search,case=False,na=False)
        filtered=filtered[mask]
    st.caption(f"Showing {len(filtered)} of {len(measurements)} valid rows · {len(raw)-len(measurements)} row(s) excluded by validation")
    st.dataframe(filtered,use_container_width=True,hide_index=True)
    st.download_button("Download filtered measurements (.csv)",filtered.to_csv(index=False).encode("utf-8"),file_name="wifi_measurements_export.csv",mime="text/csv",type="primary")
    with st.expander("Upload a CSV to inspect (does not overwrite your saved data)"):
        uploaded=st.file_uploader("CSV file",type=["csv"])
        if uploaded:
            try:
                uploaded_df=clean_measurements(pd.read_csv(uploaded)); st.success(f"Loaded {len(uploaded_df)} valid rows from uploaded file."); st.dataframe(uploaded_df,use_container_width=True,hide_index=True)
            except Exception as exc: st.error(f"Could not read uploaded CSV: {exc}")

with tab_report:
    st.markdown("<div class='guide-card'><b>For evaluation:</b> export the analysis report to document the threshold, dataset size, locations analyzed and interpretation limits. Use the same threshold and measurement procedure when comparing runs.</div>", unsafe_allow_html=True)
    st.markdown('<div class="section-kicker">Export & reproducibility</div><h3>Analysis report</h3>',unsafe_allow_html=True)
    now=datetime.now().astimezone().isoformat(timespec="seconds")
    report_lines=["Wi-Fi Quality Mapping — Coverage Analysis Report",f"Generated: {now}",f"Threshold: {threshold} dBm",f"Valid measurements: {len(measurements)}",f"Locations analyzed: {len(summary)}",f"Locations in current view: {len(view)}",f"Rows excluded during validation: {len(raw)-len(measurements)}", "", "Interpretation notes:","- Signal categories are heuristic RSSI bands, not a certification of user experience.","- A potential dead zone is a location whose mean RSSI is below the selected threshold.","- RSSI alone cannot prove loss of connectivity or poor throughput.","- Interpolated coverage surface is estimated between measurement points.","", "Location summary:"]
    if not view.empty:
        report_lines.append(view[["location_id","x_m","y_m","mean_rssi_dbm","min_rssi_dbm","max_rssi_dbm","std_dev_db","readings","signal_quality","status"]].round(2).to_string(index=False))
    report_text="\n".join(report_lines)
    st.text_area("Report preview",report_text,height=350)
    st.download_button("Download text report",report_text.encode("utf-8"),file_name="wifi_coverage_report.txt",mime="text/plain",type="primary")
    html="<html><head><meta charset='utf-8'><title>Wi-Fi Coverage Report</title><style>body{font:15px Arial;max-width:1000px;margin:40px auto;color:#17233b}h1{color:#0e7777}pre{white-space:pre-wrap;background:#f4f7fa;padding:20px;border-radius:10px}</style></head><body><h1>Wi-Fi Quality Mapping / Wi-Fi Coverage Report</h1><p>Generated analysis summary</p><pre>"+report_text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")+"</pre></body></html>"
    st.download_button("Download HTML report",html.encode("utf-8"),file_name="wifi_coverage_report.html",mime="text/html")
    st.markdown("#### Methodology & limitations")
    st.markdown("- **Mean RSSI:** average signal power for repeated samples at each location.\n- **Variability:** standard deviation highlights unstable readings.\n- **Dead-zone flag:** mean RSSI below the selected threshold; threshold should be calibrated for the target environment.\n- **Signal categories:** Excellent ≥ −50, Good ≥ −60, Fair ≥ −67, Weak ≥ −75, Very weak below −75 dBm.\n- **Interpolation:** inverse-distance weighting creates a visual estimate only; more measured points improve spatial reliability.\n- **Windows scan:** Windows `netsh` reports signal percentage, not direct RSSI; the displayed conversion is only a rough estimate.")

st.markdown("<hr style='border:0;border-top:1px solid #e4eaf1;margin-top:30px'>",unsafe_allow_html=True)
st.caption("Wi-Fi Quality Mapping · Network diagnostics research prototype · Use repeated, consistently collected measurements before making deployment decisions.")
