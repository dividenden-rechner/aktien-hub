# Americas Equity Hub (Kanada, Brasilien, Mexiko)

Stand: Kanada (S&P/TSX Composite) umgesetzt; Brasilien und Mexiko: Quellen geprüft, Import offen.

- `docs/QUELLENPRUEFUNG.md` – welche offiziellen Quellen erreichbar sind, was geladen wurde, Nutzungsbedingungen
- `docs/ABDECKUNG.md` – tatsächlich erreichte Abdeckung (aus den erzeugten Dateien)
- `data/universe/canada/` – getrennte Tabellen: `issuers`, `securities`, `listings`, `index_memberships`, `review`, `summary`
- `scripts/build_canada.py` – Indexbestand (iShares XIC als Proxy, Stichtag) + ISIN/LEI aus ESMA FIRDS (nur eindeutig)
- `scripts/sec_cik.py` → `tools/sec_fundamentals.py` (SEC_LISTE) → `scripts/export_hub.py` – SEC-Jahreszahlen 2010–2025 je Firma nach `data/americas/firma/`
- Workflow `.github/workflows/americas-kanada.yml` (wöchentlich)

Regeln: fehlende Werte bleiben leer, nichts `verified`, `human_review: pending`; Hub-Kürzel `TICKER.TO`
(Gattung mit Bindestrich, z. B. `TECK-B.TO`), damit es keine Verwechslung mit US-Kürzeln gibt.
Tests: `cd americas-equity-hub && python3 -m pytest -q tests`
