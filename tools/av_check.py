#!/usr/bin/env python3
"""Prueft woechentlich, ob sich die Konditionen der Altersvorsorgedepot-Anbieter geaendert haben.

Ablauf: Die Quellseiten aus data/av-anbieter.json (plus optionale Seiten aus tools/av_check_config.json) werden geladen,
ein Modell liest daraus je Anbieter Kosten zu Beginn, Dauer der Erstattung und langfristige Kosten. Eine Aenderung wird nur
uebernommen, wenn das woertliche Zitat im Seitentext steht, den Anbieternamen UND die neue Zahl enthaelt und die Zahl plausibel ist.
Uebernommene Aenderungen stehen mit Datum und Quelle in "aenderungen" (die Seite zeigt die letzten). Es wird nie etwas geloescht,
unklare Funde landen nur im Protokoll (data/av-pruefung.json). Danach baut der Workflow die Seite neu (tools/build_av.py).

Aufruf:  python3 tools/av_check.py          (AV_CHECK_MOCK=datei.json fuer Tests ohne Netz und Modell)
"""
import json, os, re, sys
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ir_agent as ia  # noqa: E402

DATA_P = os.path.join(ROOT, "data", "av-anbieter.json")
CFG_P = os.path.join(HERE, "av_check_config.json")
LOG_P = os.path.join(ROOT, "data", "av-pruefung.json")
MOCK = json.load(open(os.environ["AV_CHECK_MOCK"], encoding="utf-8")) if os.environ.get("AV_CHECK_MOCK") else None

SCHEMA = {"type": "OBJECT", "required": ["funde"], "properties": {"funde": {"type": "ARRAY", "items": {
    "type": "OBJECT", "required": ["anbieter", "beleg"],
    "properties": {"anbieter": {"type": "STRING", "description": "Name exakt wie in der Liste"},
                   "kosten_start": {"type": "NUMBER", "description": "Kosten in Prozent pro Jahr waehrend der Erstattungs-/Startphase, 0 bei voller Erstattung"},
                   "start_jahre": {"type": "INTEGER", "description": "Dauer der Startphase in Jahren ab Vertragsbeginn 2027, 0 wenn keine"},
                   "kosten_dauer": {"type": "NUMBER", "description": "Laufende Gesamtkosten in Prozent pro Jahr nach der Startphase (Standarddepot)"},
                   "beleg": {"type": "STRING", "description": "Woertliches Zitat (max. 240 Zeichen) aus dem Seitentext, das Anbieter und die genannte Zahl enthaelt"}}}}}}


def norm(t):
    return re.sub(r"\s+", " ", (t or "")).strip().lower()


def fetch(url):
    if MOCK is not None:
        return (MOCK.get("seiten") or {}).get(url, "")
    txt = ""
    try:
        txt = ia.html_to_text(ia.http(url, ua=ia.CHROME_UA, timeout=60))
    except Exception as e:
        print(f"Abruf nicht moeglich: {url} ({e})")
    if len(txt.strip()) < 500:
        try:
            h, _ = ia.chrome_fetch(url)
            txt = ia.html_to_text(h) if h else txt
        except Exception as e:
            print(f"Browser-Abruf nicht moeglich: {url} ({e})")
    return txt


def ask(names, url, text):
    if MOCK is not None:
        return [f for f in (MOCK.get("funde") or []) if f.get("url", url) == url]
    prompt = ("Lies den Text einer Seite ueber das neue Altersvorsorgedepot (Start 1.1.2027). Gesucht sind die angekuendigten laufenden Kosten "
              "des STANDARDDEPOTS dieser Anbieter: " + "; ".join(names) + ". Gib nur Anbieter an, zu denen der Text konkrete Zahlen nennt. "
              "kosten_start/start_jahre nur, wenn der Text eine zeitlich begrenzte Erstattung oder Gratisphase nennt. Nichts schaetzen, nichts aus anderen "
              "Quellen ergaenzen. Das Zitat im Feld beleg muss woertlich im Text stehen und Anbieter und Zahl enthalten.")
    try:
        out = ia._generate([{"text": prompt}, {"text": "SEITENTEXT:\n\n" + text[:120000]}], SCHEMA, ia.api_key())
    except SystemExit as e:
        print(f"Modell-Fehler bei {url}: {e}")
        return []
    return out.get("funde", [])


