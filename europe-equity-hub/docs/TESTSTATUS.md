# Teststatus Europe Equity Hub v0.7 (18.11.2026)

## Tatsächlich ausgeführt
| Schritt | Ergebnis |
|---|---|
| `python scripts/audit_europe_workbook.py input/…xlsx --out artifacts/europe` | 422 Bestandszeilen, 580 Kandidaten, 0 verifiziert |
| `python scripts/build_official_lists.py` | 44/44 Listen geladen (1. Lauf: Xetra 502 Proxy-Fehler, 2. Lauf erfolgreich); URL, Zeit, SHA-256 in `data/official_lists/sources.json` |
| `python scripts/build_universe.py` | 11.663 Notierungen (7.361 aktiv, 4.302 beendet), 10.683 Wertpapiere, 8.876 Emittenten (8.715 GLEIF-bestätigt, 161 ohne LEI), 0 ungültige ISINs |
| `python scripts/build_history.py` | 8.190 ESEF-Werte + 414 abgeleitete, 114 Emittenten, 4 Plausibilitätsauffälligkeiten |
| Idempotenz: beide Builds zweimal | alle Ausgaben byte-identisch (außer Zeitstempel `generated_at`) |
| `python -m pytest -q` (europe-equity-hub) | **32 bestanden** (4 Paket-Tests + 28 neue) |
| `python -m pytest -q` (asia-equity-hub, Regression) | **149 bestanden, 1 übersprungen** (Live-PDF-Test ohne PDFs) – unverändert |
| Website-Build `tools/live_filter.py` simuliert | `europe-equity-hub/` wird ausgeschlossen |

## Abgedeckt durch Tests
ISIN-Format und Prüfziffer; fehlende/ungültige ISIN wird abgewiesen; gleiche ISIN auf zwei Börsen = 1 Wertpapier, 2 Notierungen; zwei Aktiengattungen eines Emittenten bleiben getrennt; Emittent ohne LEI; Delisting bleibt erhalten und wird markiert; Import-Idempotenz; Ticker-Anreicherung nur über ISIN+MIC; Matching nie `verified`, Fuzzy → Prüfliste, mehrdeutige Gattungen → Prüfliste, ADR → nicht europäisch; Indexzugehörigkeit nur zum Stichtag; Währung/Einheit je Wert; Vorjahresspalten gekennzeichnet; Free-Cashflow-Formel dokumentiert; fehlende Jahre = `missing`, nie 0; Plausibilität (gemischte Währung); Konsistenz der eingecheckten Ausgaben.

## Nicht ausgeführt / offen
- **Finanzhistorie 2010–2018:** keine Daten. ESEF ist erst ab GJ 2020 Pflicht (2017–2019 nur als Vorjahresspalten). PDF-Geschäftsberichte vor 2020 wurden nicht ausgewertet.
- **Kurs-/Dividendenhistorie 2010–2025:** keine frei weiterverwendbare offizielle Tagesreihe abgerufen. Dividenden nur als ESEF-Werte je Aktie (ohne Ex-Tag/Zahltag). Kapitalmaßnahmen nicht importiert.
- **Ticker:** nur 4.031 von 11.663 Notierungen (Xetra, Euronext, Nasdaq Nordic, SIX). LSE, Wien, BME, GPW, Athen und Osteuropa ohne freie maschinenlesbare Tickerliste.
- **Bulgarien:** unter MIC `XBUL` nur 2018/2019 beendete Einträge; aktueller MIC der Bulgarischen Börse nicht ermittelt → 0 aktive Notierungen ausgewiesen (Lücke).
- **Indizes:** nur MDAX/SDAX aus dem Repo (Stichtag = letzter Git-Commit der Datei). Keine weiteren Indexlisten.
- **Prüfliste:** 204 Kandidaten (85 unscharfe Treffer, 114 nicht gefunden, 5 mehrere Gattungen) brauchen menschliche Entscheidung; 43 US-ADRs/OTC sind nicht europäische Notierungen.
- **Nutzungsbedingungen** der Listen sind verlinkt (`terms_note`), aber nicht rechtlich geprüft.
- Menschliche Prüfung: für alles ausstehend. Nichts ist `verified`.
- Workflow `europa-universum.yml`: Syntax geprüft, nicht auf GitHub ausgeführt.
