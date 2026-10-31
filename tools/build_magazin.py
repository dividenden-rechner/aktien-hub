#!/usr/bin/env python3
"""Baut das Magazin: Markdown-Dateien in content/magazin/*.md -> HTML-Seiten, Übersicht, RSS-Feed, Sitemap, llms.txt,
Startseiten-Teaser und Navigationseintrag. Aufruf im Repo-Hauptordner:  python3 tools/build_magazin.py
Benötigt: pip install markdown pillow"""
import urllib.parse, re, os, sys, json, html, glob, datetime, email.utils
from zoneinfo import ZoneInfo
import markdown
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glossar
import build_wissen
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
CFG = json.load(open("tools/site.json", encoding="utf-8"))
BASE = CFG["base"] if CFG["base"].endswith("/") else CFG["base"] + "/"
SITE = CFG["name"]
esc = lambda s: html.escape(str(s), quote=True)
NAV = [("rechner", "", "Rechner"), ("aktien", "aktien/", "Aktien"), ("depot", "depot/", "Depot"), ("news", "news/", "News"),
       ("earnings", "earnings/", "Earnings"), ("screener", "screener/", "Screener"),
       ("einfuehrung", "einfuehrung/", "Einführung"), ("grundlagen", "grundlagen/", "Grundlagen"),
       ("fortgeschrittene", "fortgeschrittene/", "Fortgeschrittene")]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
KURZ_HINWEIS = ('Diese Kurzmeldung wurde automatisch aus der Pressemitteilung des Unternehmens erstellt und nicht vorab redaktionell geprüft. '
               'Maßgeblich ist die verlinkte Originalmeldung.')
HINT = ('<p class="note"><strong>Hinweis:</strong> Dieser Text dient der allgemeinen Information und ist weder Anlage-, '
        'Steuer- noch Rechtsberatung. Kapitalanlagen sind mit Risiken verbunden, bis hin zum Totalverlust.</p>')

def de_date(d):
    return f"{d.day}. {MONTHS[d.month-1]} {d.year}"

def de_dt_kurz(d):
    """kompakt fuer Karten: 27.10.2026, 20:20 Uhr"""
    return d.strftime("%d.%m.%Y, %H:%M") + " Uhr"

def de_dt(d):
    """Datum mit Uhrzeit, z. B. 28. Oktober 2026, 14:52 Uhr"""
    return f"{de_date(d)}, {d.strftime('%H:%M')} Uhr"

def parse_date(s):
    s = str(s).strip()
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try: return datetime.datetime.strptime(s, f)
        except ValueError: pass
    raise ValueError("Datum nicht lesbar: " + s)

def iso(d):  # mit deutscher Zeitzone (Sommer- und Winterzeit korrekt)
    try:
        from zoneinfo import ZoneInfo
        d = d.replace(tzinfo=ZoneInfo("Europe/Berlin"))
        return d.strftime("%Y-%m-%dT%H:%M:%S%z")[:-2] + ":" + d.strftime("%z")[-2:]
    except Exception:
        off = "+02:00" if 4 <= d.month <= 10 else "+01:00"
        return d.strftime("%Y-%m-%dT%H:%M:%S") + off

def clean_entities(t, keep_markup=False):
    """HTML-Entities (&auml; &amp; &#8211; ...) in lesbare Zeichen umwandeln. Im Text bleiben &lt; &gt; &amp; erhalten, damit kein Markup entsteht."""
    if not t or "&" not in t: return t
    if not keep_markup: return html.unescape(t)
    return re.sub(r"&(?!(?:lt|gt|amp|quot|#39);)(#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);", lambda m: html.unescape(m.group(0)), t)


def fix_kurz(body):
    """Der Kurz-Kasten (!!! kurz) darf nicht durch Bilder oder Absaetze unterbrochen sein, sonst wird die Liste zum Codeblock.
    Unterbrechungen (nicht eingerueckte Zeilen mitten im Kasten) werden hinter den Kasten verschoben."""
    lines = body.split("\n")
    st = next((i for i, l in enumerate(lines) if l.startswith("!!! kurz")), None)
    if st is None: return body
    block, moved, i, seen_indented_after_break = [lines[st]], [], st + 1, False
    n = len(lines)
    # Ende des Kastens: bis zur naechsten Ueberschrift (## ...)
    end = next((j for j in range(st + 1, n) if lines[j].startswith("#")), n)
    for j in range(st + 1, end):
        l = lines[j]
        if l.startswith("    ") or not l.strip(): block.append(l)
        else: moved.append(l)
    if not moved: return body
    while block and not block[-1].strip(): block.pop()
    return "\n".join(lines[:st] + block + [""] + moved + [""] + lines[end:])


def read_post(path):
    raw = clean_entities(open(path, encoding="utf-8").read(), keep_markup=True)
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if not m: raise SystemExit(f"{path}: Kopfbereich zwischen --- fehlt")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1); meta[k.strip().lower()] = clean_entities(v.strip().strip('"').strip("'"))
    for k in ("title", "description", "date"):
        if not meta.get(k): raise SystemExit(f"{path}: Feld '{k}' fehlt im Kopfbereich")
    import artikel; stem = artikel.slug_of(path)   # Datum und Zaehler vor dem Dateinamen gehoeren nicht zur Adresse
    meta["slug"] = meta.get("slug") or re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    meta["file"] = os.path.relpath(path, "content/magazin").replace(os.sep, "/")
    meta["dt"] = parse_date(meta["date"])
    meta["upd"] = parse_date(meta["updated"]) if meta.get("updated") else meta["dt"]
    meta["body_md"] = fix_kurz(m.group(2).strip())
    for k in ("title", "description"):
        if meta.get(k): meta[k] = nbsp_units(round_big(meta[k]))
    meta["body_md"] = nbsp_units(meta["body_md"])
    if meta.get("kein_logo", "").lower() in ("ja", "true", "1", "yes"):   # Artikel ohne Firmenlogo (zum Beispiel Marktueberblick)
        meta["logo_file"] = meta["logo_symbol"] = meta["logo_domain"] = ""; meta["kein_logo"] = True
    meta["draft"] = meta.get("draft", "").lower() in ("true", "ja", "1", "yes")
    meta["author"] = meta.get("author") or CFG["default_author"]
    if "redaktion" in meta["author"].lower(): meta["author"] = "Aus der Redaktion"
    meta["category"] = meta.get("category") or "Analyse"
    return meta

_BIG = re.compile(r"(?<![\d,.])(\d{1,3}(?:\.\d{3})*|\d+),(\d{2,})(\s*(?:Mrd\.|Mio\.|Bio\.|Milliarden|Millionen|Billionen)(?!\w))")


def round_big(t):
    """Betraege in Milliarden/Millionen mit genau einer Nachkommastelle (17,404 Mrd. -> 17,4 Mrd.)."""
    from decimal import Decimal, ROUND_HALF_UP
    def r(m):
        v = Decimal(m.group(1).replace(".", "") + "." + m.group(2)).quantize(Decimal("0.1"), ROUND_HALF_UP)
        i, d = str(v).split(".")
        return "{:,}".format(int(i)).replace(",", ".") + "," + d + m.group(3)
    return _BIG.sub(r, t or "")


_NB = re.compile(r"(\d) (%|Prozent\b|Mrd\.|Mio\.|Bio\.|USD\b|EUR\b|US-Dollar\b|Euro\b|Dollar\b|Punkte\b|Cent\b|Pence\b)")


