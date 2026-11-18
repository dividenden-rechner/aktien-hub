# Europe Equity Hub (v0.7)

Europäisches Aktienuniversum aus **offiziellen, kostenlosen Quellen** mit sauber getrennten Ebenen
Emittent (LEI) → Wertpapier (ISIN) → Notierung (ISIN + MIC) → Indexzugehörigkeit (mit Stichtag),
Abgleich der Kandidaten aus dem Europa-Paket v0.6 und Finanzhistorie FY2010–2025 (ESEF, ab GJ 2020).

```bash
pip install -r requirements.txt
python scripts/build_official_lists.py   # 44 offizielle Listen laden (ESMA/FCA FIRDS, SIX, Xetra, Euronext, Nasdaq Nordic)
python scripts/build_universe.py         # Emittenten/Wertpapiere/Notierungen + Kandidatenabgleich (+ GLEIF)
python scripts/build_history.py          # FY2010-2025 aus ESEF, Coverage-Matrix, Kurs-/Dividendenabdeckung
python -m pytest -q
```

| Ergebnis | Datei |
|---|---|
| 11.663 Notierungen (7.361 aktiv), 10.683 Wertpapiere, 8.876 Emittenten | `data/universe/listings.json`, `securities.json`, `issuers.json` |
| 1.002 Kandidaten: 755 zugeordnet (533 Wertpapiere / 532 Emittenten), 204 Prüfliste, 43 US-ADR/OTC | `data/universe/candidates_matched.json`, `review_queue.csv` |
| Dubletten: 214 Gruppen gleicher ISIN aufgelöst, 1 Emittent mit 2 Gattungen getrennt gehalten | `data/universe/duplicates.json` |
| 8.190 ESEF-Werte + 414 abgeleitete, Coverage-Matrix 2010–2025 | `data/history/` |
| Quellen mit URL, Abrufzeit, SHA-256, Lücken | `data/official_lists/sources.json` |

Alles ist maschinell erzeugt: `human_review: pending`, nichts ist `verified`. Details: `docs/TESTSTATUS.md`,
`CHANGELOG.md`, `INTEGRATION.md`, `docs/BESTANDSAUFNAHME.md`.
