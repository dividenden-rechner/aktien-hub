# Changelog – Americas Equity Hub

## v0.3 (2026-11-20) – Rechte-Gate, Brasilien, Kanada/Mexiko über SEC
- Rechte-Register `data/rights/source_license.json` (12 Quellen × 7 Zwecke, AGB-URL, Abrufdatum, Textbeleg) und
  Export-Sperre `app/rights.py`: öffentlicher Export nur bei `allowed` für Speichern, öffentliche API und kommerzielle Nutzung.
- **Entfernt:** S&P/TSX-Composite-Proxy aus der BlackRock-XIC-Bestandsliste (Bedingungen verbieten öffentliche/kommerzielle
  Nutzung) samt Kanada-Hub-Dateien `*.TO`; FIRDS-ISINs (Rechte für das Register ungeklärt). Die Git-Historie enthält die
  frühere Datei weiterhin.
- Brasilien aus CVM Dados Abertos (ODbL): Emittenten, Wertpapiere (ON/PN/PNA/PNB/PNC/PND/Units), Notierungen inkl. beendeter,
  DFP 2010–2025 mit Referenz je Wert, Dividenden/JCP/gemischt getrennt, LEI über GLEIF.
- Kanada und Mexiko: Universum aus SEC-Stammdaten (Sitz), LEI/ISIN aus GLEIF (CC0), Finanzen aus SEC-XBRL.
- Workflows `americas-sec.yml` (wöchentlich), `americas-brasilien.yml` (monatlich); `americas-kanada.yml` entfällt.

## v0.2 (2026-11-19) – Kanada (S&P/TSX Composite) – ersetzt durch v0.3
## v0.1 (2026-11-19) – Quellenprüfung
