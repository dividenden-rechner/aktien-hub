# Verifikation Geschäftsberichte GJ 2025

Erzeugt: 2026-11-18 20:02 UTC durch `python extract_reports.py`.

Legende Spalte „2. Engine“: `row_confirmed` = pdfplumber findet denselben Wert in einer Zeile mit passendem Label; `token_on_page` = Wert steht auf derselben Seite (Label nicht in derselben Zeile erkennbar); `not_found` = Abweichung, manuell prüfen. Spalte „Referenz“: Abgleich mit IR-Webseite des Emittenten.

## CK Hutchison Holdings Limited (0001.HK)

- Geschäftsjahr: 2025 (Stichtag 2025-12-31)
- Rechnungslegung: IFRS Accounting Standards (first-time adoption in 2025, see note 2 / note 48)
- Berichtswährung/Einheit: HKD, million
- Quelle: <https://doc.irasia.com/listco/hk/ckh/annual/2025/ar2025.pdf>
- PDF: 352 Seiten, SHA-256 `e5fe1da8c7c39d04586814fa3e6b9ec13c4db2c79034a93a89d7dd533fa42440` (Profil: match)
- Status: **extracted_consistent**; Prüfungen: balance_sheet_identity=pass, profit_split=pass, net_assets_equals_total_equity=pass, cash_flow_closing_cash_equals_balance_sheet=pass, dps_interim_plus_final=pass

- 2. PDF-Engine (pdfplumber): 17 Zeile bestätigt, 9 Wert auf Seite, 0 nicht gefunden

| Kennzahl | Wert | Einheit | PDF-S. | Druck-S. | 2. Engine | Referenz |
|---|---:|---|---:|---:|---|---|
| Umsatz | 280.036 | HKD Mio. | 134 | 132 | row_confirmed | – |
| Gewinn vor Steuern | 26.607 | HKD Mio. | 134 | 132 | row_confirmed | – |
| Jahresüberschuss (inkl. Minderheiten) | 19.370 | HKD Mio. | 134 | 132 | row_confirmed | – |
| Konzerngewinn (Aktionäre) | 11.841 | HKD Mio. | 134 | 132 | row_confirmed | match |
| Ergebnis je Aktie (unverwässert) | 3,09 | HKD | 134 | 132 | token_on_page | match |
| Bilanzsumme | 1.155.673 | HKD Mio. | 136 | – | n/a (derived) | – |
| Verbindlichkeiten gesamt | 467.281 | HKD Mio. | 136 | – | n/a (derived) | – |
| Eigenkapital gesamt | 688.392 | HKD Mio. | 137 | 135 | row_confirmed | – |
| Eigenkapital (Aktionäre) | 562.772 | HKD Mio. | 137 | 135 | row_confirmed | – |
| Liquide Mittel (lt. Definition) | 143.748 | HKD Mio. | 136 | 134 | row_confirmed | – |
| Operativer Cashflow | 62.567 | HKD Mio. | 141 | 139 | row_confirmed | – |
| Investitionen (Capex, lt. Definition) | 18.743 | HKD Mio. | 141 | 139 | row_confirmed | – |
| Free Cashflow (OCF − Capex) | 43.824 | HKD Mio. | 141 | – | n/a (derived) | – |
| Gezahlte Dividenden (Aktionäre) | 8.518 | HKD Mio. | 141 | 139 | row_confirmed | – |
| Dividende je Aktie (GJ) | 2,312 | HKD | 17 | 15 | token_on_page | match |
| Nettoverschuldung (lt. Emittent) | 117.885 | HKD Mio. | 142 | 140 | row_confirmed | – |

Kennzahlen (berechnet aus obigen Werten): net_margin=0.0423, return_on_equity_simple=0.0210, equity_ratio=0.5957, liabilities_to_assets=0.4043, cash_conversion=3.2301, payout_ratio_per_share=0.7482, cash_dividend_cover=5.1449

Hinweise:
- A US$ convenience-translation column precedes the HK$ columns; it is ignored.
- Financial-highlights "total revenue" (HK$507,297m) is on a proportionate basis incl. associates/JVs and is NOT comparable with IFRS revenue (HK$280,036m).

## Swire Pacific Limited (0019.HK)

- Geschäftsjahr: 2025 (Stichtag 2025-12-31)
- Rechnungslegung: HKFRS Accounting Standards (HKICPA)
- Berichtswährung/Einheit: HKD, million
- Quelle: <https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0408/2026040800985.pdf>
- PDF: 260 Seiten, SHA-256 `2f4b1b4435e04184d4b5940f21b96c2ce34c91af9eb95eeb4d825a31313a60a2` (Profil: match)
- Status: **extracted_consistent**; Prüfungen: balance_sheet_identity=pass, profit_split=pass, net_assets_equals_total_equity=pass, net_debt_definition=pass, dps_matches_ten_year_summary=pass

