# Wi-Fi Quality Mapping — Wi-Fi Quality Mapping & Dead-Zone Diagnostics

A local Streamlit application for analyzing Wi-Fi RSSI measurements across a set of mapped locations. It combines an interactive spatial coverage view, signal-quality summaries, variability diagnostics, threshold-based low-coverage flags, data validation, and downloadable reports.

## Features

- **Interactive coverage plane:** hoverable location points, coordinates, mean/min/max RSSI, reading count, quality category, and status.
- **Estimated coverage surface:** inverse-distance-weighted interpolation between measured points. This is a visualization estimate, not a replacement for measurements.
- **Diagnostics:** mean, min/max, standard deviation, percentage of readings below -67 dBm, and threshold-based potential dead-zone flags.
- **Method comparison:** compares an any-reading baseline with a mean-based decision to illustrate the effect of outliers.
- **Data explorer:** filter readings, inspect data quality, upload a CSV for inspection, and export the current measurements.
- **Reports:** downloadable text and HTML analysis summaries.
- **Measurement entry:** add a manually recorded reading or prefill network details from Windows `netsh`.
- **Tests:** unit tests for data cleaning, summary calculations, signal classes, and interpolation preconditions.

## Requirements

- Python 3.10 or newer recommended
- Windows for the optional live scan button (`netsh`); all CSV analysis and dashboard features can run on other platforms

## Run on Windows (PowerShell)

Open the extracted project folder in VS Code. Make sure the terminal is in the directory containing `app.py` and `requirements.txt`.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`.

If `requirements.txt` is in a nested folder, use `dir` to locate the folder containing both `app.py` and `requirements.txt`, then `cd` into it before running the commands.

## Run the analysis tests

```powershell
py -m unittest discover -s tests -v
```

## Data format

The main input file is `data/wifi_measurements.csv`. It expects columns such as `timestamp`, `location_id`, `x_m`, `y_m`, `ssid`, `rssi_dbm`, `signal_percent`, `band`, `channel`, `receive_rate_mbps`, and `transmit_rate_mbps`. Missing optional columns are added during normalization; rows without a location, coordinates, or valid RSSI are excluded from spatial analysis.

## Interpretation and limitations

- RSSI is a useful received-signal indicator, but it does not alone measure internet throughput, packet loss, latency, or prove that a location has no connectivity.
- Default dead-zone threshold is **mean RSSI below -80 dBm**. Calibrate it for the environment and intended use.
- Signal categories are heuristic: Excellent ≥ -50 dBm, Good ≥ -60 dBm, Fair ≥ -67 dBm, Weak ≥ -75 dBm, Very weak < -75 dBm.
- Windows `netsh` generally reports signal percentage rather than raw RSSI. The app labels its conversion as an estimate; use measured RSSI when available.
- The interpolation surface is an estimated guide between measured locations. Do not present it as directly measured coverage.
- The included dataset is a small example dataset. For a meaningful evaluation, take repeated readings at more positions, at consistent intervals, and record the conditions under which each sample was collected.

## Project modules

- `app.py` — dashboard and user interaction
- `analysis_core.py` — reusable, testable data cleaning and analysis logic
- `wifi_collector.py` — command-line measurement collection
- `validate_data.py` — data validation utility
- `analyze_data.py` — statistical summary utility
- `detect_dead_zones.py` — command-line dead-zone analysis utility
- `generate_report.py` — existing report utility
- `tests/` — automated unit tests


## Dark interface and presentation guide

The app uses a dark navy theme with teal accents. At the top of the dashboard, expand **How to explain Wi-Fi Quality Mapping during your project review** for a concise walkthrough. Each tab also includes a short explanation of how to interpret the map, diagnostics, measurements, or report.

## What the metrics mean

- **Mean RSSI:** average signal power across readings at one location; values closer to 0 dBm are stronger.
- **Minimum / maximum RSSI:** weakest and strongest recorded readings at that location.
- **Standard deviation:** spread of readings; larger values indicate more variability.
- **Dead-zone threshold:** a user-selected cutoff. A location is flagged when its mean RSSI is below the cutoff. This is a potential weak-coverage flag, not proof of no connectivity.
- **Coverage surface:** inverse-distance-weighted interpolation between measured points. It is an estimate, not additional observed data.

For a defensible demonstration, collect multiple readings at each position under similar conditions and include more spatial points than the small example dataset.