def nbsp_units(t):
    """Zahl und Einheit zusammenhalten (feines geschuetztes Leerzeichen), damit '%' nie allein in die naechste Zeile rutscht."""
    t = _NB.sub("\\1\u202f\\2", t or "")
    return re.sub(r"(Mrd\.|Mio\.|Bio\.) (USD|EUR|Euro|Dollar|US-Dollar)\b", "\\1\u202f\\2", t)


def fix_kurz(t):
    """Kennzahlenzeile im Kurz-gesagt-Kasten: Umsatz und Gewinn untereinander (alte Einzeiler werden umgeformt, leere Werte entfallen)."""
    def one(m):
        parts = [x.strip() for x in m.group(1).split(" · ")]
        parts = [x for x in parts if not re.search(r":\*\*\s*(n\.\s?a\.|k\.\s?A\.|keine Angabe)\s*$", x, re.I)]
        return "".join("    " + x + "  \n" for x in parts).rstrip(" \n") if parts else ""
    t = re.sub(r"^    (\*\*(?:Umsatz|Erlöse?|Einnahmen)[^\n]*? · \*\*[^\n]+)$", one, t, flags=re.M)
    t = round_big(t)
    t = re.sub(r"^    \*\*[^*\n]+:\*\*\s*(?:n\.\s?a\.|k\.\s?A\.|keine Angabe)\s*\n", "", t, flags=re.M | re.I)   # leere Kennzahlzeilen entfallen
    # bereits untereinander geschriebene Zeilen: Zeilenumbruch erzwingen
    t = re.sub(r"^(    \*\*(?:Umsatz|Erlöse?|Einnahmen):\*\*[^\n]*?)[ ]*\n(    \*\*(?!\s))", r"\1  \n\2", t, flags=re.M)
    return t


def md_to_html(md_text, depth):
    pre = "../" * depth
    md_text = re.sub(r"<!--\s*PRÜFEN.*?-->\s*", "", md_text, flags=re.S)   # Redaktionshinweise des IR-Agenten nie veröffentlichen
    md_text = fix_kurz(md_text)
    md = markdown.Markdown(extensions=["tables", "sane_lists", "admonition", "attr_list", "toc"], extension_configs={"toc": {"permalink": False}})
    h = md.convert(md_text)
    h = re.sub(r'(href|src)="/(?!/)', lambda m: f'{m.group(1)}="{pre}', h)       # /pfad/ -> relativ
    h = re.sub(r"<table>", '<div class="tablewrap"><table>', h); h = h.replace("</table>", "</table></div>")
    h = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" rel="noopener"', h)
    return h

def words(s): return len(re.sub(r"<[^>]+>", " ", s).split())

def nav_html(depth, cur, with_mag=True):
    p = "../" * depth
    return "".join(f'<a href="{p}{u}"{" aria-current=\"page\"" if k == cur else ""}>{n}</a>' for k, u, n in NAV if with_mag or k != "news")

def footer_html(depth):
    p = "../" * depth
    l = "".join(f'<a href="{p}{u}">{n}</a>' for k, u, n in NAV)
    return (f'<footer class="site-footer"><div class="wrap">\n<div class="cols">\n{l}\n<a href="{p}ueber-uns/">Über uns</a><a href="{p}impressum/">Impressum</a><a href="{p}datenschutz/">Datenschutz</a><a href="https://www.instagram.com/dividenden.rechner" rel="noopener nofollow me" target="_blank">Instagram</a>\n</div>\n'
            '<p>Alle Inhalte dienen der allgemeinen Information und sind keine Anlage-, Steuer- oder Rechtsberatung. Kapitalanlagen sind mit Risiken verbunden.</p>\n</div></footer>')

def _cssv():
    import hashlib
    try: return hashlib.md5(open("assets/site.css", "rb").read()).hexdigest()[:8]
    except Exception: return "1"
CSSV = _cssv()

def head(depth, title, desc, url, og_type, image_url, extra=""):
    p = "../" * depth
    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1">
