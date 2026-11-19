#!/usr/bin/env python3
"""Erzeugt ein Facebook-Feed-Bild im Format 4:5 (1080 x 1350 px).

Facebook zeigt Hochformat ohne Beschnitt am größten; die Link-Vorschau
(1200 x 630, 1,91:1) bleibt davon unberührt, weil sie aus og:image kommt.

Aufruf:
  python3 tools/fb_post_bild.py BILD.jpg "Überschrift" AUSGABE.png [--kicker "Quartalszahlen"] [--logo assets/logos/wmt.png]
"""
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1080, 1350
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
GREEN = (47, 158, 91)


def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for wort in text.split():
        probe = (cur + " " + wort).strip()
        if draw.textlength(probe, font=font) <= max_w:
            cur = probe
        else:
            lines.append(cur)
            cur = wort
    if cur:
        lines.append(cur)
    return lines


def bauen(bild_pfad, ueberschrift, ausgabe, kicker=None, logo_pfad=None):
    foto = ImageOps.exif_transpose(Image.open(bild_pfad)).convert("RGB")
    # Cover-Zuschnitt auf 4:5, Mitte bleibt sichtbar
    ratio = W / H
    fw, fh = foto.size
    if fw / fh > ratio:
        nw = int(fh * ratio)
        x = (fw - nw) // 2
        foto = foto.crop((x, 0, x + nw, fh))
    else:
        nh = int(fw / ratio)
        y = (fh - nh) // 2
        foto = foto.crop((0, y, fw, y + nh))
    img = foto.resize((W, H), Image.LANCZOS)

    # Dunkler Verlauf unten für die Schrift
    verlauf = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(verlauf)
    start = int(H * 0.42)
    for y in range(start, H):
        a = int(230 * (y - start) / (H - start))
        vd.line([(0, y), (W, y)], fill=(8, 22, 16, a))
    img = Image.alpha_composite(img.convert("RGBA"), verlauf)

    d = ImageDraw.Draw(img)
    pad = 72
    # Überschrift so klein wie nötig, höchstens 5 Zeilen
    size = 74
    while True:
        f_h = ImageFont.truetype(FONT_BOLD, size)
        zeilen = wrap(d, ueberschrift, f_h, W - 2 * pad)
        if len(zeilen) <= 5 or size <= 48:
            break
        size -= 4
    lh = int(size * 1.18)
    kicker_h = 52 if kicker else 0
    block_h = kicker_h + lh * len(zeilen)
    # Block von unten aufbauen: Abstand zur Fußzeile 150 px
    y = H - 150 - block_h
    if kicker:
        f_k = ImageFont.truetype(FONT_BOLD, 34)
        d.text((pad, y), kicker.upper(), font=f_k, fill=(127, 224, 167))
        y += kicker_h
    for z in zeilen:
        d.text((pad, y), z, font=f_h, fill=(255, 255, 255))
        y += lh

    # Logo oben links auf weißer Fläche
    if logo_pfad:
        logo = Image.open(logo_pfad).convert("RGBA")
        logo.thumbnail((150, 150))
        box = Image.new("RGBA", (logo.width + 40, logo.height + 40), (255, 255, 255, 235))
        img.alpha_composite(box, (pad, pad))
        img.alpha_composite(logo, (pad + 20, pad + 20))

    # Marke unten
    f_m = ImageFont.truetype(FONT_REG, 34)
    d = ImageDraw.Draw(img)
    d.text((pad, H - pad - 34), "dividenden-rechner.de", font=f_m, fill=(220, 230, 225))

    img.convert("RGB").save(ausgabe, quality=92, optimize=True)
    print(ausgabe, img.size)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("bild")
    p.add_argument("ueberschrift")
    p.add_argument("ausgabe")
    p.add_argument("--kicker")
    p.add_argument("--logo")
    a = p.parse_args()
    bauen(a.bild, a.ueberschrift, a.ausgabe, a.kicker, a.logo)
