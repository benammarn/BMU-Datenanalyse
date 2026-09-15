"""Führt Simulation und Analyse in einem Schritt aus."""

from pathlib import Path

from analyze_data import analyze_file
from generate_data import generate_dataset


def main() -> None:
    data_path = Path("data/simulated_bmu_data.csv")
    truth_path = Path("data/injected_faults.csv")
    findings_path = Path("results/findings.csv")
    plot_path = Path("results/measurement_overview.png")
    report_path = Path("results/bmu_report.html")

    generate_dataset(data_path, truth_path, seed=42, inject_faults=True)
    findings = analyze_file(data_path, findings_path, plot_path, report_path)

    print("BMU-Demonstrator erfolgreich ausgeführt.")
    print(f"Messpunkte: 600 | Erkannte Befunde: {len(findings)}")
    for rule_id, count in findings["rule_id"].value_counts().sort_index().items():
        print(f"  {rule_id}: {count}")


if __name__ == "__main__":
    main()

