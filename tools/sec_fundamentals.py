#!/usr/bin/env python3
"""SEC-Fundamentaldaten (ab 11.11.2026): Jahreszahlen aus data.sec.gov (companyfacts, XBRL) fuer alle US-Firmen aus
data/universe.json (S&P 500) plus Zusatzliste. Je Kennzahl werden mehrere XBRL-Namen probiert; fehlt der neueste Jahreswert,
sucht ein Suchmuster ueber alle Namen der Firma nach einem aktuelleren Ersatz (Firmen wechseln ihre Bezeichnungen).
Schreibt data/sec/fundamentals.json (kompakt, je Firma Zeitreihen) und data/sec-abdeckung.md (Abdeckung, Luecken).
US-Behoerdendaten sind frei nutzbar; Kurse, FFO/AFFO und Nicht-US-Firmen kommen hier nicht vor."""
import json, os, re, time, datetime, urllib.request

UA = "dividenden-rechner.de Kilian Tress dividenden.rechner@gmail.com"
JAHRE = 10
# Zusaetzliche US-Werte ausserhalb des S&P 500 (Ticker -> CIK leer = aus SEC-Tickerliste)
ZUSATZ = {"VICI": None, "MAIN": None, "ARCC": None, "ADC": None, "STAG": None, "EPD": None, "ET": None}
# Feste Zuordnung, wo die SEC-Tickerliste auf eine falsche Gesellschaft zeigt
CIK_FEST = {"XOM": 34088}

