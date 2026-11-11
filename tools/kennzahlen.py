#!/usr/bin/env python3
"""Taegliche Kennzahlen je Aktie (ab 11.11.2026): Xetra-Schlusskurs (Deutsche Boerse, verzoegert, kostenlos) +
SEC-Jahreszahlen + EZB-Referenzkurse. Schreibt data/kennzahlen.json.
Alle Bewertungskennzahlen beziehen sich auf das letzte abgeschlossene Geschaeftsjahr (kein TTM).
Der Kurs wird mit dem EZB-Referenzkurs des Handelstags in die Berichtswaehrung umgerechnet."""
import json, re, urllib.request, xml.etree.ElementTree as ET

EZB = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"


def ezb_kurse():
    x = ET.fromstring(urllib.request.urlopen(urllib.request.Request(EZB, headers={"User-Agent": "dividenden-rechner.de"}), timeout=60).read())
    tage = {}
    for c in x.iter():
        if c.get("time"):
            tage[c.get("time")] = {k.get("currency"): float(k.get("rate")) for k in c if k.get("currency")}
    return tage


def letzter(f, k):
    r = f["k"].get(k)
    return (r[-1][0], r[-1][1]) if r else (None, None)


def wert_am(f, k, ende):
    for e, v in f["k"].get(k, []):
        if e == ende:
            return v
    return None


def cagr(reihe, jahre):
    if not reihe or len(reihe) <= jahre:
        return None
    a, b = reihe[-1 - jahre][1], reihe[-1][1]
    return round(((b / a) ** (1 / jahre) - 1) * 100, 1) if a and b and a > 0 and b > 0 else None


def r2(v, n=2):
    return None if v is None else round(v, n)


def main():
    sec = json.load(open("data/sec/fundamentals.json"))
    kurse = json.load(open("data/kurse/xetra-letzter.json"))
    isin = json.load(open("data/kurse/isin-zuordnung.json"))
    fx = ezb_kurse()
    tag = kurse["datum"]
    fx_tag = max((d for d in fx if d <= tag), default=max(fx))
    rate = fx[fx_tag]
    out = {}
    for t, f in sec["firmen"].items():
        z = isin.get(t)
        if not isinstance(z, dict) or not z or z["isin"] not in kurse["k"]:
            continue
        k_eur, veraend, kw = kurse["k"][z["isin"]][:3]
        boerse = kurse["k"][z["isin"]][3] if len(kurse["k"][z["isin"]]) > 3 else "DETR"
        if kw != "EUR":
            continue
        w = f.get("w", "USD")
        if w != "EUR" and w not in rate:
            continue
        kurs = k_eur * (rate[w] if w != "EUR" else 1.0)   # Kurs in Berichtswaehrung
        gj = f["gj"]
        dps_r = f["k"].get("dividende_je_aktie") or f["k"].get("dividende_je_aktie_ber") or []
        dps = wert_am(f, "dividende_je_aktie", gj) or wert_am(f, "dividende_je_aktie_ber", gj)
        eps = wert_am(f, "eps_verw", gj) or wert_am(f, "eps_ber", gj)
        aktien = wert_am(f, "aktien_verw", gj)
        ek = wert_am(f, "eigenkapital", gj)
        ocf, cx = wert_am(f, "operativer_cf", gj), wert_am(f, "capex", gj)
        fcf = ocf - abs(cx) if ocf is not None and cx is not None else None
        bw = kurs * aktien if aktien else None
        o = {"isin": z["isin"], "kurs_eur": k_eur, "boerse": {"DETR": "Xetra", "DGAT": "Tradegate", "DFRA": "Frankfurt"}.get(boerse, boerse), "veraenderung": veraend, "datum": tag, "waehrung": w, "gj": gj[:4],
             "boersenwert_eur": round(k_eur * aktien) if aktien else None,
             "dividende": r2(dps, 4), "rendite": r2(dps / kurs * 100) if dps and kurs else None,
             "kgv": r2(kurs / eps, 1) if eps and eps > 0 else None,
             "kbv": r2(bw / ek, 2) if bw and ek and ek > 0 else None,
             "ausschuettung": r2(dps / eps * 100, 0) if dps and eps and eps > 0 else None,
             "fcf_rendite": r2(fcf / bw * 100) if fcf is not None and bw else None,
             "div_wachstum_5j": cagr(dps_r, 5), "div_wachstum_10j": cagr(dps_r, 9),
             "dividende_berechnet": "dividende_je_aktie" not in f["k"]}
        out[t] = o
    json.dump({"stand": tag, "ezb_kurs_vom": fx_tag,
               "hinweis": "Kurs: Xetra-Schluss (Deutsche Börse, 15 Min. verzögert). Kennzahlen: letztes Geschäftsjahr laut SEC-Bericht; Kurs per EZB-Referenzkurs in die Berichtswährung umgerechnet.",
               "werte": out}, open("data/kennzahlen.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print(len(out), "Aktien mit Kennzahlen, Stand", tag)
    for t in ("KO", "MSFT", "O", "SAP", "JNJ", "ASML"):
        print(t, out.get(t))


if __name__ == "__main__":
    main()
