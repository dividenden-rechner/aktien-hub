#!/usr/bin/env python3
"""Holt fuer Firmenkarten in Artikeln ([[firma: SYM | artikel-slug]]) die letzten 5 Geschaeftsjahre (Umsatz, Nettogewinn) von FMP
und schreibt data/firmenkarten.json. Ohne Daten bleibt der bisherige Stand erhalten; nichts wird geschaetzt."""
import os, re, sys, json, datetime
sys.path.insert(0, os.path.dirname(__file__))
import ir_agent as ia
import artikel as A
import fetch_logos as fl

OUT = "data/firmenkarten.json"
TOK = re.compile(r"\[\[\s*firma\s*:\s*([A-Za-z0-9.\-]+)")

def main():
    syms = set()
    for p in A.all_md():
        if p.endswith("README.md"): continue
        syms |= {m.upper() for m in TOK.findall(open(p, encoding="utf-8").read())}
    try: cur = json.load(open(OUT, encoding="utf-8"))
    except Exception: cur = {}
    log = {"gefunden": sorted(syms), "key": bool(os.environ.get("FMP_API_KEY"))}
    for s in sorted(syms):
        lp = f"assets/logos/{s.lower().replace('.', '-')}.png"
        if not os.path.exists(lp):
            png = fl.from_fmp(s)
            if png: os.makedirs('assets/logos', exist_ok=True); open(lp, 'wb').write(png)
        inc = ia.fmp_get("income-statement", symbol=s, period="annual", limit=5)
        if inc is None:
            import urllib.parse
            try: ia.http("https://financialmodelingprep.com/stable/income-statement?" + urllib.parse.urlencode({"symbol": s, "period": "annual", "limit": 5, "apikey": os.environ.get("FMP_API_KEY", "")}), timeout=60)
            except Exception as e: log[s + "_fehler"] = str(e)[:200] + " | " + str(getattr(e, "read", lambda: b"")()[:200])
        log[s] = (type(inc).__name__ + (":" + str(len(inc)) if isinstance(inc, list) else ""))
        if not isinstance(inc, list) or len(inc) < 3: print(s, ": keine Daten"); continue
        inc = sorted(inc, key=lambda x: x.get("date", ""))[-5:]
        q = [{"d": x["date"], "p": x.get("period", ""), "y": str(x.get("fiscalYear") or x["date"][:4]),
              "rev": x.get("revenue"), "ni": x.get("netIncome")} for x in inc]
        if any(a["rev"] is None or a["ni"] is None for a in q): print(s, ": unvollstaendig"); continue
        cur[s] = {"q": q, "stand": datetime.date.today().isoformat()}; print(s, ": ok,", len(q), "Quartale")
    os.makedirs("data", exist_ok=True)
    open("data/firmenkarten-log.json", "w").write(json.dumps(log, ensure_ascii=False))
    open(OUT, "w", encoding="utf-8").write(json.dumps(cur, ensure_ascii=False, indent=1))

if __name__ == "__main__": main()
