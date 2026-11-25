"""Indonesien (IDX): Jahreszahlen aus den XBRL-Instanzen der Jahresberichte (Prüfbericht).
Quelle: idx.id GetFinancialReport (öffentlich), Dateien instance.zip. Ausgabe: data/idx/fundamentals.json
Format wie data/asien/fundamentals.json: firmen[Kürzel] = {n, w, gj, k: {Kennzahl: [[Datum, Wert]]}}.
Werte in IDR (Rupiah), Vorzeichen wie im Bericht, Dividenden und Investitionen als positive Beträge."""
import datetime, io, json, os, re, time, urllib.parse, urllib.request, zipfile

UA = {"User-Agent": "Mozilla/5.0 (dividenden-rechner.de Datensammlung)", "Accept": "application/json"}
API = "https://www.idx.id/primary/ListedCompany/GetFinancialReport?indexFrom=0&pageSize=12&year={j}&reportType=rdf&periode=audit&kodeEmiten={k}&SortColumn=KodeEmiten&SortOrder=asc"
AUSGABE = "data/idx/fundamentals.json"
JAHRE = range(2016, 2026)
# Kürzel -> Name laut Liste (MSCI Indonesia)
FIRMEN = {
    "BBCA": "Bank Central Asia", "BBRI": "Bank Rakyat Indonesia", "BMRI": "Bank Mandiri", "ASII": "Astra International",
    "BBNI": "Bank Negara Indonesia", "TLKM": "Telkom Indonesia", "INDF": "Indofood Sukses Makmur", "ADRO": "Alamtri Resources Indonesia",
    "PGAS": "Perusahaan Gas Negara", "AADI": "Adaro Andalan Indonesia", "MDKA": "Merdeka Copper Gold", "CPIN": "Charoen Pokphand Indonesia",
    "BRMS": "Bumi Resources Minerals", "BRPT": "Barito Pacific", "PTBA": "Tambang Batubara Bukit Asam", "KLBF": "Kalbe Farma",
    "ENRG": "Energi Mega Persada", "INKP": "Indah Kiat Pulp & Paper", "AMRT": "Sumber Alfaria Trijaya", "BUMI": "Bumi Resources",
    "AKRA": "AKR Corporindo", "ITMG": "Indo Tambangraya Megah", "INCO": "Vale Indonesia", "GGRM": "Gudang Garam",
    "CMRY": "Cisarua Mountain Dairy", "MEDC": "Medco Energi Internasional", "INTP": "Indocement Tunggal Prakarsa", "EXCL": "XLSMART Telecom Sejahtera",
    "MAPA": "MAP Aktif Adiperkasa", "JPFA": "Japfa Comfeed Indonesia", "TOWR": "Sarana Menara Nusantara", "BBTN": "Bank Tabungan Negara",
    "UNTR": "United Tractors",
}
# Kennzahl -> XBRL-Konzepte (der erste gefundene gewinnt)
KONZEPTE = {
    "umsatz": ["SalesAndRevenue"],
    "gewinn": ["ProfitLossAttributableToParentEntity", "ProfitLoss"],
    "operativer_cf": ["NetCashFlowsReceivedFromUsedInOperatingActivities"],
    "capex": ["PaymentsForAcquisitionOfPropertyAndEquipment"],
    "dividenden_gezahlt": ["DividendsPaidFromFinancingActivities"],
    "eigenkapital": ["EquityAttributableToEquityOwnersOfParentEntity", "Equity"],
    "bilanzsumme": ["Assets"],
    "zinsaufwand": ["InterestAndFinanceCosts"],
    "abschreibungen": ["DepreciationAndAmortisationExpenses"],
    "eps_verw": ["BasicEarningsLossPerShareFromContinuingOperations"],
}
ABS = {"capex", "dividenden_gezahlt"}


def get(u, bin_=False):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90).read()


def kontexte(t):
    """context-id -> (Datum des Stichtags, Zeitraumstart oder None, hat Dimensionen)"""
    out = {}
    for m in re.finditer(r"<xbrli:context id=\"([^\"]+)\">(.*?)</xbrli:context>", t, re.S):
        cid, body = m.group(1), m.group(2)
        dim = "<xbrli:segment" in body or "xbrldi:" in body
        inst = re.search(r"<xbrli:instant>([\d-]+)</xbrli:instant>", body)
        end = re.search(r"<xbrli:endDate>([\d-]+)</xbrli:endDate>", body)
        start = re.search(r"<xbrli:startDate>([\d-]+)</xbrli:startDate>", body)
        if inst:
            out[cid] = (inst.group(1), None, dim)
        elif end:
            out[cid] = (end.group(1), start.group(1) if start else None, dim)
    return out


