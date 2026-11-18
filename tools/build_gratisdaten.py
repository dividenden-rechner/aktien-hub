#!/usr/bin/env python3
"""Erzeugt data/frei/kennzahlen.json: nur die freigegebenen Felder (aktuelle Dividende, Ausschüttungsquote, KGV)
für die Firmen aus data/freigabe.json. Quelle ist data/kennzahlen.json. Alle anderen Kennzahlen und Firmen
gehören in den Bezahlbereich und stehen NICHT in dieser Datei.
Aufruf: python3 tools/build_gratisdaten.py
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def bauen(freigabe, kennzahlen):
    felder = freigabe["felder_frei"]
    werte = kennzahlen["werte"]
    out, fehlt = {}, []
    for f in freigabe["firmen"]:
        k = werte.get(f["sym"])
        if not k:
            fehlt.append(f["sym"]); continue
        out[f["sym"]] = {"name": f["name"], **{x: k.get(x) for x in felder},
                         "waehrung": k.get("waehrung"), "datum": k.get("datum"), "gj": k.get("gj")}
    return {"stand": kennzahlen.get("stand"), "felder": felder, "anzahl": len(out), "werte": out, "ohne_daten": fehlt,
            "hinweis": "Kostenlose Auswahl. Weitere Kennzahlen und Firmen im Abo."}

if __name__ == "__main__":
    fr = json.load(open(os.path.join(ROOT, "data", "freigabe.json"), encoding="utf-8"))
    kz = json.load(open(os.path.join(ROOT, "data", "kennzahlen.json"), encoding="utf-8"))
    res = bauen(fr, kz)
    os.makedirs(os.path.join(ROOT, "data", "frei"), exist_ok=True)
    json.dump(res, open(os.path.join(ROOT, "data", "frei", "kennzahlen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(res["anzahl"], "Firmen frei,", len(res["ohne_daten"]), "ohne Daten:", res["ohne_daten"])
