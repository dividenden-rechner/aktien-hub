#!/usr/bin/env python3
"""Baut das Magazin: Markdown-Dateien in content/magazin/*.md -> HTML-Seiten, Übersicht, RSS-Feed, Sitemap, llms.txt,
Startseiten-Teaser und Navigationseintrag. Aufruf im Repo-Hauptordner:  python3 tools/build_magazin.py
Benötigt: pip install markdown pillow"""
import re, os, sys, json, html, glob, datetime, email.utils
from zoneinfo import ZoneInfo
import markdown
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
CFG = json.load(open("tools/site.json", encoding="utf-8"))
BASE = CFG["base"] if CFG["base"].endswith("/") else CFG["base"] + "/"
SITE = CFG["name"]
esc = lambda s: html.escape(str(s), quote=True)
NAV = [("rechner", "", "Rechner"), ("aktien", "aktien/", "Aktien"), ("depot", "depot/", "Depot"), ("news", "news/", "News"),
       ("earnings", "earnings/", "Earnings"), ("screener", "screener/", "Screener"), ("magazin", "magazin/", "Magazin"),
       ("einfuehrung", "einfuehrung/", "Einführung"), ("grundlagen", "grundlagen/", "Grundlagen"),
       ("fortgeschrittene", "fortgeschrittene/", "Fortgeschrittene")]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
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
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}(-\d{4})?-", "", os.path.splitext(os.path.basename(path))[0])   # Datum vor dem Dateinamen gehoert nicht zur Adresse
    meta["slug"] = meta.get("slug") or re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    meta["file"] = os.path.basename(path)
    meta["dt"] = parse_date(meta["date"])
    meta["upd"] = parse_date(meta["updated"]) if meta.get("updated") else meta["dt"]
    meta["body_md"] = fix_kurz(m.group(2).strip())
    meta["draft"] = meta.get("draft", "").lower() in ("true", "ja", "1", "yes")
    meta["author"] = meta.get("author") or CFG["default_author"]
    meta["category"] = meta.get("category") or "Analyse"
    return meta

def md_to_html(md_text, depth):
    pre = "../" * depth
    md_text = re.sub(r"<!--\s*PRÜFEN.*?-->\s*", "", md_text, flags=re.S)   # Redaktionshinweise des IR-Agenten nie veröffentlichen
    md = markdown.Markdown(extensions=["tables", "sane_lists", "admonition", "attr_list", "toc"], extension_configs={"toc": {"permalink": False}})
    h = md.convert(md_text)
    h = re.sub(r'(href|src)="/(?!/)', lambda m: f'{m.group(1)}="{pre}', h)       # /pfad/ -> relativ
    h = re.sub(r"<table>", '<div class="tablewrap"><table>', h); h = h.replace("</table>", "</table></div>")
    h = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" rel="noopener"', h)
    return h

def words(s): return len(re.sub(r"<[^>]+>", " ", s).split())

def nav_html(depth, cur, with_mag=True):
    p = "../" * depth
    return "".join(f'<a href="{p}{u}"{" aria-current=\"page\"" if k == cur else ""}>{n}</a>' for k, u, n in NAV if with_mag or k != "magazin")

