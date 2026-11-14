"""Japan (EDINET) und Suedkorea (DART): Gewinn je Aktie (letzte 12 Monate) und Dividende je Aktie (letztes Geschaeftsjahr)
fuer alle Japan- und Korea-Werte aus data/asia-seed.txt. Schluessel: EDINET_API_KEY und DART_API_KEY.
Ausgabe: data/asien-fundamente.json. Ohne Kurse, die kommen aus einer anderen Quelle."""
import datetime as dt, io, json, os, re, time, urllib.parse, urllib.request, zipfile, xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDINET_KEY = os.environ.get("EDINET_API_KEY", "")
DART_KEY = os.environ.get("DART_API_KEY", "")
EBASE = "https://api.edinet-fsa.go.jp/api/v2"
DBASE = "https://opendart.fss.or.kr/api"
TAGE = 200
UA = {"User-Agent": "dividenden-rechner.de Datensammlung"}

def get(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()

# ---------- Seed: Japan und Korea
JP, KR = {}, {}
for line in open(os.path.join(ROOT, "data", "asia-seed.txt"), encoding="utf-8"):
    if line.startswith("#") or "|" not in line:
        continue
    sym, name = line.split("|")[:2]
    if sym.endswith(".T") and sym[:-2].isdigit() and len(sym[:-2]) == 4:
        JP[sym[:-2] + "0"] = (sym, name)          # EDINET-Code = 4-stellig + Pruefziffer 0
    elif sym.endswith(".KS"):
        KR[sym[:-3]] = (sym, name)

# ---------- EDINET (Japan)
def edinet_docs(tag):
    j = json.loads(get(f"{EBASE}/documents.json?date={tag}&type=2&Subscription-Key={EDINET_KEY}"))
    return j.get("results", []) or []

def edinet_xbrl(doc_id):
    z = zipfile.ZipFile(io.BytesIO(get(f"{EBASE}/documents/{doc_id}?type=1&Subscription-Key={EDINET_KEY}", timeout=300)))
    namen = [n for n in z.namelist() if n.endswith(".xbrl") and "PublicDoc" in n]
    return z.read(namen[0]).decode("utf-8", errors="replace") if namen else ""

def kontext_ohne_dim(x):
    ids = set()
    for cid, block in re.findall(r'<xbrli:context id="([^"]+)">(.*?)</xbrli:context>', x, re.S):
        if "explicitMember" not in block:
            ids.add(cid)
    return ids

def wert(x, element_regex, ctx_namen):
    """Wert zum ersten passenden Kontext (ohne Dimension), in der Reihenfolge der Kontextnamen."""
    gefunden = {}
    for name, ctx, val in re.findall(r'<(' + element_regex + r')\s[^>]*?contextRef="([^"]+)"[^>]*>([-\d.]+)</', x):
        gefunden.setdefault(ctx, float(val))
    for c in ctx_namen:
        if c in gefunden:
            return gefunden[c]
    return None

EDINET_INDEX = {}
def edinet_index():
    """Einmal fuer alle Tage: Jahres- (120) und Halbjahresberichte (160) je Firma, neuester Treffer zuerst."""
    for i in range(TAGE):
        tag = (dt.date.today() - dt.timedelta(days=i)).isoformat()
        try:
            for d in edinet_docs(tag):
                sc, typ = d.get("secCode"), d.get("docTypeCode")
                if sc in JP and typ in ("120", "160") and (sc, typ) not in EDINET_INDEX:
                    EDINET_INDEX[(sc, typ)] = d["docID"]
        except Exception:
            pass
        time.sleep(0.2)

def edinet_fundamente(sec):
    found = {"120": EDINET_INDEX.get((sec, "120")), "160": EDINET_INDEX.get((sec, "160"))}
    out = {"jahresbericht": found["120"], "halbjahresbericht": found["160"]}
    eps_re = r"[\w\-]+:BasicEarningsLossPerShare\w*"
    if found["120"]:
        x = edinet_xbrl(found["120"])
        out["eps_jahr"] = wert(x, eps_re, ["CurrentYearDuration"])
        out["dps_jahr"] = wert(x, r"jpcrp_cor:DividendPaidPerShareSummaryOfBusinessResults", ["CurrentYearDuration_NonConsolidatedMember", "CurrentYearDuration"])
    if found["160"]:
        x = edinet_xbrl(found["160"])
        out["eps_h1"] = wert(x, eps_re, ["InterimDuration", "CurrentYTDDuration", "CurrentSemiAnnualDuration"])
        out["eps_h1_vorjahr"] = wert(x, eps_re, ["Prior1InterimDuration", "Prior1YTDDuration", "Prior1SemiAnnualDuration"])
    return out

# ---------- DART (Korea)
def dart(pfad, **params):
    q = urllib.parse.urlencode({"crtfc_key": DART_KEY, **params})
    return json.loads(get(f"{DBASE}/{pfad}?{q}", timeout=60))

def konto(liste, feld, suche):
    for z in liste:
        if z.get("account_id") == suche[0] or all(s in z.get("account_nm", "") for s in suche[1]):
            try:
                return float(str(z.get(feld) or "").replace(",", ""))
            except ValueError:
                return None
    return None

KR_CODES = {}
if DART_KEY:
    zx = zipfile.ZipFile(io.BytesIO(get(f"{DBASE}/corpCode.xml?crtfc_key={DART_KEY}")))
    for e in ET.fromstring(zx.read("CORPCODE.xml")).iter("list"):
        sc = (e.findtext("stock_code") or "").strip()
        if sc in KR:
            KR_CODES[sc] = e.findtext("corp_code")

def korea_fundamente(sc):
    out = {"dart_code": KR_CODES.get(sc)}
    if not out["dart_code"]:
        out["fehler"] = "kein DART-Code"; return out
    jahr = dart("fnlttSinglAcntAll.json", corp_code=out["dart_code"], bsns_year=str(dt.date.today().year - 1), reprt_code="11011", fs_div="CFS")
    eps_j = jahr.get("list") or []
    out["eps_jahr"] = konto(eps_j, "thstrm_amount", ("ifrs-full_BasicEarningsLossPerShare", ["주당", "이익", "기본"]))
    h1 = dart("fnlttSinglAcntAll.json", corp_code=out["dart_code"], bsns_year=str(dt.date.today().year), reprt_code="11014", fs_div="CFS")
    if not h1.get("list"):
        h1 = dart("fnlttSinglAcntAll.json", corp_code=out["dart_code"], bsns_year=str(dt.date.today().year - 1), reprt_code="11014", fs_div="CFS")
        out["stichtag_jahr"] = dt.date.today().year - 1
    else:
        out["stichtag_jahr"] = dt.date.today().year
    out["eps_ytd"] = konto(h1.get("list") or [], "thstrm_add_amount", ("ifrs-full_BasicEarningsLossPerShare", ["주당", "이익", "기본"]))
    out["eps_ytd_vorjahr"] = konto(h1.get("list") or [], "frmtrm_add_amount", ("ifrs-full_BasicEarningsLossPerShare", ["주당", "이익", "기본"]))
    # Dividende je Aktie (Stammaktie) aus der Dividendenmitteilung
    div = dart("alotMatter.json", corp_code=out["dart_code"], bsns_year=str(dt.date.today().year - 1), reprt_code="11011")
    for z in div.get("list") or []:
        if "주당 현금배당금" in z.get("se", "") and "보통" in (z.get("stock_knd") or "보통"):
            try:
                out["dps_jahr"] = float(str(z.get("thstrm") or "").replace(",", ""))
            except ValueError:
                pass
            break
    return out

# ---------- Lauf
ergebnis = []
if EDINET_KEY:
    edinet_index()
for sec, (sym, name) in JP.items():
    e = {"ticker": sym, "name": name, "land": "Japan", "quelle": "EDINET"}
    try:
        e.update(edinet_fundamente(sec))
        if e.get("eps_jahr") is not None and e.get("eps_h1") is not None and e.get("eps_h1_vorjahr") is not None:
            e["eps_ttm"] = round(e["eps_jahr"] + e["eps_h1"] - e["eps_h1_vorjahr"], 2)
    except Exception as ex:
        e["fehler"] = str(ex)[:200]
    ergebnis.append(e)
for sc, (sym, name) in KR.items():
    e = {"ticker": sym, "name": name, "land": "Korea", "quelle": "DART"}
    try:
        if DART_KEY:
            e.update(korea_fundamente(sc))
            if None not in (e.get("eps_jahr"), e.get("eps_ytd"), e.get("eps_ytd_vorjahr")):
                e["eps_ttm"] = round(e["eps_jahr"] + e["eps_ytd"] - e["eps_ytd_vorjahr"], 2)
    except Exception as ex:
        e["fehler"] = str(ex)[:200]
    ergebnis.append(e)
    time.sleep(0.5)

json.dump({"stand": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "anzahl": len(ergebnis), "firmen": ergebnis},
          open(os.path.join(ROOT, "data", "asien-fundamente.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(ergebnis)} Firmen geschrieben")
