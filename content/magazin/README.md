# Magazin: So schreibst du einen Artikel

1. Lege hier in `content/magazin/` eine neue Datei an, zum Beispiel `dividendenfalle-erkennen.md`
   (GitHub: Add file → Create new file). Der Dateiname wird zur Adresse: `/magazin/dividendenfalle-erkennen/`.
2. Beginne mit dem Kopfbereich zwischen zwei `---` Zeilen:

```
---
title: Überschrift, möglichst unter 70 Zeichen
description: Ein bis zwei Sätze, die Lust aufs Lesen machen (max. ca. 160 Zeichen).
date: 2026-10-27 08:00
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

Ergebnis: ein Entwurf (`draft: true`) in `content/magazin/`. Hinweise für dich stehen als `<!-- PRÜFEN: ... -->` am Textanfang
(werden nie veröffentlicht): Foto passend? Zahlen im Bericht gefunden? Prompt: `tools/ir_prompt.md`, Autor/Bio: `tools/ir_config.json`.
Gibt es den Artikel schon, bricht der Agent ab, damit nichts überschrieben wird.
Zum Veröffentlichen: lesen, Zahlen prüfen, `draft: true` löschen.
Voraussetzungen: Secret `GEMINI_API_KEY`; optional Variable `SEC_USER_AGENT` (Name und E-Mail, so verlangt es die SEC).
