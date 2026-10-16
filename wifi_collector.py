
import csv
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Project data folder
DATA_DIR = Path(__file__).parent / "data"
CSV_FILE = DATA_DIR / "wifi_measurements.csv"


def get_field(output, field):
    """Extract a field from Windows netsh output."""
    pattern = rf"^\s*{re.escape(field)}\s*:\s*(.*?)\s*$"
    match = re.search(
        pattern,
        output,
        re.MULTILINE | re.IGNORECASE
    )
    return match.group(1).strip() if match else ""


def get_wifi_measurement():
    """Collect one Wi-Fi measurement."""

    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10
        )

    except (OSError, subprocess.TimeoutExpired) as error:
        print("Could not read Wi-Fi information:", error)
        return None

    if result.returncode != 0:
        print("Windows could not retrieve Wi-Fi information.")
        return None

    output = result.stdout

    # Check connection status
    state = get_field(output, "State")

    if state.lower() != "connected":
        print("Wi-Fi is not connected. No measurement recorded.")
        return None

    # Extract Wi-Fi details
    ssid = get_field(output, "SSID")
    rssi = get_field(output, "Rssi")
    signal = get_field(output, "Signal")
    band = get_field(output, "Band")
    channel = get_field(output, "Channel")

    rx_rate = get_field(output, "Receive rate (Mbps)")
    tx_rate = get_field(output, "Transmit rate (Mbps)")

    # Validate RSSI
    if not rssi or not re.fullmatch(r"-?\d+", rssi):
        print("RSSI is unavailable. No measurement recorded.")
        return None

    rssi_value = int(rssi)

    if not -127 <= rssi_value <= 0:
        print("RSSI is outside the valid range. No measurement recorded.")
        return None

    # Extract signal percentage if available
    signal_match = re.search(r"\d+", signal)
    signal_percent = (
        int(signal_match.group())
        if signal_match
        else ""
    )

    if signal_percent != "" and not 0 <= signal_percent <= 100:
        print("Invalid signal percentage. No measurement recorded.")
        return None

    # Return one measurement
    return {
        "timestamp": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "ssid": ssid,
        "rssi_dbm": rssi_value,
        "signal_percent": signal_percent,
        "band": band,
        "channel": channel,
        "receive_rate_mbps": rx_rate,
        "transmit_rate_mbps": tx_rate
    }


def main():
    print("=== Wi-Fi Data Collection ===")

    # Get location information
    location_id = input(
        "Enter location ID (e.g. P1): "
    ).strip().upper()

    if not location_id:
        print("Location ID cannot be empty.")
        return

    try:
        x = float(input("Enter X coordinate in metres: "))
        y = float(input("Enter Y coordinate in metres: "))
        count = int(input("Number of readings (e.g. 5): "))
        interval = float(input("Interval in seconds (e.g. 2): "))

        if count < 1 or interval <= 0:
            raise ValueError

    except ValueError:
        print(
            "Enter valid coordinates, a positive reading count, "
            "and a positive interval."
        )
        return

    # Create data folder if it does not exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Preserve the existing dataset column names
    columns = [
        "timestamp",
        "location_id",
        "x_m",
        "y_m",
        "ssid",
        "rssi_dbm",
        "signal_percent",
        "band",
        "channel",
        "receive_rate_mbps",
        "transmit_rate_mbps"
    ]

    file_needs_header = (
        not CSV_FILE.exists()
        or CSV_FILE.stat().st_size == 0
    )

    successful_readings = 0
    skipped_readings = 0

    try:
        with CSV_FILE.open(
            "a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=columns
            )

            if file_needs_header:
                writer.writeheader()

            for i in range(count):
                print(f"\nCollecting reading {i + 1}/{count}...")

                measurement = get_wifi_measurement()

                if measurement is not None:
                    row = {
                        "timestamp": measurement["timestamp"],
                        "location_id": location_id,
                        "x_m": x,
                        "y_m": y,
                        **measurement
                    }

                    writer.writerow(row)
                    file.flush()

                    successful_readings += 1

                    print(
                        f"RSSI: {measurement['rssi_dbm']} dBm | "
                        f"Signal: "
                        f"{measurement['signal_percent']}% | "
                        f"Band: {measurement['band'] or 'Unavailable'} | "
                        f"Channel: "
                        f"{measurement['channel'] or 'Unavailable'}"
                    )

                else:
                    skipped_readings += 1
                    print(
                        f"Reading {i + 1}/{count} skipped."
                    )

                if i < count - 1:
                    time.sleep(interval)

        print("\n=== Collection Finished ===")
        print(f"Requested readings: {count}")
        print(f"Successfully saved: {successful_readings}")
        print(f"Skipped readings: {skipped_readings}")
        print(f"Data saved to: {CSV_FILE}")

    except OSError as error:
        print("Could not save the CSV file:", error)


if __name__ == "__main__":
    main()
