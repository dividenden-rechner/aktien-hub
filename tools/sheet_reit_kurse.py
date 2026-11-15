"""Liest die veroeffentlichte CSV der eigenen REIT-Liste (Google Sheets) und schreibt
Kurs und Marktkapitalisierung nach data/reit-kurse-sheet.json.

Erwartet werden die Spalten "Ticker" und eine Kurs-Spalte (Name beginnt mit "Kurs").
Fehlt eine davon, bricht das Skript mit Fehlermeldung ab, statt falsche Daten zu schreiben.
"""
import csv
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

URL = os.environ.get("REIT_SHEET_CSV", "")
OUT = "data/reit-kurse-sheet.json"


def zahl(s):
    s = (s or "").strip()
    if not s or s.startswith("#") or s in ("–", "-"):
        return None
    s = s.replace("%", "").replace("+", "").replace(" Mrd.", "").replace(" $", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def ticker(s):
    s = (s or "").strip()
    return re.sub(r"^[A-Z]+:", "", s)


def main():
    if not URL:
        print("REIT_SHEET_CSV fehlt", file=sys.stderr)
        sys.exit(1)
    with urllib.request.urlopen(URL, timeout=60) as r:
        text = r.read().decode("utf-8", "replace")
    rows = list(csv.reader(io.StringIO(text)))
    kopf = [c.strip() for c in rows[0]]
    if "Ticker" not in kopf:
        print("Spalte Ticker fehlt:", kopf, file=sys.stderr)
        sys.exit(1)
    kurs_i = next((i for i, k in enumerate(kopf) if k.startswith("Kurs")), None)
    if kurs_i is None:
        print("Keine Kurs-Spalte:", kopf, file=sys.stderr)
        sys.exit(1)
    t_i = kopf.index("Ticker")
    mc_i = kopf.index("Marketcap") if "Marketcap" in kopf else None
    kurse = {}
    for r in rows[1:]:
        if len(r) <= max(t_i, kurs_i):
            continue
        t = ticker(r[t_i])
        kurs = zahl(r[kurs_i])
        if not t or kurs is None:
            continue
        mc = zahl(r[mc_i]) if mc_i is not None and mc_i < len(r) else None
        kurse[t] = {"kurs": kurs, "marktkap_mrd": mc}
    jetzt = datetime.now(timezone(timedelta(hours=1)))
    daten = {
        "stand": jetzt.strftime("%d.%m.%Y %H:%M") + " (Berlin)",
        "quelle": "Eigene REIT-Liste (Google Sheets)",
        "anzahl": len(kurse),
        "kurse": kurse,
    }
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    print(f"{len(kurse)} Kurse geschrieben nach {OUT}")


if __name__ == "__main__":
    main()
