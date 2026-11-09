# Konto-Server (Anmeldung per E-Mail-Link, Watchlist speichern)

Cloudflare Worker + D1-Datenbank. Keine Passwoerter. Gespeichert werden E-Mail-Adresse, Zeitpunkt der Einwilligung und die Kuerzel der Watchlist.

## Veroeffentlichen (einmalig, spaeter wiederholbar)
1. Cloudflare: API-Token braucht zusaetzlich das Recht **D1: Edit** (Konto-Ebene). Die GitHub-Secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` und `BREVO_API_KEY` sind schon fuer Newsletter und FMP-Proxy da.
2. GitHub > Actions > **Konto-Server bereitstellen** > Run workflow. Der Workflow legt die Datenbank `dividenden-konto` an, spielt `schema.sql` ein, laedt den Worker hoch und legt den Brevo-Schluessel ab.
3. Die Adresse des Workers steht danach in der Ausgabe (meist `https://konto.dividenden-rechner.workers.dev`). Stimmt sie nicht, in `assets/konto.js` bei `KONTO_URL` eintragen.
4. Seite freigeben: in `data/live.json` den Eintrag `"konto"` aus `versteckt` nehmen. Bis dahin ist `/konto/` nur in der Testkopie erreichbar.

## Lokal testen (ohne Cloudflare)
`node --no-warnings worker-konto/test.mjs` (Node 22). Prueft Anmeldung, Einmal-Link, Bremse, Watchlist, Export, Abmelden, Loeschen.

## Ablauf
`POST /login` (E-Mail + Einwilligung) -> Mail mit Einmal-Link (15 Min.) auf `/konto/?t=...` -> `POST /verify` -> Sitzungsschluessel (90 Tage, im Browser, auf dem Server nur als Hash) -> `GET/PUT /watchlist`, `GET /export`, `POST /logout`, `DELETE /konto`.
Bremse: hoechstens 5 Mails je Adresse und 20 Anfragen je Besucher pro Stunde. Watchlist: hoechstens 300 Eintraege. Die Liste speichert Kuerzel (`s`), Name (`n`) und optional die ISIN (`i`), damit spaeter FMP-Daten ohne Umbau andocken.

## Noch zu tun vor dem Start
- Datenschutzerklaerung ergaenzen (Textbausteine unten).
- In den Seiten mit Watchlist (Aktien-Hub, News) `assets/konto.js` einbinden und nach jeder Aenderung `Konto.speichern(liste)` aufrufen, beim Laden `Konto.abgleichen()`.
- Link zum Konto in die Navigation, wenn freigegeben.

## Textbausteine Datenschutzerklaerung (vor Veroeffentlichung rechtlich pruefen)
**Kundenkonto und Watchlist.** Wenn du ein Konto anlegst, speichern wir deine E-Mail-Adresse, den Zeitpunkt deiner Einwilligung und die Liste der Aktien in deiner Watchlist. Rechtsgrundlage ist deine Einwilligung (Art. 6 Abs. 1 lit. a DSGVO) bzw. die Bereitstellung des Kontos (Art. 6 Abs. 1 lit. b DSGVO). Die Anmeldung erfolgt ohne Passwort ueber einen Link, den wir per E-Mail senden. Fuer den Versand nutzen wir Brevo (Sendinblue GmbH / Brevo, Frankreich), fuer Speicherung und Betrieb Cloudflare, Inc. (USA, Standardvertragsklauseln). Du kannst dein Konto jederzeit auf der Seite "Mein Konto" loeschen und deine Daten herunterladen. Dann werden E-Mail-Adresse, Anmeldungen und Watchlist geloescht. Technisch notwendige Anmeldedaten (Sitzungsschluessel) speichern wir im lokalen Speicher deines Browsers.
