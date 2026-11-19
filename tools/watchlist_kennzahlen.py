#!/usr/bin/env python3
"""Kennzahlen für die Watchlist aus den SEC-Jahreszahlen (data/sec/fundamentals.json).

Schreibt data/watchlist-kennzahlen.json. Keine Kurse, keine Schätzungen: nur Werte, die aus den Berichten folgen.
Aufruf: python3 tools/watchlist_kennzahlen.py [TICKER ...]   (ohne Angabe: Standard-Watchlist aus aktien-hub/index.html)
"""
import json, os, re, sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEC_P = os.path.join(ROOT, "data", "sec", "fundamentals.json")
OUT_P = os.path.join(ROOT, "data", "watchlist-kennzahlen.json")
HUB_P = os.path.join(ROOT, "aktien-hub", "index.html")


def standard_watchlist():
    t = open(HUB_P, encoding="utf-8").read()
    m = re.search(r"POP=\[(.*?)\];", t, re.S)
    return re.findall(r'\["([A-Z.]+)"', m.group(1)) if m else []


def serie(k, name):
    return {d[:4]: v for d, v in k.get(name, [])}


def aktien_serie(k):
    # Stückzahlen liegen in den Quelldaten teils in Stück, teils in Millionen. Werte unter 1 Mio. gelten als Millionen.
    return {j: (v * 1e6 if v < 1e6 else v) for j, v in serie(k, "aktien_verw").items() if v}


def cagr(a, b, jahre):
    if a is None or b is None or a <= 0 or b <= 0 or jahre <= 0:
        return None
    return round(((b / a) ** (1 / jahre) - 1) * 100, 1)


def wachstum(s, j, n):
    """CAGR über n Jahre; Startjahr muss exakt j-n in der Reihe liegen."""
    start = str(int(j) - n)
    if start in s and j in s:
        return cagr(s[start], s[j], n)
    return None


def kennzahlen(f):
    k = f["k"]
    umsatz, gewinn, eps, div = serie(k, "umsatz"), serie(k, "gewinn"), serie(k, "eps_verw"), serie(k, "dividende_je_aktie")
    ocf, capex = serie(k, "operativer_cf"), serie(k, "capex")
    aktien, ek = aktien_serie(k), serie(k, "eigenkapital")
    schulden, zins, op = serie(k, "schulden_lang"), serie(k, "zinsaufwand"), serie(k, "operatives_ergebnis")
    jahre = sorted(set(umsatz) & set(gewinn))
    if not jahre:
        return None
    j = jahre[-1]
    out = {"geschaeftsjahr": j, "waehrung": f.get("w", "USD")}
    out["umsatz_mrd"] = round(umsatz[j] / 1e9, 2) if j in umsatz else None
    out["eps"] = eps.get(j)
    out["dividende_je_aktie"] = div.get(j)
    if eps.get(j) and div.get(j) is not None and eps[j] > 0:
        out["ausschuettungsquote_pct"] = round(div[j] / eps[j] * 100, 1)
    if j in ocf and j in capex:
        fcf = ocf[j] - abs(capex[j])
        out["fcf_mrd"] = round(fcf / 1e9, 2)
        if aktien.get(j):
            out["fcf_je_aktie"] = round(fcf / aktien[j], 2)
    if ek.get(j, 0) < 0:
        out["eigenkapital_negativ"] = True  # Verschuldungsgrad und Eigenkapitalrendite dann nicht aussagekräftig
    elif j in ek and ek[j]:
        if j in schulden:
            out["schulden_zu_eigenkapital"] = round(schulden[j] / ek[j], 2)
        if j in gewinn:
            out["eigenkapitalrendite_pct"] = round(gewinn[j] / ek[j] * 100, 1)
    if j in op and j in zins and zins[j]:
        out["zinsdeckung_x"] = round(op[j] / abs(zins[j]), 1)
    for n in (5, 10):
        out[f"eps_wachstum_{n}j_pct"] = wachstum(eps, j, n)
        out[f"dividende_wachstum_{n}j_pct"] = wachstum(div, j, n)
    out["datenjahre"] = [min(jahre), max(jahre)]
    return out


def main():
    tick = [t.upper() for t in sys.argv[1:]] or standard_watchlist()
    sec = json.load(open(SEC_P, encoding="utf-8"))["firmen"]
    ergebnis, fehlt = {}, []
    for t in tick:
        f = sec.get(t)
        r = kennzahlen(f) if f else None
        if r:
            r["name"] = f.get("n")
            ergebnis[t] = r
        else:
            fehlt.append(t)
    stand = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d")
    json.dump({"stand": stand, "quelle": "SEC-Jahreszahlen (companyfacts), Stand Datenbasis 2026-11-17",
               "hinweis": "Nur Werte aus den Berichten. Kurse, Bewertung und Schaetzungen fehlen bewusst.",
               "firmen": ergebnis, "ohne_daten": fehlt},
              open(OUT_P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(OUT_P, len(ergebnis), "Firmen", "ohne Daten:", fehlt)


if __name__ == "__main__":
    main()
