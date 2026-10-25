from pathlib import Path
from datetime import datetime
import platform
import subprocess
import re

import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Wi-Fi Quality Studio",
    page_icon="📶",
    layout="wide",
    initial_sidebar_state="expanded",
)

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
MEASUREMENTS_FILE = DATA_DIR / "wifi_measurements.csv"
DEAD_ZONE_FILE = DATA_DIR / "dead_zone_results.csv"
DEAD_ZONE_THRESHOLD = -80

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem}
.hero {
  padding: 1.35rem 1.6rem; border-radius: 18px;
  background: linear-gradient(115deg, #102a43, #176b87);
  color: white; margin-bottom: 1rem;
}
.hero h1 {color: white; margin: 0 0 .3rem 0; font-size: 2rem}
.hero p {color: #e8f4f8; margin: 0}
div[data-testid="stMetric"] {
  background: rgba(128,128,128,.07); border: 1px solid rgba(128,128,128,.18);
  padding: 12px 14px; border-radius: 12px;
}
.small-note {font-size: .88rem; opacity: .8}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>📶 Wi-Fi Quality Studio</h1>
  <p>Explore coverage · compare locations · collect readings · identify weak-signal areas</p>
</div>
""", unsafe_allow_html=True)


def scan_current_wifi():
    """Read connected Wi-Fi details from Windows; RSSI is an estimate from signal percentage."""
    if platform.system() != "Windows":
        raise RuntimeError("Automatic Wi-Fi scanning currently supports Windows only.")
    result = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
    )
    output = result.stdout
    if result.returncode != 0 or not output.strip():
        raise RuntimeError(result.stderr.strip() or "Windows returned no Wi-Fi interface details.")

    def field(pattern):
        match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else ""

    ssid = field(r"^\s*SSID\s*:\s*(.+)$")
    signal = field(r"^\s*Signal\s*:\s*(\d+)\s*%")
    channel = field(r"^\s*Channel\s*:\s*(\d+)")
    radio = field(r"^\s*Radio type\s*:\s*(.+)$")
    receive = field(r"^\s*Receive rate \(Mbps\)\s*:\s*(\d+(?:\.\d+)?)")
    transmit = field(r"^\s*Transmit rate \(Mbps\)\s*:\s*(\d+(?:\.\d+)?)")
    state = field(r"^\s*State\s*:\s*(.+)$")
    if not ssid or state.lower() == "disconnected":
        raise RuntimeError("No connected Wi-Fi network found. Connect to Wi-Fi and scan again.")

    percent = int(signal) if signal else None
    channel_num = int(channel) if channel else None
    if channel_num is None:
        band = "Unknown"
    elif channel_num <= 14:
        band = "2.4 GHz"
    elif channel_num <= 177:
        band = "5 GHz"
    else:
        band = "6 GHz / Unknown"
    estimated_rssi = round(percent / 2 - 100) if percent is not None else None
    return {
        "ssid": ssid, "signal_percent": percent, "channel": channel_num, "band": band,
        "radio_type": radio or "Not reported",
        "receive_rate_mbps": float(receive) if receive else None,
        "transmit_rate_mbps": float(transmit) if transmit else None,
        "estimated_rssi": estimated_rssi,
    }


def load_measurements():
    if not MEASUREMENTS_FILE.exists():
        return pd.DataFrame()
    data = pd.read_csv(MEASUREMENTS_FILE)
    required = [
        "timestamp", "location_id", "x_m", "y_m", "ssid", "rssi_dbm",
        "signal_percent", "band", "channel", "receive_rate_mbps", "transmit_rate_mbps"
    ]
    for col in required:
        if col not in data.columns:
            data[col] = pd.NA
    for col in ["x_m", "y_m", "rssi_dbm", "signal_percent", "channel",
                "receive_rate_mbps", "transmit_rate_mbps"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data["location_id"] = data["location_id"].astype("string").str.strip().str.upper()
    data = data.dropna(subset=["location_id", "x_m", "y_m", "rssi_dbm"])
    return data[data["location_id"] != ""].copy()


def classify_signal(rssi):
    if rssi >= -50:
        return "Strong"
    if rssi >= -60:
        return "Moderate"
    if rssi >= -70:
        return "Weak"
    return "Very Weak"


def build_summary(data):
    if data.empty:
        return pd.DataFrame()
    summary = data.groupby("location_id", as_index=False).agg(
        x_m=("x_m", "mean"),
        y_m=("y_m", "mean"),
        rssi_dbm=("rssi_dbm", "mean"),
        min_rssi=("rssi_dbm", "min"),
        max_rssi=("rssi_dbm", "max"),
        readings=("rssi_dbm", "size"),
    )
    summary["signal_quality"] = summary["rssi_dbm"].apply(classify_signal)
    summary["status"] = summary["rssi_dbm"].apply(
        lambda value: "Potential Dead Zone" if value < DEAD_ZONE_THRESHOLD else "Not flagged by RSSI threshold"
    )
    if DEAD_ZONE_FILE.exists():
        try:
            dz = pd.read_csv(DEAD_ZONE_FILE)
            if {"location_id", "status"}.issubset(dz.columns):
                dz["location_id"] = dz["location_id"].astype(str).str.strip().str.upper()
                cols = [c for c in ["location_id", "dead_zone", "status"] if c in dz.columns]
                # The latest detector output, when available, takes precedence.
                summary = summary.drop(columns=["status"]).merge(dz[cols], on="location_id", how="left")
                summary["status"] = summary["status"].fillna(
                    summary["rssi_dbm"].apply(
                        lambda value: "Potential Dead Zone" if value < DEAD_ZONE_THRESHOLD else "Not flagged by RSSI threshold"
                    )
                )
        except Exception:
            pass
    return summary


if not MEASUREMENTS_FILE.exists():
    st.error(f"Measurements file not found: {MEASUREMENTS_FILE}")
    st.info("Place your existing wifi_measurements.csv inside the project's data folder.")
    st.stop()

try:
    measurements = load_measurements()
except Exception as exc:
    st.error(f"Could not read the measurements CSV: {exc}")
    st.stop()

if measurements.empty:
    st.warning("No valid readings with location coordinates and RSSI were found.")
    st.stop()

# Sidebar controls
summary_all = build_summary(measurements)
st.sidebar.header("🔎 Explore the data")
all_locations = sorted(summary_all["location_id"].astype(str).unique().tolist())
selected_locations = st.sidebar.multiselect("Locations", all_locations, default=all_locations)
quality_options = ["Strong", "Moderate", "Weak", "Very Weak"]
selected_quality = st.sidebar.multiselect("Signal quality", quality_options, default=quality_options)
available_bands = sorted([str(x) for x in measurements["band"].dropna().unique() if str(x).strip()])
selected_bands = st.sidebar.multiselect("Wi-Fi band", available_bands, default=available_bands)
st.sidebar.caption("Filters apply to the dashboard summary and charts.")

filtered_data = measurements[measurements["location_id"].isin(selected_locations)].copy()
if selected_bands:
    filtered_data = filtered_data[filtered_data["band"].astype(str).isin(selected_bands)]
elif available_bands:
    filtered_data = filtered_data.iloc[0:0]
summary = build_summary(filtered_data)
if selected_quality:
    summary = summary[summary["signal_quality"].isin(selected_quality)].copy()
else:
    summary = summary.iloc[0:0]
filtered_data = filtered_data[filtered_data["location_id"].isin(summary["location_id"])]

# Add-reading workflow
with st.expander("➕ Add a new Wi-Fi reading", expanded=False):
    st.write("Scan the connected Wi-Fi network if desired, then confirm the location and save the reading.")
    scan_col, info_col = st.columns([1, 2])
    with scan_col:
        if st.button("📡 Scan current Wi-Fi", type="primary", use_container_width=True):
            try:
                found = scan_current_wifi()
                st.session_state["wifi_scan"] = found
                st.session_state["wifi_scan_error"] = ""
            except Exception as exc:
                st.session_state["wifi_scan_error"] = str(exc)
    with info_col:
        st.caption("Uses Windows netsh. The RSSI derived from signal percentage is only an estimate, not a direct RSSI reading.")
    if st.session_state.get("wifi_scan_error"):
        st.error(st.session_state["wifi_scan_error"])
    scan = st.session_state.get("wifi_scan")
    if scan:
        st.success(f"Connected network detected: {scan['ssid']}")
        st.write(
            f"Signal: {scan['signal_percent'] if scan['signal_percent'] is not None else 'Unknown'}% · "
            f"Band: {scan['band']} · Channel: {scan['channel'] if scan['channel'] is not None else 'Unknown'} · "
            f"Radio: {scan['radio_type']}"
        )
        st.caption("Receive/transmit rates may not be exposed by Windows on every device.")
    with st.form("add_wifi_reading", clear_on_submit=True):
        left, middle, right = st.columns(3)
        with left:
            new_location = st.text_input("Location ID", placeholder="e.g. P6")
            new_x = st.number_input("X coordinate (m)", value=0.0, step=0.5, format="%.2f")
        with middle:
            new_y = st.number_input("Y coordinate (m)", value=0.0, step=0.5, format="%.2f")
            scan_rssi = scan.get("estimated_rssi") if scan and scan.get("estimated_rssi") is not None else -60
            new_rssi = st.number_input("RSSI (dBm)", min_value=-100, max_value=0, value=int(scan_rssi), step=1)
        with right:
            new_ssid = st.text_input("SSID", value=scan["ssid"] if scan else "")
            band_options = ["2.4 GHz", "5 GHz", "6 GHz", "Unknown"]
            scan_band = scan.get("band", "Unknown") if scan else "Unknown"
            band_index = band_options.index(scan_band) if scan_band in band_options else 3
            new_band = st.selectbox("Band", band_options, index=band_index)
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            scan_channel = scan.get("channel") if scan else None
            new_channel = st.number_input("Channel (0 = unknown)", min_value=0, max_value=233,
                                          value=int(scan_channel or 0), step=1)
        with col_b:
            scan_percent = scan.get("signal_percent") if scan else None
            new_percent = st.number_input("Signal % (0 = unknown)", min_value=0, max_value=100,
                                          value=int(scan_percent or 0), step=1)
        with col_c:
            st.caption("Optional link rates are retained when available; leave unknown values blank in the saved CSV.")
        save = st.form_submit_button("💾 Save reading", type="primary", use_container_width=True)
    if save:
        clean_id = new_location.strip().upper()
        if not clean_id:
            st.error("Enter a location ID, such as P6.")
        else:
            row = {
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "location_id": clean_id, "x_m": float(new_x), "y_m": float(new_y),
                "ssid": new_ssid.strip(), "rssi_dbm": int(new_rssi),
                "signal_percent": int(new_percent) if new_percent else pd.NA,
                "band": new_band, "channel": int(new_channel) if new_channel else pd.NA,
                "receive_rate_mbps": scan.get("receive_rate_mbps") if scan else pd.NA,
                "transmit_rate_mbps": scan.get("transmit_rate_mbps") if scan else pd.NA,
            }
            try:
                original = pd.read_csv(MEASUREMENTS_FILE)
                for col in row:
                    if col not in original.columns:
                        original[col] = pd.NA
                original = pd.concat([original, pd.DataFrame([row])], ignore_index=True)
                original.to_csv(MEASUREMENTS_FILE, index=False)
                st.success(f"Saved one reading for {clean_id}. The dashboard will refresh now.")
                st.rerun()
            except PermissionError:
                st.error("Windows could not write the CSV. Close it in Excel if it is open, then retry.")
            except Exception as exc:
                st.error(f"Could not save the reading: {exc}")

# Reload after possible write and prepare selected view
measurements = load_measurements()
summary_all = build_summary(measurements)
filtered_data = measurements[measurements["location_id"].isin(selected_locations)].copy()
if selected_bands:
    filtered_data = filtered_data[filtered_data["band"].astype(str).isin(selected_bands)]
elif available_bands:
    filtered_data = filtered_data.iloc[0:0]
summary = build_summary(filtered_data)
summary = summary[summary["signal_quality"].isin(selected_quality)] if selected_quality else summary.iloc[0:0]
filtered_data = filtered_data[filtered_data["location_id"].isin(summary["location_id"])]

if summary.empty:
    st.warning("No locations match the current filters. Change the filters in the sidebar.")
    st.stop()

# KPI cards
strongest = summary.loc[summary["rssi_dbm"].idxmax()]
weakest = summary.loc[summary["rssi_dbm"].idxmin()]
dead_count = int((summary["rssi_dbm"] < DEAD_ZONE_THRESHOLD).sum())
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Locations", len(summary))
k2.metric("Readings", len(filtered_data))
k3.metric("Average RSSI", f"{filtered_data['rssi_dbm'].mean():.1f} dBm")
k4.metric("Strongest location", str(strongest["location_id"]), f"{strongest['rssi_dbm']:.1f} dBm")
k5.metric("Below −80 dBm", dead_count)

tab_overview, tab_compare, tab_details, tab_data, tab_about = st.tabs(
    ["📊 Overview", "⚖️ Compare locations", "📍 Location explorer", "🧾 Data & export", "ℹ️ Methodology"]
)

with tab_overview:
    st.subheader("Coverage map")
    st.caption("Points show measured locations. Coordinates are the project's estimated indoor layout, not GPS. Heat between points is not measured directly.")
    map_fig = px.scatter(
        summary, x="x_m", y="y_m", color="rssi_dbm", size="readings",
        hover_name="location_id",
        hover_data={"rssi_dbm":":.1f", "signal_quality":True, "status":True,
                    "readings":True, "x_m":":.2f", "y_m":":.2f"},
        color_continuous_scale="RdYlGn", range_color=[-80, -40],
        labels={"x_m":"X coordinate (m)", "y_m":"Y coordinate (m)", "rssi_dbm":"Mean RSSI (dBm)"},
        title="Measured Wi-Fi signal by location",
    )
    map_fig.update_traces(marker=dict(line=dict(width=1, color="black")))
    map_fig.update_layout(height=440, margin=dict(l=10,r=10,t=55,b=10))
    st.plotly_chart(map_fig, use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Average RSSI by location")
        bar = px.bar(summary.sort_values("rssi_dbm"), x="rssi_dbm", y="location_id",
                     orientation="h", color="rssi_dbm", color_continuous_scale="RdYlGn",
                     range_color=[-80, -40], text_auto=".1f",
                     labels={"rssi_dbm":"Mean RSSI (dBm)", "location_id":"Location"})
        bar.add_vline(x=DEAD_ZONE_THRESHOLD, line_dash="dash",
                      annotation_text="−80 dBm reference")
        bar.update_layout(height=370, coloraxis_showscale=False, margin=dict(l=10,r=10,t=20,b=10))
        st.plotly_chart(bar, use_container_width=True)
    with right:
        st.subheader("Signal quality distribution")
        quality_counts = summary["signal_quality"].value_counts().reindex(quality_options, fill_value=0).reset_index()
        quality_counts.columns = ["Signal quality", "Locations"]
        pie = px.pie(quality_counts, names="Signal quality", values="Locations",
                     hole=.48, title="Locations by average signal quality")
        pie.update_layout(height=370, margin=dict(l=10,r=10,t=50,b=10))
        st.plotly_chart(pie, use_container_width=True)

    st.subheader("Quick interpretation")
    if dead_count:
        st.error(f"{dead_count} displayed location(s) have mean RSSI below −80 dBm. Inspect these areas and collect repeat readings.")
    else:
        st.success("No displayed location has a mean RSSI below −80 dBm in the current filtered data.")
    st.info(f"Weakest displayed location: **{weakest['location_id']}** at **{weakest['rssi_dbm']:.1f} dBm**. This is the weakest sampled point, not proof that all nearby areas have the same signal.")

with tab_compare:
    st.subheader("Compare two or more locations")
    compare_options = sorted(summary["location_id"].astype(str).unique().tolist())
    default_compare = compare_options[:min(3, len(compare_options))]
    chosen_compare = st.multiselect("Choose locations to compare", compare_options, default=default_compare)
    compare_df = summary[summary["location_id"].isin(chosen_compare)].copy()
    if compare_df.empty:
        st.info("Choose at least one location to see the comparison.")
    else:
        compare_fig = px.bar(compare_df.sort_values("rssi_dbm"), x="location_id", y="rssi_dbm",
                             color="signal_quality", text_auto=".1f",
                             hover_data=["min_rssi", "max_rssi", "readings", "status"],
                             labels={"location_id":"Location", "rssi_dbm":"Mean RSSI (dBm)",
                                     "signal_quality":"Signal quality"},
                             title="Mean signal strength comparison")
        compare_fig.add_hline(y=DEAD_ZONE_THRESHOLD, line_dash="dash",
                              annotation_text="Potential dead-zone threshold")
        compare_fig.update_layout(height=420)
        st.plotly_chart(compare_fig, use_container_width=True)
        st.dataframe(compare_df[["location_id","x_m","y_m","readings","min_rssi","rssi_dbm","max_rssi","signal_quality","status"]]
                     .sort_values("rssi_dbm", ascending=False), use_container_width=True, hide_index=True)
        if len(compare_df) >= 2:
            strongest_c = compare_df.loc[compare_df["rssi_dbm"].idxmax()]
            weakest_c = compare_df.loc[compare_df["rssi_dbm"].idxmin()]
            st.write(f"**Comparison:** {strongest_c['location_id']} is strongest ({strongest_c['rssi_dbm']:.1f} dBm); "
                     f"{weakest_c['location_id']} is weakest ({weakest_c['rssi_dbm']:.1f} dBm) among the selected locations.")

with tab_details:
    st.subheader("Location explorer")
    detail_locations = sorted(summary["location_id"].astype(str).unique().tolist())
    chosen = st.selectbox("Select a location", detail_locations, key="location_explorer")
    row = summary[summary["location_id"] == chosen].iloc[0]
    raw = filtered_data[filtered_data["location_id"].astype(str).str.upper() == chosen.upper()].copy()
    a,b,c,d = st.columns(4)
    a.metric("Mean RSSI", f"{row['rssi_dbm']:.1f} dBm")
    b.metric("Signal quality", row["signal_quality"])
    c.metric("Readings", int(row["readings"]))
    d.metric("Range", f"{row['min_rssi']:.0f} to {row['max_rssi']:.0f} dBm")
    st.write(f"**Coordinates:** ({row['x_m']:.2f} m, {row['y_m']:.2f} m)")
    st.write(f"**Status:** {row['status']}")
    detail_chart = px.line(raw.sort_values("timestamp") if "timestamp" in raw else raw,
                           y="rssi_dbm", markers=True,
                           hover_data=[c for c in ["timestamp","ssid","band","channel"] if c in raw],
                           labels={"rssi_dbm":"RSSI (dBm)", "index":"Reading"},
                           title=f"Individual readings at {chosen}")
    detail_chart.add_hline(y=DEAD_ZONE_THRESHOLD, line_dash="dash", annotation_text="−80 dBm reference")
    detail_chart.update_layout(height=350)
    st.plotly_chart(detail_chart, use_container_width=True)
    st.dataframe(raw, use_container_width=True, hide_index=True)

with tab_data:
    st.subheader("Measurements and export")
    st.caption("The table reflects the current sidebar filters.")
    st.dataframe(filtered_data, use_container_width=True, hide_index=True)
    csv_bytes = filtered_data.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download filtered readings (CSV)", csv_bytes,
                       file_name="wifi_measurements_filtered.csv", mime="text/csv")
    summary_csv = summary.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download location summary (CSV)", summary_csv,
                       file_name="wifi_location_summary.csv", mime="text/csv")
    report_lines = [
        "WI-FI QUALITY MAPPING — SUMMARY REPORT",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Locations shown: {len(summary)}",
        f"Readings shown: {len(filtered_data)}",
        f"Mean RSSI: {filtered_data['rssi_dbm'].mean():.2f} dBm",
        f"Strongest: {strongest['location_id']} ({strongest['rssi_dbm']:.2f} dBm)",
        f"Weakest: {weakest['location_id']} ({weakest['rssi_dbm']:.2f} dBm)",
        f"Locations below −80 dBm mean RSSI: {dead_count}",
        "",
        "Location summary:",
        summary[["location_id","x_m","y_m","readings","rssi_dbm","signal_quality","status"]].to_string(index=False),
        "",
        "Caution: Coordinates are assumed indoor coordinates. RSSI thresholds are indicators, not a substitute for connectivity/throughput tests.",
    ]
    st.download_button("⬇️ Download text summary report", "\n".join(report_lines).encode("utf-8"),
                       file_name="wifi_quality_report.txt", mime="text/plain")

with tab_about:
    st.subheader("Methodology and interpretation")
    st.markdown("""
- **RSSI:** received signal strength in dBm. Values closer to zero generally indicate a stronger signal.
- **Signal categories used here:** Strong ≥ −50 dBm; Moderate ≥ −60 dBm; Weak ≥ −70 dBm; Very Weak < −70 dBm.
- **Potential dead-zone reference:** mean RSSI below −80 dBm. This is a project threshold, not a universal standard.
- **Scanning:** the button reads the connected Wi-Fi interface through Windows `netsh wlan show interfaces`.
- **Estimated RSSI:** Windows signal percentage is converted to a rough estimate when direct RSSI is unavailable. It is not a direct measurement.
- **Coordinates:** represent an assumed indoor layout used to compare sampled points; they are not GPS coordinates.
- **Heatmap/map:** only measured points are actual samples. Any apparent signal between them is not directly measured.
- **Dead-zone results:** the dashboard applies the −80 dBm reference to the currently filtered data. Run `python .\\detect_dead_zones.py` to refresh the separate project output file if your team uses it.
""")
    st.warning("For a fair comparison, collect repeated readings at each location with the same device and, where possible, the same Wi-Fi band. RSSI alone does not measure internet speed.")

st.caption("Wi-Fi Quality Studio · Local Streamlit application · Data is stored in your project's data/wifi_measurements.csv")
