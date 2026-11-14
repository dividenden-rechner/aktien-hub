"""Liest die veroeffentlichte CSV der eigenen BDC-Liste (Google Sheets, Tabellenblatt
"BDC P/Nav") und schreibt Kurs und Marktkapitalisierung nach data/bdc-kurse-sheet.json.

Quelle ist die vom Betreiber selbst gepflegte Liste. Die Seite weist sie ausdruecklich als
"Kurs laut eigener BDC-Liste" aus. Dividenden und NAV kommen weiterhin aus den SEC-Daten.
"""
import csv
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

URL = os.environ.get("BDC_SHEET_CSV", "")
OUT = "data/bdc-kurse-sheet.json"


def zahl(s):
    s = (s or "").strip()
    if not s or s.startswith("#") or s in ("–", "-"):
        return None
    s = s.replace("%", "").replace(" Mrd. $", "").replace(" $", "").replace("x", "")
    s = s.replace(",", ".")  # Kurse im Sheet: Komma als Dezimalzeichen; Marktkapitalisierung: Punkt
    try:
        return float(s)
    except ValueError:
        return None


def ticker(s):
    s = (s or "").strip()
    return re.sub(r"^[A-Z]+:", "", s)


def main():
    if not URL:
        print("BDC_SHEET_CSV fehlt", file=sys.stderr)
        sys.exit(1)
    with urllib.request.urlopen(URL, timeout=60) as r:
        text = r.read().decode("utf-8", "replace")
    rows = list(csv.reader(io.StringIO(text)))
    kopf = [c.strip() for c in rows[0]]
    idx = {k: i for i, k in enumerate(kopf)}
    need = ["Ticker", "Marketcap", "Kurs in $"]
    if not all(n in idx for n in need):
        print("Spalten fehlen:", kopf, file=sys.stderr)
        sys.exit(1)
    kurse = {}
    for r in rows[1:]:
        if len(r) <= idx["Kurs in $"]:
            continue
        t = ticker(r[idx["Ticker"]])
        if not t:
            continue
        kurs = zahl(r[idx["Kurs in $"]])
        mc = zahl(r[idx["Marketcap"]].replace("Mrd. $", "")) if r[idx["Marketcap"]].strip() not in ("", "–") else None
        if kurs is None:
            continue
        kurse[t] = {"kurs": kurs, "marktkap_mrd": mc}
    jetzt = datetime.now(timezone(timedelta(hours=1)))
    daten = {
        "stand": jetzt.strftime("%d.%m.%Y %H:%M") + " (Berlin)",
        "quelle": "Eigene BDC-Liste (Google Sheets)",
        "anzahl": len(kurse),
        "kurse": kurse,
    }
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    print(f"{len(kurse)} Kurse geschrieben nach {OUT}")


if __name__ == "__main__":
    main()
