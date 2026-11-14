"""TESTLAUF: Was liefert Massive (frueher Polygon.io) mit dem Schluessel? Kurs, Firmendaten, Dividenden, Finanzkennzahlen,
fuer US-Aktien und zum Vergleich einige internationale Kuerzel. Schluessel aus dem Geheimnis MASSIVE_API_KEY.
Ausgabe: data/massive-test.json
"""
import datetime as dt, json, os, time, urllib.parse, urllib.request

KEY = os.environ["MASSIVE_API_KEY"]
BASEN = ["https://api.massive.com", "https://api.polygon.io"]
HEUTE = dt.date.today()
TESTS = [
    ("kurs_vortag", "/v2/aggs/ticker/{t}/prev", {}),
    ("firma", "/v3/reference/tickers/{t}", {}),
    ("dividenden", "/v3/reference/dividends", {"ticker": "{t}", "limit": 4}),
    ("finanzen", "/vX/reference/financials", {"ticker": "{t}", "limit": 1}),
]
SYMBOLE = {"AAPL": "USA", "KO": "USA", "XTKS:7203": "Japan (Toyota)", "XASX:WBC": "Australien (Westpac)", "XKRX:005930": "Korea (Samsung)"}

def abruf(pfad, params):
    for basis in BASEN:
        q = urllib.parse.urlencode({**params, "apiKey": KEY})
        try:
            with urllib.request.urlopen(f"{basis}{pfad}?{q}", timeout=30) as r:
                return basis, r.status, r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:250]
            if e.code in (401, 403) and basis == BASEN[0]:
                continue
            return basis, e.code, body
        except Exception as e:
            continue
    return None, None, "keine Verbindung"

ergebnis = []
for t, land in SYMBOLE.items():
    eintrag = {"ticker": t, "land": land}
    for name, pfad, extra in TESTS:
        params = {k: (v.replace("{t}", t) if isinstance(v, str) else v) for k, v in extra.items()}
        basis, status, text = abruf(pfad.replace("{t}", t), params)
        eintrag[name] = {"basis": basis, "status": status}
        try:
            j = json.loads(text)
        except Exception:
            j = None
        if status == 200 and isinstance(j, dict):
            if name == "kurs_vortag":
                eintrag[name]["ergebnis"] = (j.get("results") or [{}])[0]
            elif name == "firma":
                r = j.get("results") or {}
                eintrag[name]["ergebnis"] = {k: r.get(k) for k in ("name", "market_cap", "primary_exchange", "locale", "currency_name", "type")}
            elif name == "dividenden":
                eintrag[name]["anzahl"] = len(j.get("results") or [])
                eintrag[name]["letzte"] = (j.get("results") or [])[:2]
            elif name == "finanzen":
                eintrag[name]["anzahl"] = len(j.get("results") or [])
                eintrag[name]["felder"] = sorted(((j.get("results") or [{}])[0].get("financials") or {}).keys())[:12]
        else:
            eintrag[name]["antwort"] = text[:200]
        time.sleep(0.5)
    ergebnis.append(eintrag)

json.dump({"stand": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "firmen": ergebnis}, open("data/massive-test.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(ergebnis, ensure_ascii=False)[:3000])
