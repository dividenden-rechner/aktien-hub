# Nutzungsrechte aller Datenquellen der Website (Stand 2026-11-20)

Geprüft wurden alle Quellen, die im Repository produktiv genutzt werden (Werkzeuge in `tools/`, Hubs, Workflows).
Jede Angabe beruht auf den am 20.11.2026 abgerufenen Bedingungen; Zitate sind wörtlich. **Keine Rechtsberatung** –
die Einstufung zeigt, was die Texte sagen; offene Punkte gehören zur rechtlichen Prüfung.

Zwecke: **öffentlich** = Anzeige/Veröffentlichung auf der Website, **kommerziell** = Website mit Bezahlbereich, Werbung o. ä.
Status: `erlaubt` · `eingeschränkt` (Bedingungen oder Gebühr) · `ungeklärt` (keine Bedingungen auffindbar/lesbar) · `verboten`.

## Überblick nach Wirkung auf die Website

| Bereich der Website | Quelle | öffentlich | kommerziell | Folge |
|---|---|---|---|---|
| **Kurse** (Kennzahlen, Screener, Hub, Depot) | Deutsche Börse – verzögerte Daten Xetra/Frankfurt | erlaubt, solange nicht kommerzialisiert | **eingeschränkt: Lizenzgebühr** | ok für die kostenlose Seite; mit Bezahlbereich Lizenz nötig |
| Kurse – **380 von ~1.280** Kennzahlen-Kursen | **Tradegate** | **verboten** ohne schriftliche Zustimmung | verboten | sofort betroffen, auch ohne Bezahlbereich |
| Kurse BDC/REIT, Asien (Tokio 42, Seoul 10) über Google Sheets | **Google Finance** (`GOOGLEFINANCE`) | **verboten** | verboten | sofort betroffen |
| Kurse Asien | **Yahoo** | **verboten** (Automatik + kommerziell) | verboten | sofort betroffen |
| Hub-Livedaten, Logos, News | **FMP** (Financial Modeling Prep) | **verboten** mit Standardlizenz | verboten | abhängig vom gebuchten FMP-Tarif |
| Jahreszahlen USA/Kanada/Mexiko/20-F | SEC EDGAR | erlaubt | erlaubt | ok |
| Jahreszahlen Brasilien | CVM Dados Abertos | erlaubt (ODbL) | erlaubt (ODbL) | Namensnennung, Share-Alike prüfen |
| Jahreszahlen Japan | EDINET (FSA) | erlaubt (PDL1.0) | erlaubt (PDL1.0) | Quellenangabe + Bearbeitungshinweis |
| Jahreszahlen Korea | OpenDART (FSS) | erlaubt laut Nutzungsbedingungen (kein Verbot) | ungeklärt (Verweis auf Gesetz) | sehr wahrscheinlich ok |
| Jahreszahlen Europa (ESEF) | filings.xbrl.org (XBRL International) | **ungeklärt** – keine Lizenz angegeben | ungeklärt | anfragen oder auf amtliche OAMs ausweichen |
| Jahreszahlen DAX/CAC/FTSE u. a. – **337 Firmen** | **boerse.de** | **verboten** („Aufnahme in … Internet … nur nach vorheriger schriftlicher Zustimmung“) | verboten | sofort betroffen |
| Geschäftsberichte Hongkong (CKH, Swire, FP) | **HKEXnews / HKEX** | **verboten** (Scraping/Automatik) | verboten | sofort betroffen |
| Geschäftsberichte China | CNINFO | ungeklärt (Bedingungen nicht abrufbar) | ungeklärt | anfragen |
| Geschäftsberichte/Listen Singapur | SGX | ungeklärt (Seite lädt nur per JavaScript) | ungeklärt | anfragen |
| Europa-Universum: Listen | **Euronext** | **verboten** (Automatik + Wiederverwendung) | verboten | Euronext-Liste herausnehmen |
| Europa-Universum: Listen | **Nasdaq (Nordic)** | **verboten** („solely for your personal, non-commercial use“) | verboten | herausnehmen |
| Europa-Universum: Listen | SIX | ungeklärt (Bedingungen nicht auffindbar) | ungeklärt | anfragen |
| Europa-Universum: Listen | ESMA FIRDS | erlaubt (Lesen) / ungeklärt (Veröffentlichen) | ungeklärt | ESMA fragen |
| Europa-Universum: Listen | FCA FIRDS | eingeschränkt (persönlich; OGL nur für „Data section“) | ungeklärt | FCA fragen |
| ISIN-Zuordnung | Deutsche Börse Instrumentenliste | ungeklärt | ungeklärt | mit der Kurs-Anfrage klären |
| ISIN-Zuordnung | OpenFIGI (Bloomberg) | erlaubt | erlaubt | ok |
| LEI | GLEIF | erlaubt (CC0) | erlaubt | ok |
| Wechselkurse | EZB | erlaubt (Quelle nennen) | erlaubt | ok |
| Earnings-Termine | Alpha Vantage | ungeklärt (Bedingungen nicht lesbar) | ungeklärt | prüfen |
| Firmen-News | Google News RSS | ungeklärt | ungeklärt | prüfen |
| Japan-Liste | JPX | ungeklärt (Hinweis untersagt Weitergabe von Kursinformationen Dritter) | ungeklärt | anfragen |
| Americas (siehe americas-equity-hub/docs/RECHTE.md) | B3, TMX, BlackRock, BMV, S&P | verboten/lizenzpflichtig | verboten | bereits herausgenommen (PR #133) |

Alle genannten Abläufe laufen täglich (Workflows asien-yahoo-kurse, bdc-/reit-/asien-sheet-kurse, bdc-kurse-fmp, av-earnings, firmennews, news, europa-universum; letzter Lauf 19./20.11.2026).

## Belege (wörtlich)

**Deutsche Börse – verzögerte Daten** (Market Data Policy Guidelines and FAQ V3.0, S. 17; Preisliste MDDA 16.3, S. 5):
„A free of charge usage right is only granted if the User who is accessing and using Delayed Data (“Delayed Data User”) does not commercialize the Delayed Data.“ Kommerzialisierung u. a.: „onward disseminates Delayed Data to third parties for a fee (including a general fee for accessing its services)“, „creates and offers value-added services using Delayed Data which are then sold for a fee“. Lizenz (Delayed, je Monat): Xetra Post-Trade 743 €, Börse Frankfurt Post-Trade 372 €, Xetra Core 1.820 €.

**Tradegate** (tradegatebsx.com/nutzungsbedingung.php): „Ohne die vorherige schriftliche Zustimmung der Tradegate Exchange GmbH dürfen weder diese Website, noch die darin zur Verfügung gestellten Daten und Informationen (insbesondere Preis-, Umsatz- und Stammdaten …) kopiert, gespeichert, nachgedruckt, veröffentlicht, versandt, übertragen oder in irgendeiner Weise verbreitet oder vertrieben werden.“

**Google Finance** (google.com/googlefinance/disclaimer): „You agree not to copy, modify, reformat, download, store, reproduce, reprocess, transmit or redistribute any data or information found herein or use any such data or information in a commercial enterprise without obtaining prior written consent.“

**Yahoo** (legal.yahoo.com, Terms): verboten ist, „access or collect data … using any automated means … robots, spiders, scrapers …“; „Unless otherwise expressly stated, you may not access or reuse the Services, or any portion thereof, for any commercial purpose.“

**FMP** (site.financialmodelingprep.com/terms-of-service, 2.2.1): „This license may only be used by a Customer who is an individual, and strictly for their own personal, non-business and non-commercial purposes … may not … integrate the Data or Services into any tools or applications accessible by any third parties, or use the Services to host, share, display, or provide content for others.“ (Anzeigelizenzen gibt es als eigene Tarife.)

**boerse.de** (boerse.de/disclaimer): „Insbesondere dürfen Nachdruck, Aufnahme in Onlinedienste und Internet sowie Vervielfältigungen auf Datenträgern sowie Ausdrucke nur nach vorheriger schriftlicher Zustimmung der boerse.de Finanzportal GmbH erfolgen; Ausnahme bei privatem, nicht kommerziellen Gebrauch.“

**HKEX** (hkex.com.hk Terms of Use): „You are not permitted to conduct, facilitate, enable, authorise or permit any text or data mining or web scraping in relation to this Website …“; erlaubt nur Speichern „for your personal use“; „You are not permitted to use, without HKEX’s express written permission, the Website, or any Information … for any other purposes not explicitly set out in these Terms.“

**Euronext** (euronext.com/en/terms-use): „you will not sell, license, rent, modify, print, copy, reproduce, download, upload, transmit, distribute, disseminate, publicly display … or create derivative works from any Content … (including … systematic retrieval to create collections, compilations, databases …)“; „use of any … spiders, robots … is strictly prohibited.“

**Nasdaq** (nasdaq.com/legal): „… license to use the Services solely for your personal, non-commercial use.“

**SEC** (sec.gov/privacy): „Information presented on www.sec.gov is considered public information and may be copied or further distributed by users of the web site without the SEC’s permission.“

**CVM**: Datensatzseiten: „Licença Aberta para Bases de Dados (ODbL) do Open Data Commons“.

**EDINET** (EDINET利用規約): Inhalte nutzbar „「公共データ利用規約（第1.0版）」（PDL1.0）に準拠した利用条件の下で“; Quelle angeben, Bearbeitung kennzeichnen; Scraping verboten außer über die API („API機能を利用する場合 … この限りではありません“).

**OpenDART** (opendart.fss.or.kr/intro/terms.do): Dienst „원칙적으로 무료“ (Art. 11); kein Nutzungsverbot; Art. 5/16: Nicht Geregeltes folgt dem „공공데이터의 제공 및 이용 활성화에 관한 법률“.

**filings.xbrl.org** (/docs/about): beschreibt Zweck und Inhalt, nennt **keine** Lizenz.

**GLEIF**: „The data available through the Access Service are provided under the CC0 licence“. **OpenFIGI**: FIGI „may be freely reproduced, distributed … for any purpose, commercial or non-commercial“. **EZB**: „users … may make free use of the information … the ECB must be cited as the source.“

**FCA** (fca.org.uk/legal): Kopien „for personal use or for use within an individual firm“; Ausnahme: UK Open Government Licence für „numerical datasets published within the Data section“.

## Empfohlene Reihenfolge

1. **Sofort (auch ohne Bezahlbereich):** Tradegate-, Google-Finance- und Yahoo-Kurse, boerse.de-Jahreszahlen, HKEX-Berichte und Euronext-/Nasdaq-Listen stoppen oder schriftliche Zustimmung einholen. FMP-Tarif prüfen.
2. **Vor dem Bezahlbereich:** Lizenz der Deutschen Börse für verzögerte Daten (oder deren Bestätigung, wie der Bezahlbereich auszugestalten ist).
3. **Klären:** filings.xbrl.org (ESEF), CNINFO, SGX, SIX, ESMA/FCA FIRDS, Alpha Vantage, Google News, JPX, Deutsche-Börse-Instrumentenliste.
4. Die Anfragetexte stehen in `docs/rechte/ANFRAGEN.md`.
