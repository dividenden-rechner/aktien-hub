#!/usr/bin/env python3
"""Europaeische Jahreszahlen aus den ESEF-Jahresberichten (filings.xbrl.org, ab 11.11.2026).
Gleiches Format wie data/sec/fundamentals.json, damit Kennzahlen, Screener, Aktienseite und Depot sie ohne Umbau nutzen.
Firmen, die schon ueber die SEC kommen (20-F: Sanofi, ASML, Shell, Novartis, SAP ...), fehlen hier absichtlich.
Deutsche Konzerne fehlen in der ESEF-Sammlung seit 2022 weitgehend, die Schweiz berichtet nicht nach ESEF.

Ablauf je Firma: Rechtsträger (LEI) einmal per Namenssuche finden und merken, dann alle Jahresberichte dieses
Rechtsträgers laden (je Bericht nur einmal, Ergebnis im Zwischenspeicher), Jahreswerte ohne Segment-Dimensionen
herausziehen, neuere Berichte ueberschreiben aeltere. Die ISIN fuer den Boersenkurs kommt von GLEIF (LEI -> ISIN).
Schreibt data/esef/fundamentals.json, data/esef/speicher.json und data/esef-abdeckung.md."""
import datetime, difflib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from sec_fundamentals import K_IFRS  # gleiche IFRS-Namen wie bei den 20-F-Firmen

UA = {"User-Agent": "dividenden-rechner.de Datensammlung (https://www.dividenden-rechner.de/impressum/)"}
BASIS = "https://filings.xbrl.org"
ZEITBUDGET = 45 * 60
JAHRE = 10

