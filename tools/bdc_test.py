#!/usr/bin/env python3
"""TESTLAUF: Lassen sich NAV je Aktie und Dividende je Aktie der BDC-Liste aus den SEC-XBRL-Daten (data.sec.gov) ziehen?
Schreibt data/bdc-test.json und data/bdc-test.md (Abdeckung, Vergleich mit den Handwerten aus dem Sheet). Aendert nichts sonst."""
import csv, json, time, datetime, urllib.request

UA = "dividenden-rechner.de Kilian Tress dividenden.rechner@gmail.com"
def get(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"}), timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            err = str(e)[:80]; time.sleep(2)
    return {"_fehler": err}

def facts_of(cf, pred):
    out = {}
    for ns, tags in (cf.get("facts") or {}).items():
        for tag, d in tags.items():
            if pred(tag):
                for unit, arr in d.get("units", {}).items():
                    out.setdefault(f"{ns}:{tag}", []).extend({**x, "unit": unit} for x in arr)
    return out

def days(x):
    try: return (datetime.date.fromisoformat(x["end"]) - datetime.date.fromisoformat(x["start"])).days
    except Exception: return None

def main():
    tick = get("https://www.sec.gov/files/company_tickers.json")
    cik = {v["ticker"].upper(): (v["cik_str"], v["title"]) for v in tick.values()} if "_fehler" not in tick else {}
    rows = list(csv.DictReader(open("data/bdc-seed.csv")))
    res = []
    for r in rows:
        t = r["sec_ticker"].upper(); o = {"ticker": r["ticker"], "sheet_nav": float(r["sheet_nav"]), "sheet_dps": float(r["sheet_dps"])}
        if t not in cik: o["status"] = "kein CIK zum Ticker"; res.append(o); continue
        c, title = cik[t]; o["cik"] = c; o["name"] = title
        cf = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c:010d}.json"); time.sleep(0.15)
        if "_fehler" in cf: o["status"] = "Abruf fehlgeschlagen: " + cf["_fehler"]; res.append(o); continue
        nav = facts_of(cf, lambda g: "NetAssetValuePerShare" in g or "NetAssetValuePerUnit" in g)
        best = None
        for k, arr in nav.items():
            for x in arr:
                if x.get("unit") in ("USD/shares", "USD/Share", "USD") and (best is None or (x["end"], x.get("filed", "")) > (best[1]["end"], best[1].get("filed", ""))): best = (k, x)
        if best: o["nav"] = {"tag": best[0], "wert": best[1]["val"], "stichtag": best[1]["end"], "form": best[1].get("form"), "eingereicht": best[1].get("filed")}
        # Besserer Weg: Nettovermoegen / ausstehende Aktien am selben Stichtag
        net = [x for arr in facts_of(cf, lambda g: g == "AssetsNet").values() for x in arr if x.get("unit") == "USD" and "start" not in x]
        shs = [x for arr in facts_of(cf, lambda g: g in ("CommonStockSharesOutstanding", "SharesOutstanding", "EntityCommonStockSharesOutstanding")).values() for x in arr if x.get("unit") == "shares"]
        if net and shs:
            n0 = max(net, key=lambda x: (x["end"], x.get("filed", "")))
            same = [x for x in shs if x["end"] == n0["end"]]
            sh = max(same, key=lambda x: x.get("filed", "")) if same else None
            if not sh:
                near = [x for x in shs if 0 <= (datetime.date.fromisoformat(x["end"]) - datetime.date.fromisoformat(n0["end"])).days <= 60]
                sh = max(near, key=lambda x: x["end"]) if near else None
            if sh and sh["val"] > 0:
                o["nav_calc"] = {"wert": round(n0["val"] / sh["val"], 2), "stichtag": n0["end"], "nettovermoegen": n0["val"], "aktien": sh["val"], "aktien_stichtag": sh["end"], "eingereicht": n0.get("filed")}
        dv = facts_of(cf, lambda g: ("DividendsDeclared" in g or "DistributionsDeclared" in g or "DividendsPerShare" in g or "DividendsCommonStock" in g and "PerShare" in g) and "PerShare" in g)
        qd = {}
        for k, arr in dv.items():
            for x in arr:
                d = days(x)
                if d and 80 <= d <= 100 and x.get("unit", "").endswith(("shares", "Share")):
                    qd.setdefault(x["end"], []).append((k, x["val"], x.get("filed", "")))
        last4 = sorted(qd)[-4:]
        if len(last4) == 4 and (datetime.date.fromisoformat(last4[-1]) - datetime.date.fromisoformat(last4[0])).days < 300:
            vals = [max(qd[e], key=lambda z: z[2])[1] for e in last4]
            o["dps"] = {"quartale": dict(zip(last4, vals)), "summe_4q": round(sum(vals), 4), "tag": qd[last4[-1]][0][0]}
        elif qd: o["dps_teilweise"] = {e: qd[e][0][1] for e in sorted(qd)[-4:]}
        o["status"] = "ok" if ("nav" in o and "dps" in o) else ("nur NAV" if "nav" in o else ("nur Dividende" if "dps" in o else "weder NAV noch Dividende"))
        res.append(o)
    json.dump(res, open("data/bdc-test.json", "w"), ensure_ascii=False, indent=1)
    L = ["| Ticker | NAV berechnet (Nettovermögen / Aktien) | Stichtag | NAV Sheet | Abweichung | NAV Tag (alt) |", "|---|---|---|---|---|---|"]
    for o in res:
        n = o.get("nav"); d = o.get("dps")
        c = o.get("nav_calc"); ab = f"{(c['wert']/o['sheet_nav']-1)*100:+.0f} %" if c else "–"
        L.append(f"| {o['ticker']} | {c['wert'] if c else '–'} | {c['stichtag'] if c else '–'} | {o['sheet_nav']} | {ab} | {n['wert'] if n else '–'} |")
    open("data/bdc-test.md", "w").write("\n".join(L) + "\n")
    from collections import Counter; print(Counter(o["status"] for o in res))

if __name__ == "__main__": main()
