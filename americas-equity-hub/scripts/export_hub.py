#!/usr/bin/env python3
"""SEC-Jahreszahlen der Kanada-/Mexiko-Emittenten -> eine Datei je Firma fuer Hub und kennzahlen.py
(data/americas/firma/<HUB-KUERZEL>.json, Format wie data/sec/fundamentals.json) plus Index.
Jedes Feld laeuft durch das Rechte-Gate: Finanzen (sec_edgar), LEI/ISIN (gleif); andere Quellen werden nicht exportiert.
Aufruf: python3 scripts/export_hub.py [--land CA,MX]"""
import argparse
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
BASIS = os.path.dirname(HIER)
sys.path.insert(0, BASIS)
from app import rights  # noqa: E402

ROOT = os.path.dirname(BASIS)
OUT = os.path.join(ROOT, "data", "americas", "firma")
ORDNER = {"CA": "canada", "MX": "mexico"}


def lade(p, leer=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return leer


def firma_datensatz(f, issuer, security, land):
    """Hub-Datensatz mit Quellenangabe je Feld; rights.filtern entfernt alles ohne Freigabe."""
    roh = dict(f)
    roh.update({"isin": security.get("isin") if security else None, "lei": issuer.get("lei"), "land": land, "quelle": "SEC",
                "human_review": "pending", "verified": False, "cik": issuer.get("cik")})
    q = {k: ["sec_edgar"] for k in roh}
    q["isin"] = security.get("quellen") or ["gleif"] if security and security.get("isin") else ["sec_edgar"]
    q["lei"] = ["gleif"]
    for k in ("land", "quelle", "human_review", "verified"):
        q[k] = ["sec_edgar"]
    roh["_quellen"] = q
    return rights.filtern(roh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--land", default="CA,MX")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    index = lade(os.path.join(OUT, "_index.json"), {}) or {}
    for land in [x.strip() for x in a.land.split(",") if x.strip()]:
        uni = os.path.join(BASIS, "data", "universe", ORDNER[land])
        fund = (lade(os.path.join(BASIS, "data", "fundamentals", f"{ORDNER[land]}_sec.json"), {}) or {}).get("firmen", {})
        liste = lade(os.path.join(uni, "sec_liste.json"), {}) or {}
        iss = {i["cik"]: i for i in lade(os.path.join(uni, "issuers.json"), []) or []}
        secs = {s["issuer_id"]: s for s in lade(os.path.join(uni, "securities.json"), []) or []}
        # alte Dateien dieses Landes entfernen (Index kennt das Land)
        for t, v in list(index.items()):
            if v[2] == land:
                p = os.path.join(OUT, f"{t}.json")
                if os.path.exists(p):
                    os.remove(p)
                del index[t]
        n = 0
        for t, f in sorted(fund.items()):
            cik = (liste.get(t) or [None])[0]
            i = iss.get(cik)
            if not i:
                continue
            d = firma_datensatz(f, i, secs.get(i["issuer_id"]), land)
            json.dump(d, open(os.path.join(OUT, f"{t}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            index[t] = [d.get("n"), d.get("isin"), land, d.get("gj")]
            n += 1
        print(f"{land}: {n} Firmen mit SEC-Jahreszahlen exportiert, davon mit ISIN {sum(1 for v in index.values() if v[2] == land and v[1])}")
    # Altlast: Kanada-Dateien aus dem BlackRock-Proxy (Kuerzel *.TO) entfernen
    for fn in os.listdir(OUT):
        if fn.endswith(".TO.json"):
            os.remove(os.path.join(OUT, fn))
            index.pop(fn[:-5], None)
    json.dump(dict(sorted(index.items())), open(os.path.join(OUT, "_index.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
