#!/usr/bin/env python3
"""SEC-Jahreszahlen der kanadischen Indexmitglieder -> eine Datei je Firma fuer Hub und kennzahlen.py:
data/americas/firma/<HUB-KUERZEL>.json (Format wie data/sec/fundamentals.json) und data/americas/firma/_index.json.
ISIN nur, wenn im Universum eindeutig zugeordnet (fuer den deutschen Kurs). human_review: pending."""
import json
import os

HIER = os.path.dirname(os.path.abspath(__file__))
BASIS = os.path.dirname(HIER)
ROOT = os.path.dirname(BASIS)
UNI = os.path.join(BASIS, "data", "universe", "canada")
OUT = os.path.join(ROOT, "data", "americas", "firma")


def main():
    fund = json.load(open(os.path.join(BASIS, "data", "fundamentals", "canada_sec.json"), encoding="utf-8"))["firmen"]
    listings = {l["hub_kuerzel"]: l for l in json.load(open(os.path.join(UNI, "listings.json"), encoding="utf-8"))}
    secs = {s["security_id"]: s for s in json.load(open(os.path.join(UNI, "securities.json"), encoding="utf-8"))}
    os.makedirs(OUT, exist_ok=True)
    alt = {f[:-5] for f in os.listdir(OUT) if f.endswith(".json") and not f.startswith("_")}
    index = {}
    for t, f in sorted(fund.items()):
        l = listings.get(t)
        if not l:
            continue
        s = secs[l["security_id"]]
        f = dict(f, isin=s["isin"], land="CA", quelle="SEC", boerse_heimat="TSX", tsx_kuerzel=l["ticker"],
                 wertpapierart=s["art"], human_review="pending", verified=False)
        json.dump(f, open(os.path.join(OUT, f"{t}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        alt.discard(t)
        index[t] = [f.get("n"), s["isin"], "CA", f.get("gj")]
    for t in alt:
        os.remove(os.path.join(OUT, f"{t}.json"))
    json.dump(index, open(os.path.join(OUT, "_index.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"Hub: {len(index)} kanadische Firmen mit SEC-Jahreszahlen, davon mit ISIN {sum(1 for v in index.values() if v[1])}")


if __name__ == "__main__":
    main()
