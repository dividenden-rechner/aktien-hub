"""Diagnose: alle XBRL-Elemente mit 'Dividend' im Namen aus einem EDINET-Jahresbericht (Toyota 72030)."""
import datetime as dt, io, json, os, re, time, urllib.request, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = os.environ.get("EDINET_API_KEY", "")
EBASE = "https://api.edinet-fsa.go.jp/api/v2"
UA = {"User-Agent": "dividenden-rechner.de Datensammlung"}
SEC = "72030"

def get(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()

doc_id, doc_tag = None, None
for i in range(400):
    tag = (dt.date.today() - dt.timedelta(days=i)).isoformat()
    try:
        j = json.loads(get(f"{EBASE}/documents.json?date={tag}&type=2&Subscription-Key={KEY}"))
        for d in j.get("results", []) or []:
            if d.get("secCode") == SEC and d.get("docTypeCode") == "120":
                doc_id, doc_tag = d["docID"], tag
                break
    except Exception:
        pass
    if doc_id:
        break
    time.sleep(0.2)

out = {"stand": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "docID": doc_id, "datum": doc_tag}
if doc_id:
    z = zipfile.ZipFile(io.BytesIO(get(f"{EBASE}/documents/{doc_id}?type=1&Subscription-Key={KEY}", timeout=300)))
    namen = [n for n in z.namelist() if n.endswith(".xbrl") and "PublicDoc" in n]
    x = z.read(namen[0]).decode("utf-8", errors="replace") if namen else ""
    fund = {}
    for el, ctx, val in re.findall(r'<([\w\-]+:[\w\-]*Dividend[\w\-]*)\s[^>]*?contextRef="([^"]+)"[^>]*>([^<]*)</', x):
        fund.setdefault(el, []).append({"kontext": ctx, "wert": val.strip()[:80]})
    out["elemente"] = {k: v[:6] for k, v in sorted(fund.items())}
    out["anzahl_elemente"] = len(fund)
else:
    out["fehler"] = "kein Jahresbericht fuer 72030 gefunden"

json.dump(out, open(os.path.join(ROOT, "data", "edinet-dividende-test.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False)[:800])
