# Magazin: So schreibst du einen Artikel

<!-- uebersicht-start -->
## Übersicht (wird automatisch erstellt, neueste zuerst)

### Zur Freigabe: Entwürfe (0)

Datei anklicken, dann Stift-Symbol: Zeile `draft: true` löschen und speichern, dann geht der Artikel online.

_Keine Entwürfe._

### Online (14)

| Datum | Titel | Datei |
|---|---|---|
| 29.10.2026 09:15 | Alphabets Rekordumsatz trifft auf Milliardeninvestitionen in KI | [2026-10-29-0915-alphabet-q3-2026-quartalszahlen.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/2026-10-29-0915-alphabet-q3-2026-quartalszahlen.md) |
| 29.10.2026 08:22 | Komatsu hebt Jahresprognose nach Umsatzplus im Halbjahr an | [2026-10-29-0822-komatsu-halbjahreszahlen-2026.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/2026-10-29-0822-komatsu-halbjahreszahlen-2026.md) |
| 28.10.2026 19:15 | Fed belässt Leitzins im Oktober 2026 bei 3,75 bis 4 Prozent | [2026-10-28-1914-fed-zinsentscheid-oktober-2026.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/2026-10-28-1914-fed-zinsentscheid-oktober-2026.md) |
| 28.10.2026 15:47 | Unilever steigert Umsatz auf 13,3 Milliarden Euro und hebt Ausblick an | [unilever-q3-2026-trading-statement.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/unilever-q3-2026-trading-statement.md) |
| 28.10.2026 15:33 | GE Vernova steigert Quartalsumsatz auf 12,6 Milliarden US-Dollar | [ge-vernova-q3-2026-ergebnisse.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/ge-vernova-q3-2026-ergebnisse.md) |
| 28.10.2026 15:18 | Ping An steigert operatives Ergebnis auf 125,9 Milliarden RMB | [ping-an-q3-2026.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/ping-an-q3-2026.md) |
| 27.10.2026 20:20 | UPS setzt 22,9 Milliarden um, Sondereffekte drücken das Ergebnis | [2026-10-27-2020-ups-q3-2026-ergebnisse.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/2026-10-27-2020-ups-q3-2026-ergebnisse.md) |
| 27.10.2026 13:23 | Boeing setzt 24,2 Milliarden um und bleibt operativ im Minus | [2026-10-27-1323-boeing-q3-ergebnis-2026.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/2026-10-27-1323-boeing-q3-ergebnis-2026.md) |
| 27.10.2026 12:58 | Coca-Cola verdient mehr: Umsatz und Konzernergebnis steigen | [2026-10-27-1258-coca-cola-q3-2026-ergebnisse.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/2026-10-27-1258-coca-cola-q3-2026-ergebnisse.md) |
| 27.10.2026 11:50 | Mercedes-Benz senkt Ausblick für 2026 wegen China und Kosten | [2026-10-27-1150-mercedes-benz-prognoseanpassung-2026.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/2026-10-27-1150-mercedes-benz-prognoseanpassung-2026.md) |
| 27.10.2026 10:13 | HSBC verdient 9,6 Milliarden vor Steuern und kauft Aktien zurück | [2026-10-27-1013-hsbc-q3-2026.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/2026-10-27-1013-hsbc-q3-2026.md) |
| 27.10.2026 09:40 | Novartis erhöht die Gewinnprognose, neue Medikamente laufen gut | [2026-10-27-0940-novartis-q3-2026-ergebnisse.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/2026-10-27-0940-novartis-q3-2026-ergebnisse.md) |
| 26.10.2026 22:28 | Verizon steigert bereinigtes EPS und hebt Jahresziele für 2026 an | [2026-10-26-2228-verizon-q3-2026.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/2026-10-26-2228-verizon-q3-2026.md) |
| 26.10.2026 21:48 | Coca-Cola hebt die Ziele für Cashflow und Gewinn je Aktie an | [2026-10-26-2148-coca-cola-q2-2026.md](https://github.com/dividenden-rechner/aktien-hub/edit/main/content/magazin/2026-10-26-2148-coca-cola-q2-2026.md) |
<!-- uebersicht-ende -->

1. Lege hier in `content/magazin/` eine neue Datei an. Der Dateiname beginnt mit Jahr-Monat-Tag und Uhrzeit, zum Beispiel
   `2026-10-28-1452-dividendenfalle-erkennen.md` (GitHub: Add file → Create new file). Dadurch ist die Liste nach Datum geordnet.
   Der Teil nach dem Datum wird zur Adresse: `/magazin/dividendenfalle-erkennen/`. Die Artikel des IR-Agenten heißen automatisch so.
2. Beginne mit dem Kopfbereich zwischen zwei `---` Zeilen:

```
---
title: Überschrift, möglichst unter 70 Zeichen
description: Ein bis zwei Sätze, die Lust aufs Lesen machen (max. ca. 160 Zeichen).
date: 2026-10-27 08:00        (Veröffentlichung: Datum und Uhrzeit, Berliner Zeit; danach wird sortiert, neueste zuerst)
updated: 2026-11-02 09:30        (optional, nur bei echten Änderungen)
author: Divi
author_bio: Ein Satz zu dir als Autor (optional)
category: Analyse                (z. B. Analyse, Steuer, Grundlagen, Kommentar)
image: assets/magazin/mein-bild.jpg   (optional, mind. 1200 px breit; sonst entsteht automatisch ein Titelbild)
image_alt: Bildbeschreibung      (optional)
draft: true                      (optional: true = noch nicht veröffentlichen)
---
```

3. Darunter der Text in Markdown:
   - `## Zwischenüberschrift`, `### Unterpunkt`
   - `**fett**`, `*kursiv*`, Listen mit `-` oder `1.`
   - Links auf eigene Seiten mit führendem Schrägstrich: `[KGV](/grundlagen/kgv/)`
   - Tabellen mit `| Spalte | Spalte |`
   - Kästen: `!!! example "Rechenbeispiel"` und dann den Text eingerückt (4 Leerzeichen); weitere Typen: `note`, `formula`
   - FAQ: eine Überschrift `## Häufige Fragen`, darunter je Frage `### Frage?` und die Antwort. Daraus entsteht automatisch FAQ-Markup.
4. Speichern (Commit). Nach etwa einer Minute baut ein GitHub-Workflow die Seite, trägt sie in Übersicht,
   Startseite, Menü, RSS-Feed, Sitemap und llms.txt ein.

Dateien, die mit `_` beginnen, und Artikel mit `draft: true` oder einem Datum in der Zukunft werden nicht veröffentlicht.
Lokal testen: `pip install markdown pillow` und `python3 tools/build_magazin.py`.

## IR-Agent: Entwurf aus einem Quartalsbericht

**US-Titel (empfohlen):** Actions > "IR-Agent" > Run workflow > Feld `ticker` (z. B. `KO` oder `KO,PEP,O`). Der Agent holt die neueste
Ergebnis-Pressemitteilung selbst von der SEC (8-K, Item 2.02), Gemini liest sie, Code zeichnet die Grafik, und aus Wikimedia Commons
wird ein frei lizenziertes Aufmacherfoto gesucht (mit Bildnachweis unter dem Foto). Die Grafik steht im Text unter dem Einstieg. Der Agent darf außerdem bis zu drei Ausschnitte (Tabellen/Grafiken) aus dem Bericht an passender Stelle in den Text setzen, etwa bei auffälligem Capex oder negativem Free Cashflow; unpassende Bildzeilen löschst du einfach.
**Anderes Dokument bei einem US-Kürzel:** Feld `art` wählen: `ergebnisse` (Standard, Quartals-/Halbjahres-/Jahreszahlen als Pressemitteilung), `jahresbericht` (10-K), `quartalsbericht` (10-Q), `meldung` (neueste Ereignismeldung der letzten 90 Tage, z. B. Aktiensplit, Fusion, Management) oder `insider` (Insiderkäufe und -verkäufe der letzten 120 Tage). Die Kategorie über dem Titel setzt der Agent nach Dokumentart.
**Andere Titel:** `pdf_url` eintragen oder die PDF in `content/ir-inbox/` hochladen.

**Vergleich mehrerer Unternehmen (Peer Group):** Actions → „IR-Vergleich (Peer Group)" → Kürzel, Links oder (Ordner `content/ir-vergleich/<name>/` mit mehreren PDFs) eintragen. Es entsteht ein Entwurf mit Kurz-Kasten, Vergleichstabelle und Analyse, wer wo vorn liegt.

Ergebnis: ein Entwurf (`draft: true`) in `content/magazin/`. Hinweise für dich stehen als `<!-- PRÜFEN: ... -->` am Textanfang
(werden nie veröffentlicht): Foto passend? Zahlen im Bericht gefunden? Prompt: `tools/ir_prompt.md`, Autor/Bio: `tools/ir_config.json`.
Gibt es den Artikel schon, bricht der Agent ab, damit nichts überschrieben wird.
Zum Veröffentlichen: lesen, Zahlen prüfen, `draft: true` löschen.
Voraussetzungen: Secret `GEMINI_API_KEY`; optional Variable `SEC_USER_AGENT` (Name und E-Mail, so verlangt es die SEC).
