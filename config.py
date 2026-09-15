"""Konfigurierbare Lern-Grenzwerte für den BMU-Demonstrator.

Die Werte sind bewusst generisch und stellen keine BMW-Spezifikation dar.
Für ein reales Batteriesystem müssten Zellchemie, Architektur, Betriebszustand
und freigegebene Prüfanforderungen berücksichtigt werden.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    cell_voltage_min_v: float = 3.00
    cell_voltage_max_v: float = 4.25
    cell_delta_max_v: float = 0.08
    temperature_max_c: float = 55.0
    temperature_spread_max_c: float = 15.0
    pack_voltage_tolerance_v: float = 0.80
    frozen_sensor_window: int = 15
    frozen_sensor_std_max: float = 1e-9

