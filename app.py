from pathlib import Path
from datetime import datetime
import subprocess
import re
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Wi-Fi Quality Mapping", page_icon="📶", layout="wide")
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
MEASUREMENTS_FILE = DATA_DIR / "wifi_measurements.csv"
DEAD_ZONE_FILE = DATA_DIR / "dead_zone_results.csv"

st.markdown("""
<style>
.block-container {padding-top:1.4rem}
.hero {padding:1.25rem 1.5rem;border-radius:16px;background:linear-gradient(115deg,#102a43,#176b87);color:white;margin-bottom:1rem}
.hero h1 {color:white;margin:0 0 .25rem 0}.hero p {margin:0;opacity:.9}
</style>
""", unsafe_allow_html=True)
st.markdown("""<div class="hero"><h1>📶 Wi-Fi Quality Mapping</h1><p>Signal overview, location comparisons, and dead-zone analysis</p></div>""", unsafe_allow_html=True)

if not MEASUREMENTS_FILE.exists():
    st.error(f"Measurements file not found: {MEASUREMENTS_FILE}")
    st.stop()

def scan_current_wifi():
    """Read current Wi-Fi details from Windows netsh. RSSI is estimated from signal percentage."""
    if __import__("platform").system() != "Windows":
        raise RuntimeError("Automatic Wi-Fi scan in this app currently supports Windows only.")
    result = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
    )
    output = result.stdout
    if result.returncode != 0 or not output.strip():
        raise RuntimeError(result.stderr.strip() or "Windows did not return Wi-Fi interface details.")
    def field(pattern):
        match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else ""
    ssid = field(r"^\s*SSID\s*:\s*(.+)$")
    signal = field(r"^\s*Signal\s*:\s*(\d+)\s*%")
    channel = field(r"^\s*Channel\s*:\s*(\d+)")
    radio = field(r"^\s*Radio type\s*:\s*(.+)$")
    receive_rate = field(r"^\s*Receive rate \(Mbps\)\s*:\s*(\d+(?:\.\d+)?)")
    transmit_rate = field(r"^\s*Transmit rate \(Mbps\)\s*:\s*(\d+(?:\.\d+)?)")
    state = field(r"^\s*State\s*:\s*(.+)$")
    if not ssid or state.lower() == "disconnected":
        raise RuntimeError("No connected Wi-Fi network was found. Connect to Wi-Fi and scan again.")
    percent = int(signal) if signal else None
    chan = int(channel) if channel else None
    if chan is not None:
        if chan <= 14:
            band = "2.4 GHz"
        elif chan >= 1 and chan <= 233:
            band = "5 GHz"
        else:
            band = "Unknown"
    else:
        band = "Unknown"
    # netsh usually provides signal percentage, not raw RSSI. This is a rough estimate only.
    estimated_rssi = round((percent / 2) - 100) if percent is not None else None
    return {
        "ssid": ssid,
        "signal_percent": percent,
        "channel": chan,
        "band": band,
        "radio_type": radio or "Not reported",
        "receive_rate_mbps": float(receive_rate) if receive_rate else None,
        "transmit_rate_mbps": float(transmit_rate) if transmit_rate else None,
        "estimated_rssi": estimated_rssi,
    }

