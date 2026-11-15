#!/usr/bin/env python3
"""US-Quartalszahlen aus data.sec.gov (companyfacts, XBRL) fuer alle Firmen aus data/sec/fundamentals.json.
Je Firma werden die letzten acht Quartale (10-Q, Q1-Q3 plus Geschaeftsjahr-Endwerte aus 10-K als Q4-Hinweis) fuer
Umsatz, Gewinn, EPS (verwaessert) und Dividende je Aktie gesammelt. Schreibt data/sec/quartal.json.
Die Abfrage braucht data.sec.gov; im Sandbox-Netz nicht erreichbar, daher laeuft sie in GitHub Actions.
Kontaktangabe fuer die SEC per Umgebungsvariable SEC_UA (z. B. 'Firmenname kontakt@domain')."""
import json, os, time, datetime, urllib.request, urllib.error

UA = os.environ.get("SEC_UA") or "dividenden-rechner.de Aktien-Hub"   # leerer Secret-Wert zählt als nicht gesetzt
QUARTALE = 8
# Reihenfolge = Prioritaet; das erste vorhandene XBRL-Konzept gewinnt je Quartal
KONZEPTE = {
    "umsatz": ("USD", ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                       "RevenuesNetOfInterestExpense"], "dauer"),
    "gewinn": ("USD", ["NetIncomeLoss", "ProfitLoss"], "dauer"),
    "eps_verw": ("USD/shares", ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"], "dauer"),
    "dividende_je_aktie": ("USD/shares", ["CommonStockDividendsPerShareDeclared",
                                          "CommonStockDividendsPerShareCashPaid"], "dauer"),
}


def hole(cik):
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
    for versuch in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(3 * (versuch + 1))
                continue
            return None
        except Exception:
            time.sleep(3 * (versuch + 1))
    return None


def tage(start, ende):
    a = datetime.date.fromisoformat(start)
    b = datetime.date.fromisoformat(ende)
    return (b - a).days


def quartale(facts, namen, einheit):
    """Sammelt 3-Monats-Werte aus 10-Q-Meldungen; neueste Einreichung gewinnt je Enddatum."""
    gefunden = {}
    for name in namen:
        konzept = (facts.get("facts", {}).get("us-gaap", {}).get(name)
                   or facts.get("facts", {}).get("dei", {}).get(name))
        if not konzept:
            continue
        for e in konzept.get("units", {}).get(einheit, []):
            if e.get("form") != "10-Q" or e.get("fp") not in ("Q1", "Q2", "Q3"):
                continue
            if not e.get("start") or not e.get("end"):
                continue
            if not 80 <= tage(e["start"], e["end"]) <= 100:
                continue
            alt = gefunden.get(e["end"])
            if alt and alt["filed"] >= e.get("filed", ""):
                continue
            gefunden[e["end"]] = {"end": e["end"], "wert": e["val"], "fp": e["fp"], "fy": e.get("fy"),
                                  "filed": e.get("filed", "")}
        if gefunden:
            break   # erstes Konzept mit Daten gewinnt
    liste = sorted(gefunden.values(), key=lambda x: x["end"])[-QUARTALE:]
    return [[x["end"], x["wert"], x["fp"], x["fy"]] for x in liste]


def main():
    fund = json.load(open("data/sec/fundamentals.json", encoding="utf-8"))["firmen"]
    ausgabe = {}
    fehler = []
    for i, (ticker, f) in enumerate(sorted(fund.items())):
        if f.get("w") != "USD" or not f.get("cik"):
            continue   # nur US-GAAP-Firmen in USD
        facts = hole(f["cik"])
        if facts is None:
            fehler.append(ticker)
            continue
        q = {}
        for metrik, (einheit, namen, _) in KONZEPTE.items():
            wert = quartale(facts, namen, einheit)
            if wert:
                q[metrik] = wert
        if q:
            ausgabe[ticker] = {"n": f.get("n", ""), "cik": f["cik"], "quartale": q}
        time.sleep(0.15)   # SEC: hoechstens etwa zehn Anfragen je Sekunde
        if i % 50 == 0:
            print(i, "Firmen verarbeitet", flush=True)
    os.makedirs("data/sec", exist_ok=True)
    json.dump({"stand": datetime.date.today().isoformat(),
               "quelle": "SEC EDGAR companyfacts (10-Q, letzte 8 Quartale)",
               "einheiten": {k: v[0] for k, v in KONZEPTE.items()},
               "firmen": ausgabe},
              open("data/sec/quartal.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(len(ausgabe), "Firmen mit Quartalsdaten;", len(fehler), "ohne Abruf:", ", ".join(fehler[:30]))
    if not ausgabe:
        raise SystemExit("Keine Quartalsdaten erhalten. Bitte den Secret SEC_UA mit einer Kontaktangabe setzen.")


if __name__ == "__main__":
    main()
