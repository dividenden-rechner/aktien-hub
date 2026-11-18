# Integration in dividenden-rechner/aktien-hub

- Ordner `europe-equity-hub/` neben `asia-equity-hub/`; keine bestehende Datei unter `data/`, `tools/` oder `asia-equity-hub/` wird verändert.
- `tools/live_filter.py`: `europe-equity-hub` steht in der Ausschlussliste, wird also nicht auf die Website kopiert.
- Workflow `.github/workflows/europa-universum.yml` (nur `workflow_dispatch`): Listen neu laden → Universum → Historie → Tests → Commit als `kurse-bot`.
- Noch **keine** Datei unter `data/` für die Website erzeugt. Ein Export (z. B. für den Screener) sollte erst nach Durchsicht der Prüfliste folgen.

## Coverage-Matrix (Zählmethodik)
- **Notierung** = Zeile ISIN+MIC aus einer offiziellen Liste; **aktiv** = kein Beendigungsdatum vor dem Abrufzeitpunkt.
- **Wertpapier** = eindeutige ISIN. **Emittent** = eindeutiger LEI (Wertpapiere ohne LEI zählen je einzeln als vorläufiger Emittent).
- **Finanzjahr** je Emittent: `complete` = Umsatz, Jahresüberschuss, Bilanzsumme, Eigenkapital und operativer Cashflow vorhanden; `partial` = mindestens ein Wert; sonst `missing`.

### Aktive Notierungen je Land (Abruf 18.11.2026)
| AT | BE | CH | CZ | DE | DK | EE | ES | FI | FR | GB | GR | HR | HU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 58 | 115 | 241 | 20 | 1.682 | 119 | 19 | 125 | 151 | 576 | 1.880 | 134 | 67 | 50 |

| IE | IS | IT | LT | LV | NL | NO | PL | PT | RO | SE | SI | SK | BG |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 17 | 27 | 399 | 22 | 8 | 120 | 175 | 780 | 32 | 88 | 413 | 17 | 26 | 0* |

\* Sofia (XBUL): alle 116 FIRDS-Einträge sind 2018/2019 beendet. Vermutlich meldet die Börse seitdem unter einem anderen MIC, der hier noch nicht abgefragt wurde – Lücke, keine Aussage über aktuelle Notierungen. DE und GB enthalten auch ausländische Aktien im Freiverkehr/International Order Book (Sitzland siehe `issuers.json`).

### Finanzdaten je Geschäftsjahr (ESEF, alle 114 Emittenten mit Daten)
| 2010–2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 3 | 26 | 93 | 109 | 114 | 114 | 111 | 110 | 95 |

Bezogen auf die 525 zugeordneten Emittenten mit LEI aus dem Paket sind 2020–2024 jeweils rund 100–106 belegt; der Rest ist `missing`.
