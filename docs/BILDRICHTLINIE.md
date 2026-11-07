# Bildrichtlinie dividenden-rechner.de

Ziel: Auf der Seite, im Newsletter und in Stories liegt nur Bildmaterial, dessen Nutzung geklaert ist. Das gilt auch dann, wenn die Seite Werbung oder Affiliate-Links enthaelt.

## Erlaubte Quellen fuer Aufmacher
1. **Unsplash** (Unsplash-Lizenz, auch kommerziell frei). Fotograf und Link zur Fotoseite angeben.
2. **Wikimedia Commons** mit CC0, CC BY oder CC BY-SA. Urheber, Lizenz und Link zur Dateiseite angeben. Bei CC BY-SA gilt die Lizenz auch fuer Bearbeitungen.
3. **Pexels und Pixabay** (eigene freie Lizenzen), Quelle angeben.
4. **Eigene Grafiken und eigene Fotos** (Charts, Pfeil-Montagen). Sie bekommen `image_lizenz: eigen`.

## Nicht erlaubt ohne ausdrueckliche Markierung
- Fotos von Pressebereichen der Firmen (zum Beispiel UBS). Solange die Nutzungsbedingungen nicht geprueft sind, nur mit `image_lizenz: Pressebild` im Kopf des Artikels und nur nach Freigabe durch Divi.
- Fotos aus Suchmaschinen, Social Media oder Zeitungen.
- KI-Bilder von realen Personen oder Marken.

## Zitate aus Unternehmensunterlagen
Folien, Diagramme und Tabellen aus Quartalsberichten duerfen als Zitat zur Erlaeuterung gezeigt werden, mit Quellenangabe und nur in dem Umfang, den der Artikel zur Erklaerung braucht. Sie dienen nie als Aufmacher oder Dekoration.

## Technik
- Im Kopf jedes Artikels mit Bild stehen `image_credit` und `image_source` (Link zur Foto- oder Dateiseite).
- `tools/build_magazin.py` gibt beim Bauen die Zeile `BILDRECHTE pruefen: <slug>` aus, wenn Quelle oder Lizenz fehlen oder die Quelle nicht auf der Freiliste steht.
- Neue Fotoanfragen in `tools/asset.request` suchen nur auf Unsplash und Wikimedia Commons.
- Im Newsletter steht am Ende die Fotozeile mit allen Urhebern.
