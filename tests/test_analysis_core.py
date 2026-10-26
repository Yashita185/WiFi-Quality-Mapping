import unittest
import pandas as pd
from analysis_core import clean_measurements, summarize_locations, classify_signal, idw_grid

class AnalysisCoreTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            "location_id": ["p1", "P1", "P2", "P2", "bad"],
            "x_m": [0, 0, 2, 2, "oops"], "y_m": [0, 0, 0, 0, 1],
            "rssi_dbm": [-50, -54, -82, -78, -60], "ssid": ["net"]*5,
        })

    def test_cleaning_normalizes_ids_and_removes_invalid_rows(self):
        cleaned = clean_measurements(self.df)
        self.assertEqual(len(cleaned), 4)
        self.assertEqual(set(cleaned.location_id), {"P1", "P2"})

    def test_summary_aggregates_and_flags_threshold(self):
        cleaned = clean_measurements(self.df)
        summary = summarize_locations(cleaned, -79)
        p2 = summary[summary.location_id == "P2"].iloc[0]
        self.assertEqual(p2.readings, 2)
        self.assertEqual(p2.status, "Potential dead zone")
        self.assertAlmostEqual(p2.mean_rssi_dbm, -80)
        self.assertEqual(summary[summary.location_id == "P1"].iloc[0].status, "Coverage acceptable")

    def test_signal_categories(self):
        self.assertEqual(classify_signal(-45), "Excellent")
        self.assertEqual(classify_signal(-58), "Good")
        self.assertEqual(classify_signal(-65), "Fair")
        self.assertEqual(classify_signal(-72), "Weak")
        self.assertEqual(classify_signal(-90), "Very weak")

    def test_interpolation_requires_three_points(self):
        two = summarize_locations(clean_measurements(self.df).query("location_id == 'P1'"))
        self.assertIsNone(idw_grid(two))

if __name__ == "__main__":
    unittest.main(verbosity=2)
