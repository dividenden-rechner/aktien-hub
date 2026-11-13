"""PROBE (kein Datenabruf): Gibt es fuer Australien (ASX) und Hongkong (HKEX) oeffentliche Zugaenge zu Berichten?
Ergebnis: data/au-hk-probe.json (Status, Laenge, Ausschnitt)."""
import datetime as dt, json, urllib.request

UA = "Mozilla/5.0 (compatible; dividenden-rechner.de Datensammlung)"
PRUEFUNG = {
    "ASX Ankuendigungen BHP": "https://www.asx.com.au/asx/1/company/BHP/announcements?count=5&market_sensitive=false",
    "ASX Firmenauskunft BHP": "https://www.asx.com.au/asx/1/company/BHP",
    "ASX Kurs BHP": "https://www.asx.com.au/asx/1/share/BHP",
    "HKEX Titelsuche": "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=en",
    "HKEX Aktienliste": "https://www1.hkexnews.hk/listedco/listconews/advancedsearch/search_active_main.aspx",
}
ergebnis = {}
for name, url in PRUEFUNG.items():
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
            body = r.read(4000).decode("utf-8", errors="replace")
            ergebnis[name] = {"status": r.status, "typ": r.headers.get("Content-Type"), "ausschnitt": body[:600]}
    except Exception as e:
        ergebnis[name] = {"fehler": str(e)}
json.dump({"stand": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "pruefung": ergebnis}, open("data/au-hk-probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(ergebnis, ensure_ascii=False, indent=1)[:3000])
