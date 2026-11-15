"""Holt den letzten Kurs je Firma (Japan und Korea) ueber den Yahoo-Chart-Endpunkt und
schreibt ihn in Landeswaehrung nach data/asien-kurse-yahoo.json.

Inoffizieller Endpunkt, kann ohne Ankuendigung ausfallen. Fehlt ein Kurs, bleibt er leer.
Die Ticker kommen aus data/asien-fundamente.json, damit beide Listen dieselben Firmen haben.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

FUND = "data/asien-fundamente.json"
OUT = "data/asien-kurse-yahoo.json"
BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def kurs(ticker):
    url = BASE + urllib.parse.quote(ticker) + "?range=5d&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    res = data["chart"]["result"][0]
    meta = res["meta"]
    return {
        "kurs": meta.get("regularMarketPrice"),
        "waehrung": meta.get("currency"),
        "vortag": meta.get("chartPreviousClose") or meta.get("previousClose"),
        "boerse_zeit": datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc).isoformat()
        if meta.get("regularMarketTime") else None,
    }


def main():
    fund = json.load(open(FUND, encoding="utf-8"))
    firmen = {}
    fehler = []
    for f in fund["firmen"]:
        t = f["ticker"]
        try:
            firmen[t] = kurs(t)
        except Exception as e:  # einzelne Firma darf den Lauf nicht stoppen
            fehler.append(f"{t}: {type(e).__name__}")
        time.sleep(0.4)
    jetzt = datetime.now(timezone(timedelta(hours=1)))
    daten = {
        "stand": jetzt.strftime("%d.%m.%Y %H:%M") + " (Berlin)",
        "quelle": "Yahoo-Chart-Endpunkt (inoffiziell), Landeswaehrung",
        "anzahl": sum(1 for v in firmen.values() if v.get("kurs") is not None),
        "fehler": fehler,
        "firmen": firmen,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    print(f"{daten['anzahl']} Kurse, {len(fehler)} Fehler nach {OUT}")
    if daten["anzahl"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
