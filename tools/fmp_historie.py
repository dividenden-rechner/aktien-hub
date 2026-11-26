#!/usr/bin/env python3
"""Wöchentlich: Schlusskurse (Historie) je Firma von Financial Modeling Prep holen.

Schreibt data/kurse/fmp-historie/<SYMBOL>.json  {"sym", "stand", "waehrung", "kurse": [[datum, schluss], ...]}
in der Handelswährung der Firma (Währung aus data/kennzahlen.json). Umrechnung in Euro macht tools/firma_kurse.py.
Fehlt der Tarif für ein Symbol (HTTP 402/403), merken wir uns das in _status.json und fragen 30 Tage nicht erneut.
Aufruf: FMP_API_KEY=... python3 tools/fmp_historie.py   (FMP_MAX = Höchstzahl Abrufe je Lauf, Standard 400)
"""
import datetime as dt, json, os, time, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORD = os.path.join(ROOT, "data", "kurse", "fmp-historie")
KEY = os.environ.get("FMP_API_KEY", "").strip()
MAX = int(os.environ.get("FMP_MAX", "400"))
URL = "https://financialmodelingprep.com/stable/historical-price-eod/full"


def lade(p, leer):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return leer


def hole(sym):
    q = urllib.parse.urlencode({"symbol": sym, "apikey": KEY})
    with urllib.request.urlopen(urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": "dividenden-rechner.de Datensammlung"}), timeout=60) as r:
        j = json.loads(r.read())
    if isinstance(j, dict):
        raise ValueError(str(j.get("Error Message") or j)[:120])
    return j


def main():
    if not KEY:
        print("FMP_API_KEY fehlt"); return
    os.makedirs(ORD, exist_ok=True)
    kz = lade(os.path.join(ROOT, "data", "kennzahlen.json"), {}).get("werte", {})
    syms = set()
    for pfad, schl in (("data/firmenseiten.json", "firmen"), ("data/dividendenseiten.json", "firmen")):
        for f in lade(os.path.join(ROOT, pfad), {}).get(schl, []):
            syms.add(f["sym"])
    status_p = os.path.join(ORD, "_status.json")
    status = lade(status_p, {})
    heute = dt.date.today()
    def faellig(s):
        datei = os.path.join(ORD, s + ".json")
        if s in status and (heute - dt.date.fromisoformat(status[s]["stand"])).days < 30:
            return False
        return not os.path.exists(datei) or (heute - dt.date.fromisoformat(json.load(open(datei))["stand"])).days >= 6
    liste = sorted((s for s in syms if faellig(s)), key=lambda s: os.path.getmtime(os.path.join(ORD, s + ".json")) if os.path.exists(os.path.join(ORD, s + ".json")) else 0)
    print("Firmen:", len(syms), "fällig:", len(liste), "Obergrenze:", MAX)
    ok = fehl = 0
    for s in liste[:MAX]:
        w = (kz.get(s) or kz.get(s.replace(".", "-")) or {}).get("waehrung")
        if not w:
            continue
        try:
            daten = hole(s)
        except urllib.error.HTTPError as e:
            status[s] = {"stand": heute.isoformat(), "fehler": e.code}; fehl += 1
        except Exception as e:
            status[s] = {"stand": heute.isoformat(), "fehler": str(e)[:80]}; fehl += 1
        else:
            kurse = sorted([[x["date"], x["close"]] for x in daten if x.get("close") is not None])
            if kurse:
                json.dump({"sym": s, "stand": heute.isoformat(), "waehrung": w, "kurse": kurse},
                          open(os.path.join(ORD, s + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
                ok += 1
                status.pop(s, None)
        time.sleep(0.2)
    json.dump(status, open(status_p, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    print(f"geholt: {ok}, abgelehnt/fehlerhaft: {fehl}")


if __name__ == "__main__":
    main()
