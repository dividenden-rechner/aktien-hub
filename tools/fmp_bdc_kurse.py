"""Nur der Kurs der BDCs aus dem FMP-Profil (Gratis-Schluessel). Aktienzahl, Dividenden und NAV kommen aus den SEC-Daten.
Nur fuer BDCs, die an keiner deutschen Boerse gehandelt werden. Ausgabe: data/bdc-kurse-fmp.json."""
import datetime as dt, json, os, time, urllib.parse, urllib.request

KEY = os.environ["FMP_API_KEY"]
FIRMEN = json.load(open("data/bdc.json", encoding="utf-8")).get("firmen", {})
KURSE, FEHLER = {}, {}
for sym in FIRMEN:
    url = "https://financialmodelingprep.com/stable/profile?" + urllib.parse.urlencode({"symbol": sym, "apikey": KEY})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dividenden-rechner.de Datensammlung"}), timeout=60) as r:
            j = json.loads(r.read())
        p = j[0] if isinstance(j, list) and j else (j if isinstance(j, dict) else {})
        if p.get("price"):
            KURSE[sym] = {"kurs": p.get("price"), "boerse": p.get("exchange")}
        else:
            FEHLER[sym] = "kein Kurs"
    except Exception as e:
        FEHLER[sym] = str(e)[:80]
    time.sleep(0.3)
json.dump({"stand": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "kurse": KURSE, "fehler": FEHLER},
          open("data/bdc-kurse-fmp.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(KURSE), "Kurse,", len(FEHLER), "Fehler")
