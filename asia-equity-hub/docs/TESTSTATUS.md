# Teststatus v1.1 (Stand 2026-11-18)

## Getestet, live mit echten Daten

| Funktion | Ergebnis | Nachweis |
|---|---|---|
| Download der 5 offiziellen PDFs über `process_reports.py --download` | 5/5 erfolgreich, HTTP 200, `application/pdf`, kein Redirect | `reports/live_test_results.json`, SHA-256 in `reports/catalog.json` |
| Identität der Berichte (Emittent, Berichtsart, GJ 2025) | bestätigt aus dem PDF-Text | Titelseiten bzw. Inhaltsverzeichnisse |
| Textextraktion (pypdf) | 1.209 Seiten, keine Kürzung, max. 7 fast leere Seiten pro Bericht (Bild- oder Trennseiten) | Cache-Metadaten |
| Profil-Extraktion Umsatz, Gewinn, Bilanz, Cashflow, Dividende | 116 Werte + 12 abgeleitete, 0 Fehler | `reports/extracted/*.json` |
| Rechnerische Konsistenzprüfungen | 24/24 bestanden | Feld `checks` |
| Zweite PDF-Engine (pdfplumber) | 116/116 Werte auf der zitierten Seite gefunden, 75 davon in einer Zeile mit passendem Label | Feld `second_engine` |
| Abgleich mit IR-Webseiten | 10/10 vergleichbare Werte stimmen (CKH 3, Swire 5, First Pacific 2) | Feld `reference_comparison` |
| Sichtprüfung am gerenderten PDF | je Bericht eine Abschlussseite, alle Werte inkl. Spalte und Vorzeichen stimmen | `manual_review.assistant_visual_check` (durch KI-Assistent, **nicht** durch einen Menschen) |
| Gedruckte Seitenzahlen | 18 Stichproben stimmen mit den Seitenfüßen überein | Profilregel `printed_page_rule` |
| HKEX-Discovery (nach Fix) | 0001/0019/0142.HK finden je den Jahresbericht 2025 | `live_test_results.json` |
| CNINFO-Discovery (nach Fix) | 002594.SZ und 600519.SS finden den Jahresbericht 2025 | dto. |
| Börsenkopien vs. Emittentenkopien | First Pacific und BYD byte-identisch; CKH andere Datei mit identischen Werten in allen 25 Feldern | Katalogfeld `alternate_sources` |

## Getestet, nur offline (Unit-Tests mit Mocks oder echten Textauszügen)
- Proxy-/DNS-Verhalten, Redirect-Abweisung, Größenlimit, Nicht-PDF-Antwort, SHA-Abweichung (`tests/test_download_hardening.py`).
- Parser-Sonderfälle mit wörtlichen Auszügen aus den echten Berichten (`tests/test_statement_extractor.py`).
- API-Endpunkt `/statements`, Export für aktien-hub.

## Nicht getestet bzw. nicht implementiert
- **Menschliche Prüfung**: steht aus (`human_review: pending`). Die Sichtprüfung erfolgte durch den KI-Assistenten.
- **SGX-Discovery**: kein stabiler, kostenloser Such-Endpunkt; DBS-URL wird manuell gepflegt. Eine SGXNet-Kopie wurde nicht verglichen.
- **Andere Emittenten oder Geschäftsjahre**: Profile gibt es nur für diese 5 Berichte (GJ 2025). Neue Berichte brauchen ein neues, geprüftes Profil. Ändert ein Emittent sein Layout, meldet der Extraktor Fehler, er rät nicht.
- **Vorjahreswerte (2024)** werden nicht ausgegeben, obwohl sie in derselben Zeile stehen (Spalte 1). Möglich wäre das per Profil.
- **OCR** für gescannte PDFs: nicht nötig für diese 5 Berichte, nicht implementiert.
- **Währungsumrechnung**: bewusst keine. Werte bleiben in Berichtswährung (HKD, USD, SGD, CNY).
- **GitHub-Actions-Workflows**: Syntax geschrieben, aber nicht auf GitHub ausgeführt.
- **yfinance-Endpunkte** (v0.1–v0.2) wurden in v1.1 nicht erneut live getestet.
- **Vergleichbarkeit**: DBS ist eine Bank (Umsatz = Total income, FCF-Kennzahlen unterdrückt). BYD bilanziert nach PRC-GAAP in Tsd. RMB, die übrigen nach IFRS/HKFRS/SFRS(I). Kennzahlen sind nicht 1:1 vergleichbar.

## Ergänzung v1.2 (2026-11-18)

**Tatsächlich lokal ausgeführt:** `python build_history.py` (5 Unternehmen) und `PYTHONPATH=. python -m pytest -q` (93 bestanden, 1 Live-Test übersprungen). Der Testlauf benötigte keine neuen PDF-Downloads.

