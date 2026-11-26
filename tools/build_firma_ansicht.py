"""Kleine Datendatei je Firma für die Firmenansicht (data/firma-ansicht/<Kürzel>.json).

Die Firmenseite lädt nur diese eine Datei statt der großen Sammeldateien. Die Zusammenführung
folgt genau der Logik von assets/firma-ansicht.js (secLoad, kzLoad, firmaNachladen):
  SEC -> ESEF -> Asien (nur fehlende Firmen) -> Deutsche Börse (fehlende Reihen/Jahre) -> Vorab-Zahlen
  danach je Firma die Einzeldateien (esef/asien/americas), wenn der Eintrag von Deutsche Börse stammt.
Kennzahlen: data/kennzahlen.json, sonst data/asien/kennzahlen.json.
"""
import json, os, re
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lade(pfad):
    try:
        with open(os.path.join(ROOT, pfad), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def sec_jahr(end):
    """Wie secJahr() im Browser: Geschäftsjahr, das im Januar (oder den ersten 7 Tagen des Februars) endet, zählt zum Vorjahr."""
    d = date.fromisoformat(str(end)[:10])
    vorjahr = d.month == 1 or (d.month == 2 and d.day <= 7)
    return str(d.year - (1 if vorjahr else 0))


def zusammen(alt, neu):
    """Reihen [[datum, wert], ...] sortiert zusammenführen, wenn das Geschäftsjahr fehlt."""
    have = {sec_jahr(d) for d, _ in alt}
    add = [x for x in neu if sec_jahr(x[0]) not in have]
    return sorted(alt + add, key=lambda x: x[0]) if add else alt


def sec_gesamt():
    s = lade("data/sec/fundamentals.json") or {"firmen": {}}
    s.setdefault("firmen", {})
    for pfad in ("data/esef/fundamentals.json", "data/asien/fundamentals.json"):
        q = lade(pfad)
        for t, f in ((q or {}).get("firmen") or {}).items():
            if t not in s["firmen"]:
                s["firmen"][t] = f
    b = lade("data/boerse-de/fundamentals.json")
    for t, bf in ((b or {}).get("firmen") or {}).items():
        o = s["firmen"].get(t)
        if o is None:
            s["firmen"][t] = bf
            continue
        o.setdefault("k", {})
        for k, reihe in (bf.get("k") or {}).items():
            o["k"][k] = zusammen(o["k"].get(k, []), reihe)
    vb = lade("data/sec/vorab.json")
    for t, v in ((vb or {}).get("firmen") or {}).items():
        o = s["firmen"].get(t)
        if o is None or not v.get("gj") or not v.get("k") or (v.get("w") and o.get("w") and v["w"] != o["w"]):
            continue
        y = sec_jahr(v["gj"])
        o.setdefault("k", {})
        n = 0
        for k, wert in v["k"].items():
            if wert is None or any(sec_jahr(d) == y for d, _ in o["k"].get(k, [])):
                continue
            o["k"][k] = sorted(o["k"].get(k, []) + [[v["gj"], wert]], key=lambda x: x[0])
            n += 1
        if n and not o.get("quelle"):
            o["quelle"] = "SEC+vorab:" + y
    return s


def sec_fuer(s, sym):
    k = sym.upper()
    return s["firmen"].get(k) or s["firmen"].get(k.replace(".", "-"))


def einzeldatei(sym):
    """firmaNachladen: Einzeldatei je Firma (ESEF, Asien, Amerika) wird nur genommen, wenn der Eintrag von Deutsche Börse stammt."""
    t = sym.upper()
    for d in ("esef", "asien", "americas"):
        f = lade(f"data/{d}/firma/{t}.json")
        if f:
            return f
    return None


def firmen_daten(s, sym):
    t = sym.upper()
    o = sec_fuer(s, sym)
    if o is not None and not str(o.get("quelle") or "").startswith("boerse.de"):
        return o
    f = einzeldatei(sym)
    if not f:
        return o
    if o is None:
        return f
    n = {**f, "k": {**(f.get("k") or {})}}
    for k, reihe in (o.get("k") or {}).items():
        n["k"][k] = zusammen(n["k"].get(k, []), reihe)
    return n


def schreiben(firmen, zielordner):
    """firmen: Liste mit 'sym' und 'slug' (aus build_firmenseiten)."""
    os.makedirs(zielordner, exist_ok=True)
    s = sec_gesamt()
    ka = (lade("data/kennzahlen.json") or {}).get("werte") or {}
    kb = (lade("data/asien/kennzahlen.json") or {}).get("werte") or {}
    ceos = lade("data/ceo-portraits.json") or {}
    n = 0
    for f in firmen:
        sym = f["sym"]
        t = sym.upper()
        kz = ka.get(t) or ka.get(t.replace(".", "-")) or kb.get(t) or kb.get(t.replace(".", "-"))
        ceo = ceos.get(f.get("slug", ""))
        hist = os.path.exists(os.path.join(ROOT, "data", "kurse", "historie", t + ".json"))
        daten = {"sec": firmen_daten(s, sym), "kz": kz, "ceo": ceo, "hist": hist}
        name = re.sub(r"[^A-Za-z0-9.\-]", "_", t)
        with open(os.path.join(zielordner, name + ".json"), "w", encoding="utf-8") as fh:
            json.dump(daten, fh, ensure_ascii=False, separators=(",", ":"))
        n += 1
    return n


def schluessel(sym):
    return re.sub(r"[^A-Za-z0-9.\-]", "_", sym.upper())


def ansicht_html(sym, stand, tiefe=2):
    """Der Block mit Steckbrief, Bewertung, Diagrammen und Meldungen (gleich wie im Aktien-Hub). Wird auf jeder Firmenseite eingebaut."""
    wurzel = "../" * tiefe
    cache = re.sub(r"\D", "", str(stand)) or "1"
    return ('<link rel="stylesheet" href="' + wurzel + 'assets/firma-ansicht.css">'
            '<section id="hub" class="fa-view" aria-label="Aktienansicht"></section><p id="msg" role="status"></p>'
            '<script>window.FA_ROOT="' + wurzel + '";</script>'
            '<script src="' + wurzel + 'assets/logos.js"></script>'
            '<script src="' + wurzel + 'assets/firma-ansicht.js"></script>'
            '<script>fetch("' + wurzel + 'data/firma-ansicht/' + schluessel(sym) + '.json?v=' + cache + '")'
            '.then(r=>r.ok?r.json():{}).catch(()=>({})).then(d=>faStart(' + json.dumps(sym.upper()) + ',d))'
            '.catch(e=>{console.error(e);document.getElementById("msg").textContent="Die Daten konnten gerade nicht geladen werden."});</script>')
