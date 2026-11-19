#!/usr/bin/env python3
"""Kanadische Indexmitglieder -> SEC-CIK (fuer Firmen, die bei der SEC melden, meist Formular 40-F, XBRL nach IFRS).
Quelle: www.sec.gov/files/company_tickers_exchange.json (US-Behoerde, gemeinfrei). Angenommen wird ein Eintrag nur,
wenn der SEC-Name in beiden Richtungen zum Emittentennamen passt und das Ergebnis eindeutig ist; bei mehreren Treffern
gewinnt das gleiche Basiskuerzel (RY = RY). Laeuft in GitHub Actions (SEC verlangt einen Absender: Secret SEC_UA).
Schreibt data/universe/canada/sec_cik.json {hub_kuerzel: [cik, sec_name]} und sec_cik_pruefung.json."""
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
from app.common import enthalten, get, norm_tokens, wort_passt  # noqa: E402

UNI = os.path.join(os.path.dirname(HIER), "data", "universe", "canada")


def _ohne_zusatz(n):
    import re
    return re.sub(r"/[A-Z]{2,4}/?", " ", n or "")   # SEC-Zusaetze wie 'BANK OF MONTREAL /CAN/'


def passt(a, b, erlaubt=0):
    ta, tb = norm_tokens(_ohne_zusatz(a)), norm_tokens(_ohne_zusatz(b))
    if not ta or not tb:
        return False
    rest = [w for w in tb if not any(wort_passt(w, z) for z in ta)]
    return enthalten(ta, tb) and len(rest) <= erlaubt


def zuordnen(listings, sec):
    """listings mit Feld 'name' (Emittent) gegen SEC-Liste [(cik, name, ticker, boerse)]."""
    sec_by = {}
    for cik, titel, tick, boerse in sec:
        sec_by.setdefault(cik, (titel, set()))[1].add((tick or "").upper())
    ergebnis, pruef = {}, []
    for l in listings:
        n = l.get("name") or ""
        basis = l["ticker"].split(".")[0]
        kand = [cik for cik, (titel, ticks) in sec_by.items() if passt(n, titel) or passt(titel, n)]
        if len(kand) > 1:
            gleich = [c for c in kand if basis in sec_by[c][1]]
            kand = gleich or kand
        if not kand:   # zweiter Versuch: ein Zusatzwort bei der SEC ('TORONTO DOMINION' ~ 'TORONTO DOMINION BANK'),
            # aber nur, wenn die SEC dasselbe Basiskuerzel fuehrt
            kand = [cik for cik, (titel, ticks) in sec_by.items() if basis in ticks and passt(n, titel, erlaubt=1)]
        if len(kand) == 1:
            ergebnis[l["hub_kuerzel"]] = [kand[0], sec_by[kand[0]][0]]
        else:
            pruef.append({"hub_kuerzel": l["hub_kuerzel"], "name": n, "kandidaten": [[c, sec_by[c][0]] for c in kand][:5]})
    return ergebnis, pruef


def main():
    ua = os.environ.get("SEC_UA", "").strip() or "dividenden-rechner.de Datenabruf"
    j = json.loads(get("https://www.sec.gov/files/company_tickers_exchange.json", headers={"User-Agent": ua}))
    f = j["fields"]
    sec = [(r[f.index("cik")], r[f.index("name")], r[f.index("ticker")], r[f.index("exchange")]) for r in j["data"]]
    listings = json.load(open(os.path.join(UNI, "listings.json"), encoding="utf-8"))
    issuers = json.load(open(os.path.join(UNI, "issuers.json"), encoding="utf-8"))
    secs = {s["security_id"]: s for s in json.load(open(os.path.join(UNI, "securities.json"), encoding="utf-8"))}
    iss_name = {i["issuer_id"]: i["name"] for i in issuers}
    for l in listings:   # Emittentenname an die Notierung haengen
        l["name"] = iss_name.get(secs[l["security_id"]]["issuer_id"])
    ergebnis, pruef = zuordnen(listings, sec)
    json.dump(ergebnis, open(os.path.join(UNI, "sec_cik.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(pruef, open(os.path.join(UNI, "sec_cik_pruefung.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"SEC-CIK: {len(ergebnis)} von {len(listings)} zugeordnet, {len(pruef)} ohne eindeutigen Treffer")


if __name__ == "__main__":
    main()
