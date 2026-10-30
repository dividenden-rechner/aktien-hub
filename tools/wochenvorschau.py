#!/usr/bin/env python3
"""Wochenvorschau: Wer meldet wann (Earnings, aus FMP) plus Konjunkturtermine, Zentralbanken und Zinsausblick (Websuche mit Quellen).
Schreibt einen Entwurf (draft: true) nach content/magazin; draft_prs.py legt danach den Pull Request zur Freigabe an.

Aufruf:  python3 tools/wochenvorschau.py [--von 2026-11-02]
Die Earnings-Tabellen stammen direkt aus den Daten (keine Zahlen vom Modell), die Textteile aus der Recherche."""
import argparse, json, os, re, sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir_agent as ia
import artikel as A

TAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
MON = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
SCHEMA = {"type": "OBJECT", "required": ["title", "description", "slug", "intro_md", "makro_md", "zins_md", "quellen"], "properties": {
    "title": {"type": "STRING"}, "description": {"type": "STRING"}, "slug": {"type": "STRING"}, "intro_md": {"type": "STRING"},
    "makro_md": {"type": "STRING"}, "zins_md": {"type": "STRING"}, "quellen": {"type": "ARRAY", "items": {"type": "STRING"}}}}


def de(d): return f"{d.day}. {MON[d.month - 1]}"


def monday(today, von=None):
    if von: return datetime.strptime(von, "%Y-%m-%d").date()
    return today if today.weekday() == 0 else today + timedelta(days=7 - today.weekday())


def load_names():
    u = json.load(open(os.path.join(ia.ROOT, "data", "universe.json"), encoding="utf-8"))["firmen"]
    names = {f["sym"]: f["name"] for f in u}
    wl = json.load(open(os.path.join(ia.ROOT, "data", "ir-watchlist.json"), encoding="utf-8"))["tickers"]
    return names, set(wl)


def zahl(v, d=2, unit=""):
    if v in (None, "", 0): return "–"
    s = f"{float(v):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + unit


def umsatz(v):
    if not v: return "–"
    v = float(v)
    return (f"{v / 1e9:.1f}".replace(".", ",") + " Mrd.") if v >= 1e9 else (f"{v / 1e6:.0f} Mio.")


def earnings(mon, names, wl):
    """Earnings der Woche aus FMP, nur Firmen aus S&P 500 und Watchlist, je Tag die wichtigsten (Watchlist zuerst, dann nach Umsatzschaetzung)."""
    rows = ia.fmp_get("earnings-calendar", **{"from": mon.isoformat(), "to": (mon + timedelta(days=4)).isoformat()}) or []
    out = {}
    for r in rows:
        sym = (r.get("symbol") or "").upper()
        if sym not in names and sym not in wl: continue
        out.setdefault(r.get("date"), {})[sym] = r
    return out


def tabellen(mon, names, wl, cal, top=8):
    h, total = "", 0
    for i in range(5):
        d = mon + timedelta(days=i); lst = list((cal.get(d.isoformat()) or {}).values())
        if not lst: continue
        total += len(lst)
        lst.sort(key=lambda r: (0 if r["symbol"] in wl else 1, -float(r.get("revenueEstimated") or 0)))
        h += f"\n### {TAGE[i]}, {de(d)}\n\n| Unternehmen | Kürzel | Gewinn je Aktie (Erwartung) | Umsatz (Erwartung) |\n|---|---|---|---|\n"
        for r in lst[:top]:
            h += f"| {names.get(r['symbol'], r['symbol'])} | ${r['symbol']} | {zahl(r.get('epsEstimated'))} | {umsatz(r.get('revenueEstimated'))} |\n"
        if len(lst) > top: h += f"\nInsgesamt melden an diesem Tag {len(lst)} Unternehmen aus dem S&P 500 und unserer Beobachtungsliste.\n"
    return h, total


