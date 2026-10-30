#!/usr/bin/env python3
"""Fuellt data/bildbibliothek.json aus den vorhandenen Firmen-Artikeln (je Boersenkuerzel das neueste Foto; vorhandene Eintraege bleiben)."""
import glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir_agent as ia

n = 0
for path in sorted(glob.glob(os.path.join(ia.ROOT, "content", "magazin", "2*.md")), reverse=True):
    t = open(path, encoding="utf-8").read(4000)
    m = re.match(r"^---\s*\n(.*?)\n---", t, re.S)
    if not m:
        continue
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1); meta[k.strip()] = v.strip().strip('"')
    sym, img = (meta.get("logo_symbol") or "").upper(), meta.get("image", "")
    if not sym or not img or meta.get("typ") == "kurz" or meta.get("category") == "Branchenvergleich" or sym in ia.bib_load():
        continue
    if not img.startswith("http") and not os.path.exists(os.path.join(ia.ROOT, img)):
        continue
    e = {"title": "Foto " + (meta.get("logo_name") or sym), "page": meta.get("image_source", ""), "artist_url": meta.get("image_artist_url", ""),
         "credit": meta.get("image_credit", ""), "desc": meta.get("image_alt", ""), "firma": meta.get("logo_name", ""), "quelle": ""}
    if img.startswith("http"):
        e["thumb"] = img; e["quelle"] = "Unsplash" if "unsplash" in img else ""
    else:
        e["file"] = img
    ia.bib_set(sym, e); n += 1
print(n, "Fotos in die Bibliothek aufgenommen,", len(ia.bib_load()), "insgesamt")
