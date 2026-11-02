# Live-Gang: Seite ohne Earnings, Screener, Depot und Aktien-Hub veröffentlichen

Einstellungen stehen in `data/live.json`, der Bau in `tools/live_filter.py`, der Ablauf in `.github/workflows/live.yml`.

## Was die öffentliche Seite enthält
Alle Rechner, News, Unternehmensmeldungen, Einführung, Grundlagen, Fortgeschrittene, Über uns, Impressum, Datenschutz.
Entfernt werden die Ordner aus `versteckt` (Aktien-Hub, Aktien, Depot, Earnings, Screener, Vorschau), alle Menüpunkte, Kacheln und Verweise darauf, ihre Einträge in Sitemap und llms.txt.
Mit `fmp_aus: true` werden außerdem die Skripte entfernt, die in Artikeln Kurse und Earnings-Ergebnisse aus dem FMP-Zwischenserver laden.

## Testkopie
Unter `/<testkopie>/` (Standard `intern-t7q4m9`) liegt die vollständige Seite mit allen Bereichen zum Testen. Nicht verlinkt, `noindex`, in robots.txt gesperrt. Wer die Adresse kennt, kann sie aufrufen. Zum Abschalten `testkopie` leer lassen.

## Schritte zum Einschalten
1. GitHub: Repository > Settings > Pages > Build and deployment > Source auf **GitHub Actions** stellen.
2. In `data/live.json` `"aktiv": true` setzen und pushen (oder Workflow "Seite veröffentlichen" von Hand starten).
3. Eigene Adresse: Settings > Pages > Custom domain (`www.dividenden-rechner.de`), bei Strato die DNS-Einträge setzen (A-Einträge 185.199.108.153, .109.153, .110.153, .111.153 für die Domain ohne www, CNAME `www` auf `dividenden-rechner.github.io`), dann `domain_neu` in `data/live.json` auf `https://www.dividenden-rechner.de/` setzen. Das ersetzt die Adresse in Canonical, Sitemap, Teilen-Links.
4. Alte Google-Sites-Adressen: vor der Umstellung die bisherigen Seiten-Adressen sammeln und Weiterleitungen anlegen, damit das Google-Ranking bleibt.

## Später freigeben
Bereich aus `versteckt` streichen (z. B. `screener`), pushen. Menüpunkte kommen von selbst zurück, weil die Quellseiten unverändert im Repository liegen.
