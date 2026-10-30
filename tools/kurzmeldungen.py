#!/usr/bin/env python3
"""Kurzmeldungs-Agent: Pressemitteilungen grosser Unternehmen -> kurze News (Markdown, typ: kurz).

Quellen
  1. SEC (USA, S&P 500): 8-K-Meldungen mit Pressemitteilung (Anlage EX-99). Die Liste der Unternehmen
     steht in data/universe.json und wird mit --update-universe aus der S&P-500-Liste erneuert.
  2. Unternehmens-Feeds (alle anderen Titel, etwa Europa und Asien): Eintraege aus data/news.json
     (siehe tools/fetch_news.py und data/feeds.json).

Ablauf: Kandidaten sammeln -> Gemini entscheidet, ob die Meldung fuer Anleger relevant ist, und schreibt
3 bis 5 Saetze -> Zahlen werden gegen den Originaltext geprueft -> Datei in content/magazin/.
Ist eine Zahl nicht im Original zu finden, wird die Meldung als Entwurf (draft: true) abgelegt.

Aufruf:
  python3 tools/kurzmeldungen.py --update-universe     # S&P-500-Liste holen (einmal pro Woche reicht)
  python3 tools/kurzmeldungen.py [--max 30] [--dry]    # Meldungen holen und schreiben
Test ohne Netz: KURZ_MOCK=antwort.json und --offline kandidaten.json
"""
import argparse, csv, io, json, os, re, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir_agent as ia

ROOT = ia.ROOT
UNIVERSE = os.path.join(ROOT, "data", "universe.json")
STATE = os.path.join(ROOT, "data", "kurz-state.json")
NEWS = os.path.join(ROOT, "data", "news.json")
OUT_DIR = os.path.join(ROOT, "content", "magazin")
CONSTITUENTS = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
WATCHLIST = os.path.join(ROOT, "data", "ir-watchlist.json")
MAX_LONG = int(os.environ.get("MAX_LONG", "4"))   # hoechstens so viele lange Artikel (IR-Agent) pro Lauf
# Auslaendische Konzerne mit US-Notierung (ADR): melden Pressemitteilungen als Formular 6-K bei der SEC.
# Kuerzel an der SEC -> Kuerzel in data/feeds.json (damit dieselbe Meldung nicht ueber zwei Wege kommt)
ADR = {"NVO": "NOVO-B.CO", "ASML": "ASML.AS", "SAP": "SAP.DE", "SHEL": "SHEL.L", "UL": "ULVR.L", "HSBC": "HSBA.L", "NVS": "NOVN.SW",
       "AZN": "AZN.L", "TM": "7203.T", "SONY": "6758.T", "TSM": "TSM", "BABA": "9988.HK", "BP": "BP.L", "SAN": "SAN.MC", "UBS": "UBSG.SW",
       "GSK": "GSK.L", "SNY": "SAN.PA", "TTE": "TTE.PA", "DEO": "DGE.L", "BTI": "BATS.L", "RIO": "RIO.L", "BHP": "BHP.AX", "HMC": "7267.T",
       "ING": "INGA.AS", "PHG": "PHIA.AS", "ERIC": "ERIC-B.ST", "NOK": "NOKIA.HE", "STLA": "STLAM.MI", "E": "ENI.MI", "BCS": "BARC.L",
       "LYG": "LLOY.L", "DB": "DBK.DE", "MUFG": "8306.T", "SMFG": "8316.T", "TEF": "TEF.MC", "BBVA": "BBVA.MC", "ABBNY": "ABBN.SW", "VOD": "VOD.L"}
