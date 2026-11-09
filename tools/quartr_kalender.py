#!/usr/bin/env python3
"""Quartr-Kalender ("Followed companies", iCal-Feed) lesen und die Termine der naechsten Wochen ablegen.

Der Feed-Link steht im GitHub-Secret QUARTR_KALENDER_URL (nie im Repository, nie im Log).
Schreibt NUR data/quartr-termine.json (rohe, gefilterte Termine) und gibt eine Auswertung aus.
data/termine-app.json (Earnings-Kalender) wird hier nicht angefasst.

Aufruf:
  QUARTR_KALENDER_URL=... python3 tools/quartr_kalender.py [--tage 28] [--tage-cmd 60]
  python3 tools/quartr_kalender.py --datei feed.ics     # Test mit lokaler Datei
"""
import argparse, json, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "quartr-termine.json")
BERLIN = ZoneInfo("Europe/Berlin")


def holen(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dividenden-rechner-termine/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def entfalten(text):
    """iCal-Zeilen, die mit Leerzeichen/Tab fortgesetzt werden, wieder zusammenfuegen."""
    return re.sub(r"\r?\n[ \t]", "", text).replace("\r\n", "\n")


def unescape(s):
    return s.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def termine(ics):
    out = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", entfalten(ics), flags=re.S):
        f = {}
        for zeile in block.strip().split("\n"):
            if ":" not in zeile:
                continue
            k, v = zeile.split(":", 1)
            f.setdefault(k.split(";")[0].upper(), (k, v))
        def wert(n):
            return unescape(f[n][1]) if n in f else ""
        ds = f.get("DTSTART")
        if not ds:
            continue
        roh = ds[1].strip()
        ganztag = "VALUE=DATE" in ds[0].upper() and len(roh) == 8
        try:
            if ganztag:
                d = datetime.strptime(roh, "%Y%m%d").replace(tzinfo=BERLIN)
            elif roh.endswith("Z"):
                d = datetime.strptime(roh, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(BERLIN)
            else:
                d = datetime.strptime(roh[:15], "%Y%m%dT%H%M%S").replace(tzinfo=BERLIN)
        except ValueError:
            continue
        out.append({"datum": d.strftime("%Y-%m-%d"), "zeit": "" if ganztag else d.strftime("%H:%M"),
                    "titel": wert("SUMMARY"), "beschr": wert("DESCRIPTION")[:300], "url": wert("URL"), "uid": wert("UID")})
    return out


def art(titel):
    """Grobe Einordnung nach dem Titel (Quartr schreibt "Firma - Ereignis"). Reihenfolge ist wichtig."""
    t = titel.split(" - ", 1)[-1].lower()
    if re.search(r"\b(conference|keynote|fireside|meet the management|summit|forum|symposium|congress|webcast|roadshow)\b", t) \
            and not re.search(r"\b(cmd|investor day|analyst day|capital markets day)\b", t):
        return "sonstiges"
    if re.search(r"\b(cmd|capital markets day|investor day|investor & analyst day|investor and analyst day|analyst day)\b", t):
        return "kapitalmarkttag"
    if re.search(r"\b(agm|annual general meeting|hauptversammlung|egm|shareholder meeting)\b", t):
        return "hauptversammlung"
    if re.search(r"\b(trading update|investor update|esg update|business update)\b", t):
        return "update"
    if re.search(r"\b(q&a|media|presentation|call)\b", t):
        return "sonstiges"
    if re.search(r"\b(q[1-4]|h[12]|fy|full[- ]year|half[- ]year|annual results|quarter)\b", t):
        return "zahlen"
    return "unbekannt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tage", type=int, default=28, help="Fenster fuer Zahlen in Tagen")
    ap.add_argument("--tage-cmd", type=int, default=60, help="Fenster fuer Kapitalmarkttage in Tagen")
    ap.add_argument("--datei", help="lokale iCal-Datei statt Secret")
    a = ap.parse_args()
    if a.datei:
        ics = open(a.datei, encoding="utf-8").read()
    else:
        url = os.environ.get("QUARTR_KALENDER_URL", "").strip()
        if not url:
            sys.exit("Das GitHub-Secret QUARTR_KALENDER_URL fehlt.")
        ics = holen(url)
    alle = termine(ics)
    heute = datetime.now(BERLIN).date()
    for t in alle:
        t["art"] = art(t["titel"])
    zaehl = {}
    for t in alle:
        zaehl[t["art"]] = zaehl.get(t["art"], 0) + 1
    print(f"Feed: {len(alle)} Termine, Arten: {zaehl}")
    if alle:
        print("Zeitraum:", min(t['datum'] for t in alle), "bis", max(t['datum'] for t in alle))

    def im_fenster(t):
        d = datetime.strptime(t["datum"], "%Y-%m-%d").date()
        grenze = a.tage_cmd if t["art"] == "kapitalmarkttag" else a.tage
        return heute <= d <= heute + timedelta(days=grenze)

    behalten = sorted((t for t in alle if t["art"] in ("zahlen", "kapitalmarkttag", "unbekannt") and im_fenster(t)),
                      key=lambda t: (t["datum"], t["zeit"], t["titel"]))
    print(f"Im Fenster (Zahlen {a.tage} Tage, Kapitalmarkttage {a.tage_cmd} Tage): {len(behalten)}")
    print("Beispiele (Titel unveraendert, damit die Form sichtbar wird):")
    for t in behalten[:25]:
        print(" ", t["datum"], t["zeit"] or "ganztags", "|", t["art"], "|", t["titel"], "|", (t["beschr"] or "")[:80])
    unb = [t for t in alle if t["art"] == "unbekannt"][:10]
    if unb:
        print("Unbekannte Titel:", [t["titel"] for t in unb])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"stand": datetime.now(BERLIN).strftime("%Y-%m-%d %H:%M"), "quelle": "Quartr Followed companies (iCal)",
               "termine": [{k: v for k, v in t.items() if k not in ("uid",)} for t in behalten]},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
