#!/usr/bin/env python3
"""BDC-Daten (ab 11.11.2026): liest aus den Quartals-Pressemitteilungen der BDCs (SEC 8-K Punkt 2.02, Anlage EX-99) je Quartal
NAV je Aktie, Nettoanlageergebnis (NII) je Aktie, beschlossene Dividenden, Portfoliowert, Non-Accruals und Verschuldung.
Die Werte werden dauerhaft gespeichert (wie bei BDCInvestor); Kurs/NAV und Renditen rechnet kennzahlen.py taeglich mit dem Kurs.
Liste der BDCs: data/bdc-seed.csv. Schreibt data/bdc.json und data/bdc-state.json."""
import csv, json, os, re, sys, time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
# Die SEC verlangt im User-Agent eine Kontaktangabe, sonst sperrt www.sec.gov mit 403. Wir nehmen dieselbe wie der SEC-Datenlauf.
if not os.environ.get("SEC_USER_AGENT"):
    import sec_fundamentals as _sf
    os.environ["SEC_USER_AGENT"] = _sf.UA
import ir_agent as ia
import kurzmeldungen as km

TAGE = int(os.environ.get("BDC_TAGE", "800"))          # rund acht Quartale zurueck
MAX_KI = int(os.environ.get("BDC_MAX_KI", "50"))
ZEITBUDGET = int(os.environ.get("ZEITBUDGET_MIN", "35")) * 60   # danach sauber aufhoeren und speichern (Job-Limit 60 Min.)
START = time.time()
OUT, STATE = "data/bdc.json", "data/bdc-state.json"

SCHEMA = {"type": "OBJECT", "properties": {
    "periode_ende": {"type": "STRING"}, "nav_je_aktie": {"type": "NUMBER"}, "nii_je_aktie": {"type": "NUMBER"},
    "nii_bereinigt_je_aktie": {"type": "NUMBER"}, "dividende_regulaer": {"type": "NUMBER"}, "dividende_zusatz": {"type": "NUMBER"},
    "dividende_quartal": {"type": "STRING"}, "portfolio_mio": {"type": "NUMBER"}, "non_accrual_fv_proz": {"type": "NUMBER"},
    "verschuldung_netto": {"type": "NUMBER"}, "beleg_nav": {"type": "STRING"}},
    "required": ["periode_ende", "nav_je_aktie", "nii_je_aktie"]}
PROMPT = """Quartalsmeldung der BDC {name} ({sym}). Lies die Zahlen fuer das berichtete Quartal aus (nicht Vorjahr, nicht Gesamtjahr):
periode_ende = Quartalsende als JJJJ-MM-TT; nav_je_aktie = Net asset value per share zum Quartalsende; nii_je_aktie = Net investment
income per share (GAAP) im Quartal; nii_bereinigt_je_aktie = bereinigtes/core NII je Aktie, falls angegeben, sonst 0;
dividende_regulaer = beschlossene regulaere Dividende je Aktie fuer das naechste Quartal (bei Monatszahlern: Summe der Monate eines
Quartals), dividende_zusatz = beschlossene Zusatz-/Sonderdividende je Aktie (sonst 0), dividende_quartal = fuer welches Quartal
(z. B. "Q1 2027"); portfolio_mio = Fair Value des Portfolios in Mio. USD; non_accrual_fv_proz = Non-Accruals in % vom Portfolio zum
Fair Value (sonst 0); verschuldung_netto = Netto-Verschuldung Schulden/Eigenkapital als Faktor (z. B. 1.05; sonst 0);
beleg_nav = Originalsatz zum NAV (hoechstens 25 Woerter). Fehlt ein Wert: 0.

Text:
{text}"""


