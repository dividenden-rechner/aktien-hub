#!/usr/bin/env python3
"""Raeumt doppelte Kurzmeldungen auf: gleiche Firma, gleiche Themengruppe, innerhalb von 3 Tagen.
Behalten wird ein langer Artikel, sonst die laengste Kurzmeldung. Lange Artikel werden nie geloescht.  --dry zeigt nur an."""
import os, re, sys, glob, collections
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kurzmeldungen import cat_group

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def meta(f):
    t = open(f, encoding="utf-8").read(); h = t.split("---")[1]
    g = lambda n: (re.search(rf'^{n}:\s*"?(.*?)"?\s*$', h, re.M) or [None, ""])[1]
    return {"f": f, "sym": g("logo_symbol"), "cat": g("category"), "typ": g("typ") or "lang", "date": datetime.strptime(g("date")[:16], "%Y-%m-%d %H:%M"),
            "draft": bool(re.search(r"^draft:\s*true", h, re.M)), "len": len(t), "img": g("image")}

def main():
    dry = "--dry" in sys.argv
    ms = [meta(f) for f in glob.glob(os.path.join(ROOT, "content/magazin/2*.md"))]
    groups = collections.defaultdict(list)
    for m in ms:
        if m["sym"]: groups[(m["sym"], cat_group(m["cat"]))].append(m)
    gone = 0
    for k, l in groups.items():
        l.sort(key=lambda m: m["date"]); cl = []
        for m in l:
            if cl and m["date"] - cl[-1][-1]["date"] <= timedelta(days=3): cl[-1].append(m)
            else: cl.append([m])
        for c in cl:
            if len(c) < 2 or all(m["typ"] != "kurz" for m in c): continue
            keep = next((m for m in c if m["typ"] != "kurz"), None) or max(c, key=lambda m: m["len"])
            for m in c:
                if m is keep or m["typ"] != "kurz": continue
                print(("[dry] " if dry else "") + "entferne", os.path.basename(m["f"]), "| behalte", os.path.basename(keep["f"]))
                gone += 1
                if not dry:
                    os.remove(m["f"])
                    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-\d{4}-", "", os.path.basename(m["f"])[:-3])
                    for a in glob.glob(os.path.join(ROOT, "assets/magazin", slug + "*")): os.remove(a)
    print(gone, "doppelte Kurzmeldungen")

if __name__ == "__main__":
    main()
