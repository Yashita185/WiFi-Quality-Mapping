import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from pathlib import Path
import numpy as np
from scipy.interpolate import griddata
import warnings

# ==================================================
# 1. LOAD AND VALIDATE THE SHARED DATASET
# ==================================================

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
CSV_FILE = DATA_DIR / "wifi_measurements.csv"

if not CSV_FILE.exists():
    raise FileNotFoundError(
        f"Dataset not found:\n{CSV_FILE}\n"
        "Place wifi_measurements.csv inside the data folder."
    )

df = pd.read_csv(CSV_FILE)

required_columns = ["location_id", "x_m", "y_m", "rssi_dbm"]
missing = [c for c in required_columns if c not in df.columns]

if missing:
    raise ValueError(f"Missing required CSV columns: {missing}")

for col in ["x_m", "y_m", "rssi_dbm"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df["location_id"] = df["location_id"].astype("string").str.strip()

df = df.dropna(
    subset=["location_id", "x_m", "y_m", "rssi_dbm"]
).copy()

df = df[df["location_id"] != ""]

if df.empty:
    raise ValueError("The CSV contains no valid measurement records.")

# ==================================================
# 2. CALCULATE LOCATION SUMMARIES AND CLASSIFY SIGNAL
# ==================================================

location_data = (
    df.groupby("location_id", as_index=False)
    .agg(
        x_m=("x_m", "mean"),
        y_m=("y_m", "mean"),
        rssi_dbm=("rssi_dbm", "mean")
    )
)

def classify_signal(rssi):
    if rssi >= -50:
        return "Strong"
    elif rssi >= -60:
        return "Moderate"
    elif rssi >= -70:
        return "Weak"
    return "Very Weak"


location_data["signal_quality"] = (
    location_data["rssi_dbm"].apply(classify_signal)
)
# ==================================================
# 3. LOAD AND MERGE DEAD-ZONE RESULTS
# ==================================================

DEAD_ZONE_FILE = DATA_DIR / "dead_zone_results.csv"

if not DEAD_ZONE_FILE.exists():
    raise FileNotFoundError(
        f"Dead-zone results not found:\n{DEAD_ZONE_FILE}\n"
        "Run detect_dead_zones.py first."
    )

dead_zone_df = pd.read_csv(DEAD_ZONE_FILE)
required_dead_zone_columns = ["location_id", "dead_zone", "status"]
missing_dead_zone_columns = [
    column for column in required_dead_zone_columns
    if column not in dead_zone_df.columns
]

if missing_dead_zone_columns:
    raise ValueError(
        "Dead-zone results are missing required columns: "
        f"{missing_dead_zone_columns}"
    )

# Normalize IDs so matching is not affected by spaces or letter case.
location_data["location_id"] = (
    location_data["location_id"].astype(str).str.strip().str.upper()
)
dead_zone_df["location_id"] = (
    dead_zone_df["location_id"].astype(str).str.strip().str.upper()
)

if dead_zone_df["location_id"].duplicated().any():
    duplicates = dead_zone_df.loc[
        dead_zone_df["location_id"].duplicated(), "location_id"
    ].tolist()
    raise ValueError(
        f"Duplicate location IDs in dead-zone results: {duplicates}"
    )

location_data = location_data.merge(
    dead_zone_df[["location_id", "dead_zone", "status"]],
    on="location_id",
    how="left",
    validate="one_to_one"
)

if location_data[["dead_zone", "status"]].isna().any().any():
    unmatched = location_data.loc[
        location_data[["dead_zone", "status"]].isna().any(axis=1),
        "location_id"
    ].tolist()
    raise ValueError(
        "No matching dead-zone result for location(s): "
        f"{unmatched}. Check the IDs and rerun detect_dead_zones.py."
    )

print("\n========== WI-FI QUALITY RESULTS ==========")
print(
    location_data[
        [
            "location_id", "x_m", "y_m", "rssi_dbm",
            "signal_quality", "status"
        ]
    ].round(2).to_string(index=False)
)
# ==================================================
# 3. HELPER: DETAILS FOR A SELECTED LOCATION
# ==================================================

def get_location_details(location_id):
    """Return original measurements and summary for one location."""
    summary = location_data[
        location_data["location_id"] == location_id
    ].iloc[0]

    original = df[df["location_id"] == location_id]

    details = [
        f"Location: {location_id}",
        f"Coordinates: ({summary['x_m']:.2f} m, "
        f"{summary['y_m']:.2f} m)",
        f"Average RSSI: {summary['rssi_dbm']:.1f} dBm",
        f"Signal quality: {summary['signal_quality']}",
        f"Status: {summary['status']}",
        f"Readings at location: {len(original)}",
    ]
    # Include optional fields when the dataset provides them.
    for column, label in [
        ("ssid", "SSID"),
        ("band", "Band"),
        ("channel", "Channel"),
        ("signal_percent", "Signal percentage"),
        ("receive_rate_mbps", "Receive rate"),
        ("transmit_rate_mbps", "Transmit rate"),
        ("timestamp", "Timestamp"),
    ]:
        if column in original.columns:
            values = original[column].dropna().astype(str).unique()
            if len(values):
                shown = ", ".join(values[:3])
                if len(values) > 3:
                    shown += ", ..."
                details.append(f"{label}: {shown}")

    return "\n".join(details)
# ==================================================
# 4. FIGURE 1: CLICKABLE WI-FI QUALITY MAP
# ==================================================

fig, ax = plt.subplots(figsize=(11, 8))
fig.subplots_adjust(bottom=0.27)

acceptable = location_data[
    location_data["status"] == "Acceptable Signal"
]
dead_zones = location_data[
    location_data["status"] == "Potential Dead Zone"
]

if not acceptable.empty:
    ax.scatter(
        acceptable["x_m"], acceptable["y_m"],
        color="green", s=190, edgecolors="black",
        label="Acceptable Signal", zorder=3
    )
if not dead_zones.empty:
    ax.scatter(
        dead_zones["x_m"], dead_zones["y_m"],
        color="red", s=190, edgecolors="black",
        label="Potential Dead Zone", zorder=3
    )
# One readable label per point
for i, (_, row) in enumerate(location_data.iterrows()):
    offset = 18 if i % 2 == 0 else -18
    valign = "bottom" if offset > 0 else "top"

    ax.annotate(
        f"{row['location_id']}\n{row['rssi_dbm']:.1f} dBm",
        (row["x_m"], row["y_m"]),
        xytext=(0, offset),
        textcoords="offset points",
        ha="center",
        va=valign,
        fontsize=8,
        bbox=dict(
            boxstyle="round,pad=0.25",
            facecolor="white",
            alpha=0.9,
            edgecolor="gray"
        ),
        zorder=4
    )
ax.set_title("Wi-Fi Quality Map — Click a Point for Details", pad=18)
ax.set_xlabel("X coordinate (m)")
ax.set_ylabel("Y coordinate (m)")
ax.grid(True, alpha=0.3)
ax.legend(loc="best")
ax.margins(x=0.12, y=0.25)

# Details panel below the map
details_text = fig.text(
    0.08, 0.035,
    "Click a measurement point to display its details here.",
    ha="left",
    va="bottom",
    fontsize=9,
    family="monospace",
    bbox=dict(
        boxstyle="round,pad=0.6",
        facecolor="whitesmoke",
        edgecolor="gray"
    )
)
# Create one scatter collection for reliable click detection.
click_points = ax.scatter(
    location_data["x_m"],
    location_data["y_m"],
    s=500,
    color="none",
    edgecolors="none",
    picker=True,
    zorder=5
)
# Keep references to callbacks and interactive objects alive.
def on_map_click(event):
    if event.inaxes != ax or event.xdata is None or event.ydata is None:
        return

    # Find the nearest location in map coordinates.
    dx = location_data["x_m"].to_numpy() - event.xdata
    dy = location_data["y_m"].to_numpy() - event.ydata
    distances = np.hypot(dx, dy)

    nearest_index = int(np.argmin(distances))
    nearest = location_data.iloc[nearest_index]

    # Only select points when the click is reasonably close.
    x_span = max(
        float(location_data["x_m"].max() - location_data["x_m"].min()),
        1.0
    )
    y_span = max(
        float(location_data["y_m"].max() - location_data["y_m"].min()),
        1.0
    )
    tolerance = 0.06 * np.hypot(x_span, y_span)

    if distances[nearest_index] > tolerance:
        return

    details_text.set_text(
        get_location_details(str(nearest["location_id"]))
    )
    fig.canvas.draw_idle()

map_callback_id = fig.canvas.mpl_connect(
    "button_press_event", on_map_click
)
quality_map_file = DATA_DIR / "wifi_quality_map.png"
fig.savefig(quality_map_file, dpi=300, bbox_inches="tight")
print(f"\nQuality map saved to:\n{quality_map_file}")
# ==================================================
# 5. FIGURE 2: INTERPOLATED COVERAGE HEATMAP
# ==================================================

x = location_data["x_m"].to_numpy(dtype=float)
y = location_data["y_m"].to_numpy(dtype=float)
signal = location_data["rssi_dbm"].to_numpy(dtype=float)
coords = np.column_stack((x, y))

fig_heat, ax_heat = plt.subplots(figsize=(10, 7))

# Combine locations with identical coordinates before interpolation.
interp_df = pd.DataFrame({
    "x_m": x,
    "y_m": y,
    "rssi_dbm": signal
})
interp_df = (
    interp_df.groupby(["x_m", "y_m"], as_index=False)
    .agg(rssi_dbm=("rssi_dbm", "mean"))
)

interp_coords = interp_df[["x_m", "y_m"]].to_numpy()
interp_signal = interp_df["rssi_dbm"].to_numpy()

# Linear interpolation requires at least three non-collinear points.
centered = interp_coords - interp_coords.mean(axis=0)
can_interpolate = (
    len(interp_coords) >= 3
    and np.linalg.matrix_rank(centered) >= 2
)
heat = None

if can_interpolate:
    grid_x, grid_y = np.meshgrid(
        np.linspace(interp_coords[:, 0].min(),
                    interp_coords[:, 0].max(), 200),
        np.linspace(interp_coords[:, 1].min(),
                    interp_coords[:, 1].max(), 200)
    )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            grid_signal = griddata(
                interp_coords,
                interp_signal,
                (grid_x, grid_y),
                method="linear"
            )

        if grid_signal is not None and np.isfinite(grid_signal).any():
            heat = ax_heat.contourf(
                grid_x, grid_y, grid_signal,
                levels=20, cmap="RdYlGn"
            )
            fig_heat.colorbar(
                heat, ax=ax_heat,
                label="Estimated signal strength (dBm)"
            )
        else:
            print(
                "Heatmap interpolation unavailable; showing points only."
            )

    except (ValueError, RuntimeError) as error:
        print(f"Heatmap interpolation failed: {error}")

else:
    print(
        "Insufficient distinct, non-collinear coordinates for a 2D heatmap. "
        "Showing measured locations only."
    )
     
    
# Plot and label actual measurements
ax_heat.scatter(
    x, y,
    c=signal,
    cmap="RdYlGn",
    vmin=float(signal.min()),
    vmax=float(signal.max()) if signal.max() > signal.min()
    else float(signal.min()) + 1,
    s=130,
    edgecolors="black",
    label="Measured locations",
    zorder=3
)
for _, row in location_data.iterrows():
    ax_heat.annotate(
        f"{row['location_id']}\n{row['rssi_dbm']:.1f} dBm",
        (row["x_m"], row["y_m"]),
        xytext=(0, 10),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=8,
        fontweight="bold",
        bbox=dict(
            boxstyle="round,pad=0.2",
            facecolor="white",
            alpha=0.85,
            edgecolor="none"
        ),
        zorder=4
    )
ax_heat.set_title("Wi-Fi Coverage Heatmap (Estimated Between Measurements)")
ax_heat.set_xlabel("X coordinate (m)")
ax_heat.set_ylabel("Y coordinate (m)")
ax_heat.grid(alpha=0.2)
ax_heat.legend(loc="best")
ax_heat.margins(x=0.12, y=0.20)
fig_heat.tight_layout()

heatmap_file = DATA_DIR / "wifi_coverage_heatmap.png"
fig_heat.savefig(heatmap_file, dpi=300, bbox_inches="tight")
print(f"Coverage heatmap saved to:\n{heatmap_file}")

# ==================================================
# 6. SHOW FIGURES
# ==================================================

print("\nClick a point on the Wi-Fi Quality Map to view its details.")
print("Close the graph windows to finish the program.")
plt.show()