def recherche(mon, key):
    fr = mon + timedelta(days=4)
    p = (f"Recherchiere mit der Websuche für die Börsenwoche vom {de(mon)} bis {de(fr)} {fr.year}: "
         "1. Alle wichtigen Konjunktur- und Zentralbanktermine mit Datum (Sitzungen von Fed, EZB, Bank of England, Bank of Japan; US-Arbeitsmarktbericht, Inflationsdaten, BIP, Einkaufsmanagerindizes, deutsche und europäische Daten). "
         "2. Aktuelle Leitzinsen von Fed, EZB, Bank of England und Bank of Japan mit Stand. "
         "3. Was Terminmärkte, Banken und Analysten für die nächste Sitzung von Fed und EZB erwarten (Erhöhung, Senkung, unverändert, mit Wahrscheinlichkeiten oder Prognosen der großen Banken), mit Datum der Aussage und wer sie macht. "
         "4. Die wichtigsten Unternehmen und Themen, auf die der Markt in dieser Woche schaut. "
         "Gib knappe Stichpunkte mit konkreten Zahlen, Datum und Quellenname. Erfinde nichts, lasse Unbelegtes weg.")
    return ia.ground(p, key)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--von", default=""); a = ap.parse_args()
    now = datetime.now(ZoneInfo("Europe/Berlin")); mon = monday(now.date(), a.von or None)
    names, wl = load_names(); key = ia.api_key()
    cal = earnings(mon, names, wl)
    tab, n = tabellen(mon, names, wl, cal)
    print(f"Woche ab {mon}: {n} Earnings aus Universum/Watchlist")
    text, srcs = recherche(mon, key)
    if not text:
        ia.fail("Keine Recherche moeglich (Websuche nicht verfuegbar), Wochenvorschau nicht erstellt.")
    prompt = (ia.read_prompt("wochenvorschau_prompt.md") + f"\n\nWOCHE: {de(mon)} bis {de(mon + timedelta(days=4))} {mon.year}\nHEUTE: {now.strftime('%d.%m.%Y')}"
              + f"\n\nRECHERCHE:\n{text}\n\nQUELLEN DER RECHERCHE: " + "; ".join(t for t, _ in srcs))
    out = ia._generate([{"text": prompt}], SCHEMA, key)
    slug = re.sub(r"[^a-z0-9]+", "-", out["slug"].lower()).strip("-") or f"wochenvorschau-{mon.isoformat()}"
    if A.find(slug): ia.fail(f"Es gibt schon einen Artikel '{slug}'.")
    q = lambda t: '"' + str(t).replace('"', "'") + '"'
    head = ["---", f"title: {q(out['title'])}", f"description: {q(out['description'])}", f"date: {now.strftime('%Y-%m-%d %H:%M')}",
            f'author: "{ia.CFG["author"]}"', f'author_bio: "{ia.CFG["author_bio"]}"', "category: Ausblick", "kein_logo: ja", "draft: true"]
    try:        # Titelfoto von Unsplash (Auswahl nach Kalenderwoche, damit es wechselt)
        cands = ia.unsplash_candidates(["stock exchange trading floor", "wall street new york financial district", "stock market screens traders", "city skyline financial district"])
        if cands:
            ph = cands[mon.isocalendar()[1] % len(cands)]
            rel = ia.save_photo(ph, slug)
            head += [f"image: {rel}", f"image_alt: {q('Foto zur Börsenwoche: ' + (ph.get('desc') or 'Finanzviertel'))}", f"image_credit: {q(ia.photo_credit(ph))}",
                     f"image_source: {ph['page']}", f"image_artist_url: {ph.get('artist_url') or ''}"]
    except Exception as e:
        print("Foto uebersprungen:", e)
    head.append("---")
    body = ("<!-- PRÜFEN: Wochenvorschau automatisch erstellt. Earnings-Tabellen direkt aus FMP (Erwartungen laut Datenanbieter), Texte aus Recherche mit Websuche. "
            "Termine und Zinserwartungen bitte kurz gegenprüfen, dann 'draft: true' löschen. -->\n\n"
            + out["intro_md"].strip() + "\n\n## Wer meldet wann\n"
            + (tab if tab else "\nFür diese Woche liegen noch keine Termine großer Unternehmen vor.\n")
            + "\n*Erwartungen laut Datenanbieter Financial Modeling Prep, Termine können sich verschieben.*\n\n"
            + "## Konjunktur und Zentralbanken\n\n" + out["makro_md"].strip() + "\n\n" + out["zins_md"].strip() + "\n\n"
            + "## Quellen\n\n" + "\n".join("- " + s for s in out["quellen"]) + "\n\n"
            + "*Dieser Beitrag fasst Informationen aus den genannten Quellen in eigenen Worten zusammen. Prognosen sind keine Gewissheiten. Keine Anlageberatung.*\n")
    stamp = now.strftime("%Y-%m-%d-%H%M"); path = A.path_for(stamp, slug)
    open(path, "w", encoding="utf-8").write("\n".join(head) + "\n" + body)
    print("Entwurf:", path)


if __name__ == "__main__":
    main()
