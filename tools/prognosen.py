#!/usr/bin/env python3
"""Unternehmensprognosen (ab 11.11.2026): liest die Ergebnis-Pressemitteilungen (8-K Punkt 2.02, Anlage EX-99) der Firmen aus
data/sec/fundamentals.json und zieht den Ausblick heraus (Gewinn je Aktie, Umsatz, Dividende ... fuer ein Geschaeftsjahr).
Das ist die eigene Prognose der Firma, keine Analystenschaetzung. Je Firma zaehlt die neueste Meldung mit Ausblick.
KI: Gemini (kostenlos), Ausweich Groq, wie beim IR-Agenten. Schreibt data/prognosen.json, Merkliste data/prognosen-state.json."""
import json, os, re, sys, time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
# Die SEC verlangt im User-Agent eine Kontaktangabe, sonst sperrt www.sec.gov mit 403. Wir nehmen dieselbe wie der SEC-Datenlauf.
if not os.environ.get("SEC_USER_AGENT"):
    import sec_fundamentals as _sf
    os.environ["SEC_USER_AGENT"] = _sf.UA
import ir_agent as ia
import kurzmeldungen as km

TAGE = int(os.environ.get("PROGNOSE_TAGE", "120"))        # so weit zurueck nach Ergebnismeldungen suchen
MAX_KI = int(os.environ.get("PROGNOSE_MAX_KI", "60"))     # KI-Aufrufe je Lauf (Gratis-Kontingent schonen)
OUT, STATE = "data/prognosen.json", "data/prognosen-state.json"
VOR = re.compile(r"(outlook|guidance|expects?|expected|anticipates?|reaffirm|raises?|raising|lowers?|forecast|full[- ]year|fiscal (year )?20\d\d)", re.I)
ZAHL = re.compile(r"(per share|EPS|revenue|net sales|sales growth|free cash flow|dividend)", re.I)

SCHEMA = {"type": "OBJECT", "properties": {
    "hat_prognose": {"type": "BOOLEAN"},
    "prognosen": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "kennzahl": {"type": "STRING", "enum": ["eps_bereinigt", "eps_gaap", "umsatz", "umsatzwachstum_proz", "organisches_wachstum_proz",
                                                 "fcf", "dividende_je_aktie", "operative_marge_proz", "sonstiges"]},
        "geschaeftsjahr": {"type": "STRING"}, "von": {"type": "NUMBER"}, "bis": {"type": "NUMBER"},
        "einheit": {"type": "STRING"}, "veraendert": {"type": "STRING", "enum": ["neu", "angehoben", "gesenkt", "bestaetigt", "unklar"]},
        "beleg": {"type": "STRING"}},
        "required": ["kennzahl", "geschaeftsjahr", "von", "bis", "einheit", "veraendert", "beleg"]}}},
    "required": ["hat_prognose", "prognosen"]}

PROMPT = """Du liest die Ergebnis-Pressemitteilung von {name} ({sym}). Ziehe NUR den Ausblick heraus, den das Unternehmen selbst
fuer ein kommendes oder laufendes Geschaeftsjahr gibt (Gewinn je Aktie bereinigt oder nach GAAP, Umsatz absolut, Umsatz- oder
organisches Wachstum in Prozent, freier Cashflow, Dividende je Aktie, operative Marge). Keine Ist-Zahlen, keine Quartalsprognosen,
keine Analystenschaetzungen. Einzelwert: von = bis. Betraege in der Waehrung der Meldung, Umsatz und FCF als volle Zahl
(z. B. 19,5 Mrd. = 19500000000), Prozente als Zahl (3 % = 3). geschaeftsjahr als vierstellige Jahreszahl des Geschaeftsjahres,
wie das Unternehmen es nennt (fiscal 2027 = 2027). veraendert: ob die Prognose neu, angehoben, gesenkt oder bestaetigt wurde.
beleg: der kurze Originalsatz (hoechstens 25 Woerter). Gibt es keinen Ausblick, hat_prognose = false und leere Liste.

Text:
{text}"""


