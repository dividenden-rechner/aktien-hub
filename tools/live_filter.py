#!/usr/bin/env python3
"""Baut aus dem Repository die oeffentliche Seite (Ordner _site) ohne die noch nicht freigegebenen Bereiche.

Einstellungen: data/live.json
  versteckt   Ordner, die oeffentlich nicht erreichbar sein sollen (Earnings, Screener, Depot, Aktien-Hub ...)
  testkopie   Name eines nicht verlinkten Unterordners mit der vollstaendigen Seite zum Testen (leer = keine Testkopie)
  fmp_aus     true = Kurse und Earnings-Ergebnisse aus dem FMP-Zwischenserver in Artikeln abschalten
  domain_neu  endgueltige Adresse, ersetzt domain_alt in Canonical, Sitemap usw. (leer = nichts ersetzen)

Aufruf: python3 tools/live_filter.py [Ausgabeordner]
"""
import json, os, re, shutil, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "_site"
CFG = json.load(open("data/live.json", encoding="utf-8"))
HID = CFG.get("versteckt", [])
TEST = (CFG.get("testkopie") or "").strip("/")
ALT, NEU = CFG.get("domain_alt", ""), CFG.get("domain_neu", "")
FMP_AUS = CFG.get("fmp_aus", False)
SKIP = {".git", ".github", "_site", "tools", "docs", "worker", "content", "node_modules", "__pycache__"}
SKIP_FILES = {"ANLEITUNG.txt", "README.md"}


def neu(s):
    """Alte Adresse durch die neue ersetzen, auch in der kodierten Form (Teilen-Links: https%3A//...)."""
    if not NEU: return s
    return s.replace(ALT, NEU).replace(ALT.replace(":", "%3A"), NEU.replace(":", "%3A"))


def kopie(ziel):
    for n in os.listdir("."):
        if n in SKIP or n in SKIP_FILES or n.startswith("."): continue
        (shutil.copytree if os.path.isdir(n) else shutil.copy2)(n, os.path.join(ziel, n))


def hid_alt():
    return "|".join(re.escape(h) for h in HID)


def filtern(html):
    h = hid_alt()
    ziel = r'href="(?:(?:\.\./)*|\./|/|' + re.escape(ALT) + r')(?:' + h + r')(?:/[^"]*)?"'
    # Kacheln auf der Startseite und Menuepunkte (Anker mit kurzem Text) ganz entfernen
    html = re.sub(r'<a class="tile" ' + ziel + r'[^>]*>.*?</a>', '', html, flags=re.S)
    html = re.sub(r'<a ' + ziel + r'[^>]*>[^<]{1,40}</a>', '', html)
    # uebrige Verweise im Text: nur der Text bleibt
    html = re.sub(r'<a\b[^>]*' + ziel + r'[^>]*>(.*?)</a>', r'\1', html, flags=re.S)
    if FMP_AUS:
        html = re.sub(r'<script[^>]*assets/(?:kurse|fkearn)\.js[^>]*></script>\n?', '', html)
    return html


def main():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    if TEST:
        t = os.path.join(OUT, TEST); os.makedirs(t); kopie(t)
        for r, _, fs in os.walk(t):
            for f in fs:
                if f.endswith(".html"):
                    p = os.path.join(r, f); s = open(p, encoding="utf-8").read()
                    s2 = re.sub(r'<meta name="robots" content="[^"]*">', '<meta name="robots" content="noindex,nofollow">', s, count=1)
                    if s2 == s and "<head>" in s: s2 = s.replace("<head>", '<head>\n<meta name="robots" content="noindex,nofollow">', 1)
                    open(p, "w", encoding="utf-8").write(s2)
        for n in ("sitemap.xml", "robots.txt", "llms.txt", "CNAME"):
            p = os.path.join(t, n)
            if os.path.exists(p): os.remove(p)
    kopie(OUT)
    if TEST: shutil.rmtree(os.path.join(OUT, TEST, TEST), ignore_errors=True)
    for d in HID:
        shutil.rmtree(os.path.join(OUT, d), ignore_errors=True)
    n_html = 0
    for r, _, fs in os.walk(OUT):
        if TEST and os.path.relpath(r, OUT).split(os.sep)[0] == TEST: continue
        for f in fs:
            p = os.path.join(r, f)
            if f.endswith(".html"):
                s = open(p, encoding="utf-8").read(); s2 = filtern(s)
                if s2 != s: n_html += 1
                s2 = neu(s2)
                open(p, "w", encoding="utf-8").write(s2)
            elif f == "sitemap.xml":
                s = open(p, encoding="utf-8").read()
                s = re.sub(r"<url><loc>" + re.escape(ALT) + r"(?:" + hid_alt() + r")/[^<]*</loc>.*?</url>\n?", "", s, flags=re.S)
                open(p, "w", encoding="utf-8").write(neu(s))
            elif f in ("llms.txt", "robots.txt"):
                lines = [l for l in open(p, encoding="utf-8").read().split("\n") if not re.search(r"(?:^|[\s(<\"])(?:" + re.escape(ALT) + r"|/)(?:" + hid_alt() + r")/", l)]
                s = "\n".join(lines)
                if f == "robots.txt" and TEST: s = s.rstrip("\n") + "\n\nUser-agent: *\nDisallow: /" + TEST + "/\n"
                open(p, "w", encoding="utf-8").write(neu(s))
            elif NEU and f.endswith((".xml", ".txt", ".json", ".webmanifest")) and f != "live.json":
                try: s = open(p, encoding="utf-8").read()
                except Exception: continue
                open(p, "w", encoding="utf-8").write(neu(s))
    print(f"{OUT}: {n_html} Seiten angepasst, versteckt: {', '.join(HID)}" + (f", Testkopie: /{TEST}/" if TEST else ""))


main()
