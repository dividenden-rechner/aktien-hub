"""Liest die veroeffentlichte CSV der eigenen Asien-Liste (Japan und Korea) und schreibt
Kurse, Waehrung, Heimatboersen-Kurs und Kennzahlen nach data/asien-kurse-sheet.json.

Die Zahlen bleiben in der Waehrung der Zeile (Spalte "Waehrung"). Umrechnung passiert nicht
hier. Der Heimatboersen-Kurs (JPY/KRW) ist fuer Japan oft leer, dann bleibt er None.
"""
import csv
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

URL = os.environ.get("ASIEN_SHEET_CSV", "")
OUT = "data/asien-kurse-sheet.json"


def zahl(s):
    s = (s or "").strip()
    if not s or s.startswith("#") or s in ("–", "-"):
        return None
    s = s.replace("%", "").replace("+", "")
    # Deutsches Format: Tausenderpunkt und Komma als Dezimalzeichen, z. B. "1.411.000,00"
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
        print("ASIEN_SHEET_CSV fehlt", file=sys.stderr)
        sys.exit(1)
    with urllib.request.urlopen(URL, timeout=60) as r:
        text = r.read().decode("utf-8", "replace")
    rows = list(csv.reader(io.StringIO(text)))
    # Die Tabelle beginnt nicht mehr zwingend in Zeile 1: oben steht ein Kursblock (USD/JPY).
    start = next((i for i, r in enumerate(rows) if any(c.strip() == "Unternehmen" for c in r)), None)
    if start is None:
        print("Kopfzeile mit 'Unternehmen' nicht gefunden", file=sys.stderr)
        sys.exit(1)
    jpy_kurs = None
    for r in rows[:start]:
        for i, c in enumerate(r):
            if "JPY pro USD" in c:
                # Wert steht links neben der Beschriftung oder eine Zelle davor
                for j in (i - 1, i - 2):
                    if j >= 0 and zahl(r[j]):
                        jpy_kurs = zahl(r[j])
                        break
    rows = rows[start:]
    kopf = [c.strip() for c in rows[0]]
    idx = {k: i for i, k in enumerate(kopf)}
    need = ["Unternehmen", "Land", "Original-Ticker", "Währung", "Kurs", "Marketcap (Mrd.)", "KGV"]
    fehlt = [n for n in need if n not in idx]
    if fehlt:
        print("Spalten fehlen:", fehlt, kopf, file=sys.stderr)
        sys.exit(1)
    heimat_idx = next((i for i, k in enumerate(kopf) if k.startswith("Kurs Heimatbörse")), None)

    def feld(r, name):
        i = idx[name]
        return r[i] if i < len(r) else ""

    firmen = {}
    for r in rows[1:]:
        t = ticker(feld(r, "Original-Ticker"))
        if not t:
            continue
        kurs = zahl(feld(r, "Kurs"))
        if kurs is None:
            continue
        heimat = None
        if heimat_idx is not None and heimat_idx < len(r):
            heimat = zahl(r[heimat_idx])
        firmen[t] = {
            "name": feld(r, "Unternehmen").strip(),
            "land": feld(r, "Land").strip(),
            "waehrung": feld(r, "Währung").strip() or None,
            "kurs": kurs,
            "kurs_heimat": heimat,
            "marktkap_mrd": zahl(feld(r, "Marketcap (Mrd.)")),
            "kgv": zahl(feld(r, "KGV")),
        }
    jetzt = datetime.now(timezone(timedelta(hours=1)))
    daten = {
        "stand": jetzt.strftime("%d.%m.%Y %H:%M") + " (Berlin)",
        "quelle": "Eigene Asien-Liste (Google Sheets, Japan und Korea)",
        "anzahl": len(firmen),
        "jpy_je_usd": jpy_kurs,
        "firmen": firmen,
    }
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    print(f"{len(firmen)} Firmen geschrieben nach {OUT}")


if __name__ == "__main__":
    main()
