#!/usr/bin/env python3
"""Einmal-Werkzeug: Wikimedia-Commons-Fotos suchen (--suche) oder eine Datei holen (--datei)."""
import argparse, json, re, sys, urllib.parse, urllib.request, io
from PIL import Image
UA = "dividenden-rechner-foto/1.0 (https://dividenden-rechner.de; kontakt via GitHub)"
API = "https://commons.wikimedia.org/w/api.php"
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
def api(**p):
    p.update(format="json"); return json.loads(get(API + "?" + urllib.parse.urlencode(p)))
def info(title):
    d = api(action="query", titles=title, prop="imageinfo", iiprop="url|size|extmetadata", iiurlwidth=1600)
    pg = list(d["query"]["pages"].values())[0]; return pg.get("imageinfo", [{}])[0]
ap = argparse.ArgumentParser(); ap.add_argument("--suche"); ap.add_argument("--datei"); ap.add_argument("--slug")
a = ap.parse_args()
if a.suche:
    d = api(action="query", list="search", srsearch=a.suche, srnamespace=6, srlimit=25)
    for h in d["query"]["search"]:
        ii = info(h["title"]); md = ii.get("extmetadata", {})
        print(h["title"], "|", ii.get("width"), "x", ii.get("height"), "|", md.get("LicenseShortName", {}).get("value"), "|", re.sub("<[^>]+>", "", md.get("Artist", {}).get("value", ""))[:50])
if a.datei:
    ii = info(a.datei); md = ii["extmetadata"]
    im = Image.open(io.BytesIO(get(ii.get("thumburl") or ii["url"]))).convert("RGB")
    w, h = im.size; tw, th = w, int(w * 9 / 16)
    if th > h: th = h; tw = int(h * 16 / 9)
    x0 = (w - tw) // 2; y0 = (h - th) // 2
    im = im.crop((x0, y0, x0 + tw, y0 + th)).resize((1600, 900), Image.LANCZOS)
    out = f"assets/magazin/{a.slug}-foto.jpg"; im.save(out, quality=84, optimize=True)
    meta = {"artist": re.sub("<[^>]+>", "", md.get("Artist", {}).get("value", "")), "license": md.get("LicenseShortName", {}).get("value"), "source": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(a.datei.replace(" ", "_"))}
    print(json.dumps(meta, ensure_ascii=False)); open(f"assets/magazin/{a.slug}-foto.json", "w").write(json.dumps(meta, ensure_ascii=False))