def load_measurements():
    data = pd.read_csv(MEASUREMENTS_FILE)
    required = ["timestamp", "location_id", "x_m", "y_m", "ssid", "rssi_dbm", "signal_percent", "band", "channel", "receive_rate_mbps", "transmit_rate_mbps"]
    for col in required:
        if col not in data.columns:
            data[col] = pd.NA
    for col in ["x_m", "y_m", "rssi_dbm", "signal_percent", "channel", "receive_rate_mbps", "transmit_rate_mbps"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data["location_id"] = data["location_id"].astype("string").str.strip()
    data = data.dropna(subset=["location_id", "x_m", "y_m", "rssi_dbm"])
    return data[data["location_id"] != ""].copy()

def classify_signal(rssi):
    if rssi >= -50: return "Strong"
    if rssi >= -60: return "Moderate"
    if rssi >= -70: return "Weak"
    return "Very Weak"

def load_summary(data):
    summary = data.groupby("location_id", as_index=False).agg(
        x_m=("x_m", "mean"), y_m=("y_m", "mean"),
        rssi_dbm=("rssi_dbm", "mean"), readings=("rssi_dbm", "size"))
    summary["signal_quality"] = summary["rssi_dbm"].apply(classify_signal)
    if DEAD_ZONE_FILE.exists():
        try:
            dz = pd.read_csv(DEAD_ZONE_FILE)
            if {"location_id", "status"}.issubset(dz.columns):
                dz["location_id"] = dz["location_id"].astype(str).str.strip().str.upper()
                summary["location_id"] = summary["location_id"].astype(str).str.strip().str.upper()
                cols = [c for c in ["location_id", "dead_zone", "status"] if c in dz.columns]
                summary = summary.merge(dz[cols], on="location_id", how="left")
        except Exception:
            pass
    if "status" not in summary.columns:
        summary["status"] = "Not evaluated — rerun detect_dead_zones.py"
    summary["status"] = summary["status"].fillna("Not evaluated — rerun detect_dead_zones.py")
    return summary

try:
    measurements = load_measurements()
except Exception as exc:
    st.error(f"Could not read the measurements CSV: {exc}")
    st.stop()
if measurements.empty:
    st.warning("No valid measurements were found.")
    st.stop()

# Scan controls are outside the form so a scan can populate the form fields.
with st.expander("➕ Add new Wi-Fi reading", expanded=False):
    st.write("Scan your connected Wi-Fi network, then enter the location coordinates and save a reading.")
    scan_col, scan_info_col = st.columns([1, 2])
    with scan_col:
        if st.button("📡 Scan current Wi-Fi", type="primary", width="stretch"):
            try:
                found = scan_current_wifi()
                st.session_state["scan_result"] = found
                st.session_state["form_ssid"] = found["ssid"]
                st.session_state["form_band"] = found["band"]
                st.session_state["form_channel"] = found["channel"] or 0
                st.session_state["form_signal_percent"] = found["signal_percent"] if found["signal_percent"] is not None else 0
                st.session_state["form_receive"] = found["receive_rate_mbps"] if found["receive_rate_mbps"] is not None else 0.0
                st.session_state["form_transmit"] = found["transmit_rate_mbps"] if found["transmit_rate_mbps"] is not None else 0.0
                st.session_state["form_rssi"] = found["estimated_rssi"] if found["estimated_rssi"] is not None else -60
                st.session_state["scan_error"] = ""
            except Exception as exc:
                st.session_state["scan_error"] = str(exc)
    with scan_info_col:
        st.caption("Uses Windows `netsh` to read the connected network. Signal percentage, SSID and channel are system-reported. RSSI is only a rough estimate from percentage, not a direct RSSI measurement.")
    if st.session_state.get("scan_error"):
        st.error(st.session_state["scan_error"])
    scan_result = st.session_state.get("scan_result")
    if scan_result:
        st.success(f"Detected network: {scan_result['ssid']}")
        st.write(
            f"**Signal:** {scan_result['signal_percent'] if scan_result['signal_percent'] is not None else 'Unknown'}% · "
            f"**Band:** {scan_result['band']} · **Channel:** {scan_result['channel'] if scan_result['channel'] is not None else 'Unknown'} · "
            f"**Receive rate:** {scan_result['receive_rate_mbps'] if scan_result['receive_rate_mbps'] is not None else 'Unknown'} Mbps · "
            f"**Transmit rate:** {scan_result['transmit_rate_mbps'] if scan_result['transmit_rate_mbps'] is not None else 'Unknown'} Mbps · "
            f"**Radio type:** {scan_result['radio_type']}"
        )
        st.warning("RSSI shown in the form is estimated from Windows signal percentage. Use your collector's measured RSSI if you need an exact dBm value.")

    with st.form("add_reading_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            location_id = st.text_input("Location ID", key="form_location_id", placeholder="e.g. P6")
            x_m = st.number_input("X coordinate (m)", key="form_x", value=0.0, step=0.5, format="%.2f")
        with c2:
            y_m = st.number_input("Y coordinate (m)", key="form_y", value=0.0, step=0.5, format="%.2f")
            rssi_dbm = st.number_input("RSSI (dBm; estimated if scanned)", key="form_rssi", min_value=-100, max_value=0, value=-60, step=1)
        with c3:
            ssid = st.text_input("Wi-Fi network name (SSID)", key="form_ssid", placeholder="e.g. LHC-VIT")
            band = st.selectbox("Wi-Fi band", ["2.4 GHz", "5 GHz", "6 GHz", "Unknown"], key="form_band")
        channel = st.number_input("Channel", key="form_channel", min_value=0, max_value=233, value=0, step=1)
        signal_percent = st.number_input("Signal percentage", key="form_signal_percent", min_value=0, max_value=100, value=0, step=1)
        receive_rate = st.number_input("Receive rate Mbps (optional)", key="form_receive", min_value=0.0, value=0.0, step=1.0)
        transmit_rate = st.number_input("Transmit rate Mbps (optional)", key="form_transmit", min_value=0.0, value=0.0, step=1.0)
        submitted = st.form_submit_button("Save reading", type="primary")
    if submitted:
        clean_id = location_id.strip().upper()
        if not clean_id:
            st.error("Enter a location ID, such as P6.")
        else:
            new_row = {
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "location_id": clean_id, "x_m": float(x_m), "y_m": float(y_m),
                "ssid": ssid.strip(), "rssi_dbm": int(rssi_dbm),
                "signal_percent": int(signal_percent) if signal_percent else pd.NA,
                "band": band, "channel": int(channel) if channel else pd.NA,
                "receive_rate_mbps": float(receive_rate) if receive_rate else pd.NA,
                "transmit_rate_mbps": float(transmit_rate) if transmit_rate else pd.NA,
            }
            try:
                existing = pd.read_csv(MEASUREMENTS_FILE)
                for col in new_row:
                    if col not in existing.columns:
                        existing[col] = pd.NA
                all_cols = list(dict.fromkeys(list(existing.columns) + list(new_row.keys())))
                existing = existing.reindex(columns=all_cols)
                existing = pd.concat([existing, pd.DataFrame([new_row])], ignore_index=True)
                existing.to_csv(MEASUREMENTS_FILE, index=False)
                st.success(f"Saved reading for {clean_id} to wifi_measurements.csv.")
                st.info("Rerun detect_dead_zones.py separately to refresh dead-zone status.")
                st.rerun()
            except PermissionError:
                st.error("Windows could not write the CSV. Close it in Excel if open, then try again.")
            except Exception as exc:
                st.error(f"Could not save the reading: {exc}")

measurements = load_measurements()
summary = load_summary(measurements)
st.sidebar.header("Dashboard controls")
locs = sorted(summary["location_id"].astype(str).unique().tolist())
selected_locations = st.sidebar.multiselect("Locations", locs, default=locs)
qualities = ["Strong", "Moderate", "Weak", "Very Weak"]
selected_quality = st.sidebar.multiselect("Signal quality", qualities, default=qualities)
view = summary[summary["location_id"].isin(selected_locations) & summary["signal_quality"].isin(selected_quality)].copy()
if view.empty:
    st.warning("No locations match your filters.")
    st.stop()
strongest = view.loc[view["rssi_dbm"].idxmax()]
dead_count = int((view["status"] == "Potential Dead Zone").sum())
m1, m2, m3, m4 = st.columns(4)
m1.metric("Locations shown", len(view))
m2.metric("Average signal", f"{view['rssi_dbm'].mean():.1f} dBm")
m3.metric("Strongest location", str(strongest["location_id"]), f"{strongest['rssi_dbm']:.1f} dBm")
m4.metric("Potential dead zones", dead_count)

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Location details", "Raw measurements", "About"])
with tab1:
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Measured Wi-Fi signal map")
        fig, ax = plt.subplots(figsize=(7, 5))
        sc = ax.scatter(view["x_m"], view["y_m"], c=view["rssi_dbm"], cmap="RdYlGn", vmin=-80, vmax=-40, s=220, edgecolors="black")
        for _, row in view.iterrows():
            ax.annotate(f"{row['location_id']}\\n{row['rssi_dbm']:.1f} dBm", (row["x_m"], row["y_m"]), xytext=(0, 10), textcoords="offset points", ha="center", fontsize=8, bbox={"boxstyle":"round,pad=0.25","fc":"white","alpha":0.85})
        ax.set_xlabel("X coordinate (m)"); ax.set_ylabel("Y coordinate (m)"); ax.grid(alpha=.25)
        fig.colorbar(sc, ax=ax, label="RSSI (dBm)")
        st.pyplot(fig, width="stretch"); plt.close(fig)
    with right:
        st.subheader("Average RSSI by location")
        chart = view.sort_values("rssi_dbm")
        fig2, ax2 = plt.subplots(figsize=(6, 5))
        bars = ax2.barh(chart["location_id"], chart["rssi_dbm"])
        ax2.axvline(-80, linestyle="--", linewidth=1.5, label="−80 dBm reference")
        ax2.set_xlabel("Average RSSI (dBm)"); ax2.grid(axis="x", alpha=.25); ax2.legend(fontsize=8)
        for bar, val in zip(bars, chart["rssi_dbm"]):
            ax2.text(val + .5, bar.get_y()+bar.get_height()/2, f"{val:.1f}", va="center", fontsize=8)
        st.pyplot(fig2, width="stretch"); plt.close(fig2)
    st.subheader("Signal quality distribution")
    counts = view["signal_quality"].value_counts().reindex(qualities, fill_value=0)
    fig3, ax3 = plt.subplots(figsize=(7, 4))
    ax3.bar(counts.index, counts.values)
    ax3.set_xlabel("Signal quality"); ax3.set_ylabel("Number of locations"); ax3.grid(axis="y", alpha=.25)
    st.pyplot(fig3, width="stretch"); plt.close(fig3)

with tab2:
    st.subheader("Location summary")
    cols = [c for c in ["location_id","x_m","y_m","rssi_dbm","signal_quality","status","readings"] if c in view]
    st.dataframe(view[cols].sort_values("rssi_dbm", ascending=False), width="stretch", hide_index=True)
    chosen = st.selectbox("Inspect a location", view["location_id"].tolist())
    row = view[view["location_id"] == chosen].iloc[0]
    raw = measurements[measurements["location_id"].astype(str).str.upper() == str(chosen).upper()]
    a,b,c = st.columns(3)
    a.metric("Average RSSI", f"{row['rssi_dbm']:.1f} dBm"); b.metric("Signal quality", row["signal_quality"]); c.metric("Readings", len(raw))
    st.write(f"**Coordinates:** ({row['x_m']:.2f} m, {row['y_m']:.2f} m)")
    st.write(f"**Dead-zone status:** {row['status']}")
    st.dataframe(raw, width="stretch", hide_index=True)
with tab3:
    st.subheader("Raw measurement data")
    st.dataframe(measurements, width="stretch", hide_index=True)
    st.download_button("Download measurements CSV", measurements.to_csv(index=False).encode("utf-8"), file_name="wifi_measurements_export.csv", mime="text/csv")
with tab4:
    st.subheader("About this project")
    st.write("The dashboard reads data/wifi_measurements.csv and optional data/dead_zone_results.csv.")
    st.markdown("- RSSI values closer to 0 dBm generally indicate stronger signal.\\n- Signal categories: Strong ≥ −50, Moderate ≥ −60, Weak ≥ −70, Very Weak < −70 dBm.\\n- The scan button reads connected Wi-Fi details from Windows.")
    st.warning("Windows reports signal percentage rather than raw RSSI through this method. The app estimates RSSI from that percentage, so use the collector's RSSI value when exact dBm accuracy matters.")
st.caption("Wi-Fi Quality Mapping & Dead-Zone Detection • Local dashboard")
