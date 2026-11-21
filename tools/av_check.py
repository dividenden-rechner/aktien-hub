#!/usr/bin/env python3
"""Prueft zweimal pro Woche, ob sich die Konditionen der Altersvorsorgedepot-Anbieter geaendert haben (Schema 2, je Depotmodell).

Ablauf: Die Quellseiten aus data/av-anbieter.json (plus optionale Seiten aus tools/av_check_config.json) werden geladen,
ein Modell liest daraus je Depotmodell Kosten zu Beginn, Dauer der Erstattung und langfristige Kosten. Ein Fund zaehlt nur,
wenn das woertliche Zitat im Seitentext steht, den Anbieternamen UND die Zahl enthaelt und die Zahl plausibel ist.
Seit dem Update vom 21.11.2026 werden Funde NICHT mehr automatisch in die Daten uebernommen: Das Datenmodell trennt
Kostenbestandteile, Zeitraeume und Bedingungen, das laesst sich aus einem Zitat nicht sicher ableiten. Abweichungen zu den
gespeicherten Werten landen in data/av-pruefung.json ("abweichungen") und muessen von Hand eingepflegt werden.
Danach baut der Workflow die Seite neu (tools/build_av.py).

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
    "properties": {"anbieter": {"type": "STRING", "description": "Angebot exakt wie in der Liste (Anbieter – Depotmodell)"},
                   "kosten_start": {"type": "NUMBER", "description": "Kosten in Prozent pro Jahr waehrend der Erstattungs-/Startphase, 0 bei voller Erstattung"},
                   "start_jahre": {"type": "INTEGER", "description": "Dauer der Startphase in Jahren ab Vertragsbeginn 2027, 0 wenn keine"},
                   "kosten_dauer": {"type": "NUMBER", "description": "Laufende Gesamtkosten in Prozent pro Jahr nach der Startphase"},
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
              "der folgenden Depotmodelle (Anbieter – Depotmodell): " + "; ".join(names) + ". Gib nur Anbieter an, zu denen der Text konkrete Zahlen nennt. "
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
    import build_av as bav
    D = json.load(open(DATA_P, encoding="utf-8"))
    cfg = json.load(open(CFG_P, encoding="utf-8")) if os.path.exists(CFG_P) else {}
    Q = D["quellen"]
    prod = {}
    for a in D["anbieter"]:
        for p in a["produkte"]:
            prod[f'{a["name"]} – {p["name"]}'] = (a, p)
    names = list(prod)
    urls = []
    for label, (a, p) in prod.items():
        for u in [Q[k]["url"] for k in p["quellen"] if k in Q] + cfg.get("seiten", {}).get(a["name"], []):
            if u not in urls:
                urls.append(u)
    urls += [u for u in cfg.get("allgemein", []) if u not in urls]
    heute = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d")
    log = {"datum": heute, "abweichungen": [], "bestaetigt": [], "verworfen": [], "nicht_lesbar": []}
    for u in urls:
        text = fetch(u)
        if len(text.strip()) < 300 and MOCK is None:
            log["nicht_lesbar"].append(u); continue
        for fd in ask(names, u, text):
            hit = prod.get(fd.get("anbieter"))
            if not hit:
                continue
            a, p = hit
            beleg = fd.get("beleg") or ""
            kurz = a["name"].split(" (")[0].split(" / ")[0]
            if len(beleg) < 15 or norm(beleg) not in norm(text) or norm(kurz) not in norm(beleg):
                log["verworfen"].append({"angebot": fd.get("anbieter"), "grund": "Beleg nicht wortgetreu oder ohne Anbietername", "url": u}); continue
            ks, _, kd, _, _ = bav.kennzahlen(p)
            gespeichert = {"kosten_start": ks, "kosten_dauer": kd}
            for k in ("kosten_start", "kosten_dauer"):
                v = fd.get(k)
                if v is None:
                    continue
                if not (0 <= v <= 3) or not zahl_im_beleg(v, beleg):
                    log["verworfen"].append({"angebot": fd.get("anbieter"), "feld": k, "wert": v, "grund": "Zahl nicht im Beleg oder unplausibel", "url": u}); continue
                eintrag = {"angebot": fd.get("anbieter"), "feld": k, "gespeichert": gespeichert[k], "gefunden": v, "url": u, "beleg": beleg[:240]}
                if gespeichert[k] is not None and abs(gespeichert[k] - v) < 1e-9:
                    log["bestaetigt"].append(eintrag)
                else:
                    log["abweichungen"].append(eintrag)
    D["geprueft"] = heute
    json.dump(D, open(DATA_P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(log, open(LOG_P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"geprueft: {len(urls)} Seiten, Abweichungen {len(log['abweichungen'])}, bestaetigt {len(log['bestaetigt'])}, verworfen {len(log['verworfen'])}, nicht lesbar {len(log['nicht_lesbar'])}")


if __name__ == "__main__":
    main()
