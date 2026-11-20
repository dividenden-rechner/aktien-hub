# Americas Aktien-Hub – Quellenprüfung (Stand 2026-11-19)

Tatsächlich ausgeführte Abrufe aus der Claude-Code-Umgebung. Rohdateien liegen nur lokal (nicht im Repository).
Alle Angaben `verified=false`, `human_review=pending`. „Erreichbar“ heißt: HTTP 200 mit erwartetem Inhalt.

## Brasilien

| Quelle | Inhalt | Ergebnis | Heruntergeladen | Nutzung |
|---|---|---|---|---|
| CVM Dados Abertos `cad_cia_aberta.csv` | Register aller Emittenten (CNPJ, CVM-Code, Status, Sektor, Markt) | ✅ | 2.680 Emittenten (754 aktiv, 1.919 gelöscht) | ODbL (Open Data Commons) |
| CVM FCA `valor_mobiliario` 2010–2026 | Wertpapiere je Emittent: Gattung ON/PN/Units, Handelskürzel, Segment, Listungsdaten | ✅ | 2026: 966 Zeilen (407 ON, 155 PN, 12 Units); **ohne ISIN** | ODbL |
| CVM DFP 2010–2026 | Jahresabschlüsse aller Emittenten (BPA/BPP/DRE/DFC/DMPL/DVA, Konzern+Einzel, Aktienzahl) | ✅ | 2010 (8,9 MB) und 2025 (12,9 MB) geladen; Jahre 2010–2026 gelistet | ODbL |
| B3 COTAHIST (Jahresdateien) | Tagesschlusskurse aller Titel mit ISIN, Gattung, Kursfaktor; unbereinigt | ✅ | 2025 (89 MB gepackt) | ⚠️ B3-Nutzungsbedingungen: keine kommerzielle Nutzung/Weitergabe ohne schriftliche Erlaubnis |
| B3 `indexProxy/GetPortfolioDay` | Theoretisches Portfolio des Tages (IBOV usw.) | ✅ | IBOV: 76 Titel, Stichtag 19.11.2026; **nur aktueller Tag, keine Historie** | ⚠️ wie oben |
| B3 `listedCompaniesProxy` | Emittentenliste (3.555 inkl. BDR/Fonds), Aktienzahl, Barausschüttungen | ✅ | Beispiel PETR: DIVIDENDO / **JRS CAP PROPRIO (JCP)** / RENDIMENTO getrennt; nur wenige Jahre zurück | ⚠️ wie oben |

## Kanada

| Quelle | Inhalt | Ergebnis | Heruntergeladen | Nutzung |
|---|---|---|---|---|
| TMX `json/company-directory/search/tsx|tsxv` | Alle gelisteten Emittenten und Instrumente (Symbole) | ✅ | TSX 2.363, TSXV 1.421 Emittenten; **ohne ISIN, Währung, Sitzland** | ⚠️ TMX-Nutzungsbedingungen: nur „non-commercial or personal use“ |
| TMX `interlisted-companies.txt` | TSX-Titel mit US-Zweitlisting | ✅ | Stand 01.11.2026 | ⚠️ wie oben |
| TMX MiG-Report | Monatsstatistik | ✅ (PDF) | September 2026 | ⚠️ wie oben |
| S&P/TSX-Indexmitglieder (spglobal.com) | Composite, 60, Completion, SmallCap, Venture | ❌ HTTP 403; Mitgliederlisten sind lizenzpflichtig | – | Lizenz S&P DJI |
| SEDAR+ (Geschäftsberichte) | Pflichtveröffentlichungen | ❌ Weiterleitung auf Bot-Schutz (perfdrive), kein maschineller Zugriff | – | – |
| SEC EDGAR (40-F/20-F kanadischer Emittenten) | XBRL-Finanzdaten | aus dieser Umgebung 403, in GitHub Actions bereits genutzt (sec_fundamentals) | – | gemeinfrei |
| Deutsche Börse Tagesdateien (vorhanden) | Kurse in EUR | ✅ | 2.233 CA-ISINs gehandelt | bereits genutzt |

## Mexiko

| Quelle | Inhalt | Ergebnis | Heruntergeladen | Nutzung |
|---|---|---|---|---|
| BIVA `emisoras/empresas` | Emittenten mit Heimatbörse (BMV/BIVA), Sektor, Status | ✅ | 347 Emittenten (inkl. reiner Schuldtitel-Emittenten) | nicht geprüft (Bedingungen nur per JavaScript) |
| BIVA `emisoras/empresas/{id}/emisiones` | Serien mit **ISIN**, Wertpapierart, Aktien im Umlauf, Listungsart | ✅ | Beispiel AC: Serie *, MX01AC100006 | nicht geprüft |
| BIVA `emisoras/tipo-instrumento` | Instrumenttypen inkl. **FIBRAS**, CKDes/CERPIs, TRACs | ✅ | 10 Typen | nicht geprüft |
| BIVA `emisoras/sic` | Ausländische Titel im SIC (getrennt von heimischen) | ✅ | 3.855 Titel | nicht geprüft |
| BIVA `.../documentos` + `/storage/data-rs-cnbv/*.xbrl` | Quartalsberichte der CNBV als **XBRL (IFRS)** | ✅ | AC Q3/2026 (6,9 MB); Bestand ab 2021 | nicht geprüft |
| BMV Emittentenseite | HTML mit JS-Abfragen | ✅ (HTML) | – | nicht geprüft |
| CNBV | – | ❌ TLS-Zertifikat nicht prüfbar | – | – |
| S&P/BMV-Indexmitglieder | IPC, CompMx, Total Mexico, Large/Mid/SmallCap, Dividend | ❌ lizenzpflichtig (S&P DJI) | – | Lizenz |

## Folgerungen

1. **Brasilien** ist amtlich und frei nutzbar (CVM, ODbL) vollständig abbildbar: Universum, Gattungen, Abschlüsse 2010–2025.
   ISIN, Kurse, Indexportfolio und Dividenden/JCP je Aktie kommen nur von der B3, deren Bedingungen kommerzielle Nutzung ohne Erlaubnis untersagen.
2. **Kanada**: Universum (Symbole) nur von TMX mit derselben Einschränkung; Indexmitglieder und SEDAR+ nicht zugänglich.
   Finanzen für Firmen mit SEC-Meldung (40-F); ISIN/Kurs über Deutsche Börse und GLEIF.
3. **Mexiko**: BIVA liefert Universum, Serien mit ISIN, FIBRAs, SIC und XBRL-Berichte ab 2021; Nutzungsbedingungen noch zu prüfen. Indexmitglieder lizenzpflichtig.
4. Indexmitgliedschaften: nur B3 (aktueller Tag) frei abrufbar; S&P/TSX und S&P/BMV nicht ohne Lizenz.