def werte(t):
    """(konzeptname, datum, startdatum) -> wert, nur Kontexte ohne Dimensionen"""
    ktx = kontexte(t)
    out = {}
    for m in re.finditer(r"<idx-cor:([A-Za-z0-9_]+)\s([^>]*?)>([^<]*)</idx-cor:\1>", t):
        name, attrs, val = m.group(1), m.group(2), m.group(3)
        c = re.search(r'contextRef="([^"]+)"', attrs)
        if not c or c.group(1) not in ktx:
            continue
        datum, start, dim = ktx[c.group(1)]
        if dim:
            continue
        try:
            v = float(val.strip().replace(",", ""))
        except ValueError:
            continue
        sc = re.search(r'scale="(-?\d+)"', attrs)
        if sc:
            v *= 10 ** int(sc.group(1))
        if re.search(r'sign="-"', attrs):
            v = -v
        out[(name, datum, start)] = v
    return out


def jahreswerte(w):
    """Kennzahl -> [[Datum, Wert]] für Geschäftsjahre (Dauer ca. 1 Jahr, Stichtag) oder Stichtage"""
    res = {}
    for kz, konzepte in KONZEPTE.items():
        for kon in konzepte:
            eintraege = {}
            for (name, datum, start), v in w.items():
                if name != kon:
                    continue
                if start is None:
                    eintraege[datum] = v
                else:
                    d1 = datetime.date.fromisoformat(start); d2 = datetime.date.fromisoformat(datum)
                    if 350 <= (d2 - d1).days <= 380:
                        eintraege[datum] = v
            if eintraege:
                if kz in ABS:
                    eintraege = {d: abs(v) for d, v in eintraege.items()}
                res[kz] = [[d, eintraege[d]] for d in sorted(eintraege)]
                break
    return res


def bericht(kode, jahr):
    d = json.loads(get(API.format(j=jahr, k=kode)))
    if not d.get("Results"):
        return None, None
    r = d["Results"][0]
    anh = [a for a in r.get("Attachments", []) if a.get("File_Name") == "instance.zip"]
    if not anh:
        return r.get("NamaEmiten"), None
    pfad = "https://www.idx.id" + urllib.parse.quote(anh[0]["File_Path"], safe="/:")
    z = zipfile.ZipFile(io.BytesIO(get(pfad)))
    xml = next((n for n in z.namelist() if n.lower().endswith((".xbrl", ".xml"))), None)
    if not xml:
        return r.get("NamaEmiten"), None
    return r.get("NamaEmiten"), z.read(xml).decode("utf-8", "replace")


def main():
    start = time.time()
    firmen, notizen = {}, []
    for kode, name in FIRMEN.items():
        k_gesamt = {}
        nam = name
        for j in JAHRE:
            try:
                nam_j, t = bericht(kode, j)
                time.sleep(1)
                if nam_j:
                    nam = nam_j
                if not t:
                    continue
                for kz, reihe in jahreswerte(werte(t)).items():
                    k_gesamt.setdefault(kz, {})
                    for d, v in reihe:
                        k_gesamt[kz][d] = v
            except Exception as e:
                notizen.append(f"{kode} {j}: {str(e)[:120]}")
                time.sleep(2)
        if k_gesamt:
            firmen[kode] = {"n": nam, "w": "IDR", "k": {kz: [[d, v] for d, v in sorted(dd.items())] for kz, dd in k_gesamt.items()}}
        else:
            notizen.append(f"{kode}: keine Daten")
    os.makedirs(os.path.dirname(AUSGABE), exist_ok=True)
    json.dump({"stand": datetime.date.today().isoformat(), "quelle": "IDX-XBRL (Prüfbericht) über idx.id", "waehrung": "IDR", "firmen": firmen},
              open(AUSGABE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{len(firmen)} Firmen mit Daten von {len(FIRMEN)}")
    for n in notizen:
        print("hinweis:", n)


if __name__ == "__main__":
    main()
