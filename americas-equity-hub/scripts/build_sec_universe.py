#!/usr/bin/env python3
"""Kanada und Mexiko aus zulaessigen Quellen: SEC EDGAR (gemeinfrei) + GLEIF (CC0).

Universum: alle Emittenten mit Boersenkuerzel laut SEC (company_tickers_exchange) sowie alle Einreicher von 40-F/20-F der
letzten vier Quartale, deren Sitz laut SEC-Stammdaten (submissions: stateOfIncorporation) in Kanada (Provinzcodes A0-A9,
B0, Z4) bzw. Mexiko (O5) liegt. Damit enthalten: Emittenten, die bei der SEC melden (meist die groesseren mit US-Notierung).
Nicht enthalten: Firmen ohne SEC-Meldung (TSX/TSXV-only, BMV/BIVA-only) - dafuer gibt es keine Quelle mit Freigabe.
LEI: GLEIF-Volltextsuche mit Sitzland, angenommen nur bei exakt passendem normalisiertem Namen (beide Richtungen).
ISIN: GLEIF LEI->ISIN, nur Aktien-ISINs des Sitzlandes (Kanada: CUSIP-Emissionsnummer numerisch; Mexiko: MX01/MXP),
nur bei Eindeutigkeit. Heimatboerse (TSX/BMV) bleibt leer: keine Quelle mit Freigabe.
Schreibt data/universe/<land>/{issuers,securities,listings,review,summary,sec_liste}.json; Cache data/universe/sec_cache.json.
Aufruf (SEC verlangt Absender): SEC_UA="Name Kontakt" python3 scripts/build_sec_universe.py [--land CA,MX] [--max-neu N]"""
import argparse
import gzip
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import date, datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
BASIS = os.path.dirname(HIER)
sys.path.insert(0, BASIS)
from app import rights  # noqa: E402
from app.common import enthalten, get, isin_gueltig, norm_tokens, wort_passt  # noqa: E402

