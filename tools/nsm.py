#!/usr/bin/env python3
"""Britische Pflichtmitteilungen (FCA National Storage Mechanism) als Kandidaten fuer die Kurzmeldungen."""
import json, os, re, subprocess, tempfile, time, urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (compatible; dividenden-rechner.de)"
API = "https://api.data.fca.org.uk/search?index=nsm-search"
ART = "https://data.fca.org.uk/artefacts/"
# Routinemeldungen, die keine Nachricht sind
SKIP = re.compile(r"(total voting rights|holding\(s\) in company|form 8|form 3[0-9]|transaction in own shares|director/pdmr|pdmr|"
                  r"notification of major|block listing|issue of equity|admission to trading|change of adviser|"
                  r"notice of (agm|general meeting)|result of (agm|general meeting)|publication of (a )?prospectus|"
                  r"net asset value|\bnav\b|rule 2\.9|rule 2\.10|early redemption|rule 2\.)", re.I)
_DROP = re.compile(r"\b(plc|p l c|group|holdings|holding|the|limited|ltd|corporation|corp|company|co|ag|sa|nv|se)\b")


def norm(s):
    s = _DROP.sub(" ", (s or "").lower().replace("&", " and "))
    return re.sub(r"[^a-z0-9]+", "", s)


def uk_firms():
    out = {}
    for line in open(os.path.join(ROOT, "data", "europa-seed.txt"), encoding="utf-8"):
        if line.startswith("#") or "|" not in line:
            continue
        p = line.strip().split("|")
        if p[0].endswith(".L"):
            out[norm(p[1])] = (p[0], p[1])
    return out


def search(hours, size=100, pages=8):
    now = datetime.now(timezone.utc)
    d0 = now - timedelta(hours=hours)
    hits, seen = [], set()
    for pg in range(pages):
        body = {"from": pg * size, "size": size, "sort": "submitted_date", "sortorder": "desc", "latestFlag": "Y", "primarySearch": [],
                "criteriaObj": {"criteria": [], "dateCriteria": [{"name": "submitted_date", "value": {
                    "from": d0.strftime("%Y-%m-%dT%H:%M:%SZ"), "to": now.strftime("%Y-%m-%dT23:59:59Z")}}]}}
        req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST",
                                     headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json",
                                              "Origin": "https://data.fca.org.uk", "Referer": "https://data.fca.org.uk/"})
        with urllib.request.urlopen(req, timeout=60) as r:
            hh = json.loads(r.read().decode())["hits"]["hits"]
        for h in hh:
            s = h["_source"]
            if s.get("disclosure_id") not in seen:
                seen.add(s.get("disclosure_id")); hits.append(s)
        if len(hh) < size:
            break
        time.sleep(0.5)
    return hits


def match(hits, firms):
    out = []
    for s in hits:
        n = norm(s.get("company", ""))
        if not n or n not in firms:
            continue
        head = s.get("headline") or ""
        if SKIP.search(head) or SKIP.search(s.get("type") or ""):
            continue
        sym, name = firms[n]
        out.append({"key": "nsm:" + s["disclosure_id"], "sym": sym, "name": name, "title": head, "link": ART + s["download_link"],
                    "when": s.get("submitted_date", ""), "src": "nsm", "category": s.get("category_group", ""), "type": s.get("type", "")})
    return out


def fetch_text(link, html_to_text, http):
    if link.lower().endswith(".pdf"):
        req = urllib.request.Request(link, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r, tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(r.read()); f.flush()
            return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True, check=True).stdout
    return html_to_text(http(link, ua=UA))


def candidates(hours, done, log=print):
    firms = uk_firms()
    try:
        hits = search(hours)
    except Exception as e:
        log(f"Hinweis: NSM nicht abrufbar ({str(e)[:100]})"); return []
    c = match(hits, firms)
    log(f"NSM: {len(hits)} Meldungen, {len(c)} von {len(firms)} britischen Firmen")
    return [x for x in c if x["key"] not in done]