def footer_html(depth):
    p = "../" * depth
    l = "".join(f'<a href="{p}{u}">{n}</a>' for k, u, n in NAV if k != "earnings")
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
<link rel="alternate" type="application/rss+xml" title="{esc(SITE)}: Magazin" href="{p}magazin/feed.xml">
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
    for f in ("/usr/share/fonts/opentype/inter/Inter-Bold.otf" if bold else "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
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

def logo_html(p):
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

def build_post(p, posts):
    slug = p["slug"]; depth = 2; pre = "../" * depth
    url = f"magazin/{slug}/"
    img = p.get("image")
    if not img:
        img = f"assets/magazin/{slug}.png"
        if not os.path.exists(img): make_cover(img, p["title"], p["category"])
    img = img.lstrip("/")
    img_url = BASE + img
    body = md_to_html(p["body_md"], depth)
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
            {"@type": "ListItem", "position": 2, "name": "Magazin", "item": BASE + "magazin/"},
            {"@type": "ListItem", "position": 3, "name": p["title"], "item": BASE + url}]},
        {"@context": "https://schema.org", "@type": "NewsArticle", "headline": p["title"][:110], "description": p["description"],
         "inLanguage": "de", "datePublished": iso(p["dt"]), "dateModified": iso(p["upd"]), "mainEntityOfPage": BASE + url,
         "image": [img_url], "articleSection": p["category"], "wordCount": n_words,
         "author": {"@type": "Organization" if "redaktion" in author.lower() else "Person", "name": author, **({"url": BASE + "ueber-uns/"} if "redaktion" in author.lower() else {}), **({"url": p["author_url"]} if p.get("author_url") else {})},
         "publisher": {"@type": "Organization", "name": SITE, "logo": {"@type": "ImageObject", "url": BASE + CFG["publisher_logo"]}}}]
    if faq:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})
    extra = '<meta property="article:published_time" content="%s">\n<meta property="article:modified_time" content="%s">\n<meta property="article:section" content="%s">\n' % (iso(p["dt"]), iso(p["upd"]), esc(p["category"]))
    extra += "".join('<script type="application/ld+json">%s</script>\n' % json.dumps(x, ensure_ascii=False) for x in ld)
    o = head(depth, p["title"], p["description"], url, "article", img_url, extra) + nav_html(depth, "magazin") + "</nav></div></header>\n"
    o += f'<script src="{pre}assets/navigation.js"></script>\n<script src="{pre}assets/logos.js"></script>\n<main class="wrap"><article class="post">\n'
    o += f'<nav class="crumbs" aria-label="Brotkrumen"><a href="{pre}">Start</a> › <a href="{pre}magazin/">Magazin</a> › <span aria-current="page">{esc(p["title"])}</span></nav>\n'
    o += f'<p class="kicker">{esc(p["category"])}</p>\n{logo_html(p)}<p class="lead">{esc(p["description"])}</p>\n'
    upd = f' · Aktualisiert: <time datetime="{iso(p["upd"])}">{de_date(p["upd"])}</time>' if p["upd"].date() > p["dt"].date() else ""
    o += f'<p class="byline">Von <strong>{esc(author)}</strong> · <time datetime="{iso(p["dt"])}">{de_dt(p["dt"])}</time>{upd} · {mins} Min. Lesezeit</p>\n'
    alt = p.get("image_alt") or p["title"]
    cred = p.get("image_credit") or ""
    if cred and p.get("image_source", "").startswith("http"):
        cred = f'<a href="{esc(p["image_source"])}" rel="noopener nofollow" target="_blank">{esc(cred)}</a>'
    else:
        cred = esc(cred)
    cap = f'<figcaption>{cred}</figcaption>' if cred else ""
    o += f'<figure class="cover"><img src="{pre}{img}" alt="{esc(alt)}" width="1200" height="675" fetchpriority="high">{cap}</figure>\n'
    o += body + "\n"
    bio = p.get("author_bio") or 'Das Redaktions-Team von Dividenden-Rechner.de schreibt über Dividendenaktien, Kennzahlen und Steuerthemen für Privatanleger. Die Rechner und Auswertungen auf der Seite entstehen im eigenen Haus.'
    o += f'<aside class="authorbox"><strong>{esc(author)}</strong><p>{esc(bio)}</p><p>Artikel können mit Unterstützung von KI entstehen. Jeder Beitrag wird manuell geprüft und geht erst danach online. <a href="{pre}ueber-uns/">Mehr über uns</a></p></aside>\n'
    others = [x for x in posts if x["slug"] != slug][:3]
    if others:
        o += '<aside class="related"><h2>Weitere Artikel</h2><ul>\n' + "\n".join(f'<li><a href="{pre}magazin/{x["slug"]}/">{esc(x["title"])}</a></li>' for x in others) + "\n</ul></aside>\n"
    o += (f'<aside class="note" style="background:#f0fdf4;border-left-color:#10b981"><strong>Passende Werkzeuge:</strong> Prüfe Aktien im <a href="{pre}aktien/">Aktien-Hub</a>, '
          f'filtere mit dem <a href="{pre}screener/">Screener</a> oder rechne mit den <a href="{pre}">Rechnern</a>.</aside>\n')
    o += HINT + "\n</article></main>\n" + footer_html(depth) + "\n</body>\n</html>\n"
    os.makedirs(f"magazin/{slug}", exist_ok=True)
    open(f"magazin/{slug}/index.html", "w", encoding="utf-8").write(o)
    p["img"] = img; p["html"] = body; p["mins"] = mins
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

