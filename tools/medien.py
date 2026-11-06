#!/usr/bin/env python3
"""Medien-Ablage: Logos, CEO-Freisteller und Aufmacherfotos, sortiert nach Boersenkuerzel.

medien/index.json:  { "MP": {"name": "MP Materials", "logo": "medien/logo/mp.png",
                             "ceo": {"name": "James Litinsky", "datei": "medien/ceo/mp.png", "rolle": "CEO", "ab": "2026-11-06"},
                             "aufmacher": ["medien/aufmacher/mp/<datei>.jpg", ...]}}
Ordner:  medien/logo/<kuerzel>.png | medien/ceo/<kuerzel>.png | medien/aufmacher/<kuerzel>/<datei>

`python3 tools/medien.py sync` liest alle Artikel und legt fehlende Dateien dort ab (Kopie, nichts wird verschoben).
Der Magazin-Bau nutzt den Index: fehlen in einem Artikel Logo, CEO-Portrait oder Aufmacher, wird das Abgelegte
fuer das Kuerzel automatisch genommen (ein CEO-Wechsel: neuen Freisteller ablegen, `ceo` im Index ueberschreiben).
"""
import os, re, sys, json, glob, shutil
IDX = "medien/index.json"
def key(sym): return re.sub(r"[^a-z0-9]+", "-", (sym or "").lower()).strip("-")
def load():
    try: return json.load(open(IDX, encoding="utf-8"))
    except Exception: return {}
def save(d):
    os.makedirs("medien", exist_ok=True)
    json.dump(d, open(IDX, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
def front(path):
    s = open(path, encoding="utf-8").read(); m = re.match(r"---\n(.*?)\n---\n", s, re.S); meta = {}
    if m:
        for ln in m.group(1).splitlines():
            if ":" in ln and not ln.startswith(" "):
                k, v = ln.split(":", 1); meta[k.strip()] = v.strip().strip('"')
    return meta
def put(src, dst):
    if not src or not os.path.exists(src): return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.exists(dst): shutil.copyfile(src, dst)
    return True
def sync():
    d = load()
    for p in sorted(glob.glob("content/magazin/*/*.md")):
        m = front(p); sym = (m.get("logo_symbol") or "").upper()
        if not sym or m.get("kein_logo", "").lower() in ("ja", "true"): continue
        k = key(sym); e = d.setdefault(sym, {}); e.setdefault("name", m.get("logo_name") or sym)
        lf = m.get("logo_file", "")
        if lf and not lf.endswith(".mono.png") and not os.path.basename(lf).startswith("combo-") and put(lf, f"medien/logo/{k}.png") and "logo" not in e:
            e["logo"] = f"medien/logo/{k}.png"
        sp, qb = m.get("story_portrait", ""), m.get("story_quote_by", "")
        if sp and put(sp, f"medien/ceo/{k}.png") and "ceo" not in e:
            nm = qb.split("|")[0].strip() if qb else ""; rolle = qb.split("|")[1].strip() if "|" in qb else ""
            e["ceo"] = {"name": nm, "datei": f"medien/ceo/{k}.png", "rolle": rolle, "zeile": qb}
        im = m.get("image", "")
        if im and os.path.exists(im):
            dst = f"medien/aufmacher/{k}/{os.path.basename(im)}"
            if put(im, dst):
                e.setdefault("aufmacher", [])
                if dst not in e["aufmacher"]: e["aufmacher"].append(dst)
    save(d); print("Medien-Index:", len(d), "Firmen;", sum(1 for v in d.values() if v.get("ceo")), "mit CEO;", sum(1 for v in d.values() if v.get("logo")), "mit Logo")
def fill(meta):
    """Im Magazin-Bau: fehlende Felder eines Artikels aus der Ablage ergaenzen."""
    sym = (meta.get("logo_symbol") or "").upper()
    if not sym or meta.get("kein_logo"): return
    e = load().get(sym)
    if not e: return
    lf = meta.get("logo_file", "")
    if (not lf or not os.path.exists(lf)) and e.get("logo") and os.path.exists(e["logo"]): meta["logo_file"] = e["logo"]
    c = e.get("ceo")
    if c and not meta.get("story_portrait") and os.path.exists(c.get("datei", "")) and meta.get("category") == "Quartalszahlen":
        meta["story_portrait"] = c["datei"]
        if not meta.get("story_quote_by") and c.get("zeile"): meta["story_quote_by"] = c["zeile"]
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sync": sync()
    else: print(__doc__)
