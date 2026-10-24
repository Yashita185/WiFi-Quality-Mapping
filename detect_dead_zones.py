"""Member 3: RSSI-based Wi-Fi dead-zone detection.

Reads data/wifi_measurements.csv and writes data/dead_zone_results.csv.
The baseline flags a location if any single reading crosses the threshold.
The proposed method flags a location if its mean RSSI crosses the threshold.
"""

import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
INPUT_FILE = DATA_DIR / "wifi_measurements.csv"
OUTPUT_FILE = DATA_DIR / "dead_zone_results.csv"

# Project design parameters. Calibrate these for the actual environment.
DEAD_ZONE_THRESHOLD_DBM = -80.0
WEAK_THRESHOLD_DBM = -70.0
MODERATE_THRESHOLD_DBM = -60.0

REQUIRED_COLUMNS = {"location_id", "x_m", "y_m", "rssi_dbm"}


def classify_signal(mean_rssi):
    """Use the same quality categories as the existing Member 2 visualizer."""
    if mean_rssi >= -50:
        return "Strong"
    if mean_rssi >= MODERATE_THRESHOLD_DBM:
        return "Moderate"
    if mean_rssi >= WEAK_THRESHOLD_DBM:
        return "Weak"
    return "Very Weak"


def read_measurements(path):
    """Read valid measurements, retaining locations even if RSSI is invalid."""
    locations = {}

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError("Input CSV is empty or has no header.")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Input CSV is missing columns: {sorted(missing)}")

        for line_number, row in enumerate(reader, start=2):
            location_id = (row.get("location_id") or "").strip()
            if not location_id:
                print(f"Skipping row {line_number}: empty location_id")
                continue

            if location_id not in locations:
                locations[location_id] = {
                    "x_values": [],
                    "y_values": [],
                    "rssis": [],
                    "bands": set(),
                    "channels": set(),
                }

            entry = locations[location_id]

            for column, target in (("x_m", "x_values"), ("y_m", "y_values")):
                try:
                    coordinate = float(row[column])
                    if math.isfinite(coordinate):
                        entry[target].append(coordinate)
                except (ValueError, TypeError):
                    pass

            try:
                rssi = float(row["rssi_dbm"])
                if math.isfinite(rssi) and -127 <= rssi <= 0:
                    entry["rssis"].append(rssi)
            except (ValueError, TypeError):
                pass

            band = (row.get("band") or "").strip()
            channel = (row.get("channel") or "").strip()
            if band:
                entry["bands"].add(band)
            if channel:
                entry["channels"].add(channel)

    return locations


def detect_dead_zones():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {INPUT_FILE}\n"
            "Keep data/wifi_measurements.csv inside the project folder."
        )

    locations = read_measurements(INPUT_FILE)
    if not locations:
        raise ValueError("No locations found in the input CSV.")

    results = []
    for location_id, entry in locations.items():
        rssis = entry["rssis"]
        x = statistics.mean(entry["x_values"]) if entry["x_values"] else ""
        y = statistics.mean(entry["y_values"]) if entry["y_values"] else ""

        if not rssis:
            results.append({
                "location_id": location_id,
                "x_m": x,
                "y_m": y,
                "sample_count": 0,
                "mean_rssi_dbm": "",
                "min_rssi_dbm": "",
                "max_rssi_dbm": "",
                "std_dev_db": "",
                "signal_quality": "Insufficient Data",
                "baseline_dead_zone": "Unknown",
                "dead_zone": "Unknown",
                "status": "Insufficient Data",
                "bands": "; ".join(sorted(entry["bands"])),
                "channels": "; ".join(sorted(entry["channels"])),
            })
            continue

        mean_rssi = statistics.mean(rssis)
        # Baseline: one weak outlier is enough to flag the location.
        baseline_flag = any(value < DEAD_ZONE_THRESHOLD_DBM for value in rssis)
        # Proposed: use repeated-measurement average for the decision.
        proposed_flag = mean_rssi < DEAD_ZONE_THRESHOLD_DBM

        results.append({
            "location_id": location_id,
            "x_m": round(x, 3) if x != "" else "",
            "y_m": round(y, 3) if y != "" else "",
            "sample_count": len(rssis),
            "mean_rssi_dbm": round(mean_rssi, 2),
            "min_rssi_dbm": min(rssis),
            "max_rssi_dbm": max(rssis),
            "std_dev_db": round(statistics.stdev(rssis), 2) if len(rssis) >= 2 else 0.0,
            "signal_quality": classify_signal(mean_rssi),
            "baseline_dead_zone": "Yes" if baseline_flag else "No",
            "dead_zone": "Yes" if proposed_flag else "No",
            "status": "Potential Dead Zone" if proposed_flag else "Acceptable Signal",
            "bands": "; ".join(sorted(entry["bands"])),
            "channels": "; ".join(sorted(entry["channels"])),
        })

    columns = [
        "location_id", "x_m", "y_m", "sample_count", "mean_rssi_dbm",
        "min_rssi_dbm", "max_rssi_dbm", "std_dev_db", "signal_quality",
        "baseline_dead_zone", "dead_zone", "status", "bands", "channels"
    ]
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(results)

    print("\n=== MEMBER 3: DEAD-ZONE DETECTION ===")
    print(f"Threshold: RSSI < {DEAD_ZONE_THRESHOLD_DBM:.0f} dBm")
    print(f"Input:  {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}\n")
    print(f"{'Location':<12}{'Samples':<9}{'Mean RSSI':<13}{'Quality':<17}{'Baseline':<12}{'Proposed'}")
    print("-" * 78)
    for row in results:
        print(
            f"{row['location_id']:<12}{row['sample_count']:<9}"
            f"{str(row['mean_rssi_dbm']):<13}{row['signal_quality']:<17}"
            f"{row['baseline_dead_zone']:<12}{row['dead_zone']}"
        )

    print("\nDone. Use dead_zone_results.csv in Member 2's visualizer.")
    print("Reminder: RSSI threshold flags potential dead zones; it does not prove no connectivity.")


if __name__ == "__main__":
    try:
        detect_dead_zones()
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}")
