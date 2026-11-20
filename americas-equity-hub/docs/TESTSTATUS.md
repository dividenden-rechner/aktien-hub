# Teststatus – Americas Equity Hub

Nur tatsächlich ausgeführte Tests. Aufruf: `cd americas-equity-hub && python3 -m pytest -q tests`

| Bereich | Tests | Stand 2026-11-20 |
|---|---|---|
| ISIN-Prüfziffern (gültig/ungültig) | 11 | bestanden |
| Rechte-Gate (Register vollständig, publizierbar je Quelle, unknown/restricted ≠ allowed, gemischte Quellen, Feldfilter) | 17 | bestanden |
| Hub-Export: gesperrte ISIN wird nicht ausgegeben; veröffentlichte Hub-Dateien nur aus SEC/CVM, keine `.TO`-Altlast, Brasilien ohne ISIN | 2 | bestanden |
| Brasilien: Gattungen, Einheiten (EPS nie skaliert), Kontoauswahl Bank/Industrie, Dividenden vs. JCP vs. gemischt, Konzern-Ersatzspalte, Bankenlayout nicht raten, Rückbuchung | 7 | bestanden |
| Brasilien erzeugte Daten: Dubletten, Trennung Emittent/Wertpapier/Notierung, MIC, Provenienz je Fakt, Geschäftsperioden, Einheiten | 2 | bestanden |
| Kanada/Mexiko: Aktien-ISIN-Filter (Anleihen raus, mehrdeutig leer), Sitzcodes | 2 | bestanden |
| Kanada/Mexiko erzeugte Daten (Dubletten, ISIN gültig, Quellen, MIC) | 2 | übersprungen bis zum ersten Workflow-Lauf |

Nicht getestet (keine Daten mit Freigabe): Kursadjustierungen, Kurszeitreihen, Dividende je Aktie/Ex-Tage, Indexmitgliedschaften.
Bestehende Suiten (asia-equity-hub, europe-equity-hub) werden vor jedem Merge mit ausgeführt.
