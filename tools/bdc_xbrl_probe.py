"""PROBE: Welche BDC-Kennzahlen gibt es in den SEC-XBRL-Daten (kostenlos, ohne KI), und wie weit reicht die Quartalshistorie?
Ausgabe: data/bdc-xbrl-probe.json"""
import csv, datetime as dt, json, time, urllib.request

UA = "dividenden-rechner.de Datensammlung (https://www.dividenden-rechner.de/impressum/)"
TAGS = ["NetAssetValuePerShare", "InvestmentCompanyNetInvestmentIncomePerShare", "NetInvestmentIncome",
        "CommonStockDividendsPerShareDeclared", "InvestmentOwnedAtFairValue", "DebtInstrumentCarryingAmount",
        "InvestmentIncomePaymentInKind", "NetAssetsNetIncrease", "DebtToEquityRatio"]

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.loads(r.read())

tick = get("https://www.sec.gov/files/company_tickers.json")
cik = {v["ticker"].upper(): v["cik_str"] for v in tick.values()}
symbole = [r["sec_ticker"] or r["ticker"] for r in csv.DictReader(open("data/bdc-seed.csv", encoding="utf-8"))]
ergebnis = {}
for sym in symbole:
    c = cik.get(sym.upper())
    if not c:
        ergebnis[sym] = {"fehler": "keine CIK"}; continue
    try:
        facts = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(c):010d}.json")
        time.sleep(0.2)
        gaap = facts.get("facts", {}).get("us-gaap", {})
        eigene = facts.get("facts", {})
        out = {}
        for t in TAGS:
            src = gaap.get(t) or None
            if src is None:
                # eigene Erweiterungen (Firmenpraefix) zu diesem Namen suchen
                for ns, fx in eigene.items():
                    if ns != "us-gaap" and t in fx:
                        src = fx[t]; break
            if src:
                werte = []
                for unit in src.get("units", {}).values():
                    werte += [x for x in unit if x.get("form") in ("10-Q", "10-K") and x.get("end")]
                enden = sorted({x["end"] for x in werte})
                out[t] = {"anzahl": len(werte), "erstes_ende": enden[0] if enden else None, "letztes_ende": enden[-1] if enden else None}
        ergebnis[sym] = out or {"hinweis": "keine der Kennzahlen gefunden"}
    except Exception as e:
        ergebnis[sym] = {"fehler": str(e)[:150]}
json.dump({"stand": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "firmen": ergebnis}, open("data/bdc-xbrl-probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(ergebnis), "Firmen geprueft")
