# Changelog Europe Equity Hub

## v0.7 (18.11.2026) – erste Integration in aktien-hub
- Eingangsdaten v0.6 unverändert unter `input/` (Arbeitsmappe, `screener.csv`, Auftrag); Paket-Audit und -Tests übernommen (Testpfad auf `input/` angepasst).
- `scripts/build_official_lists.py`: 44 datierte offizielle Listen mit URL, Abrufzeit, HTTP-Status, Größe, SHA-256 und Hinweis auf Nutzungsbedingungen; Fehler werden protokolliert.
  - ESMA FIRDS (32 EU-Handelsplätze inkl. Wachstumssegmente: Xetra/Scale, Euronext Paris/Growth, Amsterdam, Brüssel, Lissabon, Dublin, Mailand/Growth, Oslo, BME/BME Growth, Wien, Stockholm, NGM, Helsinki, Kopenhagen, Island, Warschau/NewConnect, Athen, Tallinn, Riga, Vilnius, Prag, Budapest, Bukarest, Zagreb, Ljubljana, Bratislava, Sofia)
  - FCA FIRDS (London Main Market, AIM), SIX Swiss Exchange, Xetra-Instrumentenliste, Euronext-Aktienliste, Nasdaq Nordic (Haupt- und First-North-Markt).
- `app/universe.py`: Modell Emittent (LEI) / Wertpapier (ISIN) / Notierung (ISIN+MIC) / Indexzugehörigkeit (Stichtag); beendete Notierungen bleiben erhalten; ISIN-Prüfziffer; GLEIF-Abgleich (rechtlicher Name, Sitzland).
- Kandidatenabgleich: Ticker+Börse oder exakter normalisierter Name → zugeordnet (nicht verifiziert); unscharfe Treffer, mehrere Gattungen und Nichtfunde → Prüfliste; US-ADRs/OTC getrennt.
- `app/history.py`: FY2010–2025 aus ESEF-XBRL (repo-Cache `data/esef/speicher.json`, unverändert) mit Konzept, Berichts-URL, Währung, Einheit, Vorjahresspalten-Kennzeichen; abgeleitete Gesamtverschuldung und Free Cashflow mit Formel; Plausibilitätsprüfungen; Coverage-Matrix ohne Nullauffüllung.
- 28 neue Tests (Auftragsliste Punkt 10 vollständig abgedeckt).
