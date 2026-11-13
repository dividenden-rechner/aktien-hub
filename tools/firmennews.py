#!/usr/bin/env python3
"""Firmen-Nachrichten fuer den Hub: je Firma eine Datei data/firmennews/<HUB>.json.
Quelle: Google-News-RSS mit deutscher Ausgabe (hl=de, gl=DE). Nur Meldungen aus deutschsprachigen Quellen,
damit keine englischen Titel auftauchen. Keine Uebersetzung, keine KI, also keine Token-Kosten.
Universum: die 100 groessten US-Werte und die deutschen Werte aus data/kennzahlen.json.
Aufruf: python3 tools/firmennews.py [--nur KO,SAP.DE]"""
import json, os, sys, time, argparse, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KENN = os.path.join(ROOT, "data", "kennzahlen.json")
OUT = os.path.join(ROOT, "data", "firmennews")
UA = "Mozilla/5.0 (compatible; DividendenRechnerNewsBot/1.0; +https://www.dividenden-rechner.de)"
TAGE = 14        # nur Meldungen der letzten 14 Tage
MAX = 8          # hoechstens so viele je Firma
PAUSE = 2        # Sekunden zwischen Abrufen

# Deutschsprachige Quellen (Domain-Teil oder Name im Google-News-Quellfeld)
DE_QUELLEN = ["handelsblatt", "faz.net", "boerse.de", "finanzen.net", "finanzen.ch", "aktionaer", "wiwo", "manager-magazin",
              "onvista", "boerse-online", "boersenmedien", "spiegel", "zeit.de", "sueddeutsche", "tagesschau", "welt.de",
              "focus", "n-tv", "stern", "dpa", "heise", "ariva", "deraktionaer", "boerse-frankfurt", "ad-hoc-news", "fool.de",
              "comdirect", "dpa-afx", "bloomberg.de", "nzz", "srf", "kleinezeitung", "derstandard", "finanzmarktwelt", "wallstreet-online"]

def universum():
    k = json.load(open(KENN))["werte"]
    us = sorted([(h, v) for h, v in k.items() if v.get("land") == "US"], key=lambda x: -(x[1].get("boersenwert_usd") or 0))[:100]
    de = [(h, v) for h, v in k.items() if v.get("land") == "DE"]
    return [(h, v.get("name") or h) for h, v in us + de]

def suche(name):
    q = f'"{name}" Aktie'
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "de", "gl": "DE", "ceid": "DE:de"})
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25).read()
    return ET.fromstring(raw)

def deutsch(quelle, link):
    s = (quelle or "").lower() + " " + (link or "").lower()
    return any(d in s for d in DE_QUELLEN)

def sammeln(name):
    root = suche(name)
    grenze = datetime.now(timezone.utc) - timedelta(days=TAGE)
    out, gesehen = [], set()
    for it in root.iter("item"):
        titel = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        quelle_el = it.find("source")
        quelle = (quelle_el.text or "").strip() if quelle_el is not None else ""
        quelle_url = quelle_el.get("url", "") if quelle_el is not None else ""
        try:
            d = parsedate_to_datetime(it.findtext("pubDate") or "").astimezone(timezone.utc)
        except Exception:
            continue
        if d < grenze or not titel or titel in gesehen: continue
        if not deutsch(quelle, quelle_url or link): continue
        # Google haengt "- Quelle" an den Titel: abschneiden, damit der Titel sauber bleibt
        if quelle and titel.endswith(" - " + quelle): titel = titel[: -len(quelle) - 3]
        gesehen.add(titel)
        out.append({"titel": titel, "quelle": quelle, "link": link, "datum": d.date().isoformat()})
    out.sort(key=lambda x: x["datum"], reverse=True)
    return out[:MAX]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--nur", default=""); a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    liste = universum()
    if a.nur:
        wahl = set(a.nur.split(",")); liste = [x for x in liste if x[0] in wahl]
    heute = datetime.now(timezone.utc).date().isoformat()
    for i, (hub, name) in enumerate(liste):
        try:
            treffer = sammeln(name)
        except Exception as e:
            print("FEHLER", hub, e); continue
        json.dump({"hub": hub, "name": name, "stand": heute, "quelle": "Google News (deutschsprachige Quellen)",
                   "meldungen": treffer}, open(os.path.join(OUT, hub + ".json"), "w"), ensure_ascii=False, indent=1)
        print(hub, len(treffer), "Meldungen")
        if i < len(liste) - 1: time.sleep(PAUSE)

if __name__ == "__main__":
    main()
