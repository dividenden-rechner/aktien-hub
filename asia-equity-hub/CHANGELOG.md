# Changelog

## v1.1 (2026-11-18)

### Neu
- **Echte PDF-Verarbeitung der fünf Geschäftsberichte GJ 2025** (DBS, BYD, CK Hutchison, Swire Pacific, First Pacific): Download über den Projektcode, SHA-256 im Katalog fixiert.
- `app/statement_extractor.py`: profilbasierte Extraktion (Seite, Zeilenlabel, Spaltenanzahl, Jahresspalte je Emittent in `reports/profiles/*.json`). Erkennt vorangestellte Umrechnungsspalten (CKH US$), Zwischensummen ohne Label (Swire, CKH, First Pacific), umbrochene Labels, chinesische Labels mit `( 1,234 )`-Negativen (BYD), Fußnotenmarker `(1)` (DBS) und Doppelseiten-PDFs (DBS).
- Konsistenzprüfungen: Bilanzidentität, Gewinnaufteilung, Kassenabgleich Cashflow/Bilanz, Nettoverschuldung, Dividendenbestandteile, Zehnjahresübersicht.
- `app/verification.py`: zweite PDF-Engine (pdfplumber) prüft jeden Wert auf der zitierten Seite; Abgleich mit IR-Webseiten (`reports/reference_ir_2025.json`).
- `extract_reports.py` (CLI) → `reports/extracted/<SYMBOL>_2025.json`, `summary_2025.json`, `VERIFIKATION_2025.md`.
- API: `GET /v1/reports/{symbol}/statements?fiscal_year=2025`.
- `export_aktien_hub.py` + Workflow-Vorlage `integration/aktien-hub/` für das Repository `aktien-hub`.
- 51 neue Tests (insgesamt 85), darunter Regressionstests mit Golden Values und ein Live-Test gegen die gecachten PDFs.

### Behobene Fehler (alle live nachgewiesen)
1. **Download scheiterte hinter HTTP-Proxys** (`gaierror`): `validate_url` machte eine lokale DNS-Abfrage vor dem Download. Fehlgeschlagene lokale Auflösung wird jetzt nur toleriert, wenn ein Proxy konfiguriert ist; private Ziel-IPs werden weiter abgewiesen.
2. **Redirect-Prüfung war unerreichbar**: `raise_for_status()` lief vor der Redirect-Prüfung (httpx wirft bei 3xx).
3. **CK-Hutchison-Bericht wurde abgeschnitten**: Limit 350 Seiten, Bericht hat 352. Neues Limit 600 Seiten; Kürzungen werden protokolliert statt still verworfen. Leere Seiten bleiben erhalten, damit Seitennummern stimmen.
4. **HKEX-Discovery lieferte nie Ergebnisse**: `stockId` ist eine interne HKEX-ID (jetzt über `prefix.do` ermittelt), `result` kommt als JSON-String. Zusätzlich Kategorie-Filter „Annual Report“. Der alte Mock-Test hatte den Fehler festgeschrieben und wurde korrigiert.
5. **CNINFO-Discovery fand den BYD-Bericht nicht**: ohne Kategorie `category_ndbg_szsh;` kamen nur die 30 neuesten Meldungen beliebiger Art zurück.
6. **CNINFO-Titelfilter ließ Halbjahresberichte durch** (`半年度报告` enthält `年度报告`) sowie Ankündigungen von Ergebnis-Calls.
7. **Referenzvergleich verglich Millionen mit Einheiten**: `compare_facts` meldete dadurch immer `mismatch`; jetzt mit Einheitenumrechnung.
8. Der alte generische Tabellenparser (v0.6) findet in allen fünf echten Berichten **0 Werte** (er verlangt zwei Leerzeichen zwischen den Jahresspalten). Er bleibt für Rückwärtskompatibilität, wird aber für profilierte Emittenten durch den neuen Extraktor ersetzt.

