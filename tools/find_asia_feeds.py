#!/usr/bin/env python3
"""Sucht fuer die Firmen in data/asia-seed.txt die IR-/Newsroom-Seite und deren RSS/Atom-Feeds.
Schritte je Firma: IR-Seite und Startseite abrufen -> <link rel=alternate>, Links mit rss/feed/.xml, uebliche Pfade -> Feed pruefen
(XML mit Eintraegen, neuester Eintrag). Ergebnis: data/asia-feeds.json (alles) und Eintrag in data/feeds.json (nur geprueft, ohne bisherige URL).
Ohne KI, verbraucht kein Kontingent."""
import json, os, re, sys, time, html, datetime, email.utils, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml,application/rss+xml;q=0.9,*/*;q=0.8"}
PATHS = ["/rss", "/rss.xml", "/feed", "/feed.xml", "/news/rss", "/news/rss.xml", "/newsroom/rss", "/en/rss.xml", "/atom.xml", "/press-releases/rss"]

def get(u, t=15):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t)
        return r.geturl(), r.read(1_500_000).decode("utf-8", "replace")
    except Exception:
        return None, None

def fresh(datestr, days=90):
    """True, wenn das Datum des neuesten Eintrags jung genug ist (unbekanntes Datum zaehlt als nicht frisch)."""
    if not datestr:
        return False
    try:
        d = email.utils.parsedate_to_datetime(datestr)
    except Exception:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", datestr)
        if not m:
            m2 = re.search(r"(\d{1,2}) (\w{3})\w* (\d{4})", datestr)
            if not m2:
                return False
            try:
                d = datetime.datetime.strptime(f"{m2.group(1)} {m2.group(2)} {m2.group(3)}", "%d %b %Y")
            except Exception:
                return False
        else:
            d = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    d = d.replace(tzinfo=None)
    return datetime.datetime.utcnow() - d < datetime.timedelta(days=days) and d < datetime.datetime.utcnow() + datetime.timedelta(days=2)


def check_feed(u):
    final, body = get(u)
    if not body or "<" not in body[:2000]:
        return None
    try:
        root = ET.fromstring(body.encode("utf-8"))
    except Exception:
        return None
    items = [e for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry")]
    if not items or re.search(r"calendar|kalender|partner|podcast|events?\b", u, re.I):
        return None
    dates = []
    for it in items[:30]:
        for c in it:
            if c.tag.split("}")[-1] in ("pubDate", "published", "updated", "date") and c.text:
                dates.append(c.text.strip())
                break
    if not fresh(dates[0] if dates else ""):
        return None
    return {"url": final or u, "eintraege": len(items), "neueste": dates[0]}

def candidates(base_pages):
    found = []
    for page in base_pages:
        final, body = get(page)
        if not body:
            continue
        for m in re.finditer(r"<link[^>]+>", body, re.I):
            tag = m.group(0)
            if re.search(r"type=[\"']application/(rss|atom)\+xml", tag, re.I):
                h = re.search(r"href=[\"']([^\"']+)", tag)
                if h:
                    found.append(urllib.parse.urljoin(final or page, html.unescape(h.group(1))))
        for m in re.finditer(r"href=[\"']([^\"']*(?:rss|/feed|\.xml|atom)[^\"']*)[\"']", body, re.I):
            u = urllib.parse.urljoin(final or page, html.unescape(m.group(1)))
            if not re.search(r"sitemap|\.(css|js|png|jpg)", u, re.I):
                found.append(u)
    for page in base_pages[:2]:
        p = urllib.parse.urlparse(page)
        for path in PATHS:
            found.append(f"{p.scheme}://{p.netloc}{path}")
    seen, out = set(), []
    for u in found:
        if u not in seen:
            seen.add(u); out.append(u)
    return out[:25]

def work(line):
    sym, name, home, ir = [x.strip() for x in line.split("|")]
    res = {"sym": sym, "name": name, "homepage": home, "ir_seite": ir}
    f_ir, b_ir = get(ir)
    res["ir_seite_ok"] = bool(b_ir)
    if f_ir:
        res["ir_seite"] = f_ir
    for u in candidates([x for x in (f_ir or ir, home) if x]):
        r = check_feed(u)
        if r:
            res["feed"] = r
            break
    return res

def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "asia"      # asia oder europa: liest data/<name>-seed.txt, schreibt data/<name>-feeds.json
    lines = [l for l in open(os.path.join(ROOT, "data", name + "-seed.txt"), encoding="utf-8") if l.strip() and not l.startswith("#")]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(work, lines))
    out = {"stand": time.strftime("%Y-%m-%d"), "firmen": results}
    json.dump(out, open(os.path.join(ROOT, "data", name + "-feeds.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    fp = os.path.join(ROOT, "data", "feeds.json")
    fd = json.load(open(fp, encoding="utf-8"))
    have = {f["sym"]: f for f in fd["feeds"]}
    added = 0
    for r in results:
        if "feed" not in r:
            continue
        cur = have.get(r["sym"])
        if cur and cur.get("url"):
            continue
        if cur:
            cur["url"] = r["feed"]["url"]; cur["geprueft"] = True
        else:
            fd["feeds"].append({"sym": r["sym"], "name": r["name"], "url": r["feed"]["url"], "region": "Welt", "geprueft": True})
        added += 1
    json.dump(fd, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_feed = sum(1 for r in results if "feed" in r); n_ir = sum(1 for r in results if r["ir_seite_ok"])
    md = [f"Firmen: {len(results)}, IR-Seite erreichbar: {n_ir}, Feed gefunden: {n_feed}, neu in feeds.json: {added}", "",
          "| Firma | Kuerzel | IR-Seite | Feed | Eintraege | Neueste |", "|---|---|---|---|---|---|"]
    for r in results:
        f = r.get("feed", {})
        md.append(f"| {r['name']} | {r['sym']} | {'ja' if r['ir_seite_ok'] else 'nein'} | {f.get('url', '-')} | {f.get('eintraege', '')} | {f.get('neueste', '')} |")
    s = "\n".join(md); print(s)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(s + "\n")

if __name__ == "__main__":
    main()
