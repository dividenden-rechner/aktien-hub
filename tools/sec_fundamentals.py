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
    # Fuer Margen, EBITDA, Bilanzkennzahlen, Altman-Z und Piotroski (ab 11.11.2026)
    "bruttogewinn": ("f", "USD", ["GrossProfit"], r"^GrossProfit$"),
    "operatives_ergebnis": ("f", "USD", ["OperatingIncomeLoss"], r"^OperatingIncomeLoss$"),
    "abschreibungen": ("f", "USD", ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
                                    "DepreciationAmortizationAndAccretionNet", "Depreciation"],
                       r"^(DepreciationDepletionAndAmortization|DepreciationAndAmortization|DepreciationAmortizationAndAccretionNet)$"),
    "zinsaufwand": ("f", "USD", ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
                    r"^(InterestExpense|InterestExpenseNonoperating|InterestExpenseDebt)$"),
    "steuern": ("f", "USD", ["IncomeTaxExpenseBenefit"], r"^IncomeTaxExpenseBenefit$"),
    "bilanzsumme": ("s", "USD", ["Assets"], r"^Assets$"),
    "umlaufvermoegen": ("s", "USD", ["AssetsCurrent"], r"^AssetsCurrent$"),
    "kurzfr_verbindl": ("s", "USD", ["LiabilitiesCurrent"], r"^LiabilitiesCurrent$"),
    "verbindlichkeiten": ("s", "USD", ["Liabilities"], r"^Liabilities$"),
    "vorraete": ("s", "USD", ["InventoryNet"], r"^InventoryNet$"),
    "gewinnruecklagen": ("s", "USD", ["RetainedEarningsAccumulatedDeficit"], r"^RetainedEarningsAccumulatedDeficit$"),
    "schulden_kurz": ("s", "USD", ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"],
                      r"^(LongTermDebtCurrent|DebtCurrent|ShortTermBorrowings)$"),
}
# Diese Namen passen zwar auf ein Suchmuster, meinen aber etwas anderes
SPERRE = re.compile(r"(MinorityInterest|Noncontrolling|Preferred|Subsidiar|PerShare|Percentage|Remaining|Deferred|Unbilled|Fees|Interest(Expense|Paid)|Current$|Maturities|Repayments|Proceeds|FairValue|Increase|Decrease|Gain|Tax)", re.I)
# Auslaendische Firmen (20-F) melden oft nach IFRS
K_IFRS = {
    "umsatz": ["Revenue", "RevenueFromContractsWithCustomers"],
    "gewinn": ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"],
    "eps_verw": ["DilutedEarningsLossPerShare", "DilutedEarningsPerShare", "BasicAndDilutedEarningsLossPerShare",
                 "BasicAndDilutedEarningsPerShare"],
    "dividende_je_aktie": [],
    "dividenden_gezahlt": ["DividendsPaidToEquityHoldersOfParentClassifiedAsFinancingActivities",
                           "DividendsPaidClassifiedAsFinancingActivities", "DividendsPaid"],
    "operativer_cf": ["CashFlowsFromUsedInOperatingActivities"],
    "capex": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
              "PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets"],
    "aktienrueckkauf": ["PaymentsToAcquireOrRedeemEntitysShares", "PurchaseOfTreasuryShares"],
    "aktien_verw": ["AdjustedWeightedAverageShares", "WeightedAverageShares"],
    "schulden_lang": ["NoncurrentPortionOfNoncurrentBorrowings", "LongtermBorrowings", "NoncurrentBorrowings"],
    "liquide_mittel": ["CashAndCashEquivalents"],
    "eigenkapital": ["EquityAttributableToOwnersOfParent", "Equity"],
    "bruttogewinn": ["GrossProfit"],
    "operatives_ergebnis": ["ProfitLossFromOperatingActivities"],
    "abschreibungen": ["DepreciationAndAmortisationExpense",
                       "DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss"],
    "zinsaufwand": ["InterestExpense", "FinanceCosts"],
    "steuern": ["IncomeTaxExpenseContinuingOperations"],
    "bilanzsumme": ["Assets"],
    "umlaufvermoegen": ["CurrentAssets"],
    "kurzfr_verbindl": ["CurrentLiabilities"],
    "verbindlichkeiten": ["Liabilities"],
    "vorraete": ["Inventories"],
    "gewinnruecklagen": ["RetainedEarnings"],
    "schulden_kurz": ["CurrentBorrowings", "CurrentPortionOfNoncurrentBorrowings", "ShorttermBorrowings"],
}
FORMEN = ("10-K", "20-F", "40-F")
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