### Entfernt/geändert
- `reports/verified_facts_2025.json` → ersetzt durch `reports/reference_ir_2025.json` (der alte Name suggerierte eine Verifikation, die es nicht gab).
- `requirements.txt`: `pdfplumber` (MIT) ergänzt.

## v1.2 (2026-11-18)

### Neu
- `app/history.py` und `build_history.py`: vorsichtiger Aufbau einer 2024/2025-Zweijahreshistorie aus den im v1.1-Extrakt gespeicherten Original-Tabellenzeilen. Keine erneute PDF-Verarbeitung behauptet.
- Vergleichsspalten je Emittent explizit definiert (einschließlich DBS-Gruppenbilanz, CKH-Mehrjahresspalten und Swire-Zehnjahreszeile); unvollständige oder nicht tabellarische Felder werden ausgelassen und begründet.
- `reports/history/history_2024_2025.json`: maschinelle Vergleichswerte für fünf Unternehmen mit Quelle, Seite, Originalzeile, Einheit und Währung.
- `reports/coverage/company_queue.json`: Jardine Matheson (`J36.SI`) mit offiziellen Berichtsquellen als noch nicht importierter Kandidat. Keine SHA-256 oder Finanzdaten erfunden.
- 9 zusätzliche Tests; insgesamt 93 bestanden, 1 Live-Test übersprungen in dieser Umgebung.

### Grenzen
- Die 2024-Vergleichsspalten wurden nicht unabhängig gegen eigenständige Geschäftsberichte 2024 oder pdfplumber geprüft. Sie bleiben `machine_extracted` und `human_review: pending`.
- Jardine Matheson wurde noch nicht heruntergeladen, gehasht oder durch den Extraktor verarbeitet.
- Bestehende v1.1-Profile, Referenzwerte und Tests unverändert beibehalten.

## v1.3 (2026-11-18)

### Neu
- `app/coverage.py` und `plan_history.py`: nachweisbasierte Abdeckungsmatrix für das Ziel 2020–2025. Fehlende Jahre werden als `missing` markiert, niemals als Nullwerte oder erfundene Daten.
- `reports/coverage/coverage_2020_2025.json`: 10 Firmen x 6 Jahre, mit Zählung vorhandener Fakten, Quellberichtsjahr und ausstehender menschlicher Prüfung.
- Warteliste erweitert: OCBC (`O39.SI`), UOB (`U11.SI`), Kweichow Moutai (`600519.SS`), China Merchants Bank (`600036.SS`), zusätzlich zu Jardine Matheson (`J36.SI`). Neue Kandidaten haben absichtlich weder PDF-URL noch SHA-256 oder Extraktionsprofil, solange diese nicht geprüft sind.
- Vier neue Tests für fehlende Jahre, Kandidaten, Jahresbereich und JSON-Ausgabe. Vorhandene Tests unverändert.

### Grenzen
- Keine zusätzlichen offiziellen Geschäftsberichte heruntergeladen und keine neuen Finanzwerte extrahiert.
- Historische Zahlen für 2020–2023 fehlen weiterhin. 2024 bleibt eine Vergleichsspalten-Extraktion aus 2025er Berichten; menschliche Prüfung ausstehend.

## v1.4 — Jardine issuer history (2026-11-18)
- Added `reports/history/jardine_issuer_web_2021_2025.json`: 26 individually sourced issuer-web facts for Jardine Matheson, FY2021–2025 (20 five-year chart values, 6 FY2024/25 CFO table values).
- Kept underlying net profit separate from reported net profit, and parent free cash flow separate from consolidated cash flow. No FX conversions; 2020 stays missing.
- Added strict `app/official_history.py` validation, new tests and source-type-aware coverage integration; source type is **issuer-web transcription**, not PDF-extracted or human-verified.
- Rebuilt 2020–2025 coverage matrix; 102 tests passed, 1 live test skipped.
- No new PDF downloaded or SHA pinned. Jardine extraction profile and FY2022–2024 independent report imports remain outstanding.

