# Quellen und Nutzungsrechte (Stand 2026-11-20)

Keine Rechtsberatung. `unknown` ist nicht `allowed`. Export nur bei `allowed` für Speichern, öffentliche API und kommerzielle Nutzung.

| Quelle | Land | einsehen | Download | Extraktion | Speichern | intern | öff. API | kommerziell | Export |
|---|---|---|---|---|---|---|---|---|---|
| CVM (Comissão de Valores Mobiliários) (cvm_dados_abertos) | BR | allowed | allowed | allowed | allowed | allowed | allowed | allowed | ja |
| B3 S.A. (b3_website) | BR | allowed | unknown | unknown | unknown | restricted | prohibited | prohibited | nein |
| TMX Group (TSX, TSXV) (tmx_website) | CA | allowed | unknown | unknown | restricted | restricted | prohibited | prohibited | nein |
| BlackRock Asset Management Canada (blackrock_ishares_holdings) | CA | allowed | unknown | unknown | restricted | restricted | prohibited | prohibited | nein |
| S&P Dow Jones Indices (spdji) | CA/MX | unknown | unknown | unknown | unknown | unknown | unknown | unknown | nein |
| CSA – SEDAR+ (sedar_plus) | CA | allowed | prohibited | unknown | unknown | unknown | unknown | unknown | nein |
| Bolsa Mexicana de Valores (bmv_website) | MX | allowed | prohibited | prohibited | prohibited | restricted | prohibited | prohibited | nein |
| Bolsa Institucional de Valores (biva_website) | MX | allowed | unknown | unknown | unknown | unknown | unknown | unknown | nein |
| Comisión Nacional Bancaria y de Valores (cnbv) | MX | unknown | unknown | unknown | unknown | unknown | unknown | unknown | nein |
| U.S. Securities and Exchange Commission (sec_edgar) | US | allowed | allowed | allowed | allowed | allowed | allowed | allowed | ja |
| GLEIF (gleif) | global | allowed | allowed | allowed | allowed | allowed | allowed | allowed | ja |
| ESMA (esma_firds) | EU | allowed | allowed | allowed | unknown | allowed | unknown | unknown | nein |

## Belege

### CVM (Comissão de Valores Mobiliários)
- Datensatz: cia_aberta CAD, FCA, DFP (CSV)
- Bedingungen: https://opendatacommons.org/licenses/odbl/1-0/ (abgerufen 2026-11-20)
- Beleg: Datensatzseite: "Licença: Licença Aberta para Bases de Dados (ODbL) do Open Data Commons"; robots.txt: Disallow /api/, Crawl-Delay: 10
- Auflagen: Namensnennung CVM/ODbL; Share-Alike: öffentlich genutzte abgeleitete Datenbanken unter ODbL anbieten; Crawl-Delay 10 s, /api/ nicht abrufen
- **Offene Frage zur rechtlichen Prüfung:** Reichweite der ODbL-Share-Alike-Pflicht für den Hub (abgeleitete Datenbank vs. Produced Work) – zur Prüfung.

### B3 S.A.
- Datensatz: COTAHIST, Indexportfolio, Emittenten-/Ausschüttungsdaten der Website
- Bedingungen: https://www.b3.com.br/pt_br/termos-de-uso-e-protecao-de-dados/termos-de-uso/ (abgerufen 2026-11-19)
- Beleg: "É vedada a utilização dos dados contidos neste website para fins comerciais salvo mediante autorização prévia e por escrito da B3." / "É vedada a distribuição, redistribuição ... publicação ... exceto mediante prévio e expresso consentimento da B3." (Abruf 20.11.2026: HTTP 403)
- **Offene Frage zur rechtlichen Prüfung:** Schriftliche Erlaubnis/Lizenz der B3 für Kurse, Indexportfolios, Ausschüttungen (JCP) und ISIN-Daten.

### TMX Group (TSX, TSXV)
- Datensatz: Firmenverzeichnis, Interlisted-Liste, MiG-Report
- Bedingungen: https://www.tsx.com/en/terms-of-use (abgerufen 2026-11-20)
- Beleg: "TMX grants to you a limited non-exclusive, non-transferable license to view and print the material on the Websites for your non-commercial or personal use only."
- **Offene Frage zur rechtlichen Prüfung:** Lizenz der TMX (TMX Datalinx) für Listings, Kurse, Venture-Daten.

### BlackRock Asset Management Canada
- Datensatz: Bestandsliste iShares XIC/XIU (Proxy für S&P/TSX-Mitglieder)
- Bedingungen: https://www.blackrock.com/ca/investors/en/terms-and-conditions (abgerufen 2026-11-20)
- Beleg: "Such content is solely for your personal, non-commercial use." / "You may not distribute, modify, transmit, reuse, repost, or use the content of this Website for public or commercial purposes ... without BlackRock's written permission."
- **Offene Frage zur rechtlichen Prüfung:** Wurde in PR #130 als Indexproxy verwendet und veröffentlicht; mit diesem Stand entfernt. Git-Historie enthält die Datei weiterhin (Entfernung = Umschreiben von main, nur nach Entscheidung des Eigentümers).

