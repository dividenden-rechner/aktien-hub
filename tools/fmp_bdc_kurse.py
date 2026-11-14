"""Nur der Kurs der BDCs aus dem FMP-Profil (Gratis-Schluessel). Aktienzahl, Dividenden und NAV kommen aus den SEC-Daten.
Ausgabe: data/bdc-kurse-fmp.json. Schlaegt ein Abruf fehl (Rate-Limit), bleibt der letzte bekannte Kurs erhalten."""
import csv, datetime as dt, json, os, time, urllib.parse, urllib.request, urllib.error

KEY = os.environ["FMP_API_KEY"]
OUT = "data/bdc-kurse-fmp.json"
SYMS = [r["sec_ticker"].upper() for r in csv.DictReader(open("data/bdc-seed.csv", encoding="utf-8"))]
alt = json.load(open(OUT, encoding="utf-8")).get("kurse", {}) if os.path.exists(OUT) else {}
KURSE, FEHLER = dict(alt), {}

def abruf(sym):
    url = "https://financialmodelingprep.com/stable/profile?" + urllib.parse.urlencode({"symbol": sym, "apikey": KEY})
    for versuch in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dividenden-rechner.de Datensammlung"}), timeout=60) as r:
                j = json.loads(r.read())
            return j[0] if isinstance(j, list) and j else (j if isinstance(j, dict) else {})
        except urllib.error.HTTPError as e:
            if e.code == 429 and versuch < 3:
                time.sleep(20 * (versuch + 1)); continue
            raise
    return {}

for sym in SYMS:
    try:
        p = abruf(sym)
        if p.get("price"):
            KURSE[sym] = {"kurs": p.get("price"), "boerse": p.get("exchange")}
        else:
            FEHLER[sym] = "kein Kurs"
    except Exception as e:
        FEHLER[sym] = str(e)[:80]
    time.sleep(1.5)
json.dump({"stand": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "kurse": KURSE, "fehler": FEHLER},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(KURSE), "Kurse,", len(FEHLER), "Fehler")
