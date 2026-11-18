# Bestandsaufnahme vor der Europa-Integration (18.11.2026)

Basis-Commit: `1969e13` (main, „Asien: Unternehmensuniversum und Berichtsquellen aktualisiert“). Gearbeitet auf `feature/europe-universe-history`.

## Repository
- Remote-Branches: `main`, zwei Asien-Branches (bereits gemergt), viele `freigabe/*`-Branches des Magazin-/News-Ablaufs. Letzte Commits stammen von Bots (`kurse-bot`, `av-bot`, `magazin-bot`, `kurz-bot`) und den Asien-Merges #116/#118.
- `README.md` im Repo-Root ist nur eine Überschrift. `CHANGELOG.md`, `INTEGRATION.md` und `docs/TESTSTATUS.md` gibt es im Root nicht, sondern nur unter `asia-equity-hub/`.
- 60 Workflows, davon 27 zeitgesteuert. Website-Build über `tools/live_filter.py` (Ausschlussliste) und Deploy auf Strato.

## Vorhandene Europa-Daten (unverändert gelassen)
| Pfad | Inhalt | Quelle / Status |
|---|---|---|
| `data/<land>/boerse-de-reihen.json` (15 Länder) | 318 Firmen, Kennzahlen 2019–2025 | boerse.de (Drittquelle), laut Datei „nicht gegen Geschäftsberichte geprüft“ |
| `data/esef/fundamentals.json`, `data/esef/speicher.json` | 114 Emittenten, 613 ESEF-Berichte (GJ 2020–2026) mit XBRL-Rohwerten | filings.xbrl.org, `tools/esef_fundamentals.py` |
| `data/kurse/isin-zuordnung.json` | 607 Ticker→ISIN (global) | OpenFIGI |
| `data/kurse/xetra`, `frankfurt`, `tradegate` | aktuelle Tageskurse | Deutsche Börse u. a. |
| `data/kurse/historie/*.json` | 4 Firmen, Wochenkurse | Alpha Vantage, unbereinigt |
| `data/indizes/mdax.csv`, `sdax.csv` | MDAX/SDAX-Mitglieder mit ISIN | ohne Stichtag in der Datei |
| `data/kennzahlen.json` | 1.035 Werte (global) für den Screener | diverse |

## Vorhandene Asien-Integration
`asia-equity-hub/` (v1.7.1): 451 Einträge, Identitäten, Berichtsquellen, Zehnjahreshistorie; Workflows `asien-universum.yml`, `asien-geschaeftsberichte.yml`. Wird in diesem PR nicht verändert.

## Europa-Paket v0.6 (Eingang, unter `input/`)
- 422 Screener-Zeilen (`Bestand_422` = `screener.csv`), teils US-ADRs/OTC ohne Börsenendung.
- 580 Recherchekandidaten in 3 Ergänzungsblättern – alle ohne ISIN, Ticker, MIC.
- Historienblätter (`Historie_2010_2025`, `Historie_v04_Kandidaten`) enthalten nur Platzhalter „missing“.
- Paket-Audit (`scripts/audit_europe_workbook.py`) und Paket-Tests laufen unverändert (4/4).
