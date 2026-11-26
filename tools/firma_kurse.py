#!/usr/bin/env python3
"""Kursverlauf je Firma in Euro: data/firma-kurse/<SYMBOL>.json  {"stand", "waehrung": "EUR", "quelle", "kurse": [[datum, euro], ...]}

Zusammensetzung:
  - ab dem ersten Tag im eigenen Archiv (data/kurse/tagesschluss, Deutsche Börse, Euro): dieser Kurs
  - davor: Historie von Financial Modeling Prep (data/kurse/fmp-historie, Handelswährung), umgerechnet mit dem
    EZB-Referenzkurs des Tages (data/wechselkurse-historie.json; fehlt ein Tag, der letzte Kurs davor, höchstens 7 Tage)
Läuft täglich nach dem Schlusskurs-Archiv und wöchentlich nach der FMP-Historie.
"""
import glob, json, os
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIEL = os.path.join(ROOT, "data", "firma-kurse")


def lade(p, leer=None):
    try:
        return json.load(open(os.path.join(ROOT, p), encoding="utf-8"))
    except (OSError, ValueError):
        return {} if leer is None else leer


def archiv():
    """ISIN -> {datum: schlusskurs in EUR} aus allen Monatsdateien."""
    out = {}
    for pfad in sorted(glob.glob(os.path.join(ROOT, "data", "kurse", "tagesschluss", "*.json"))):
        for tag, werte in lade(os.path.relpath(pfad, ROOT)).get("tage", {}).items():
            for isin, v in werte.items():
                out.setdefault(isin, {})[tag] = v[0]
    return out


def kurs_am(ecb, w, tag):
    if w == "EUR":
        return 1.0
    reihe = ecb.get(w) or {}
    t = date.fromisoformat(tag)
    for i in range(8):
        k = (t - timedelta(days=i)).isoformat()
        if k in reihe:
            return reihe[k]
    return None


def main():
    kz = lade("data/kennzahlen.json").get("werte", {})
    iz = lade("data/kurse/isin-zuordnung.json")
    ecb = lade("data/wechselkurse-historie.json").get("kurse", {})
    arch = archiv()
    os.makedirs(ZIEL, exist_ok=True)
    n = 0
    syms = set(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(ROOT, "data", "kurse", "fmp-historie", "*.json")))
    syms |= set(kz.keys())
    for sym in sorted(syms):
        if sym.startswith("_"):
            continue
        isin = (iz.get(sym) or {}).get("isin") or (kz.get(sym) or {}).get("isin")
        eigen = arch.get(isin, {}) if isin else {}
        fmp = lade(f"data/kurse/fmp-historie/{sym}.json", {})
        davor = {}
        if fmp and fmp.get("kurse"):
            erster = min(eigen) if eigen else "9999-12-31"
            for tag, schluss in fmp["kurse"]:
                if tag >= erster:
                    continue
                r = kurs_am(ecb, fmp.get("waehrung", "EUR"), tag)
                if r:
                    davor[tag] = schluss / r
        reihe = {**davor, **eigen}
        if len(reihe) < 2:
            continue
        kurse = [[t, round(reihe[t], 4)] for t in sorted(reihe)]
        quelle = []
        if davor: quelle.append("Financial Modeling Prep, umgerechnet mit EZB-Referenzkurs")
        if eigen: quelle.append("Deutsche Börse (Schlusskurse, Archiv seit " + min(eigen) + ")")
        json.dump({"sym": sym, "stand": date.today().isoformat(), "waehrung": "EUR", "quelle": "; ".join(quelle), "kurse": kurse},
                  open(os.path.join(ZIEL, sym.replace("/", "_") + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        n += 1
    print("Kursdateien:", n)


if __name__ == "__main__":
    main()
