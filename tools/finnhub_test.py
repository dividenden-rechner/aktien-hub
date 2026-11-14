"""TESTLAUF: Was liefert Finnhub mit dem Schluessel? Kurs, Profil, Kennzahlen und Dividenden fuer ein paar Boersen.
Schluessel aus dem Geheimnis FINNHUB_API_KEY. Ausgabe: data/finnhub-test.json
"""
import datetime as dt, json, os, time, urllib.parse, urllib.request

KEY = os.environ["FINNHUB_API_KEY"]
BASE = "https://finnhub.io/api/v1"
SYMBOLE = {"AAPL": "USA", "7203.T": "Japan", "WBC.AX": "Australien", "005930.KS": "Korea", "0005.HK": "Hongkong"}
ENDPUNKTE = {
    "quote": ("quote", {}),
    "profil": ("stock/profile2", {}),
    "kennzahlen": ("stock/metric", {"metric": "all"}),
    "dividende": ("stock/dividend", {"from": (dt.date.today() - dt.timedelta(days=730)).isoformat(), "to": dt.date.today().isoformat()}),
}

def abruf(pfad, params):
    q = urllib.parse.urlencode({**params, "token": KEY})
    try:
        with urllib.request.urlopen(f"{BASE}/{pfad}?{q}", timeout=30) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:300]

ergebnis = []
for sym, land in SYMBOLE.items():
    eintrag = {"symbol": sym, "land": land}
    for name, (pfad, extra) in ENDPUNKTE.items():
        status, text = abruf(pfad, {"symbol": sym, **extra})
        try:
            j = json.loads(text)
        except Exception:
            j = None
        if name == "kennzahlen" and isinstance(j, dict):
            m = j.get("metric") or {}
            eintrag[name] = {"status": status, "felder": len(m), "beispiel": {k: m.get(k) for k in ("dividendYieldIndicatedAnnual", "peTTM", "marketCapitalization", "currency") if k in m}}
        elif name == "dividende" and isinstance(j, list):
            eintrag[name] = {"status": status, "anzahl": len(j), "letzte": j[:2]}
        elif name == "quote" and isinstance(j, dict):
            eintrag[name] = {"status": status, "c": j.get("c"), "dp": j.get("dp"), "t": j.get("t")}
        elif name == "profil" and isinstance(j, dict):
            eintrag[name] = {"status": status, **{k: j.get(k) for k in ("name", "exchange", "country", "currency", "marketCapitalization", "finnhubIndustry") if k in j}}
        else:
            eintrag[name] = {"status": status, "antwort": text[:200]}
        time.sleep(1.1)
    ergebnis.append(eintrag)

json.dump({"stand": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "firmen": ergebnis}, open("data/finnhub-test.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(ergebnis, ensure_ascii=False, indent=1)[:4000])
