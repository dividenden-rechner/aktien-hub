#!/usr/bin/env python3
"""Dividenden-Termine (ab 11.11.2026): liest aus den Pressemitteilungen der Firmen (SEC 8-K, Anlage EX-99, Punkte 2.02, 7.01, 8.01)
die beschlossene Dividende mit Betrag, Stichtag (record date) und Zahltag. In den USA ist der Ex-Tag seit Mai 2024 gleich dem Stichtag.
Erst ein Suchmuster (ohne KI), nur bei unklaren Saetzen Gemini. Je Firma bleiben die letzten acht Beschluesse.
Schreibt data/dividenden-termine.json, Merkliste data/dividenden-termine-state.json."""
import json, os, re, sys, time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
# Die SEC verlangt im User-Agent eine Kontaktangabe, sonst sperrt www.sec.gov mit 403. Wir nehmen dieselbe wie der SEC-Datenlauf.
if not os.environ.get("SEC_USER_AGENT"):
    import sec_fundamentals as _sf
    os.environ["SEC_USER_AGENT"] = _sf.UA
import ir_agent as ia
import kurzmeldungen as km

TAGE = int(os.environ.get("DIV_TAGE", "100"))
MAX_KI = int(os.environ.get("DIV_MAX_KI", "40"))
MAX_ABRUF = int(os.environ.get("DIV_MAX_MELDUNGEN", "400"))
OUT, STATE = "data/dividenden-termine.json", "data/dividenden-termine-state.json"
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
DATUM = re.compile(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{1,2}),?\s+(20\d\d)")
SATZ = re.compile(r"[^.]*?(?:declar|approv|authoriz|announc)[^.]{0,300}?dividend[^.]{0,500}\.(?:[^.]{0,300}\.)?", re.I)


def iso(m):
    return f"{int(m.group(3)):04d}-{MON[m.group(1)[:3].lower()]:02d}-{int(m.group(2)):02d}"


def muster(text):
    """Sucht Saetze mit Dividendenbeschluss; liefert Liste von Dicts oder [] bzw. None (unklar -> KI)."""
    t = " ".join(text.split())
    # Punkte in Zahlen und Monatskuerzeln wuerden die Satzerkennung stoeren
    t = re.sub(r"(\d)\.(\d)", r"\1§\2", t)
    t = re.sub(r"\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Inc|Co|Corp|Ltd|No)\.", r"\1", t)
    t = re.sub(r"\bU\.S\.", "US", t)
    out, unklar = [], False
    for s in SATZ.finditer(t):
        satz = s.group(0)
        if re.search(r"preferred|depositary", satz, re.I):
            continue
        betrag = re.search(r"\$\s?(\d{1,3}(?:§\d{1,4})?)\s*(?:per|a)\s+(?:common\s+)?share", satz, re.I) or re.search(r"\$\s?(\d{1,2}§\d{2,4})", satz)
        pay = re.search(r"payable[^.]{0,40}?" + DATUM.pattern, satz, re.I)
        rec = re.search(r"record[^.]{0,60}?" + DATUM.pattern, satz, re.I) or re.search(DATUM.pattern + r"[^.]{0,40}?record", satz, re.I)
        if betrag and pay and rec:
            mp = DATUM.search(pay.group(0)); mr = DATUM.search(rec.group(0))
            out.append({"betrag": float(betrag.group(1).replace("§", ".")), "zahltag": iso(mp), "stichtag": iso(mr),
                        "art": "sonder" if re.search(r"special|one-time", satz, re.I) else "regulaer", "beleg": satz[:300].replace("§", ".")})
        elif re.search(r"dividend", satz, re.I) and (betrag or pay):
            unklar = True
    if out:
        return out
    return None if unklar else []


SCHEMA = {"type": "OBJECT", "properties": {"dividenden": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "betrag": {"type": "NUMBER"}, "waehrung": {"type": "STRING"}, "zahltag": {"type": "STRING"}, "stichtag": {"type": "STRING"},
    "art": {"type": "STRING", "enum": ["regulaer", "sonder"]}, "beleg": {"type": "STRING"}},
    "required": ["betrag", "waehrung", "zahltag", "stichtag", "art", "beleg"]}}}, "required": ["dividenden"]}
PROMPT = """Aus dieser Pressemitteilung von {name}: Welche Dividende je Stammaktie wurde beschlossen bzw. erklaert?
Je Dividende: Betrag je Aktie, Waehrung, Zahltag (payable date) und Stichtag (record date) als JJJJ-MM-TT, Art (regulaer oder sonder),
beleg = Originalsatz (hoechstens 30 Woerter). Keine Vorzugsaktien, keine bereits frueher gezahlten Dividenden, keine Jahressummen.
Wenn keine Dividende mit Zahltag beschlossen wurde: leere Liste.

Text:
{text}"""


