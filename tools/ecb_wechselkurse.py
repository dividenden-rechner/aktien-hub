"""Holt die taeglichen Referenzkurse der EZB (EUR gegen JPY, USD, KRW; zusaetzlich HKD, SGD, CNY, GBP, CHF, IDR fuer
Asien- und Europa-Werte) und rechnet daraus USD/JPY und KRW/USD. Schreibt data/wechselkurse-ezb.json.
"""
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
OUT = "data/wechselkurse-ezb.json"
NS = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "dividenden-rechner-bot"})
    with urllib.request.urlopen(req, timeout=60) as r:
        root = ET.fromstring(r.read())
    cube = root.find(".//e:Cube[@time]", NS)
    datum = cube.attrib["time"]
    kurse = {c.attrib["currency"]: float(c.attrib["rate"]) for c in cube.findall("e:Cube", NS)}
    for w in ("USD", "JPY", "KRW"):
        if w not in kurse:
            raise SystemExit(f"Waehrung fehlt: {w}")
    usd_jpy = kurse["JPY"] / kurse["USD"]
    krw_usd = kurse["USD"] / kurse["KRW"]
    daten = {
        "stand": jetzt_text(),
        "datum_ezb": datum,
        "quelle": "EZB Referenzkurse (taeglich, ca. 16 Uhr CET)",
        "je_eur": {"USD": kurse["USD"], "JPY": kurse["JPY"], "KRW": kurse["KRW"],
                   **{w: kurse[w] for w in ("HKD", "SGD", "CNY", "GBP", "CHF", "IDR", "SEK", "DKK", "NOK") if w in kurse}},
        "abgeleitet": {"JPY_je_USD": round(usd_jpy, 4), "USD_je_KRW": round(krw_usd, 8)},
    }
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    print(f"EZB {datum}: JPY/USD {usd_jpy:.2f}, geschrieben nach {OUT}")


def jetzt_text():
    return datetime.now(timezone(timedelta(hours=1))).strftime("%d.%m.%Y %H:%M") + " (Berlin)"


if __name__ == "__main__":
    main()
