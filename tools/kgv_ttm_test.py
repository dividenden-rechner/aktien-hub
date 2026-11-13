"""TESTLAUF: KGV auf Basis der letzten vier Quartale (TTM) fuer die Top-20-US-Firmen mit hoher Marge.

Rechnung: TTM-Gewinn je Aktie = letztes Geschaeftsjahr + Jahresbeginn bis heute (laufendes Jahr)
          - Jahresbeginn bis zum selben Stichtag im Vorjahr. Quelle: SEC EDGAR companyfacts (XBRL).
Vergleich mit dem bisherigen Hub-KGV (letztes Geschaeftsjahr).
Ausgabe: data/kgv-ttm-test.json und data/kgv-ttm-test.md
"""
import json, time, datetime as dt, urllib.request

UA = "dividenden-rechner.de Datensammlung (https://www.dividenden-rechner.de/impressum/)"
H = json.load(open("data/kennzahlen.json", encoding="utf-8"))["werte"]
SEC = json.load(open("data/sec/fundamentals.json", encoding="utf-8"))["firmen"]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def d(s):
    return dt.date.fromisoformat(s)

def tage(a, b):
    return (d(b) - d(a)).days

def eps_reihe(facts):
    for name in ("EarningsPerShareDiluted", "EarningsPerShareBasic"):
        try:
            return facts["facts"]["us-gaap"][name]["units"]["USD/shares"]
        except KeyError:
            continue
    return None

def ttm(u):
    jahre = [x for x in u if x.get("form") in ("10-K", "10-K/A") and x.get("fp") == "FY" and 340 <= tage(x["start"], x["end"]) <= 380]
    if not jahre:
        return None, "kein Jahreswert"
    fy = max(jahre, key=lambda x: x["end"])
    ytd = [x for x in u if x.get("form") in ("10-Q", "10-Q/A") and x.get("start") == fy["start"] and tage(x["start"], x["end"]) >= 80 and x["end"] > fy["end"]]
    if not ytd:
        return fy["val"], "nur Jahreswert (kein neues Quartal)"
    cur = max(ytd, key=lambda x: x["end"])
    vor_start = (d(fy["start"]) - dt.timedelta(days=365)).isoformat()
    vor_end = (d(cur["end"]) - dt.timedelta(days=365)).isoformat()
    vor = [x for x in u if x.get("start") and abs(tage(x["start"], vor_start)) <= 10 and abs(tage(x["end"], vor_end)) <= 10]
    if not vor:
        return None, "Vorjahresquartal fehlt"
    v = max(vor, key=lambda x: x["end"])
    return fy["val"] + cur["val"] - v["val"], f"bis {cur['end']}"

# Top 20 US-Firmen nach operativer Marge (Hub-Daten), dazu Kontrolle NVDA und AVGO
kandidaten = [(t, f) for t, f in H.items() if f.get("land") == "US" and f.get("operative_marge") is not None and t in SEC and SEC[t].get("cik")]
kandidaten.sort(key=lambda x: -x[1]["operative_marge"])
top = kandidaten[:20]
for kontrolle in ("NVDA", "AVGO"):
    if kontrolle in H and kontrolle in SEC and not any(t == kontrolle for t, _ in top):
        top.append((kontrolle, H[kontrolle]))

ergebnis = []
for t, f in top:
    cik = int(SEC[t]["cik"])
    try:
        facts = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
        time.sleep(0.2)
        u = eps_reihe(facts)
        wert, info = ttm(u) if u else (None, "keine EPS-Reihe")
    except Exception as e:
        wert, info = None, f"Fehler: {e}"
    kurs = f.get("kurs_usd")
    kgv_ttm = round(kurs / wert, 1) if wert and wert > 0 and kurs else None
    ergebnis.append({"symbol": t, "name": f.get("name"), "kurs_usd": kurs, "kgv_hub": f.get("kgv"),
                     "eps_ttm": round(wert, 2) if wert is not None else None, "kgv_ttm": kgv_ttm,
                     "stand": info, "operative_marge": f.get("operative_marge")})

stand = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
json.dump({"stand": stand, "firmen": ergebnis}, open("data/kgv-ttm-test.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
zeilen = ["| Symbol | Firma | Kurs USD | KGV Hub (Jahr) | EPS TTM | KGV TTM | Stand |", "|---|---|---:|---:|---:|---:|---|"]
for e in ergebnis:
    zeilen.append(f"| {e['symbol']} | {e['name']} | {e['kurs_usd']} | {e['kgv_hub']} | {e['eps_ttm']} | {e['kgv_ttm']} | {e['stand']} |")
open("data/kgv-ttm-test.md", "w", encoding="utf-8").write(f"# KGV-Test TTM (Stand {stand})\n\n" + "\n".join(zeilen) + "\n")
print("\n".join(zeilen))
