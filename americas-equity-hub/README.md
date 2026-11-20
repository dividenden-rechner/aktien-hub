# Americas Equity Hub (Kanada, Brasilien, Mexiko)

Lizenzsichere Erweiterung des Aktien-Hubs. Grundsatz: Nur Quellen, deren Bedingungen Speicherung, öffentliche Ausgabe und
kommerzielle Nutzung ausdrücklich erlauben, gelangen in Hub, Website oder Repository (`app/rights.py`).

- `docs/RECHTE.md` – Quellen, Status je Zweck, Belege, offene Rechtsfragen (aus `data/rights/source_license.json`)
- `docs/ABDECKUNG.md` – tatsächlich erreichte Abdeckung · `docs/TESTSTATUS.md` · `docs/QUELLENPRUEFUNG.md` · `CHANGELOG.md`
- Brasilien: `scripts/build_brazil.py` (CVM, ODbL) → `data/universe/brazil/`, `data/financials/brazil/<CNPJ>.json`, Hub `data/americas/firma/<KÜRZEL>.SA.json`
- Kanada/Mexiko: `scripts/build_sec_universe.py` (SEC + GLEIF) → `tools/sec_fundamentals.py` (SEC_LISTE) → `scripts/export_hub.py`
- Datenmodell: issuer / security / listing getrennt; financial_fact mit Datei, Konto, Version, Rohwert, Skala, Prüfstatus.
  price_bar, dividend_event, index_membership: Schema vorgesehen, **keine Daten** (keine Quelle mit Freigabe).
- Rohdateien in `data/raw/` (nicht im Repository). Alles `verified=false`, `human_review=pending`.
