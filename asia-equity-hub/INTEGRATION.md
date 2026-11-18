# Integration in `dividenden-rechner/aktien-hub`

Das Projekt ist eigenständig lauffähig und lässt sich als Unterordner in `aktien-hub` übernehmen. Ich habe nichts in dein Repository gepusht.

## Schritte
1. Ordner `asia-equity-hub/` (Inhalt dieses ZIPs, **ohne** `integration/`) ins Repo-Wurzelverzeichnis kopieren.
2. `integration/aktien-hub/.github/workflows/asien-geschaeftsberichte.yml` nach `.github/workflows/` im Repo kopieren.
   Der Workflow hält sich an deine bestehende Konvention (wie `asien-fundamente.yml`): `workflow_dispatch`, Commit als `kurse-bot`, Push mit 3 Versuchen.
3. Optional sofort: `integration/aktien-hub/asien-geschaeftsberichte.json` nach `data/` kopieren (aktueller Export, 5 Firmen).
4. Workflow einmal manuell starten: Er testet, lädt die PDFs, extrahiert, prüft (bricht bei Inkonsistenz ab), schreibt `data/asien-geschaeftsberichte.json` und committet.

## Datenformat `data/asien-geschaeftsberichte.json`
Gleiches Grundschema wie `data/asien-fundamente.json` (`stand`, `anzahl`, `firmen[]`, Ticker im Yahoo-Format wie `D05.SI`).
Je Firma: `eps_jahr`, `dps_jahr` (mit `*_einheit`/`*_waehrung`), `werte.{umsatz, konzerngewinn_aktionaere, bilanzsumme, eigenkapital, operativer_cashflow, free_cashflow, ...}` mit `wert`, `einheit`, `waehrung`, `pdf_seite`, `druckseite`, sowie `kennzahlen`, `pruefungen` und `pruefstatus`.

Wichtig für die Anzeige:
- `einheit` beachten (`million`, `thousand` bei BYD, `cents` bei First Pacific EPS/DPS).
- Keine Umrechnung zwischen Währungen.
- Hinweis „maschinell extrahiert, menschliche Prüfung ausstehend“ anzeigen, solange `pruefstatus.mensch` = `pending` ist.

## Pflege
- Neues Geschäftsjahr: URL im Katalog eintragen (Kandidaten über `GET /v1/reports/{symbol}/discover-asia`), PDF laden, Profil kopieren und Seiten/Labels anpassen, `extract_reports.py` laufen lassen. Erst wenn der Status `extracted_consistent` ist, Werte veröffentlichen.
- Ersetzt ein Emittent sein PDF, schlägt der Download wegen SHA-256-Abweichung fehl. Das ist Absicht: neu prüfen, dann die Prüfsumme aktualisieren.
- Die PDFs selbst werden nicht eingecheckt (`.gitignore`, Urheberrecht der Emittenten).

## Zweijahreshistorie ab v1.2

`python build_history.py` erzeugt `reports/history/history_2024_2025.json` aus den vorhandenen `reports/extracted/*_2025.json`. Die Datei kann als zusätzliche, separate Datenquelle in `dividenden-rechner/aktien-hub` übernommen werden. Sie ersetzt **nicht** `data/asien-geschaeftsberichte.json` und ändert das bestehende Exportschema nicht.

Die Datensätze enthalten `years.2024.facts` und `years.2025.facts` je Emittent. 2024 hat den Status `comparative_extracted_pending_review` und die Herkunft `source_report_year: 2025`. Nur angegebene Felder anzeigen; fehlende Felder nicht mit null oder 0 gleichsetzen. Einheiten und Währungen je Feld berücksichtigen. Keine automatische Kennzeichnung als menschlich geprüft.

Jardine Matheson ist unter `reports/coverage/company_queue.json` als Kandidat eingetragen. Es wird erst nach echtem PDF-Download, Hash-Pinning, Extraktionsprofil und Tests in den produktiven Export aufgenommen.

## Abdeckungsmatrix v1.3 (2020–2025)

`python plan_history.py` erstellt `reports/coverage/coverage_2020_2025.json`. Diese Datei zeigt für 10 Firmen pro Jahr `status`, `fact_count`, `source_report_year` und `human_review`. Sie ist ein **Arbeits- und Lückenplan**, keine vollständige Kurs- oder Fundamentalhistorie. Im Ziel-Repository separat einbinden; `missing` nie als 0 interpretieren. Neue Firmen aus `reports/coverage/company_queue.json` erst nach PDF-Download, SHA-Pinning, Profil und Tests in den produktiven Datenexport übernehmen.

## v1.5: Unternehmensuniversum
- `reports/universe/requested_companies.txt`: ursprüngliche Namensliste (5 Märkte, 451 gewünschte Markteinträge).
- `reports/universe/companies.json`: maschinenlesbarer Katalog; `ticker: null` heißt ungeprüft, **nicht** unbekanntes Finanzinstrument erraten.
- `reports/coverage/universe_history_2016_2025.json`: reine Arbeitsmatrix mit `not_assessed`, **keine** finanzielle Datenquelle.
- Nicht automatisch mit `data/asien-geschaeftsberichte.json` vermischen: dort stehen bereits tatsächlich extrahierte Finanzdaten mit eigenen Nachweisen. Ein späterer Identity-Mapping-Schritt muss Unternehmen, Börsenlisting und Ticker gesondert abgleichen.

## v1.6: im Repository aktien-hub
- Projekt liegt unter `asia-equity-hub/` (ohne `integration/`, ohne PDFs und ohne heruntergeladene Rohlisten).
- `.github/workflows/asien-geschaeftsberichte.yml`: Tests → PDFs laden → Extraktion → Zehnjahreshistorie → Export nach `data/asien-geschaeftsberichte.json` → Commit als `kurse-bot`.
- `.github/workflows/asien-universum.yml`: lädt die offiziellen Listen neu, baut `identity_map.json` und `annual_report_sources.json` neu und committet sie.
- Neue Daten (noch nicht von der Website gelesen): `asia-equity-hub/reports/universe/identity_map.json`, `asia-equity-hub/reports/sources/annual_report_sources.json`, `asia-equity-hub/reports/history/ten_year_2016_2025.json`.
- Ticker-Format wie in `data/` (Yahoo: `0700.HK`, `D05.SI`, `600519.SS`, `7203.T`, `005930.KS`). Koreanische Ticker sind ungeprüfte Kandidaten.
