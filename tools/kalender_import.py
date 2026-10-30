#!/usr/bin/env python3
"""Liest eine Liste von Kalendereintraegen (JSON: firma, was, start, ganztag) und schreibt data/termine-kalender.json:
Ergebniskalender (Quartals-/Jahreszahlen, Trading Updates), Investorentage und Hauptversammlungen. Konferenzen u. a. werden ignoriert.
Firmennamen werden mit universe.json, feeds.json und asia-seed.txt auf Boersenkuerzel abgeglichen (sonst ohne Kuerzel).
Aufruf:  python3 tools/kalender_import.py export.json"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOP = {"the", "inc", "corp", "corporation", "company", "co", "ltd", "limited", "plc", "group", "holdings", "holding", "ag", "se", "sa", "nv", "de", "und", "and", "of", "class",
        "international", "technologies", "technology", "systems", "industries", "enterprises", "pharmaceuticals", "financial", "sab"}

def norm(n):
    n = re.sub(r"[^a-z0-9 ]", " ", n.lower().replace("&", " and "))
    return " ".join(w for w in n.split() if w not in STOP)

def known():
    m = {}
    for f in json.load(open(os.path.join(ROOT, "data/universe.json"), encoding="utf-8"))["firmen"]:
        m[norm(f["name"])] = f["sym"]
    for f in json.load(open(os.path.join(ROOT, "data/feeds.json"), encoding="utf-8"))["feeds"]:
        m[norm(f["name"])] = f["sym"]
    for l in open(os.path.join(ROOT, "data/asia-seed.txt"), encoding="utf-8"):
        if l.strip() and not l.startswith("#"):
            p = l.split("|"); m.setdefault(norm(p[1]), p[0].strip())
    m.pop("", None)
    return m

ALIAS = {"AMD": "AMD", "Commerzbank": "CBK.DE", "Bayer": "BAYN.DE", "Infineon Technologies": "IFX.DE", "Fresenius": "FRE.DE", "Hannover Rück": "HNR1.DE",
         "Hapag-Lloyd": "HLAG.DE", "Ferrari": "RACE", "Imperial Brands": "IMB.L", "Legal & General Group": "LGEN.L", "Maersk": "MAERSK-B.CO",
         "Koninklijke Ahold Delhize": "AD.AS", "Enbridge": "ENB", "Nutrien": "NTR", "Celanese": "CE", "Conagra Brands": "CAG", "Kohl’s": "KSS",
         "MercadoLibre": "MELI", "Main Street Capital": "MAIN", "Gladstone Capital": "GLAD", "Gladstone Commercial": "GOOD", "Gladstone Investment": "GAIN",
         "Gladstone Land": "LAND", "Oaktree Specialty Lending": "OCSL", "Blue Owl Capital Corporation": "OBDC", "Capital Southwest": "CSWC",
         "Franco-Nevada": "FNV", "MP Materials": "MP", "Nexstar Media Group": "NXST", "EnerSys": "ENS", "3i Group": "III.L", "On": "ONON", "Nebius": "NBIS",
         "Alimentation Couche-Tard": "ATD.TO", "Barrick Mining": "B"}


def kind(was):
    w = was.lower()
    if re.search(r"\(q&a\)|\(media\)|prepared remarks|conference|status update|corporate presentation|webcast", w): return None
    if re.search(r"\bagm\b|annual general", w): return "hauptversammlung"
    if re.search(r"investor day|\bcmd\b|capital markets", w): return "investorentag"
    if re.search(r"\btu\b|trading update", w): return "trading-update"
    if re.search(r"\bq[1-4]\b|\bh[12]\b|\bfy\b|full year|half|quarter|results", w): return "ergebnis"
    return None

def main():
    rows = json.load(open(sys.argv[1], encoding="utf-8")); k = known(); out = []; seen = set()
    for r in rows:
        art = kind(r["was"])
        if not art: continue
        n = norm(r["firma"]); sym = ALIAS.get(r["firma"]) or k.get(n)
        if not sym:
            for kn, s in k.items():
                if len(n) >= 4 and len(kn) >= 4 and (kn.startswith(n) or n.startswith(kn)): sym = s; break
        datum = r["start"][:10]; zeit = "" if r.get("ganztag") else r["start"][11:16]
        key = (r["firma"], art, datum)
        if key in seen: continue
        seen.add(key)
        out.append({"firma": r["firma"], "sym": sym or "", "art": art, "was": re.sub(r"\s*\(.*?\)\s*$", "", r["was"]).strip(), "datum": datum, "zeit_utc": zeit})
    out.sort(key=lambda x: (x["datum"], x["zeit_utc"], x["firma"]))
    json.dump({"stand": os.popen("date +%F").read().strip(), "quelle": "eigener Kalender (Unternehmenstermine)", "termine": out},
              open(os.path.join(ROOT, "data", "termine-kalender.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(out), "Termine,", sum(1 for x in out if x["sym"]), "mit Kuerzel;", "ohne Kuerzel:", sorted({x["firma"] for x in out if not x["sym"]})[:40])

if __name__ == "__main__":
    main()