def einheit_waehlen(units, einheit, waehrung):
    """USD-Kennzahlen: bei Auslandsfirmen in deren Berichtswaehrung (EUR, JPY, TWD ...)."""
    if einheit in units and (waehrung in (None, "USD") or einheit == "shares"):
        return units[einheit]
    if waehrung and einheit in ("USD", "USD/shares"):
        alt = einheit.replace("USD", waehrung)
        if alt in units:
            return units[alt]
    return units.get(einheit, [])


def werte_eines_namens(gaap, tag, art, einheit, waehrung=None):
    cand = {}
    for x in einheit_waehlen((gaap.get(tag) or {}).get("units", {}), einheit, waehrung):
        if not str(x.get("form", "")).startswith(FORMEN):
            continue
        if art == "f":
            d = dauer(x)
            if d is None or not (350 <= d <= 380):
                continue
        end = x["end"]
        if end not in cand or x.get("filed", "") > cand[end][2]:
            cand[end] = (x["val"], tag, x.get("filed", ""))
    return {e: v[:2] for e, v in cand.items()}


def reihe_max(gaap, art, einheit, tags, waehrung=None):
    """Fuer den Umsatz: je Geschaeftsjahr der groesste Wert ueber alle Namen. Manche Firmen melden unter 'Revenues'
    nur einen Teilumsatz (z. B. General Mills 2019-2024), der Gesamtumsatz steht dann unter einem anderen Namen."""
    out = {}
    for tag in tags:
        for e, v in werte_eines_namens(gaap, tag, art, einheit, waehrung).items():
            if e not in out or (v[0] or 0) > (out[e][0] or 0):
                out[e] = v
    return out


def reihe(gaap, art, einheit, tags, waehrung=None):
    out = {}
    for tag in tags:
        for e, v in werte_eines_namens(gaap, tag, art, einheit, waehrung).items():
            out.setdefault(e, v)
    return out


