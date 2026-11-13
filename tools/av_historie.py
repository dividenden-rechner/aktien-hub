#!/usr/bin/env python3
"""Kurshistorie je Firma aus Alpha Vantage (TIME_SERIES_DAILY, outputsize=full).
Holt pro Lauf höchstens AV_MAX Firmen aus data/kurse/historie/queue.json, die noch keine Datei haben,
und legt sie als data/kurse/historie/<HUB-SYMBOL>.json ab. Keine Aktuell-Abrufe: nur Historie.
Gratis-Schlüssel: rund 25 Aufrufe am Tag, geteilt mit dem Earnings-Lauf. Standard daher AV_MAX=1."""
import os, sys, json, time, datetime, urllib.request, urllib.parse

KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
MAX = int(os.environ.get("AV_MAX", "1"))
ZIEL = os.path.join(os.path.dirname(__file__), "..", "data", "kurse", "historie")
Q = os.path.join(ZIEL, "queue.json")

def hole(symbol):
    p = {"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "full", "datatype": "json", "apikey": KEY}
    url = "https://www.alphavantage.co/query?" + urllib.parse.urlencode(p)
    txt = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dividenden-rechner"}), timeout=120).read().decode("utf-8", "replace")
    return json.loads(txt)

def main():
    if not KEY:
        print("ALPHAVANTAGE_API_KEY fehlt"); sys.exit(0)
    q = json.load(open(Q))
    offen = [f for f in q["firmen"] if not os.path.exists(os.path.join(ZIEL, f["hub"] + ".json"))]
    print("Offen:", len(offen), "von", len(q["firmen"]))
    for f in offen[:MAX]:
        time.sleep(13)   # höchstens 5 Aufrufe pro Minute
        d = hole(f["av"])
        reihe = d.get("Time Series (Daily)")
        if not reihe:
            print("KEIN ERGEBNIS", f["hub"], f["av"], str(d)[:200]); continue
        kurse = []
        for datum in sorted(reihe):
            z = reihe[datum]
            kurse.append([datum, float(z["1. open"]), float(z["2. high"]), float(z["3. low"]), float(z["4. close"]), int(float(z["5. volume"]))])
        out = {"hub": f["hub"], "av": f["av"], "name": f["name"], "waehrung_hinweis": "Börsenwährung der Handelslinie, nicht umgerechnet",
               "quelle": "Alpha Vantage TIME_SERIES_DAILY (ungeteilt, Schlusskurse)", "stand": datetime.date.today().isoformat(),
               "felder": ["datum", "eröffnung", "hoch", "tief", "schluss", "volumen"], "kurse": kurse}
        json.dump(out, open(os.path.join(ZIEL, f["hub"] + ".json"), "w"), ensure_ascii=False)
        print("OK", f["hub"], len(kurse), "Tage von", kurse[0][0], "bis", kurse[-1][0])

if __name__ == "__main__":
    main()
