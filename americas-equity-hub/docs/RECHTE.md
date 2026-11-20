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
| Deutsche Börse AG (Market Data + Services) (deutsche_boerse_delayed) | DE | allowed | allowed | allowed | unknown | allowed | restricted | restricted | nein |
| Deutsche Börse AG / Börse Frankfurt (deutsche_boerse_instrumente) | DE | allowed | unknown | unknown | unknown | unknown | unknown | unknown | nein |
| Tradegate Exchange (Tradegate BSX) (tradegate_delayed) | DE | allowed | unknown | unknown | unknown | unknown | unknown | unknown | nein |

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

### Deutsche Börse AG (Market Data + Services)
- Datensatz: Verzögerte MiFIR-Post-Trade-Dateien Xetra und Börse Frankfurt (mfs.deutsche-boerse.com) – Grundlage aller Kurse der Website
- Bedingungen: https://www.mds.deutsche-boerse.com/resource/blob/5322802/8a82ea41893249520d1b5fb4878c8dad/data/Market%20Data%20Policy%20Guidelines%20and%20FAQ_V3_0.pdf (abgerufen 2026-11-20)
- Beleg: Market Data Policy Guidelines and FAQ V3.0, S. 17: "The access to and use of the Delayed Data is subject to a license ... A free of charge usage right is only granted if the User who is accessing and using Delayed Data (“Delayed Data User”) does not commercialize the Delayed Data. A commercialization of Delayed Data which is subject to license for a fee and applies in the following events (non-exhaustive list): • Delayed Data User onward disseminates Delayed Data to third parties for a fee (including a general fee for accessing its services); • Delayed Data User creates and offers value-added services using Delayed Data which are then sold for a fee ..." Preisliste MDDA 16.3, S. 5 (Distribution License, Delayed, je Monat): Xetra Post-Trade 743 €, Börse Frankfurt Post-Trade 372 €, Xetra Core (inkl. beider) 1.820 €.
- Auflagen: kostenlos nur ohne Kommerzialisierung; Gebühr/Bezahlzugang auf die Dienste oder verkaufte Mehrwertdienste mit diesen Daten = lizenzpflichtig (Distribution License)
- **Offene Frage zur rechtlichen Prüfung:** Gilt die heutige kostenlose, werbe-/abofreie Anzeige als nicht kommerziell? Spätestens mit Bezahlbereich (Freemium) ist eine Distribution License nötig (Preisliste: Delayed Xetra Post-Trade 743 €/Monat + Börse Frankfurt Post-Trade 372 €/Monat oder Xetra Core 1.820 €/Monat). Speicherung einer eigenen Kurshistorie: im Vertrag (MDDA) zu klären.

### Deutsche Börse AG / Börse Frankfurt
- Datensatz: Liste aller handelbaren Instrumente Xetra (t7-xetr-allTradableInstruments.csv) – ISIN und Name
- Bedingungen: https://www.cashmarket.deutsche-boerse.com/cash-en/disclaimer (abgerufen 2026-11-20)
- Beleg: Auf der Seite und im Disclaimer keine Nutzungsbedingungen für die Liste; der Disclaimer regelt nur Haftung und Marken ("They may not be used or exploited without the prior express consent of the respective owner" bezieht sich auf die Marken).
- **Offene Frage zur rechtlichen Prüfung:** Darf die Instrumentenliste (ISIN-Zuordnung) gespeichert und für eine öffentliche/kommerzielle Website genutzt werden? Anfrage an data.services@deutsche-boerse.com.

### Tradegate Exchange (Tradegate BSX)
- Datensatz: Verzögerte Post-Trade-Dateien über mfs.deutsche-boerse.com
- Bedingungen: None (abgerufen 2026-11-20)
- Beleg: Die Datei wird über den Dienst der Deutschen Börse angeboten; Tradegate steht nicht in der Preisliste der Deutschen Börse; eigene Bedingungen von Tradegate nicht geprüft.
- **Offene Frage zur rechtlichen Prüfung:** Bedingungen der Tradegate Exchange für verzögerte Daten.

