# BMU-Datenanalyse und regelbasierte Fehlerbefundung

Ein kompakter Python-Demonstrator zur strukturierten Analyse vollständig simulierter Messdaten eines vereinfachten Hochvoltspeichers.

> **Wichtiger Hinweis:** Dieses Lernprojekt verwendet ausschließlich selbst erzeugte Daten und generische, frei konfigurierte Schwellenwerte. Es enthält keine BMW-Daten und bildet keine konkrete BMW-BMU oder freigegebene Batteriespezifikation ab.

## Ziel

Der Demonstrator verbindet Datenanalyse mit einer nachvollziehbaren technischen Befundlogik:

1. Zeitreihen für zwölf Zellspannungen, vier Temperaturen, Packstrom, Packspannung und SOC simulieren.
2. Definierte Fehlerfälle kontrolliert einfügen.
3. Datenqualität und technische Plausibilität regelbasiert prüfen.
4. Messverläufe visualisieren.
5. Auffälligkeiten in einem Befundbericht dokumentieren.

## Enthaltene Fehlerfälle

- auffällige Zellspannungsdifferenz
- lokale Übertemperatur und hohe Temperaturspreizung
- eingefrorenes Temperatursignal
- fehlender Zellspannungswert
- Inkonsistenz zwischen Packspannung und Summe der Zellspannungen

## Projektstruktur

```text
bmu-data-analysis/
├── config.py                 # Konfigurierbare Lern-Grenzwerte
├── generate_data.py          # Simulation und kontrollierte Fehlerfälle
├── analyze_data.py           # Regeln, Diagramm und HTML-Bericht
├── run_pipeline.py           # Kompletter Ablauf mit einem Befehl
├── data/
│   ├── simulated_bmu_data.csv
│   └── injected_faults.csv
├── results/
│   ├── findings.csv
│   ├── measurement_overview.png
│   └── bmu_report.html
└── tests/test_analysis.py
```

## Ausführen

Im Projektordner:

```bash
python3 -m pip install -r requirements.txt
python3 run_pipeline.py
```

Danach kann `results/bmu_report.html` im Browser geöffnet werden.

Tests starten:

```bash
python3 -m unittest discover -s tests -v
```

## Analyseprinzip

Der Kern ist bewusst regelbasiert und transparent. Beispiele:

- Zellspreizung: `max(Zellspannungen) - min(Zellspannungen)`
- Temperaturspreizung: `max(Temperaturen) - min(Temperaturen)`
- Packkonsistenz: `abs(Packspannung - Summe der Zellspannungen)`
- Datenqualität: fehlende Werte und über ein Zeitfenster konstante Sensorsignale

Ein Befund ist noch keine endgültige Fehlerursache. In einem realen Entwicklungsprozess wären zusätzliche Messungen, Testbedingungen, Diagnoseinformationen, freigegebene Grenzwerte und eine fachliche Bewertung erforderlich.

## Kurzer Gesprächs-Pitch

> Ich habe einen ersten Python-Demonstrator für mein BMU-Eigenprojekt umgesetzt. Er erzeugt vollständig simulierte Zeitreihen für Zellspannungen, Temperaturen, Strom und SOC und fügt kontrolliert definierte Fehlerfälle ein. Anschließend prüft er die Daten mit transparenten Plausibilitätsregeln, visualisiert die Messverläufe und erstellt einen strukturierten Befundbericht. Die Werte sind generische Lernwerte und keine BMW-Spezifikation. Mir ging es vor allem darum, einen nachvollziehbaren Ablauf von der Messdatei bis zur dokumentierten Auffälligkeit aufzubauen.

## Sinnvolle nächste Schritte

- Regeln abhängig vom Betriebszustand auswerten
- CAN-/MDF-Messdateien über geeignete Bibliotheken einlesen
- Konfiguration aus YAML laden
- Ergebnisse mit bekannten Fehlerlabels quantitativ bewerten
- Bericht um Fotodokumentation und Review-Status erweitern
- KI nur für freigegebene Zusammenfassungsaufgaben testen; technische Befunde weiterhin menschlich validieren

