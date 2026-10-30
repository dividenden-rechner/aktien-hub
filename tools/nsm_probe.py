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
    extra = []
    for cfg in ("assets/config.json", "config.json", "assets/environment.json", "environment.json", "assets/env.json", "assets/appconfig.json"):
        t = get("https://data.fca.org.uk/" + cfg)
        found.setdefault("config", {})[cfg] = t[:400]
    mainjs = get("https://data.fca.org.uk/" + [x for x in scripts if x.startswith("main")][0]) if any(x.startswith("main") for x in scripts) else ""
    chunks = sorted(set(re.findall(r"chunk-[A-Z0-9]+\.js", mainjs)))
    found["chunks"] = chunks[:40]
    scripts = scripts + chunks[:40]
    for sc in scripts[:60]:
        u = sc if sc.startswith("http") else "https://data.fca.org.uk/" + sc.lstrip("/")
        js = get(u)
        for m in re.finditer(r"api\.data\.fca\.org\.uk[^\"'`\s]{0,120}", js):
            found.setdefault("api_treffer", []).append(m.group(0))
        for m in re.finditer(r"index=[A-Za-z0-9_\-]+", js):
            found.setdefault("index_treffer", []).append(m.group(0))
        for pat in (r"search\?[^\"'`]{0,80}", r"[\"'`][^\"'`]{0,60}fca[^\"'`]{0,80}[\"'`]", r"[A-Za-z_]*[Uu]rl[\"']?\s*[:=]\s*[\"'`][^\"'`]{5,120}[\"'`]", r"[\"'`]fca-nsm[^\"'`]*[\"'`]"):
            for m in re.finditer(pat, js):
                found.setdefault("kontext", []).append(m.group(0)[:200])
        for m in re.finditer(r".{300}criteriaObj=\{[^;]{0,500}", js, re.S):
            found.setdefault("anfrage_beispiele", []).append(m.group(0)); break
        for pat in (r".{700}\.post\(Fl\.search_api.{200}", r"search_api\s*[:=][^,;]{0,160}", r"index\s*:\s*[\"'`][^\"'`]{2,40}[\"'`]", r"nsm_index_name\s*:\s*[\"'`][^\"'`]+[\"'`]", r"[a-z_]*index_name\s*:\s*[\"'`][^\"'`]+[\"'`]", r".{400}fetchData\([^)]*\).{300}", r"fca-[a-z\-]+(?:data|index)[a-z\-]*", r"[\"'`]x-[a-z\-]+[\"'`]\s*:\s*[^,}]{0,80}", r"[Aa]pi[Kk]ey[^,;]{0,100}"):
            for m in re.finditer(pat, js, re.S):
                found.setdefault("tiefe", []).append(m.group(0)[:1000])
        for m in re.finditer(r"\.post\([^)]{0,200}\)", js):
            found.setdefault("post_aufrufe", []).append(m.group(0))
    found["tiefe"] = sorted(set(found.get("tiefe", [])))[:40]
    found["kontext"] = sorted(set(found.get("kontext", [])))[:60]
    found["post_aufrufe"] = sorted(set(found.get("post_aufrufe", [])))[:20]
    for k in ("api_treffer", "index_treffer"):
        found[k] = sorted(set(found.get(k, [])))[:20]
    return found


def main():
    now = datetime.datetime.utcnow(); d0 = now - datetime.timedelta(days=2)
    iso = (d0.strftime("%Y-%m-%dT00:00:00Z"), now.strftime("%Y-%m-%dT23:59:59Z"))
    us = (d0.strftime("%m/%d/%Y"), now.strftime("%m/%d/%Y"))
    base = {"from": 0, "size": 20, "sort": "submitted_date", "sortorder": "desc", "latestFlag": "Y", "primarySearch": []}
    variants = {
        "ohne_datum": dict(base, criteriaObj={"criteria": [], "dateCriteria": []}),
        "datum_us": dict(base, criteriaObj={"criteria": [], "dateCriteria": [{"name": "submitted_date", "value": {"from": us[0], "to": us[1]}}]}),
        "datum_iso": dict(base, criteriaObj={"criteria": [], "dateCriteria": [{"name": "submitted_date", "value": {"from": iso[0], "to": iso[1]}}]}),
        "firma_lei": dict(base, criteriaObj={"criteria": [{"name": "company_lei", "value": ["213800QAFRA3HPXKAG33"]}], "dateCriteria": []}),
    }
    out = {}
    for k, b in variants.items():
        st, txt = post(b, "nsm-search")
        info = {"status": st, "laenge": len(txt), "anfang": txt[:1500]}
        try:
            j = json.loads(txt); hits = j["hits"]["hits"]; info["treffer_gesamt"] = j["hits"]["total"]; info["erste_quellen"] = [h["_source"] for h in hits[:3]]
        except Exception as e:
            info["fehler"] = str(e)[:100]
        out[k] = info
        print(k, st, len(txt), info.get("treffer_gesamt")); print(json.dumps(info.get("erste_quellen", [])[:1], ensure_ascii=False)[:800])
    json.dump(out, open(os.path.join(ROOT, "data", "nsm-probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
