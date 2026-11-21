# Altersvorsorgedepot-Vergleich: Daten, Seite, Rechner

Seite: `altersvorsorgedepot/index.html` (live: https://www.dividenden-rechner.de/altersvorsorgedepot/)

## Dateien

| Datei | Aufgabe |
| --- | --- |
| `data/av-anbieter.json` | Alle Anbieter, Depotmodelle, Kostenbestandteile und Quellen (Schema 2) |
| `tools/build_av.py` | Baut den Vergleich zwischen `<!--av-start-->` und `<!--av-end-->` (über dem Rechner) und das JSON `#av-data` für den Rechner |
| `assets/rechner.js` | Rechner; Kostenmodell `avKostenAm`, `avKostenFn`, `avKennzahlen`, Fördermathematik `avdCalc`, `zulage` |
| `tools/av_check.py` | Prüf-Bot (montags und donnerstags, `.github/workflows/av-check.yml`): sucht Abweichungen, ändert die Daten aber **nicht** |
| `data/av-pruefung.json` | Protokoll des Prüf-Bots (`abweichungen`, `bestaetigt`, `verworfen`) |
| `tests/av.test.js` | Node-Tests (Kostenmodell, Zulagen, Steuer, Daten, Quellen, Python/JS-Gleichheit) |
| `tests/test_av_seite.py` | Seitenbau, Prüf-Bot, Browser-Tests (Handy 390 px und Desktop) |

Tests: `node --test tests/av.test.js` und `python3 -m unittest tests/test_av_seite.py`

## Datenmodell (Schema 2)

Anbieter → Depotmodell (`produkte`) → Kostenbestandteil (`bestandteile`) → Zeitraum/Bedingung → Quelle (`quellen`).

Depotmodell:

- `art`: `standard`, `gesteuert`, `frei`, `beratung`, `garantie`
- `pruefstatus`: `primary_verified` (Anbieterseite, Preisblatt, Pressemitteilung des Anbieters), `secondary_lead` (nur Presse/Vergleichsportal), `pending`
- `konditionen`: `veroeffentlicht`, `teilweise`, `offen`
- `im_rechner`: nur zusammen mit `primary_verified` erscheint das Modell im Rechner

Kostenbestandteil:

- `art`: `fund_ter`, `ter_erstattung`, `service_fee`, `management_fee`, `total_cost`, `custody_fee`, `order_fee`, `saving_plan_fee`
- `pct` (Prozent p. a.) oder `null`, wenn der Anbieter keinen Wert nennt. **Nie schätzen.**
- `eur_jahr` (feste Gebühr im Jahr), `eur_order` (je Order, fließt nicht in den Sparplan-Rechner ein)
- Zeitraum: `ab_kalender`/`bis_kalender` (Datum), `ab_vertragsjahr`/`bis_vertragsjahr`, `eroeffnung_ab`/`eroeffnung_bis` (Monat der Eröffnung)
- `ter_erstattung` mit `voll: true` erstattet alle aktiven `fund_ter`; `max_volumen` begrenzt die Erstattung auf einen Depotwert; `freiwillig: true` = ohne Enddatum, widerruflich (im Rechner abschaltbar)
- `obergrenze: true` („max.“), `ca: true` („ca.“), `bedingung` (Text), `quelle` (Pflicht)

Rechenregel: Kosten im Monat = aktive Fondskosten × (1 − erstatteter Anteil) + übrige Prozentkosten, feste Euro-Gebühren werden monatlich abgezogen. Ist ein aktiver Bestandteil `null` (bei Fondskosten: nicht vollständig erstattet), ist das Ergebnis „noch offen“ und der Rechner zeigt keine Zahl.

## Ablauf bei neuen Konditionen

1. Primärquelle des Anbieters suchen (Produktseite, Preis- und Leistungsverzeichnis, Pressemitteilung des Anbieters).
2. Quelle in `quellen` eintragen (`typ`, `datum`, `abgerufen`).
3. Bestandteile mit Zeitraum und Bedingung eintragen, `pruefstatus` setzen, Eintrag in `aenderungen`.
4. `python3 tools/build_av.py`, `python3 tools/build_seo.py`, Tests laufen lassen.
5. Abweichungen aus `data/av-pruefung.json` genauso von Hand prüfen.

Zertifizierung: Nur aus der Liste des Bundeszentralamts für Steuern übernehmen, nicht von Drittseiten.
