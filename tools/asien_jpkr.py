#!/usr/bin/env python3
"""Japan (EDINET) und Suedkorea (OpenDART): Jahreszahlen fuer bis zu 10 Geschaeftsjahre fuer alle Japan- und Korea-Firmen
des Asien-Universums (asia-equity-hub/reports/universe/identity_map.json). Beide Quellen sind die amtlichen
Offenlegungssysteme (Finanzaufsicht Japan bzw. Korea), kostenlos mit Schluessel: EDINET_API_KEY, DART_API_KEY.

Japan: je Geschaeftsjahr der Jahresbericht (有価証券報告書) als XBRL; die Dokument-IDs fuer 2016-2025 stehen schon in
  asia-equity-hub/reports/sources/annual_report_sources.json. Ausgelesen werden die Uebersicht 主要な経営指標等の推移
  (jpcrp_cor:*SummaryOfBusinessResults, 5 Jahre je Bericht) und die Abschlussposten (jppfs_cor / jpigp_cor) fuer das
  laufende und das Vorjahr. Neuere Berichte ueberschreiben aeltere (nachtraegliche Anpassungen).
Korea: fnlttSinglAcntAll (vollstaendiger Konzernabschluss, je Abruf 3 Jahre) fuer die Jahre Y, Y-3, Y-6, Y-9 und
  alotMatter (Dividende je Stammaktie, je Abruf 3 Jahre).
Abgeleitet (exakte Rechnung, so vermerkt): Aktienzahl = Gewinn / Gewinn je Aktie (unverwaessert); Japan (J-GAAP):
  Eigenkapital der Aktionaere = Reinvermoegen - Minderheitsanteile - Bezugsrechte; Finanzschulden = Summe der Posten.
Nichts wird geschaetzt oder als geprueft markiert (human_review: pending).

Speicher: data/asien/roh/<Ticker>.json (Rohwerte je Dokument, nur neu bei neuen Dokumenten), data/asien/roh/_status.json
Ausgabe:  data/asien/firma/<Ticker>.json (Format wie data/sec/fundamentals.json), data/asien/firma/_index.json,
          data/asien-jpkr-abdeckung.md
Aufruf: python3 tools/asien_jpkr.py [--max-minuten 100] [--nur-bauen] [--markt Japan|Südkorea] [--limit N]
"""
import argparse, datetime as dt, io, json, os, re, time, urllib.error, urllib.parse, urllib.request, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDINET_KEY = os.environ.get("EDINET_API_KEY", "")
DART_KEY = os.environ.get("DART_API_KEY", "")
EBASE = "https://api.edinet-fsa.go.jp/api/v2"
DBASE = "https://opendart.fss.or.kr/api"
UA = {"User-Agent": "dividenden-rechner.de Datensammlung"}
ROH = os.path.join(ROOT, "data", "asien", "roh")
OUT = os.path.join(ROOT, "data", "asien", "firma")
JAHRE = 10


