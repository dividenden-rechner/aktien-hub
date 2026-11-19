#!/usr/bin/env python3
"""Kanada-Universum: Mitglieder des S&P/TSX Composite (Proxy: iShares XIC-Bestand mit Stichtag) -> getrennte Tabellen
issuer / security / listing / index_membership / review in data/universe/canada/. ISIN und LEI aus ESMA FIRDS
(amtliches EU-Register), nur bei eindeutigem Treffer; sonst leer mit Prüfeintrag. Nichts wird als verified markiert.
Aufruf: python3 scripts/build_canada.py [--xic DATEI] [--firds-cache DATEI.json]"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
from app import canada, firds  # noqa: E402
from app.common import get, norm_tokens  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HIER))
OUT = os.path.join(os.path.dirname(HIER), "data", "universe", "canada")


def de_gehandelt():
    try:
        return set(json.load(open(os.path.join(ROOT, "data/kurse/xetra-letzter.json")))["k"])
    except Exception:
        return set()


def schreibe(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")


def bauen(stichtag, mitglieder, verworfen, fd, de, abruf):
    quelle_idx = {"quelle": "iShares S&P/TSX Capped Composite Index ETF (XIC), veröffentlichte Bestandsliste",
                  "url": canada.XIC_URL, "art": "Proxy für die lizenzpflichtige S&P-Mitgliederliste", "stichtag": stichtag,
                  "abgerufen": abruf}
    issuers, securities, listings, mitgl, review = {}, {}, [], [], []
    for m in mitglieder:
        isin, lei, methode, kand = firds.zuordnen(m["name"], m["ticker"], fd, de)
        issuer_id = f"LEI:{lei}" if lei else "NAME:CA:" + "-".join(sorted(norm_tokens(m["name"]))) 
        iss = issuers.setdefault(issuer_id, {"issuer_id": issuer_id, "name": m["name"], "lei": lei,
                                             "country_laut_etf": m.get("sitz_laut_etf"), "sector_laut_etf": m.get("sektor") or None,
                                             "verified": False, "human_review": "pending", "quellen": ["XIC"] + (["ESMA FIRDS"] if lei else [])})
        sec_id = isin or f"OHNE_ISIN:{m['ticker']}@{canada.MIC_TSX}"
        securities[sec_id] = {"security_id": sec_id, "isin": isin, "issuer_id": issuer_id, "name": m["name"],
                              "klasse": canada.klasse_aus(m["ticker"], m["name"]), "art": canada.wertpapierart(m["ticker"], m["name"]),
                              "isin_methode": methode, "isin_kandidaten": kand or None,
                              "firds_name": fd[isin]["name"] if isin else None, "verified": False, "human_review": "pending"}
        listings.append({"listing_id": f"{m['ticker']}@{canada.MIC_TSX}", "ticker": m["ticker"], "mic": canada.MIC_TSX,
                         "boerse": "Toronto Stock Exchange", "waehrung": m.get("waehrung"), "security_id": sec_id, "isin": isin,
                         "hub_kuerzel": canada.hub_kuerzel(m["ticker"]), "status": "aktiv_laut_indexbestand",
                         "quelle": "XIC", "abgerufen": abruf, "verified": False, "human_review": "pending"})
        mitgl.append({"index_id": canada.INDEX_ID, "index": canada.INDEX_NAME, "listing_id": f"{m['ticker']}@{canada.MIC_TSX}",
                      "isin": isin, "gueltig_ab": None, "stand": stichtag, "quelle": "XIC", "human_review": "pending"})
        if not isin:
            review.append({"listing_id": f"{m['ticker']}@{canada.MIC_TSX}", "name": m["name"], "grund": methode,
                           "kandidaten": kand or None, "aktion": "ISIN aus amtlicher Quelle bestätigen"})
    for v in verworfen:
        review.append({"listing_id": v["ticker"], "name": v["name"], "grund": v["grund"], "aktion": "nicht als Indexmitglied gezählt"})
    return list(issuers.values()), list(securities.values()), listings, mitgl, review, quelle_idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xic", help="lokale XIC-CSV statt Abruf")
    ap.add_argument("--firds-cache", help="FIRDS-Auszug als JSON (Ergebnis eines früheren Abrufs)")
    a = ap.parse_args()
    abruf = datetime.now(timezone.utc).isoformat(timespec="seconds")
    text = open(a.xic, encoding="utf-8").read() if a.xic else get(canada.XIC_URL).decode("utf-8")
    stichtag, mitglieder, verworfen = canada.parse_xic(text)
    if a.firds_cache and os.path.exists(a.firds_cache):
        fd = {k: dict(v, mics=set(v["mics"])) for k, v in json.load(open(a.firds_cache)).items()}
    else:
        fd = firds.laden(("CA", "BM"))
        if a.firds_cache:
            json.dump({k: dict(v, mics=sorted(m for m in v["mics"] if m)) for k, v in fd.items()}, open(a.firds_cache, "w"))
    iss, secs, lst, mitgl, review, qi = bauen(stichtag, mitglieder, verworfen, fd, de_gehandelt(), abruf)
    schreibe("issuers.json", iss)
    schreibe("securities.json", secs)
    schreibe("listings.json", lst)
    schreibe("index_memberships.json", {"index": qi, "mitglieder": mitgl})
    schreibe("review.json", review)
    mit_isin = sum(1 for s in secs if s["isin"])
    summary = {"erstellt": abruf, "index": qi, "mitglieder": len(mitgl), "emittenten": len(iss), "wertpapiere": len(secs),
               "notierungen": len(lst), "mit_isin": mit_isin, "ohne_isin": len(secs) - mit_isin,
               "mit_lei": sum(1 for i in iss if i["lei"]), "verworfen": verworfen,
               "arten": {k: sum(1 for s in secs if s["art"] == k) for k in sorted({s["art"] for s in secs})}}
    schreibe("summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