# (Kürzel, Anzeigename, Suchbegriff im Rechtsträgernamen, Land, Sektor)
FIRMEN = [
    # Frankreich
    ("MC.PA", "LVMH", "lvmh", "FR", "Consumer Cyclical"), ("OR.PA", "L'Oréal", "l_or_al", "FR", "Consumer Defensive"),
    ("RMS.PA", "Hermès", "herm_s international", "FR", "Consumer Cyclical"), ("KER.PA", "Kering", "kering", "FR", "Consumer Cyclical"),
    ("CS.PA", "AXA", "axa", "FR", "Financial Services"), ("BNP.PA", "BNP Paribas", "bnp paribas", "FR", "Financial Services"),
    ("ACA.PA", "Crédit Agricole", "cr_dit agricole s", "FR", "Financial Services"), ("GLE.PA", "Société Générale", "soci_t_ g_n_rale", "FR", "Financial Services"),
    ("SU.PA", "Schneider Electric", "schneider electric", "FR", "Industrials"), ("DG.PA", "Vinci", "vinci", "FR", "Industrials"),
    ("SAF.PA", "Safran", "safran", "FR", "Industrials"), ("AIR.PA", "Airbus", "airbus", "NL", "Industrials"),
    ("SGO.PA", "Saint-Gobain", "saint-gobain", "FR", "Industrials"), ("LR.PA", "Legrand", "legrand", "FR", "Industrials"),
    ("BN.PA", "Danone", "danone", "FR", "Consumer Defensive"), ("RI.PA", "Pernod Ricard", "pernod ricard", "FR", "Consumer Defensive"),
    ("CA.PA", "Carrefour", "carrefour", "FR", "Consumer Defensive"), ("AI.PA", "Air Liquide", "air liquide", "FR", "Basic Materials"),
    ("EL.PA", "EssilorLuxottica", "essilorluxottica", "FR", "Healthcare"), ("ORA.PA", "Orange", "orange", "FR", "Communication Services"),
    ("PUB.PA", "Publicis", "publicis", "FR", "Communication Services"), ("ENGI.PA", "Engie", "engie", "FR", "Utilities"),
    ("VIE.PA", "Veolia", "veolia environnement", "FR", "Utilities"), ("CAP.PA", "Capgemini", "capgemini", "FR", "Technology"),
    ("ML.PA", "Michelin", "michelin", "FR", "Consumer Cyclical"), ("URW.PA", "Unibail-Rodamco-Westfield", "unibail", "FR", "Real Estate"),
    # Italien
    ("ENEL.MI", "Enel", "enel", "IT", "Utilities"), ("ISP.MI", "Intesa Sanpaolo", "intesa sanpaolo", "IT", "Financial Services"),
    ("G.MI", "Generali", "assicurazioni generali", "IT", "Financial Services"), ("UCG.MI", "UniCredit", "unicredit", "IT", "Financial Services"),
    ("SRG.MI", "Snam", "snam", "IT", "Utilities"), ("TRN.MI", "Terna", "terna", "IT", "Utilities"),
    ("RACE.MI", "Ferrari", "ferrari n", "NL", "Consumer Cyclical"), ("PST.MI", "Poste Italiane", "poste italiane", "IT", "Financial Services"),
    # Spanien und Portugal
    ("IBE.MC", "Iberdrola", "iberdrola", "ES", "Utilities"), ("ITX.MC", "Inditex", "industria de dise", "ES", "Consumer Cyclical"),
    ("TEF.MC", "Telefónica", "telef_nica", "ES", "Communication Services"), ("REP.MC", "Repsol", "repsol", "ES", "Energy"),
    ("ELE.MC", "Endesa", "endesa", "ES", "Utilities"), ("CABK.MC", "CaixaBank", "caixabank", "ES", "Financial Services"),
    ("NTGY.MC", "Naturgy", "naturgy", "ES", "Utilities"), ("ENG.MC", "Enagás", "enag_s", "ES", "Utilities"),
    ("AENA.MC", "Aena", "aena", "ES", "Industrials"), ("RED.MC", "Redeia", "redeia", "ES", "Utilities"),
    ("MAP.MC", "Mapfre", "mapfre", "ES", "Financial Services"), ("EDP.LS", "EDP", "edp", "PT", "Utilities"),
    ("GALP.LS", "Galp", "galp energia", "PT", "Energy"), ("JMT.LS", "Jerónimo Martins", "jer_nimo martins", "PT", "Consumer Defensive"),
    # Benelux
    ("AD.AS", "Ahold Delhaize", "ahold delhaize", "NL", "Consumer Defensive"), ("WKL.AS", "Wolters Kluwer", "wolters kluwer", "NL", "Industrials"),
    ("HEIA.AS", "Heineken", "heineken n", "NL", "Consumer Defensive"), ("KPN.AS", "KPN", "koninklijke kpn", "NL", "Communication Services"),
    ("NN.AS", "NN Group", "nn group", "NL", "Financial Services"), ("ASRNL.AS", "ASR Nederland", "asr nederland", "NL", "Financial Services"),
    ("AGN.AS", "Aegon", "aegon", "NL", "Financial Services"), ("ABN.AS", "ABN Amro", "abn amro bank", "NL", "Financial Services"),
    ("RAND.AS", "Randstad", "randstad", "NL", "Industrials"), ("AKZA.AS", "Akzo Nobel", "akzo nobel", "NL", "Basic Materials"),
    ("PRX.AS", "Prosus", "prosus", "NL", "Technology"), ("ABI.BR", "Anheuser-Busch InBev", "anheuser-busch inbev", "BE", "Consumer Defensive"),
    ("KBC.BR", "KBC", "kbc gro", "BE", "Financial Services"), ("UCB.BR", "UCB", "ucb", "BE", "Healthcare"),
    ("AGS.BR", "Ageas", "ageas", "BE", "Financial Services"),
    # Nordeuropa
    ("NDA-FI.HE", "Nordea", "nordea bank", "FI", "Financial Services"), ("KNEBV.HE", "Kone", "kone oyj", "FI", "Industrials"),
    ("SAMPO.HE", "Sampo", "sampo", "FI", "Financial Services"), ("FORTUM.HE", "Fortum", "fortum", "FI", "Utilities"),
    ("UPM.HE", "UPM-Kymmene", "upm-kymmene", "FI", "Basic Materials"), ("NESTE.HE", "Neste", "neste", "FI", "Energy"),
    ("ELISA.HE", "Elisa", "elisa", "FI", "Communication Services"), ("VOLV-B.ST", "Volvo", "volvo", "SE", "Industrials"),
    ("ATCO-A.ST", "Atlas Copco", "atlas copco", "SE", "Industrials"), ("INVE-B.ST", "Investor AB", "investor a", "SE", "Financial Services"),
    ("SEB-A.ST", "SEB", "skandinaviska enskilda", "SE", "Financial Services"), ("SHB-A.ST", "Handelsbanken", "svenska handelsbanken", "SE", "Financial Services"),
    ("SWED-A.ST", "Swedbank", "swedbank", "SE", "Financial Services"), ("HM-B.ST", "H&M", "hennes & mauritz", "SE", "Consumer Cyclical"),
    ("SAND.ST", "Sandvik", "sandvik", "SE", "Industrials"), ("ASSA-B.ST", "Assa Abloy", "assa abloy", "SE", "Industrials"),
    ("TELIA.ST", "Telia", "telia company", "SE", "Communication Services"), ("ESSITY-B.ST", "Essity", "essity", "SE", "Consumer Defensive"),
    ("DSV.CO", "DSV", "dsv a", "DK", "Industrials"), ("CARL-B.CO", "Carlsberg", "carlsberg", "DK", "Consumer Defensive"),
    ("MAERSK-B.CO", "A.P. Møller-Mærsk", "m_ller", "DK", "Industrials"), ("DANSKE.CO", "Danske Bank", "danske bank", "DK", "Financial Services"),
    ("COLO-B.CO", "Coloplast", "coloplast", "DK", "Healthcare"), ("EQNR.OL", "Equinor", "equinor", "NO", "Energy"),
    ("DNB.OL", "DNB", "dnb bank", "NO", "Financial Services"), ("TEL.OL", "Telenor", "telenor", "NO", "Communication Services"),
    ("ORK.OL", "Orkla", "orkla", "NO", "Consumer Defensive"), ("MOWI.OL", "Mowi", "mowi", "NO", "Consumer Defensive"),
    ("YAR.OL", "Yara", "yara international", "NO", "Basic Materials"), ("NHY.OL", "Norsk Hydro", "norsk hydro", "NO", "Basic Materials"),
    ("GJF.OL", "Gjensidige", "gjensidige", "NO", "Financial Services"),
    # Österreich und Irland
    ("OMV.VI", "OMV", "omv aktiengesellschaft", "AT", "Energy"), ("VER.VI", "Verbund", "verbund ag", "AT", "Utilities"),
    ("EBS.VI", "Erste Group", "erste group", "AT", "Financial Services"), ("KRZ.IR", "Kerry Group", "kerry group", "IE", "Consumer Defensive"),
    # Großbritannien (nicht schon über die SEC)
    ("LGEN.L", "Legal & General", "legal & general group", "GB", "Financial Services"), ("NG.L", "National Grid", "national grid plc", "GB", "Utilities"),
    ("SSE.L", "SSE", "sse plc", "GB", "Utilities"), ("IMB.L", "Imperial Brands", "imperial brands", "GB", "Consumer Defensive"),
    ("AV.L", "Aviva", "aviva", "GB", "Financial Services"), ("REL.L", "RELX", "relx", "GB", "Industrials"),
    ("TSCO.L", "Tesco", "tesco", "GB", "Consumer Defensive"), ("PHNX.L", "Phoenix Group", "phoenix group", "GB", "Financial Services"),
    ("MNG.L", "M&G", "m&g plc", "GB", "Financial Services"), ("RKT.L", "Reckitt", "reckitt", "GB", "Consumer Defensive"),
    ("BA.L", "BAE Systems", "bae systems", "GB", "Industrials"), ("GLEN.L", "Glencore", "glencore", "JE", "Basic Materials"),
    ("UU.L", "United Utilities", "united utilities group", "GB", "Utilities"), ("SVT.L", "Severn Trent", "severn trent", "GB", "Utilities"),
    ("NWG.L", "NatWest", "natwest group", "GB", "Financial Services"), ("BT-A.L", "BT Group", "bt group", "GB", "Communication Services"),
    ("TW.L", "Taylor Wimpey", "taylor wimpey", "GB", "Consumer Cyclical"), ("PSN.L", "Persimmon", "persimmon", "GB", "Consumer Cyclical"),
    ("SGRO.L", "Segro", "segro", "GB", "Real Estate"),
    # Schweiz (nur, wer freiwillig ESEF einreicht)
    ("ROG.SW", "Roche", "roche holding", "CH", "Healthcare"),
]

