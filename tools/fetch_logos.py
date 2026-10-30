#!/usr/bin/env python3
"""Holt fuer jeden Magazin-Artikel ein Firmenlogo und speichert es im Repo (assets/logos/).

Reihenfolge der Quellen: 1) FMP-Symbolbild, 2) Icon der Firmenwebsite (apple-touch-icon / icon),
3) Google-Favicon, 4) DuckDuckGo-Icon, 5) Wikipedia (nur wenn der Bildname "logo" enthaelt).
Klappt nichts, entsteht ein Buchstaben-Logo (Datei *.mono.png); beim naechsten Lauf wird es erneut versucht.
Der Pfad steht danach im Artikel als `logo_file:`. Eigene Datei? Einfach `logo_file:` selbst setzen.
Aufruf: python3 tools/fetch_logos.py   (laeuft im Workflow vor dem Bauen des Magazins)"""
import re, os, io, glob, sys, json, urllib.request, urllib.parse
from PIL import Image, ImageDraw, ImageFont

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = "assets/logos"
SIZE = 256


def get(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                return None
            return r.read(6_000_000)
    except Exception as e:
        print("   -", url[:90], "->", str(e)[:60])
        return None


def to_logo(raw, min_side=48):
    """Bytes -> quadratisches PNG (SIZE x SIZE, transparent, Logo eingepasst) oder None."""
    if not raw:
        return None
    try:
        im = Image.open(io.BytesIO(raw))
        if getattr(im, "n_frames", 1) > 1 and im.format == "ICO":
            sizes = im.info.get("sizes") or []
            if sizes:
                im.size = max(sizes)
                im.load()
        im = im.convert("RGBA")
    except Exception:
        return None
    if min(im.size) < min_side:
        return None
    # leere Raender abschneiden (Transparenz oder reines Weiss)
    px = im.getdata()
    if len(set(px)) < 2:        # einfarbig = Platzhalter
        return None
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(bg, im).convert("RGB")
    diff = Image.eval(flat.convert("L"), lambda v: 255 if v < 245 else 0)
    box = im.getchannel("A").getbbox() if im.getchannel("A").getextrema()[0] < 250 else diff.getbbox()
    if box:
        im = im.crop(box)
    if min(im.size) < 8:
        return None
    s = min((SIZE - 24) / im.width, (SIZE - 24) / im.height)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    canvas.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2), im)
    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def from_fmp(sym):
    if not sym:
        return None
    if sym.upper().endswith(".L") and not get(f"https://images.financialmodelingprep.com/symbol/{urllib.parse.quote(sym)}.png"):
        sym = sym[:-2]      # Londoner Titel: Bild der Hauptnotiz/ADR (z. B. BP.L -> BP)
    return to_logo(get(f"https://images.financialmodelingprep.com/symbol/{urllib.parse.quote(sym)}.png"), 48)


def from_site(dom):
    if not dom:
        return None
    for base in (f"https://www.{dom}/", f"https://{dom}/"):
        raw = get(base)
        if not raw:
            continue
        html = raw.decode("utf-8", "ignore")[:400000]
        cands = []
        for m in re.finditer(r"<link\b[^>]*>", html, re.I):
            tag = m.group(0)
            rel = re.search(r'rel=["\']([^"\']+)["\']', tag, re.I)
            href = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
            if not rel or not href or "icon" not in rel.group(1).lower():
                continue
            sz = re.search(r'sizes=["\'](\d+)x(\d+)', tag, re.I)
            score = int(sz.group(1)) if sz else (180 if "apple" in rel.group(1).lower() else 32)
            if href.group(1).lower().split("?")[0].endswith(".svg"):
                continue
            cands.append((score, urllib.parse.urljoin(base, href.group(1))))
        for _, u in sorted(cands, reverse=True)[:3]:
            lg = to_logo(get(u), 64)
            if lg:
                return lg
    return None


def from_google(dom):
    if not dom:
        return None
    return to_logo(get(f"https://t1.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://{dom}&size=256"), 48)


def from_ddg(dom):
    if not dom:
        return None
    return to_logo(get(f"https://icons.duckduckgo.com/ip3/{dom}.ico"), 32)


def from_wiki(name):
    if not name:
        return None
    try:
        q = urllib.parse.urlencode({"action": "query", "generator": "search", "gsrsearch": name + " company", "gsrlimit": 1, "prop": "pageimages",
                                    "piprop": "thumbnail|name", "pithumbsize": 400, "format": "json"})
        raw = get("https://en.wikipedia.org/w/api.php?" + q)
        if not raw:
            return None
        pages = (json.loads(raw).get("query") or {}).get("pages") or {}
        for p in pages.values():
            if "logo" in (p.get("pageimage") or "").lower() and p.get("thumbnail"):
                return to_logo(get(p["thumbnail"]["source"]), 48)
    except Exception as e:
        print("   - Wikipedia:", str(e)[:60])
    return None


def monogram(name):
    letter = (re.sub(r"[^A-Za-z0-9]", "", name or "?") or "?")[0].upper()
    im = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((16, 16, SIZE - 16, SIZE - 16), radius=44, fill=(47, 158, 91, 255))
    font = None
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            font = ImageFont.truetype(f, 130)
            break
    font = font or ImageFont.load_default()
    d.text((SIZE / 2, SIZE / 2 + 4), letter, fill=(255, 255, 255, 255), font=font, anchor="mm")
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def front(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if not m:
        return None, None, raw
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return meta, m, raw


def main():
    os.makedirs(OUT, exist_ok=True)
    for path in sorted(glob.glob("content/magazin/*.md")):
        if path.endswith("README.md"):
            continue
        meta, m, raw = front(path)
        if meta is None:
            continue
        sym = re.sub(r"[^A-Za-z0-9.\-]", "", meta.get("logo_symbol", ""))
        dom = re.sub(r"^(https?://)?(www\.)?|/.*$", "", meta.get("logo_domain", "").lower())
        if not re.fullmatch(r"[a-z0-9\-]+(\.[a-z0-9\-]+){1,3}", dom) or re.search(r"invalid|example|dummy|avoided", dom):
            dom = ""          # unbrauchbare Domain (vom Modell erfunden) ignorieren
        name = meta.get("logo_name") or re.split(r"[ :,]", meta.get("title", ""))[0]
        cur = meta.get("logo_file", "")
        if cur and os.path.exists(cur) and not cur.endswith(".mono.png"):
            continue
        key = re.sub(r"[^a-z0-9]+", "-", (sym or dom or name).lower()).strip("-") or "firma"
        final, mono = f"{OUT}/{key}.png", f"{OUT}/{key}.mono.png"
        print(os.path.basename(path), "->", key)
        if os.path.exists(final):
            data = True
        else:
            data = None
            for label, fn, arg in (("FMP", from_fmp, sym), ("Website", from_site, dom), ("Google", from_google, dom), ("DuckDuckGo", from_ddg, dom), ("Wikipedia", from_wiki, name)):
                png = fn(arg)
                if png:
                    open(final, "wb").write(png)
                    print("   Logo gefunden:", label)
                    data = True
                    break
        use = final if data else mono
        if not data:
            print("   kein Logo gefunden, Buchstaben-Logo")
            open(mono, "wb").write(monogram(name))
        if cur != use:
            head = m.group(1).rstrip("\n")
            head = re.sub(r"^logo_file:.*\n?", "", head, flags=re.M).rstrip("\n")
            new = f"---\n{head}\nlogo_file: {use}\n---\n{m.group(2)}"
            open(path, "w", encoding="utf-8").write(new)


if __name__ == "__main__":
    main()