def lade(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def kandidaten(firmen, erledigt):
    grenze = datetime.now(timezone.utc) - timedelta(days=TAGE)
    out = []
    for t, f in firmen.items():
        if f.get("std") == "IFRS":
            continue
        try:
            sub = json.loads(ia.http(f"https://data.sec.gov/submissions/CIK{int(f['cik']):010d}.json", ua=km.UA_HDR, timeout=30))
            rec = sub["filings"]["recent"]
        except Exception:
            time.sleep(0.3); continue
        for j, form in enumerate(rec.get("form", [])[:60]):
            if form != "8-K":
                continue
            items = rec.get("items", [""] * 999)[j] or ""
            if not re.search(r"2\.02|7\.01|8\.01", items):
                continue
            dt = km._parse_dt(rec["acceptanceDateTime"][j]) if rec.get("acceptanceDateTime") else None
            if dt and dt < grenze:
                break
            acc = rec["accessionNumber"][j]
            if acc not in erledigt:
                out.append({"sym": t, "name": f["n"], "cik": int(f["cik"]), "acc": acc, "when": dt.isoformat() if dt else "",
                            "primary": (rec.get("primaryDocument") or [""] * 999)[j], "fpi": False})
        time.sleep(0.3)
    out.sort(key=lambda c: c["when"], reverse=True)
    return out


def main():
    firmen = lade("data/sec/fundamentals.json", {}).get("firmen", {})
    state = lade(STATE, {"erledigt": {}})
    daten = lade(OUT, {"firmen": {}})
    try:
        key = ia.api_key()
    except SystemExit:
        key = None
    kand = kandidaten(firmen, state["erledigt"])
    print(len(kand), "neue Meldungen")
    ki = abgerufen = treffer = 0
    fehler = []
    for c in kand:
        if abgerufen >= MAX_ABRUF:
            break
        r = None
        try:
            for v in range(3):
                try:
                    r = km.edgar_press_release(c); break
                except Exception as e:
                    if "403" in str(e) and v < 2:
                        time.sleep(60); continue
                    raise
        except Exception as e:
            fehler.append(f"{c['sym']}: {str(e)[:80]}"); continue
        abgerufen += 1
        if not r:
            state["erledigt"][c["acc"]] = "ohne Anlage"; continue
        text, url = r
        if not re.search(r"dividend", text, re.I):
            state["erledigt"][c["acc"]] = "keine Dividende"; continue
        divs = muster(text)
        if divs is None and key and ki < MAX_KI:
            ki += 1
            ab = re.search(r"dividend", text, re.I).start()
            try:
                res = ia._generate([{"text": PROMPT.format(name=c["name"], text=text[max(0, ab - 2500): ab + 4000])}], SCHEMA, key)
                divs = [d for d in (res or {}).get("dividenden", []) if re.fullmatch(r"20\d\d-\d\d-\d\d", str(d.get("zahltag", ""))) and d.get("betrag", 0) > 0]
            except SystemExit:
                key = None; divs = None
            except Exception as e:
                fehler.append(f"{c['sym']} KI: {str(e)[:80]}"); divs = None
        if divs is None:
            continue   # spaeter erneut versuchen (KI-Grenze)
        state["erledigt"][c["acc"]] = f"{len(divs)} Dividenden"
        if divs:
            treffer += 1
            liste = daten["firmen"].setdefault(c["sym"], [])
            for d in divs:
                d.setdefault("waehrung", "USD")
                d.update({"ex_tag": d["stichtag"], "meldung": c["when"][:10], "quelle": url})
                if not any(x["zahltag"] == d["zahltag"] and abs(x["betrag"] - d["betrag"]) < 1e-6 for x in liste):
                    liste.append(d)
            liste.sort(key=lambda x: x["zahltag"])
            daten["firmen"][c["sym"]] = liste[-8:]
        time.sleep(0.3)
    daten["stand"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daten["hinweis"] = "Beschlossene Dividenden aus Pressemitteilungen der Unternehmen (SEC 8-K, EX-99). Ex-Tag = Stichtag (USA, seit Mai 2024)."
    daten["letzter_lauf"] = {"zeit": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "kandidaten": len(kand), "abgerufen": abgerufen,
                             "mit_dividende": treffer, "ki_aufrufe": ki, "fehler": fehler[:10]}
    json.dump(daten, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(daten["letzter_lauf"], "Firmen:", len(daten["firmen"]))


if __name__ == "__main__":
    main()