def ersatz_suchen(gaap, art, einheit, muster, schon, ziel_ende, waehrung="USD"):
    """Sucht unter allen Namen der Firma einen, der das Muster trifft und bis ziel_ende reicht."""
    best = None
    for tag in gaap:
        if tag in schon or not re.match(muster, tag) or SPERRE.search(tag):
            continue
        w = werte_eines_namens(gaap, tag, art, einheit, waehrung)
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
        facts = cf.get("facts") or {}
        gaap, ifrs = facts.get("us-gaap", {}), False
        if not any(g in gaap for g in ("Revenues", "NetIncomeLoss", "RevenueFromContractWithCustomerExcludingAssessedTax", "ProfitLoss")) and facts.get("ifrs-full"):
            gaap, ifrs = facts["ifrs-full"], True
        # Berichtswaehrung: die Waehrung mit den meisten Angaben bei Umsatz und Gewinn (USD, EUR, JPY ...)
        zaehl = {}
        for g in (K_IFRS["umsatz"] + K_IFRS["gewinn"]) if ifrs else (K["umsatz"][2] + K["gewinn"][2]):
            for u, v in (gaap.get(g) or {}).get("units", {}).items():
                if re.fullmatch(r"[A-Z]{3}", u):
                    zaehl[u] = zaehl.get(u, 0) + len(v)
        waehrung = max(zaehl, key=zaehl.get) if zaehl else "USD"
        if not gaap:
            notizen.append(f"{t}: keine Finanzdaten (CIK {cik})"); continue
        reihen = {k: (reihe_max if k == "umsatz" else reihe)(gaap, a, e, (K_IFRS[k] if ifrs else tags), waehrung) for k, (a, e, tags, _) in K.items()}
        enden = set(reihen["umsatz"]) | set(reihen["gewinn"])
        if not enden:
            notizen.append(f"{t}: keine Jahreswerte"); continue
        letztes_gj = max(enden)
        for k, (a, e, tags, muster) in K.items():
            w = reihen[k]
            if not ifrs and (not w or max(w) < letztes_gj):
                b = ersatz_suchen(gaap, a, e, muster, set(tags), letztes_gj, waehrung)
                if b:
                    for end, v in b[2].items():
                        w.setdefault(end, v)
                    ersatz_log.append(f"{t} {k}: {b[1]}")
            if a == "s":
                w = {end: v for end, v in w.items() if end in enden}
            reihen[k] = w
        # 1) Nur echte Geschaeftsjahre: Jahreswerte, deren Stichtag nicht zum Geschaeftsjahresende passt
        #    (z. B. ein 12-Monats-Zeitraum bis Juni bei einer Firma mit Jahresende Dezember), fliegen raus
        md_gj = datetime.date.fromisoformat(letztes_gj)
        def passt(e):
            d = datetime.date.fromisoformat(e)
            return min(abs((d - d.replace(year=d.year, month=md_gj.month, day=min(md_gj.day, 28))).days),
                       abs((d - d.replace(year=d.year + 1, month=md_gj.month, day=min(md_gj.day, 28))).days),
                       abs((d - d.replace(year=d.year - 1, month=md_gj.month, day=min(md_gj.day, 28))).days)) <= 10
        for k in reihen:
            reihen[k] = {e: v for e, v in reihen[k].items() if passt(e)}
        enden = {e for e in enden if passt(e)}
        # 2) Aktiensplits: aeltere Jahreswerte je Aktie stehen in alten Berichten noch unbereinigt. Springt die Aktienzahl
        #    um einen glatten Faktor und faellt der Wert je Aktie entsprechend, werden alle frueheren Jahre umgerechnet.
        sh = reihen["aktien_verw"]
        jahre = sorted(sh)
        for a, b in reversed(list(zip(jahre, jahre[1:]))):
            if not sh[a][0] or not sh[b][0]:
                continue
            r = sh[b][0] / sh[a][0]
            f = round(r)
            if f < 2 or abs(r - f) / f > 0.15:
                continue
            je = [x for x in ("dividende_je_aktie", "eps_verw") if a in reihen[x] and b in reihen[x] and reihen[x][b][0]]
            if not je or not any(0.5 < (reihen[x][a][0] / reihen[x][b][0]) / f < 2 for x in je):
                continue
            for e in [e for e in jahre if e <= a]:
                for x in ("dividende_je_aktie", "eps_verw"):
                    if e in reihen[x]:
                        reihen[x][e] = (reihen[x][e][0] / f, reihen[x][e][1])
                if e in sh:
                    sh[e] = (sh[e][0] * f, sh[e][1])
            ersatz_log.append(f"{t}: Split 1:{f} zwischen {a[:4]} und {b[:4]} bereinigt")
        # Dividende je Aktie nachrechnen (gezahlte Dividenden / verwaesserte Aktien), wo sie nicht gemeldet wird
        dg, av, dps = reihen["dividenden_gezahlt"], reihen["aktien_verw"], reihen["dividende_je_aktie"]
        # Vorzugsdividenden abziehen, wenn der Name nicht ausdruecklich nur Stammaktien meint (Banken wie Citigroup)
        vz = {} if ifrs else reihe(gaap, "f", "USD", ["DividendsPreferredStock", "DividendsPreferredStockCash",
                                                      "PreferredStockDividendsIncomeStatementImpact"], waehrung)
        def stamm(e):
            v = abs(dg[e][0])
            if "CommonStock" not in dg[e][1] and e in vz:
                v -= abs(vz[e][0])
            return v
        ber = {e: (round(stamm(e) / av[e][0], 4), "berechnet") for e in dg
               if e in av and av[e][0] and e not in dps and dg[e][0] and stamm(e) > 0}
        fa = {"n": cf.get("entityName") or name, "cik": int(cik), "gj": letztes_gj, "w": waehrung,
              "std": "IFRS" if ifrs else "US-GAAP", "k": {}}
        if ber:
            fa["k"]["dividende_je_aktie_ber"] = [[e, ber[e][0]] for e in sorted(ber)[-JAHRE:]]
        # Gewinn je Aktie nachrechnen (Gewinn / verwaesserte Aktien), wo er fehlt
        gw, eps = reihen["gewinn"], reihen["eps_verw"]
        eb = {e: round(gw[e][0] / av[e][0], 4) for e in gw if e in av and av[e][0] and e not in eps}
        if eb:
            fa["k"]["eps_ber"] = [[e, eb[e]] for e in sorted(eb)[-JAHRE:]]
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
    def hat(f, k):
        if k == "dividende_je_aktie":
            dg = f["k"].get("dividenden_gezahlt")
            if not dg or dg[-1][0] < f["gj"] or not dg[-1][1]:
                return True   # zahlt keine Dividende: keine Luecke
            return any(x in f["k"] and f["k"][x][-1][0] >= f["gj"] for x in ("dividende_je_aktie", "dividende_je_aktie_ber"))
        if k == "eps_verw":
            return any(x in f["k"] and f["k"][x][-1][0] >= f["gj"] for x in ("eps_verw", "eps_ber"))
        return k in f["k"] and f["k"][k][-1][0] >= f["gj"]
    voll = [t for t, f in firmen.items() if all(hat(f, k) for k in KERN)]
    ber_n = sum(1 for f in firmen.values() if "dividende_je_aktie_ber" in f["k"] and "dividende_je_aktie" not in f["k"])
    ifrs_n = sum(1 for f in firmen.values() if f["std"] == "IFRS")
    md = [f"# SEC-Fundamentaldaten: Abdeckung (Stand {heute.isoformat()})", "",
          f"Firmen mit Daten: **{n}** von {len(liste)}. Kernkennzahlen (Umsatz, Gewinn, EPS, Dividende je Aktie, operativer Cashflow) "
          f"vollständig und aktuell: **{len(voll)}**.", "",
          "„Aktuell“ heißt: Wert für das letzte Geschäftsjahr der Firma vorhanden. Firmen ohne Dividende zählen bei der Dividende nicht als Lücke.", "",
          f"Nach IFRS (Auslandsfirmen, Beträge in Berichtswährung): {ifrs_n}. Dividende je Aktie nur nachgerechnet (gezahlte Dividenden / Aktien): {ber_n}.", "",
          "| Kennzahl | mit Daten | davon aktuell |", "|---|---:|---:|"]
    for k, s in stat.items():
        md.append(f"| {k} | {s['da']} ({s['da']/max(n,1):.0%}) | {s['aktuell']} ({s['aktuell']/max(n,1):.0%}) |")
    luecken = []
    for t, f in sorted(firmen.items()):
        fehlt = [k for k in KERN if not hat(f, k)]
        if fehlt:
            luecken.append(f"- {t} ({f['n']}, GJ {f['gj'][:4]}): {', '.join(fehlt)}")
    md += ["", f"## Lücken bei Kernkennzahlen ({len(luecken)})", ""] + luecken
    md += ["", f"## Ersatz-Namen und Split-Bereinigungen ({len(ersatz_log)})", ""] + [f"- {x}" for x in ersatz_log]
    if notizen:
        md += ["", "## Hinweise", ""] + [f"- {x}" for x in notizen]
    open("data/sec-abdeckung.md", "w").write("\n".join(md) + "\n")
    print("\n".join(md[:20]))


if __name__ == "__main__":
    main()
