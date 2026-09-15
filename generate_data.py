"""Erzeugt reproduzierbare, vollständig simulierte BMU-Messdaten."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


CELL_COUNT = 12
TEMPERATURE_SENSOR_COUNT = 4
SAMPLE_COUNT = 600
SAMPLE_PERIOD_SECONDS = 1.0
NOMINAL_CAPACITY_AH = 60.0


def _current_profile(sample_count: int, rng: np.random.Generator) -> np.ndarray:
    current = np.zeros(sample_count)
    current[50:180] = 62.0
    current[180:300] = 88.0
    current[300:410] = -42.0
    current[410:520] = 36.0
    current[520:] = 5.0
    return current + rng.normal(0.0, 1.2, sample_count)


def _calculate_soc(current_a: np.ndarray) -> np.ndarray:
    # Konvention im Demonstrator: positiver Strom = Entladen.
    delta_soc = -(current_a * SAMPLE_PERIOD_SECONDS) / (NOMINAL_CAPACITY_AH * 3600.0) * 100.0
    return np.clip(76.0 + np.cumsum(delta_soc), 0.0, 100.0)


def generate_dataset(
    output_path: Path,
    ground_truth_path: Path | None = None,
    *,
    seed: int = 42,
    inject_faults: bool = True,
) -> pd.DataFrame:
    """Generiert ein vereinfachtes Batteriesignalmodell und optionale Fehlerfälle."""
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2026-09-15 08:00:00", periods=SAMPLE_COUNT, freq="s")
    current_a = _current_profile(SAMPLE_COUNT, rng)
    soc_percent = _calculate_soc(current_a)

    data: dict[str, object] = {
        "timestamp": timestamps,
        "operating_state": np.where(
            current_a > 5.0,
            "DISCHARGE",
            np.where(current_a < -5.0, "CHARGE", "REST"),
        ),
        "pack_current_a": current_a,
        "soc_percent": soc_percent,
    }

    # Vereinfachte OCV-Näherung plus lastabhängiger Spannungseinbruch.
    base_voltage = 3.55 + 0.0060 * soc_percent - 0.00045 * current_a
    cell_offsets = rng.normal(0.0, 0.004, CELL_COUNT)
    for cell_index in range(1, CELL_COUNT + 1):
        data[f"cell_{cell_index:02d}_voltage_v"] = (
            base_voltage
            + cell_offsets[cell_index - 1]
            + rng.normal(0.0, 0.002, SAMPLE_COUNT)
        )

    heating = np.cumsum(np.abs(current_a)) * 0.000035
    for sensor_index in range(1, TEMPERATURE_SENSOR_COUNT + 1):
        data[f"temp_{sensor_index:02d}_c"] = (
            26.0
            + heating
            + (sensor_index - 1) * 0.35
            + rng.normal(0.0, 0.08, SAMPLE_COUNT)
        )

    df = pd.DataFrame(data)
    cell_columns = [f"cell_{index:02d}_voltage_v" for index in range(1, CELL_COUNT + 1)]
    df["pack_voltage_v"] = df[cell_columns].sum(axis=1) + rng.normal(0.0, 0.04, SAMPLE_COUNT)

    truth: list[dict[str, object]] = []
    if inject_faults:
        df.loc[180:204, "cell_07_voltage_v"] -= 0.16
        truth.append(
            {
                "fault_id": "F01",
                "expected_rule": "CELL_IMBALANCE",
                "start_index": 180,
                "end_index": 204,
                "component": "cell_07_voltage_v",
                "description": "Künstlich abgesenkte Zellspannung",
            }
        )

        df.loc[330:354, "temp_03_c"] += 35.0
        truth.append(
            {
                "fault_id": "F02",
                "expected_rule": "OVER_TEMPERATURE",
                "start_index": 330,
                "end_index": 354,
                "component": "temp_03_c",
                "description": "Künstliche lokale Übertemperatur",
            }
        )

        df.loc[420:449, "temp_02_c"] = float(df.loc[420, "temp_02_c"])
        truth.append(
            {
                "fault_id": "F03",
                "expected_rule": "FROZEN_SENSOR",
                "start_index": 420,
                "end_index": 449,
                "component": "temp_02_c",
                "description": "Eingefrorenes Temperatursignal",
            }
        )

        df.loc[500, "cell_10_voltage_v"] = np.nan
        truth.append(
            {
                "fault_id": "F04",
                "expected_rule": "MISSING_VALUE",
                "start_index": 500,
                "end_index": 500,
                "component": "cell_10_voltage_v",
                "description": "Fehlender Zellspannungswert",
            }
        )

        df.loc[540:549, "pack_voltage_v"] += 2.0
        truth.append(
            {
                "fault_id": "F05",
                "expected_rule": "PACK_VOLTAGE_MISMATCH",
                "start_index": 540,
                "end_index": 549,
                "component": "pack_voltage_v",
                "description": "Inkonsistenz zwischen Pack- und Zellspannungssumme",
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.5f")

    if ground_truth_path is not None:
        ground_truth_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(truth).to_csv(ground_truth_path, index=False)

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/simulated_bmu_data.csv"))
    parser.add_argument("--ground-truth", type=Path, default=Path("data/injected_faults.csv"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = generate_dataset(args.output, args.ground_truth, seed=args.seed)
    print(f"{len(df)} Messpunkte erzeugt: {args.output}")
    print(f"Definierte Fehlerfälle: {args.ground_truth}")


if __name__ == "__main__":
    main()