def build_index(posts):
    depth = 1; pre = "../"; url = "magazin/"
    title = "Magazin: Dividenden, Kennzahlen und Steuern erklärt"
    desc = "Analysen, Erklärstücke und Einordnungen zu Dividendenaktien, Kennzahlen, Quellensteuer und Depot, geschrieben für Privatanleger in Deutschland."
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc, "url": BASE + url, "inLanguage": "de",
          "hasPart": [{"@type": "Article", "headline": x["title"], "url": f'{BASE}magazin/{x["slug"]}/', "datePublished": iso(x["dt"])} for x in posts[:20]]}
    extra = '<script type="application/ld+json">%s</script>\n' % json.dumps(ld, ensure_ascii=False)
    default_img = BASE + (posts[0]["img"] if posts else "assets/logo.png")
    o = head(depth, title, desc, url, "website", default_img, extra) + nav_html(depth, "magazin") + "</nav></div></header>\n"
    o += f'<script src="{pre}assets/navigation.js"></script>\n<script src="{pre}assets/logos.js"></script>\n<main class="wrap">\n'
    o += f'<nav class="crumbs" aria-label="Brotkrumen"><a href="{pre}">Start</a> › <span aria-current="page">Magazin</span></nav>\n<h1>Magazin</h1>\n<p class="lead">{esc(desc)}</p>\n<div class="cards magcards">\n'
    for x in posts:
        o += (f'<a class="card" href="{x["slug"]}/"><div class="mcwrap" style="position:relative;margin:0"><img class="mcover" src="{pre}{x["img"]}" alt="" width="1200" height="675" loading="lazy">{card_logo(x, pre)}</div>'
              f'<p class="kicker">{esc(x["category"])} · {de_dt_kurz(x["dt"])}</p><h3>{esc(x["title"])}</h3><p>{esc(x["description"])}</p></a>\n')
    o += '</div>\n<p class="meta"><a href="feed.xml">RSS-Feed abonnieren</a></p>\n' + HINT + "\n</main>\n" + footer_html(depth) + "\n</body>\n</html>\n"
    open("magazin/index.html", "w", encoding="utf-8").write(o)

def build_feed(posts):
    now = email.utils.format_datetime(datetime.datetime.now(datetime.timezone.utc))
    items = ""
    for x in posts[:30]:
        link = f'{BASE}magazin/{x["slug"]}/'
        content = re.sub(r'(href|src)="(\.\./)+', lambda m: f'{m.group(1)}="{BASE}', x["html"])
        pub = email.utils.format_datetime(x["dt"].replace(tzinfo=ZoneInfo("Europe/Berlin")))
        items += (f'<item><title>{esc(x["title"])}</title><link>{link}</link><guid isPermaLink="true">{link}</guid><pubDate>{pub}</pubDate>'
                  f'<category>{esc(x["category"])}</category><dc:creator>{esc(x["author"])}</dc:creator><description>{esc(x["description"])}</description>'
                  f'<enclosure url="{BASE}{x["img"]}" type="image/{"jpeg" if x["img"].lower().endswith(("jpg","jpeg")) else "png"}" length="0"/>'
                  f'<content:encoded><![CDATA[{content}]]></content:encoded></item>\n')
    feed = (f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            f'<channel><title>{esc(SITE)}: Magazin</title><link>{BASE}magazin/</link><description>Dividenden, Kennzahlen und Steuern erklärt</description><language>de-DE</language>'
            f'<lastBuildDate>{now}</lastBuildDate><atom:link href="{BASE}magazin/feed.xml" rel="self" type="application/rss+xml"/>\n{items}</channel></rss>\n')
    open("magazin/feed.xml", "w", encoding="utf-8").write(feed)