**Neu getestet:** 2024-Vergleichsspalten für Umsatz aller fünf Emittenten; fehlende Vergleichsspalten werden nicht geschätzt; SHA-Abweichungen führen zum Abbruch; Jardine bleibt ausdrücklich ein unbearbeiteter Kandidat.

**Noch nicht getestet:** Eigenständige 2024-Geschäftsberichte, zweite PDF-Engine für 2024-Vergleichswerte, unabhängige Jahresabgleiche, Jardine-PDF-Download und Jardine-Profil, GitHub-Ausführung. Menschliche Prüfung weiterhin ausstehend. Keine Daten als `verified` markiert.

**Datenhinweis:** 2024 stammt aus den in v1.1 gespeicherten Tabellenzeilen der Geschäftsberichte 2025. Zahlen können rückwirkend angepasst worden sein und sind deshalb nicht automatisch mit einem separat veröffentlichten Bericht 2024 identisch.

## Ergänzung v1.3 (2026-11-18)

**Lokal ausgeführt:** `python plan_history.py` und `PYTHONPATH=. python -m pytest -q`: **97 bestanden, 1 übersprungen**.

**Getestet:** 2020–2025-Abdeckungsmatrix mit 10 Unternehmen, fehlende Geschäftsjahre werden nicht erfunden, Wartelistenfirmen haben keine Finanzwerte, ungültige Jahresbereiche werden abgewiesen, JSON-Ausgabe lässt sich wieder einlesen.

**Nicht ausgeführt:** neue PDF-Downloads, Live-Suche für Jardine/OCBC/UOB/Moutai/China Merchants Bank, Profilierung oder Extraktion weiterer Berichte, menschliche Prüfung, GitHub-Ausführung. **Keine** neuen Fakten wurden als `verified` markiert.

## Ergänzung v1.4 (2026-11-18)

**Tatsächlich lokal ausgeführt:** `python plan_history.py` und `PYTHONPATH=. python -m pytest -q`: **102 bestanden, 1 Live-Test übersprungen**.

**Neu:** 26 Jardine-Matheson-Fakten für 2021–2025 aus den offiziellen IR-Webseiten `https://ar.jardines.com/2025/Highlights.html` und `https://ar.jardines.com/2025/CFOStatement.html` in `reports/history/jardine_issuer_web_2021_2025.json`. Herkunft wird ausdrücklich als `issuer_web_transcribed_pending_pdf_review` ausgewiesen; keine PDF-Seitenangaben, kein SHA, keine Behauptung einer PDF-Extraktion. 2020 bleibt leer. Das Vorjahresjahr 2024 aus der CFO-Tabelle kann eine rückwirkend angepasste Darstellung sein.

**Noch nicht ausgeführt:** Jardine-PDF-Download, PDF-Profile, unabhängiger Abgleich mit den PDF-Tabellen, Downloads und Extraktion eigenständiger 2022–2024-Berichte der fünf Bestandsfirmen, menschliche Prüfung, GitHub-Ausführung. Kein Wert wurde als `verified` markiert.

## Ergänzung v1.5 (2026-11-18)
- **Tatsächlich lokal ausgeführt:** `python build_universe.py`, `python plan_universe_history.py` und `PYTHONPATH=. python -m pytest -q`: 108 Tests bestanden, 1 Live-Test übersprungen.
- **Getestet:** fünf Marktsegmente, Vollständigkeit der JSON-Abbildung gegenüber der gespeicherten Ursprungsliste, eindeutige Eintrags-IDs, keine erfundenen Ticker, Dublettenhinweise, zehnjährige Lückenmatrix ohne künstliche Nullwerte.
- **Nicht getestet/noch nicht umgesetzt:** Ticker-/ISIN-/LEI-Abgleich, Handelsstatus historischer Emittenten, neue offizielle Berichtsdownloads, Japan-EDINET- und Korea-DART-Anbindungen, Finanzdatenextraktion für die neu gelisteten Unternehmen, GitHub-Integration, menschliche Prüfung. Bestehende sechs Emittenten-Historien bleiben separat bestehen.

## Ergänzung v1.6 (2026-11-18)

