#!/usr/bin/env python3
"""Testet, ueber welchen Weg fuer die Firmen in data/feeds.json (Europa, Asien) Pressemitteilungen ankommen.
Ausgabe als Markdown-Tabelle (im Workflow: Zusammenfassung des Laufs). Wege: SEC 6-K (ADR), FMP-Pressemitteilungen, eigene Feed-URL."""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir_agent as ia
import kurzmeldungen as k

def main():
    feeds = [f for f in json.load(open(os.path.join(ia.ROOT, "data", "feeds.json"), encoding="utf-8"))["feeds"] if f.get("region")]
    key = os.environ.get("FMP_API_KEY", "")
    adr_by_feed = {v: t for t, v in k.ADR.items()}
    try:
        tick = json.loads(ia.http("https://www.sec.gov/files/company_tickers.json", ua=k.UA_HDR))
        by = {v["ticker"].upper(): v for v in tick.values()}
    except Exception as e:
        by = {}; print("SEC-Liste nicht ladbar:", e)
    rows = ["| Firma | Kuerzel | SEC 6-K (ADR) | FMP-Pressemitteilungen | Eigene Feed-URL |", "|---|---|---|---|---|"]
    for f in feeds:
        adr = adr_by_feed.get(f["sym"]); sec = "-"
        if adr and adr in by:
            try:
                sub = json.loads(ia.http(f"https://data.sec.gov/submissions/CIK{int(by[adr]['cik_str']):010d}.json", ua=k.UA_HDR))["filings"]["recent"]
                n = sum(1 for x in sub["form"][:60] if x == "6-K")
                sec = f"ja ({adr}), {n} Meldungen zuletzt"
            except Exception as e:
                sec = f"{adr}: Fehler {str(e)[:40]}"
            time.sleep(0.15)
        elif adr:
            sec = f"{adr}: nicht in SEC-Liste"
        fmp = "kein Schluessel"
        if key:
            try:
                u = "https://financialmodelingprep.com/stable/news/press-releases?" + urllib.parse.urlencode({"symbols": f["sym"], "limit": 3, "apikey": key})
                d = json.loads(ia.http(u, timeout=30))
                fmp = f"{len(d)} Eintraege, neueste {str(d[0].get('publishedDate', ''))[:10]}" if isinstance(d, list) and d else "keine Eintraege"
            except Exception as e:
                fmp = f"Fehler {str(e)[:50]}"
        url = "ja" if f.get("url") else "-"
        rows.append(f"| {f['name']} | {f['sym']} | {sec} | {fmp} | {url} |")
    out = "\n".join(rows)
    print(out)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write("## Test der Meldungswege (Europa, Asien)\n\n" + out + "\n")

if __name__ == "__main__":
    main()
