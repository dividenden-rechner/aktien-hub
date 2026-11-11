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
    try:
        PROG = json.load(open("data/prognosen.json", encoding="utf-8")).get("firmen", {})
    except Exception:
        PROG = {}
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
        o = {"isin": z["isin"], "kurs_eur": k_eur, "boerse": {"DETR": "Xetra", "DGAT": "Tradegate", "DFRA": "Frankfurt"}.get(boerse, boerse), "veraenderung": veraend, "datum": tag, "waehrung": w, "fx": 1.0 if w == "EUR" else rate[w], "gj": gj[:4],
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
        # Margen, EBITDA, Unternehmenswert, Bilanz, Altman-Z und Piotroski (SEC-Bilanz und GuV)
        bg, op, da, zins = g("bruttogewinn"), g("operatives_ergebnis"), g("abschreibungen"), g("zinsaufwand")
        st = g("steuern")
        op_ber = False
        if op is None and gew is not None and st is not None and zins is not None:
            op, op_ber = gew + st + abs(zins), True   # EBIT naeherungsweise: Gewinn + Steuern + Zinsaufwand
        A, ca, cl, L, inv, re_, sk = g("bilanzsumme"), g("umlaufvermoegen"), g("kurzfr_verbindl"), g("verbindlichkeiten"), g("vorraete"), g("gewinnruecklagen"), g("schulden_kurz")
        ebitda = op + abs(da) if op is not None and da is not None else None
        schulden_ges = (sch or 0) + (sk or 0) if sch is not None or sk is not None else None
        ev = bw + schulden_ges - (cash or 0) if bw and schulden_ges is not None else None
        ffo = gew + abs(da) if gew is not None and da is not None else None
        P = lambda a, b, n=1: r2(a / b * 100, n) if a is not None and b else None
        X = lambda a, b, n=2: r2(a / b, n) if a is not None and b and b > 0 else None
        alt = None
        if all(v is not None for v in (ca, cl, re_, op, ums, L)) and A and L and bw:
            alt = r2(1.2 * (ca - cl) / A + 1.4 * re_ / A + 3.3 * op / A + 0.6 * bw / L + 1.0 * ums / A, 2)
        # Piotroski-F-Score: 9 Pruefungen gegen das Vorjahr
        pio = None
        e1 = (f["k"].get("umsatz") or [[None]])[-2][0] if len(f["k"].get("umsatz") or []) > 1 else None
        if e1 and A and gew is not None and ocf is not None:
            A1, n1, o1 = wert_am(f, "bilanzsumme", e1), wert_am(f, "gewinn", e1), wert_am(f, "operativer_cf", e1)
            if A1 and n1 is not None:
                lt1, ca1, cl1, sh1 = wert_am(f, "schulden_lang", e1), wert_am(f, "umlaufvermoegen", e1), wert_am(f, "kurzfr_verbindl", e1), wert_am(f, "aktien_verw", e1)
                bg1, u1 = wert_am(f, "bruttogewinn", e1), wert_am(f, "umsatz", e1)
                tests = [gew > 0, ocf > 0, gew / A > n1 / A1, ocf > gew,
                         (sch or 0) / A < (lt1 or 0) / A1 if lt1 is not None or sch is not None else None,
                         (ca / cl > ca1 / cl1) if ca and cl and ca1 and cl1 else None,
                         (aktien <= sh1 * 1.005) if aktien and sh1 else None,
                         (bg / ums > bg1 / u1) if bg and ums and bg1 and u1 else None,
                         (ums / A > u1 / A1) if ums and u1 else None]
                if sum(t is not None for t in tests) >= 7:
                    pio = sum(1 for t in tests if t)
        epsg5 = wachs(eps, vj("eps_verw", 5), 5)
        o.update({
            "bruttomarge": P(bg, ums, 1) if ums and ums > 0 else None, "operative_marge": P(op, ums, 1) if ums and ums > 0 else None,
            "ebitda_marge": P(ebitda, ums, 1) if ums and ums > 0 else None, "ebitda_usd": U(ebitda), "ev_usd": U(ev),
            "ev_ebitda": X(ev, ebitda, 1), "ev_umsatz": X(ev, ums, 2), "ev_fcf": X(ev, fcf, 1),
            "nettoschulden_ebitda": r2((schulden_ges - (cash or 0)) / ebitda, 2) if schulden_ges is not None and ebitda and ebitda > 0 else None,
            "zinsdeckung": X(op, abs(zins) if zins else None, 1), "zinsaufwand_usd": U(abs(zins) if zins is not None else None),
            "zins_ebitda": P(abs(zins) if zins is not None else None, ebitda) if ebitda and ebitda > 0 else None,
            "roa": P(gew, A), "roce": P(op, (A - cl) if A and cl is not None else None),
            "roic": P(op * 0.79 if op is not None else None, (schulden_ges or 0) + ek if ek else None),
            "schulden_bilanz": X(schulden_ges, A), "current_ratio": X(ca, cl), "quick_ratio": X((ca - (inv or 0)) if ca is not None else None, cl),
            "schulden_ges_usd": U(schulden_ges), "op_wachstum": wachs(op, vj("operatives_ergebnis")),
            "peg": r2((kurs / eps) / epsg5, 2) if eps and eps > 0 and epsg5 and epsg5 > 0 else None,
            "ffo_usd": U(ffo), "ffo_je_aktie": r2(ffo / aktien, 2) if ffo is not None and aktien else None,
            "kurs_ffo": X(kurs, ffo / aktien if ffo and aktien else None, 1),
            "ffo_ausschuettung": P(abs(dg) if dg else None, ffo, 0) if ffo and ffo > 0 else None,
            "altman_z": alt, "piotroski": pio, "ebit_berechnet": op_ber, "eps": r2(eps, 2),
        })
        # Ausblick der Firma (Prognose aus der Ergebnismeldung): Forward-KGV, erwartetes Wachstum, erwartete Dividendenrendite
        pr = PROG.get(t)
        if pr:
            gjj = int(gj[:4])
            def wahl(*arten):
                for a in arten:
                    c = [x for x in pr["prognosen"] if x["kennzahl"] == a and int(x["geschaeftsjahr"]) >= gjj]
                    if c:
                        return min(c, key=lambda x: int(x["geschaeftsjahr"]))
                return None
            pe_ = wahl("eps_bereinigt", "eps_gaap")
            um_ = wahl("umsatz")
            uw_ = wahl("umsatzwachstum_proz", "organisches_wachstum_proz")
            dv_ = wahl("dividende_je_aktie")
            mid = lambda x: (x["von"] + x["bis"]) / 2
            fwd = {"datum": pr["datum"], "quelle": pr["quelle"]}
            if pe_ and mid(pe_) > 0:
                fwd.update({"eps_jahr": pe_["geschaeftsjahr"], "eps_von": pe_["von"], "eps_bis": pe_["bis"], "eps_art": "bereinigt" if pe_["kennzahl"] == "eps_bereinigt" else "GAAP",
                            "kgv_forward": r2(kurs / mid(pe_), 1), "eps_veraendert": pe_["veraendert"],
                            "eps_wachstum_erwartet": r2((mid(pe_) / eps - 1) * 100, 1) if eps and eps > 0 and pe_["kennzahl"] == "eps_gaap" else None})
            if um_ and ums:
                fwd.update({"umsatz_jahr": um_["geschaeftsjahr"], "umsatz_von": um_["von"], "umsatz_bis": um_["bis"],
                            "umsatz_wachstum_erwartet": r2((mid(um_) / ums - 1) * 100, 1)})
            elif uw_:
                fwd.update({"umsatz_jahr": uw_["geschaeftsjahr"], "umsatz_wachstum_von": uw_["von"], "umsatz_wachstum_bis": uw_["bis"]})
            if dv_ and kurs:
                fwd.update({"dividende_jahr": dv_["geschaeftsjahr"], "dividende_erwartet": mid(dv_), "rendite_erwartet": r2(mid(dv_) / kurs * 100, 2)})
            if len(fwd) > 2:
                o["prognose"] = fwd
        out[t] = o
    # BDCs: Quartalszahlen aus data/bdc.json + Kurs -> Kurs/NAV, NII-Rendite, Dividendendeckung
    try:
        BDC = json.load(open("data/bdc.json", encoding="utf-8")).get("firmen", {})
    except Exception:
        BDC = {}
    for t, b in BDC.items():
        qs = [q for q in b.get("quartale", []) if q.get("nav_je_aktie")]
        z = isin.get(t)
        if not qs or not isinstance(z, dict) or z["isin"] not in kurse["k"]:
            continue
        k_eur, veraend, kw = kurse["k"][z["isin"]][:3]
        if kw != "EUR" or "USD" not in rate:
            continue
        boerse = kurse["k"][z["isin"]][3] if len(kurse["k"][z["isin"]]) > 3 else "DETR"
        kusd = k_eur * rate["USD"]
        q = qs[-1]
        nav = q["nav_je_aktie"]
        nii = q.get("nii_bereinigt_je_aktie") or q.get("nii_je_aktie")
        reg, zus = q.get("dividende_regulaer") or 0, q.get("dividende_zusatz") or 0
        alt = next((x for x in reversed(qs[:-1]) if x["periode_ende"] <= str(int(q["periode_ende"][:4]) - 1) + q["periode_ende"][4:]), None)
        o = out.setdefault(t, {"isin": z["isin"], "name": b.get("name", t), "sektor": "BDC", "waehrung": "USD", "datum": tag,
                               "kurs_eur": k_eur, "veraenderung": veraend, "kurs_usd": r2(kusd),
                               "boerse": {"DETR": "Xetra", "DGAT": "Tradegate", "DFRA": "Frankfurt"}.get(boerse, boerse)})
        o["sektor"] = "BDC"
        o["bdc"] = {
            "quartal": q["periode_ende"], "nav": nav, "kurs_nav": r2(kusd / nav, 2),
            "nii": nii, "nii_rendite": r2(nii * 4 / kusd * 100, 2) if nii else None,
            "dividende_regulaer": reg or None, "dividende_zusatz": zus or None,
            "rendite": r2(reg * 4 / kusd * 100, 2) if reg else None, "rendite_inkl_zusatz": r2((reg + zus) * 4 / kusd * 100, 2) if reg or zus else None,
            "deckung": r2(nii / reg * 100, 0) if nii and reg else None,
            "nav_1j": r2((nav / alt["nav_je_aktie"] - 1) * 100, 1) if alt and alt.get("nav_je_aktie") else None,
            "non_accrual": q.get("non_accrual_fv_proz") or None, "verschuldung": q.get("verschuldung_netto") or None,
            "portfolio_mio": q.get("portfolio_mio") or None, "quelle": q.get("quelle"),
            "verlauf": [[x["periode_ende"], x.get("nav_je_aktie"), x.get("nii_bereinigt_je_aktie") or x.get("nii_je_aktie"), x.get("dividende_regulaer")] for x in qs]}
        # Fuer den Screener: allgemeine Felder mit BDC-Werten fuellen
        o["rendite"] = o.get("rendite") or o["bdc"]["rendite"]
        o["kbv"] = o["bdc"]["kurs_nav"]
        o["nav_je_aktie"] = nav
        o["schulden_ek"] = o["bdc"]["verschuldung"] or o.get("schulden_ek")
    json.dump({"stand": tag, "ezb_kurs_vom": fx_tag,
               "hinweis": "Kurs: Xetra-Schluss (Deutsche Börse, 15 Min. verzögert). Kennzahlen: letztes Geschäftsjahr laut SEC-Bericht; Kurs per EZB-Referenzkurs in die Berichtswährung umgerechnet.",
               "werte": out}, open("data/kennzahlen.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print(len(out), "Aktien mit Kennzahlen, Stand", tag)
    for t in ("KO", "MSFT", "O", "SAP", "JNJ", "ASML"):
        print(t, out.get(t))


if __name__ == "__main__":
    main()
