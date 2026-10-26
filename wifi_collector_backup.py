
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
    pattern = rf"^\s*{re.escape(field)}\s*:\s*(.*?)\s*$"
    match = re.search(pattern, output, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""

def get_wifi_measurement():
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
    state = get_field(output, "State")

    if state.lower() != "connected":
        print("Wi-Fi is not connected. No measurement recorded.")
        return None

    ssid = get_field(output, "SSID")
    rssi = get_field(output, "Rssi")
    signal = get_field(output, "Signal")

    if not rssi or not re.fullmatch(r"-?\d+", rssi):
        print("RSSI is unavailable. No measurement recorded.")
        return None

    signal_match = re.search(r"\d+", signal)
    band = get_field(output, "Band")
    channel = get_field(output, "Channel")
    rx_rate = get_field(output, "Receive rate (Mbps)")
    tx_rate = get_field(output, "Transmit rate (Mbps)")

    return {
        "timestamp": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "ssid": ssid,
        "rssi_dbm": int(rssi),
        "signal_percent": (
            int(signal_match.group()) if signal_match else ""
        ),
        "band": band,
        "channel": channel,
        "receive_rate_mbps": rx_rate,
        "transmit_rate_mbps": tx_rate,
    }

def main():
    print("=== Wi-Fi Data Collection ===")

    location_id = input("Enter location ID (e.g. P1): ").strip()
    if not location_id:
        print("Location ID cannot be empty.")
        return

    try:
        x = float(input("Enter X coordinate in metres: "))
        y = float(input("Enter Y coordinate in metres: "))
        count = int(input("Number of readings (e.g. 10): "))
        interval = float(input("Interval in seconds (e.g. 2): "))

        if count < 1 or interval <= 0:
            raise ValueError
    except ValueError:
        print("Enter valid coordinates, a positive reading count,")
        print("and a positive interval.")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    columns = [
        "timestamp", "location_id", "x_m", "y_m", "ssid",
        "rssi_dbm", "signal_percent", "band", "channel",
        "receive_rate_mbps", "transmit_rate_mbps"
    ]

    file_needs_header = (
        not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0
    )

    try:
        with CSV_FILE.open(
            "a", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(file, fieldnames=columns)

            if file_needs_header:
                writer.writeheader()

            for i in range(count):
                measurement = get_wifi_measurement()

                if measurement is not None:
                    row = {
                        "timestamp": measurement["timestamp"],
                        "location_id": location_id,
                        "x_m": x,
                        "y_m": y,
                        **{
                            key: measurement[key]
                            for key in columns
                            if key in measurement
                        }
                    }
                    writer.writerow(row)
                    file.flush()

                    print(
                        f"Reading {i + 1}/{count}: "
                        f"RSSI = {measurement['rssi_dbm']} dBm, "
                        f"Signal = {measurement['signal_percent']}%"
                    )
                else:
                    print(f"Reading {i + 1}/{count}: skipped")

                if i < count - 1:
                    time.sleep(interval)

        print(f"\nCollection finished. Data saved to: {CSV_FILE}")

    except OSError as error:
        print("Could not save the CSV file:", error)

if __name__ == "__main__":
    main()