- 2. PDF-Engine (pdfplumber): 23 Zeile bestätigt, 6 Wert auf Seite, 0 nicht gefunden

| Kennzahl | Wert | Einheit | PDF-S. | Druck-S. | 2. Engine | Referenz |
|---|---:|---|---:|---:|---|---|
| Umsatz | 90.467 | HKD Mio. | 147 | 145 | row_confirmed | match |
| Operativer Gewinn | 4.454 | HKD Mio. | 147 | 145 | row_confirmed | match |
| Gewinn vor Steuern | 5.836 | HKD Mio. | 147 | 145 | row_confirmed | – |
| Jahresüberschuss (inkl. Minderheiten) | 3.495 | HKD Mio. | 147 | 145 | row_confirmed | – |
| Konzerngewinn (Aktionäre) | 2.938 | HKD Mio. | 147 | 145 | row_confirmed | match |
| Ergebnis je Aktie (unverwässert) | 2,17 | HKD | 147 | 145 | row_confirmed | – |
| Bilanzsumme | 476.413 | HKD Mio. | 149 | – | n/a (derived) | – |
| Verbindlichkeiten gesamt | 160.178 | HKD Mio. | 149 | – | n/a (derived) | – |
| Eigenkapital gesamt | 316.235 | HKD Mio. | 149 | 147 | row_confirmed | – |
| Eigenkapital (Aktionäre) | 259.577 | HKD Mio. | 149 | 147 | row_confirmed | – |
| Liquide Mittel (lt. Definition) | 23.172 | HKD Mio. | 149 | 147 | row_confirmed | – |
| Operativer Cashflow | 14.551 | HKD Mio. | 150 | 148 | row_confirmed | – |
| Investitionen (Capex, lt. Definition) | 5.595 | HKD Mio. | 150 | 148 | row_confirmed | – |
| Free Cashflow (OCF − Capex) | 8.956 | HKD Mio. | 150 | – | n/a (derived) | – |
| Gezahlte Dividenden (Aktionäre) | 4.602 | HKD Mio. | 150 | 148 | row_confirmed | – |
| Dividende je Aktie (GJ) | 3,8 | HKD | 170 | – | n/a (derived) | match |
| Nettoverschuldung (lt. Emittent) | 65.264 | HKD Mio. | 92 | 90 | row_confirmed | match |

Kennzahlen (berechnet aus obigen Werten): net_margin=0.0325, operating_margin=0.0492, return_on_equity_simple=0.0113, equity_ratio=0.6638, liabilities_to_assets=0.3362, cash_conversion=4.1634, payout_ratio_per_share=1.7512, cash_dividend_cover=1.9461

Hinweise:
- Two share classes ('A' and 'B'); per-share figures refer to 'A' shares (0019.HK). 'B' shares (0087.HK) receive 1/5.
- Cash flow closing cash (HK$20,966m) differs from balance-sheet bank balances (HK$23,172m) because deposits > 3 months are excluded.
- Large non-cash investment-property revaluation losses depress IFRS profit; issuer also reports underlying profit.

## First Pacific Company Limited (0142.HK)

- Geschäftsjahr: 2025 (Stichtag 2025-12-31)
- Rechnungslegung: HKFRS Accounting Standards (HKICPA)
- Berichtswährung/Einheit: USD, million
- Quelle: <https://www.firstpacific.com/wp-content/uploads/2026/04/ew0142.pdf>
- PDF: 222 Seiten, SHA-256 `4dca002f1a256863e5343968f47d6f669dfcdf7930509a445f6aad0585822fe0` (Profil: match)
- Status: **extracted_consistent**; Prüfungen: balance_sheet_identity=pass, profit_split=pass, dps_interim_plus_final_usd=pass

- 2. PDF-Engine (pdfplumber): 19 Zeile bestätigt, 8 Wert auf Seite, 0 nicht gefunden

