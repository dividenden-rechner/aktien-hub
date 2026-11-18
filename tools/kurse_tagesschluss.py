#!/usr/bin/env python3
"""Einmal am Tag: Schlusskurse dauerhaft speichern und Kurskennzahlen fuer die Asien-Firmen berechnen.

Quelle: die Tagesdateien der Deutschen Boerse, die xetra-kurse.yml bereits laedt
(data/kurse/xetra|tradegate|frankfurt/<datum>.json, MiFID-II-Post-Trade, 15 Min. verzoegert, EUR).

1) Archiv: data/kurse/tagesschluss/<JJJJ-MM>.json  {"tage": {datum: {ISIN: [schluss, platz, abschluesse]}}}
   fuer alle ISINs aus data/kennzahlen.json und die Asien-Firmen. Unbereinigte Schlusskurse in EUR, keine
   Split-/Dividendenanpassung. Gleicher Tag erneut -> wird ersetzt (idempotent). So waechst die Historie ab heute.
2) data/asien/kennzahlen.json fuer die Asien-Firmen aus data/asien/fundamentals.json: Kurs (EUR), Rendite,
   KGV, Ausschuettungsquote; Dividende und Gewinn je Aktie werden mit dem EZB-Referenzkurs in EUR umgerechnet.
Aufruf: python3 tools/kurse_tagesschluss.py
"""
import glob
import json
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAETZE = [("xetra", "Xetra"), ("tradegate", "Tradegate"), ("frankfurt", "Börse Frankfurt")]
# Asien-Firmen im Hub -> in Deutschland gehandelte ISIN (geprüft gegen HKEX-Liste bzw. Frankfurt-Datei)
ASIEN_ISIN = {
    "0001.HK": ("KYG217651051", None),
    "0019.HK": ("HK0019000162", None),
    "0142.HK": ("BMG348041077", None),
    "D05.SI": ("SG1L01001701", None),
    "002594.SZ": ("CNE100000296", "Kurs der H-Aktie (1211.HK); die A-Aktie 002594.SZ wird in Deutschland nicht gehandelt"),
}


def lade(pfad):
    with open(pfad, encoding="utf-8") as f:
        return json.load(f)


def verfuegbare_tage():
    tage = set()
    for ordner, _ in PLAETZE:
        tage |= {os.path.basename(p)[:10] for p in glob.glob(os.path.join(ROOT, "data", "kurse", ordner, "*.json"))}
    return sorted(tage)


def tagesdateien(tag):
    daten = {}
    for ordner, name in PLAETZE:
        p = os.path.join(ROOT, "data", "kurse", ordner, f"{tag}.json")
        if os.path.exists(p):
            daten[name] = lade(p)["k"]
    return daten


def bester_kurs(isin, daten):
    """Erster Handelsplatz (Xetra, Tradegate, Frankfurt) mit Abschluessen; sonst None."""
    for _, name in PLAETZE:
        z = daten.get(name, {}).get(isin)
        if z and z[3] is not None and (z[5] or 0) > 0 and z[6] == "EUR":
            return float(z[3]), name, int(z[5])
    return None


def archivieren(tag, daten, isins):
    pfad = os.path.join(ROOT, "data", "kurse", "tagesschluss", f"{tag[:7]}.json")
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    arch = lade(pfad) if os.path.exists(pfad) else {
        "quelle": "Deutsche Börse Post-Trade (Xetra, Tradegate, Börse Frankfurt), 15 Min. verzögert",
        "art": "Schlusskurs in EUR, unbereinigt (keine Split- oder Dividendenanpassung)",
        "felder": ["schluss_eur", "platz", "abschluesse"], "tage": {}}
    eintrag = {}
    for isin in sorted(isins):
        k = bester_kurs(isin, daten)
        if k:
            eintrag[isin] = [k[0], k[1], k[2]]
    arch["tage"][tag] = eintrag
    arch["tage"] = dict(sorted(arch["tage"].items()))
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(arch, f, ensure_ascii=False, separators=(",", ":"))
    return pfad, len(eintrag)


def letzter(reihe):
    return reihe[-1] if reihe else None


def asien_kennzahlen(tag, daten, fx):
    fund = lade(os.path.join(ROOT, "data", "asien", "fundamentals.json"))["firmen"]
    werte = {}
    for sym, (isin, hinweis) in ASIEN_ISIN.items():
        f = fund.get(sym)
        k = bester_kurs(isin, daten)
        if not f or not k:
            continue
        w = f.get("w")
        kurs = fx.get(w) if w != "EUR" else 1.0
        eps = letzter(f["k"].get("eps_ber", []))
        dps = letzter(f["k"].get("dividende_je_aktie", []))
        eintrag = {"isin": isin, "kurs_eur": k[0], "boerse": k[1], "datum": tag, "waehrung": w, "fx": kurs,
                   "gj": (eps or dps or [f.get("gj", "")])[0][:4], "bericht": "Geschäftsbericht", "abschluesse": k[2]}
        if hinweis:
            eintrag["hinweis"] = hinweis
        if kurs:
            if eps and eps[1]:
                eps_eur = eps[1] / kurs
                eintrag["eps"] = round(eps[1], 4)
                eintrag["kgv"] = round(k[0] / eps_eur, 1) if eps_eur > 0 else None
            if dps and dps[1]:
                eintrag["dividende"] = round(dps[1], 4)
                eintrag["rendite"] = round(dps[1] / kurs / k[0] * 100, 2)
                if eps and eps[1] and eps[1] > 0 and eps[0][:4] == dps[0][:4]:
                    eintrag["ausschuettung"] = round(dps[1] / eps[1] * 100, 0)
        werte[sym] = eintrag
    return werte


def main():
    tage = verfuegbare_tage()
    if not tage:
        raise SystemExit("Keine Tagesdateien unter data/kurse/ gefunden")
    kz = lade(os.path.join(ROOT, "data", "kennzahlen.json"))["werte"]
    isins = {v["isin"] for v in kz.values() if v.get("isin")} | {i for i, _ in ASIEN_ISIN.values()}
    # alle noch vorhandenen Tagesdateien archivieren (idempotent); die Deutsche Boerse haelt sie nur kurz vor
    for t in tage:
        pfad, n = archivieren(t, tagesdateien(t), isins)
        print(f"  archiviert {t}: {n} Schlusskurse")
    tag = tage[-1]
    daten = tagesdateien(tag)
    ezb = lade(os.path.join(ROOT, "data", "wechselkurse-ezb.json"))
    werte = asien_kennzahlen(tag, daten, ezb.get("je_eur", {}))
    out = {"stand": date.today().isoformat(), "kurstag": tag, "ezb_kurs_vom": ezb.get("datum_ezb"),
           "hinweis": ("Kurs: Deutsche Börse (verzögert, EUR). Dividende und Gewinn je Aktie aus dem Geschäftsbericht, "
                       "mit EZB-Referenzkurs umgerechnet. Maschinell, ungeprüft, keine Anlageberatung."),
           "werte": werte}
    os.makedirs(os.path.join(ROOT, "data", "asien"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "asien", "kennzahlen.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"Kurstag {tag}: {n} Schlusskurse archiviert in {os.path.relpath(pfad, ROOT)}; Asien-Kennzahlen: {len(werte)}")
    for s, v in werte.items():
        print(" ", s, v.get("kurs_eur"), v.get("boerse"), "KGV", v.get("kgv"), "Rendite", v.get("rendite"), "Payout", v.get("ausschuettung"))


if __name__ == "__main__":
    main()
