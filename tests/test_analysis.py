"""Automatische Plausibilitätsprüfungen für den Demonstrator."""

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from analyze_data import analyze_dataframe  # noqa: E402
from generate_data import generate_dataset  # noqa: E402


class BMUAnalysisTests(unittest.TestCase):
    def test_injected_faults_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "data.csv"
            df = generate_dataset(data_path, seed=42, inject_faults=True)
            findings = analyze_dataframe(df)
            detected = set(findings["rule_id"])
            expected = {
                "CELL_IMBALANCE",
                "OVER_TEMPERATURE",
                "TEMPERATURE_SPREAD",
                "FROZEN_SENSOR",
                "MISSING_VALUE",
                "PACK_VOLTAGE_MISMATCH",
            }
            self.assertTrue(expected.issubset(detected), expected - detected)

    def test_normal_dataset_has_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "normal.csv"
            df = generate_dataset(data_path, seed=42, inject_faults=False)
            findings = analyze_dataframe(df)
            self.assertTrue(findings.empty, findings.to_dict("records"))

    def test_missing_required_column_raises_error(self) -> None:
        frame = pd.DataFrame({"timestamp": ["2026-09-15 08:00:00"]})
        with self.assertRaises(ValueError):
            analyze_dataframe(frame)


if __name__ == "__main__":
    unittest.main()