**Tatsächlich ausgeführt (live, mit Netzwerk):**
- Download der 5 offiziellen Listen (HKEX 17.342 Zeilen, SGX 616 Aktien/REITs/Trusts, CNINFO 6.267, JPX 4.444, EDINET 11.471); SHA-256 je Liste in `identity_map.json`.
- Zuordnung der 451 Einträge: **364 gegen offizielle Listen bestätigt** (HK 50/51, SG 30/30, CN 50/50, JP 234/247). Nicht in aktuellen Listen: 10 (HK: Hang Seng Bank; JP: Toshiba, Bank of Yokohama, Hino Motors, Kyushu Electric Power, Nippon Sheet Glass, NTT Data, Sazaby League, Tokyo Dome, UNY Group). Nicht börsennotiert: 2 (Nikkei, Mitsubishi Shindoh). Mehrdeutig: 2 (Green Cross, „J Powders“). **Korea 73: nur Kandidaten, ungeprüft** (KRX-Listen nur mit Login, DART nur mit API-Schlüssel).
- Automatischer Namensabgleich Japan: 212 exakte, 5 Präfix-Treffer (einzeln geprüft; Toshiba → Toshiba TEC als falsch verworfen), 17 manuelle Zuordnungen mit Begründung; alle 234 mit EDINET-Code und Unternehmensnummer.
- Berichtsquellen: HKEXnews für 51 HK-Einträge, CNINFO für 50 CN-Einträge abgefragt (GJ 2016–2025). Ergebnis: Kandidaten für **470 von 510** HK- und **420 von 500** CN-Unternehmensjahren (10 HK-Dokumente mit aus dem Veröffentlichungsdatum abgeleitetem GJ, 52 CN-Dokumente über die Rückfallsuche). CNINFO liefert zwischen Läufen leicht unterschiedliche Treffer. Lücken durch spätere Börsengänge (z. B. Alibaba, Meituan) und durch CNINFO-Indexlücken (häufig GJ 2020); Hang Seng Bank ohne Treffer unter der inaktiven HKEX-ID.
- Zehnjahreshistorie: 3 Emittenten × 10 Jahre, 420 Werte, 60/60 Jahresprüfungen bestanden, 23/23 Abgleiche 2025 mit der Abschluss-Extraktion identisch, pdfplumber findet 420/420 Werte, 23/23 vergleichbare 2024-Werte identisch mit v1.2 (ein Definitionsunterschied bei First-Pacific-Capex wurde durch eigenes Feld `capex_issuer_defined` getrennt).
- Testlauf mit gecachten PDFs: **143 bestanden**, davon alle 109 Tests aus v1.5 unverändert. Im Repo ohne PDFs: 142 bestanden, 1 Live-Test übersprungen.

**Nicht ausgeführt / offen:**
- Download, Hashing und Extraktion der gefundenen Berichtskandidaten (HK/CN 2016–2024).
- EDINET-Dokumentlisten (Japan) und OpenDART (Korea): brauchen die API-Schlüssel, die als Secrets in aktien-hub liegen; nicht in dieser Sitzung verfügbar.
- Singapur-Berichtsquellen außer DBS (manuelle Recherche nötig).
- Zehnjahreswerte 2016–2023 wurden nicht gegen die damaligen Originalberichte geprüft (können restated sein; als `presentation_note` gekennzeichnet).
- Menschliche Prüfung: weiterhin für alles ausstehend. Nichts ist als `verified` markiert.
- GitHub-Workflows: Syntax geprüft, nicht auf GitHub ausgeführt.

## Ergänzung v1.7 (2026-11-18)
- **Getestet (offline, nachgebaute Antworten):** DART-Firmenliste, KOSPI/KOSDAQ-Endung, Berichtstitel `사업보고서 (JJJJ.MM)`, Korrekturen getrennt, EDINET-Tagesindex mit Wochenend-Überspringen, Fehlerzählung, Geschäftsjahr nach Periodenbeginn, Schlüssel nie in Fehlermeldungen. Testlauf: 148 bestanden, 1 übersprungen (ohne PDFs).
- **Nicht ausgeführt:** echte DART- und EDINET-Abfragen. Sie laufen erst auf GitHub mit den Secrets. Bis dahin bleibt Korea „candidate_unverified“ und Japan ohne Dokumentliste.

## Ergänzung v1.8 (2026-11-18)
- **Live ausgeführt:** HKEXnews-Suche nach den Jahresberichten 2015 und 2019 (je Firma gefunden); Download der drei Berichte 2019 über `sync_report` (Prüfsummen fixiert); Zehnjahresextraktion: 3 × konsistent, alle Jahresprüfungen bestanden, zweite PDF-Engine findet 400/400 Werte; Zusammenführung 2010–2025.
- **Tests:** mit gecachten PDFs 164 bestanden; ohne PDFs 163 bestanden, 1 übersprungen. `extract_reports.py` endet mit Code 0 (5 Abschlüsse konsistent, 3 Berichte nur Historie).
- **Browser:** Hub lädt ohne Fehler; die Diagramme zeigen weiterhin nur die letzten 10 Jahre (bestehende Gestaltungsgrenze des Hubs), die Daten ab 2010 liegen in `data/asien/fundamentals.json` bereit.
- **Nicht ausgeführt:** Berichte 2015 (würden 2006–2015 liefern), ältere Berichte von DBS (Fünfjahresübersicht) und BYD (Dreijahresdaten), Prüfung durch einen Menschen.