## v1.5 — Unternehmensuniversum und Zehnjahres-Arbeitsplan (2026-11-18)
- Alle 451 vom Nutzer gewünschten Markteinträge aus fünf Märkten verlustfrei als ursprüngliche Namensliste und JSON-Katalog übernommen: HK 51, SG 30, CN 50, JP 247, KR 73.
- `app/universe.py`, `build_universe.py`, `reports/universe/`: marktgetreue Listeneinträge, ungeprüfte Ticker ausdrücklich `null`, Dublettenhinweise ohne unzulässiges Zusammenführen von A-/H-Aktien.
- `plan_universe_history.py`: 2016–2025 als Lückenmatrix mit `not_assessed` und `facts: null`, nicht als behauptete Finanzhistorie.
- Vorhandene v1.4-Historien, Berichtsprofile, Prüfsummen und Tests unverändert beibehalten; zusätzliche Regressionstests.
- Keine neuen PDFs heruntergeladen, keine Ticker recherchiert oder als geprüft markiert, keine neuen Finanzzahlen extrahiert.

## v1.6 — Identitäten, Berichtsquellen, Zehnjahreshistorie, Integration in aktien-hub (2026-11-18)

### Neu
- **Ticker- und Kennungszuordnung für alle 451 Einträge** (`app/identity.py`, `build_identity_map.py`, Ergebnis `reports/universe/identity_map.json`) gegen fünf kostenlose offizielle Listen: HKEX List of Securities (inkl. ISIN), SGX-Wertpapierliste, CNINFO-Aktienliste (Code + orgId), JPX-Liste und EDINET-Codeliste (EDINET-Code + japanische Unternehmensnummer). `companies.json` bleibt unverändert; Kandidaten des Assistenten stehen getrennt in `reports/universe/ticker_candidates.json` und gelten nicht als Nachweis.
- **Offizielle Berichtsquellen** (`build_report_sources.py`, `reports/sources/annual_report_sources.json`): HKEXnews- und CNINFO-Kandidaten für GJ 2016–2025 je Unternehmen (nicht heruntergeladen, nicht gehasht), EDINET-Codes für Japan, Status für Korea (DART-Schlüssel nötig) und Singapur (keine freie Such-API).
- **Finanzhistorie 2016–2025 für CK Hutchison, Swire Pacific, First Pacific** aus den Zehnjahresübersichten der bereits gehashten Berichte 2025 (`app/multi_year.py`, `build_ten_year_history.py`, Profile in `reports/profiles_history/`, Ergebnis `reports/history/ten_year_2016_2025.json`): 420 Werte, Jahresprüfungen, Abgleich 2025 mit der Abschluss-Extraktion, zweite PDF-Engine.
- HKEX-Suche findet auch **inaktive (ehemalige) Wertpapiere**; Mehrjahressuche HKEX/CNINFO; Jahresberichte ohne Jahreszahl im Titel werden mit ausdrücklich gekennzeichnetem, abgeleitetem Geschäftsjahr erfasst.
- `find_row(..., after_occurrence=N)` für Tabellen mit wiederholten Segmentlisten (rückwärtskompatibel).
- Workflows für aktien-hub: `asien-geschaeftsberichte.yml` (erweitert um Zehnjahreshistorie) und neu `asien-universum.yml`.

### Behobene Fehler
1. CNINFO-Titelfilter ließ Meldungen **über** Jahresberichte durch (`关于《2022年年度报告》…的公告`).
2. CNINFO legt nicht jeden Jahresbericht unter der Kategorie „年度报告“ ab (live: Yangtze Power GJ 2020); neue Rückfallsuche über den Titel für fehlende Jahre.

### Unverändert
- Alle v1.1–v1.5-Module, Profile, Prüfsummen, Daten und Tests. Kein bestehender Test wurde geändert oder entfernt; die zwei Discovery-Testdateien wurden nur um neue Tests ergänzt.
