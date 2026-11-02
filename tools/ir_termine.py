#!/usr/bin/env python3
"""IR-Termine: liest die Investor-Relations-Seiten ausgewaehlter Firmen und traegt NUR Earnings-Termine
(Quartals-, Halbjahres-, Jahreszahlen) in data/termine-app.json ein. Danach holt es, sobald die Zahlen
veroeffentlicht sind, Gewinn je Aktie und Umsatz und legt sie in data/ist-zahlen.json ab (der Earnings-Kalender
zeigt sie dann als "berichtet").

Aufruf:
  python3 tools/ir_termine.py                     # beide Schritte fuer alle aktiven Firmen
  python3 tools/ir_termine.py --phase termine     # nur Termine
  python3 tools/ir_termine.py --phase ergebnisse  # nur Ergebnisse
  python3 tools/ir_termine.py --sym AAPL,V        # nur diese Kuerzel
  IR_TERMINE_MOCK=datei.json ...                  # Test ohne Netz und ohne Gemini

Regeln:
- Es werden nur Termine uebernommen, deren Datum UND Ereignis wortgetreu als Beleg im Seitentext stehen.
- Konferenzen, Hauptversammlungen, Investorentage, Dividendentermine werden nie eingetragen.
- Bestehende Eintraege werden nur aktualisiert oder ergaenzt, nie geloescht.
- Uhrzeiten werden in deutsche Zeit umgerechnet.
"""
import argparse, hashlib, json, os, re, sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ir_agent as ia  # noqa: E402

BERLIN = ZoneInfo("Europe/Berlin")
CFG_P = os.path.join(HERE, "ir_termine_config.json")
LINKS_P = os.path.join(ROOT, "data", "ir-links.json")
TERM_P = os.path.join(ROOT, "data", "termine-app.json")
STATE_P = os.path.join(ROOT, "data", "ir-termine-state.json")
IST_P = os.path.join(ROOT, "data", "ist-zahlen.json")

TZ = {"ET": "America/New_York", "EST": "America/New_York", "EDT": "America/New_York", "CT": "America/Chicago", "CST": "America/Chicago",
      "CDT": "America/Chicago", "MT": "America/Denver", "MST": "America/Denver", "MDT": "America/Denver", "PT": "America/Los_Angeles",
      "PST": "America/Los_Angeles", "PDT": "America/Los_Angeles", "GMT": "Europe/London", "BST": "Europe/London", "UK": "Europe/London",
      "CET": "Europe/Berlin", "CEST": "Europe/Berlin", "JST": "Asia/Tokyo", "SGT": "Asia/Singapore", "HKT": "Asia/Hong_Kong",
      "AEST": "Australia/Sydney", "AEDT": "Australia/Sydney", "UTC": "UTC"}

EVENT_SCHEMA = {"type": "OBJECT", "required": ["events"], "properties": {"events": {"type": "ARRAY", "items": {
    "type": "OBJECT", "required": ["period", "datum", "beleg"],
    "properties": {"period": {"type": "STRING", "description": "Berichtszeitraum, z. B. Q3 2026, Q4 2026, Halbjahr 2026, GJ 2026"},
                   "datum": {"type": "STRING", "description": "YYYY-MM-DD, Tag der Veroeffentlichung der Zahlen (bzw. des Earnings Calls)"},
                   "zeit": {"type": "STRING", "description": "HH:MM im 24-Stunden-Format, leer wenn keine Uhrzeit genannt wird"},
                   "zeitzone": {"type": "STRING", "description": "z. B. ET, CET, GMT oder IANA-Name, leer wenn nicht genannt"},
                   "beleg": {"type": "STRING", "description": "Woertliches Zitat (max. 200 Zeichen) aus dem Seitentext, das Datum und Ereignis enthaelt"}}}}}}

IST_SCHEMA = {"type": "OBJECT", "required": ["matches_period"], "properties": {
    "matches_period": {"type": "BOOLEAN", "description": "true nur wenn die Meldung genau den gefragten Berichtszeitraum behandelt"},
    "eps": {"type": "NUMBER", "description": "Gewinn je Aktie, verwaessert, des Berichtszeitraums, exakt wie im Text"},
    "eps_basis": {"type": "STRING", "description": "bereinigt oder berichtet"},
    "revenue": {"type": "NUMBER", "description": "Umsatz des Berichtszeitraums, Zahl exakt wie im Text"},
    "unit": {"type": "STRING", "description": "Mrd, Mio oder leer, passend zu revenue"},
    "currency": {"type": "STRING"}}}