def lade(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def kandidaten(firmen, erledigt):
    """Neueste Ergebnismeldung (8-K Punkt 2.02) je Firma aus den letzten TAGE Tagen, noch nicht ausgewertet."""
    grenze = datetime.now(timezone.utc) - timedelta(days=TAGE)
    out = []
    for t, f in firmen.items():
        if f.get("std") == "IFRS":
            continue   # Auslandsfirmen melden per 6-K ohne Punktnummern, spaeter
        try:
            sub = json.loads(ia.http(f"https://data.sec.gov/submissions/CIK{int(f['cik']):010d}.json", ua=km.UA_HDR, timeout=30))
            rec = sub["filings"]["recent"]
        except Exception:
            time.sleep(0.15); continue
        for j, form in enumerate(rec.get("form", [])[:60]):
            if form != "8-K" or "2.02" not in (rec.get("items", [""] * 999)[j] or ""):
                continue
            acc = rec["accessionNumber"][j]
            dt = km._parse_dt(rec["acceptanceDateTime"][j]) if rec.get("acceptanceDateTime") else None
            if dt and dt < grenze:
                break
            if acc not in erledigt:
                out.append({"sym": t, "name": f["n"], "cik": int(f["cik"]), "acc": acc, "when": dt.isoformat() if dt else "",
                            "primary": (rec.get("primaryDocument") or [""] * 999)[j], "fpi": False})
            break   # nur die neueste Ergebnismeldung je Firma
        time.sleep(0.3)   # SEC drosselt bei schnellen Serienabrufen (Fehler 403)
    out.sort(key=lambda c: c["when"], reverse=True)
    return out


def main():
    firmen = lade("data/sec/fundamentals.json", {}).get("firmen", {})
    state = lade(STATE, {"erledigt": {}})
    daten = lade(OUT, {"firmen": {}})
    try:
        key = ia.api_key()
    except SystemExit as e:
        key = None; print("Kein Gemini-Schluessel:", e)
    kand = kandidaten(firmen, state["erledigt"])
    print(len(kand), "neue Ergebnismeldungen")
    ki, abbruch, fehler = 0, "", []
    for c in kand:
        if ki >= MAX_KI:
            print("KI-Grenze je Lauf erreicht, Rest beim naechsten Lauf"); break
        r = None
        try:
            for versuch in range(3):
                try:
                    r = km.edgar_press_release(c); break
                except Exception as e:
                    if "403" in str(e) and versuch < 2:
                        time.sleep(60); continue   # SEC-Sperre kurz abwarten
                    raise
        except Exception as e:
            fehler.append(f"{c['sym']} Meldung: {str(e)[:80]}"); print(c["sym"], "Meldung nicht ladbar:", str(e)[:80]); continue
        if not r:
            state["erledigt"][c["acc"]] = "ohne Anlage"; continue
        text, url = r
        if not (VOR.search(text) and ZAHL.search(text)):
            state["erledigt"][c["acc"]] = "kein Ausblick (Vorfilter)"; continue
        # Den Ausblick-Teil bevorzugen: ab dem ersten Treffer von outlook/guidance, sonst Textanfang
        m = re.search(r"(outlook|guidance)", text, re.I)
        teil = text[max(0, m.start() - 1500): m.start() + 9000] if m else text[:10000]
        ki += 1
        try:
            res = ia._generate([{"text": PROMPT.format(name=c["name"], sym=c["sym"], text=teil)}], SCHEMA, key)
        except SystemExit as e:
            abbruch = "KI nicht verfuegbar: " + str(e)[:200]; print(abbruch); break
        except Exception as e:
            fehler.append(f"{c['sym']}: {str(e)[:100]}"); print(c["sym"], "KI-Fehler:", str(e)[:100]); continue
        progs = [p for p in (res or {}).get("prognosen", []) if isinstance(p.get("von"), (int, float)) and isinstance(p.get("bis"), (int, float))
                 and re.fullmatch(r"20\d\d", str(p.get("geschaeftsjahr", "")))]
        state["erledigt"][c["acc"]] = f"{len(progs)} Prognosen"
        if progs:
            alt = daten["firmen"].get(c["sym"])
            if not alt or alt.get("datum", "") <= c["when"][:10]:
                daten["firmen"][c["sym"]] = {"datum": c["when"][:10], "quelle": url, "prognosen": progs}
        print(c["sym"], c["when"][:10], len(progs), "Prognosen")
        time.sleep(1.5)
    daten["stand"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daten["letzter_lauf"] = {"zeit": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "kandidaten": len(kand), "ki_aufrufe": ki,
                             "abbruch": abbruch, "fehler": fehler[:10]}
    daten["hinweis"] = "Eigene Prognosen der Unternehmen aus ihren Ergebnis-Pressemitteilungen (SEC 8-K, Anlage EX-99), automatisch ausgelesen. Keine Analystenschaetzungen."
    json.dump(daten, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("Firmen mit Prognose:", len(daten["firmen"]), "| KI-Aufrufe:", ki)


if __name__ == "__main__":
    main()
