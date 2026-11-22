#!/usr/bin/env python3
"""Ersetzt im Fuß aller HTML-Seiten den Instagram-Link durch alle Links aus data/social.json.
Idempotent über die Marken <!--social--> ... <!--/social-->. Aufruf: python3 tools/social_links.py [Ordner]"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ziel = sys.argv[1] if len(sys.argv) > 1 else ROOT
links = json.load(open(os.path.join(ROOT, "data/social.json"), encoding="utf-8"))["links"]
html = "<!--social-->" + "".join(f'<a href="{l["url"]}" rel="noopener nofollow me" target="_blank">{l["name"]}</a>' for l in links) + "<!--/social-->"
ALT = re.compile(r'<!--social-->.*?<!--/social-->|<a href="https://www\.instagram\.com/dividenden\.rechner" rel="noopener nofollow me" target="_blank">Instagram</a>', re.S)
n = 0
for dp, dn, fn in os.walk(ziel):
    dn[:] = [d for d in dn if d not in (".git", "node_modules", "intern-t7q4m9")]
    for f in fn:
        if not f.endswith(".html"):
            continue
        p = os.path.join(dp, f)
        s = open(p, encoding="utf-8", errors="ignore").read()
        if 'class="site-footer"' not in s:
            continue
        neu = ALT.sub(html, s, count=1)
        if neu != s:
            open(p, "w", encoding="utf-8").write(neu); n += 1
print(n, "Seiten aktualisiert")