K = {
    "umsatz": ("f", "USD", ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                            "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
                            "SalesRevenueGoodsNet", "RevenuesNetOfInterestExpense", "OperatingLeasesIncomeStatementLeaseRevenue"],
               r"^(Revenues|RevenueFromContractWithCustomer\w*|SalesRevenue\w*|RevenuesNetOfInterestExpense)$"),
    "gewinn": ("f", "USD", ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"],
               r"^(NetIncomeLoss\w*|ProfitLoss)$"),
    "eps_verw": ("f", "USD/shares", ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
                 r"^EarningsPerShare(Diluted|BasicAndDiluted)$"),
    "dividende_je_aktie": ("f", "USD/shares", ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"],
                           r"^(CommonStockDividendsPerShare\w*|DistributionMadeToLimitedPartnerDistributionsPaidPerUnit|DistributionMadeToLimitedPartnerDistributionsDeclaredPerUnit)$"),
    "dividenden_gezahlt": ("f", "USD", ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends", "PaymentsOfOrdinaryDividends"],
                           r"^(PaymentsOf\w*Dividends\w*|PaymentsOfDistributionsToAffiliates|DistributionMadeToLimitedPartnerCashDistributionsPaid)$"),
    "operativer_cf": ("f", "USD", ["NetCashProvidedByUsedInOperatingActivities",
                                   "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
                      r"^NetCashProvidedByUsedInOperatingActivities\w*$"),
    "capex": ("f", "USD", ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
                           "PaymentsForCapitalImprovements", "PaymentsToAcquireRealEstate"],
              r"^(PaymentsToAcquire(PropertyPlantAndEquipment|ProductiveAssets|OtherPropertyPlantAndEquipment|RealEstate|OilAndGasPropertyAndEquipment|OilAndGasProperty)\w*|PaymentsForCapitalImprovements|PaymentsToDevelopRealEstateAssets)$"),
    "aktienrueckkauf": ("f", "USD", ["PaymentsForRepurchaseOfCommonStock"],
                        r"^PaymentsForRepurchaseOf(CommonStock|Equity)\w*$"),
    "aktien_verw": ("f", "shares", ["WeightedAverageNumberOfDilutedSharesOutstanding"],
                    r"^WeightedAverageNumberOf(DilutedSharesOutstanding|SharesOutstandingBasicAndDiluted)$"),
    "schulden_lang": ("s", "USD", ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations",
                                   "LongTermDebtAndCapitalLeaseObligationsNoncurrent", "SeniorNotes", "UnsecuredDebt"],
                      r"^(LongTermDebt\w*|SeniorNotes\w*|UnsecuredDebt\w*|SecuredDebt\w*|NotesPayable\w*|LongTermNotesPayable\w*|DebtInstrumentCarryingAmount|DebtLongtermAndShorttermCombinedAmount|OtherLongTermDebt\w*)$"),
    "liquide_mittel": ("s", "USD", ["CashAndCashEquivalentsAtCarryingValue",
                                    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash"],
                       r"^(CashAndCashEquivalentsAtCarryingValue|CashCashEquivalentsRestrictedCash\w*|Cash|CashAndDueFromBanks)$"),
    "eigenkapital": ("s", "USD", ["StockholdersEquity",
                                  "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
                     r"^(StockholdersEquity\w*|PartnersCapital\w*|MembersEquity)$"),
}
# Diese Namen passen zwar auf ein Suchmuster, meinen aber etwas anderes
SPERRE = re.compile(r"(PerShare|Percentage|Remaining|Deferred|Unbilled|Fees|Interest(Expense|Paid)|Current$|Maturities|Repayments|Proceeds|FairValue|Increase|Decrease|Gain|Tax)", re.I)
KERN = ["umsatz", "gewinn", "eps_verw", "dividende_je_aktie", "operativer_cf"]


def get(url):
    err = ""
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except Exception as e:
            err = str(e)[:80]; time.sleep(2)
    return {"_fehler": err}


def dauer(x):
    try:
        return (datetime.date.fromisoformat(x["end"]) - datetime.date.fromisoformat(x["start"])).days
    except Exception:
        return None


def werte_eines_namens(gaap, tag, art, einheit):
    cand = {}
    for x in (gaap.get(tag) or {}).get("units", {}).get(einheit, []):
        if not str(x.get("form", "")).startswith("10-K"):
            continue
        if art == "f":
            d = dauer(x)
            if d is None or not (350 <= d <= 380):
                continue
        end = x["end"]
        if end not in cand or x.get("filed", "") > cand[end][2]:
            cand[end] = (x["val"], tag, x.get("filed", ""))
    return {e: v[:2] for e, v in cand.items()}


def reihe(gaap, art, einheit, tags):
    out = {}
    for tag in tags:
        for e, v in werte_eines_namens(gaap, tag, art, einheit).items():
            out.setdefault(e, v)
    return out


def ersatz_suchen(gaap, art, einheit, muster, schon, ziel_ende):
    """Sucht unter allen Namen der Firma einen, der das Muster trifft und bis ziel_ende reicht."""
    best = None
    for tag in gaap:
        if tag in schon or not re.match(muster, tag) or SPERRE.search(tag):
            continue
        w = werte_eines_namens(gaap, tag, art, einheit)
        if not w or max(w) < ziel_ende:
            continue
        # Bei Schulden lieber den groessten Gesamtwert, sonst den mit der laengsten Reihe
        wert = abs(w[max(w)][0]) if art == "s" else len(w)
        if best is None or wert > best[0]:
            best = (wert, tag, w)
    return best


def main():
    heute = datetime.date.today()
    uni = json.load(open("data/universe.json"))["firmen"]
    liste = {f["sym"].upper(): (f.get("cik"), f.get("name")) for f in uni}
    tick = get("https://www.sec.gov/files/company_tickers.json")
    cikmap = {v["ticker"].upper(): (v["cik_str"], v["title"]) for v in tick.values()} if "_fehler" not in tick else {}
    for t in ZUSATZ:
        liste.setdefault(t, (cikmap.get(t, (None, t))[0], cikmap.get(t, (None, t))[1]))
    for t, c in CIK_FEST.items():
        if t in liste:
            liste[t] = (c, liste[t][1])

    firmen, notizen, ersatz_log = {}, [], []
    stat = {k: {"da": 0, "aktuell": 0} for k in K}
    for i, (t, (cik, name)) in enumerate(sorted(liste.items())):
        if not cik and t in cikmap:
            cik = cikmap[t][0]
        if not cik:
            notizen.append(f"{t}: keine CIK"); continue
        cf = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"); time.sleep(0.12)
        if "_fehler" in cf:
            notizen.append(f"{t}: Abruf fehlgeschlagen ({cf['_fehler']})"); continue
        gaap = (cf.get("facts") or {}).get("us-gaap", {})
        if not gaap:
            notizen.append(f"{t}: keine us-gaap-Daten (CIK {cik})"); continue
        reihen = {k: reihe(gaap, a, e, tags) for k, (a, e, tags, _) in K.items()}
        enden = set(reihen["umsatz"]) | set(reihen["gewinn"])
        if not enden:
            notizen.append(f"{t}: keine Jahreswerte"); continue
        letztes_gj = max(enden)
        for k, (a, e, tags, muster) in K.items():
            w = reihen[k]
            if not w or max(w) < letztes_gj:
                b = ersatz_suchen(gaap, a, e, muster, set(tags), letztes_gj)
                if b:
                    for end, v in b[2].items():
                        w.setdefault(end, v)
                    ersatz_log.append(f"{t} {k}: {b[1]}")
            if a == "s":
                w = {end: v for end, v in w.items() if end in enden}
            reihen[k] = w
        fa = {"n": cf.get("entityName") or name, "cik": int(cik), "gj": letztes_gj, "k": {}}
        for k, w in reihen.items():
            ends = sorted(w)[-JAHRE:]
            if ends:
                fa["k"][k] = [[e, w[e][0]] for e in ends]
                stat[k]["da"] += 1
                if ends[-1] >= letztes_gj:
                    stat[k]["aktuell"] += 1
        firmen[t] = fa
        if i % 50 == 0:
            print(i, t, flush=True)

    os.makedirs("data/sec", exist_ok=True)
    json.dump({"stand": heute.isoformat(), "quelle": "SEC EDGAR companyfacts (XBRL), US-Behördendaten",
               "einheiten": {k: v[1] for k, v in K.items()}, "firmen": firmen},
              open("data/sec/fundamentals.json", "w"), ensure_ascii=False, separators=(",", ":"))

    n = len(firmen)
    voll = [t for t, f in firmen.items() if all(k in f["k"] and f["k"][k][-1][0] >= f["gj"] for k in KERN)]
    md = [f"# SEC-Fundamentaldaten: Abdeckung (Stand {heute.isoformat()})", "",
          f"Firmen mit Daten: **{n}** von {len(liste)}. Kernkennzahlen (Umsatz, Gewinn, EPS, Dividende je Aktie, operativer Cashflow) "
          f"vollständig und aktuell: **{len(voll)}**.", "",
          "„Aktuell“ heißt: Wert für das letzte Geschäftsjahr der Firma vorhanden. Firmen ohne Dividende fehlen bei der Dividende zu Recht.", "",
          "| Kennzahl | mit Daten | davon aktuell |", "|---|---:|---:|"]
    for k, s in stat.items():
        md.append(f"| {k} | {s['da']} ({s['da']/max(n,1):.0%}) | {s['aktuell']} ({s['aktuell']/max(n,1):.0%}) |")
    luecken = []
    for t, f in sorted(firmen.items()):
        fehlt = [k for k in KERN if k not in f["k"] or f["k"][k][-1][0] < f["gj"]]
        if fehlt:
            luecken.append(f"- {t} ({f['n']}, GJ {f['gj'][:4]}): {', '.join(fehlt)}")
    md += ["", f"## Lücken bei Kernkennzahlen ({len(luecken)})", ""] + luecken
    md += ["", f"## Ersatz-Namen per Suchmuster ({len(ersatz_log)})", ""] + [f"- {x}" for x in ersatz_log]
    if notizen:
        md += ["", "## Hinweise", ""] + [f"- {x}" for x in notizen]
    open("data/sec-abdeckung.md", "w").write("\n".join(md) + "\n")
    print("\n".join(md[:20]))


if __name__ == "__main__":
    main()
