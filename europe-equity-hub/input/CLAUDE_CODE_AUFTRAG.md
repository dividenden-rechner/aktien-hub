# Claude Code – Europa Aktien-Hub: verbindlicher Integrationsauftrag

Repository: https://github.com/dividenden-rechner/aktien-hub
Quelle: beigefuegte Europa-Arbeitsmappe v0.5 und screener.csv. Dies ist ein **Arbeitsbestand**, KEIN verifiziertes Gesamtuniversum.

## Vorgehen (in dieser Reihenfolge)
1. Arbeite erst nach abgeschlossenem laufendem Push. `git status`, Branch, letzte Commits, bestehende Tests und Verzeichnisstruktur pruefen. Neuen Branch `feature/europe-universe-history` anlegen; keine bestehenden Daten ueberschreiben.
2. Vor jeder Aenderung, sofern vorhanden: `CHANGELOG.md`, `docs/TESTSTATUS.md`, `INTEGRATION.md`, `reports/extracted/VERIFIKATION_2025.md` lesen. Repo-eigene Konventionen gehen vor. Backup/Commit-Referenz dokumentieren.
3. `python scripts/audit_europe_workbook.py europa_aktien_hub_v0_5_boersenabgleich.xlsx` ausfuehren. Audit-JSON und CSV unter `artifacts/europe/` sichern.
4. Vorhandene Emittenten/ISIN/Instrumente/Notierungen aus dem Repo exportieren und gegen die Kandidaten abgleichen. Nicht blind 1002 Listenpositionen als Unternehmen importieren.
5. Aktuelle **datierte** offizielle Instrumentenlisten je Boerse/Segment beschaffen (Xetra, Euronext, LSE Main/AIM, SIX, Wiener Boerse, BME, Borsa Italiana, Nasdaq Nordic/Baltic, Oslo, GPW, ATHEX, CEE). Download-URL, Abrufzeit, Lizenz/Nutzungsbedingungen, Dateihash und Snapshotdatum sichern. Fehlt eine frei nutzbare Voll-Liste, die Luecke dokumentieren, keine Vollstaendigkeit behaupten.
6. Identitaeten sauber trennen: `issuer` (juristische Gesellschaft), `security` (ISIN/Aktiengattung), `listing` (MIC, lokaler Ticker, Handelswaehrung, Zeitgueltigkeit), `index_membership` (Index + Stichtag). Dieselbe ISIN auf mehreren Boersen ist nicht automatisch Dublette zum Loeschen; gleiche Gesellschaft mit mehreren ISINs nicht verschmelzen.
7. Alle v0.5-Kandidaten gegen offizielle Quellen matchen; fuzzy matches nur als Review-Queue, nie automatisch als bestaetigt. Delistings, Namenswechsel, Fusionen, ADRs, ETFs/Fonds/ETNs und Cross-Listings gesondert behandeln. Indexmitgliedschaft nie aus einem Index-Familienvorschlag ableiten.
8. Historie FY2010–FY2025 je Emittent und Kennzahl erfassen: Originalbericht, Berichtstyp, Geschaeftsjahr-Ende, Wert, Währung, Einheit, Seite/Tabelle, URL, SHA256, Extraktionsmethode, `human_review=pending`. 2025 nur wenn Bericht veroeffentlicht. Restatements und vergleichende Vorjahreswerte kennzeichnen.
9. Kurs- und Dividendenhistorie 2010–2025 nur aus rechtlich nutzbaren Quellen: datum, boerse/MIC, waehrung, adjusted/unadjusted, Corporate Actions; Dividende je Aktie, ex-date, payment-date, Waehrung, ordinary/special, Brutto/Netto, Split-Anpassung. Keine ausstehende Historie als vorhanden markieren.
10. Tests fuer Import-Idempotenz, fehlende ISIN, identische ISIN mit zwei Listings, zwei Aktiengattungen eines Emittenten, delisted instruments, Currency/Unit, zeitliche Indexzugehoerigkeit, Source-Provenance und kein automatisches `verified`.
11. `docs/TESTSTATUS.md`, `CHANGELOG.md`, `INTEGRATION.md` und eine Europa-Coverage-Matrix mit Zaehlmethodik aktualisieren. Testausgabe und ungepruefte Luecken dokumentieren. Pull Request statt direktem Merge; keine Secrets committen.

## Abnahme
- Keine Regression in Asien oder bestehenden Europa-Daten.
- Jede neu eingefuehrte ISIN/Ticker/MIC-Zuordnung hat nachvollziehbare datierte Quelle oder ist `unverified`.
- Anzahl Unternehmen, Wertpapiere, Listings und Index-Mitgliedschaften separat ausgewiesen.
- Fehlende 2010–2025 Werte als `missing`, nicht als 0; `human_review=pending`.
- Reproduzierbare Imports, Tests und nachvollziehbarer PR mit Diff/Zusammenfassung.

## Wichtige Ehrlichkeit
Die beigefuegte v0.5 enthaelt 422 CSV-Listings und 580 zusaetzliche **Recherchekandidaten**, aber noch keine amtliche Volluniversums-Datei und keine verifizierte 16-Jahres-Historie. Einige Firmen koennen mehrfach vorkommen, umbenannt oder delisted sein.
