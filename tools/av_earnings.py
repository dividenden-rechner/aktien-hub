#!/usr/bin/env python3
"""Alpha-Vantage-Tageslauf fuer die Earnings-Seite und die Quartalsbloecke in Artikeln.
Schreibt data/av-earnings.json: Termin (vor/nach Boerse), EPS- und Umsatzschaetzung, spaeter die Ist-Zahlen.
Ohne Key (ALPHAVANTAGE_API_KEY) passiert nichts. Aufrufe laufen nacheinander (Limit 1 Anfrage pro Sekunde)."""
import os, sys, csv, io, json, time, datetime, urllib.request, urllib.parse

OUT = "data/av-earnings.json"
KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
MAX_CALLS = int(os.environ.get("AV_MAX", "24"))
BACK, FWD = 4, 14
calls = 0

def av(**p):
    global calls
    if calls >= MAX_CALLS or LIMIT: return None
    calls += 1
    time.sleep(1.1)
    p["apikey"] = KEY
    url = "https://www.alphavantage.co/query?" + urllib.parse.urlencode(p)
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dividenden-rechner"}), timeout=60).read().decode("utf-8", "replace")
    except Exception as e:
        print("AV-Fehler", p.get("function"), p.get("symbol", ""), e); return None

LIMIT = False
def js(txt):
    global LIMIT
    if txt and "rate limit" in txt: LIMIT = True; print("AV-Tageslimit erreicht, Rest morgen."); return None
    try:
        j = json.loads(txt)
    except Exception:
        return None
    if isinstance(j, dict) and (j.get("Note") or j.get("Information") or j.get("Error Message")):
        print("AV-Hinweis:", str(j.get("Note") or j.get("Information") or j.get("Error Message"))[:160]); return None
    return j

def num(x):
    try:
        v = float(x); return v
    except Exception:
        return None

def watch():
    s = set()
    try: s |= {f["sym"] for f in json.load(open("data/universe.json", encoding="utf-8"))["firmen"]}
    except Exception: pass
    try: s |= {i["sym"] for i in json.load(open("data/termine-app.json", encoding="utf-8"))["items"] if "." not in i["sym"]}
    except Exception: pass
    try: s |= {i["sym"] for i in json.load(open("data/logo-bedarf.json", encoding="utf-8")) if "." not in i["sym"]}
    except Exception: pass
    return s

def prio():
    s = set()
    try: s |= {i["sym"] for i in json.load(open("data/termine-app.json", encoding="utf-8"))["items"]}
    except Exception: pass
    try: s |= {i["sym"] for i in json.load(open("data/logo-bedarf.json", encoding="utf-8"))}
    except Exception: pass
    return s

def main():
    if not KEY:
        print("Kein ALPHAVANTAGE_API_KEY, uebersprungen."); return
    try: cur = json.load(open(OUT, encoding="utf-8"))
    except Exception: cur = {}
    items = {(i["sym"], i["datum"]): i for i in cur.get("items", [])}
    today = datetime.date.today()
    lo, hi = today - datetime.timedelta(days=BACK), today + datetime.timedelta(days=FWD)
    txt = av(function="EARNINGS_CALENDAR", horizon="3month")
    if not txt or txt.lstrip().startswith("{"):
        print("Kalender nicht geladen:", (txt or "")[:160]); return
    W = watch(); n = 0
    for r in csv.DictReader(io.StringIO(txt)):
        sym, d = (r.get("symbol") or "").strip(), (r.get("reportDate") or "").strip()
        if not sym or sym not in W: continue
        try: dd = datetime.date.fromisoformat(d)
        except Exception: continue
        if not (lo <= dd <= hi): continue
        t = (r.get("timeOfTheDay") or "").lower()
        zeit = "vor" if "pre" in t or "before" in t else "nach" if "post" in t or "after" in t else ""
        it = items.setdefault((sym, d), {"sym": sym, "datum": d})
        if it.get("eps_est") is None and num(r.get("estimate")) is not None: it["eps_est"] = num(r.get("estimate")); it["eps_src"] = "kalender"
        it.update(name=r.get("name") or sym, fiscal=r.get("fiscalDateEnding") or "", cur=r.get("currency") or "USD", zeit=zeit or it.get("zeit", ""))
        n += 1
    print("Termine im Fenster:", n)
    # 1) Schaetzungen fuer kommende Termine (heute und spaeter)
    PRIO = prio()
    for (sym, d), it in sorted(items.items(), key=lambda kv: (kv[0][1], kv[0][0] not in PRIO)):
        if d < today.isoformat() or it.get("est_stand") == today.isoformat(): continue
        j = js(av(function="EARNINGS_ESTIMATES", symbol=sym) or "")
        if j is None: continue
        qs = [e for e in j.get("estimates", []) if e.get("horizon") == "fiscal quarter"]
        pick = next((e for e in qs if e["date"] == it.get("fiscal")), None)
        if not pick:
            c = [e for e in qs if e["date"] < d]
            pick = max(c, key=lambda e: e["date"]) if c else None
            if not pick: continue
        it.pop("eps_src", None); it.update(fiscal=pick["date"], eps_est=num(pick.get("eps_estimate_average")), eps_n=int(num(pick.get("eps_estimate_analyst_count")) or 0),
                  rev_est=num(pick.get("revenue_estimate_average")), rev_n=int(num(pick.get("revenue_estimate_analyst_count")) or 0), est_stand=today.isoformat())
    # 2) Ist-Zahlen fuer bereits berichtete Termine (kommen bei AV mit Verzug von Stunden bis zu einem Tag)
    for (sym, d), it in sorted(items.items(), key=lambda kv: kv[0][1], reverse=True):
        if d > today.isoformat() or (it.get("eps_act") is not None and it.get("rev_act") is not None): continue
        if it.get("act_try") == today.isoformat(): continue
        it["act_try"] = today.isoformat()
        if it.get("eps_act") is None:
            j = js(av(function="EARNINGS", symbol=sym) or "")
            for q in (j or {}).get("quarterlyEarnings", []):
                if q.get("fiscalDateEnding") == it.get("fiscal") or q.get("reportedDate") == d:
                    v = num(q.get("reportedEPS"))
                    if v is not None:
                        it.update(eps_act=v, eps_act_basis="GAAP laut AV", rep_date=q.get("reportedDate"), fiscal=q.get("fiscalDateEnding") or it.get("fiscal"))
                        if it.get("eps_est") is None: it["eps_est"] = num(q.get("estimatedEPS"))
                    break
        if it.get("eps_act") is not None and it.get("rev_act") is None:
            j = js(av(function="INCOME_STATEMENT", symbol=sym) or "")
            for q in (j or {}).get("quarterlyReports", []):
                if q.get("fiscalDateEnding") == it.get("fiscal"):
                    it["rev_act"] = num(q.get("totalRevenue")); break
    keep = [i for i in items.values() if i["datum"] >= (today - datetime.timedelta(days=60)).isoformat()]
    keep.sort(key=lambda i: (i["datum"], i["sym"]))
    json.dump({"updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), "quelle": "Alpha Vantage", "items": keep}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Gespeichert:", len(keep), "Eintraege,", calls, "AV-Aufrufe")

if __name__ == "__main__":
    main()
