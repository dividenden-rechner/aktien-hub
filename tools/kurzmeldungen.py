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
    },
}
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
- Der Firmenname steht im Titel."""

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
        for j, form in enumerate(rec.get("form", [])[:25]):
            if form != "8-K":
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
                          "when": acc_dt.isoformat() if acc_dt else "", "src": "sec"})
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
    if not ex:
        return None
    ex.sort(key=lambda f: (0 if re.search(r"99[-_.]?0?1", f) else 1, f))
    raw = ia.http(base + ex[0], ua=UA_HDR)
    txt = raw if ex[0].lower().endswith(".txt") else ia.html_to_text(raw)
    time.sleep(0.12)
    return txt, base + ex[0]


def feed_candidates(sp_syms, done):
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


def slugify(s):
    s = s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:70] or "meldung"


def esc_yaml(s):
    return str(s).replace("\\", " ").replace('"', "'").replace("\n", " ").strip()


def write_post(c, out, url, bad):
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
    if bad:
        head.append("draft: true")
    head.append("---")
    body = out["body_markdown"].strip()
    if bad:
        body = f"<!-- PRÜFEN: Diese Zahlen stehen nicht im Originaltext: {', '.join(bad)}. Bitte pruefen, dann 'draft: true' loeschen. -->\n\n" + body
    open(path, "w", encoding="utf-8").write("\n".join(head) + "\n" + body + "\n")
    return path


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
    made = 0
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
        if not out or not out.get("relevant"):
            log("  nicht relevant:", (out or {}).get("reason", "")[:100]); continue
        if not (out.get("title") and out.get("body_markdown") and out.get("description")):
            log("  Antwort unvollstaendig"); continue
        bad = unverified_numbers(out["body_markdown"] + " " + out["title"] + " " + out["description"], text)
        if a.dry:
            log("  [dry]", out["title"], "| ungeprueft:", bad); continue
        p = write_post(c, out, url, bad)
        if p:
            made += 1; log("  geschrieben:", os.path.basename(p), "(Entwurf)" if bad else "")
    cut = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    state["done"] = {k: v for k, v in done.items() if v >= cut}
    if not a.dry:
        json.dump(state, open(STATE, "w", encoding="utf-8"), indent=0)
    log(f"{made} Kurzmeldungen erstellt")


if __name__ == "__main__":
    main()
