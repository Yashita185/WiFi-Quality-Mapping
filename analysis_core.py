"""Core, testable analysis functions for Wi-Fi quality mapping."""
from __future__ import annotations
import math
import pandas as pd

REQUIRED_COLUMNS = ["timestamp", "location_id", "x_m", "y_m", "ssid", "rssi_dbm", "signal_percent", "band", "channel", "receive_rate_mbps", "transmit_rate_mbps"]


def clean_measurements(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize schema and remove rows that cannot be spatially analyzed."""
    df = frame.copy()
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    for col in ["x_m", "y_m", "rssi_dbm", "signal_percent", "channel", "receive_rate_mbps", "transmit_rate_mbps"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["location_id"] = df["location_id"].astype("string").str.strip().str.upper()
    df = df.dropna(subset=["location_id", "x_m", "y_m", "rssi_dbm"])
    df = df[(df.location_id != "") & df.rssi_dbm.between(-127, 0) & df.x_m.map(math.isfinite) & df.y_m.map(math.isfinite)]
    return df.reset_index(drop=True)


def classify_signal(rssi: float) -> str:
    if pd.isna(rssi): return "Insufficient data"
    if rssi >= -50: return "Excellent"
    if rssi >= -60: return "Good"
    if rssi >= -67: return "Fair"
    if rssi >= -75: return "Weak"
    return "Very weak"


def summarize_locations(measurements: pd.DataFrame, threshold_dbm: float = -80.0) -> pd.DataFrame:
    """Summarize each point and flag potential low-coverage areas by mean RSSI."""
    if measurements.empty:
        return pd.DataFrame(columns=["location_id", "x_m", "y_m", "mean_rssi_dbm", "min_rssi_dbm", "max_rssi_dbm", "std_dev_db", "readings", "signal_quality", "status", "weak_reading_pct"])
    grouped = measurements.groupby("location_id", as_index=False).agg(
        x_m=("x_m", "mean"), y_m=("y_m", "mean"), mean_rssi_dbm=("rssi_dbm", "mean"),
        min_rssi_dbm=("rssi_dbm", "min"), max_rssi_dbm=("rssi_dbm", "max"),
        std_dev_db=("rssi_dbm", "std"), readings=("rssi_dbm", "size"),
        weak_reading_pct=("rssi_dbm", lambda s: 100 * (s < -67).mean()))
    grouped["std_dev_db"] = grouped["std_dev_db"].fillna(0)
    grouped["signal_quality"] = grouped["mean_rssi_dbm"].map(classify_signal)
    grouped["status"] = grouped["mean_rssi_dbm"].apply(lambda v: "Potential dead zone" if v < threshold_dbm else ("Weak coverage" if v < -67 else "Coverage acceptable"))
    return grouped.sort_values("mean_rssi_dbm").reset_index(drop=True)


def idw_grid(summary: pd.DataFrame, resolution: int = 60, power: float = 2.0):
    """Inverse-distance-weighted interpolation for a visual guide, not measured data."""
    import numpy as np
    if len(summary) < 3:
        return None
    xs = summary["x_m"].to_numpy(dtype=float); ys = summary["y_m"].to_numpy(dtype=float)
    vals = summary["mean_rssi_dbm"].to_numpy(dtype=float)
    pad_x = max((xs.max() - xs.min()) * .12, .5); pad_y = max((ys.max() - ys.min()) * .12, .5)
    gx = np.linspace(xs.min() - pad_x, xs.max() + pad_x, resolution)
    gy = np.linspace(ys.min() - pad_y, ys.max() + pad_y, resolution)
    xx, yy = np.meshgrid(gx, gy)
    dist = np.sqrt((xx[..., None] - xs) ** 2 + (yy[..., None] - ys) ** 2)
    weights = 1 / np.maximum(dist, 1e-9) ** power
    zz = (weights * vals).sum(axis=2) / weights.sum(axis=2)
    return gx, gy, zz
