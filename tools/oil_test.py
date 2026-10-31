"""Testlauf OilPriceAPI: nur lesen, Ergebnis ins Workflow-Log (nichts wird committet, der Schluessel wird nie ausgegeben)."""
import os, json, urllib.request, urllib.error

KEY = os.environ.get("OILPRICE_API_KEY", "")
BASE = "https://api.oilpriceapi.com"
if not KEY:
    raise SystemExit("OILPRICE_API_KEY fehlt")

def get(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Token " + KEY, "Accept": "application/json", "User-Agent": "dividenden-rechner-test"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, {}, repr(e)

out=[]
for pfad in ["/v1/prices/latest?by_code=BRENT_CRUDE_USD",
             "/v1/prices/latest?by_code=WTI_USD",
             "/v1/prices/past_week?by_code=BRENT_CRUDE_USD",
             "/v1/prices/past_week?by_code=WTI_USD"]:
    st, h, body = get(pfad)
    out.append("=" * 70); out.append(f"{pfad} -> {st}")
    for k in ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"):
        if k in {a.lower() for a in h}:
            out.append(f"{k} {[v for a, v in h.items() if a.lower() == k][0]}")
    out.append(body[:1800])
open("oil-test-result.txt","w",encoding="utf-8").write("\n".join(out))
