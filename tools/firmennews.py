#!/usr/bin/env python3
"""Firmen-Nachrichten fuer den Hub: je Firma eine Datei data/firmennews/<HUB>.json.
Quelle: Google News RSS, einmal deutsch (DE) und einmal englisch (US). Nur Quellen aus der Allowlist
(Wirtschaftsmedien), keine Routine-Renditerechner, keine Uebersetzung, keine KI, also keine Token-Kosten.
Universum: die 100 groessten US-Werte und die deutschen Werte aus data/kennzahlen.json.
Aufruf: python3 tools/firmennews.py [--nur KO,SAP.DE]"""
import json, os, re, sys, time, argparse, urllib.request, urllib.parse
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

# Erlaubte Quellen (Teil des Namens oder der Domain, kleingeschrieben)
QUELLEN = ["handelsblatt", "faz", "wiwo", "manager-magazin", "spiegel", "sueddeutsche", "zeit.de", "welt.de", "tagesschau",
           "dpa", "boersen-zeitung", "boersenzeitung", "nzz", "reuters", "bloomberg", "wall street journal", "wsj.com",
           "financial times", "ft.com", "cnbc", "barron", "economist", "new york times", "nytimes", "washington post",
           "associated press", "apnews", "fortune", "forbes", "the guardian", "bbc", "südwest", "suedwest", "handelszeitung",
           "finanztreff", "börse online", "boerse-online"]
# Keine Renditerechner, Chartsignale, Kaufempfehlungen oder Video-/Forenbeitraege
AUSSCHLUSS = re.compile(
    r"Investition|hätte .*(abgeworfen|gewonnen|verdient)|So viel|Chartsignal|Chartanalyse|Expertenmeinung|Trading-Chance|"
    r"Aktie kaufen|Kaufen oder|Kaufempfehlung|Top-Aktie|Aktien-Tipp|Börsenbrief|Kursziel|Hot Stock|stock to buy|should you buy|"
    r"buy now|Motley Fool|YouTube|Podcast|Video|Anleger aufgepasst|Dividendenkönig|\bwarum\b.*Aktie|"
    r"Handelsstart|Handelsende|Zweiter Tag|Tag ohne|Tag mit|Im Plus|Im Minus|Im Fokus|Kurs-Check|Börsentag|Tagesgewinner|Tagesverlierer|"
    r"Stock Price|stock price|Shares of|Stock Quote|Pre-Market|premarket|Ticker|Analystenmeinung",
    re.I)

def universum():
    k = json.load(open(KENN))["werte"]
    us = sorted([(h, v) for h, v in k.items() if v.get("land") == "US"], key=lambda x: -(x[1].get("boersenwert_usd") or 0))[:100]
    de = [(h, v) for h, v in k.items() if v.get("land") == "DE"]
    return [(h, v.get("name") or h) for h, v in us + de]

def suche(name, sprache):
    if sprache == "de":
        q, par = f'"{name}" Unternehmen', {"hl": "de", "gl": "DE", "ceid": "DE:de"}
    else:
        q, par = f'"{name}"', {"hl": "en-US", "gl": "US", "ceid": "US:en"}
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, **par})
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25).read()
    return ET.fromstring(raw)

def erlaubt(quelle, quelle_url):
    s = ((quelle or "") + " " + (quelle_url or "")).lower()
    return any(q in s for q in QUELLEN)

def sammeln(name):
    out = []
    for sprache in ("de", "en"):
        out += _sammeln(name, sprache)
    out.sort(key=lambda x: x["datum"], reverse=True)
    seen, res = set(), []
    for m in out:
        k = m["titel"].lower()[:60]
        if k in seen: continue
        seen.add(k); res.append(m)
    return res[:MAX]

VERWORFEN = {}

def _sammeln(name, sprache):
    root = suche(name, sprache)
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
        if not erlaubt(quelle, quelle_url):
            VERWORFEN[quelle or "?"] = VERWORFEN.get(quelle or "?", 0) + 1; continue
        if AUSSCHLUSS.search(titel):
            VERWORFEN["Filter"] = VERWORFEN.get("Filter", 0) + 1; continue
        # Google haengt "- Quelle" an den Titel: abschneiden, damit der Titel sauber bleibt
        if quelle and titel.endswith(" - " + quelle): titel = titel[: -len(quelle) - 3]
        gesehen.add(titel)
        out.append({"titel": titel, "quelle": quelle, "link": link, "datum": d.date().isoformat(), "sprache": sprache})
    return out

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
        json.dump({"hub": hub, "name": name, "stand": heute, "quelle": "Google News (Wirtschaftsmedien, deutsch und englisch)",
                   "meldungen": treffer}, open(os.path.join(OUT, hub + ".json"), "w"), ensure_ascii=False, indent=1)
        top = sorted(VERWORFEN.items(), key=lambda x: -x[1])[:8]
        print(hub, len(treffer), "Meldungen; verworfen:", top)
        VERWORFEN.clear()
        if i < len(liste) - 1: time.sleep(PAUSE)

if __name__ == "__main__":
    main()