| Kennzahl | Wert | Einheit | PDF-S. | Druck-S. | 2. Engine | Referenz |
|---|---:|---|---:|---:|---|---|
| Umsatz | 10.232,5 | USD Mio. | 103 | 101 | row_confirmed | match |
| Gewinn vor Steuern | 2.252 | USD Mio. | 103 | 101 | row_confirmed | – |
| Jahresüberschuss (inkl. Minderheiten) | 1.780,9 | USD Mio. | 103 | 101 | row_confirmed | – |
| Konzerngewinn (Aktionäre) | 661 | USD Mio. | 103 | 101 | row_confirmed | match |
| Ergebnis je Aktie (unverwässert) | 15,53 | USD Cent | 103 | 101 | row_confirmed | – |
| Bilanzsumme | 30.647,6 | USD Mio. | 105 | – | n/a (derived) | – |
| Verbindlichkeiten gesamt | 17.524 | USD Mio. | 105 | – | n/a (derived) | – |
| Eigenkapital gesamt | 13.123,6 | USD Mio. | 105 | 103 | row_confirmed | – |
| Eigenkapital (Aktionäre) | 4.388,8 | USD Mio. | 105 | 103 | row_confirmed | – |
| Liquide Mittel (lt. Definition) | 4.206,1 | USD Mio. | 105 | 103 | row_confirmed | – |
| Operativer Cashflow | 1.748,3 | USD Mio. | 107 | 105 | row_confirmed | – |
| Investitionen (Capex, lt. Definition) | 528,8 | USD Mio. | 108 | 106 | row_confirmed | – |
| Free Cashflow (OCF − Capex) | 1.219,5 | USD Mio. | 107+108 | – | n/a (derived) | – |
| Gezahlte Dividenden (Aktionäre) | 144,6 | USD Mio. | 108 | 106 | row_confirmed | – |
| Dividende je Aktie (GJ) | 27 | HKD Cent | 14 | 12 | token_on_page | – |

Kennzahlen (berechnet aus obigen Werten): net_margin=0.0646, return_on_equity_simple=0.1506, equity_ratio=0.4282, liabilities_to_assets=0.5718, cash_conversion=0.9817, payout_ratio_per_share=0.2228, cash_dividend_cover=8.4336

Hinweise:
- Reporting currency USD; distributions declared in HK cents with U.S. cent equivalents.
- A 2025 special distribution (Maynilad shares + cash, ~U.S. 0.15 cent/share) is excluded from dividend_per_share.
- Cash flow closing cash (US$4,149.4m) excludes deposits > 3 months contained in balance-sheet cash (US$4,206.1m).

## DBS Group Holdings Ltd (D05.SI)

- Geschäftsjahr: 2025 (Stichtag 2025-12-31)
- Rechnungslegung: SFRS(I) (Singapore Financial Reporting Standards (International))
- Berichtswährung/Einheit: SGD, million
- Quelle: <https://www.dbs.com/iwov-resources/images/investors/annual-report/dbs-annual-report-2025.pdf>
- PDF: 107 Seiten, SHA-256 `e7952ba9dff9e339070334ec5d67a71c81a8c618be7f34abad6f3118189b38ce` (Profil: match)
- Status: **extracted_consistent**; Prüfungen: balance_sheet_identity=pass, profit_split=pass, net_assets_equals_total_equity=pass, total_income_components=pass, dps_components=pass

- 2. PDF-Engine (pdfplumber): 10 Zeile bestätigt, 16 Wert auf Seite, 0 nicht gefunden

| Kennzahl | Wert | Einheit | PDF-S. | Druck-S. | 2. Engine | Referenz |
|---|---:|---|---:|---:|---|---|
| Umsatz | 22.900 | SGD Mio. | 58 | 112-113 | token_on_page | – |
| Gewinn vor Steuern | 12.999 | SGD Mio. | 58 | 112-113 | token_on_page | – |
| Jahresüberschuss (inkl. Minderheiten) | 10.934 | SGD Mio. | 58 | 112-113 | token_on_page | – |
| Konzerngewinn (Aktionäre) | 10.933 | SGD Mio. | 58 | 112-113 | token_on_page | – |
| Ergebnis je Aktie (unverwässert) | 3,84 | SGD | 58 | 112-113 | row_confirmed | – |
| Bilanzsumme | 897.488 | SGD Mio. | 59 | 114-115 | row_confirmed | – |
| Verbindlichkeiten gesamt | 828.572 | SGD Mio. | 59 | 114-115 | token_on_page | – |
| Eigenkapital gesamt | 68.916 | SGD Mio. | 59 | 114-115 | row_confirmed | – |
| Eigenkapital (Aktionäre) | 68.867 | SGD Mio. | 59 | 114-115 | row_confirmed | – |
| Liquide Mittel (lt. Definition) | 55.844 | SGD Mio. | 59 | 114-115 | row_confirmed | – |
| Operativer Cashflow | 11.024 | SGD Mio. | 60 | 116-117 | row_confirmed | – |
| Investitionen (Capex, lt. Definition) | 525 | SGD Mio. | 60 | 116-117 | row_confirmed | – |
| Gezahlte Dividenden (Aktionäre) | 8.151 | SGD Mio. | 60 | 116-117 | token_on_page | – |
| Dividende je Aktie (GJ) | 3,06 | SGD | 89 | 174-175 | token_on_page | – |

