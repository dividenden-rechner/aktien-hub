"""Tagesschlusskurse der IDX-Werte (Indonesien) aus der Tagesübersicht der Börse.

Ein Aufruf liefert alle Wertpapiere eines Handelstags. Ohne Datum kommt der letzte Handelstag.
Ausgabe: data/idx/kurse.json (Werte in IDR, Schlusskurs je Kürzel).
"""
import json, os, sys, time, urllib.request
from idx_fundamentals import FIRMEN  # gleiche 35 Kürzel wie bei den Jahreszahlen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUSGABE = os.path.join(ROOT, "data", "idx", "kurse.json")
URL = "https://www.idx.id/primary/TradingSummary/GetStockSummary?start=0&length=1000"
UA = "Mozilla/5.0 (dividenden-rechner.de Datensammlung)"
SCHLUSS_FELDER = ["Close", "ClosePrice", "LastPrice", "Last"]


def laden(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def feld(zeile, namen):
    for n in namen:
        if zeile.get(n) is not None:
            return zeile[n]
    return None


def main():
    daten = None
    for versuch in range(3):
        try:
            daten = laden(URL)
            break
        except Exception as e:
            print(f"Versuch {versuch + 1} fehlgeschlagen: {e}", file=sys.stderr)
            time.sleep(10)
    if not daten:
        sys.exit("Keine Antwort von IDX")
    zeilen = daten.get("data", [])
    print("Felder:", sorted(zeilen[0].keys()) if zeilen else "keine Zeilen")
    kurse, fehlend = {}, []
    for kode in FIRMEN:
        z = next((x for x in zeilen if x.get("StockCode") == kode), None)
        if not z:
            fehlend.append(kode)
            continue
        schluss = feld(z, SCHLUSS_FELDER)
        kurse[kode] = {
            "datum": (z.get("Date") or "")[:10],
            "schluss": schluss,
            "vorschluss": z.get("Previous"),
            "hoch": z.get("High"),
            "tief": z.get("Low"),
            "volumen": z.get("Volume"),
        }
    ausgabe = {
        "quelle": "IDX, TradingSummary/GetStockSummary (Tagesübersicht)",
        "waehrung": "IDR",
        "stand": time.strftime("%Y-%m-%d %H:%M", time.gmtime()) + " UTC",
        "kurse": kurse,
        "fehlend": fehlend,
    }
    os.makedirs(os.path.dirname(AUSGABE), exist_ok=True)
    with open(AUSGABE, "w", encoding="utf-8") as f:
        json.dump(ausgabe, f, ensure_ascii=False, indent=1)
    print(f"{len(kurse)} Kurse, fehlend: {fehlend}")


if __name__ == "__main__":
    main()
