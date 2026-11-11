#!/usr/bin/env python3
"""TESTLAUF (11.11.2026): Wie viel liefern die SEC-XBRL-Daten (data.sec.gov, companyfacts) fuer 20 typische Dividendenwerte?
Je Kennzahl werden mehrere moegliche XBRL-Namen probiert, Jahreswerte aus 10-K (Zeitraum ca. 1 Jahr) bzw. Stichtagswerte genommen.
Schreibt data/sec-test.json (Zeitreihen) und data/sec-test.md (Abdeckung und Auffaelligkeiten). Aendert sonst nichts."""
import json, time, datetime, urllib.request

UA = "dividenden-rechner.de Kilian Tress dividenden.rechner@gmail.com"
TICKER = ["KO", "PEP", "PG", "JNJ", "ABBV", "PFE", "MCD", "MSFT", "AAPL", "XOM",
          "CVX", "O", "VICI", "MO", "PM", "T", "VZ", "HD", "TXN", "JPM"]
JAHRE = 10

# Kennzahl -> (Art, Einheit, moegliche XBRL-Namen in Reihenfolge)
# Art: "f" = Zeitraumwert (Jahr), "s" = Stichtagswert
K = {
    "umsatz": ("f", "USD", ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                            "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
                            "SalesRevenueGoodsNet", "RevenuesNetOfInterestExpense", "OperatingLeasesIncomeStatementLeaseRevenue",
                            "RevenuesNetOfInterestExpense"]),
    "gewinn": ("f", "USD", ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"]),
    "eps_verw": ("f", "USD/shares", ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"]),
    "dividende_je_aktie": ("f", "USD/shares", ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"]),
    "dividenden_gezahlt": ("f", "USD", ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends", "PaymentsOfOrdinaryDividends"]),
    "operativer_cf": ("f", "USD", ["NetCashProvidedByUsedInOperatingActivities",
                                   "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]),
    "capex": ("f", "USD", ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
                           "PaymentsForCapitalImprovements", "PaymentsToAcquireRealEstate"]),
    "aktienrueckkauf": ("f", "USD", ["PaymentsForRepurchaseOfCommonStock"]),
    "aktien_verw": ("f", "shares", ["WeightedAverageNumberOfDilutedSharesOutstanding"]),
    "schulden_lang": ("s", "USD", ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations",
                                   "LongTermDebtAndCapitalLeaseObligationsNoncurrent", "SeniorNotes", "UnsecuredDebt"]),
    "liquide_mittel": ("s", "USD", ["CashAndCashEquivalentsAtCarryingValue",
                                    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash"]),
    "eigenkapital": ("s", "USD", ["StockholdersEquity",
                                  "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]),
}


def get(url):
    err = ""
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            err = str(e)[:80]; time.sleep(2)
    return {"_fehler": err}


def dauer(x):
    try:
        return (datetime.date.fromisoformat(x["end"]) - datetime.date.fromisoformat(x["start"])).days
    except Exception:
        return None


def jahreswerte(cf, art, einheit, tags):
    """Liefert {Geschaeftsjahresende: (wert, tag)} aus 10-K-Angaben; erster passender Name pro Jahr gewinnt."""
    gaap = (cf.get("facts") or {}).get("us-gaap", {})
    out = {}
    for tag in tags:
        arr = (gaap.get(tag) or {}).get("units", {}).get(einheit, [])
        cand = {}
        for x in arr:
            if not str(x.get("form", "")).startswith("10-K"):
                continue
            if art == "f":
                d = dauer(x)
                if d is None or not (350 <= d <= 380):
                    continue
            end = x["end"]
            # spaeter eingereichte Angabe (z. B. angepasster Vorjahreswert) gewinnt
            if end not in cand or x.get("filed", "") > cand[end][2]:
                cand[end] = (x["val"], tag, x.get("filed", ""))
        for end, v in cand.items():
            out.setdefault(end, v[:2])
    return out


def nur_gj_enden(werte, gj_enden):
    """Stichtagswerte: nur Werte an Geschaeftsjahresenden behalten (10-K enthaelt auch Vorjahres-Stichtage)."""
    return {e: v for e, v in werte.items() if e in gj_enden} if gj_enden else werte


def main():
    tick = get("https://www.sec.gov/files/company_tickers.json")
    cikmap = {v["ticker"].upper(): (v["cik_str"], v["title"]) for v in tick.values()} if "_fehler" not in tick else {}
    heute = datetime.date.today()
    ergebnis, zeilen, notizen = {}, [], []
    for t in TICKER:
        if t not in cikmap:
            notizen.append(f"{t}: kein CIK gefunden"); continue
        cik, name = cikmap[t]
        cf = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"); time.sleep(0.2)
        if "_fehler" in cf:
            notizen.append(f"{t}: Abruf fehlgeschlagen ({cf['_fehler']})"); continue
        reihen, genutzt = {}, {}
        for k, (art, einheit, tags) in K.items():
            w = jahreswerte(cf, art, einheit, tags)
            reihen[k] = w
        # Geschaeftsjahresenden aus Umsatz/Gewinn ableiten
        gj = set(reihen["umsatz"]) | set(reihen["gewinn"])
        firma = {"name": name, "cik": cik, "kennzahlen": {}}
        zeile = {"ticker": t}
        for k, w in reihen.items():
            if K[k][0] == "s":
                w = nur_gj_enden(w, gj)
            enden = sorted(w)[-JAHRE:]
            firma["kennzahlen"][k] = [{"ende": e, "wert": w[e][0], "xbrl": w[e][1]} for e in enden]
            genutzt[k] = sorted({w[e][1] for e in enden})
            if not enden:
                zeile[k] = "–"
            else:
                letzt = enden[-1]
                alt = (heute - datetime.date.fromisoformat(letzt)).days
                zeile[k] = f"{len(enden)} J. bis {letzt[:4]}" + (" (alt)" if alt > 500 else "")
        # Plausibilitaet
        kz = firma["kennzahlen"]
        def letzter(k):
            return kz[k][-1]["wert"] if kz[k] else None
        flags = []
        eps, dps = letzter("eps_verw"), letzter("dividende_je_aktie")
        if eps and dps:
            q = dps / eps if eps else None
            if q is not None and not (0 < q < 3):
                flags.append(f"Ausschüttungsquote {q:.0%} auffällig")
        if letzter("umsatz") is not None and letzter("umsatz") <= 0:
            flags.append("Umsatz ≤ 0")
        if letzter("operativer_cf") and letzter("capex"):
            firma["fcf_letztes_jahr"] = letzter("operativer_cf") - letzter("capex")
        if len({len(kz[k]) for k in ("umsatz", "gewinn", "operativer_cf") if kz[k]}) > 1:
            flags.append("ungleich lange Reihen")
        firma["xbrl_namen"] = genutzt
        firma["auffaellig"] = flags
        zeile["auffällig"] = "; ".join(flags) or "–"
        ergebnis[t] = firma
        zeilen.append(zeile)

    json.dump({"stand": heute.isoformat(), "quelle": "SEC EDGAR companyfacts (XBRL)", "firmen": ergebnis},
              open("data/sec-test.json", "w"), ensure_ascii=False, indent=1)

    spalten = ["ticker"] + list(K) + ["auffällig"]
    md = [f"# SEC-Test: Abdeckung für {len(TICKER)} Dividendenwerte (Stand {heute.isoformat()})", "",
          f"Je Kennzahl: Anzahl Geschäftsjahre (max. {JAHRE}) und letztes Jahr. „alt“ = letzter Wert älter als rund 16 Monate.", "",
          "| " + " | ".join(spalten) + " |", "|" + "---|" * len(spalten)]
    for z in zeilen:
        md.append("| " + " | ".join(str(z.get(s, "")) for s in spalten) + " |")
    md += ["", "## Genutzte XBRL-Namen je Firma", ""]
    for t, f in ergebnis.items():
        teile = [f"{k}: {', '.join(v) or '–'}" for k, v in f["xbrl_namen"].items()]
        md.append(f"- **{t}** – " + "; ".join(teile))
    md += ["", "## Beispiel: letzte drei Jahre", ""]
    for t, f in ergebnis.items():
        kz = f["kennzahlen"]
        def fm(k):
            return " / ".join(f"{x['ende'][:4]}: {x['wert']:,.2f}" if abs(x['wert']) < 1000 else f"{x['ende'][:4]}: {x['wert']/1e9:,.1f} Mrd."
                              for x in kz[k][-3:]) or "–"
        md.append(f"- **{t}** Umsatz {fm('umsatz')} · Gewinn {fm('gewinn')} · Dividende/Aktie {fm('dividende_je_aktie')}")
    if notizen:
        md += ["", "## Hinweise", ""] + [f"- {n}" for n in notizen]
    open("data/sec-test.md", "w").write("\n".join(md) + "\n")
    print("\n".join(md[:30]))


if __name__ == "__main__":
    main()