def patch_sitemap(posts):
    s = open("sitemap.xml", encoding="utf-8").read()
    s = re.sub(r"<url><loc>%smagazin/[^<]*</loc>.*?</url>\n?" % re.escape(BASE), "", s)
    add = f"<url><loc>{BASE}magazin/</loc><lastmod>{posts[0]['upd'].date()}</lastmod><priority>0.8</priority></url>\n" if posts else ""
    for x in posts:
        add += f"<url><loc>{BASE}magazin/{x['slug']}/</loc><lastmod>{x['upd'].date()}</lastmod><priority>0.8</priority></url>\n"
    s = s.replace("</urlset>", add + "</urlset>")
    open("sitemap.xml", "w", encoding="utf-8").write(s)

def patch_llms(posts):
    s = open("llms.txt", encoding="utf-8").read()
    s = re.sub(r"- \[[^\]]*\]\(%smagazin/[^)]*\)[^\n]*\n" % re.escape(BASE), "", s)
    add = "".join(f"- [{x['title']}]({BASE}magazin/{x['slug']}/): {x['description']}\n" for x in posts)
    if posts: add = f"- [Magazin: Artikel zu Dividenden, Kennzahlen und Steuern]({BASE}magazin/)\n" + add
    s = s.replace("\n## Hinweis", "\n" + add + "\n## Hinweis", 1) if "\n## Hinweis" in s else s + "\n" + add
    open("llms.txt", "w", encoding="utf-8").write(s)

def patch_home(posts):
    p = "index.html"; s = open(p, encoding="utf-8").read()
    block = ""
    if posts:
        block = ('<section class="home-mag" id="magazin"><h2>Neu im Magazin</h2><p class="sub">Quartalszahlen verständlich erklärt, mit Kurzfassung in drei Punkten.</p>\n<div class="cards magcards">\n')
        for x in posts[:3]:
            block += (f'<a class="card" href="magazin/{x["slug"]}/"><div class="mcwrap" style="position:relative;margin:0"><img class="mcover" src="{x["img"]}" alt="" width="1200" height="675" loading="lazy">{card_logo(x, "")}</div>'
                      f'<p class="kicker">{esc(x["category"])} · {de_dt_kurz(x["dt"])}</p><h3>{esc(x["title"])}</h3></a>\n')
        block += '</div>\n<p class="more"><a href="magazin/">Alle Artikel im Magazin →</a></p></section>\n'
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
    p = "news/index.html"
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
        if f.startswith(("magazin/", "node_modules/")) or f == "404.html": continue
        s = open(f, encoding="utf-8").read(); o = s
        m = re.search(r'<a href="((?:\.\./)*)screener/">Screener</a>', s)
        if not m: continue
        pre = m.group(1)
        link = f'<a href="{pre}magazin/">Magazin</a>'
        s = s.replace(link, "")
        if has_posts:
            s = s.replace(f'<a href="{pre}screener/">Screener</a>', f'<a href="{pre}screener/">Screener</a>{link}', 1)
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

def main():
    posts, allp = [], []
    for f in sorted(glob.glob("content/magazin/*.md")):
        if os.path.basename(f).startswith(("_", "README")): continue
        p = read_post(f); allp.append(p)
        if p["draft"]: print("Entwurf übersprungen:", f); continue
        if p["dt"] > datetime.datetime.now() + datetime.timedelta(days=1): print("Zukunftsdatum übersprungen:", f); continue
        posts.append(p)
    posts.sort(key=lambda x: (x["dt"], x["upd"], x["slug"]), reverse=True)
    for x in glob.glob("magazin/*/"):
        if os.path.basename(os.path.normpath(x)) not in [p["slug"] for p in posts]:
            import shutil; shutil.rmtree(x)
    posts = [build_post(p, posts) for p in posts]
    if posts:
        build_index(posts); build_feed(posts)
    else:
        for f in ("magazin/index.html", "magazin/feed.xml"):
            if os.path.exists(f): os.remove(f)
    patch_sitemap(posts); patch_llms(posts); patch_home(posts); patch_news(posts); write_mag_index(posts); patch_nav_everywhere(bool(posts))
    write_overview(allp)
    print(f"{len(posts)} Artikel gebaut")

if __name__ == "__main__":
    main()
