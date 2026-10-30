#!/usr/bin/env python3
"""Testet den Abruf der FCA National Storage Mechanism (NSM): liefert Rohantworten nach data/nsm-probe.json (nur zum Auswerten)."""
import json, os, sys, urllib.request, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
URL = "https://api.data.fca.org.uk/search?index=fca-nsm-searchdata"

def post(body):
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json, text/plain, */*",
                                          "Origin": "https://data.fca.org.uk", "Referer": "https://data.fca.org.uk/"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)

def main():
    now = datetime.datetime.utcnow(); frm = (now - datetime.timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z"); to = now.strftime("%Y-%m-%dT23:59:59Z")
    variants = {
        "mit_datum": {"from": 0, "size": 20, "sort": "submitted_date", "sortorder": "desc",
                      "criteriaObj": {"criteria": [{"name": "latest_flag", "value": "Y"}],
                                      "dateCriteria": [{"name": "submitted_date", "value": {"from": frm, "to": to}}]}},
        "einfach": {"from": 0, "size": 20, "sort": "submitted_date", "sortorder": "desc", "criteriaObj": {"criteria": [], "dateCriteria": []}},
    }
    out = {}
    for k, b in variants.items():
        st, txt = post(b)
        out[k] = {"status": st, "laenge": len(txt), "anfang": txt[:3000]}
        print(k, st, len(txt)); print(txt[:600])
    json.dump(out, open(os.path.join(ROOT, "data", "nsm-probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
