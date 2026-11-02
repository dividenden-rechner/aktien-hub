# Roadmap: Login, Bezahlung, freie und bezahlte Bereiche

Stand: 1. November 2026. Planungsdokument, keine Rechtsberatung. Rechtliche Punkte bitte vor dem Start mit Steuerberater/Anwalt abklaren.

## Zielbild
- Frei: Startseite, Magazin, Wissen, Rechner, News, Earnings und nur wenige ausgewaehlte Aktienseiten komplett.
- Bezahlt: Depot, Screener und alle weiteren Aktienseiten (Steckbrief, Charts, Finanzdaten, Vergleich).
- Nutzerdaten (Watchlist, Depot) bleiben beim Nutzer: Browser oder eigenes Google-Drive (appDataFolder). Wir speichern nur E-Mail-Adresse und Abo-Status.
- Echter Schutz nur ueber den Worker: Die Kursdaten werden erst nach Pruefung des Abo-Status ausgeliefert. Reine Browser-Sperren sind umgehbar.

## Phase 0: Voraussetzungen klaeren (vor jeder Entwicklung)
1. **FMP-Lizenz:** Antwort zur Display-/Redistribution-Lizenz abwarten. Fuer ein bezahltes Angebot vermutlich kommerzieller Tarif noetig. Gleichzeitig fragen: Intraday-Daten (1D/5D-Chart) im Tarif enthalten?
2. **Adresse/Domain:** Startseite unter www.dividenden-rechner.de (eigene Domain auf dieses Projekt) oder neues Repo dividenden-rechner.github.io. Login und Zahlung brauchen eine feste Adresse. Google-Sites-Inhalte vorher umziehen.
3. **Gewerbe/Steuern:** siehe Abschnitt Rechtliches. Nebentaetigkeit beim Arbeitgeber pruefen.
4. **Preis- und Freemium-Modell festlegen:** Welche Aktien frei, Monats-/Jahresabo, Testzeitraum.

## Phase 1: Datenhoheit beim Nutzer (kostenlos, kein Server noetig)
1. Export/Import von Watchlist und Depot als Datei (JSON).
2. Optional: Anmeldung mit Google, Daten im Drive-App-Ordner (OAuth-Client-ID in Google Cloud anlegen, Pruefung durch Google).
3. Datenschutzerklaerung anpassen (Daten bleiben im Browser/Google-Konto).

## Phase 2: Zugang (Worker)
1. Cloudflare Worker erweitern: E-Mail-Anmeldung per Link (Magic Link), signierte Sitzung.
2. Mailversand ueber einen EU-Dienst, Double-Opt-in.
3. Speicher (Cloudflare D1/KV): nur E-Mail, Abo-Status, Zeitstempel. Konto-Loeschfunktion.
4. FMP-Proxy: Abfragen nur mit gueltiger Sitzung und aktivem Abo, ausgenommen die freien Aktien (Whitelist).
5. Missbrauchsschutz: Rate Limits pro Nutzer und IP.

## Phase 3: Bezahlung
1. Stripe-Konto, Produkte und Preise, Stripe Tax fuer Umsatzsteuer, Stripe Customer Portal (Kuendigung, Rechnungen).
2. Webhook an den Worker: Abo aktiv/beendet.
3. Bestell-Button mit Hinweis "zahlungspflichtig bestellen", Zustimmung zum vorzeitigen Leistungsbeginn, Kuendigungsbutton.
4. Testlauf im Stripe-Testmodus, dann Live.

## Phase 4: Sperre aktivieren
1. Freie Aktien festlegen (z. B. 5 bis 10 bekannte Werte), Rest hinter der Schranke.
2. Seiten fuer Nicht-Abonnenten: Teaser mit Steckbrief-Ampel, Details gesperrt.
3. Sitemap/SEO: bezahlte Seiten bleiben indexierbar mit Kurzinfo, Daten werden nachgeladen.
4. Beobachten: Anmeldungen, Abbrueche, Support-Anfragen.

## Rechtliches (Checkliste)
- Gewerbeanmeldung beim Gewerbeamt, Fragebogen zur steuerlichen Erfassung beim Finanzamt.
- Nebentaetigkeit: Arbeitsvertrag pruefen, ggf. Arbeitgeber informieren oder genehmigen lassen.
- Impressum, Datenschutzerklaerung (Zahlungsdienst, Mailversand, Worker), AGB, Widerrufsbelehrung.
- Digitale Inhalte: Widerrufsrecht erlischt nur mit ausdruecklicher Zustimmung und Bestaetigung.
- Button-Loesung: Bestellbutton "zahlungspflichtig bestellen".
- Kuendigungsbutton fuer Verbraucher-Abos (Paragraf 312k BGB).
- Kein Anlageberatung-Eindruck: Hinweis "keine Anlageberatung", keine persoenlichen Kauf-/Verkaufsempfehlungen. Bei Zweifeln BaFin-Fragen mit Anwalt klaeren.
- Datenschutz: Auftragsverarbeitung mit Stripe, Cloudflare und Mailanbieter, Loeschkonzept.
- Steuerberater einplanen.

### Kleinunternehmer
- Kleinunternehmerregelung (Paragraf 19 UStG) ist freiwillig, keine Pflicht. Du musst nicht Kleinunternehmer sein.
- Nach meinem Kenntnisstand: Vorjahresumsatz bis 25.000 Euro und laufendes Jahr bis 100.000 Euro. Dann keine Umsatzsteuer auf Rechnungen, kein Vorsteuerabzug. Aktuelle Grenzen beim Steuerberater bestaetigen.
- Gegen Kleinunternehmer: Vorsteuer aus Kosten (FMP, Hosting) ist nicht abziehbar, bei Kunden im EU-Ausland gelten ab bestimmten Schwellen eigene Regeln.
- Regelbesteuerung: 19 % Umsatzsteuer, Vorsteuerabzug, monatliche/quartalsweise Voranmeldung. Stripe Tax hilft bei der Berechnung.
- Umsatz aus Werbung und Affiliate zaehlt mit.
- Gewerbesteuer: Freibetrag 24.500 Euro Gewinn. Einkommensteuer auf den Gewinn bleibt.

## Offene Punkte
- FMP-Lizenzantwort
- Domain-Entscheidung
- Preise und freie Aktien
- Steuerberater-Termin