# Dividende je Aktie: vorgeschlagene Dividende fuer das Geschaeftsjahr (Kontinentaleuropa), im Jahr gezahlte (UK: Zwischen- plus Schlussdividende)
DPS_VORSCHLAG = ["DividendsProposedOrDeclaredBeforeFinancialStatementsAuthorisedForIssueButNotRecognisedAsDistributionToOwnersPerShare"]
DPS_GEZAHLT = ["DividendsRecognisedAsDistributionsToOwnersPerShare"]
DPS_FREI = re.compile(r"Dividend.*PerShare|PerShare.*Dividend", re.I)
DPS_SPERRE = re.compile(r"Prefer|Interim|Special|Extraordinary|Hybrid", re.I)
CAPEX_FREI = re.compile(r"CapitalExpenditure|(Purchase|Acquisition|Payments?For|Investments?In|Payments?ToAcquire).*(PropertyPlant|TangibleAssets|TangibleFixedAssets|IntangibleAssets)", re.I)
K_ESEF = dict(K_IFRS)
K_ESEF["eps_verw"] = K_IFRS["eps_verw"] + ["BasicEarningsLossPerShare", "BasicEarningsPerShare"]
K_ESEF["capex"] = K_IFRS["capex"] + ["PurchaseOfPropertyPlantAndEquipmentAndIntangibleAssets", "PurchaseOfPropertyPlantAndEquipment"]
ALLE_NAMEN = {n for v in K_ESEF.values() for n in v} | set(DPS_VORSCHLAG) | set(DPS_GEZAHLT)
BETRAG_POS = {"capex", "dividenden_gezahlt", "aktienrueckkauf", "zinsaufwand"}
DAUER = {"umsatz", "gewinn", "eps_verw", "dividenden_gezahlt", "operativer_cf", "capex", "aktienrueckkauf", "aktien_verw",
         "bruttogewinn", "operatives_ergebnis", "abschreibungen", "zinsaufwand", "steuern"}


