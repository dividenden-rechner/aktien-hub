"""TESTLAUF: Gewinn je Aktie (Jahr, laufendes Jahr, Vorjahr) aus EDINET fuer ein paar japanische Firmen.

TTM = Jahreswert (Jahresbericht 120) + Jahresbeginn bis Stichtag (Quartalsbericht 043000)
      - Jahresbeginn bis Stichtag im Vorjahr (steht im selben Quartalsbericht).
Quelle: EDINET-API v2 (FSA). Schluessel aus dem Geheimnis EDINET_API_KEY.
Ausgabe: data/edinet-test.json
"""
import datetime as dt, io, json, os, re, time, zipfile, urllib.request

KEY = os.environ["EDINET_API_KEY"]
BASE = "https://api.edinet-fsa.go.jp/api/v2"
FIRMEN = {"72030": "Toyota", "67580": "Sony", "83060": "MUFG", "83160": "SMFG", "72670": "Honda"}
TAGE = 200

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dividenden-rechner.de Datensammlung"}), timeout=120) as r:
        return r.read()

def dokumente(tag):
    raw = get(f"{BASE}/documents.json?date={tag}&type=2&Subscription-Key={KEY}")
    return json.loads(raw).get("results", []) or []

def xbrl_text(doc_id):
    z = zipfile.ZipFile(io.BytesIO(get(f"{BASE}/documents/{doc_id}?type=1&Subscription-Key={KEY}")))
    namen = [n for n in z.namelist() if n.endswith(".xbrl") and "PublicDoc" in n]
    return z.read(namen[0]).decode("utf-8", errors="replace") if namen else ""

def kontexte(x):
    out = {}
    for cid, block in re.findall(r'<xbrli:context id="([^"]+)">(.*?)</xbrli:context>', x, re.S):
        if "explicitMember" in block:
            continue
        out[cid] = (re.search(r"<xbrli:startDate>([^<]+)", block), re.search(r"<xbrli:endDate>([^<]+)", block))
        out[cid] = (out[cid][0].group(1) if out[cid][0] else None, out[cid][1].group(1) if out[cid][1] else None)
    return out

def eps(x):
    werte = {}
    for name, ctx, val in re.findall(r"<(jppfs_cor:BasicEarningsLossPerShare\w*)\s[^>]*contextRef=\"([^\"]+)\"[^>]*>([-\d.]+)</", x):
        werte.setdefault(ctx, float(val))
    return werte

# Zeitraum absuchen
tage = [(dt.date.today() - dt.timedelta(days=i)).isoformat() for i in range(TAGE)]
gefunden = {}
for tag in tage:
    try:
        for d in dokumente(tag):
            sc = d.get("secCode")
            if sc in FIRMEN and d.get("docTypeCode") in ("120", "043000"):
                key = (sc, d["docTypeCode"])
                if key not in gefunden or d.get("submitDateTime", "") > gefunden[key].get("submitDateTime", ""):
                    gefunden[key] = d
    except Exception as e:
        print("Fehler", tag, e)
    time.sleep(0.3)

ergebnis = []
for sc, name in FIRMEN.items():
    jahr, quartal = gefunden.get((sc, "120")), gefunden.get((sc, "043000"))
    eintrag = {"firma": name, "secCode": sc, "jahresbericht": jahr and jahr.get("docID"), "quartalsbericht": quartal and quartal.get("docID")}
    try:
        if jahr:
            ex = eps(xbrl_text(jahr["docID"]))
            eintrag["eps_jahr"] = ex.get("CurrentYearDuration")
        if quartal:
            qx = xbrl_text(quartal["docID"])
            qe = eps(qx)
            eintrag["eps_ytd"] = qe.get("CurrentYTDDuration")
            eintrag["eps_ytd_vorjahr"] = qe.get("Prior1YTDDuration")
            ko = kontexte(qx)
            eintrag["stichtag"] = ko.get("CurrentYTDDuration", (None, None))[1]
        if eintrag.get("eps_jahr") is not None and eintrag.get("eps_ytd") is not None and eintrag.get("eps_ytd_vorjahr") is not None:
            eintrag["eps_ttm"] = round(eintrag["eps_jahr"] + eintrag["eps_ytd"] - eintrag["eps_ytd_vorjahr"], 2)
    except Exception as e:
        eintrag["fehler"] = str(e)
    ergebnis.append(eintrag)

json.dump({"stand": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), "firmen": ergebnis}, open("data/edinet-test.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(ergebnis, ensure_ascii=False, indent=1))
