"""TESTLAUF: Liefert der FMP-Gratisschluessel Kurs, Boersenwert und letzte Dividende fuer die BDCs ohne Kurs?
Ausgabe: data/fmp-bdc-test.json (nur Status und Zahlen, kein Schluessel)."""
import datetime as dt, json, os, urllib.request, urllib.parse, time

KEY = os.environ["FMP_API_KEY"]
SYMS = ["HTGC", "TSLX", "MSDL", "PSEC", "CSWC", "NMFC", "CGBD", "SLRC", "NCDL", "MSIF", "CCAP", "CION",
        "PSBD", "SAR", "SCM", "HRZN", "LIEN", "TPVG", "WHF", "GECC", "OFS", "ICMB", "RAND", "GBDC", "ARCC", "MAIN"]
ERG = {}
for sym in SYMS:
    url = "https://financialmodelingprep.com/stable/profile?" + urllib.parse.urlencode({"symbol": sym, "apikey": KEY})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dividenden-rechner.de Datensammlung"}), timeout=60) as r:
            j = json.loads(r.read())
        p = j[0] if isinstance(j, list) and j else (j if isinstance(j, dict) else {})
        if not p:
            ERG[sym] = {"leer": True}
        else:
            ERG[sym] = {"kurs": p.get("price"), "boersenwert": p.get("marketCap"), "letzte_dividende": p.get("lastDividend"), "boerse": p.get("exchange")}
    except urllib.error.HTTPError as e:
        ERG[sym] = {"http": e.code}
    except Exception as e:
        ERG[sym] = {"fehler": str(e)[:120]}
    time.sleep(0.3)
json.dump({"stand": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "ergebnis": ERG}, open("data/fmp-bdc-test.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(ERG, ensure_ascii=False, indent=1))
