# Americas Aktien-Hub – tatsächliche Abdeckung (Stand 2026-11-22)

Nur Quellen, deren Nutzungsbedingungen Speicherung, öffentliche Ausgabe und kommerzielle Nutzung ausdrücklich erlauben (siehe RECHTE.md). Alle Datensätze `verified=false`, `human_review=pending`. Leere Felder = keine freigegebene Quelle.

## Brasilien (CVM Dados Abertos, ODbL)

- Emittenten mit Aktien an der B3 (laut CVM-FCA 2010–2026, inkl. beendeter): **430**, davon aktiv 315
- Wertpapiere: **601** – Gattungen {'ON': 415, 'PN': 118, 'PNA': 25, 'PNB': 23, 'PNC': 3, 'PND': 1, 'UNIT': 16}; Notierungen: **657** (aktiv 422)
- LEI (GLEIF über CNPJ): **120**; ISIN: **0** (CVM ohne ISIN, B3 = Vergabestelle mit Verbot kommerzieller Nutzung)
- Mit Jahresabschlüssen (DFP): **430**; Jahre mit Gewinn je Emittent: 16 J.: 239, 15 J.: 18, 14 J.: 16, 13 J.: 5, 12 J.: 12, 11 J.: 7, 10 J.: 16, 9 J.: 17, 8 J.: 13, 7 J.: 36, 6 J.: 25, 5 J.: 12, 4 J.: 2, 3 J.: 8, 2 J.: 4
- Mit JCP-Zahlungen (getrennt von Dividenden): **208**; Hub-Dateien: **315**
- Kurse, Dividende je Aktie, Ex-Tage, Indexmitglieder (IBOV, IBrX, SMLL, IDIV …): **nicht erfasst** (B3: kommerzielle Nutzung untersagt)

## Kanada (SEC EDGAR + GLEIF)

- Emittenten (Sitz CA laut SEC, mit SEC-Meldung): **610**, Wertpapiere 610, US-Notierungen 775
- LEI (GLEIF, exakter Namensabgleich): **355**; ISIN (GLEIF, eindeutig): **0**; davon mit deutschem Börsenkurs: **0**
- Mit SEC-Jahreszahlen: **265**; Jahre 2010–2025 je Firma (Gewinn): 16 J.: 13, 15 J.: 8, 14 J.: 9, 13 J.: 4, 12 J.: 2, 11 J.: 8, 10 J.: 45, 9 J.: 11, 8 J.: 14, 7 J.: 18, 6 J.: 30, 5 J.: 24, 4 J.: 17, 3 J.: 30, 2 J.: 21, 1 J.: 10, 0 J.: 1
- Heimatbörse (TSX/TSXV bzw. BMV/BIVA), Indexmitglieder, Kurs- und Dividendenhistorie: **nicht erfasst** (keine Quelle mit Freigabe)

## Mexiko (SEC EDGAR + GLEIF)

- Emittenten (Sitz MX laut SEC, mit SEC-Meldung): **11**, Wertpapiere 11, US-Notierungen 15
- LEI (GLEIF, exakter Namensabgleich): **1**; ISIN (GLEIF, eindeutig): **0**; davon mit deutschem Börsenkurs: **0**
- Mit SEC-Jahreszahlen: **10**; Jahre 2010–2025 je Firma (Gewinn): 10 J.: 6, 8 J.: 2, 7 J.: 1, 5 J.: 1
- Heimatbörse (TSX/TSXV bzw. BMV/BIVA), Indexmitglieder, Kurs- und Dividendenhistorie: **nicht erfasst** (keine Quelle mit Freigabe)

## Bewusst nicht erfasst

- S&P/TSX- und S&P/BMV-Indexmitglieder (S&P DJI: lizenzpflichtig, Seiten 403), TSX/TSXV-Listen (TMX: nur nicht-kommerziell),
  BlackRock-ETF-Bestände (öffentliche/kommerzielle Nutzung untersagt), BMV (Reproduktion und Parsing untersagt),
  BIVA und CNBV (Bedingungen nicht lesbar bzw. nicht erreichbar), SEDAR+ (Bot-Schutz, kein maschineller Abruf).