def get(url, timeout=180):
    for v in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and v < 3:
                time.sleep(20 * (v + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if v < 3:
                time.sleep(10); continue
            raise


def lade(p, leer=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return leer


def schreibe(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(p + ".tmp", p)


# =====================================================================  Japan (EDINET XBRL)
KTX = re.compile(r"^(CurrentYear|Prior[1-4]Year)(Duration|Instant)(_NonConsolidatedMember)?$")
POSTEN = {   # Abschlussposten (laufendes und Vorjahr), J-GAAP / IFRS / US-GAAP
    "NetAssets", "NonControllingInterests", "SubscriptionRightsToShares", "ShareholdersEquity", "EquityAttributableToOwnersOfParentIFRS",
    "Liabilities", "LiabilitiesIFRS", "CurrentAssets", "CurrentAssetsIFRS", "CurrentLiabilities", "TotalCurrentLiabilitiesIFRS",
    "Inventories", "InventoriesCAIFRS", "RetainedEarnings", "RetainedEarningsIFRS", "GrossProfit", "GrossProfitIFRS",
    "OperatingIncome", "OperatingProfitLossIFRS", "OperatingIncomeLossUSGAAP", "IncomeTaxes", "IncomeTaxExpenseIFRS",
    "InterestExpensesNOE", "FinanceCostsIFRS", "DepreciationAndAmortizationOpeCF", "DepreciationAndAmortizationOpeCFIFRS",
    "ShortTermLoansPayable", "CommercialPapersLiabilities", "CurrentPortionOfBonds", "CurrentPortionOfLongTermLoansPayable",
    "BondsPayable", "LongTermLoansPayable", "BondsAndBorrowingsCLIFRS", "BondsAndBorrowingsNCLIFRS",
    "Assets", "AssetsIFRS", "CashAndCashEquivalents", "CashAndCashEquivalentsIFRS",
}
UMSATZ_POSTEN = re.compile(r"^(Revenue|Revenues|NetSales|OperatingRevenue|OperatingRevenues|SalesRevenues|TotalRevenue|TotalRevenues|"
                           r"SalesAndFinancialServicesRevenue|OrdinaryIncome|OperatingIncomeINS)\w*$")
POSTEN_RE = re.compile(r"^(PurchaseOfPropertyPlantAndEquipment\w*InvCF\w*|PurchaseOfNoncurrentAssets\w*InvCF\w*|"
                       r"(CashDividendsPaid|DividendsPaid|DividendsPaidToOwnersOfParent)\w*FinCF\w*|PurchaseOfTreasuryShares\w*FinCF\w*)$")


def edinet_xbrl(doc_id):
    z = zipfile.ZipFile(io.BytesIO(get(f"{EBASE}/documents/{doc_id}?type=1&Subscription-Key={EDINET_KEY}", timeout=300)))
    namen = [n for n in z.namelist() if n.endswith(".xbrl") and "PublicDoc" in n]
    namen.sort(key=lambda n: ("jpcrp" not in n, len(n)))
    return z.read(namen[0]).decode("utf-8", errors="replace") if namen else ""


def edinet_auslesen(x):
    """XBRL-Text -> {"ktx": {kontext: enddatum}, "w": {element: {kontext: [wert, einheit]}}}"""
    ktx = {}
    for cid, block in re.findall(r'<xbrli:context id="([^"]+)">(.*?)</xbrli:context>', x, re.S):
        if not KTX.match(cid):
            continue
        if "explicitMember" in block and not cid.endswith("_NonConsolidatedMember"):
            continue
        m = re.search(r"<xbrli:(?:endDate|instant)>([\d-]+)<", block)
        if m:
            ktx[cid] = m.group(1)
    w = {}
    for ns, lokal, attr1, ctx, attr2, val in re.findall(
            r'<([A-Za-z0-9_\-]+):([A-Za-z0-9_]+)\s([^>]*?)contextRef="([^"]+)"([^>]*)>([^<]*)</\1:\2>', x):
        if ctx not in ktx:
            continue
        if not (lokal in POSTEN or POSTEN_RE.match(lokal) or lokal.endswith("SummaryOfBusinessResults") or
                (UMSATZ_POSTEN.match(lokal) and not re.search(r"Cost|Other|PerShare|Ratio", lokal))):
            continue
        try:
            v = float(val.strip())
        except ValueError:
            continue
        u = re.search(r'unitRef="([^"]+)"', attr1 + attr2)
        w.setdefault(lokal, {}).setdefault(ctx, [v, u.group(1) if u else ""])
    return {"ktx": ktx, "w": w}


def _erst(w, muster):
    """Erstes Element (Reihenfolge der Muster), das vorkommt."""
    for m in muster:
        if m.startswith("^"):
            for n in sorted(w):
                if re.match(m, n):
                    return n
        elif m in w:
            return m
    return None


JP_ZUSAMMENFASSUNG = {   # Feld -> (Muster, nicht konsolidiert?)
    "umsatz": ([r"^(Revenue|Revenues|NetSales|OperatingRevenue|TotalRevenue|GrossOperatingRevenue)\w*(IFRS|USGAAP|JMIS)SummaryOfBusinessResults$",
                r"^(Revenue|Revenues|NetSales|OperatingRevenue\d*|TotalRevenue|GrossOperatingRevenue|NetSalesOfCompletedConstructionContracts)SummaryOfBusinessResults$",
                "OrdinaryIncomeSummaryOfBusinessResults", r"^OperatingIncomeINS\w*SummaryOfBusinessResults$",
                r"^(?!.*(Cost|PerShare|Ratio|Growth|NumberOf|Employee|Staff|Worker))\w*(Revenue|Sales)\w*SummaryOfBusinessResults$"], False),
    "gewinn": ([r"^(ProfitLoss|NetIncomeLoss)AttributableToOwnersOfParent\w*SummaryOfBusinessResults$",
                "NetIncomeLossSummaryOfBusinessResults", "ProfitLossSummaryOfBusinessResults"], False),
    "_eps_verw": ([r"^DilutedEarnings\w*PerShare\w*SummaryOfBusinessResults$"], False),
    "_eps_unv": ([r"^BasicEarnings\w*PerShare\w*SummaryOfBusinessResults$"], False),
    "operativer_cf": ([r"^(NetCashProvidedByUsedInOperatingActivities|CashFlowsFromUsedInOperatingActivities)\w*SummaryOfBusinessResults$"], False),
    "liquide_mittel": ([r"^CashAndCashEquivalents\w*SummaryOfBusinessResults$"], False),
    "bilanzsumme": ([r"^TotalAssets\w*SummaryOfBusinessResults$"], False),
    "_ek_ifrs": ([r"^(EquityAttributableToOwnersOfParent|TotalEquityAttributableToOwnersOfParent|EquityIncludingPortionAttributableToNonControllingInterest)\w*(IFRS|USGAAP)\w*SummaryOfBusinessResults$"], False),
    "dividende_je_aktie": (["DividendPaidPerShareSummaryOfBusinessResults"], True),
}
JP_POSTEN = {   # Feld -> Muster (Abschluss, konsolidiert)
    "capex": [r"^PurchaseOfPropertyPlantAndEquipment\w*InvCF\w*$", r"^PurchaseOfNoncurrentAssets\w*InvCF\w*$"],
    "dividenden_gezahlt": [r"^DividendsPaidToOwnersOfParent\w*FinCF\w*$", r"^CashDividendsPaid\w*FinCF\w*$", r"^DividendsPaid(?!ToNonControlling)\w*FinCF\w*$"],
    "aktienrueckkauf": [r"^PurchaseOfTreasuryShares\w*FinCF\w*$"],
    "bruttogewinn": ["GrossProfitIFRS", "GrossProfit"],
    "operatives_ergebnis": ["OperatingProfitLossIFRS", "OperatingIncomeLossUSGAAP", "OperatingIncome"],
    "steuern": ["IncomeTaxExpenseIFRS", "IncomeTaxes"],
    "zinsaufwand": ["FinanceCostsIFRS", "InterestExpensesNOE"],
    "abschreibungen": ["DepreciationAndAmortizationOpeCFIFRS", "DepreciationAndAmortizationOpeCF"],
    "verbindlichkeiten": ["LiabilitiesIFRS", "Liabilities"],
    "umlaufvermoegen": ["CurrentAssetsIFRS", "CurrentAssets"],
    "kurzfr_verbindl": ["TotalCurrentLiabilitiesIFRS", "CurrentLiabilities"],
    "vorraete": ["InventoriesCAIFRS", "Inventories"],
    "gewinnruecklagen": ["RetainedEarningsIFRS", "RetainedEarnings"],
}
BETRAG_POS = {"capex", "dividenden_gezahlt", "aktienrueckkauf", "zinsaufwand"}


def _relevant(lokal):
    return any((re.match(m, lokal) if m.startswith("^") else m == lokal) for muster, _ in JP_ZUSAMMENFASSUNG.values() for m in muster)


def jp_reihen(dok):
    """Ein Dokument -> {feld: {enddatum: wert}}, Waehrung."""
    ktx, w = dok["ktx"], dok["w"]
    r, waehr = {}, {}

    def werte(name, nk):
        out = {}
        for c, (v, u) in w.get(name, {}).items():
            if c.endswith("_NonConsolidatedMember") != nk:
                continue
            out[ktx[c]] = v
            m = re.match(r"^([A-Z]{3})$", u)
            if m:
                waehr[m.group(1)] = waehr.get(m.group(1), 0) + 1
        return out

    # Konzern: Konzernwerte; nur Firmen ganz ohne Konzernabschluss bekommen Werte aus dem Einzelabschluss
    konzern = any(not c.endswith("_NonConsolidatedMember") for n, v in w.items() if n.endswith("SummaryOfBusinessResults") for c in v)
    for feld, (muster, nk) in JP_ZUSAMMENFASSUNG.items():
        nk_hier = nk or not konzern
        for m in muster:
            namen = [n for n in sorted(w) if re.match(m, n)] if m.startswith("^") else ([m] if m in w else [])
            treffer = next((werte(n, nk_hier) for n in namen if werte(n, nk_hier)), None)
            if treffer:
                r[feld] = treffer
                break
        if feld == "dividende_je_aktie" and feld not in r:   # selten im Konzernkontext gemeldet
            n = _erst(w, muster)
            if n and werte(n, False):
                r[feld] = werte(n, False)
    # Übersicht ohne Umsatz (z. B. Toyota, Sony): Umsatzposten des Konzernabschlusses in fester Reihenfolge
    if "umsatz" not in r:
        for n in ("RevenueIFRS", "NetSalesIFRS", "OperatingRevenueIFRS", "SalesRevenuesIFRS", "TotalRevenuesIFRS", "TotalRevenueIFRS",
                  "SalesAndFinancialServicesRevenueIFRS", "RevenuesUSGAAP", "NetSales", "Revenue", "OperatingRevenue1", "OperatingIncomeINS"):
            if werte(n, False):
                r["umsatz"] = werte(n, False)
                break
    for feld, muster in JP_POSTEN.items():
        n = _erst(w, muster)
        if n:
            r[feld] = werte(n, False)
    # Eigenkapital der Aktionaere: IFRS/US-GAAP direkt, J-GAAP = Reinvermoegen - Minderheiten - Bezugsrechte
    ek = dict(r.get("_ek_ifrs", {}))
    if "EquityAttributableToOwnersOfParentIFRS" in w:
        ek.update(werte("EquityAttributableToOwnersOfParentIFRS", False))
    na = werte("NetAssets", False)
    for e, v in na.items():
        if e not in ek:
            ek[e] = v - werte("NonControllingInterests", False).get(e, 0) - werte("SubscriptionRightsToShares", False).get(e, 0)
    if ek:
        r["eigenkapital"] = ek
    # Finanzschulden: IFRS-Summenposten oder Summe der J-GAAP-Posten
    for feld, ifrs, jg in (("schulden_kurz", "BondsAndBorrowingsCLIFRS", ("ShortTermLoansPayable", "CommercialPapersLiabilities", "CurrentPortionOfBonds", "CurrentPortionOfLongTermLoansPayable")),
                           ("schulden_lang", "BondsAndBorrowingsNCLIFRS", ("BondsPayable", "LongTermLoansPayable"))):
        s = werte(ifrs, False)
        if not s:
            for n in jg:
                for e, v in werte(n, False).items():
                    s[e] = s.get(e, 0) + v
        if s:
            r[feld] = s
    w_ = max(waehr, key=waehr.get) if waehr else "JPY"
    return r, w_


# =====================================================================  Korea (OpenDART)
def dart(pfad, **params):
    q = urllib.parse.urlencode({"crtfc_key": DART_KEY, **params})
    return json.loads(get(f"{DBASE}/{pfad}?{q}", timeout=90))


KR_KONTEN = {   # Feld -> (Abschluss, account_id-Endungen, Namensbestandteile)
    "umsatz": (("IS", "CIS"), ("Revenue", "RevenueFromContractsWithCustomers"), ("매출액", "영업수익", "수익(매출액)")),
    "gewinn": (("IS", "CIS"), ("ProfitLossAttributableToOwnersOfParent",), ("지배기업", "소유주")),
    "_gewinn_ges": (("IS", "CIS"), ("ProfitLoss",), ("당기순이익",)),
    "_eps_unv": (("IS", "CIS"), ("BasicEarningsLossPerShare",), ("기본주당",)),
    "_eps_verw": (("IS", "CIS"), ("DilutedEarningsLossPerShare",), ("희석주당",)),
    "operatives_ergebnis": (("IS", "CIS"), ("OperatingIncomeLoss",), ("영업이익",)),
    "bruttogewinn": (("IS", "CIS"), ("GrossProfit",), ("매출총이익",)),
    "steuern": (("IS", "CIS"), ("IncomeTaxExpenseContinuingOperations",), ("법인세비용",)),
    "zinsaufwand": (("IS", "CIS"), ("FinanceCosts",), ("금융비용", "금융원가")),
    "operativer_cf": (("CF",), ("CashFlowsFromUsedInOperatingActivities",), ("영업활동",)),
    "capex": (("CF",), ("PurchaseOfPropertyPlantAndEquipment",), ("유형자산의 취득", "유형자산의취득")),
    "dividenden_gezahlt": (("CF",), ("DividendsPaidClassifiedAsFinancingActivities", "DividendsPaid"), ("배당금지급", "배당금의 지급", "배당금 지급")),
    "aktienrueckkauf": (("CF",), ("PaymentsToAcquireOrRedeemEntitysShares",), ("자기주식의 취득", "자기주식의취득")),
    "abschreibungen": (("CF",), ("AdjustmentsForDepreciationAndAmortisationExpense", "AdjustmentsForDepreciationExpense"), ("감가상각비",)),
    "liquide_mittel": (("BS",), ("CashAndCashEquivalents",), ("현금및현금성자산",)),
    "bilanzsumme": (("BS",), ("Assets",), ("자산총계",)),
    "verbindlichkeiten": (("BS",), ("Liabilities",), ("부채총계",)),
    "eigenkapital": (("BS",), ("EquityAttributableToOwnersOfParent",), ("지배기업",)),
    "_ek_ges": (("BS",), ("Equity",), ("자본총계",)),
    "umlaufvermoegen": (("BS",), ("CurrentAssets",), ("유동자산",)),
    "kurzfr_verbindl": (("BS",), ("CurrentLiabilities",), ("유동부채",)),
    "vorraete": (("BS",), ("Inventories",), ("재고자산",)),
    "gewinnruecklagen": (("BS",), ("RetainedEarnings",), ("이익잉여금",)),
}


def betrag(s):
    s = str(s or "").replace(",", "").strip()
    if not s or s in ("-",):
        return None
    neg = s.startswith("(") and s.endswith(")")
    try:
        v = float(s.strip("()"))
    except ValueError:
        return None
    return -v if neg else v


def kr_konten(liste):
    """fnlttSinglAcntAll-Liste -> {feld: [thstrm, frmtrm, bfefrmtrm]} (erster passender Posten je Feld)."""
    out = {}
    for feld, (sjs, ids, nms) in KR_KONTEN.items():
        treffer = None
        for z in liste:   # zuerst ueber die Standard-Kontokennung
            if z.get("sj_div") in sjs and z.get("account_id", "").split("_", 1)[-1] in ids:
                treffer = z; break
        if not treffer:   # sonst ueber den Kontonamen (nur Posten ohne Standardkennung)
            for z in liste:
                nm = (z.get("account_nm") or "").replace(" ", "")
                if z.get("sj_div") in sjs and any(n.replace(" ", "") in nm for n in nms) and "-표준계정코드" in (z.get("account_id") or "-표준계정코드"):
                    treffer = z; break
        if treffer:
            out[feld] = [betrag(treffer.get("thstrm_amount")), betrag(treffer.get("frmtrm_amount")), betrag(treffer.get("bfefrmtrm_amount"))]
    return out


def kr_holen(corp, stand):
    """Rohdaten je Geschaeftsjahr: {"abschluss": {jahr: {...}}, "dividende": {jahr: [...]}, "acc_mt": "12"}"""
    roh = stand or {"abschluss": {}, "dividende": {}, "fs": {}}
    if "acc_mt" not in roh:
        c = dart("company.json", corp_code=corp)
        roh["acc_mt"] = c.get("acc_mt") or "12"
        roh["name"] = c.get("corp_name_eng") or c.get("corp_name")
    heute = dt.date.today()
    letztes = heute.year - 1 if heute.month >= 4 else heute.year - 2
    jahre = [letztes - 3 * i for i in range(4)] + [letztes + 1]
    for y in jahre:
        if str(y) in roh["abschluss"] and y < letztes:
            continue   # aeltere Jahre aendern sich nicht mehr
        for fs in ("CFS", "OFS"):
            j = dart("fnlttSinglAcntAll.json", corp_code=corp, bsns_year=str(y), reprt_code="11011", fs_div=fs)
            time.sleep(0.4)
            if j.get("status") == "000" and j.get("list"):
                roh["abschluss"][str(y)] = kr_konten(j["list"])
                roh["fs"][str(y)] = fs
                break
            if j.get("status") not in ("013",):   # 013 = keine Daten
                raise RuntimeError(f"DART {j.get('status')}: {j.get('message')}")
        d = dart("alotMatter.json", corp_code=corp, bsns_year=str(y), reprt_code="11011")
        time.sleep(0.4)
        for z in d.get("list") or []:
            if "주당 현금배당금" in (z.get("se") or "") and "보통" in (z.get("stock_knd") or "보통"):
                roh["dividende"][str(y)] = [betrag(z.get("thstrm")), betrag(z.get("frmtrm")), betrag(z.get("lwfr"))]
                break
    return roh


def kr_reihen(roh):
    mon = int(roh.get("acc_mt") or 12)
    def ende(y):
        import calendar
        return f"{y}-{mon:02d}-{calendar.monthrange(y, mon)[1]:02d}"
    r = {}
    for y in sorted(roh["abschluss"], key=int):   # aeltere zuerst, neuere ueberschreiben (Anpassungen)
        for feld, drei in roh["abschluss"][y].items():
            for i, v in enumerate(drei):
                if v is not None:
                    r.setdefault(feld, {})[ende(int(y) - i)] = v
    for y in sorted(roh["dividende"], key=int):
        for i, v in enumerate(roh["dividende"][y]):
            if v is not None and v > 0:
                r.setdefault("dividende_je_aktie", {})[ende(int(y) - i)] = v
    for feld, ersatz in (("gewinn", "_gewinn_ges"), ("eigenkapital", "_ek_ges")):
        for e, v in r.get(ersatz, {}).items():
            r.setdefault(feld, {}).setdefault(e, v)
    return r, "KRW"


# =====================================================================  Zusammenbau (beide Maerkte)
def firma(e, reihen, w, quelle, isin):
    gw = reihen.get("gewinn", {})
    eps = dict(reihen.get("_eps_unv", {}))
    eps.update({k: v for k, v in reihen.get("_eps_verw", {}).items() if v})   # verwaessert, wo gemeldet
    enden = sorted(set(reihen.get("umsatz", {})) | set(gw))
    if not enden:
        return None
    letzte = enden[-JAHRE:]
    gj = letzte[-1]
    k = {}
    for feld, r in reihen.items():
        if feld.startswith("_") or not r:
            continue
        r = {d: (abs(v) if feld in BETRAG_POS else v) for d, v in r.items() if d in letzte or feld not in
             ("umsatz", "gewinn", "operativer_cf", "capex", "dividenden_gezahlt", "aktienrueckkauf", "bruttogewinn", "operatives_ergebnis",
              "abschreibungen", "zinsaufwand", "steuern", "dividende_je_aktie")}
        ds = sorted(r)[-JAHRE:]
        if ds:
            k[feld] = [[d, round(r[d], 4)] for d in ds]
    if eps:
        k["eps_verw"] = [[d, eps[d]] for d in sorted(eps) if d in letzte]
    # Aktienzahl = Gewinn / unverwaesserter Gewinn je Aktie (nachgerechnet)
    av = {d: round(gw[d] / reihen["_eps_unv"][d]) for d in gw if reihen.get("_eps_unv", {}).get(d) and gw[d] / reihen["_eps_unv"][d] > 0}
    if av:
        k["aktien_verw"] = [[d, av[d]] for d in sorted(av) if d in letzte]
    fa = {"n": e.get("official_name") or e.get("requested_name"), "n_lokal": e.get("official_name_local"), "isin": isin,
          "land": {"Japan": "JP", "Südkorea": "KR"}[e["market"]], "gj": gj, "w": w, "quelle": quelle,
          "std": "IFRS/J-GAAP/US-GAAP" if quelle == "EDINET" else "K-IFRS", "human_review": "pending",
          "abgeleitet": ["aktien_verw = Gewinn / Gewinn je Aktie (unverwässert)"] +
                        (["eigenkapital (J-GAAP) = Reinvermögen − Minderheitsanteile − Bezugsrechte", "schulden_kurz/lang = Summe der Finanzschuldposten"] if quelle == "EDINET" else []),
          "k": k}
    if quelle == "EDINET":
        fa["hinweis"] = ("Dividende je Aktie wie im jeweiligen Jahresbericht gemeldet (Einzelabschluss der Muttergesellschaft), "
                         "nicht rückwirkend an Aktiensplits angepasst; Gewinn je Aktie ist laut Bericht angepasst.")
    return fa


def _ohne_umsatz(roh):
    """Neuester Bericht (v2) ohne Umsatz in der Übersicht -> mit Umsatzposten neu laden."""
    if not roh or roh.get("v") != 2 or not roh.get("dok"):
        return False
    d = max(roh["dok"].values(), key=lambda x: x.get("ende") or "")
    return "umsatz" not in jp_reihen(d)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minuten", type=float, default=100)
    ap.add_argument("--nur-bauen", action="store_true")
    ap.add_argument("--markt", choices=["Japan", "Südkorea"])
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    start, heute = time.time(), dt.date.today().isoformat()
    ident = lade(os.path.join(ROOT, "asia-equity-hub/reports/universe/identity_map.json"))["entries"]
    quellen = {e["id"]: e for e in lade(os.path.join(ROOT, "asia-equity-hub/reports/sources/annual_report_sources.json"))["entries"]}
    isins = lade(os.path.join(ROOT, "data/asien/isin.json"), {}) or {}
    status = lade(os.path.join(ROOT, "data/asien/roh/_status.json"), {}) or {}
    firmen = [e for e in ident if e["market"] in ("Japan", "Südkorea") and e.get("status") == "confirmed_official_list"
              and (not a.markt or e["market"] == a.markt)]
    firmen.sort(key=lambda e: (status.get(e["ticker"], [""])[0], e["ticker"]))
    fehler, n_dok = [], 0

    def jp_docs(e):
        docs = []
        for y, ds in sorted(((quellen.get(e["id"]) or {}).get("documents_by_year") or {}).items(), reverse=True):
            d = next((x for x in ds if not x.get("is_amendment")), None)
            if d and d.get("doc_id"):
                docs.append(d)
        return docs

    def kern(docs):   # neuester Bericht und der fuenf Jahre aeltere: zusammen 10 Jahre Uebersicht
        return docs[:1] + docs[5:6] if len(docs) > 5 else docs[:1] + docs[-1:]

    # Phase 1, solange einer Firma noch die beiden Kernberichte fehlen: nur diese laden; danach die uebrigen Jahre
    def _dok(t):
        r = lade(os.path.join(ROH, f"{t}.json")) or {}
        return r.get("dok") or {} if r.get("v") in (2, 3) else {}
    phase1 = any(d["doc_id"] not in _dok(e["ticker"])
                 for e in firmen if e["market"] == "Japan" for d in kern(jp_docs(e)))
    if not a.nur_bauen:
        bearbeitet = 0
        for e in firmen:
            if time.time() - start > a.max_minuten * 60 or (a.limit and bearbeitet >= a.limit):
                break
            t = e["ticker"]
            p = os.path.join(ROH, f"{t}.json")
            roh = lade(p)
            if status.get(t, [""])[0] == heute and (e["market"] != "Japan" or ((roh or {}).get("v") in (2, 3) and not _ohne_umsatz(roh))):
                continue
            try:
                if e["market"] == "Japan":
                    if not EDINET_KEY:
                        continue
                    if not roh or roh.get("v") not in (2, 3):   # v2: alle Übersichtselemente gespeichert
                        roh = {"v": 2, "dok": {}}
                    elif roh.get("v") == 2 and _ohne_umsatz(roh):   # v3: zusätzlich Umsatzposten des Abschlusses
                        roh = {"v": 3, "dok": {}}
                    docs = kern(jp_docs(e)) if phase1 else jp_docs(e)
                    neu = 0
                    for d in docs:
                        if d["doc_id"] in roh["dok"]:
                            continue
                        dok = edinet_auslesen(edinet_xbrl(d["doc_id"]))
                        dok["ende"] = d.get("period_end")
                        roh["dok"][d["doc_id"]] = dok
                        neu += 1; n_dok += 1
                        time.sleep(1)
                        if time.time() - start > a.max_minuten * 60:
                            break
                    if neu:
                        schreibe(p, roh)
                    status[t] = [heute, len(roh["dok"])]
                else:
                    if not DART_KEY:
                        continue
                    corp = (e.get("identifiers") or {}).get("dart_corp_code")
                    if not corp:
                        continue
                    alt = json.dumps(roh, sort_keys=True) if roh else ""
                    roh = kr_holen(corp, roh)
                    n_dok += 1
                    if json.dumps(roh, sort_keys=True) != alt:
                        schreibe(p, roh)
                    status[t] = [heute, len(roh["abschluss"])]
                bearbeitet += 1
                print(t, status[t], flush=True)
            except Exception as ex:  # noqa: BLE001
                fehler.append(f"{t}: {str(ex)[:150]}")
                if roh and e["market"] == "Japan" and roh.get("dok"):
                    schreibe(p, roh)
            if bearbeitet % 10 == 0:
                schreibe(os.path.join(ROH, "_status.json"), status)
        schreibe(os.path.join(ROH, "_status.json"), status)

    # Zusammenbau
    os.makedirs(OUT, exist_ok=True)
    index, zeilen = {}, []
    for e in [x for x in ident if x["market"] in ("Japan", "Südkorea") and x.get("status") == "confirmed_official_list"]:
        t = e["ticker"]
        roh = lade(os.path.join(ROH, f"{t}.json"))
        if not roh:
            zeilen.append(f"| {t} | {e.get('requested_name')} | – | noch nicht abgerufen | |"); continue
        if e["market"] == "Japan":
            reihen, w = {}, "JPY"
            for doc_id, dok in sorted(roh["dok"].items(), key=lambda kv: kv[1].get("ende") or ""):
                r, w = jp_reihen(dok)
                for feld, werte in r.items():
                    reihen.setdefault(feld, {}).update(werte)
            quelle = "EDINET"
        else:
            reihen, w = kr_reihen(roh)
            quelle = "DART"
        isin = (isins.get(t) or {}).get("isin")
        fa = firma(e, reihen, w, quelle, isin)
        if not fa:
            zeilen.append(f"| {t} | {e.get('requested_name')} | – | keine Jahreswerte | |"); continue
        schreibe(os.path.join(OUT, f"{t}.json"), fa)
        index[t] = [fa["n"], isin, fa["land"], fa["gj"]]
        jahre = sorted({d[:4] for d, _ in fa["k"].get("umsatz", []) + fa["k"].get("gewinn", [])})
        zeilen.append(f"| {t} | {fa['n']} | {jahre[0]}–{jahre[-1]} ({len(jahre)}) | {len(fa['k'])} Reihen | "
                      f"{'ja' if (isins.get(t) or {}).get('in_de_gehandelt') else 'nein'} |")
    schreibe(os.path.join(OUT, "_index.json"), dict(sorted(index.items())))
    md = [f"# Japan (EDINET) und Korea (DART): Abdeckung (Stand {heute})", "",
          "Amtliche Offenlegungssysteme, maschinell ausgelesen, ungeprüft (human_review: pending).", "",
          f"- Firmen (bestätigt in der offiziellen Liste): {len([z for z in zeilen])}, mit Jahreszahlen: **{len(index)}**",
          f"- in diesem Lauf: {n_dok} Abrufe, {len(fehler)} Fehler", "",
          "| Ticker | Name | Jahre | Umfang | Kurs in DE |", "|---|---|---|---|---|"] + zeilen
    if fehler:
        md += ["", "## Fehler (nächster Lauf versucht es erneut)", ""] + [f"- {x}" for x in fehler[:60]]
    open(os.path.join(ROOT, "data", "asien-jpkr-abdeckung.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md[4:6]))
    if fehler:
        print("\n".join(fehler[:20]))


if __name__ == "__main__":
    main()
