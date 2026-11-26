#!/usr/bin/env python3
"""EZB-Referenzkurse als Zeitreihe (eurofxref-hist): je Währung und Tag, Einheiten je 1 EUR.

Schreibt data/wechselkurse-historie.json  {"stand", "quelle", "kurse": {WAEHRUNG: {datum: kurs}}}
Nur Währungen aus data/wechselkurse-ezb.json und ab 2019, damit die Datei klein bleibt.
"""
import csv, io, json, os, urllib.request, zipfile
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
AB = "2019-01-01"


def main():
    waehrungen = set(json.load(open(os.path.join(ROOT, "data", "wechselkurse-ezb.json")))["je_eur"].keys())
    roh = urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "dividenden-rechner"}), timeout=180).read()
    z = zipfile.ZipFile(io.BytesIO(roh))
    csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
    zeilen = list(csv.reader(io.StringIO(z.read(csv_name).decode("utf-8"))))
    kopf = [k.strip() for k in zeilen[0]]
    kurse = {}
    for zeile in zeilen[1:]:
        if not zeile or zeile[0] < AB:
            continue
        for k, v in zip(kopf[1:], zeile[1:]):
            if k in waehrungen and v not in ("", "N/A"):
                kurse.setdefault(k, {})[zeile[0]] = float(v)
    ziel = os.path.join(ROOT, "data", "wechselkurse-historie.json")
    json.dump({"stand": date.today().isoformat(), "quelle": "EZB Referenzkurse (eurofxref-hist), Einheiten je 1 EUR",
               "kurse": kurse}, open(ziel, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("EZB-Historie:", {k: len(v) for k, v in sorted(kurse.items())})


if __name__ == "__main__":
    main()
