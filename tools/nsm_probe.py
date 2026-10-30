#!/usr/bin/env python3
"""Testet den Abruf der FCA National Storage Mechanism (NSM): liefert Rohantworten nach data/nsm-probe.json (nur zum Auswerten)."""
import json, os, sys, urllib.request, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
URL = "https://api.data.fca.org.uk/search?index=fca-nsm-searchdata"

def post(body, idx="fca-nsm-searchdata"):
    req = urllib.request.Request("https://api.data.fca.org.uk/search?index=" + idx, data=json.dumps(body).encode(), method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json, text/plain, */*",
                                          "Origin": "https://data.fca.org.uk", "Referer": "https://data.fca.org.uk/"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)

def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        return "FEHLER " + str(e)


def discover():
    """Sucht im Web-Auftritt der NSM nach dem verwendeten Suchdienst (Index-Name und Aufbau der Anfrage)."""
    import re
    found = {}
    html = get("https://data.fca.org.uk/")
    found["startseite_laenge"] = len(html)
    scripts = re.findall(r'src="([^"]+\.js[^"]*)"', html)
    found["scripte"] = scripts[:15]
    for sc in scripts[:15]:
        u = sc if sc.startswith("http") else "https://data.fca.org.uk/" + sc.lstrip("/")
        js = get(u)
        for m in re.finditer(r"api\.data\.fca\.org\.uk[^\"'`\s]{0,120}", js):
            found.setdefault("api_treffer", []).append(m.group(0))
        for m in re.finditer(r"index=[A-Za-z0-9_\-]+", js):
            found.setdefault("index_treffer", []).append(m.group(0))
        for m in re.finditer(r".{200}criteriaObj.{400}", js, re.S):
            found.setdefault("anfrage_beispiele", []).append(m.group(0))
            break
    for k in ("api_treffer", "index_treffer"):
        found[k] = sorted(set(found.get(k, [])))[:20]
    return found


def main():
    disc = discover()
    print(json.dumps(disc, ensure_ascii=False, indent=1)[:4000])
    json.dump(disc, open(os.path.join(ROOT, "data", "nsm-discover.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    now = datetime.datetime.utcnow(); frm = (now - datetime.timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z"); to = now.strftime("%Y-%m-%dT23:59:59Z")
    variants = {
        "mit_datum": {"from": 0, "size": 20, "sort": "submitted_date", "sortorder": "desc",
                      "criteriaObj": {"criteria": [{"name": "latest_flag", "value": "Y"}],
                                      "dateCriteria": [{"name": "submitted_date", "value": {"from": frm, "to": to}}]}},
        "einfach": {"from": 0, "size": 20, "sort": "submitted_date", "sortorder": "desc", "criteriaObj": {"criteria": [], "dateCriteria": []}},
    }
    out = {}
    idxs = sorted({i.split("=")[1] for i in disc.get("index_treffer", [])} | {"fca-nsm-searchdata"})
    for idx in idxs:
        for k, b in variants.items():
            st, txt = post(b, idx)
            out[idx + ":" + k] = {"status": st, "laenge": len(txt), "anfang": txt[:3000]}
            print(idx, k, st, len(txt)); print(txt[:400])
    json.dump(out, open(os.path.join(ROOT, "data", "nsm-probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