CATEGORIES = ["Dividende", "Quartalszahlen", "Ausblick", "Aktienrückkauf", "Übernahme", "Management", "Geschäft", "Recht & Regulierung", "Sonstige Meldung"]
SKIP_ITEMS = {"5.07", "5.03", "9.01", "3.03", "2.04", "5.08"}   # Abstimmungsergebnisse, Satzung, nur Anlagen usw.
MAX_AGE_H = 40
SCHEMA = {
    "type": "OBJECT",
    "required": ["relevant", "reason"],
    "properties": {
        "relevant": {"type": "BOOLEAN", "description": "Ist die Meldung fuer Privatanleger in Dividendenwerte relevant?"},
        "reason": {"type": "STRING", "description": "Kurze Begruendung, warum relevant oder nicht"},
        "category": {"type": "STRING", "enum": CATEGORIES},
        "title": {"type": "STRING", "description": "Sachlicher deutscher Titel, hoechstens 90 Zeichen, Kernzahl nennen"},
        "description": {"type": "STRING", "description": "Ein bis zwei Saetze, hoechstens 200 Zeichen"},
        "body_markdown": {"type": "STRING", "description": "Drei bis fuenf Saetze Fliesstext auf Deutsch, hoechstens 120 Woerter"},
        "slug": {"type": "STRING", "description": "kurze URL-Kennung in Kleinbuchstaben, z. B. altria-dividende-q4-2026"},
        "foto_person": {"type": "STRING", "description": "Voller Name einer Person, die im Mittelpunkt der Meldung steht (neuer CEO, neuer Finanzchef, Ruecktritt), sonst leer"},
        "termine": {"type": "ARRAY", "description": "Termine, die woertlich in der Meldung genannt werden (auch wenn die Meldung sonst nicht relevant ist); leer, wenn keine",
                    "items": {"type": "OBJECT", "required": ["art", "datum"], "properties": {
                        "art": {"type": "STRING", "enum": ["ergebnis", "dividende_exdatum", "dividende_zahltag"], "description": "ergebnis = Veroeffentlichung von Quartals- oder Jahreszahlen"},
                        "datum": {"type": "STRING", "description": "YYYY-MM-DD, nur wenn Tag, Monat und Jahr im Text stehen"},
                        "betrag": {"type": "STRING", "description": "Dividende je Aktie als Zahl wie im Text (zum Beispiel 1.02), sonst leer"},
                        "waehrung": {"type": "STRING", "description": "Waehrungskuerzel (USD, JPY, HKD ...), sonst leer"}}}},
    },
}
CTX_SCHEMA = {
    "type": "OBJECT",
    "required": ["einordnung_titel", "einordnung_markdown"],
    "properties": {
        "einordnung_titel": {"type": "STRING", "description": "Kurze, konkrete Zwischenueberschrift (3 bis 8 Woerter), die den Kern der Einordnung benennt; nicht 'Einordnung'"},
        "einordnung_markdown": {"type": "STRING", "description": "Ein bis zwei Absaetze, zusammen 70 bis 140 Woerter"},
    },
}
CTX_PROMPT = """Schreibe die Einordnung zu dieser Kurzmeldung fuer ein deutsches Finanzportal fuer Privatanleger.
Sie soll zeigen, wie diese Meldung zur AKTUELLEN, INDIVIDUELLEN Lage genau dieses Unternehmens passt. Es ist keine Checkliste und kein Schema:
Entscheide anhand von PRESSEMITTEILUNG und HINTERGRUND, was fuer dieses Unternehmen JETZT wirklich zaehlt, und schreibe darueber.
Moegliche Blickwinkel, von denen du nur die ein bis drei nimmst, die hier den Unterschied machen: Stellung gegenueber den konkreten Wettbewerbern
oder der Branche in dieser Phase; die Entwicklung der letzten Quartale und Jahre (Trend, Wendepunkt oder Ausreisser); die Themen, die das Unternehmen
gerade bewegen (Strategie, Fuehrung, Rechtsstreit, Regulierung, Zoelle, Uebernahmen, Produktzyklus); die Finanzlage (Schulden, Cashflow, Dividendendeckung).
Regeln:
- Beginne mit dem Punkt, der die Lage dieses Unternehmens heute am besten beschreibt, nicht mit Allgemeinplaetzen.
- Die Zwischenueberschrift benennt diese konkrete Lage (Firma, Thema, Zahl oder Konflikt), nicht das Wort 'Einordnung' und keine Formel,
  die auf jedes Unternehmen passen wuerde. Uebernimm keine Beispiele aus diesem Auftrag.
- Nutze nur Fakten aus PRESSEMITTEILUNG und HINTERGRUND. Zahlen aus dem HINTERGRUND mit Zeitbezug und als Einordnung
  ('im Vorjahr', 'laut Medienberichten'), wenige Zahlen. Nichts erfinden, keine Kaufempfehlung, keine Kursprognose.
- Gibt der HINTERGRUND wenig her, schreibe kurz und bleibe beim Belegten. Sachlich, Kritisches nennen. Deutsch."""
PROMPT = """Du schreibst Kurzmeldungen fuer ein deutsches Finanzportal fuer Privatanleger (Schwerpunkt Dividenden).
Unten steht eine Pressemitteilung. Entscheide zuerst, ob sie fuer Anleger relevant ist.

RELEVANT: Dividendenbeschluss oder -aenderung, Quartals- und Jahreszahlen, Prognoseaenderung, Aktienrueckkauf, Uebernahmen und
Verkaeufe, Wechsel in der Fuehrung, grosse Auftraege oder Vertraege, wesentliche Rechtsfragen, Kapitalmassnahmen.
NICHT RELEVANT: Produktwerbung, Veranstaltungs- und Webinar-Einladungen, Nachhaltigkeits- und Imagemeldungen, Preise und Auszeichnungen,
Routine (Hauptversammlungs-Einladung, Abstimmungsergebnisse, Satzungsaenderung, kleine Anleiheemissionen), Meldungen ohne Zahlen oder Folgen.

Wenn relevant, schreibe:
- Titel, Beschreibung und 3 bis 5 Saetze Text auf Deutsch, sachlich und ohne Wertung, Kaufempfehlung oder Prognose.
- Nenne nur Fakten und Zahlen, die woertlich im Text stehen. Zahlen exakt uebernehmen, Waehrung und Zeitraum nennen
  (zum Beispiel '1,02 US-Dollar je Aktie', 'im dritten Quartal 2026'). Nichts hinzuerfinden, nichts umrechnen.
- Erster Satz: Was ist passiert? Danach die wichtigsten Zahlen, zuletzt ein Satz mit dem naechsten Termin (zum Beispiel Zahltag), falls genannt.
- Keine woertlichen Zitate, keine Ueberschriften, keine Aufzaehlungen.
- Der Firmenname steht im Titel.
- termine: Veroeffentlichungstermine von Zahlen, Ex-Dividenden-Tage und Zahltage, die mit Tag, Monat und Jahr im Text stehen (auch bei nicht relevanten Meldungen). Nichts schaetzen.
- foto_person: nur setzen, wenn eine einzelne Person im Mittelpunkt steht (zum Beispiel Ernennung eines neuen Vorstandschefs), sonst leer."""

