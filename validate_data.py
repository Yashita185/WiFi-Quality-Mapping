
import csv
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent
CSV_FILE = BASE_DIR / "data" / "wifi_measurements.csv"

REQUIRED_COLUMNS = [
    "timestamp", "location_id", "x_m", "y_m",
    "ssid", "rssi_dbm", "signal_percent",
    "band", "channel"
]

def main():
    if not CSV_FILE.exists():
        print("ERROR: Measurement CSV file not found.")
        return

    with CSV_FILE.open(
        "r", newline="", encoding="utf-8"
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            print("ERROR: CSV is empty or has no header.")
            return

        missing_columns = [
            col for col in REQUIRED_COLUMNS
            if col not in reader.fieldnames
        ]

        if missing_columns:
            print("ERROR: Missing columns:", missing_columns)
            return

        rows = list(reader)

    print("\n=== Wi-Fi Dataset Validation ===")
    print("Total data rows:", len(rows))

    if not rows:
        print("ERROR: No measurement records found.")
        return

    errors = []
    locations = defaultdict(list)
    seen = set()
    duplicate_count = 0

    for line_number, row in enumerate(rows, start=2):
        location = row["location_id"].strip().upper()

        # Check required fields.
        for column in REQUIRED_COLUMNS:
            if not row.get(column, "").strip():
                errors.append(
                    f"Row {line_number}: missing {column}"
                )

        # Check RSSI.
        try:
            rssi = float(row["rssi_dbm"])
            if not -127 <= rssi <= 0:
                errors.append(
                    f"Row {line_number}: RSSI out of range"
                )
        except ValueError:
            errors.append(
                f"Row {line_number}: invalid RSSI"
            )
            continue

        # Check signal percentage.
        try:
            signal = float(row["signal_percent"])
            if not 0 <= signal <= 100:
                errors.append(
                    f"Row {line_number}: invalid signal percentage"
                )
        except ValueError:
            errors.append(
                f"Row {line_number}: invalid signal percentage"
            )

        # Check coordinates.
        try:
            float(row["x_m"])
            float(row["y_m"])
        except ValueError:
            errors.append(
                f"Row {line_number}: invalid coordinates"
            )

        # Flag exact duplicate records.
        record = tuple(row.get(k, "") for k in reader.fieldnames)
        if record in seen:
            duplicate_count += 1
        seen.add(record)

        locations[location].append(row)

    print("Locations found:", len(locations))
    print("Exact duplicate rows:", duplicate_count)

    print("\nReadings per location:")
    for location, readings in sorted(locations.items()):
        print(f"{location}: {len(readings)}")

        coordinate_pairs = {
            (r["x_m"], r["y_m"]) for r in readings
        }
        if len(coordinate_pairs) > 1:
            errors.append(
                f"{location}: inconsistent coordinates"
            )

    configurations = Counter(
        (row["band"], row["channel"]) for row in rows
    )

    print("\nRecorded band/channel combinations:")
    for (band, channel), count in configurations.items():
        print(f"{band}, channel {channel}: {count} readings")

    print("\nValidation result:")
    if errors:
        print(f"FOUND {len(errors)} ISSUE(S):")
        for error in errors:
            print("-", error)
    else:
        print("No missing required fields or invalid values found.")

    print(
        "\nNote: duplicate rows are flagged for review; "
        "they are not automatically deleted."
    )

if __name__ == "__main__":
    main()
