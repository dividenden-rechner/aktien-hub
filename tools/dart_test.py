"""TESTLAUF: Gewinn je Aktie (Jahr, laufendes Jahr, Vorjahr) aus DART (Finanzaufsicht Suedkorea) fuer ein paar Firmen.

TTM = Jahreswert (Geschaeftsbericht 11011) + Jahresbeginn bis Stichtag (Quartalsbericht 11014 = 3. Quartal)
      - Jahresbeginn bis Stichtag im Vorjahr (steht im selben Bericht).
Schluessel aus dem Geheimnis DART_API_KEY. Ausgabe: data/dart-test.json
"""
import datetime as dt, io, json, os, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET, zipfile

KEY = os.environ["DART_API_KEY"]
BASE = "https://opendart.fss.or.kr/api"
FIRMEN = {"005930": "Samsung Electronics", "000660": "SK Hynix", "105560": "KB Financial", "005380": "Hyundai Motor", "005490": "POSCO Holdings"}
JAHR = dt.date.today().year - 1   # letzter abgeschlossener Geschaeftsjahrgang

def get(pfad, **params):
    q = urllib.parse.urlencode({"crtfc_key": KEY, **params})
    with urllib.request.urlopen(urllib.request.Request(f"{BASE}/{pfad}?{q}", headers={"User-Agent": "dividenden-rechner.de Datensammlung"}), timeout=60) as r:
        return r.read()

# Firmencode-Liste (Boersenkuerzel -> DART-Firmencode)
zip_bytes = get("corpCode.xml")
xml = zipfile.ZipFile(io.BytesIO(zip_bytes)).read("CORPCODE.xml")
corp = {}
for e in ET.fromstring(xml).iter("list"):
    sc = (e.findtext("stock_code") or "").strip()
    if sc in FIRMEN:
        corp[sc] = e.findtext("corp_code")

KONTEN_DEBUG = []
def konto_eps(eintrag_liste, feld):
    for z in eintrag_liste:
        n = z.get("account_nm", "")
        if "주당" in n and len(KONTEN_DEBUG) < 40:
            KONTEN_DEBUG.append({"id": z.get("account_id"), "name": n, "sj": z.get("sj_div")})
        if z.get("account_id") == "ifrs-full_BasicEarningsLossPerShare" or ("주당" in n and "이익" in n and "기본" in n):
            wert = (z.get(feld) or "").replace(",", "")
            try:
                return float(wert)
            except ValueError:
                return None
    return None

STATUS = []
def bericht(corp_code, jahr, code):
    raw = get("fnlttSinglAcntAll.json", corp_code=corp_code, bsns_year=str(jahr), reprt_code=code, fs_div="CFS")
    j = json.loads(raw)
    STATUS.append({"jahr": jahr, "code": code, "status": j.get("status"), "message": j.get("message")})
    return j.get("list", []) or []

ergebnis = []
for sc, name in FIRMEN.items():
    e = {"firma": name, "boerse": sc, "dart_code": corp.get(sc)}
    try:
        if not corp.get(sc):
            e["fehler"] = "kein Firmencode"
            ergebnis.append(e); continue
        jahr = bericht(corp[sc], JAHR, "11011")
        e["eps_jahr"] = konto_eps(jahr, "thstrm_amount")
        q3 = bericht(corp[sc], JAHR + 1, "11014")
        if not q3:
            q3 = bericht(corp[sc], JAHR, "11014")
            e["stichtag_jahr"] = JAHR
        else:
            e["stichtag_jahr"] = JAHR + 1
        e["eps_ytd"] = konto_eps(q3, "thstrm_add_amount")
        e["eps_ytd_vorjahr"] = konto_eps(q3, "frmtrm_add_amount")
        if None not in (e.get("eps_jahr"), e.get("eps_ytd"), e.get("eps_ytd_vorjahr")):
            e["eps_ttm"] = round(e["eps_jahr"] + e["eps_ytd"] - e["eps_ytd_vorjahr"], 2)
    except Exception as ex:
        e["fehler"] = str(ex)
    ergebnis.append(e)
    time.sleep(0.5)

json.dump({"status_antworten": STATUS, "konten_debug": KONTEN_DEBUG, "stand": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "firmen": ergebnis}, open("data/dart-test.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(ergebnis, ensure_ascii=False, indent=1))