def jload(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default


def jsave(p, d):
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def norm(t):
    return re.sub(r"\s+", " ", (t or "")).strip().lower()


def today():
    return datetime.now(BERLIN).date()


MOCK = jload(os.environ["IR_TERMINE_MOCK"], {}) if os.environ.get("IR_TERMINE_MOCK") else None


def fetch_text(sym, url):
    if MOCK is not None:
        return (MOCK.get(sym) or {}).get("text", "")
    txt = ""
    try:
        txt = ia.html_to_text(ia.http(url, ua=ia.CHROME_UA, timeout=60))
    except Exception as e:
        print(f"{sym}: direkter Abruf nicht moeglich ({e})")
    if len(txt.strip()) < 500:
        h, _ = ia.chrome_fetch(url)
        txt = ia.html_to_text(h) if h else ""
    return txt


def extract_events(sym, name, text, key):
    if MOCK is not None:
        return (MOCK.get(sym) or {}).get("events", [])
    prompt = (f"Du liest den Text der Investor-Relations-Seite von {name} ({sym}). Heute ist der {today().isoformat()}.\n"
              "Finde ausschliesslich angekuendigte Veroeffentlichungstermine von Quartals-, Halbjahres- oder Jahreszahlen "
              "(Earnings Release, Earnings Call, Webcast zu den Ergebnissen). NICHT aufnehmen: Konferenzen, Hauptversammlungen, "
              "Investorentage, Dividendenzahlungen, Ex-Dividenden-Tage, Praesentationen auf Branchenkonferenzen. "
              "Nur Termine ab heute. Datum und Uhrzeit muessen woertlich im Text stehen, nichts schaetzen oder aus Vorjahren ableiten. "
              "Gib im Feld beleg ein woertliches Zitat aus dem Text an. Wenn kein passender Termin im Text steht, gib eine leere Liste zurueck.")
    try:
        out = ia._generate([{"text": prompt}, {"text": "SEITENTEXT:\n\n" + text[:120000]}], EVENT_SCHEMA, key)
    except SystemExit as e:
        print(f"{sym}: Modell-Fehler: {e}")
        return None
    return out.get("events", [])


def to_berlin(datum, zeit, zone):
    """-> (datum_berlin, zeit_berlin oder '')"""
    if not zeit or not re.fullmatch(r"\d{1,2}:\d{2}", zeit):
        return datum, ""
    z = TZ.get((zone or "").strip().upper()) or ((zone or "").strip() if "/" in (zone or "") else None)
    if not z:
        return datum, ""
    try:
        d = datetime.fromisoformat(datum + "T" + zeit.zfill(5)).replace(tzinfo=ZoneInfo(z)).astimezone(BERLIN)
    except Exception:
        return datum, ""
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M")


def valid(ev, text, t0):
    """Beleg muss wortgetreu im Seitentext stehen und Tag und Zeitraum plausibel sein."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ev.get("datum") or ""):
        return False
    d = date.fromisoformat(ev["datum"])
    if d < t0 or d > t0 + timedelta(days=200):
        return False
    b = norm(ev.get("beleg"))
    if len(b) < 12 or b not in norm(text):
        return False
    if re.search(r"conference|konferenz|annual meeting|hauptversammlung|investor day|investorentag|ex-dividend|dividend payment", b) and \
            not re.search(r"earnings|results|ergebnis|zahlen|quarter|quartal|half|halbjahr|annual report|jahres", b):
        return False
    if not re.search(r"(?<!\d)0?%d(?!\d)" % d.day, b):
        return False
    return True


def merge_event(items, sym, name, ev, url):
    """Aktualisiert oder ergaenzt einen Quartalszahlen-Termin. Gibt Beschreibung der Aenderung oder None."""
    dat, zeit = to_berlin(ev["datum"], ev.get("zeit", ""), ev.get("zeitzone", ""))
    period = (ev.get("period") or "").strip()
    ex = [x for x in items if x["sym"] == sym and x.get("typ") == "q" and not x.get("_x")]
    hit = next((x for x in ex if norm(x.get("was")) == norm(period)), None) or \
        next((x for x in ex if abs((date.fromisoformat(x["datum"]) - date.fromisoformat(dat)).days) <= 3), None)
    if hit:
        old = (hit["datum"], hit.get("zeit", ""), hit.get("quelle", ""))
        hit["datum"] = dat
        if zeit or not hit.get("zeit"):
            hit["zeit"] = zeit
        if period and not hit.get("was"):
            hit["was"] = period
        hit["quelle"] = url
        hit["auto"] = True
        return f"{sym}: Termin {period or hit.get('was')} aktualisiert auf {dat} {zeit}".strip() if old[:2] != (hit["datum"], hit.get("zeit", "")) else None
    items.append({"datum": dat, "zeit": zeit, "sym": sym, "name": name, "was": period or "Quartalszahlen", "typ": "q", "quelle": url, "auto": True})
    return f"{sym}: neuer Termin {period} am {dat} {zeit}".strip()


def phase_termine(syms, links, state, key):
    t0 = today()
    doc = jload(TERM_P, {"items": []})
    items = doc["items"]
    log = []
    for sym in syms:
        info = links.get(sym) or {}
        url = (CFG["firmen"].get(sym) or {}).get("url") or info.get("url")
        name = info.get("name") or sym
        if not url:
            print(f"{sym}: keine IR-Adresse hinterlegt"); continue
        text = fetch_text(sym, url)
        st = state.setdefault(sym, {})
        if len(text.strip()) < (20 if MOCK is not None else 500):
            st.update({"status": "Seite nicht lesbar", "stand": t0.isoformat()})
            print(f"::warning title=IR-Termine::{sym}: IR-Seite nicht lesbar ({url})")
            continue
        h = hashlib.sha256(norm(text).encode()).hexdigest()[:16]
        if st.get("hash") == h and st.get("status") == "ok":
            print(f"{sym}: Seite unveraendert"); st["stand"] = t0.isoformat(); continue
        evs = extract_events(sym, name, text, key)
        if evs is None:
            st.update({"status": "Modell-Fehler", "stand": t0.isoformat()}); continue
        good = [e for e in evs if valid(e, text, t0)]
        if len(good) < len(evs):
            print(f"{sym}: {len(evs) - len(good)} Termin(e) verworfen (Beleg fehlt oder kein Earnings-Termin)")
        for e in good:
            c = merge_event(items, sym, name, e, url)
            if c:
                log.append(c); print(c)
        st.update({"hash": h, "status": "ok", "stand": t0.isoformat(), "gefunden": len(good)})
    doc["updated"] = t0.isoformat()
    jsave(TERM_P, doc)
    return log


def phase_ergebnisse(syms, links, key):
    """Fuer Quartalszahlen-Termine der letzten Tage ohne Ist-Zahlen: Meldung holen, EPS und Umsatz ablegen. Nur US-Titel (SEC)."""
    t0 = today()
    items = jload(TERM_P, {"items": []})["items"]
    ist = jload(IST_P, {"items": []})["items"]
    done = []
    for x in items:
        if x.get("typ") != "q" or x["sym"] not in syms:
            continue
        d = date.fromisoformat(x["datum"])
        if not (t0 - timedelta(days=7) <= d <= t0):
            continue
        if any(i["sym"] == x["sym"] and abs((date.fromisoformat(i["datum"]) - d).days) <= 4 for i in ist):
            continue
        sym = x["sym"]
        if "." in sym or "-" in sym:
            print(f"{sym}: Ergebnisse ausserhalb der USA noch nicht automatisch"); continue
        try:
            if MOCK is not None:
                m = MOCK.get(sym) or {}
                if "release" not in m:
                    continue
                src, out = {"text": m["release"], "url": m.get("release_url", ""), "date": m.get("release_date", x["datum"])}, m.get("ist")
            else:
                src = ia.sec_release(sym)
                if src.get("kind") != "text":
                    try:
                        src["text"] = ia.pdf_text(src["path"])
                    except Exception as e:
                        print(f"{sym}: Meldung nicht lesbar ({e})"); continue
                fd = (src.get("date") or "")[:10]
                if fd and abs((date.fromisoformat(fd) - d).days) > 5:
                    print(f"{sym}: neueste Meldung ({fd}) passt nicht zum Termin {x['datum']}"); continue
                p = (f"Berichtszeitraum: {x.get('was')}. Lies die Pressemitteilung und gib Gewinn je Aktie und Umsatz des Berichtszeitraums an, "
                     "Zahlen exakt wie im Text. matches_period nur true, wenn die Meldung genau diesen Zeitraum behandelt.")
                out = ia._generate([{"text": p}, {"text": "PRESSEMITTEILUNG:\n\n" + src["text"][:300000]}], IST_SCHEMA, key)
        except SystemExit as e:
            print(f"{sym}: {e}"); continue
        if not out or not out.get("matches_period"):
            print(f"{sym}: Meldung gehoert nicht zu {x.get('was')}"); continue
        ia.save_ist(sym, x["name"], x["datum"], out, src["text"], src.get("url", ""))
        done.append(sym)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["termine", "ergebnisse", "beide"], default="beide")
    ap.add_argument("--sym")
    a = ap.parse_args()
    links = jload(LINKS_P, {}).get("firmen", {})
    syms = [s for s in CFG["aktiv"] if not a.sym or s in [t.strip().upper() for t in a.sym.split(",")]]
    key = None if MOCK is not None else (os.environ.get("GEMINI_API_KEY") or ia.api_key())
    state = jload(STATE_P, {})
    log = []
    if a.phase in ("termine", "beide"):
        log += phase_termine(syms, links, state, key)
        jsave(STATE_P, state)
    res = []
    if a.phase in ("ergebnisse", "beide"):
        res = phase_ergebnisse(syms, links, key)
    print("Termine geaendert:", len(log), "| Ergebnisse geladen:", ", ".join(res) or "keine")
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write("### IR-Termine\n" + ("\n".join("- " + l for l in log) or "- keine Terminänderungen") + "\n\n### Ergebnisse\n- " + (", ".join(res) or "keine neuen") + "\n")


CFG = jload(CFG_P, {"aktiv": [], "firmen": {}})

if __name__ == "__main__":
    main()