UA_HDR = ia.UA


def log(*a):
    print(*a, flush=True)


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


# ---------------------------------------------------------------- Unternehmensliste
def update_universe():
    raw = ia.http(CONSTITUENTS)
    rows = list(csv.DictReader(io.StringIO(raw)))
    out = []
    for r in rows:
        try:
            cik = int(r["CIK"])
        except Exception:
            continue
        out.append({"sym": r["Symbol"].strip().replace(".", "-"), "name": r["Security"].strip(), "cik": cik, "sektor": r.get("GICS Sector", "")})
    try:
        tick = json.loads(ia.http("https://www.sec.gov/files/company_tickers.json", ua=UA_HDR))
        by = {v["ticker"].upper(): v for v in tick.values()}
        for t in ADR:
            v = by.get(t)
            if v:
                out.append({"sym": t, "name": v["title"].title() if v["title"].isupper() else v["title"], "cik": int(v["cik_str"]), "sektor": "", "fpi": True})
            else:
                log(f"Hinweis: {t} nicht in der SEC-Liste")
    except Exception as e:
        log("Hinweis: ADR-Liste nicht ladbar:", str(e)[:100])
    if len(out) < 300:
        ia.fail(f"S&P-500-Liste unplausibel kurz ({len(out)}), nichts gespeichert.")
    json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "quelle": CONSTITUENTS, "firmen": out},
              open(UNIVERSE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    log(f"{len(out)} Unternehmen gespeichert")


# ---------------------------------------------------------------- Kandidaten
def _parse_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def edgar_candidates(firmen, done):
    """Neue 8-K-Meldungen der S&P-500-Firmen (pro Firma ein Abruf der letzten Einreichungen)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_H)
    found = []
    for i, f in enumerate(firmen):
        try:
            sub = json.loads(ia.http(f"https://data.sec.gov/submissions/CIK{f['cik']:010d}.json", ua=UA_HDR, timeout=30))
            rec = sub["filings"]["recent"]
        except Exception as e:
            if i < 3 or i % 100 == 0:
                log(f"Hinweis: {f['sym']} nicht abrufbar ({str(e)[:80]})")
            time.sleep(0.15); continue
        for j, form in enumerate(rec.get("form", [])[:40]):
            if form != ("6-K" if f.get("fpi") else "8-K"):
                continue
            acc = rec["accessionNumber"][j]
            acc_dt = _parse_dt(rec["acceptanceDateTime"][j]) if rec.get("acceptanceDateTime") else None
            if acc_dt and acc_dt < cutoff:
                continue
            key = "sec:" + acc
            if key in done:
                continue
            items = {x.strip() for x in (rec.get("items", [""] * 999)[j] or "").split(",") if x.strip()}
            if items and items <= SKIP_ITEMS:
                continue
            found.append({"key": key, "sym": f["sym"], "name": f["name"], "acc": acc, "cik": f["cik"], "items": sorted(items),
                          "when": acc_dt.isoformat() if acc_dt else "", "src": "sec",
                          "primary": (rec.get("primaryDocument") or [""] * 999)[j], "fpi": bool(f.get("fpi"))})
        time.sleep(0.12)   # SEC erlaubt hoechstens 10 Abrufe pro Sekunde
    found.sort(key=lambda x: x["when"])
    return found


def edgar_press_release(c):
    """Findet in der 8-K die Pressemitteilung (EX-99) und liefert (text, url) oder None."""
    nodash = c["acc"].replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{c['cik']}/{nodash}/"
    files = [x["name"] for x in json.loads(ia.http(base + "index.json", ua=UA_HDR))["directory"]["item"]]
    cand = [f for f in files if re.search(r"\.(htm|html|txt)$", f, re.I) and not re.search(r"(-index|^R\d+\.|xbrl|\.xml)", f, re.I)]
    ex = [f for f in cand if re.search(r"(^|[^0-9])99[-_.]?0?[1-9]?", f)]
    ex = [f for f in ex if re.search(r"99", f)]
    if not ex and c.get("fpi") and c.get("primary") and re.search(r"\.(htm|html|txt)$", c["primary"], re.I):
        ex = [c["primary"]]          # 6-K ohne eigene Anlage: Das Hauptdokument ist die Meldung
    if not ex:
        return None
    ex.sort(key=lambda f: (0 if re.search(r"99[-_.]?0?1", f) else 1, f))
    raw = ia.http(base + ex[0], ua=UA_HDR)
    txt = raw if ex[0].lower().endswith(".txt") else ia.html_to_text(raw)
    time.sleep(0.12)
    return txt, base + ex[0]


def feed_candidates(sp_syms, done):
    sp_syms = set(sp_syms) | set(ADR.values())
    """Eintraege aus data/news.json fuer Titel, die nicht ueber die SEC laufen (Europa, Asien, ...)."""
    d = load_json(NEWS, {"items": []})
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_H)
    out = []
    for it in d.get("items", []):
        sym = it.get("sym", "")
        if not sym or sym in sp_syms:
            continue
        dt = _parse_dt(it.get("date", ""))
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt and dt < cutoff:
            continue
        key = "feed:" + (it.get("link") or it.get("title", ""))
        if key in done or not it.get("link"):
            continue
        out.append({"key": key, "sym": sym, "name": it.get("name") or sym, "title": it.get("title", ""), "link": it["link"],
                    "text": it.get("text", ""), "when": dt.isoformat() if dt else "", "src": "feed"})
    out.sort(key=lambda x: x["when"])
    return out


def feed_text(c):
    txt = c.get("text") or ""
    if len(txt) < 400:
        try:
            txt = ia.html_to_text(ia.http(c["link"], ua="Mozilla/5.0 (compatible; dividenden-rechner.de)"))
        except Exception as e:
            log(f"  Seite nicht abrufbar: {str(e)[:80]}")
    return txt, c["link"]


# ---------------------------------------------------------------- Schreiben
def generate(c, text):
    mock = os.environ.get("KURZ_MOCK")
    if mock:
        d = json.load(open(mock, encoding="utf-8"))
        return d.get(c["key"]) or d.get("*")
    prompt = f"{PROMPT}\n\nUNTERNEHMEN: {c['name']} ({c['sym']})\n\nPRESSEMITTEILUNG:\n{text[:60000]}"
    return ia._generate([{"text": prompt}], SCHEMA, ia.api_key())


def background(c, text):
    """Websuche (Gemini) mit Hintergrund zu Peers, Vergangenheit, aktuellen Themen und Finanzlage. Liefert (Text, Quellen)."""
    if os.environ.get("KURZ_MOCK"):
        m = json.load(open(os.environ["KURZ_MOCK"], encoding="utf-8")).get("_hintergrund", "")
        return m, []
    prompt = (f"Recherchiere mit der Websuche knappen Hintergrund zu {c['name']} ({c['sym']}) zu dieser Meldung: {text[:1500]}\n\n"
              "Finde zuerst heraus, was fuer dieses Unternehmen gerade die entscheidenden Themen sind, und liefere dazu Stichpunkte auf Deutsch mit Zahlen und Zeitangaben. Beruecksichtige, soweit sie jetzt wichtig sind: Vergleich mit den konkreten Wettbewerbern und der Branche, Entwicklung der letzten Quartale und Jahre, aktuelle Unternehmensthemen (Strategie, Fuehrungswechsel, Rechtsstreit, Regulierung, Zoelle, Uebernahmen) und Finanzlage (Schulden, Cashflow, Rating, Dividendenhistorie). Die Gewichtung richtet sich nach der aktuellen Lage dieses Unternehmens, nicht nach einem festen Schema. Berichte sachlich und kritisch. Nenne zu jeder Zahl Jahr oder Quartal. Erfinde nichts; was du nicht findest, laesst du weg.")
    return ia.ground(prompt, ia.api_key())


def context_part(c, text, out, bg):
    """Zweiter Modellaufruf: Einordnung aus Pressemitteilung und Hintergrund."""
    mock = os.environ.get("KURZ_MOCK")
    if mock:
        d = json.load(open(mock, encoding="utf-8")).get("_einordnung")
        return d
    prompt = (f"{CTX_PROMPT}\n\nUNTERNEHMEN: {c['name']} ({c['sym']})\n\nKURZMELDUNG (bereits geschrieben):\n{out['body_markdown']}\n\n"
              f"PRESSEMITTEILUNG (Auszug):\n{text[:8000]}\n\nHINTERGRUND (per Websuche):\n{bg[:8000] or '(keiner verfuegbar)'}")
    return ia._generate([{"text": prompt}], CTX_SCHEMA, ia.api_key())


def person_photo(c, person, slug):
    """Portraet der genannten Person von Wikimedia Commons (freie Lizenz); None, wenn keins eindeutig passt."""
    import urllib.parse
    from io import BytesIO
    from PIL import Image
    if os.environ.get("KURZ_MOCK"):
        return None
    ua = "dividenden-rechner.de Magazin-Agent (https://www.dividenden-rechner.de)"
    seen = {}
    for term in (person, f"{person} {c['name']}"):
        q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrsearch": term, "gsrnamespace": 6, "gsrlimit": 15,
                                    "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 900})
        try:
            data = json.loads(ia.http("https://commons.wikimedia.org/w/api.php?" + q, ua=ua))
        except Exception as e:
            log("  Commons nicht erreichbar:", str(e)[:80]); continue
        for pg in (data.get("query", {}).get("pages", {}) or {}).values():
            ii = (pg.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata", {})
            title = pg.get("title", ""); lic = ia._strip(md.get("LicenseShortName", {}).get("value", ""))
            if (ii.get("mime") != "image/jpeg" or ii.get("width", 0) < 500 or ia.BAD_TITLE.search(title) or not ia.OK_LIC.search(lic)
                    or re.search(r"-(NC|ND)", lic) or ia._strip(md.get("Restrictions", {}).get("value", "")) or not ii.get("thumburl")):
                continue
            seen[title] = {"title": title, "thumb": ii["thumburl"], "page": ii.get("descriptionurl", ""), "lic": lic,
                           "artist": ia._strip(md.get("Artist", {}).get("value", "")) or "Unbekannt",
                           "desc": ia._strip(md.get("ImageDescription", {}).get("value", ""))[:200],
                           "date": ia._strip(md.get("DateTimeOriginal", {}).get("value", ""))[:10]}
    cands = list(seen.values())[:20]
    log(f"  Foto-Kandidaten fuer {person}: {len(cands)}")
    if not cands:
        return None
    listing = "\n".join(f"{i}: {x['title']} | {x['desc']} | {x['date']}" for i, x in enumerate(cands))
    prompt = (f"Welches Foto zeigt eindeutig {person} ({c['name']})? Der Name muss im Dateititel oder in der Beschreibung stehen, "
              "das Foto soll die Person allein oder klar erkennbar im Mittelpunkt zeigen und nicht stark veraltet sein. "
              "Wenn keins sicher passt, antworte -1.\n\n" + listing)
    try:
        idx = ia._generate([{"text": prompt}], {"type": "OBJECT", "required": ["index"], "properties": {"index": {"type": "INTEGER"}}}, ia.api_key())["index"]
    except SystemExit:
        return None
    if not (isinstance(idx, int) and 0 <= idx < len(cands)):
        return None
    ph = cands[idx]
    try:
        im = Image.open(BytesIO(ia.http(ph["thumb"], binary=True, ua=ua))).convert("RGB")
        im.thumbnail((900, 900))
        rel = f"assets/magazin/{slug}-foto.jpg"
        os.makedirs(os.path.join(ROOT, "assets", "magazin"), exist_ok=True)
        im.save(os.path.join(ROOT, rel), "JPEG", quality=85, optimize=True)
    except Exception as e:
        log("  Foto nicht speicherbar:", str(e)[:80]); return None
    return {"rel": rel, "alt": f"Foto von {person}", "credit": ia.photo_credit(ph), "source": ph["page"]}


def _nums(t):
    return [re.sub(r"[.,]", "", x) for x in re.findall(r"\d[\d.,]*\d|\d", t)]


def unverified_numbers(body, source):
    """Zahlen im Text, die nicht als eigene Zahl im Original vorkommen (Trennzeichen werden ignoriert)."""
    have = set(_nums(source))
    have |= {h.rstrip("0") for h in have if h.rstrip("0")}
    bad = []
    for tok in re.findall(r"\d[\d.,]*\d|\d", body):
        d = re.sub(r"[.,]", "", tok)
        if len(d) <= 1:
            continue
        if d not in have and d.rstrip("0") not in have:
            bad.append(tok)
    return bad


TERMINE = os.path.join(ia.ROOT, "data", "termine.json")


def save_termine(c, termine, text, url):
    """Termine aus der Meldung in data/termine.json (Earnings-Seite). Nur, wenn Jahr, Tag und Betrag im Original stehen."""
    nums = {str(int(x)) for x in re.findall(r"\d+", text)}; allnums = set(_nums(text))
    d = load_json(TERMINE, {"termine": []})
    have = {(t["sym"], t["art"], t["datum"]) for t in d["termine"]}
    new = 0
    for t in termine:
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", (t.get("datum") or "").strip())
        if not m or str(int(m.group(1))) not in nums or str(int(m.group(3))) not in nums:
            continue
        b = (t.get("betrag") or "").strip()
        if b and re.sub(r"[.,]", "", b) not in allnums and re.sub(r"[.,]", "", b).rstrip("0") not in allnums:
            b = ""
        key = (c["sym"], t["art"], t["datum"])
        if key in have:
            continue
        d["termine"].append({"sym": c["sym"], "name": c.get("name", c["sym"]), "art": t["art"], "datum": t["datum"],
                             "betrag": b, "waehrung": (t.get("waehrung") or "").strip()[:4], "quelle": url})
        have.add(key); new += 1
    cut = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
    d["termine"] = sorted([t for t in d["termine"] if t["datum"] >= cut], key=lambda t: (t["datum"], t["sym"]))
    json.dump(d, open(TERMINE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if new:
        log(f"  {new} Termin(e) gespeichert")


def slugify(s):
    s = s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:70] or "meldung"


def esc_yaml(s):
    return str(s).replace("\\", " ").replace('"', "'").replace("\n", " ").strip()


def write_post(c, out, url, bad, ctx=None, srcs=None, photo=None):
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    slug = slugify(out.get("slug") or out["title"])
    existing = [f for f in os.listdir(OUT_DIR) if f.endswith(f"{slug}.md")]
    if existing:
        log("  gibt es schon:", existing[0]); return None
    stamp = now.strftime("%Y-%m-%d-%H%M")
    path = os.path.join(OUT_DIR, f"{stamp}-{slug}.md")
    name = "Pressemitteilung " + c["name"] + (" (SEC-Meldung)" if c["src"] == "sec" else "")
    head = ["---", f'title: "{esc_yaml(out["title"])}"', f'description: "{esc_yaml(out["description"])}"', f"date: {now.strftime('%Y-%m-%d %H:%M')}",
            f'author: "{ia.CFG["author"]}"', f'author_bio: "{esc_yaml(ia.CFG["author_bio"])}"', f'category: {out.get("category") or "Sonstige Meldung"}',
            "typ: kurz", f'quelle_url: {url}', f'quelle_name: "{esc_yaml(name)}"', f'logo_symbol: {c["sym"]}', f'logo_name: "{esc_yaml(c["name"])}"']
    if photo:
        head += [f'image: {photo["rel"]}', f'image_alt: "{esc_yaml(photo["alt"])}"', f'image_credit: "{esc_yaml(photo["credit"])}"', f'image_source: {photo["source"]}']
    if bad:
        head.append("draft: true")
    head.append("---")
    body = out["body_markdown"].strip()
    if ctx:
        body += f"\n\n## {ctx['einordnung_titel'].strip()}\n\n{ctx['einordnung_markdown'].strip()}"
        if srcs:
            body += "\n\nWeitere Quellen zum Hintergrund: " + " · ".join(f"[{(ti or u)[:60]}]({u})" for ti, u in srcs[:5])
    if bad:
        body = f"<!-- PRÜFEN: Diese Zahlen stehen nicht im Originaltext: {', '.join(bad)}. Bitte pruefen, dann 'draft: true' loeschen. -->\n\n" + body
    open(path, "w", encoding="utf-8").write("\n".join(head) + "\n" + body + "\n")
    return path


def has_recent_article(sym, days=3):
    """True, wenn es zu dieser Firma in den letzten Tagen schon einen langen Artikel (oder Entwurf) gibt."""
    cut = datetime.now() - timedelta(days=days)
    for f in os.listdir(OUT_DIR):
        if not f.endswith(".md") or f.startswith(("_", "README")):
            continue
        try:
            t = open(os.path.join(OUT_DIR, f), encoding="utf-8").read(2500)
        except Exception:
            continue
        if re.search(rf"^logo_symbol:\s*\"?{re.escape(sym)}\"?\s*$", t, re.M) and not re.search(r"^typ:\s*kurz", t, re.M):
            m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", t, re.M)
            if m and datetime.strptime(m.group(1), "%Y-%m-%d") >= cut:
                return True
    return False


def long_article(c, state):
    """Bei Quartalszahlen einer Firma aus der Beobachtungsliste: IR-Agent starten (langer Artikel als Entwurf)."""
    import subprocess
    done = state["done"]; fails = state.setdefault("fails", {})
    key = "ir:" + c["acc"]
    if has_recent_article(c["sym"]):
        done[key] = datetime.now(timezone.utc).strftime("%Y-%m-%d"); log(f"  {c['sym']}: es gibt schon einen aktuellen Artikel"); return False
    if key in done or fails.get(key, 0) >= 3:
        return False
    cmd = [sys.executable, os.path.join(ROOT, "tools", "ir_agent.py"), "--ticker", c["sym"], "--art", "ergebnisse"]
    log(f"  IR-Agent startet fuer {c['sym']} (Entwurf)")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=ROOT)
    except Exception as e:
        fails[key] = fails.get(key, 0) + 1; log("  IR-Agent Fehler:", str(e)[:100]); return False
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    if r.returncode == 0:
        done[key] = datetime.now(timezone.utc).strftime("%Y-%m-%d"); log("  IR-Agent fertig:", " | ".join(tail)[:200]); return True
    msg = " ".join(tail)
    if "gibt es schon" in msg or "Es gibt schon einen Artikel" in msg:
        done[key] = datetime.now(timezone.utc).strftime("%Y-%m-%d"); log("  Artikel gibt es schon"); return False
    fails[key] = fails.get(key, 0) + 1; log("  IR-Agent gescheitert:", msg[:200]); return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-universe", action="store_true")
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--offline", help="JSON-Liste fertiger Kandidaten (key, sym, name, src, text, link) statt Netzabruf")
    a = ap.parse_args()
    if a.update_universe:
        return update_universe()
    state = load_json(STATE, {"done": {}})
    done = state["done"]
    if a.offline:
        cands = json.load(open(a.offline, encoding="utf-8"))
    else:
        uni = load_json(UNIVERSE, None)
        if not uni:
            ia.fail("data/universe.json fehlt: erst --update-universe ausfuehren.")
        firmen = uni["firmen"]
        cands = edgar_candidates(firmen, done) + feed_candidates({f["sym"] for f in firmen}, done)
    log(f"{len(cands)} neue Kandidaten")
    made = 0; longs = 0
    watch = set(load_json(WATCHLIST, {}).get("tickers", []))
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for c in cands:
        if made >= a.max:
            log("Obergrenze erreicht, Rest beim naechsten Lauf."); break
        log(f"- {c['sym']} {c['key']}")
        try:
            if c.get("text"):
                text, url = c["text"], c.get("link") or c.get("url", "")
            elif c["src"] == "sec":
                r = edgar_press_release(c)
                if not r:
                    log("  keine Pressemitteilung in der Meldung"); done[c["key"]] = now_iso; continue
                text, url = r
            else:
                text, url = feed_text(c)
            if len(text) < 300:
                log("  zu wenig Text"); done[c["key"]] = now_iso; continue
            out = generate(c, text)
        except SystemExit:
            log("  Modell-Fehler, spaeter erneut"); continue
        except Exception as e:
            log(f"  Fehler: {str(e)[:120]}"); continue
        done[c["key"]] = now_iso
        if (c.get("src") == "sec" and "2.02" in c.get("items", []) and c["sym"] in watch and longs < MAX_LONG and not a.dry
                and not os.environ.get("KURZ_MOCK")):
            if long_article(c, state): longs += 1
        if out and out.get("termine") and not a.dry:
            save_termine(c, out["termine"], text, url)
        if not out or not out.get("relevant"):
            log("  nicht relevant:", (out or {}).get("reason", "")[:100]); continue
        if not (out.get("title") and out.get("body_markdown") and out.get("description")):
            log("  Antwort unvollstaendig"); continue
        bad = unverified_numbers(out["body_markdown"] + " " + out["title"] + " " + out["description"], text)
        bg, srcs = "", []
        ctx = None
        try:
            bg, srcs = background(c, text)
            ctx = context_part(c, text, out, bg)
        except SystemExit:
            log("  Einordnung: Modell-Fehler")
        if ctx and ctx.get("einordnung_markdown") and ctx.get("einordnung_titel"):
            bad += ["Einordnung: " + t for t in unverified_numbers(ctx["einordnung_markdown"], text + " " + bg)]
        else:
            ctx = None; bad.append("Einordnung fehlt (Hintergrundrecherche nicht verfuegbar)")
        slug_guess = slugify(out.get("slug") or out["title"])
        photo = person_photo(c, out["foto_person"].strip(), slug_guess) if (out.get("foto_person") or "").strip() and not a.dry else None
        if a.dry:
            log("  [dry]", out["title"], "| ungeprueft:", bad); continue
        p = write_post(c, out, url, bad, ctx, srcs, photo)
        if p:
            made += 1; log("  geschrieben:", os.path.basename(p), "(Entwurf)" if bad else "")
    cut = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    state["done"] = {k: v for k, v in done.items() if v >= cut}
    if not a.dry:
        json.dump(state, open(STATE, "w", encoding="utf-8"), indent=0)
    log(f"{made} Kurzmeldungen, {longs} lange Entwuerfe erstellt")


if __name__ == "__main__":
    main()
