
import csv
import statistics
from collections import defaultdict
from pathlib import Path

# Locate the existing measurement file
BASE_DIR = Path(__file__).parent
INPUT_FILE = BASE_DIR / "data" / "wifi_measurements.csv"
OUTPUT_FILE = BASE_DIR / "data" / "wifi_summary.csv"


def main():
    if not INPUT_FILE.exists():
        print("Error: Measurement CSV file not found.")
        return

    locations = defaultdict(list)

    with INPUT_FILE.open(
        "r", newline="", encoding="utf-8"
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                location = row["location_id"].strip().upper()
                rssi = float(row["rssi_dbm"])
                locations[location].append(rssi)
            except (KeyError, ValueError):
                print("Skipping an invalid row.")

    if not locations:
        print("No valid measurements found.")
        return

    summary = []

    print("\n=== Wi-Fi Measurement Summary ===")
    print(f"{'Location':<12}{'Count':<8}{'Mean RSSI':<14}{'Min':<10}{'Max':<10}")

    for location in sorted(locations):
        values = locations[location]

        mean_rssi = statistics.mean(values)
        min_rssi = min(values)
        max_rssi = max(values)
        std_dev = statistics.stdev(values) if len(values) >= 2 else 0.0

        print(
            f"{location:<12}{len(values):<8}"
            f"{mean_rssi:<14.2f}{min_rssi:<10.1f}{max_rssi:<10.1f}"
        )

        summary.append({
            "location_id": location,
            "readings": len(values),
            "mean_rssi_dbm": round(mean_rssi, 2),
            "min_rssi_dbm": min_rssi,
            "max_rssi_dbm": max_rssi,
            "std_dev_db": round(std_dev, 2),
        })

    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        columns = [
            "location_id", "readings", "mean_rssi_dbm",
            "min_rssi_dbm", "max_rssi_dbm", "std_dev_db"
        ]
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(summary)

    print(f"\nSummary saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
