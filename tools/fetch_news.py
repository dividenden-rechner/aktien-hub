#!/usr/bin/env python3
# Holt IR-RSS-Feeds (data/feeds.json) und schreibt data/news.json. Nur Standardbibliothek.
import json, os, re, sys, html, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import xml.etree.ElementTree as ET
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (compatible; DividendenRechnerNewsBot/1.0; +https://www.dividenden-rechner.de)"
KEEP_DAYS, PER_FEED = 60, 15

class T(HTMLParser):
    def __init__(s): super().__init__(); s.o = []
    def handle_data(s, d): s.o.append(d)
    def handle_starttag(s, t, a):
        if t in ("p", "br", "li", "div", "h1", "h2", "h3", "h4", "tr"): s.o.append("\n")
    def handle_endtag(s, t):
        if t in ("p", "li", "div", "h1", "h2", "h3", "h4"): s.o.append("\n")
def text(h):
    p = T(); p.feed(html.unescape(h or "") if "<" not in (h or "") and "&lt;" in (h or "") else (h or "")); t = "".join(p.o)
    t = re.sub(r"[ \t\xa0]+", " ", t); t = re.sub(r"\s*\n\s*", "\n", t).strip()
    return re.sub(r"\n{3,}", "\n\n", t)
def tag(e): return e.tag.split("}")[-1].lower()
def kid(e, *names):
    for c in e:
        if tag(c) in names: return c
def dt(s):
    if not s: return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)
def get(url):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(r, timeout=25) as f: return f.read()
def parse(raw):
    root = ET.fromstring(raw); out = []
    for it in root.iter():
        if tag(it) not in ("item", "entry"): continue
        t = kid(it, "title"); l = kid(it, "link"); link = ""
        if l is not None: link = l.get("href") or (l.text or "").strip()
        if not link:
            g = kid(it, "guid", "id"); link = (g.text or "").strip() if g is not None else ""
        body = kid(it, "encoded", "content", "description", "summary")
        d = kid(it, "pubdate", "published", "updated", "date")
        title = text(t.text if t is not None else "")
        if not title: continue
        out.append({"title": title.replace("\n", " "), "link": link, "date": dt(d.text if d is not None else None), "text": text(body.text if body is not None else "")})
    return out
def from_fmp(sym, key):
    u = "https://financialmodelingprep.com/stable/news/press-releases?" + urllib.parse.urlencode({"symbols": sym, "limit": PER_FEED, "apikey": key})
    out = []
    for x in json.loads(get(u)):
        out.append({"title": (x.get("title") or "").strip(), "link": x.get("url") or "", "date": dt((x.get("publishedDate") or "").replace(" ", "T")), "text": text(x.get("text") or "")})
    return out
def main():
    cfg = json.load(open(os.path.join(ROOT, "data", "feeds.json"), encoding="utf-8"))["feeds"]
    key = os.environ.get("FMP_API_KEY", ""); now = datetime.now(timezone.utc); lim = now - timedelta(days=KEEP_DAYS)
    items, errors = [], []
    for f in cfg:
        sym, url = f["sym"], (f.get("url") or "").strip()
        try:
            if url: rows, src = parse(get(url)), "RSS"
            elif key: rows, src = from_fmp(sym, key), "FMP"
            else: errors.append({"sym": sym, "fehler": "keine Feed-URL und kein FMP_API_KEY"}); continue
        except Exception as e:
            errors.append({"sym": sym, "fehler": str(e)[:160]}); continue
        rows = [r for r in rows if r["title"]]
        rows.sort(key=lambda r: r["date"] or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)
        for r in rows[:PER_FEED]:
            if r["date"] and r["date"] < lim: continue
            if r["date"] and r["date"] > now + timedelta(days=1): continue
            items.append({"sym": sym, "name": f["name"], "title": r["title"], "link": r["link"], "date": (r["date"] or now).isoformat(), "text": r["text"][:6000], "quelle": src})
    items.sort(key=lambda x: x["date"], reverse=True)
    out = {"updated": now.isoformat(), "items": items, "errors": errors}
    json.dump(out, open(os.path.join(ROOT, "data", "news.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(items), "Meldungen,", len(errors), "Feeds ohne Ergebnis")
    for e in errors: print(" -", e["sym"], e["fehler"])
if __name__ == "__main__": main()