def zahl_im_beleg(z, beleg):
    cands = {f"{z:g}".replace(".", ","), f"{z:.2f}".replace(".", ","), f"{z:.1f}".replace(".", ","), f"{z:g}"}
    b = beleg.replace("\xa0", " ")
    return any(re.search(r"(?<![\d,.])" + re.escape(c) + r"(?![\d])", b) for c in cands)


def main():
    D = json.load(open(DATA_P, encoding="utf-8"))
    cfg = json.load(open(CFG_P, encoding="utf-8")) if os.path.exists(CFG_P) else {}
    names = [f["name"] for f in D["firmen"]]
    byname = {f["name"]: f for f in D["firmen"]}
    urls = []
    for f in D["firmen"]:
        for u in [q["url"] for q in f["quellen"]] + cfg.get("seiten", {}).get(f["name"], []):
            if u not in urls:
                urls.append(u)
    urls += [u for u in cfg.get("allgemein", []) if u not in urls]
    heute = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d")
    log = {"datum": heute, "uebernommen": [], "verworfen": [], "nicht_lesbar": []}
    D.setdefault("aenderungen", [])
    changed = False
    for u in urls:
        text = fetch(u)
        if len(text.strip()) < 300 and MOCK is None:
            log["nicht_lesbar"].append(u); continue
        for fd in ask(names, u, text):
            f = byname.get(fd.get("anbieter"))
            if not f:
                continue
            beleg = fd.get("beleg") or ""
            if len(beleg) < 15 or norm(beleg) not in norm(text) or norm(f["name"].split(" (")[0].split(" / ")[0]) not in norm(beleg):
                log["verworfen"].append({"anbieter": fd.get("anbieter"), "grund": "Beleg nicht wortgetreu oder ohne Anbietername", "url": u}); continue
            neu = {}
            for k in ("kosten_start", "kosten_dauer"):
                v = fd.get(k)
                if v is None: continue
                if not (0 <= v <= 3) or not zahl_im_beleg(v, beleg):
                    log["verworfen"].append({"anbieter": f["name"], "feld": k, "wert": v, "grund": "Zahl nicht im Beleg oder unplausibel", "url": u}); continue
                if f.get(k) is None or abs(f[k] - v) > 1e-9: neu[k] = v
            sj = fd.get("start_jahre")
            if isinstance(sj, int) and 0 <= sj <= 10 and sj != f.get("start_jahre", 0) and re.search(r"jahr|year|20\d\d", beleg, re.I):
                neu["start_jahre"] = sj
            if not neu:
                continue
            # Beleg der gleichen Seite darf nicht dem widersprechen, was schon als neuer wert eingetragen wurde (erste Quelle gewinnt je Lauf)
            if any(a["anbieter"] == f["name"] and a["datum"] == heute and set(neu) & {a["feld"]} for a in D["aenderungen"]):
                continue
            for k, v in neu.items():
                D["aenderungen"].append({"datum": heute, "anbieter": f["name"], "feld": k, "alt": f.get(k), "neu": v, "quelle": u, "beleg": beleg[:240]})
                f[k] = v
            f["kosten"] = beleg[:240].strip()
            if not any(q["url"] == u for q in f["quellen"]):
                f["quellen"].append({"titel": u.split("/")[2], "url": u})
            log["uebernommen"].append({"anbieter": f["name"], "neu": neu, "url": u}); changed = True
    D["geprueft"] = heute
    if changed:
        D["stand"] = heute
        D["aenderungen"] = D["aenderungen"][-60:]
    json.dump(D, open(DATA_P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(log, open(LOG_P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"geprueft: {len(urls)} Seiten, uebernommen {len(log['uebernommen'])}, verworfen {len(log['verworfen'])}, nicht lesbar {len(log['nicht_lesbar'])}")


if __name__ == "__main__":
    main()