Kennzahlen (berechnet aus obigen Werten): net_margin=0.4774, return_on_equity_simple=0.1588, equity_ratio=0.0768, liabilities_to_assets=0.9232, payout_ratio_per_share=0.7969

Hinweise:
- Bank: "revenue" is total income; FCF/operating-margin style ratios are not meaningful and are suppressed.
- PDF pages are two-page spreads; printed pages are given as ranges (e.g. 112-113).
- Balance sheet page shows Group and Company columns; Group 2025 column (index 0) is used.

## BYD Company Limited (比亚迪股份有限公司) (002594.SZ)

- Geschäftsjahr: 2025 (Stichtag 2025-12-31)
- Rechnungslegung: PRC Accounting Standards for Business Enterprises (企业会计准则)
- Berichtswährung/Einheit: CNY, thousand
- Quelle: <https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-03-28/f5cdbdbf-b138-4e83-8c6d-5a7eecb9e670.PDF>
- PDF: 268 Seiten, SHA-256 `710d8b2e08e37ba521f1c4071d2c3e2369d3cadabc21a45073215d9f72138b0b` (Profil: match)
- Status: **extracted_consistent**; Prüfungen: balance_sheet_identity=pass, profit_split=pass, liabilities_and_equity_total=pass, assets_split=pass, liabilities_split=pass, dps_vs_per_10_shares=pass

- 2. PDF-Engine (pdfplumber): 26 Zeile bestätigt, 3 Wert auf Seite, 0 nicht gefunden

| Kennzahl | Wert | Einheit | PDF-S. | Druck-S. | 2. Engine | Referenz |
|---|---:|---|---:|---:|---|---|
| Umsatz | 803.964.958 | CNY Tsd. | 126 | 126 | row_confirmed | – |
| Operativer Gewinn | 40.184.709 | CNY Tsd. | 126 | 126 | row_confirmed | – |
| Gewinn vor Steuern | 39.753.049 | CNY Tsd. | 126 | 126 | row_confirmed | – |
| Jahresüberschuss (inkl. Minderheiten) | 33.760.758 | CNY Tsd. | 126 | 126 | row_confirmed | – |
| Konzerngewinn (Aktionäre) | 32.619.022 | CNY Tsd. | 126 | 126 | row_confirmed | – |
| Ergebnis je Aktie (unverwässert) | 3,58 | CNY | 126 | 126 | row_confirmed | – |
| Bilanzsumme | 883.729.883 | CNY Tsd. | 123 | 123 | row_confirmed | – |
| Verbindlichkeiten gesamt | 625.190.698 | CNY Tsd. | 124 | 124 | row_confirmed | – |
| Eigenkapital gesamt | 258.539.185 | CNY Tsd. | 125 | 125 | row_confirmed | – |
| Eigenkapital (Aktionäre) | 246.274.606 | CNY Tsd. | 125 | 125 | row_confirmed | – |
| Liquide Mittel (lt. Definition) | 75.424.747 | CNY Tsd. | 123 | 123 | row_confirmed | – |
| Operativer Cashflow | 59.135.544 | CNY Tsd. | 130 | 130 | row_confirmed | – |
| Investitionen (Capex, lt. Definition) | 156.807.853 | CNY Tsd. | 130 | 130 | row_confirmed | – |
| Free Cashflow (OCF − Capex) | -97.672.309 | CNY Tsd. | 130 | – | n/a (derived) | – |
| Dividende je Aktie (GJ) | 0,358 | CNY | 249 | 249 | token_on_page | – |

Kennzahlen (berechnet aus obigen Werten): net_margin=0.0406, operating_margin=0.0500, return_on_equity_simple=0.1324, equity_ratio=0.2926, liabilities_to_assets=0.7074, cash_conversion=1.7516, payout_ratio_per_share=0.1000

Hinweise:
- Amounts in RMB thousand (千元), as stated on page 123 (财务附注中报表的单位为：千元).
- 2024 comparatives in the income statement are restated (经重述); 2024 EPS adjusted for the 2025 bonus issue (8 bonus shares + 12 capitalisation shares per 10).
- Cash-flow line for dividends also contains interest payments; no cash dividend cover is computed.
- Dividend per share is a board proposal pending AGM approval.

