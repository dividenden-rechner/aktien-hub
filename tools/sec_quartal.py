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


# Cashflow-Posten werden in 10-Q und 10-K kumuliert gemeldet (3, 6, 9 bzw. 12 Monate seit Geschaeftsjahresbeginn)
KUMULIERT = {
    "ocf": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "div": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends", "PaymentsOfOrdinaryDividends"],
}
DAUER_MONATE = [(80, 100, 3), (170, 200, 6), (260, 290, 9), (350, 380, 12)]


def kumuliert(facts, namen):
    """Liefert [start, end, dauer_monate, wert] je Meldung. Von den Konzeptnamen wird der mit dem neuesten
    Enddatum genommen (Firmen wechseln den Namen), je Zeitraum gewinnt die neueste Einreichung."""
    beste = []
    for name in namen:
        konzept = facts.get("facts", {}).get("us-gaap", {}).get(name)
        if not konzept:
            continue
        gefunden = {}
        for e in konzept.get("units", {}).get("USD", []):
            if e.get("form") not in ("10-Q", "10-K") or not e.get("start") or not e.get("end"):
                continue
            t = tage(e["start"], e["end"])
            monate = next((m for lo, hi, m in DAUER_MONATE if lo <= t <= hi), None)
            if monate is None:
                continue
            schluessel = (e["start"], e["end"])
            alt = gefunden.get(schluessel)
            if alt and alt["filed"] >= e.get("filed", ""):
                continue
            gefunden[schluessel] = {"start": e["start"], "end": e["end"], "m": monate, "wert": e["val"],
                                    "filed": e.get("filed", "")}
        if gefunden:
            liste = sorted(gefunden.values(), key=lambda x: (x["start"], x["end"]))[-16:]
            beste.append((max(x["end"] for x in liste), [[x["start"], x["end"], x["m"], x["wert"]] for x in liste]))
    return max(beste)[1] if beste else []


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
        kum = {}
        for metrik, namen in KUMULIERT.items():
            eintraege = kumuliert(facts, namen)
            if eintraege:
                kum[metrik] = eintraege
        if q or kum:
            ausgabe[ticker] = {"n": f.get("n", ""), "cik": f["cik"], "quartale": q, "kumuliert": kum}
        time.sleep(0.15)   # SEC: hoechstens etwa zehn Anfragen je Sekunde
        if i % 50 == 0:
            print(i, "Firmen verarbeitet", flush=True)
    os.makedirs("data/sec", exist_ok=True)
    json.dump({"stand": datetime.date.today().isoformat(),
               "quelle": "SEC EDGAR companyfacts (10-Q, letzte 8 Quartale)",
               "einheiten": {k: v[0] for k, v in KONZEPTE.items()},
               "kumuliert_einheit": "USD (Cashflow, kumuliert seit Geschaeftsjahresbeginn)",
               "firmen": ausgabe},
              open("data/sec/quartal.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(len(ausgabe), "Firmen mit Quartalsdaten;", len(fehler), "ohne Abruf:", ", ".join(fehler[:30]))
    if not ausgabe:
        raise SystemExit("Keine Quartalsdaten erhalten. Bitte den Secret SEC_UA mit einer Kontaktangabe setzen.")


if __name__ == "__main__":
    main()