def lade(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def main():
    seed = [r["sec_ticker"].upper() for r in csv.DictReader(open("data/bdc-seed.csv"))]
    tick = json.loads(ia.http("https://www.sec.gov/files/company_tickers.json", ua=km.UA_HDR))
    by = {v["ticker"].upper(): v for v in tick.values()}
    state = lade(STATE, {"erledigt": {}})
    daten = lade(OUT, {"firmen": {}})
    key = ia.api_key()
    grenze = datetime.now(timezone.utc) - timedelta(days=TAGE)
    kand, fehlt = [], []
    for t in seed:
        v = by.get(t)
        if not v:
            fehlt.append(t); continue
        try:
            rec = json.loads(ia.http(f"https://data.sec.gov/submissions/CIK{int(v['cik_str']):010d}.json", ua=km.UA_HDR, timeout=30))["filings"]["recent"]
        except Exception:
            fehlt.append(t); time.sleep(0.3); continue
        daten["firmen"].setdefault(t, {"name": v["title"], "quartale": []})
        for j, form in enumerate(rec.get("form", [])[:120]):
            if form != "8-K" or "2.02" not in (rec.get("items", [""] * 999)[j] or ""):
                continue
            dt = km._parse_dt(rec["acceptanceDateTime"][j]) if rec.get("acceptanceDateTime") else None
            if dt and dt < grenze:
                break
            acc = rec["accessionNumber"][j]
            if acc not in state["erledigt"]:
                kand.append({"sym": t, "name": v["title"], "cik": int(v["cik_str"]), "acc": acc, "when": dt.isoformat() if dt else "",
                             "primary": (rec.get("primaryDocument") or [""] * 999)[j], "fpi": False})
        time.sleep(0.3)
    kand.sort(key=lambda c: c["when"], reverse=True)   # neueste zuerst, Historie folgt in spaeteren Laeufen
    print(len(kand), "Meldungen offen")
    ki, fehler = 0, []
    for c in kand:
        if time.time() - START > ZEITBUDGET:
            print("Zeitbudget erreicht, Rest beim naechsten Lauf"); break
        if ki >= MAX_KI:
            break
        try:
            r = None
            for v_ in range(3):
                try:
                    r = km.edgar_press_release(c); break
                except Exception as e:
                    if "403" in str(e) and v_ < 2:
                        time.sleep(60); continue
                    raise
        except Exception as e:
            fehler.append(f"{c['sym']}: {str(e)[:80]}"); continue
        if not r:
            state["erledigt"][c["acc"]] = "ohne Anlage"; continue
        text, url = r
        if not re.search(r"net asset value", text, re.I):
            state["erledigt"][c["acc"]] = "kein NAV"; continue
        i = re.search(r"net asset value", text, re.I).start()
        teil = text[max(0, i - 3000): i + 9000]
        ki += 1
        try:
            q = ia._generate([{"text": PROMPT.format(name=c["name"], sym=c["sym"], text=teil)}], SCHEMA, key)
        except SystemExit:
            break
        except Exception as e:
            fehler.append(f"{c['sym']} KI: {str(e)[:80]}"); continue
        if not q or not re.fullmatch(r"20\d\d-\d\d-\d\d", str(q.get("periode_ende", ""))) or not (q.get("nav_je_aktie") or 0) > 0:
            state["erledigt"][c["acc"]] = "nicht lesbar"; continue
        q = {k: v for k, v in q.items() if v not in (None, "")}
        q.update({"meldung": c["when"][:10], "quelle": url})
        qs = [x for x in daten["firmen"][c["sym"]]["quartale"] if x["periode_ende"] != q["periode_ende"]]
        qs.append(q); qs.sort(key=lambda x: x["periode_ende"])
        daten["firmen"][c["sym"]]["quartale"] = qs[-12:]
        state["erledigt"][c["acc"]] = q["periode_ende"]
        print(c["sym"], q["periode_ende"], "NAV", q.get("nav_je_aktie"), "NII", q.get("nii_je_aktie"))
        time.sleep(1.5)
    daten["stand"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daten["hinweis"] = "Quartalszahlen der BDCs aus ihren Ergebnis-Pressemitteilungen (SEC 8-K, EX-99), automatisch ausgelesen."
    daten["letzter_lauf"] = {"zeit": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "offen": len(kand), "ki_aufrufe": ki,
                             "ohne_sec": fehlt, "fehler": fehler[:10]}
    json.dump(daten, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(daten["letzter_lauf"])


if __name__ == "__main__":
    main()