### S&P Dow Jones Indices
- Datensatz: S&P/TSX- und S&P/BMV-Indexmitglieder
- Bedingungen: https://www.spglobal.com/en/terms-of-use (abgerufen 2026-11-20)
- Beleg: Nutzungsbedingungen und Indexseiten: HTTP 403 (nicht abrufbar); Mitgliederlisten werden als Lizenzprodukt vertrieben.
- **Offene Frage zur rechtlichen Prüfung:** Indexlizenz S&P DJI für Mitglieder und Historie.

### CSA – SEDAR+
- Datensatz: Pflichtveröffentlichungen kanadischer Emittenten
- Bedingungen: https://www.sedarplus.ca/onlinehelp/terms-of-use/ (abgerufen 2026-11-20)
- Beleg: Weiterleitung auf Bot-Schutz (validate.perfdrive.com); Nutzungsbedingungen nicht abrufbar. Technischer Schutz wird nicht umgangen.
- **Offene Frage zur rechtlichen Prüfung:** Bedingungen von SEDAR+ für Speicherung/Weitergabe von Berichtsdaten; manueller Abruf je Bericht.

### Bolsa Mexicana de Valores
- Datensatz: Emittenten, Berichte, Kurse, Indizes der Website
- Bedingungen: https://www.bmv.com.mx/es/Grupo_BMV/Aviso_legal (abgerufen 2026-11-20)
- Beleg: "El contenido del presente Sitio no podrá ser reproducido con o sin fines de lucro, a menos que se cuente con la previa autorización por escrito de la BMV" / "queda expresamente prohibida ... parsing (uso de algoritmos para extraer del código HTML ...)"
- **Offene Frage zur rechtlichen Prüfung:** Schriftliche Erlaubnis der BMV.

### Bolsa Institucional de Valores
- Datensatz: Emittenten, Serien/ISIN, FIBRAs, SIC, CNBV-XBRL-Berichte
- Bedingungen: https://www.biva.mx/terminos-y-condiciones (abgerufen 2026-11-20)
- Beleg: Bedingungen werden nur per JavaScript geladen und konnten nicht gelesen werden; robots.txt: nur /es/web/ gesperrt.
- **Offene Frage zur rechtlichen Prüfung:** Nutzungsbedingungen der BIVA für Emittentendaten und die gespiegelten CNBV-Berichte (XBRL).

### Comisión Nacional Bancaria y de Valores
- Datensatz: Emittentenberichte
- Bedingungen: None (abgerufen 2026-11-20)
- Beleg: www.cnbv.gob.mx: TLS-Zertifikat nicht prüfbar (keine Verbindung ohne Abschalten der Prüfung, wird nicht gemacht).
- **Offene Frage zur rechtlichen Prüfung:** Offizieller Abrufweg und Bedingungen der CNBV.

### U.S. Securities and Exchange Commission
- Datensatz: EDGAR-Formularverzeichnis, submissions, companyfacts (XBRL), company_tickers_exchange
- Bedingungen: https://www.sec.gov/privacy (abgerufen 2026-11-20)
- Beleg: "Information presented on www.sec.gov is considered public information and may be copied or further distributed by users of the web site without the SEC's permission." (Abruf mit Absenderkennung, Rate-Limit beachten)
- Auflagen: User-Agent mit Kontakt (Secret SEC_UA); höchstens 10 Anfragen je Sekunde

### GLEIF
- Datensatz: LEI-Register, LEI-ISIN-Zuordnung
- Bedingungen: https://www.gleif.org/en/meta/lei-data-terms-of-use (abgerufen 2026-11-20)
- Beleg: "The data available through the Access Service are provided under the CC0 licence"

### ESMA
- Datensatz: FIRDS (registers.esma.europa.eu)
- Bedingungen: https://www.esma.europa.eu/about-esma/legal-notice-and-data-protection (abgerufen 2026-11-20)
- Beleg: "Reproduction of all information on this site (ESMA Library) is authorised except as otherwise stated, provided the source is acknowledged" – bezieht sich ausdrücklich auf die ESMA Library; ob das Register erfasst ist, ist nicht belegt.
- **Offene Frage zur rechtlichen Prüfung:** Gilt der Legal Notice (Reproduktion mit Quellenangabe) auch für die FIRDS-Registerdaten? Bis dahin ISINs nur über GLEIF (CC0) veröffentlichen.

