#!/usr/bin/env python3
"""Sucht fuer die DAX-Unternehmen auf den Investor-Relations-Seiten nach Wegen, Meldungen sofort zu bekommen:
RSS/Atom-Feeds (auch versteckte per <link rel=alternate>) und Anmeldung fuer E-Mail-Benachrichtigungen (Newsletter, Alerts).
Ausgabe: data/dax-ir-scan.json und docs/DAX-IR-QUELLEN.md. Laeuft im Workflow (dort ist Internet erlaubt)."""
import re, json, os, sys, time, urllib.request, urllib.parse, concurrent.futures as cf, xml.etree.ElementTree as ET
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (compatible; Dividenden-Rechner-IR-Scan; +https://dividenden-rechner.de)"
DAX = [
 ("Adidas","https://www.adidas-group.com/en/investors/"),("Airbus","https://www.airbus.com/en/investors"),
 ("Allianz","https://www.allianz.com/en/investor_relations.html"),("BASF","https://www.basf.com/global/en/investors"),
 ("Bayer","https://www.bayer.com/en/investors"),("Beiersdorf","https://www.beiersdorf.com/investors"),
 ("BMW","https://www.bmwgroup.com/en/investor-relations.html"),("Brenntag","https://www.brenntag.com/en/investor-relations/"),
 ("Commerzbank","https://www.commerzbank.de/en/hauptnavigation/aktionaere/aktionaere.html"),("Continental","https://www.continental.com/en/investor-relations/"),
 ("Daimler Truck","https://www.daimlertruck.com/en/investors"),("Deutsche Bank","https://investor-relations.db.com/"),
 ("Deutsche Boerse","https://deutsche-boerse.com/dbg-en/investor-relations"),("DHL Group","https://group.dhl.com/en/investors.html"),
 ("Deutsche Telekom","https://www.telekom.com/en/investor-relations"),("E.ON","https://www.eon.com/en/investor-relations.html"),
 ("Fresenius","https://www.fresenius.com/investors"),("Fresenius Medical Care","https://www.freseniusmedicalcare.com/en/investors"),
 ("Hannover Rueck","https://www.hannover-re.com/en/investor-relations"),("Heidelberg Materials","https://www.heidelbergmaterials.com/en/investor-relations"),
 ("Henkel","https://www.henkel.com/investors-and-analysts"),("Infineon","https://www.infineon.com/about/investor"),
 ("Mercedes-Benz","https://group.mercedes-benz.com/investors/"),("Merck KGaA","https://www.merckgroup.com/en/investors.html"),
 ("MTU Aero Engines","https://www.mtu.de/investor-relations/"),("Munich Re","https://www.munichre.com/en/company/investors.html"),
 ("Porsche AG","https://investorrelations.porsche.com/en/"),("Porsche SE","https://www.porsche-se.com/en/investor-relations"),
 ("Qiagen","https://corporate.qiagen.com/investors"),("Rheinmetall","https://www.rheinmetall.com/en/investors"),
 ("RWE","https://www.rwe.com/en/investor-relations/"),("SAP","https://www.sap.com/investors/en.html"),
 ("Siemens","https://www.siemens.com/global/en/company/investor-relations.html"),("Siemens Energy","https://www.siemens-energy.com/global/en/home/investor-relations.html"),
 ("Siemens Healthineers","https://www.siemens-healthineers.com/investor-relations"),("Symrise","https://www.symrise.com/investors/"),
 ("Volkswagen","https://www.volkswagen-group.com/en/investors-15846"),("Vonovia","https://www.vonovia.de/en/investors"),
 ("Zalando","https://corporate.zalando.com/en/investor-relations"),("Scout24","https://www.scout24.com/en/investor-relations"),
]
KEY_LINK = re.compile(r"rss|atom|feed|newsletter|e-?mail|alert|subscri|abonn|mailing|news-?room|press|ad-?hoc|ir-?news|service", re.I)
KEY_ALERT = re.compile(r"newsletter|e-?mail[ -]?(alert|service|notification|benachricht)|email alerts?|alert|subscribe|abonnieren|mailing|benachrichtigung|ir[- ]?mail|news by e-?mail", re.I)
FEED_PATHS = ["/rss", "/rss.xml", "/feed", "/feed.xml", "/press/rss", "/en/rss.xml", "/newsroom/rss", "/investors/rss", "/en/press/rss.xml"]

def get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml,*/*", "Accept-Language": "en,de;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.geturl(), r.headers.get("Content-Type", ""), r.read(900000)

def feed_info(url):
    """Ist die URL ein Feed? Gibt (Eintraege, neuestes Datum) zurueck oder None."""
    try:
        _, ct, data = get(url, 15)
        t = data.decode("utf-8", "ignore")
        if "<rss" not in t[:3000].lower() and "<feed" not in t[:3000].lower() and "<rdf" not in t[:3000].lower():
            return None
        items = re.findall(r"<(?:item|entry)[ >]", t)
        dates = re.findall(r"<(?:pubDate|updated|published|dc:date)>([^<]+)<", t)
        return (len(items), dates[0].strip() if dates else "")
    except Exception:
        return None

def scan(name, start):
    out = {"name": name, "start": start, "seiten": [], "feeds": [], "alert_links": [], "fehler": ""}
    seen, queue, base_ok = set(), [(start, 0)], False
    feeds = {}
    alerts = {}
    while queue and len(seen) < 7:
        url, depth = queue.pop(0)
        if url in seen: continue
        seen.add(url)
        try:
            final, ct, data = get(url)
        except Exception as e:
            if depth == 0: out["fehler"] = str(e)[:80]
            continue
        base_ok = True
        out["seiten"].append(final)
        html = data.decode("utf-8", "ignore")
        for m in re.finditer(r"<link[^>]+rel=[\"']alternate[\"'][^>]*>", html, re.I):
            tag = m.group(0)
            if re.search(r"rss|atom", tag, re.I):
                h = re.search(r"href=[\"']([^\"']+)", tag)
                if h: feeds[urllib.parse.urljoin(final, h.group(1))] = "link-alternate"
        for m in re.finditer(r"<a[^>]+href=[\"']([^\"'#][^\"']*)[\"'][^>]*>(.*?)</a>", html, re.I | re.S):
            href, text = urllib.parse.urljoin(final, m.group(1)), re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()[:80]
            if re.search(r"\.(rss|xml)(\?|$)|/rss|/feed", href, re.I):
                feeds.setdefault(href, "link")
            if KEY_ALERT.search(text) or KEY_ALERT.search(href):
                alerts.setdefault(href, text)
            if depth == 0 and KEY_LINK.search(href + " " + text) and urllib.parse.urlparse(href).netloc.split(".")[-2:] == urllib.parse.urlparse(final).netloc.split(".")[-2:] and href not in seen and len(queue) < 6 and not re.search(r"\.(pdf|jpg|png|zip)$", href, re.I):
                queue.append((href, 1))
    if base_ok:
        root = "{u.scheme}://{u.netloc}".format(u=urllib.parse.urlparse(out["seiten"][0]))
        for p in FEED_PATHS:
            feeds.setdefault(root + p, "pfad-test")
    for u, how in list(feeds.items())[:25]:
        fi = feed_info(u)
        if fi: out["feeds"].append({"url": u, "eintraege": fi[0], "neueste": fi[1], "fund": how})
    out["alert_links"] = [{"url": u, "text": t} for u, t in list(alerts.items())[:8]]
    return out

def main():
    t0 = time.time()
    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda x: scan(*x), DAX))
    json.dump({"stand": time.strftime("%Y-%m-%d"), "firmen": res}, open(os.path.join(ROOT, "data", "dax-ir-scan.json"), "w"), ensure_ascii=False, indent=1)
    rows = ["# DAX: Wege zu Meldungen auf den IR-Seiten", "", f"Automatisch gesucht am {time.strftime('%d.%m.%Y')}. Feed = RSS oder Atom, der tatsaechlich abrufbar war und Eintraege enthielt. Anmelde-Links sind Treffer fuer E-Mail-Dienste, Newsletter oder Alerts und muessen von Hand geprueft werden.", "",
            "| Firma | RSS/Atom-Feed | E-Mail/Alert-Link | Hinweis |", "|---|---|---|---|"]
    for r in res:
        fe = "; ".join(f"[{f['eintraege']} Eintr., neu {f['neueste'][:16]}]({f['url']})" for f in r["feeds"][:2]) or "kein Feed gefunden"
        al = "; ".join(f"[{(a['text'] or 'Link')[:30]}]({a['url']})" for a in r["alert_links"][:2]) or "-"
        rows.append(f"| {r['name']} | {fe} | {al} | {r['fehler'] or ''} |")
    md = "\n".join(rows) + "\n"
    open(os.path.join(ROOT, "docs", "DAX-IR-QUELLEN.md"), "w", encoding="utf-8").write(md)
    print(md); print("Dauer", round(time.time() - t0))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write(md)

if __name__ == "__main__":
    main()
