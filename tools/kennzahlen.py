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


# GICS-Sektoren aus der S&P-500-Liste, auf die Sektornamen des Screeners abgebildet
GICS = {"Information Technology": "Technology", "Health Care": "Healthcare", "Financials": "Financial Services",
        "Consumer Discretionary": "Consumer Cyclical", "Consumer Staples": "Consumer Defensive", "Materials": "Basic Materials"}
SEKTOR = {}


def main():
    try:
        for x in json.load(open("data/universe.json"))["firmen"]:
            SEKTOR[x["sym"].upper()] = GICS.get(x.get("sektor"), x.get("sektor"))
    except Exception:
        pass
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
        # Erweiterte Werte fuer den Screener (Geldbetraege zusaetzlich in USD, damit sie vergleichbar sind)
        usd = (rate["USD"] / rate[w]) if w != "EUR" and w in rate else rate.get("USD", 1.0)   # 1 Einheit Berichtswaehrung in USD
        if w == "USD":
            usd = 1.0
        def g(k, e=gj):
            return wert_am(f, k, e)
        ends = [e for e, _ in f["k"].get("umsatz", [])]
        def vj(k, n=1):   # Wert n Jahre vor dem letzten Geschaeftsjahr
            r = f["k"].get(k) or []
            return r[-1 - n][1] if len(r) > n and r[-1][0] == gj else None
        def wachs(a, b, n=1):
            return round(((a / b) ** (1 / n) - 1) * 100, 1) if a is not None and b and b > 0 and a > 0 else None
        ums, gew, dg, sch, cash = g("umsatz"), g("gewinn"), g("dividenden_gezahlt"), g("schulden_lang"), g("liquide_mittel")
        eps_a = vj("eps_verw")
        fcf_a = (vj("operativer_cf") - abs(vj("capex"))) if vj("operativer_cf") is not None and vj("capex") is not None else None
        streak = 0
        for (e1, a), (e2, b) in zip(reversed(dps_r[:-1]), reversed(dps_r[1:])):
            if b > a * 1.001:
                streak += 1
            else:
                break
        U = lambda v: None if v is None else round(v * usd)
        o.update({
            "name": f["n"], "sektor": SEKTOR.get(t), "kurs_usd": r2(k_eur * rate.get("USD", 1.0)),
            "boersenwert_usd": round(k_eur * rate.get("USD", 1.0) * aktien) if aktien else None,
            "umsatz_usd": U(ums), "gewinn_usd": U(gew), "ocf_usd": U(ocf), "fcf_usd": U(fcf), "capex_usd": U(abs(cx) if cx is not None else None),
            "dividenden_usd": U(abs(dg) if dg is not None else None), "schulden_usd": U(sch), "cash_usd": U(cash),
            "nettoschulden_usd": U(sch - cash) if sch is not None and cash is not None else None, "ek_usd": U(ek),
            "kuv": r2(bw / ums, 2) if bw and ums and ums > 0 else None,
            "kcv": r2(bw / ocf, 1) if bw and ocf and ocf > 0 else None,
            "kfcf": r2(bw / fcf, 1) if bw and fcf and fcf > 0 else None,
            "gewinnrendite": r2(eps / kurs * 100) if eps and kurs else None,
            "nettomarge": r2(gew / ums * 100, 1) if gew is not None and ums and ums > 0 else None,
            "roe": r2(gew / ek * 100, 1) if gew is not None and ek and ek > 0 else None,
            "schulden_ek": r2(sch / ek, 2) if sch is not None and ek and ek > 0 else None,
            "fcf_ausschuettung": r2(abs(dg) / fcf * 100, 0) if dg and fcf and fcf > 0 else None,
            "ocf_ausschuettung": r2(abs(dg) / ocf * 100, 0) if dg and ocf and ocf > 0 else None,
            "capex_umsatz": r2(abs(cx) / ums * 100, 1) if cx is not None and ums and ums > 0 else None,
            "capex_ocf": r2(abs(cx) / ocf * 100, 1) if cx is not None and ocf and ocf > 0 else None,
            "umsatz_wachstum": wachs(ums, vj("umsatz")), "umsatz_wachstum_3j": wachs(ums, vj("umsatz", 3), 3), "umsatz_wachstum_5j": wachs(ums, vj("umsatz", 5), 5),
            "gewinn_wachstum": wachs(gew, vj("gewinn")), "gewinn_wachstum_5j": wachs(gew, vj("gewinn", 5), 5),
            "eps_wachstum": wachs(eps, eps_a), "fcf_wachstum": wachs(fcf, fcf_a),
            "div_wachstum_1j": wachs(dps_r[-1][1], dps_r[-2][1]) if len(dps_r) > 1 else None,
            # Ganze Datenreihe (bis 10 Jahre) durchgehend erhoeht: die echte Serie ist vermutlich laenger -> 99 = "9+"
            "dividendenserie": (99 if dps_r and streak >= len(dps_r) - 1 and streak >= 9 else streak) if dps_r else None,
            "nav_je_aktie": r2(ek / aktien, 2) if ek and aktien else None,
        })
        out[t] = o
    json.dump({"stand": tag, "ezb_kurs_vom": fx_tag,
               "hinweis": "Kurs: Xetra-Schluss (Deutsche Börse, 15 Min. verzögert). Kennzahlen: letztes Geschäftsjahr laut SEC-Bericht; Kurs per EZB-Referenzkurs in die Berichtswährung umgerechnet.",
               "werte": out}, open("data/kennzahlen.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print(len(out), "Aktien mit Kennzahlen, Stand", tag)
    for t in ("KO", "MSFT", "O", "SAP", "JNJ", "ASML"):
        print(t, out.get(t))


if __name__ == "__main__":
    main()
