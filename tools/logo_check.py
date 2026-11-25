#!/usr/bin/env python3
"""Logo-Waechter: erkennt, ob ein Bild ein Foto statt eines Logos ist (zum Beispiel ein Gebaeude oder eine Landschaft).
Ein Logo hat wenige, flaechige Farben (oder Transparenz). Ein Foto ist deckend und hat sehr viele Farbtoene.
Wird von fetch_logos.py und hub_logos.py beim Herunterladen, vom Magazin-Bau beim Einbinden benutzt, damit nie wieder
ein Foto als Firmenlogo erscheint. Aufruf zur Pruefung aller vorhandenen Logos: python3 tools/logo_check.py"""
import io, os, re, sys, glob, collections
from PIL import Image


def ist_foto_bild(im):
    im = im.convert("RGBA").resize((64, 64))
    px = list(im.getdata())
    deckend = [p for p in px if p[3] > 128]
    if not deckend or 1 - len(deckend) / len(px) > 0.02:   # Transparenz = Logo
        return False
    farben = collections.Counter((r >> 4, g >> 4, b >> 4) for r, g, b, a in deckend)
    top8 = sum(c for _, c in farben.most_common(8)) / len(deckend)
    return len(farben) >= 150 and top8 < 0.45


def ist_foto(quelle):
    """quelle: Dateipfad oder Bytes. Im Zweifel False (kein Foto)."""
    try:
        im = Image.open(io.BytesIO(quelle) if isinstance(quelle, (bytes, bytearray)) else quelle)
        return ist_foto_bild(im)
    except Exception:
        return False


if __name__ == "__main__":
    loeschen = "--loeschen" in sys.argv
    n = 0; gefunden = []
    for p in sorted(glob.glob("assets/logos/*.png") + glob.glob("assets/logos/hub/*.png")):
        if p.endswith(".mono.png") or os.path.basename(p).startswith("combo-"):
            continue
        if ist_foto(p):
            n += 1
            print("Foto statt Logo:", p)
            if p.startswith("assets/logos/hub/"):
                gefunden.append(os.path.basename(p)[:-4])
            if loeschen:
                os.remove(p)
    if loeschen and gefunden:   # Kuerzel in assets/logos.js eintragen, damit die Seite das Foto nicht direkt von FMP nachlaedt
        js = open("assets/logos.js", encoding="utf-8").read()
        m = re.search(r"/\*FOTO\*/var FOTO = \{(.*?)\};/\*/FOTO\*/", js)
        alt = set(re.findall(r'"([^"]+)":1', m.group(1))) if m else set()
        neu = ",".join('"%s":1' % x for x in sorted(alt | set(gefunden)))
        js = re.sub(r"/\*FOTO\*/var FOTO = \{.*?\};/\*/FOTO\*/", lambda _: "/*FOTO*/var FOTO = {" + neu + "};/*/FOTO*/", js)
        open("assets/logos.js", "w", encoding="utf-8").write(js)
    print(n, "verdaechtige Dateien")