def get(url, roh=False):
    for v in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                b = r.read()
                return b if roh else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and v < 4:
                time.sleep(30 * (v + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if v < 4:
                time.sleep(10); continue
            raise


def norm(s):
    s = s.lower()
    for a, b in (("é", "e"), ("è", "e"), ("ó", "o"), ("ø", "o"), ("æ", "ae"), ("á", "a"), ("&", " and ")):
        s = s.replace(a, b)
    s = re.sub(r"\b(s\.?a\.?|s\.?e\.?|n\.?v\.?|plc|oyj|abp|asa|a/s|ab|ag|s\.?p\.?a\.?|aktiengesellschaft|group|holding|publ)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def lei_suchen(name, such, land):
    """Rechtsträger per Namenssuche finden: unter allen Treffern der mit dem aehnlichsten Namen und passendem Land."""
    flt = json.dumps([{"name": "entity.name", "op": "ilike", "val": f"%{such}%"}, {"name": "country", "op": "eq", "val": land}])
    try:
        j = get(f"{BASIS}/api/filings?include=entity&sort=-period_end&page[size]=60&filter=" + urllib.parse.quote(flt))
    except urllib.error.HTTPError:   # Filter auf das Land nicht moeglich: nur nach Namen
        j = get(f"{BASIS}/api/filings?include=entity&sort=-period_end&page[size]=60&filter=" + urllib.parse.quote(json.dumps([json.loads(flt)[0]])))
    ent = {e.get("id"): e.get("attributes", {}) for e in j.get("included", []) if e.get("type") == "entity"}
    namen, laender = {}, {}
    for d in j.get("data", []):
        rel = ((d.get("relationships") or {}).get("entity") or {}).get("data") or {}
        a = ent.get(rel.get("id"), {})
        at = d.get("attributes") or {}
        ju = at.get("json_url") or ""
        lei = a.get("identifier") or (ju.split("/")[1] if ju.startswith("/") else None)
        if lei and a.get("name"):
            namen[lei] = a["name"]
            laender.setdefault(lei, set()).add(at.get("country") or "")
    muster = re.compile(r"(^|[^a-z])" + re.escape(such.lower()).replace("_", ".").replace("\\.", "."), re.I)
    best, bwert = None, 0.0
    for lei, n in namen.items():
        w = difflib.SequenceMatcher(None, norm(n), norm(name)).ratio()
        if muster.search(n.lower()):
            w += 0.5   # Suchbegriff steht am Wortanfang im Namen
        w += 0.3 if land in laender[lei] else -0.4
        if w > bwert:
            best, bwert = (lei, n), w
    return best if best and bwert >= 0.75 else None


def berichte(lei):
    """Alle Jahresberichte eines Rechtsträgers, je Stichtag einer (bevorzugt die erste Sprachfassung)."""
    try:
        j = get(f"{BASIS}/api/entities/{lei}/filings?page[size]=50")
    except urllib.error.HTTPError:
        flt = json.dumps([{"name": "entity.identifier", "op": "eq", "val": lei}])
        j = get(f"{BASIS}/api/filings?include=entity&page[size]=50&filter=" + urllib.parse.quote(flt))
    je = {}
    for d in j.get("data", []):
        a = d.get("attributes", {})
        if not a.get("json_url") or not a.get("period_end"):
            continue
        alt = je.get(a["period_end"])
        if alt is None or ("/0/" in a["json_url"] and "/0/" not in alt["json_url"]) or \
                (("/0/" in a["json_url"]) == ("/0/" in alt["json_url"]) and (a.get("date_added") or "") > (alt.get("date_added") or "")):
            je[a["period_end"]] = a
    return [je[k] for k in sorted(je)]


def periode(p):
    """xBRL-JSON-Zeitraum -> (Beginn, Ende) als Datum; Enden mit T00:00:00 sind exklusiv (ein Tag zurück)."""
    def d(s, ende):
        if "T" in s:
            x = datetime.datetime.fromisoformat(s[:19])
            if ende and x.time() == datetime.time(0):
                x -= datetime.timedelta(days=1)
            return x.date()
        return datetime.date.fromisoformat(s[:10])
    if "/" in p:
        a, b = p.split("/")
        return d(a, False), d(b, True)
    return None, d(p, True)


def relevant(n):
    return n in ALLE_NAMEN or DPS_FREI.search(n) or CAPEX_FREI.search(n)


def auslesen(x):
    """Rohwerte ohne Segment-Dimensionen, nur Geschaeftsjahre und nur die Konzepte, die wir nutzen:
    {konzept: {ende: [wert, einheit, ist_zeitraum]}}. Wird je Bericht gespeichert, damit Regelaenderungen keinen Neuabruf brauchen."""
    werte = {}
    for f in (x.get("facts") or {}).values():
        dim = f.get("dimensions", {})
        if set(dim) - {"concept", "entity", "period", "unit", "language"}:
            continue   # Segment, Region, Eigenkapitalkomponente ...
        lokal = str(dim.get("concept", "")).split(":")[-1]
        if not relevant(lokal):
            continue
        try:
            v = float(f.get("value"))
            a, e = periode(str(dim.get("period", "")))
        except (TypeError, ValueError):
            continue
        if a is not None and not 330 <= (e - a).days <= 380:
            continue   # nur ganze Geschaeftsjahre
        werte.setdefault(lokal, {}).setdefault(e.isoformat(), [v, str(dim.get("unit", "")), a is not None])
    return werte


def auswerten(werte):
    """Rohwerte -> {kennzahl: {ende: wert}} und Berichtswaehrung."""
    zaehl = {}
    for n in K_IFRS["umsatz"] + K_IFRS["gewinn"]:
        for v, u, _ in werte.get(n, {}).values():
            m = re.fullmatch(r"iso4217:([A-Z]{3})", u)
            if m:
                zaehl[m.group(1)] = zaehl.get(m.group(1), 0) + 1
    w = max(zaehl, key=zaehl.get) if zaehl else None

    def passt(u, je_aktie):
        if not w:
            return True
        if je_aktie:   # Betrag je Aktie in Berichtswaehrung (Pence bei Pfund erlaubt)
            return "shares" in u and (u.startswith(f"iso4217:{w}") or (w == "GBP" and "GBX" in u.upper()))
        if u.startswith("iso4217:"):
            return u == f"iso4217:{w}"
        return True   # Stueckzahlen, reine Zahlen

    def reihe(namen, dauer, je_aktie=False):
        r = {}
        for n in namen:
            for e, (v, u, ist_dauer) in werte.get(n, {}).items():
                if ist_dauer == dauer and e not in r and passt(u, je_aktie):
                    if "GBX" in u.upper():
                        v /= 100
                    if je_aktie and not 0 < abs(v) < 5000:
                        continue
                    r[e] = v
        return r

    aus = {}
    for k, namen in K_ESEF.items():
        if namen:
            aus[k] = reihe(namen, k in DAUER, k == "eps_verw")
    if not any(aus.get("capex", {}).values()):
        frei = [n for n in werte if CAPEX_FREI.search(n) and not re.search(r"Proceeds|Sale|Disposal", n, re.I)]
        aus["capex"] = reihe(sorted(frei), True)
    for k in BETRAG_POS:
        aus[k] = {e: abs(v) for e, v in aus.get(k, {}).items()}
    vor, gez = reihe(DPS_VORSCHLAG, True, True), reihe(DPS_GEZAHLT, True, True)
    for e, v in reihe(DPS_VORSCHLAG, False, True).items():
        vor.setdefault(e, v)
    if not vor and not gez and w:   # Dividende in anderer Waehrung beschlossen (AB InBev: Bericht in Dollar, Dividende in Euro)
        for n, ziel in ((DPS_VORSCHLAG[0], vor), (DPS_GEZAHLT[0], gez)):
            for e, (v, u, _) in werte.get(n, {}).items():
                m = re.match(r"iso4217:([A-Z]{3})/.*shares", u)
                if m and m.group(1) != w and 0 < v < 5000:
                    ziel.setdefault(e, v); aus.setdefault("_dps_wae", {})[e] = m.group(1)
    frei = {}
    for n in sorted(werte):
        if DPS_FREI.search(n) and not DPS_SPERRE.search(n) and n not in DPS_VORSCHLAG + DPS_GEZAHLT:
            for e, v in {**reihe([n], True, True), **reihe([n], False, True)}.items():
                if v > 0:
                    frei.setdefault(e, v)
    aus["_dps_vor"], aus["_dps_gez"], aus["_dps_frei"] = vor, gez, frei
    return aus, w


def isin_holen(lei, kurse, land):
    """LEI -> ISINs (GLEIF, alle Seiten; Banken haben Tausende Anleihen), davon die in Euro gehandelten ohne US-Zertifikate,
    dann per OpenFIGI die erste, die wirklich eine Aktie ist."""
    kand = []
    for seite in range(1, 40):
        try:
            j = get(f"https://api.gleif.org/api/v1/lei-records/{lei}/isins?page[size]=200&page[number]={seite}")
        except Exception:
            break
        for d in j.get("data", []):
            i = d.get("attributes", {}).get("isin")
            if i and i in kurse and kurse[i][2] == "EUR" and not i.startswith("US"):
                kand.append(i)
        if seite >= ((j.get("meta") or {}).get("pagination") or {}).get("lastPage", 1):
            break
        time.sleep(0.5)
    kand = sorted(set(kand), key=lambda i: (i[:2] != land, i))[:30]
    for a in range(0, len(kand), 10):
        teil = kand[a:a + 10]
        try:
            req = urllib.request.Request("https://api.openfigi.com/v3/mapping", headers={"Content-Type": "application/json", **UA},
                                         data=json.dumps([{"idType": "ID_ISIN", "idValue": i} for i in teil]).encode())
            res = json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception:
            time.sleep(15); continue
        for i, r in zip(teil, res):
            d = ((r or {}).get("data") or [{}])[0]
            if d.get("marketSector") == "Equity" and re.search(r"Common Stock|Ordinary|Share", d.get("securityType", "") + d.get("securityType2", ""), re.I) \
                    and "Pref" not in d.get("securityType", ""):
                return i
        time.sleep(3)
    return None


XETRA_LISTE = "https://www.cashmarket.deutsche-boerse.com/resource/blob/1528/ef73eef09b2e8353e17090956eee878b/data/t7-xetr-allTradableInstruments.csv"
_INST = None


def isin_per_name(name, rname, land, kurse):
    """Ersatzweg: Heimat-ISIN ueber den Namen in der Xetra-Instrumentenliste (nur Aktien, nur gehandelte, Länderkennung passt)."""
    global _INST
    import csv, io
    from isin_zuordnung import norm as xnorm
    if _INST is None:
        _INST = []
        try:
            raw = urllib.request.urlopen(urllib.request.Request(XETRA_LISTE, headers={"User-Agent": "Mozilla/5.0 (dividenden-rechner.de)"}), timeout=120).read().decode("utf-8-sig", "replace")
            zeilen = raw.splitlines()
            kopf = next(i for i, z in enumerate(zeilen) if "ISIN" in z and ";" in z)
            for r in csv.DictReader(io.StringIO("\n".join(zeilen[kopf:])), delimiter=";"):
                isin = (r.get("ISIN") or "").strip()
                grp = (r.get("Product Assignment Group Description") or "").upper()
                if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", isin) and not any(x in grp for x in ("ETF", "ETP", "ETC", "ETN", "FUND", "BOND")):
                    nm = r.get("Instrument") or r.get("Instrument Name") or list(r.values())[2]
                    _INST.append((isin, xnorm(nm)))
        except Exception as e:
            print("Xetra-Liste nicht ladbar:", e)
    ziel = [xnorm(name), xnorm(rname or "")]
    best, bw = None, 0
    for isin, n in _INST:
        if isin[:2] != land or isin not in kurse or kurse[isin][2] != "EUR" or not n:
            continue
        w = max(difflib.SequenceMatcher(None, n, z).ratio() for z in ziel if z)
        if w > bw:
            best, bw = isin, w
    return best if bw >= 0.8 else None


def main():
    start = time.time()
    os.makedirs("data/esef", exist_ok=True)
    try:
        sp = json.load(open("data/esef/speicher.json", encoding="utf-8"))
    except Exception:
        sp = {}
    if sp.get("version") != 2:   # Version 2: Rohwerte je Bericht, strengere Namenssuche, ISIN nur fuer Aktien
        sp = {"version": 2}
    sp.setdefault("lei", {}); sp.setdefault("berichte", {}); sp.setdefault("isin", {}); sp.setdefault("geprueft", {})
    try:
        kurse = json.load(open("data/kurse/xetra-letzter.json"))["k"]
    except Exception:
        kurse = {}
    heute = datetime.date.today().isoformat()
    notizen = []
    # Wer am laengsten nicht geprueft wurde, kommt zuerst dran
    reihenfolge = sorted(FIRMEN, key=lambda f: sp["geprueft"].get(f[0], ""))
    for t, name, such, land, sektor in reihenfolge:
        if time.time() - start > ZEITBUDGET:
            notizen.append("Zeitbudget erreicht, Rest im nächsten Lauf"); break
        if sp["geprueft"].get(t) == heute:
            continue
        try:
            if not sp["lei"].get(t):   # noch nie gesucht oder beim letzten Mal nicht gefunden
                r = lei_suchen(name, such, land)
                sp["lei"][t] = list(r) if r else None
                time.sleep(3)
            if not sp["lei"][t]:
                sp["geprueft"][t] = heute; continue
            lei = sp["lei"][t][0]
            for b in berichte(lei):
                schl = b["json_url"]
                if schl in sp["berichte"]:
                    continue
                x = get(BASIS + schl if schl.startswith("/") else schl)
                roh = auslesen(x)
                sp["berichte"][schl] = {"lei": lei, "ende": b["period_end"], "roh": roh}
                print(t, b["period_end"], len(roh), flush=True)
                time.sleep(4)
            if t not in sp["isin"] or sp["isin"][t] is None:
                sp["isin"][t] = isin_holen(lei, kurse, land) or isin_per_name(name, sp["lei"][t][1], land, kurse)
                time.sleep(1)
            sp["geprueft"][t] = heute
        except Exception as e:
            notizen.append(f"{t}: {str(e)[:100]}")
            time.sleep(5)
        json.dump(sp, open("data/esef/speicher.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    # Zusammenbauen: je Firma alle Berichte in zeitlicher Folge, neuere ueberschreiben aeltere
    firmen, zeilen = {}, []
    for t, name, such, land, sektor in FIRMEN:
        info = sp["lei"].get(t)
        if not info:
            zeilen.append(f"| {t} | {name} | – | {'nicht gefunden' if t in sp['lei'] else 'noch nicht geprüft'} | | | |"); continue
        lei, rname = info
        bs = sorted((b for b in sp["berichte"].values() if b["lei"] == lei), key=lambda b: b["ende"])
        if not bs:
            zeilen.append(f"| {t} | {name} | {rname} | keine Berichte | | | |"); continue
        ausw = [auswerten(b["roh"]) for b in bs]
        waehr = [x[1] for x in ausw if x[1]]
        w = waehr[-1] if waehr else "EUR"
        reihen = {}
        for aus, bw in ausw:
            if bw and bw != w:
                continue   # Waehrungswechsel: aeltere Berichte in anderer Waehrung auslassen
            for k, r in aus.items():
                for e, v in r.items():
                    if v is not None:
                        reihen.setdefault(k, {})[e] = v
        enden = set(reihen.get("umsatz", {})) | set(reihen.get("gewinn", {}))
        if not enden:
            zeilen.append(f"| {t} | {name} | {rname} | keine Jahreswerte | | | |"); continue
        gj = max(enden)
        # Dividende je Aktie: UK im Jahr gezahlt, sonst die vorgeschlagene fuer das Geschaeftsjahr
        # UK: die "vorgeschlagene" Dividende ist nur die Schluss- oder letzte Quartalsrate, deshalb dort nur gezahlte Werte
        reih = ("_dps_gez",) if land in ("GB", "JE") else ("_dps_vor", "_dps_gez", "_dps_frei")
        dps = {}
        for k in reversed(reih):
            dps.update(reihen.get(k, {}))
        dps = {e: v for e, v in dps.items() if e in enden}
        dwae = reihen.get("_dps_wae", {})
        dps_w = dwae.get(max(dps)) if dps else None
        if dps:   # nur Jahre in derselben Waehrung wie der letzte Wert
            dps = {e: v for e, v in dps.items() if dwae.get(e) == dps_w}
        # Gewinn je Aktie in Pence statt Pfund (oder umgekehrt) erkennen: Gewinn / EPS muss zur Aktienzahl passen
        eps, av, gw = reihen.get("eps_verw", {}), reihen.get("aktien_verw", {}), reihen.get("gewinn", {})
        for e in list(eps):
            if e in av and e in gw and av[e] and eps[e]:
                q = (gw[e] / eps[e]) / av[e]
                if 60 < q < 160:
                    eps[e] /= 100   # Gewinn je Aktie als Pence-Zahl in Pfund getaggt
                elif 0.006 < q < 0.016:
                    eps[e] *= 100
        for e in gw:   # Aktienzahl aus Gewinn / Gewinn je Aktie, wo sie nicht getaggt ist
            if e not in av and eps.get(e) and gw[e] and gw[e] / eps[e] > 0:
                av[e] = round(gw[e] / eps[e])
        reihen["aktien_verw"] = av
        fa = {"n": name, "rechtstraeger": rname, "lei": lei, "isin": sp["isin"].get(t), "land": land, "sektor": sektor,
              "gj": gj, "w": w, "std": "IFRS", "quelle": "ESEF", "k": {}}
        if dps_w:
            fa["dps_w"] = dps_w   # Dividende je Aktie steht in dieser Waehrung, nicht in der Berichtswaehrung
        if dps:
            fa["k"]["dividende_je_aktie"] = [[e, round(dps[e], 4)] for e in sorted(dps)[-JAHRE:]]
        dg = reihen.get("dividenden_gezahlt", {})
        ber = {} if dps_w else {e: round(dg[e] / av[e], 4) for e in dg if e in av and av[e] and dg[e] and e not in dps}
        if ber:
            fa["k"]["dividende_je_aktie_ber"] = [[e, ber[e]] for e in sorted(ber)[-JAHRE:]]
        eb = {e: round(gw[e] / av[e], 4) for e in gw if e in av and av[e] and e not in eps}
        if eb:
            fa["k"]["eps_ber"] = [[e, eb[e]] for e in sorted(eb)[-JAHRE:]]
        for k, r in reihen.items():
            if k.startswith("_") or not r:
                continue
            if k in DAUER or k in K_IFRS:
                r = {e: v for e, v in r.items() if e in enden} if k in DAUER else r
                ends = sorted(r)[-JAHRE:]
                if ends:
                    fa["k"][k] = [[e, r[e]] for e in ends]
        firmen[t] = fa
        kern = ["umsatz", "gewinn", "eps_verw", "dividende_je_aktie", "operativer_cf", "capex", "eigenkapital"]
        da = [k for k in kern if k in fa["k"] and fa["k"][k][-1][0] >= gj or
              (k == "eps_verw" and "eps_ber" in fa["k"]) or (k == "dividende_je_aktie" and "dividende_je_aktie_ber" in fa["k"])]
        jahre = sorted({e[:4] for e in enden})
        zeilen.append(f"| {t} | {name} | {rname} | {jahre[0]}–{jahre[-1]} ({w}) | {len(da)}/7 | "
                      f"{'ja' if fa['isin'] else 'fehlt'} | {', '.join(k for k in kern if k not in da) or '–'} |")

    json.dump({"stand": heute, "quelle": "ESEF-Jahresberichte (filings.xbrl.org), IFRS", "firmen": firmen},
              open("data/esef/fundamentals.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    mit_kurs = sum(1 for f in firmen.values() if f.get("isin"))
    md = [f"# ESEF-Jahreszahlen Europa: Abdeckung (Stand {heute})", "",
          f"{len(FIRMEN)} Firmen in der Liste, mit Jahreszahlen: **{len(firmen)}**, davon mit Börsenkurs (ISIN): **{mit_kurs}**.", "",
          "| Kürzel | Name | Rechtsträger laut Bericht | Jahre | Kern | Kurs | fehlt |", "|---|---|---|---|---|---|---|"] + zeilen
    if notizen:
        md += ["", "## Hinweise", ""] + [f"- {n}" for n in notizen]
    open("data/esef-abdeckung.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md[:4] + notizen))


if __name__ == "__main__":
    main()
