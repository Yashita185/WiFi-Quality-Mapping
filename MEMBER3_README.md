# Member 3: Dead-Zone Detection Module

## Responsibility
Read the shared Wi-Fi measurement dataset, aggregate repeated RSSI measurements by location, classify signal quality, and produce potential dead-zone flags for the mapping module.

## Run
From the project root:

```bash
python detect_dead_zones.py
```

Input: `data/wifi_measurements.csv`
Output: `data/dead_zone_results.csv`

No additional packages are required by this module; it uses Python's standard library.

## Detection design
- Baseline: flag a location if any individual RSSI reading is below -80 dBm.
- Proposed method: flag a location if the mean of valid repeated RSSI readings is below -80 dBm.
- Quality categories: Strong (>= -50), Moderate (>= -60), Weak (>= -70), and Very Weak (< -70), all in dBm.
- The thresholds are initial project parameters, not universal Wi-Fi standards. Calibrate and justify them for the environment.
- RSSI-based classification indicates a potential dead zone; verify actual connectivity separately if possible.

## Existing project integration
`visualize_wifi.py` currently has its own dead-zone threshold of -60 dBm. That means a mean of -61 dBm is flagged as a potential dead zone, which conflicts with this module's -80 dBm design threshold. For consistent results, update the visualizer to read `data/dead_zone_results.csv` rather than recomputing status independently. See the instructions shared with the team.

## Important dataset note
The provided initial dataset has 25 readings across 5 locations. P2 uses 5 GHz while the other locations use 2.4 GHz, so comparisons between locations can be affected by band/channel differences. The current dataset may contain no readings below -80 dBm; if so, reporting zero detected dead zones is the honest result, not a failure of the program.
