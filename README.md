# Wi-Fi Network Quality Mapping and Dead-Zone Detection System

## 1. Project Overview

This project measures Wi-Fi signal strength at multiple physical locations to support network quality mapping and dead-zone detection.

My contribution focuses on collecting Wi-Fi measurements, storing them in CSV format, summarizing signal strength, and validating the collected dataset.

## 2. Tools and Technologies

- Python 3
- Windows Command Prompt / PowerShell
- VS Code
- Windows `netsh` command
- CSV files for measurement storage

## 3. Module Files

- `wifi_collector.py` — collects Wi-Fi measurements at specified locations.
- `analyze_data.py` — calculates RSSI statistics for each location.
- `validate_data.py` — checks the dataset for missing fields, invalid values, duplicate records, and measurement consistency.
- `data/wifi_measurements.csv` — stores the raw measurement records.
- `data/wifi_summary.csv` — stores the summarized RSSI statistics.

## 4. Execution Instructions

Run the commands from the project root directory:

```bash
python wifi_collector.py
python validate_data.py
python analyze_data.py
```

The collector asks for the location identifier, coordinates, number of readings, and interval between readings.

## 5. Initial Dataset

- Number of locations: 5
- Readings per location: 5
- Total readings: 25
- Locations: P1, P2, P3, P4, P5

## 6. Initial Results

| Location | Mean RSSI |
|---|---:|
| P1 | -55.0 dBm |
| P2 | -61.0 dBm |
| P3 | -46.2 dBm |
| P4 | -54.4 dBm |
| P5 | -53.0 dBm |

P3 recorded the strongest mean signal, while P2 recorded the weakest mean signal in this initial dataset. These results identify locations for further investigation but do not independently establish a dead zone.

## 7. Dataset Validation

The validation script reported:

- 25 data rows across 5 locations
- 5 readings per location
- No exact duplicate rows
- No missing required fields or invalid values detected

The dataset contains 20 readings on 2.4 GHz, channel 13, and 5 readings on 5 GHz, channel 40. This variation should be considered during further analysis.

## 8. Limitations

- RSSI fluctuates due to environmental conditions and device behaviour.
- Location coordinates must represent the actual measurement positions.
- Signal percentage and RSSI may not provide identical information.
- Receive and transmit link rates do not directly measure actual internet throughput.
- RSSI alone is insufficient to establish a Wi-Fi dead zone.
- The initial dataset is small and requires additional measurements for stronger conclusions.

## 9. Team Handoff

The validated measurement CSV can be used by the mapping module to visualize Wi-Fi quality across locations. The summary and raw readings can also support the dead-zone detection module, which should define and evaluate its detection criteria.

Testing, integration, final evaluation, documentation review, and presentation are shared responsibilities of all team members.