<link rel="canonical" href="{BASE}{url}">
<link rel="alternate" type="application/rss+xml" title="{esc(SITE)}: News" href="{p}news/feed.xml">
<meta property="og:type" content="{og_type}">
<meta property="og:locale" content="de_DE">
<meta property="og:site_name" content="{esc(SITE)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{BASE}{url}">
<meta property="og:image" content="{image_url}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="675">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{image_url}">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="{p}assets/site.css?v={CSSV}">
{extra}<link rel="icon" href="{p}favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="{p}assets/favicon-32.png">
<link rel="icon" type="image/png" sizes="192x192" href="{p}assets/favicon-192.png">
<link rel="apple-touch-icon" href="{p}assets/apple-touch-icon.png">
<link rel="stylesheet" href="{p}assets/navigation.css?v=20261025a">
</head>
<body>
<header id="hub-global-header"><div class="hub-nav-inner"><a class="hub-brand" href="{p}"><img class="hub-logo" src="{p}assets/logo.png" alt="" width="36" height="36"> <span class="hub-brand-name">Dividenden-Rechner <span>Aktien-Hub</span></span></a><nav class="hub-links" aria-label="Hauptmenü">'''

def font(size, bold=True):
    for f in ("assets/fonts/Inter-Bold.otf" if bold else "assets/fonts/Inter-Regular.otf","/usr/share/fonts/opentype/inter/Inter-Bold.otf" if bold else "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f): return ImageFont.truetype(f, size)
    return ImageFont.load_default()

def make_cover(path, title, category):
    W, H = 1200, 675
    im = Image.new("RGB", (W, H), "#ffffff"); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 18], fill="#2f9e5b")
    d.rectangle([0, H-150, W, H], fill="#f0f8f3")
    d.text((70, 70), category.upper(), font=font(30), fill="#2f9e5b")
    words_ = title.split(); lines = []; cur = ""
    f = font(66)
    for w in words_:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > W - 140: lines.append(cur); cur = w
        else: cur = t
    lines.append(cur)
    y = 130
    for ln in lines[:5]:
        d.text((70, y), ln, font=f, fill="#14202b"); y += 84
    d.text((70, H-100), "dividenden-rechner.de", font=font(36), fill="#1a7a45")
    d.text((70, H-52), "Dividenden verstehen, Aktien prüfen", font=font(24, False), fill="#5d6b78")
    im.save(path, optimize=True)

def make_share_card(p, slug, img):
    """Vorschaubild fuer X, Facebook, LinkedIn und WhatsApp (1200x675): Foto (nur eigene Dateien), Firmenlogo, Ueberschrift, Umsatz und Gewinn."""
    import hashlib
    lf = p.get("logo_file") or ""
    logo_ok = bool(lf) and not lf.endswith(".mono.png") and os.path.exists(lf)
    photo_ok = bool(img) and not ext(img) and os.path.exists(img) and "-foto" in img
    lines = kurz_lines(p.get("body_md", ""))
    key = hashlib.md5(json.dumps([p["title"], lines, lf if logo_ok else "", img if photo_ok else "", cashtag(p), p.get("category")], ensure_ascii=False).encode()).hexdigest()[:8]
    rel = f"assets/share/{slug}-{key}.jpg"
    if os.path.exists(rel):
        return rel
    os.makedirs("assets/share", exist_ok=True)
    for old in glob.glob(f"assets/share/{slug}-*.*"):
        os.remove(old)
    W, H = 1200, 675
    im = Image.new("RGB", (W, H), "#0f2a1c")
    d = ImageDraw.Draw(im)
    for yy in range(H):                       # Verlauf
        t = yy / H
        d.line([(0, yy), (W, yy)], fill=(int(15 + 5 * t), int(42 - 10 * t), int(28 - 2 * t)))
    if photo_ok:
        try:
            ph = Image.open(img).convert("RGB")
            r = max(W / ph.width, H / ph.height)
            ph = ph.resize((int(ph.width * r) + 1, int(ph.height * r) + 1), Image.LANCZOS)
            im.paste(ph.crop(((ph.width - W) // 2, (ph.height - H) // 2, (ph.width - W) // 2 + W, (ph.height - H) // 2 + H)), (0, 0))
            ov = Image.new("RGBA", (W, H))
            od = ImageDraw.Draw(ov)
            for yy in range(H):
                a = int(255 * (0.5 + 0.43 * min(1, max(0, (yy - 60) / 330))))
                od.line([(0, yy), (W, yy)], fill=(15, 36, 26, a))
            im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
            d = ImageDraw.Draw(im)
        except Exception:
            pass
    green = "#7fd6a3"
    x = 60
    if logo_ok:
        try:
            lg = Image.open(lf).convert("RGBA").resize((96, 96), Image.LANCZOS)
            d.rounded_rectangle([60, 48, 60 + 128, 48 + 128], 26, fill="#ffffff")
            im.paste(lg, (60 + 16, 48 + 16), lg)
            x = 60 + 128 + 28
        except Exception:
            pass
    lab = (p.get("category") or "News").upper() + (("  ·  " + cashtag(p)) if cashtag(p) else "")
    d.text((x, 48 + 46), lab, font=font(30), fill=green)
    f = font(58)
    words_, tl, cur = p["title"].split(), [], ""
    for w in words_:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > W - 120: tl.append(cur); cur = w
        else: cur = t
    tl.append(cur)
    y = 250
    for ln in tl[:3]:
        d.text((60, y), ln, font=f, fill="#ffffff"); y += 72
    y += 14
    for ln in lines[:2]:
        k, _, v = ln.partition(":")
        d.text((60, y), k + ":", font=font(38), fill=green)
        d.text((60 + d.textlength(k + ": ", font=font(38)) + 6, y - 4), v.strip(), font=font(44), fill="#ffffff"); y += 62
    d.text((60, H - 56), "dividenden-rechner.de", font=font(28, False), fill="#a9bdb1")
    im.save(rel, quality=88, optimize=True)
    return rel


def ext(u):
    return u.startswith("http")


def src(pre, u):
    """Bildadresse: externe Adressen (Unsplash-Hotlink) unveraendert, eigene Dateien relativ."""
    return u.replace("&", "&amp;") if ext(u) else pre + u


def absu(u):
    return u if ext(u) else BASE + u


def credit_html(p):
    cred = p.get("image_credit") or ""
    if "unsplash.com" in (p.get("image_source") or "") and p.get("image_artist_url") and p.get("image_artist_url2"):
        m = re.match(r"Fotos:\s*(.*?)\s+und\s+(.*?)\s+auf Unsplash\s*$", cred)
        n1, n2 = (esc(m.group(1)), esc(m.group(2))) if m else ("Foto 1", "Foto 2")
        return (f'Fotos: <a href="{esc(p["image_artist_url"])}" rel="noopener nofollow" target="_blank">{n1}</a> und '
                f'<a href="{esc(p["image_artist_url2"])}" rel="noopener nofollow" target="_blank">{n2}</a> auf '
                f'<a href="https://unsplash.com/?utm_source=dividenden-rechner&amp;utm_medium=referral" rel="noopener nofollow" target="_blank">Unsplash</a>')
    if "unsplash.com" in (p.get("image_source") or "") and p.get("image_artist_url"):
        m = re.match(r"Foto:\s*(.*?)\s+auf Unsplash\s*$", cred)
        nm = esc(m.group(1) if m else cred.replace("Foto:", "").strip())
        return (f'Foto: <a href="{esc(p["image_artist_url"])}" rel="noopener nofollow" target="_blank">{nm}</a> auf '
                f'<a href="https://unsplash.com/?utm_source=dividenden-rechner&amp;utm_medium=referral" rel="noopener nofollow" target="_blank">Unsplash</a>')
    if cred and p.get("image_source", "").startswith("http"):
        return f'<a href="{esc(p["image_source"])}" rel="noopener nofollow" target="_blank">{esc(cred)}</a>'
    return esc(cred)


def kurs_chip(p):
    """Aktienkuerzel mit Kurs (assets/kurse.js fuellt den Kurs). Nur bei Artikeln zu einer einzelnen Firma mit Kuerzel."""
    sym = re.sub(r"[^A-Za-z0-9.\-]", "", (p.get("logo_symbol") or "")).upper()
    if not sym or p.get("typ") == "vergleich": return ""
    return f'<p class="kchip-row"><span class="kchip" data-kurs="{esc(sym)}">${esc(re.sub(r"[.]L$|[.][A-Z]+$", "", sym))}</span></p>\n'


def logo_html(p):
    if p.get("kein_logo"): return f'<h1>{esc(p["title"])}</h1>\n'
    """Titel mit Firmenlogo (FMP-Symbolbild, Rueckfall Favicon der Firmenwebsite, sonst ohne Logo)."""
    lf = p.get("logo_file", "")
    if lf and os.path.exists(lf) and os.path.basename(lf).startswith("combo-"):
        return (f'<div class="titlerow"><img class="hlogo combo" src="../../{esc(lf)}" alt="" style="height:64px;width:auto;border:0;background:none;padding:0;object-fit:contain">'
                f'<h1>{esc(p["title"])}</h1></div>\n')
    if lf and os.path.exists(lf):
        return (f'<div class="titlerow"><img class="hlogo{" dark" if logo_is_light(lf) else ""}" src="../../{esc(lf)}" alt="" width="56" height="56">'
                f'<h1>{esc(p["title"])}</h1></div>\n')
    sym = re.sub(r"[^A-Za-z0-9.\-]", "", p.get("logo_symbol", "")); dom = re.sub(r"[^a-z0-9.\-]", "", p.get("logo_domain", "").lower())
    fav = (f"https://t1.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://{dom}&size=128") if dom else ""
    if sym:
        src = f"https://images.financialmodelingprep.com/symbol/{sym}.png"
        fb = f"this.onerror=null;this.src='{fav}'" if fav else "this.parentNode.removeChild(this)"
    elif fav:
        src, fb = fav, "this.parentNode.removeChild(this)"
    else:
        return f'<h1>{esc(p["title"])}</h1>\n'
    return (f'<div class="titlerow"><img class="hlogo" src="{src}" alt="" width="56" height="56" onerror="{fb}">'
            f'<h1>{esc(p["title"])}</h1></div>\n')

_BOERSEN_ZUSATZ = {"F", "NE", "BE", "DU", "MU", "SG", "HM", "HA", "VI"}      # Nebenplaetze: dafuer gibt es keinen sinnvollen Cashtag


def cashtag(p):
    """$TICKER fuer X (nur Buchstaben; Boersenzusatz wie .L oder .DE entfaellt, Nebenplaetze und Zahlenkuerzel nicht)."""
    sym = (p.get("x_cashtag") or p.get("logo_symbol") or "").strip().upper()
    if not sym:
        return ""
    base, _, suf = sym.partition(".")
    if suf in _BOERSEN_ZUSATZ or not re.fullmatch(r"[A-Z]{1,6}", base):
        return ""
    return "$" + base


ICONS = {
    "x": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>',
    "instagram": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5.2" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4.1" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="17.3" cy="6.7" r="1.3"/></svg>',
    "facebook": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>',
    "linkedin": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
    "whatsapp": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 00-8.6 15.1L2 22l5-1.3A10 10 0 1012 2zm0 18.2c-1.5 0-3-.4-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1112 20.2zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1-1.4-.7-2.4-1.3-3.3-2.9-.2-.4.2-.4.7-1.3.1-.2 0-.3 0-.5l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.5.1-.7.3-.8.8-1 1.7-.9 2.6.2 1.1.8 2.1 1.6 3 1.4 1.7 3.1 2.6 5.2 3.2.7.2 1.3.2 1.8.1.6-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2-.1-.1-.3-.2-.5-.3z"/></svg>',
    "telegram": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z"/></svg>',
    "mail": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2.5" y="5" width="19" height="14" rx="2.2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3.5 7l8.5 6.2L20.5 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
    "link": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
}


def kurz_lines(md_text):
    """Kennzahlzeilen (Umsatz, Gewinn) aus dem Kurz-gesagt-Kasten, ohne Markdown-Zeichen."""
    m = re.search(r'^!!! kurz[^\n]*\n((?:    [^\n]*\n|\n)+)', fix_kurz(md_text), re.M)
    out = []
    if m:
        for ln in m.group(1).splitlines():
            t = ln.strip()
            if re.match(r"\*\*[^*]+:\*\*", t) and not re.match(r"\d+\.", t):
                out.append(re.sub(r"\*\*", "", t).strip())
    return out[:3]


def kurz_points(md_text):
    """Die drei nummerierten Punkte aus dem Kurz-gesagt-Kasten als kurze Texte."""
    m = re.search(r'^!!! kurz[^\n]*\n((?:    [^\n]*\n|\n)+)', fix_kurz(md_text), re.M)
    out = []
    if m:
        for ln in m.group(1).splitlines():
            t = re.match(r"\s*\d+\.\s*(.+)", ln)
            if t:
                out.append(re.sub(r"\*\*", "", t.group(1)).strip())
    return out[:3]


def story_vorlage(p):
    """Welche Instagram-Vorlage zu welcher Rubrik passt (Dateien in assets/story-vorlagen)."""
    c = (p.get("category") or "").lower()
    if p.get("typ") == "kurz":
        return "aktuelle-meldung"
    if "quartal" in c or "jahres" in c or "halbjahr" in c:
        return "quartalsbericht"
    if "vergleich" in c or "analyse" in c:
        return "daten-fakten"
    return "aktuelle-meldung"


def share_html(p, url, img):
    """Teilen-Leiste mit Symbolen: X (Text, Cashtag, Link; Bild ueber die Vorschaukarte), Facebook, LinkedIn, WhatsApp, Telegram, E-Mail,
    Link kopieren und Instagram-Story (9:16-Bild wird im Browser erzeugt und ueber das Teilen-Menue des Handys geteilt)."""
    page = BASE + url
    q = urllib.parse.quote
    ct = cashtag(p)
    tags = ["#Dividende", "#Aktien"] + (["#Quartalszahlen"] if p.get("category") == "Quartalszahlen" else [])
    x_text = p["title"] + "\n\n" + " ".join(([ct] if ct else []) + tags)
    lf = p.get("logo_file") or ""
    story = {"title": p["title"], "lines": kurz_lines(p.get("body_md", "")), "points": kurz_points(p.get("body_md", "")), "ct": ct, "img": img,
             "logo": ("../../" + lf) if lf and not lf.endswith(".mono.png") and os.path.exists(lf) else "", "cat": p.get("category", ""),
             "tpl": "../../assets/story-vorlagen/" + story_vorlage(p) + ".png"}
    links = [
        ("x", "Auf X teilen", "https://twitter.com/intent/tweet?text=" + q(x_text) + "&url=" + q(page)),
        ("facebook", "Auf Facebook teilen", "https://www.facebook.com/sharer/sharer.php?u=" + q(page)),
        ("linkedin", "Auf LinkedIn teilen", "https://www.linkedin.com/sharing/share-offsite/?url=" + q(page)),
        ("whatsapp", "Per WhatsApp senden", "https://wa.me/?text=" + q(p["title"] + " " + page)),
        ("telegram", "Per Telegram senden", "https://t.me/share/url?url=" + q(page) + "&text=" + q(p["title"])),
        ("mail", "Per E-Mail senden", "mailto:?subject=" + q(p["title"]) + "&body=" + q(p["description"] + "\n\n" + page)),
    ]
    h = '<div class="sharebar" data-url="%s" data-story="%s"><span class="sharelab">Teilen</span>' % (esc(page), esc(json.dumps(story, ensure_ascii=False)))
    h += '<button type="button" class="sharebtn ig" id="igshare" title="Als Instagram-Story teilen" aria-label="Als Instagram-Story teilen">%s</button>' % ICONS["instagram"]
    for k, label, href in links:
        h += '<a class="sharebtn %s" href="%s" target="_blank" rel="noopener nofollow" title="%s" aria-label="%s">%s</a>' % (k, esc(href), label, label, ICONS[k])
    h += '<button type="button" class="sharebtn" id="cpshare" title="Link kopieren" aria-label="Link kopieren">%s</button>' % ICONS["link"]
    h += '<span class="sharemsg" id="igmsg" role="status"></span></div>\n'
    return h


SHARE_JS = r"""<script src="../../assets/story.js"></script>
<script src="../../assets/kurse.js"></script>
<script>(function(){var bar=document.querySelector(".sharebar");if(!bar)return;var m=document.getElementById("igmsg"),pg=bar.getAttribute("data-url"),S=JSON.parse(bar.getAttribute("data-story")||"{}");
document.getElementById("cpshare").onclick=async function(){try{await navigator.clipboard.writeText(pg);m.textContent="Link kopiert."}catch(e){m.textContent=pg}};
document.getElementById("igshare").onclick=function(){window.StoryShare(S,m)}})();</script>"""


def build_post(p, posts):
    slug = p["slug"]; depth = 2; pre = "../" * depth
    url = f"news/{slug}/"
    img = p.get("image")
    if not img:
        img = f"assets/magazin/{slug}.png"
        if not os.path.exists(img): make_cover(img, p["title"], p["category"])
    img = img.lstrip("/")
    img_url = absu(img)
    body = md_to_html(p["body_md"], depth)
    hits = glossar.analyse(p, body)                    # Stichworte -> Erklaerartikel
    body = glossar.verlinke(body, hits, pre)
    n_words = words(body); mins = max(1, round(n_words / 200))
    # FAQ aus Überschriften "## Häufige Fragen" mit ### Frage
    faq = []
    m = re.search(r"<h2[^>]*>\s*Häufige Fragen\s*</h2>(.*)$", body, re.S)
    if m:
        for q, a in re.findall(r"<h3[^>]*>(.*?)</h3>\s*(.*?)(?=<h3|$)", m.group(1), re.S):
            faq.append((re.sub(r"<[^>]+>", "", q).strip(), re.sub(r"<[^>]+>", " ", a).strip()))
    author = p["author"]
    ld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Start", "item": BASE},
            {"@type": "ListItem", "position": 2, "name": "News", "item": BASE + "news/"},
            {"@type": "ListItem", "position": 3, "name": p["title"], "item": BASE + url}]},
        {"@context": "https://schema.org", "@type": "NewsArticle", "headline": p["title"][:110], "description": p["description"],
         "inLanguage": "de", "datePublished": iso(p["dt"]), "dateModified": iso(p["upd"]), "mainEntityOfPage": BASE + url,
         "image": [img_url], "articleSection": p["category"], "wordCount": n_words,
         "author": {"@type": "Organization" if "redaktion" in author.lower() else "Person", "name": SITE if "redaktion" in author.lower() else author, **({"url": BASE + "ueber-uns/"} if "redaktion" in author.lower() else {}), **({"url": p["author_url"]} if p.get("author_url") else {})},
         "publisher": {"@type": "Organization", "name": SITE, "logo": {"@type": "ImageObject", "url": BASE + CFG["publisher_logo"]}}}]
    if faq:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})
    extra = '<meta property="article:published_time" content="%s">\n<meta property="article:modified_time" content="%s">\n<meta property="article:section" content="%s">\n' % (iso(p["dt"]), iso(p["upd"]), esc(p["category"]))
    extra += "".join('<script type="application/ld+json">%s</script>\n' % json.dumps(x, ensure_ascii=False) for x in ld)
    o = head(depth, p["title"], p["description"], url, "article", absu(make_share_card(p, slug, img)).replace("&", "&amp;"), extra) + nav_html(depth, "news") + "</nav></div></header>\n"
    o += f'<script src="{pre}assets/navigation.js"></script>\n<script src="{pre}assets/logos.js"></script>\n<main class="wrap"><article class="post">\n'
    o += f'<nav class="crumbs" aria-label="Brotkrumen"><a href="{pre}">Start</a> › <a href="{pre}news/">News</a> › <span aria-current="page">{esc(p["title"])}</span></nav>\n'
    o += f'<p class="kicker">{esc(p["category"])}</p>\n{logo_html(p)}{kurs_chip(p)}<p class="lead">{esc(p["description"])}</p>\n'
    upd = f' · Aktualisiert: <time datetime="{iso(p["upd"])}">{de_date(p["upd"])}</time>' if p["upd"].date() > p["dt"].date() else ""
    o += f'<p class="byline">{('<strong><a href="' + pre + 'ueber-uns/">Aus der Redaktion</a></strong>') if 'redaktion' in author.lower() else 'Von <strong>' + esc(author) + '</strong>'} · <time datetime="{iso(p["dt"])}">{de_dt(p["dt"])}</time>{upd} · {mins} Min. Lesezeit</p>\n'
    o += share_html(p, url, img if ext(img) else pre + img)
    alt = p.get("image_alt") or p["title"]
    cred = credit_html(p)
    cap = f'<figcaption>{cred}</figcaption>' if cred else ""
    kurz = p.get("typ") == "kurz"
    if not kurz or p.get("image"):
        o += (f'<figure class="cover kurzcover"><img src="{src(pre, img)}" alt="{esc(alt)}" loading="lazy">{cap}</figure>\n' if kurz else
              f'<figure class="cover"><img src="{src(pre, img)}" alt="{esc(alt)}" width="1200" height="675" fetchpriority="high">{cap}</figure>\n')
    o += body + "\n"
    if kurz and p.get("quelle_url", "").startswith("http"):
        o += (f'<p class="kurzquelle">Quelle: <a href="{esc(p["quelle_url"])}" rel="noopener nofollow" target="_blank">{esc(p.get("quelle_name") or "Originalmeldung des Unternehmens")}</a></p>\n')
    o += glossar.box(hits, pre)
    bio = p.get("author_bio") or 'Die Redaktion von Dividenden-Rechner.de schreibt über Dividendenaktien, Kennzahlen und Steuerthemen für Privatanleger. Die Rechner und Auswertungen auf der Seite entstehen im eigenen Haus.'
    o += f'<aside class="authorbox"><strong>{esc(author)}</strong><p>{esc(bio)}</p><p>{KURZ_HINWEIS if kurz else "Artikel können mit Unterstützung von KI entstehen. Jeder Beitrag wird manuell geprüft und geht erst danach online."} <a href="{pre}ueber-uns/">Mehr über uns</a></p></aside>\n'
    others = [x for x in posts if x["slug"] != slug and x.get("typ") != "kurz"][:3]
    if others:
        o += '<aside class="related"><h2>Weitere Artikel</h2><ul>\n' + "\n".join(f'<li><a href="{pre}news/{x["slug"]}/">{esc(x["title"])}</a></li>' for x in others) + "\n</ul></aside>\n"
    o += (f'<aside class="note" style="background:#f0fdf4;border-left-color:#10b981"><strong>Passende Werkzeuge:</strong> Prüfe Aktien im <a href="{pre}aktien/">Aktien-Hub</a>, '
          f'filtere mit dem <a href="{pre}screener/">Screener</a> oder rechne mit den <a href="{pre}">Rechnern</a>.</aside>\n')
    o += HINT + "\n</article></main>\n" + footer_html(depth) + "\n" + SHARE_JS + "\n</body>\n</html>\n"
    os.makedirs(f"news/{slug}", exist_ok=True)
    open(f"news/{slug}/index.html", "w", encoding="utf-8").write(o)
    p["img"] = img; p["html"] = body; p["mins"] = mins; p["glossar_hits"] = [{k: h[k] for k in ("id", "url", "title")} for h in hits]
    return p

def logo_is_light(path):
    """True, wenn das Logo fast nur aus hellen Pixeln besteht (z. B. weisses Logo): dann dunkle Plakette."""
    try:
        from PIL import Image
        im = Image.open(path).convert("RGBA").resize((48, 48))
        px = [p for p in im.getdata() if p[3] > 128]
        if not px: return False
        lum = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b, a in px) / len(px)
        return lum > 215
    except Exception:
        return False

def card_logo(x, pre):
    if x.get("kein_logo"): return ""
    """Logo-Plakette links oben im Titelbild der Magazinkarten (immer vorhanden: Datei, sonst Buchstabe).
    Stil steht zusaetzlich inline, damit es auch mit einer alten, zwischengespeicherten site.css richtig sitzt."""
    base = "position:absolute;left:12px;top:12px;width:52px;height:52px;box-sizing:border-box;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,.22);display:flex;align-items:center;justify-content:center;"
    lf = x.get("logo_file", "")
    if lf and os.path.exists(lf) and os.path.basename(lf).startswith("combo-"):
        return (f'<span class="mclogo combo" style="position:absolute;left:6px;top:6px;display:block;line-height:0;width:auto;height:auto;padding:0;background:none;box-shadow:none;border-radius:0"><img src="{pre}{esc(lf)}" alt="" height="64" loading="lazy" style="display:block;height:64px;width:auto;max-width:none"></span>')
    if lf and os.path.exists(lf):
        dark = logo_is_light(lf)
        return (f'<span class="mclogo{" dark" if dark else ""}" style="{base}padding:6px;background:{"#14202b" if dark else "#fff"}">'
                f'<img src="{pre}{esc(lf)}" alt="" width="40" height="40" loading="lazy" style="display:block;max-width:100%;max-height:100%;object-fit:contain"></span>')
    name = re.sub(r"[^A-Za-z0-9]", "", x.get("title", "?")) or "?"
    return f'<span class="mclogo mcmono" style="{base}background:#2f9e5b;color:#fff;font-weight:800;font-size:24px">{esc(name[0].upper())}</span>'

def mini_logo(x, pre):
    if x.get("kein_logo"): return ""
    """Kleines Logo fuer die Archivliste (ohne Titelbild)."""
    lf = x.get("logo_file", "")
    if lf and os.path.exists(lf):
        dark = logo_is_light(lf) and not os.path.basename(lf).startswith("combo-")
        cls = "arlogo combo" if os.path.basename(lf).startswith("combo-") else ("arlogo dark" if dark else "arlogo")
        return f'<span class="{cls}"><img src="{pre}{esc(lf)}" alt="" loading="lazy"></span>'
    name = re.sub(r"[^A-Za-z0-9]", "", x.get("title", "?")) or "?"
    return f'<span class="arlogo mono">{esc(name[0].upper())}</span>'

RUBRIKEN = [("Quartalszahlen & Berichte", {"Quartalszahlen", "Zahlen", "Jahresbericht", "Halbjahreszahlen"}), ("Dividende", {"Dividende"}), ("Aktienrückkauf", {"Aktienrückkauf"}),
            ("Übernahme", {"Übernahme"}), ("Management", {"Management"}), ("Ausblick", {"Ausblick"}), ("Recht & Regulierung", {"Recht & Regulierung"})]


def rubrik_of(cat):
    for n, cs in RUBRIKEN:
        if cat in cs: return n
    return "Weitere Meldungen"


def rubrik_html(posts, pre):
    """Filterleiste nach Rubrik (Schaltflaechen) mit eingebetteter Artikelliste; die Ergebnisse zeigt ein kleines Skript."""
    cnt = {}
    for x in posts: cnt[rubrik_of(x["category"])] = cnt.get(rubrik_of(x["category"]), 0) + 1
    names = [n for n, _ in RUBRIKEN if n in cnt] + (["Weitere Meldungen"] if "Weitere Meldungen" in cnt else [])
    data = [{"s": x["slug"], "t": x["title"], "r": rubrik_of(x["category"]), "c": x["category"], "d": de_dt_kurz(x["dt"]),
             "l": (pre + x["logo_file"]) if x.get("logo_file") and os.path.exists(x["logo_file"]) and not x["logo_file"].endswith(".mono.png") else ""} for x in posts]
    h = '<nav class="rubriken" aria-label="Nach Rubrik filtern"><button type="button" class="rb on" data-r="">Alle</button>'
    h += "".join('<button type="button" class="rb" data-r="%s">%s</button>' % (esc(n), esc(n)) for n in names) + "</nav>\n"
    h += '<div id="catres" hidden></div>\n<script type="application/json" id="magdata">%s</script>\n' % json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    h += """<script>(function(){var d=JSON.parse(document.getElementById("magdata").textContent),bs=document.querySelectorAll(".rb"),res=document.getElementById("catres"),mn;
function e(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function go(r,push){mn=document.getElementById("magmain");Array.prototype.forEach.call(bs,function(b){b.classList.toggle("on",b.getAttribute("data-r")===r)});
if(!r){res.hidden=true;mn.hidden=false;if(push)history.replaceState(null,"",location.pathname);return}
var l=d.filter(function(x){return x.r===r});mn.hidden=true;res.hidden=false;
res.innerHTML='<h2 class="mag-more-h">'+e(r)+'</h2><ul class="mag-archiv">'+l.map(function(x){return '<li><a href="'+e(x.s)+'/"><span class="arlogo">'+(x.l?'<img src="'+e(x.l)+'" alt="" loading="lazy">':e(x.t.charAt(0)))+'</span><span class="artx"><span class="kicker">'+e(x.c)+' · '+e(x.d)+'</span><strong>'+e(x.t)+'</strong></span></a></li>'}).join("")+'</ul>';
if(push)history.replaceState(null,"","#rubrik="+encodeURIComponent(r))}
Array.prototype.forEach.call(bs,function(b){b.onclick=function(){go(b.getAttribute("data-r"),true)}});
document.addEventListener("DOMContentLoaded",function(){var m=/#rubrik=([^&]+)/.exec(location.hash);if(m)go(decodeURIComponent(m[1]),false)})})();</script>
"""
    return h


def build_index(posts):
    depth = 1; pre = "../"; url = "news/"
    title = "News: Dividenden, Kennzahlen und Steuern erklärt"
    desc = "Analysen, Erklärstücke und Einordnungen zu Dividendenaktien, Kennzahlen, Quellensteuer und Depot, geschrieben für Privatanleger in Deutschland."
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc, "url": BASE + url, "inLanguage": "de",
          "hasPart": [{"@type": "Article", "headline": x["title"], "url": f'{BASE}news/{x["slug"]}/', "datePublished": iso(x["dt"])} for x in posts[:20]]}
    extra = '<script type="application/ld+json">%s</script>\n' % json.dumps(ld, ensure_ascii=False)
    default_img = absu(posts[0]["img"]) if posts else BASE + "assets/logo.png"
    o = head(depth, title, desc, url, "website", default_img, extra) + nav_html(depth, "news") + "</nav></div></header>\n"
    o += f'<script src="{pre}assets/navigation.js"></script>\n<script src="{pre}assets/logos.js"></script>\n<main class="wrap">\n'
    o += f'<nav class="crumbs" aria-label="Brotkrumen"><a href="{pre}">Start</a> › <span aria-current="page">News</span></nav>\n<h1>News</h1>\n'
    # Aufmacher: Standard ist der neueste Artikel; mit "aufmacher: ja" im Kopfbereich wird ein juengerer Artikel (max. 3 Tage hinter dem neuesten) zum Hauptthema
    longp = [x for x in posts if x.get("typ") != "kurz"] or posts
    hero = longp[0]
    for x in longp:
        if x.get("aufmacher", "").lower() in ("ja", "true", "1", "yes") and (posts[0]["dt"] - x["dt"]).days <= 3:
            hero = x; break
    kurz_posts = [x for x in posts if x.get("typ") == "kurz"]
    rest = [x for x in posts if x is not hero and x.get("typ") != "kurz"]
    side, grid, archiv = rest[:4], rest[4:12], rest[12:]
    o += rubrik_html(posts, pre) + '<div id="magmain">\n'
    o += (f'<section class="mag-top" aria-label="Thema des Tages"><a class="mag-hero" href="{hero["slug"]}/"><div class="mcwrap" style="position:relative;margin:0"><img class="mcover" src="{src(pre, hero["img"])}" alt="" width="1200" height="675" fetchpriority="high">{card_logo(hero, pre)}</div>'
          f'<div class="mag-hero-body"><p class="kicker"><span class="mag-badge">Thema des Tages</span> {esc(hero["category"])} · {de_dt_kurz(hero["dt"])}</p><h2>{esc(hero["title"])}</h2><p class="mag-lead">{esc(hero["description"])}</p><span class="mag-more">Artikel lesen →</span></div></a>\n')
    if side:
        o += '<aside class="mag-side" aria-label="Weitere aktuelle Artikel"><h2>Außerdem aktuell</h2><ul>\n'
        for x in side:
            o += (f'<li><a href="{x["slug"]}/"><span class="mag-thumb"><img src="{src(pre, x["img"])}" alt="" width="120" height="68" loading="lazy">{card_logo(x, pre)}<span class="kicker"><b>{esc(x["category"])}</b>{de_dt_kurz(x["dt"])}</span></span><strong>{esc(x["title"])}</strong></a></li>\n')
        o += '</ul></aside>\n'
    o += '</section>\n'
    if kurz_posts:
        o += '<h2 class="mag-more-h">Kurzmeldungen</h2>\n<ul class="mag-archiv mag-kurz">\n'
        for x in kurz_posts[:16]:
            o += (f'<li><a href="{x["slug"]}/">{mini_logo(x, pre)}<span class="artx"><span class="kicker">{esc(x["category"])} · {de_dt_kurz(x["dt"])}</span>'
                  f'<strong>{esc(x["title"])}</strong></span></a></li>\n')
        o += '</ul>\n'
    if grid:
        o += '<h2 class="mag-more-h">Weitere Artikel</h2>\n<div class="cards magcards">\n'
        for x in grid:
            o += (f'<a class="card" href="{x["slug"]}/"><div class="mcwrap" style="position:relative;margin:0"><img class="mcover" src="{src(pre, x["img"])}" alt="" width="1200" height="675" loading="lazy">{card_logo(x, pre)}</div>'
                  f'<p class="kicker">{esc(x["category"])} · {de_dt_kurz(x["dt"])}</p><h3>{esc(x["title"])}</h3><p>{esc(x["description"])}</p></a>\n')
    if grid: o += '</div>\n'
    if archiv:
        o += '<h2 class="mag-more-h">Älter</h2>\n<ul class="mag-archiv">\n'
        for x in archiv:
            o += (f'<li><a href="{x["slug"]}/">{mini_logo(x, pre)}<span class="artx"><span class="kicker">{esc(x["category"])} · {de_dt_kurz(x["dt"])}</span>'
                  f'<strong>{esc(x["title"])}</strong></span></a></li>\n')
        o += '</ul>\n'
    o += '</div>\n'
    o += ('<section class="ek-embed" aria-label="Unternehmensmeldungen"><h2 class="mag-more-h">Unternehmensmeldungen</h2>\n'
          '<p class="meta">Aktuelle Meldungen und Investorenberichte aus den Investor-Relations-Feeds. <a href="../unternehmensmeldungen/">Seite einzeln öffnen</a></p>\n'
          '<iframe src="../unternehmensmeldungen/?embed=1" title="Unternehmensmeldungen" loading="lazy" style="width:100%;height:900px;border:1px solid var(--line);border-radius:12px;background:#fff"></iframe></section>\n')
    o += '<p class="meta"><a href="feed.xml">RSS-Feed abonnieren</a></p>\n' + HINT + "\n</main>\n" + footer_html(depth) + "\n</body>\n</html>\n"
    open("news/index.html", "w", encoding="utf-8").write(o)

def build_feed(posts):
    now = email.utils.format_datetime(datetime.datetime.now(datetime.timezone.utc))
    items = ""
    for x in posts[:30]:
        link = f'{BASE}news/{x["slug"]}/'
        content = re.sub(r'(href|src)="(\.\./)+', lambda m: f'{m.group(1)}="{BASE}', x["html"])
        pub = email.utils.format_datetime(x["dt"].replace(tzinfo=ZoneInfo("Europe/Berlin")))
        items += (f'<item><title>{esc(x["title"])}</title><link>{link}</link><guid isPermaLink="true">{link}</guid><pubDate>{pub}</pubDate>'
                  f'<category>{esc(x["category"])}</category><dc:creator>{esc(x["author"])}</dc:creator><description>{esc(x["description"])}</description>'
                  f'<enclosure url="{absu(x["img"]).replace("&", "&amp;")}" type="image/{"png" if x["img"].lower().split("?")[0].endswith("png") else "jpeg"}" length="0"/>'
                  f'<content:encoded><![CDATA[{content}]]></content:encoded></item>\n')
    feed = (f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            f'<channel><title>{esc(SITE)}: News</title><link>{BASE}news/</link><description>Dividenden, Kennzahlen und Steuern erklärt</description><language>de-DE</language>'
            f'<lastBuildDate>{now}</lastBuildDate><atom:link href="{BASE}news/feed.xml" rel="self" type="application/rss+xml"/>\n{items}</channel></rss>\n')
    open("news/feed.xml", "w", encoding="utf-8").write(feed)

def patch_sitemap(posts):
    s = open("sitemap.xml", encoding="utf-8").read()
    s = re.sub(r"<url><loc>%snews/[^<]*</loc>.*?</url>\n?" % re.escape(BASE), "", s)
    add = f"<url><loc>{BASE}news/</loc><lastmod>{posts[0]['upd'].date()}</lastmod><priority>0.8</priority></url>\n" if posts else ""
    for x in posts:
        add += f"<url><loc>{BASE}news/{x['slug']}/</loc><lastmod>{x['upd'].date()}</lastmod><priority>0.8</priority></url>\n"
    s = s.replace("</urlset>", add + "</urlset>")
    open("sitemap.xml", "w", encoding="utf-8").write(s)

def patch_llms(posts):
    s = open("llms.txt", encoding="utf-8").read()
    s = re.sub(r"- \[[^\]]*\]\(%snews/[^)]*\)[^\n]*\n" % re.escape(BASE), "", s)
    add = "".join(f"- [{x['title']}]({BASE}news/{x['slug']}/): {x['description']}\n" for x in posts)
    if posts: add = f"- [News: Artikel zu Dividenden, Kennzahlen und Steuern]({BASE}news/)\n" + add
    s = s.replace("\n## Hinweis", "\n" + add + "\n## Hinweis", 1) if "\n## Hinweis" in s else s + "\n" + add
    open("llms.txt", "w", encoding="utf-8").write(s)

def patch_home(posts):
    p = "index.html"; s = open(p, encoding="utf-8").read()
    block = ""
    if posts:
        block = ('<section class="home-mag" id="magazin"><h2>Neu in den News</h2><p class="sub">Quartalszahlen verständlich erklärt, mit Kurzfassung in drei Punkten.</p>\n<div class="cards magcards">\n')
        for x in posts[:3]:
            block += (f'<a class="card" href="news/{x["slug"]}/"><div class="mcwrap" style="position:relative;margin:0"><img class="mcover" src="{src("", x["img"])}" alt="" width="1200" height="675" loading="lazy">{card_logo(x, "")}</div>'
                      f'<p class="kicker">{esc(x["category"])} · {de_dt_kurz(x["dt"])}</p><h3>{esc(x["title"])}</h3></a>\n')
        block += '</div>\n<p class="more"><a href="news/">Alle Artikel in den News →</a></p></section>\n'
    mk = "<!-- magazin-neu -->"
    if mk not in s:
        s = s.replace('<section class="home-more">', mk + "\n" + mk.replace("neu", "ende") + '\n<section class="home-more">', 1)
    s = re.sub(r"<!-- magazin-neu -->.*?<!-- magazin-ende -->", lambda m: mk + "\n" + block + "<!-- magazin-ende -->", s, flags=re.S)
    css = ('<style id="mag-css">.home-mag .mcover{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}'
           '.home-mag .card{padding:0;overflow:hidden}.home-mag .card>*:not(.mcover){margin-left:16px;margin-right:16px}'
           '.home-mag .kicker{margin-top:12px;margin-bottom:4px;font-size:13px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#1a7a45}'
           '.home-mag .card p:last-child{margin-bottom:16px}</style>')
    if 'id="mag-css"' not in s: s = s.replace("</head>", css + "\n</head>", 1)
    open(p, "w", encoding="utf-8").write(s)

MAGCSS = ('<style id="mag-css">.home-mag .magcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}'
          '.home-mag .mcover{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}'
          '.home-mag .card{display:block;padding:0;overflow:hidden;text-decoration:none;color:inherit;border:1px solid #e3e8ee;border-radius:12px;background:#fff}'
          '.home-mag .card>*:not(.mcover){margin-left:16px;margin-right:16px}'
          '.home-mag .card h3{margin-top:4px;font-size:18px;line-height:1.3}.home-mag .card p{font-size:15px;color:#3d4955}'
          '.home-mag .kicker{margin-top:12px;margin-bottom:4px;font-size:13px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#1a7a45}'
          '.home-mag .card p:last-child{margin-bottom:16px}</style>')

def write_mag_index(posts):
    """data/magazin.json: damit die News-Seite zu Meldungen auf passende Artikel verlinken kann."""
    items = [{"slug": x["slug"], "title": x["title"], "sym": re.sub(r"[^A-Za-z0-9.\-]", "", x.get("logo_symbol", "")), "date": iso(x["dt"])} for x in posts]
    os.makedirs("data", exist_ok=True)
    open("data/magazin.json", "w", encoding="utf-8").write(json.dumps({"items": items}, ensure_ascii=False, indent=1))


def patch_news(posts):
    """Neue Magazin-Artikel ganz oben auf der News-Seite."""
    p = "unternehmensmeldungen/index.html"
    if not os.path.exists(p): return
    s = open(p, encoding="utf-8").read()
    block = ""   # Magazin-Teaser stehen auf Startseite und Magazin, nicht auf der News-Seite
    mk = "<!-- magazin-neu -->"
    if mk not in s:
        s = s.replace('<div id="days"', mk + "\n" + mk.replace("neu", "ende") + '\n<div id="days"', 1)
    s = re.sub(r"<!-- magazin-neu -->.*?<!-- magazin-ende -->", lambda m: mk + "\n" + block + "<!-- magazin-ende -->", s, flags=re.S)
    open(p, "w", encoding="utf-8").write(s)

def patch_nav_everywhere(has_posts):
    """Magazin-Link in Kopf- und Fußzeile aller Seiten ein- bzw. austragen."""
    for f in glob.glob("**/*.html", recursive=True):
        if f.startswith(("news/", "magazin/", "node_modules/")) or f == "404.html": continue
        s = open(f, encoding="utf-8").read(); o = s
        m = re.search(r'<a href="((?:\.\./)*)screener/"[^>]*>Screener</a>', s)
        if not m: continue
        pre = m.group(1)
        link = f'<a href="{pre}news/">News</a>'
        s = s.replace(link, "")
        if has_posts:
            if re.search(r'<a href="%searnings/"[^>]*>Earnings</a>' % re.escape(pre), s):
                s = re.sub(r'(<a href="%searnings/"[^>]*>Earnings</a>)' % re.escape(pre), lambda mm: link + mm.group(1), s, count=1)
            else:
                s = re.sub(r'(<a href="%sscreener/"[^>]*>Screener</a>)' % re.escape(pre), lambda mm: link + mm.group(1), s, count=1)
        if s != o: open(f, "w", encoding="utf-8").write(s)

REPO = "dividenden-rechner/aktien-hub"

def write_overview(allp):
    """Uebersicht aller Artikel (Entwuerfe zuerst, neueste oben) in content/magazin/README.md, mit Links zum Bearbeiten."""
    path = "content/magazin/README.md"
    if not os.path.exists(path): return
    def rows(items):
        out = ["| Datum | Titel | Datei |", "|---|---|---|"]
        for x in items:
            link = f"https://github.com/{REPO}/edit/main/content/magazin/{x['file']}"
            out.append(f"| {x['dt'].strftime('%d.%m.%Y %H:%M')} | {x['title'].replace('|', '/')} | [{x['file']}]({link}) |")
        return "\n".join(out)
    drafts = sorted([x for x in allp if x["draft"]], key=lambda x: (x["dt"], x["slug"]), reverse=True)
    live = sorted([x for x in allp if not x["draft"]], key=lambda x: (x["dt"], x["slug"]), reverse=True)
    blk = "<!-- uebersicht-start -->\n## Übersicht (wird automatisch erstellt, neueste zuerst)\n\n"
    blk += f"### Zur Freigabe: Entwürfe ({len(drafts)})\n\nDatei anklicken, dann Stift-Symbol: Zeile `draft: true` löschen und speichern, dann geht der Artikel online.\n\n" + (rows(drafts) if drafts else "_Keine Entwürfe._") + "\n\n"
    blk += f"### Online ({len(live)})\n\n" + (rows(live) if live else "_Noch nichts online._") + "\n<!-- uebersicht-ende -->"
    s = open(path, encoding="utf-8").read()
    if "<!-- uebersicht-start -->" in s:
        s = re.sub(r"<!-- uebersicht-start -->.*?<!-- uebersicht-ende -->", lambda m: blk, s, flags=re.S)
    else:
        first, _, rest = s.partition("\n")
        s = first + "\n\n" + blk + "\n" + rest
    if s != open(path, encoding="utf-8").read():
        open(path, "w", encoding="utf-8").write(s)

def write_redirects(posts):
    """Alte Adressen /magazin/... -> /news/... (GitHub Pages kennt keine 301: Meta-Refresh mit Canonical, noindex)."""
    import shutil
    if os.path.isdir("magazin"): shutil.rmtree("magazin")
    def stub(path, target, depth):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        t = BASE + target
        open(path, "w", encoding="utf-8").write(
            f'<!DOCTYPE html>\n<html lang="de"><head><meta charset="utf-8"><title>Weitergeleitet</title><meta name="robots" content="noindex">'
            f'<link rel="canonical" href="{t}"><meta http-equiv="refresh" content="0; url={"../" * depth}{target}">'
            f'<script>location.replace("{"../" * depth}{target}"+location.search+location.hash)</script></head>'
            f'<body><p>Diese Seite ist umgezogen: <a href="{"../" * depth}{target}">{t}</a></p></body></html>\n')
    stub("magazin/index.html", "news/", 1)
    for x in posts:
        stub(f"magazin/{x['slug']}/index.html", f"news/{x['slug']}/", 2)
    if os.path.exists("news/feed.xml"):
        shutil.copy("news/feed.xml", "magazin/feed.xml")

def main():
    build_wissen.run(sys.modules[__name__])        # Wissensartikel zuerst: Magazin-Verlinkung und Rueck-Links brauchen die fertigen Seiten
    posts, allp = [], []
    import artikel; artikel.sortiere()
    for f in sorted(artikel.all_md()):
        p = read_post(f); allp.append(p)
        if p["draft"]: print("Entwurf übersprungen:", f); continue
        if p["dt"] > datetime.datetime.now() + datetime.timedelta(days=1): print("Zukunftsdatum übersprungen:", f); continue
        posts.append(p)
    posts.sort(key=lambda x: (x["dt"], x["upd"], x["slug"]), reverse=True)
    for x in glob.glob("news/*/"):
        if os.path.basename(os.path.normpath(x)) not in [p["slug"] for p in posts]:
            import shutil; shutil.rmtree(x)
    posts = [build_post(p, posts) for p in posts]
    if posts:
        build_index(posts); build_feed(posts)
    else:
        for f in ("news/index.html", "news/feed.xml"):
            if os.path.exists(f): os.remove(f)
    longp = [x for x in posts if x.get("typ") != "kurz"]
    glossar.patch_erklaerseiten(longp)
    patch_sitemap(posts); patch_llms(posts); patch_home(longp); patch_news(posts); write_mag_index(posts); patch_nav_everywhere(bool(posts))
    write_overview(allp)
    write_redirects(posts)
    print(f"{len(posts)} Artikel gebaut")

if __name__ == "__main__":
    main()
