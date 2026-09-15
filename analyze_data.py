"""Regelbasierte Plausibilitätsanalyse simulierter BMU-Messdaten."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import Thresholds


FINDING_COLUMNS = [
    "rule_id",
    "severity",
    "component",
    "start_time",
    "end_time",
    "duration_samples",
    "observed_value",
    "threshold",
    "description",
]


def _episodes(mask: pd.Series) -> list[tuple[int, int]]:
    """Wandelt eine boolesche Maske in zusammenhängende Indexbereiche um."""
    values = mask.fillna(False).to_numpy(dtype=bool)
    if not values.any():
        return []
    starts = np.flatnonzero(values & ~np.r_[False, values[:-1]])
    ends = np.flatnonzero(values & ~np.r_[values[1:], False])
    return list(zip(starts.tolist(), ends.tolist()))


def _append_episode_findings(
    findings: list[dict[str, object]],
    df: pd.DataFrame,
    mask: pd.Series,
    *,
    rule_id: str,
    severity: str,
    component: str,
    threshold: str,
    description: str,
    observed: Callable[[int, int], float | str],
) -> None:
    for start, end in _episodes(mask):
        findings.append(
            {
                "rule_id": rule_id,
                "severity": severity,
                "component": component,
                "start_time": df.loc[start, "timestamp"],
                "end_time": df.loc[end, "timestamp"],
                "duration_samples": end - start + 1,
                "observed_value": observed(start, end),
                "threshold": threshold,
                "description": description,
            }
        )


def analyze_dataframe(df: pd.DataFrame, thresholds: Thresholds | None = None) -> pd.DataFrame:
    """Prüft Datenqualität, Zellspannungen, Temperaturen und Packkonsistenz."""
    thresholds = thresholds or Thresholds()
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.sort_values("timestamp").reset_index(drop=True)

    cell_columns = sorted(column for column in df if column.startswith("cell_") and column.endswith("_voltage_v"))
    temp_columns = sorted(column for column in df if column.startswith("temp_") and column.endswith("_c"))
    required = ["timestamp", "pack_current_a", "soc_percent", "pack_voltage_v", *cell_columns, *temp_columns]
    missing_columns = [column for column in required if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Pflichtspalten fehlen: {', '.join(missing_columns)}")

    findings: list[dict[str, object]] = []

    for column in required:
        mask = df[column].isna()
        _append_episode_findings(
            findings,
            df,
            mask,
            rule_id="MISSING_VALUE",
            severity="WARNING",
            component=column,
            threshold="Wert vorhanden",
            description="Fehlender oder nicht interpretierbarer Messwert",
            observed=lambda _start, _end: "NaN",
        )

    for column in cell_columns:
        low_mask = df[column] < thresholds.cell_voltage_min_v
        high_mask = df[column] > thresholds.cell_voltage_max_v
        _append_episode_findings(
            findings,
            df,
            low_mask,
            rule_id="CELL_UNDERVOLTAGE",
            severity="CRITICAL",
            component=column,
            threshold=f">= {thresholds.cell_voltage_min_v:.2f} V",
            description="Zellspannung unter generischem Lern-Grenzwert",
            observed=lambda start, end, col=column: round(float(df.loc[start:end, col].min()), 4),
        )
        _append_episode_findings(
            findings,
            df,
            high_mask,
            rule_id="CELL_OVERVOLTAGE",
            severity="CRITICAL",
            component=column,
            threshold=f"<= {thresholds.cell_voltage_max_v:.2f} V",
            description="Zellspannung über generischem Lern-Grenzwert",
            observed=lambda start, end, col=column: round(float(df.loc[start:end, col].max()), 4),
        )

    cell_min = df[cell_columns].min(axis=1, skipna=True)
    cell_max = df[cell_columns].max(axis=1, skipna=True)
    cell_delta = cell_max - cell_min
    _append_episode_findings(
        findings,
        df,
        cell_delta > thresholds.cell_delta_max_v,
        rule_id="CELL_IMBALANCE",
        severity="WARNING",
        component="cell_voltage_group",
        threshold=f"Delta <= {thresholds.cell_delta_max_v:.3f} V",
        description="Spannungsdifferenz zwischen höchster und niedrigster Zelle auffällig",
        observed=lambda start, end: round(float(cell_delta.iloc[start : end + 1].max()), 4),
    )

    for column in temp_columns:
        _append_episode_findings(
            findings,
            df,
            df[column] > thresholds.temperature_max_c,
            rule_id="OVER_TEMPERATURE",
            severity="CRITICAL",
            component=column,
            threshold=f"<= {thresholds.temperature_max_c:.1f} °C",
            description="Temperatur über generischem Lern-Grenzwert",
            observed=lambda start, end, col=column: round(float(df.loc[start:end, col].max()), 2),
        )

        rolling_std = df[column].rolling(thresholds.frozen_sensor_window).std()
        frozen_mask = rolling_std <= thresholds.frozen_sensor_std_max
        _append_episode_findings(
            findings,
            df,
            frozen_mask,
            rule_id="FROZEN_SENSOR",
            severity="WARNING",
            component=column,
            threshold=f"keine konstante Folge über {thresholds.frozen_sensor_window} Werte",
            description="Mögliches eingefrorenes Sensorsignal erkannt",
            observed=lambda start, _end, col=column: round(float(df.loc[start, col]), 2),
        )

    temp_spread = df[temp_columns].max(axis=1, skipna=True) - df[temp_columns].min(axis=1, skipna=True)
    _append_episode_findings(
        findings,
        df,
        temp_spread > thresholds.temperature_spread_max_c,
        rule_id="TEMPERATURE_SPREAD",
        severity="WARNING",
        component="temperature_sensor_group",
        threshold=f"Delta <= {thresholds.temperature_spread_max_c:.1f} °C",
        description="Temperaturdifferenz zwischen Sensoren auffällig",
        observed=lambda start, end: round(float(temp_spread.iloc[start : end + 1].max()), 2),
    )

    voltage_sum = df[cell_columns].sum(axis=1, min_count=len(cell_columns))
    pack_difference = (df["pack_voltage_v"] - voltage_sum).abs()
    _append_episode_findings(
        findings,
        df,
        pack_difference > thresholds.pack_voltage_tolerance_v,
        rule_id="PACK_VOLTAGE_MISMATCH",
        severity="WARNING",
        component="pack_voltage_v",
        threshold=f"Abweichung <= {thresholds.pack_voltage_tolerance_v:.2f} V",
        description="Packspannung passt nicht zur Summe der Zellspannungen",
        observed=lambda start, end: round(float(pack_difference.iloc[start : end + 1].max()), 3),
    )

    result = pd.DataFrame(findings, columns=FINDING_COLUMNS)
    if not result.empty:
        result = result.sort_values(["start_time", "severity", "rule_id"]).reset_index(drop=True)
    return result


def create_overview_plot(df: pd.DataFrame, output_path: Path) -> None:
    cell_columns = sorted(column for column in df if column.startswith("cell_") and column.endswith("_voltage_v"))
    temp_columns = sorted(column for column in df if column.startswith("temp_") and column.endswith("_c"))
    time_s = np.arange(len(df))

    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    for column in cell_columns:
        axes[0].plot(time_s, df[column], linewidth=0.8, alpha=0.8)
    axes[0].set_ylabel("Zellspannung [V]")
    axes[0].set_title("Simulierte BMU-Messdaten – Überblick")
    axes[0].grid(alpha=0.25)

    for column in temp_columns:
        axes[1].plot(time_s, df[column], linewidth=1.0, label=column.replace("_c", ""))
    axes[1].set_ylabel("Temperatur [°C]")
    axes[1].legend(ncol=4, fontsize=8)
    axes[1].grid(alpha=0.25)

    axes[2].plot(time_s, df["pack_current_a"], color="#6a3d9a")
    axes[2].axhline(0.0, color="black", linewidth=0.7)
    axes[2].set_ylabel("Strom [A]")
    axes[2].grid(alpha=0.25)

    axes[3].plot(time_s, df["soc_percent"], color="#1f78b4")
    axes[3].set_ylabel("SOC [%]")
    axes[3].set_xlabel("Zeit [s]")
    axes[3].grid(alpha=0.25)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def create_html_report(findings: pd.DataFrame, plot_name: str, output_path: Path) -> None:
    severity_counts = findings["severity"].value_counts().to_dict() if not findings.empty else {}
    rows = []
    for row in findings.itertuples(index=False):
        rows.append(
            "<tr>"
            f"<td>{escape(str(row.start_time))}</td>"
            f"<td>{escape(str(row.rule_id))}</td>"
            f"<td>{escape(str(row.severity))}</td>"
            f"<td>{escape(str(row.component))}</td>"
            f"<td>{escape(str(row.observed_value))}</td>"
            f"<td>{escape(str(row.threshold))}</td>"
            f"<td>{escape(str(row.description))}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>BMU-Befundbericht</title>
<style>
body{{font-family:Arial,sans-serif;margin:36px;color:#202020}} h1,h2{{color:#1c033c}}
.notice{{background:#f2eff8;border-left:5px solid #371e77;padding:12px}}
.cards{{display:flex;gap:12px;margin:18px 0}} .card{{border:1px solid #ddd;padding:12px;min-width:120px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #ddd;padding:7px;text-align:left}}
th{{background:#1c033c;color:white}} tr:nth-child(even){{background:#f7f7f7}} img{{max-width:100%}}
</style></head><body>
<h1>BMU-Datenanalyse – Befundbericht</h1>
<p class="notice"><strong>Demonstrator:</strong> vollständig simulierte Daten und generische Lern-Grenzwerte. Keine BMW-Daten und keine freigegebene technische Spezifikation.</p>
<div class="cards"><div class="card"><strong>{len(findings)}</strong><br>Gesamtbefunde</div>
<div class="card"><strong>{severity_counts.get('CRITICAL', 0)}</strong><br>Kritisch</div>
<div class="card"><strong>{severity_counts.get('WARNING', 0)}</strong><br>Warnungen</div></div>
<h2>Messdatenübersicht</h2><img src="{escape(plot_name)}" alt="Übersicht der simulierten BMU-Messdaten">
<h2>Erkannte Auffälligkeiten</h2>
<table><thead><tr><th>Startzeit</th><th>Regel</th><th>Stufe</th><th>Komponente</th><th>Wert</th><th>Grenze</th><th>Beschreibung</th></tr></thead>
<tbody>{''.join(rows) if rows else '<tr><td colspan="7">Keine Auffälligkeiten erkannt.</td></tr>'}</tbody></table>
<p><small>Ein Befund markiert eine Auffälligkeit. Die endgültige technische Ursache muss durch qualifiziertes Fachpersonal geprüft werden.</small></p>
</body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def analyze_file(input_path: Path, findings_path: Path, plot_path: Path, report_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    findings = analyze_dataframe(df)
    findings_path.parent.mkdir(parents=True, exist_ok=True)
    findings.to_csv(findings_path, index=False)
    create_overview_plot(df, plot_path)
    create_html_report(findings, plot_path.name, report_path)
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/simulated_bmu_data.csv"))
    parser.add_argument("--findings", type=Path, default=Path("results/findings.csv"))
    parser.add_argument("--plot", type=Path, default=Path("results/measurement_overview.png"))
    parser.add_argument("--report", type=Path, default=Path("results/bmu_report.html"))
    args = parser.parse_args()

    findings = analyze_file(args.input, args.findings, args.plot, args.report)
    print(f"{len(findings)} Befunde erzeugt: {args.findings}")
    print(f"Diagramm: {args.plot}")
    print(f"HTML-Bericht: {args.report}")


if __name__ == "__main__":
    main()

