
import csv
import statistics
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
DATA_FILE = PROJECT_DIR / "data" / "wifi_measurements.csv"
REPORT_FILE = PROJECT_DIR / "data" / "member1_results_report.txt"


def main():
    if not DATA_FILE.exists():
        print(f"Dataset not found: {DATA_FILE}")
        return

    with DATA_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    if not rows:
        print("No measurement data found.")
        return

    measurements = defaultdict(list)
    band_channels = Counter()
    ssids = Counter()

    for row in rows:
        location = (row.get("location_id") or "").strip().upper()

        try:
            rssi = float(row["rssi_dbm"])
        except (KeyError, TypeError, ValueError):
            print(f"Skipping invalid RSSI row for {location or 'unknown'}.")
            continue

        if not location:
            print("Skipping a row with no location ID.")
            continue

        measurements[location].append(rssi)

        band = (row.get("band") or "Unavailable").strip()
        channel = (row.get("channel") or "Unavailable").strip()
        ssid = (row.get("ssid") or "Unavailable").strip()

        band_channels[(band, channel)] += 1
        ssids[ssid] += 1

    if not measurements:
        print("No valid measurements were found.")
        return

    means = {
        location: statistics.mean(values)
        for location, values in measurements.items()
    }

    strongest = max(means, key=means.get)
    weakest = min(means, key=means.get)

    lines = [
        "WI-FI NETWORK QUALITY MAPPING AND DEAD-ZONE DETECTION",
        "MEMBER 1: DATA COLLECTION AND ANALYSIS",
        "=" * 65,
        f"Report generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "1. DATASET OVERVIEW",
        f"Valid measurements analyzed: {sum(len(v) for v in measurements.values())}",
        f"Locations represented: {len(measurements)}",
        f"Location IDs: {', '.join(sorted(measurements))}",
        "",
        "2. LOCATION-WISE RSSI STATISTICS",
        "RSSI is measured in dBm. Values closer to zero generally indicate stronger signal.",
        "",
        f"{'Location':<12}{'Count':>8}{'Mean':>12}{'Min':>12}{'Max':>12}{'Std Dev':>12}",
        "-" * 68,
    ]

    for location in sorted(measurements):
        values = measurements[location]
        mean_value = statistics.mean(values)
        min_value = min(values)
        max_value = max(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0.0

        lines.append(
            f"{location:<12}{len(values):>8}{mean_value:>12.2f}"
            f"{min_value:>12.1f}{max_value:>12.1f}{std_dev:>12.2f}"
        )

    lines.extend([
        "",
        "3. INITIAL OBSERVATIONS",
        f"Strongest mean RSSI: {strongest} ({means[strongest]:.2f} dBm).",
        f"Weakest mean RSSI: {weakest} ({means[weakest]:.2f} dBm).",
        "These results do not independently establish a Wi-Fi dead zone.",
        "",
        "4. SSID COUNTS",
    ])

    for ssid, count in sorted(ssids.items()):
        lines.append(f"- {ssid}: {count} reading(s)")

    lines.extend(["", "5. BAND AND CHANNEL COUNTS"])

    for (band, channel), count in sorted(band_channels.items()):
        lines.append(f"- {band}, channel {channel}: {count} reading(s)")

    lines.extend([
        "",
        "6. METHODOLOGY AND LIMITATIONS",
        "- Measurements were collected using Windows netsh WLAN information.",
        "- Five readings were collected at each of the five recorded locations.",
        "- Coordinates are an assumed layout, not independently measured distances.",
        "- The dataset contains measurements from multiple Wi-Fi bands/channels.",
        "- Differences between bands may affect RSSI comparisons.",
        "- Signal percentage and link rates are not substitutes for direct throughput testing.",
        "- RSSI alone is insufficient to confirm a dead zone; a defined threshold and further evaluation are required.",
        "- Results can vary with device position, interference, time, and network conditions.",
        "",
        "7. TEAM HANDOFF",
        "- Member 2 can use the raw CSV and assumed coordinates for initial visualization.",
        "- Member 3 can use the raw readings and summary statistics to develop detection criteria.",
        "- The team should account for band/channel differences during evaluation.",
        "",
        "End of report.",
    ])

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=== Member 1 Results Report ===")
    print(f"Measurements analyzed: {sum(len(v) for v in measurements.values())}")
    print(f"Locations analyzed: {len(measurements)}")
    print(f"Strongest mean RSSI: {strongest} ({means[strongest]:.2f} dBm)")
    print(f"Weakest mean RSSI: {weakest} ({means[weakest]:.2f} dBm)")
    print(f"Report saved to: {REPORT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, csv.Error) as error:
        print("Could not generate the report:", error)