ROOT = os.path.dirname(BASIS)
UNI = os.path.join(BASIS, "data", "universe")
LAND_CODES = {"CA": {"A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "B0", "Z4"}, "MX": {"O5"}}
MIC = {"NYSE": "XNYS", "Nasdaq": "XNAS", "CBOE": "BATS", "NYSE American": "XASE", "NYSE Arca": "ARCX", "OTC": "OTCM"}
FORMEN = ("40-F", "20-F", "10-K")


def ua():
    return {"User-Agent": os.environ.get("SEC_UA", "").strip() or "dividenden-rechner.de Datenabruf"}


def sec_json(url):
    time.sleep(0.12)   # unter 10 Anfragen je Sekunde
    return json.loads(get(url, headers=ua(), timeout=90))


def formular_ciks(quartale):
    """CIKs mit 40-F/20-F/10-K in den gegebenen Quartalen aus dem EDGAR-Formularverzeichnis (form.gz)."""
    ciks = {}
    for j, q in quartale:
        try:
            roh = gzip.decompress(get(f"https://www.sec.gov/Archives/edgar/full-index/{j}/QTR{q}/form.gz", headers=ua(), timeout=300))
        except Exception as e:  # noqa: BLE001
            print("  form.gz", j, q, "nicht ladbar:", str(e)[:60])
            continue
        for z in roh.decode("latin-1").splitlines():
            f = z[:12].strip()
            if f.rstrip("/A") in FORMEN or f in FORMEN:
                m = re.search(r"\s(\d{1,10})\s+\d{4}-\d{2}-\d{2}\s", z)
                if m:
                    ciks.setdefault(int(m.group(1)), set()).add(f.rstrip("/A"))
        time.sleep(0.2)
    return ciks


def letzte_quartale(n=4):
    h = date.today()
    j, q = h.year, (h.month - 1) // 3 + 1
    out = []
    for _ in range(n):
        out.append((j, q))
        q -= 1
        if q == 0:
            j, q = j - 1, 4
    return out


def gleif_lei(name, land):
    ziel = norm_tokens(name)
    such = re.sub(r"[^\w\s&-]", " ", name)
    try:
        d = json.loads(get("https://api.gleif.org/api/v1/lei-records?" + urllib.parse.urlencode(
            {"filter[fulltext]": such, "filter[entity.legalAddress.country]": land, "page[size]": 10})))["data"]
    except Exception:
        return None
    treffer = []
    for x in d:
        e = x["attributes"]["entity"]
        namen = [e["legalName"]["name"]] + [o.get("name") for o in e.get("otherNames") or []]
        for n in namen:
            tk = norm_tokens(n)
            if tk and enthalten(ziel, tk) and not [w for w in tk if not any(wort_passt(w, z) for z in ziel)]:
                treffer.append((x["id"], e["legalName"]["name"], e.get("status")))
                break
    akt = [t for t in treffer if t[2] == "ACTIVE"] or treffer
    return akt[0] if len({t[0] for t in akt}) == 1 else None


def gleif_isins(lei):
    out, seite = [], 1
    while seite < 15:
        try:
            r = json.loads(get(f"https://api.gleif.org/api/v1/lei-records/{lei}/isins?page[size]=200&page[number]={seite}"))
        except Exception:
            break
        out += [x["attributes"]["isin"] for x in r.get("data", [])]
        if seite >= ((r.get("meta") or {}).get("pagination") or {}).get("lastPage", 1):
            break
        seite += 1
        time.sleep(0.3)
    return out


def aktien_isin(isins, land):
    if land == "CA":
        k = [i for i in isins if i.startswith("CA") and isin_gueltig(i) and i[9:11].isdigit()]
    else:
        k = [i for i in isins if (i.startswith("MX01") or i.startswith("MXP")) and isin_gueltig(i)]
    k = sorted(set(k))
    return (k[0], "gleif_lei_isin_eindeutig", k) if len(k) == 1 else (None, "mehrdeutig" if k else "keine_aktien_isin_bei_gleif", k)


def vorhandene_kuerzel():
    s = set()
    for p in ("data/sec/fundamentals.json", "data/esef/fundamentals.json", "data/boerse-de/fundamentals.json", "data/asien/fundamentals.json"):
        try:
            s |= {k.upper() for k in json.load(open(os.path.join(ROOT, p), encoding="utf-8"))["firmen"]}
        except Exception:
            pass
    for d in ("data/esef/firma", "data/asien/firma"):
        try:
            s |= {f[:-5].upper() for f in os.listdir(os.path.join(ROOT, d)) if f.endswith(".json")}
        except Exception:
            pass
    return s


def schreibe(pfad, obj):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(pfad + ".tmp", pfad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--land", default="CA,MX")
    ap.add_argument("--max-neu", type=int, default=12000, help="hoechstens so viele neue submissions-Abrufe je Lauf")
    a = ap.parse_args()
    laender = [x.strip() for x in a.land.split(",") if x.strip()]
    assert rights.publizierbar(["sec_edgar"]) and rights.publizierbar(["gleif"]), "Rechte-Gate: SEC/GLEIF nicht freigegeben"
    abruf = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cache_p = os.path.join(UNI, "sec_cache.json")
    try:
        cache = json.load(open(cache_p, encoding="utf-8"))
    except Exception:
        cache = {}
    cache.setdefault("submissions", {})
    cache.setdefault("gleif", {})
    j = sec_json("https://www.sec.gov/files/company_tickers_exchange.json")
    f = j["fields"]
    boerse = {}
    for r in j["data"]:
        boerse.setdefault(int(r[f.index("cik")]), []).append((r[f.index("ticker")], r[f.index("exchange")], r[f.index("name")]))
    form = formular_ciks(letzte_quartale(4))
    kandidaten = sorted(set(boerse) | {c for c, fs in form.items() if fs & {"40-F", "20-F"}})
    neu = 0
    for cik in kandidaten:
        k = str(cik)
        if k in cache["submissions"]:
            continue
        if neu >= a.max_neu:
            break
        try:
            s = sec_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        except Exception:
            continue
        cache["submissions"][k] = [s.get("stateOfIncorporation") or "", s.get("name") or "", s.get("sic") or "",
                                   (s.get("addresses", {}).get("business") or {}).get("stateOrCountry") or ""]
        neu += 1
        if neu % 500 == 0:
            schreibe(cache_p, cache)
            print(f"  submissions: {neu} neu, {len(cache['submissions'])} gesamt", flush=True)
    schreibe(cache_p, cache)
    vergeben = vorhandene_kuerzel()
    for land in laender:
        codes = LAND_CODES[land]
        iss, secs, lst, review, sec_liste = [], [], [], [], {}
        for k, (staat, name, sic, adresse) in sorted(cache["submissions"].items(), key=lambda kv: int(kv[0])):
            if staat not in codes:
                continue
            cik = int(k)
            if sic == "6770":
                review.append({"cik": cik, "name": name, "grund": "Mantelgesellschaft (SIC 6770), nicht übernommen"})
                continue
            if cik not in boerse and not (form.get(cik, set()) & {"40-F", "20-F", "10-K"}):
                continue
            gk = f"{land}:{cik}"
            if gk not in cache["gleif"]:
                lei = gleif_lei(name, land)
                isins = gleif_isins(lei[0]) if lei else []
                cache["gleif"][gk] = {"lei": lei, "isins": isins}
                time.sleep(0.5)
            g = cache["gleif"][gk]
            lei = g["lei"][0] if g.get("lei") else None
            isin, methode, kand = aktien_isin(g.get("isins") or [], land) if lei else (None, "kein_lei", [])
            issuer_id = f"SEC:CIK:{cik}"
            iss.append({"issuer_id": issuer_id, "cik": cik, "name": name, "lei": lei, "sitz_sec_code": staat, "sitzland": land,
                        "sic": sic or None, "quellen": ["sec_edgar"] + (["gleif"] if lei else []), "verified": False, "human_review": "pending"})
            sec_id = isin or f"{issuer_id}:STAMM"
            secs.append({"security_id": sec_id, "issuer_id": issuer_id, "isin": isin, "isin_methode": methode,
                         "isin_kandidaten": kand or None, "gattung": None, "quellen": ["gleif"] if isin else [],
                         "verified": False, "human_review": "pending"})
            ticks = boerse.get(cik, [])
            for t, b, _ in ticks:
                lst.append({"listing_id": f"{t}@{MIC.get(b, b)}", "kuerzel": t, "mic": MIC.get(b), "boerse": b, "security_id": sec_id,
                            "issuer_id": issuer_id, "status": "aktiv_laut_sec", "handelswaehrung": None,
                            "handelswaehrung_hinweis": "nicht in SEC-Daten angegeben", "quelle": "sec_edgar", "abgerufen": abruf,
                            "verified": False, "human_review": "pending"})
            # Hub-Kuerzel: erstes Kuerzel an NYSE/Nasdaq, sonst ISIN, sonst CIK; nie ein schon vergebenes Kuerzel
            haupt = [t for t, b, _ in ticks if b in ("NYSE", "Nasdaq", "NYSE American", "CBOE")]
            hub = next((t.upper() for t in haupt if t.upper() not in vergeben), None) or isin or f"CIK{cik}"
            vergeben.add(hub)
            sec_liste[hub] = [cik, name]
            if not isin:
                review.append({"issuer_id": issuer_id, "name": name, "grund": f"ISIN offen ({methode})", "kandidaten": kand or None})
            if not ticks:
                review.append({"issuer_id": issuer_id, "name": name, "grund": "kein Börsenkürzel laut SEC (nur Formular)"})
        ziel = os.path.join(UNI, {"CA": "canada", "MX": "mexico"}[land])
        schreibe(os.path.join(ziel, "issuers.json"), iss)
        schreibe(os.path.join(ziel, "securities.json"), secs)
        schreibe(os.path.join(ziel, "listings.json"), lst)
        schreibe(os.path.join(ziel, "review.json"), review)
        schreibe(os.path.join(ziel, "sec_liste.json"), sec_liste)
        summary = {"erstellt": abruf, "land": land, "quelle": "SEC EDGAR + GLEIF", "emittenten": len(iss), "wertpapiere": len(secs),
                   "notierungen": len(lst), "mit_lei": sum(1 for i in iss if i["lei"]), "mit_isin": sum(1 for s in secs if s["isin"]),
                   "mit_us_notierung": sum(1 for i in iss if any(l["issuer_id"] == i["issuer_id"] for l in lst)),
                   "nicht_enthalten": "Emittenten ohne SEC-Meldung (nur Heimatbörse) – keine Quelle mit Freigabe"}
        schreibe(os.path.join(ziel, "summary.json"), summary)
        print(json.dumps(summary, ensure_ascii=False))
    schreibe(cache_p, cache)


if __name__ == "__main__":
    main()
