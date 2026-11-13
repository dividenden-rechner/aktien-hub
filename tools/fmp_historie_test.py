"""TESTLAUF: Liefert der FMP-Gratisschluessel Kurshistorie (Tagesschluss) fuer Coca-Cola und McDonald's?
Ausgabe: data/fmp-historie-test.json (nur Anzahl, Zeitraum, Stichproben, keine Schluesselwerte)."""
import datetime as dt, json, os, urllib.request, urllib.parse

KEY = os.environ["FMP_API_KEY"]
ERGEBNIS = {}
for sym in ("KO", "MCD"):
    for name, url in {
        "stable": "https://financialmodelingprep.com/stable/historical-price-eod/full",
        "v3": f"https://financialmodelingprep.com/api/v3/historical-price-full/{sym}",
    }.items():
        try:
            q = {"symbol": sym, "apikey": KEY} if name == "stable" else {"apikey": KEY}
            with urllib.request.urlopen(urllib.request.Request(f"{url}?{urllib.parse.urlencode(q)}", headers={"User-Agent": "dividenden-rechner.de Datensammlung"}), timeout=60) as r:
                j = json.loads(r.read())
            daten = j if isinstance(j, list) else j.get("historical", [])
            if isinstance(j, dict) and j.get("Error Message"):
                ERGEBNIS[f"{sym} {name}"] = {"fehler": "Plan-Hinweis"}
                continue
            ERGEBNIS[f"{sym} {name}"] = {"anzahl": len(daten), "von": daten[-1].get("date") if daten else None, "bis": daten[0].get("date") if daten else None}
        except urllib.error.HTTPError as e:
            ERGEBNIS[f"{sym} {name}"] = {"http": e.code}
        except Exception as e:
            ERGEBNIS[f"{sym} {name}"] = {"fehler": str(e)[:200]}
json.dump({"stand": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "ergebnis": ERGEBNIS}, open("data/fmp-historie-test.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(ERGEBNIS, ensure_ascii=False, indent=1))
