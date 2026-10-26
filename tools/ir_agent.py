#!/usr/bin/env python3
"""IR-Agent: Quartalsbericht -> Kennzahlen (JSON) -> Grafik (PNG) + Aufmacherfoto + Artikelentwurf (Markdown).

Aufruf:
  python3 tools/ir_agent.py --ticker KO                         # US-Titel: Bericht selbst von der SEC holen
  python3 tools/ir_agent.py content/ir-inbox/bericht.pdf        # eigene PDF
  python3 tools/ir_agent.py bericht.pdf --mock antwort.json     # Test ohne API (fertige Modell-Antwort)

Der Entwurf landet mit `draft: true` in content/magazin/. Nichts wird veroeffentlicht,
bevor du `draft: true` entfernst. Zahlen werden gegen den Berichtstext geprueft.
"""
import argparse, base64, html, json, os, re, subprocess, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import date, datetime
from html.parser import HTMLParser
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "tools", "ir_config.json"), encoding="utf-8"))
MODEL = os.environ.get("GEMINI_MODEL") or CFG.get("model", "gemini-2.5-flash")

NUM = {"type": "NUMBER"}
SCHEMA = {   # Aufruf 1: Zahlen aus dem Bericht
    "type": "OBJECT",
    "required": ["company", "period", "report_date", "kpis", "chart"],
    "properties": {
        "company": {"type": "STRING"}, "ticker": {"type": "STRING"},
        "period": {"type": "STRING", "description": "z. B. Q2 2026"},
        "report_date": {"type": "STRING", "description": "YYYY-MM-DD"},
        "website_domain": {"type": "STRING", "description": "Domain der Unternehmenswebsite, nur wenn im Bericht genannt, z. B. verizon.com"},
        "ceo_quote": {"type": "OBJECT", "description": "Ein aussagekraeftiges, woertliches Zitat des CEO oder CFO aus dem Bericht",
            "properties": {"text_original": {"type": "STRING", "description": "Exakter Wortlaut wie im Bericht, ohne Auslassungen"},
                           "text_de": {"type": "STRING", "description": "Deutsche Uebersetzung des Zitats"},
                           "speaker": {"type": "STRING"}, "role": {"type": "STRING", "description": "z. B. CEO"}}},
        "figures": {"type": "ARRAY", "description": "0 bis 5 Tabellen oder Grafiken aus dem Bericht, die als Ausschnitt im Artikel stehen koennten",
            "items": {"type": "OBJECT", "required": ["id", "page", "box", "title", "shows"],
                "properties": {"id": {"type": "STRING", "description": "f1, f2, ..."},
                               "page": {"type": "INTEGER", "description": "Seitenzahl im PDF, ab 1"},
                               "box": {"type": "ARRAY", "items": {"type": "INTEGER"}, "description": "Bereich auf der Seite als [ymin, xmin, ymax, xmax], Werte 0 bis 1000"},
                               "title": {"type": "STRING", "description": "Kurze deutsche Bildunterschrift"},
                               "shows": {"type": "STRING", "description": "Ein Satz: was zeigt der Ausschnitt und warum ist er relevant"}}}},
        "period_end": {"type": "STRING", "description": "Ende des Berichtszeitraums, YYYY-MM-DD"},
        "prior_period_end": {"type": "STRING", "description": "Ende des Vergleichszeitraums im Vorjahr, YYYY-MM-DD"},
        "kpis": {"type": "ARRAY", "items": {"type": "OBJECT",
            "required": ["label", "value"],
            "properties": {"label": {"type": "STRING"}, "value": {"type": "STRING", "description": "Wert exakt wie im Bericht, z. B. 13,4 Mrd. USD"},
                           "change": {"type": "STRING", "description": "Veraenderung zum Vorjahr, z. B. +7 %"},
                           "page": {"type": "INTEGER", "description": "Seite im PDF, 0 wenn der Bericht keine Seiten hat"}}}},
        "chart": {"type": "OBJECT", "required": ["title", "unit", "bars"],
            "properties": {"title": {"type": "STRING"}, "unit": {"type": "STRING"}, "page": {"type": "INTEGER", "description": "0 wenn keine Seiten"},
                           "bars": {"type": "ARRAY", "items": {"type": "OBJECT", "required": ["label", "value"],
                               "properties": {"label": {"type": "STRING"}, "value": {"type": "NUMBER"}}}}}},
        "cashflow": {"type": "OBJECT", "description": "Aus der Kapitalflussrechnung des Berichts, Zahlen exakt wie dort (positiv, in der Berichtseinheit)",
            "properties": {"period_label": {"type": "STRING", "description": "z. B. Halbjahr 2026 oder 6 Monate"}, "unit": {"type": "STRING", "description": "z. B. Mio. USD"},
                           "operating_cash_flow": NUM, "capex": NUM, "dividends_paid": NUM, "share_repurchases": NUM,
                           "prior_dividends_paid": NUM, "page": {"type": "INTEGER"}}},
    },
}
ARTICLE_SCHEMA = {   # Aufruf 2: Artikeltext
    "type": "OBJECT", "required": ["title", "description", "slug", "body_markdown"],
    "properties": {"title": {"type": "STRING"}, "description": {"type": "STRING"}, "slug": {"type": "STRING"},
                   "body_markdown": {"type": "STRING"}},
}


def fail(msg):
    msg = " ".join(str(msg).split())
    print("::error title=IR-Agent::" + msg[:900])
    sys.exit(msg)


def pdf_text(path):
    try:
        return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout
    except Exception:
        return ""


GOOD_MODEL = None


def _generate(parts, schema, key):
    """Ruft Gemini auf (mit Wiederholung bei Ueberlastung, Modellwechsel bei Fehlern)."""
    global GOOD_MODEL
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json", "responseSchema": schema}}
    last = ""
    for model in ([GOOD_MODEL] if GOOD_MODEL else candidate_models(key)):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        res = None
        for attempt in range(3):
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
            try:
                with urllib.request.urlopen(req, timeout=240) as r:
                    res = json.load(r)
                break
            except urllib.error.HTTPError as e:
                last = f"{model}: Fehler {e.code}: {e.read().decode()[:300]}"
                print("Modell-Problem ->", last)
                if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(25 * (attempt + 1)); continue
                break
            except Exception as e:
                last = f"{model}: {e}"; print("Modell-Problem ->", last)
                break
        if res is None:
            continue
        try:
            out = json.loads(res["candidates"][0]["content"]["parts"][0]["text"])
            print("Modell:", model)
            GOOD_MODEL = model
            return out
        except Exception:
            last = f"{model}: unerwartete Antwort " + json.dumps(res)[:300]
    fail("Kein Gemini-Modell hat funktioniert. Letzter Fehler: " + last)


def api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        fail("GEMINI_API_KEY fehlt (GitHub: Settings > Secrets and variables > Actions).")
    return key


def doc_part(src):
    if src["kind"] == "pdf":
        data = open(src["path"], "rb").read()
        if len(data) > 18 * 1024 * 1024:
            fail("PDF ist groesser als 18 MB, bitte kuerzen.")
        return {"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(data).decode()}}
    return {"text": "BERICHT (Text der Pressemitteilung):\n\n" + src["text"][:600000]}


def call_gemini(src, prompt, schema=None):
    return _generate([doc_part(src), {"text": prompt}], schema or SCHEMA, api_key())


def read_prompt(name):
    return open(os.path.join(ROOT, "tools", name), encoding="utf-8").read()


def candidate_models(key):
    """Fragt bei Google ab, welche Flash-Modelle der Key nutzen darf; neueste Version zuerst."""
    names = []
    if os.environ.get("GEMINI_MODEL"):
        names.append(os.environ["GEMINI_MODEL"])
    try:
        req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": key})
        with urllib.request.urlopen(req, timeout=60) as r:
            ms = json.load(r).get("models", [])
        found = []
        for m in ms:
            n = m["name"].split("/")[-1]
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            if "flash" not in n or any(x in n for x in ("image", "tts", "live", "audio", "embedding", "thinking", "robotics", "computer", "customtools")):
                continue
            v = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
            ver = float(v.group(1)) if v else 0
            found.append((-ver, "preview" in n, "lite" in n, n))
        found.sort()
        names += [x[3] for x in found]
        print("Verfuegbare Flash-Modelle:", ", ".join(x[3] for x in found) or "keine")
    except Exception as e:
        print("Modellliste nicht abrufbar:", e)
    names += [MODEL, "gemini-flash-latest"]
    seen = []
    for n in names:
        if n and n not in seen:
            seen.append(n)
    return seen[:6]


def digits(s):
    return re.sub(r"[^0-9]", "", s or "")


def check_numbers(out, text):
    """Markiert Kennzahlen, deren Ziffernfolge nicht im PDF-Text vorkommt."""
    flat = re.sub(r"[^0-9]", "", text) if text else ""
    flat_raw = text or ""
    bad = []
    for k in out["kpis"]:
        for field in ("value", "change"):
            v = k.get(field) or ""
            nums = re.findall(r"\d+[.,]?\d*", v)
            for n in nums:
                cand = {n, n.replace(",", "."), n.replace(".", ","), n.rstrip("0").rstrip(".,")}
                if not any(c and c in flat_raw for c in cand):
                    bad.append(f"{k['label']} ({field}: {v})")
                    break
    cf = out.get("cashflow") or {}
    for f in ("operating_cash_flow", "capex", "dividends_paid", "share_repurchases", "prior_dividends_paid"):
        v = cf.get(f)
        if v:
            cands = {f"{v:,.0f}", f"{v:,.0f}".replace(",", "."), f"{v:,.0f}".replace(",", " "), "%g" % v}
            if not any(c in flat_raw for c in cands):
                bad.append(f"Kapitalflussrechnung {f}: {v:g}")
    for b in out["chart"]["bars"]:
        n = ("%g" % b["value"])
        if not any(c in flat_raw for c in {n, n.replace(".", ",")}):
            bad.append(f"Grafik {b['label']}: {n}")
    return bad if text else None

# ---------------------------------------------------------------- Berichtsquellen
UA = os.environ.get("SEC_USER_AGENT") or "dividenden-rechner.de Magazin-Agent (Kontakt ueber die Website)"


def http(url, binary=False, ua=None, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": ua or UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "section"}

    def __init__(self):
        super().__init__(); self.out = []; self.skip = 0

    def handle_starttag(self, t, a):
        if t in ("script", "style"): self.skip += 1
        elif t in ("td", "th"): self.out.append(" | ")
        elif t in self.BLOCK: self.out.append("\n")

    def handle_endtag(self, t):
        if t in ("script", "style"): self.skip = max(0, self.skip - 1)
        elif t in self.BLOCK: self.out.append("\n")

    def handle_data(self, d):
        if not self.skip: self.out.append(d)


def html_to_text(h):
    p = _Text(); p.feed(h)
    t = html.unescape("".join(p.out)).replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()


def sec_release(ticker):
    """Neueste Ergebnis-Pressemitteilung (8-K, Item 2.02, Exhibit 99.1) eines US-Titels von der SEC."""
    t = ticker.upper().strip()
    if not re.match(r"^[A-Z0-9.\-]{1,10}$", t):
        fail(f"Ungueltiges Kuerzel: {ticker}")
    try:
        tick = json.loads(http("https://www.sec.gov/files/company_tickers.json"))
    except Exception as e:
        fail(f"SEC nicht erreichbar ({e}). Tipp: Variable SEC_USER_AGENT mit Name und E-Mail setzen oder eine PDF hochladen.")
    hit = next((v for v in tick.values() if v["ticker"].upper() == t), None)
    if not hit:
        fail(f"{t} nicht bei der SEC gefunden. Fuer Titel ausserhalb der USA bitte eine PDF hochladen oder einen PDF-Link angeben.")
    cik = int(hit["cik_str"])
    sub = json.loads(http(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
    rec = sub["filings"]["recent"]
    for i, form in enumerate(rec["form"]):
        if form != "8-K" or "2.02" not in str(rec["items"][i]).split(","):
            continue
        acc = rec["accessionNumber"][i]; nod = acc.replace("-", ""); fdate = rec["filingDate"][i]
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nod}/"
        files = [x["name"] for x in json.loads(http(base + "index.json"))["directory"]["item"]]
        cand = [f for f in files if re.search(r"\.(htm|html|txt|pdf)$", f, re.I) and not re.search(r"(-index|^R\d+\.|xbrl)", f, re.I)]
        prim = rec["primaryDocument"][i]
        order = ([f for f in cand if re.search(r"99[-_.]?0?1", f)] or [f for f in cand if "99" in f]
                 or [f for f in cand if re.search(r"(earnings|release)", f, re.I)] or [f for f in cand if f != prim] or cand)
        if not order:
            continue
        name = order[0]
        raw = http(base + name, binary=True)
        age = (date.today() - datetime.strptime(fdate, "%Y-%m-%d").date()).days
        if age > 150:
            print(f"::warning title=IR-Agent::Neueste Ergebnismeldung von {t} ist {age} Tage alt ({fdate}).")
        print(f"SEC: {hit['title']} ({t}), 8-K vom {fdate}, Datei {name}")
        if name.lower().endswith(".pdf"):
            path = "/tmp/sec_release.pdf"; open(path, "wb").write(raw)
            return {"kind": "pdf", "path": path, "company": hit["title"], "url": base + name, "date": fdate}
        rawtxt = raw.decode("utf-8", "replace")
        txt = html_to_text(rawtxt) if not name.lower().endswith(".txt") else rawtxt
        if name.lower().endswith((".htm", ".html")) and html_to_pdf(rawtxt, base, "/tmp/sec_release.pdf"):
            print("Pressemitteilung als PDF gerendert (Seiten und Ausschnitte moeglich).")
            return {"kind": "pdf", "path": "/tmp/sec_release.pdf", "company": hit["title"], "url": base + name, "date": fdate}
        return {"kind": "text", "text": txt, "company": hit["title"], "url": base + name, "date": fdate}
    fail(f"Keine Ergebnismeldung (8-K, Item 2.02) von {t} gefunden.")

def html_to_pdf(raw_html, base_url, out_path):
    """Rendert eine HTML-Pressemitteilung mit Chrome zu PDF (damit es Seiten und Ausschnitte gibt)."""
    exe = next((c for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if subprocess.run(["which", c], capture_output=True).returncode == 0), None)
    if not exe:
        return False
    h = re.sub(r"(?i)<head([^>]*)>", lambda m: m.group(0) + f'<base href="{base_url}">', raw_html, count=1) if "<head" in raw_html.lower() else f'<base href="{base_url}">' + raw_html
    tmp = "/tmp/release.html"; open(tmp, "w", encoding="utf-8").write(h)
    try:
        subprocess.run([exe, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out_path}", "file://" + tmp],
                       capture_output=True, timeout=150)
    except Exception as e:
        print("HTML-zu-PDF fehlgeschlagen:", e); return False
    return os.path.exists(out_path) and os.path.getsize(out_path) > 5000


def render_figure(pdf_path, fig, out_path):
    """Seite als Bild rendern und auf den Bereich zuschneiden; ist der Bereich unplausibel, die ganze Seite."""
    pg = int(fig.get("page") or 0)
    if pg < 1:
        return False
    prefix = "/tmp/pg"
    try:
        subprocess.run(["pdftoppm", "-r", "170", "-f", str(pg), "-l", str(pg), "-png", pdf_path, prefix], check=True, capture_output=True, timeout=120)
    except Exception as e:
        print("Seite nicht renderbar:", e); return False
    cand = [f for f in os.listdir("/tmp") if f.startswith("pg-") and f.endswith(".png")]
    if not cand:
        return False
    f = os.path.join("/tmp", sorted(cand)[-1])
    im = Image.open(f).convert("RGB"); os.remove(f)
    W, H = im.size
    b = fig.get("box") or []
    if len(b) == 4 and all(isinstance(v, (int, float)) for v in b):
        y0, x0, y1, x1 = [max(0, min(1000, v)) / 1000 for v in b]
        if (y1 - y0) * (x1 - x0) >= 0.06 and y1 > y0 and x1 > x0:
            pad = 0.012
            im = im.crop((int(max(0, x0 - pad) * W), int(max(0, y0 - pad) * H), int(min(1, x1 + pad) * W), int(min(1, y1 + pad) * H)))
    if im.width > 1400:
        im = im.resize((1400, int(im.height * 1400 / im.width)), Image.LANCZOS)
    im.save(out_path, "PNG", optimize=True)
    return True



# ---------------------------------------------------------------- Aufmacherfoto (Wikimedia Commons, freie Lizenz)
OK_LIC = re.compile(r"^(CC0|Public domain|PD[- ]|CC[- ]BY(-SA)?[- ]\d\.\d)", re.I)
BAD_TITLE = re.compile(r"(logo|icon|flag|map|chart|diagram|stamp|coin|signature|screenshot|\.svg|poster|advert|label|can\b|bottle|stock price|graph)", re.I)


def _strip(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


def brand_of(company):
    b = re.sub(r"\b(the|company|inc\.?|corp\.?|corporation|co\.?|ltd\.?|plc|holdings?|group|/de/|\.com)\b", " ", company, flags=re.I)
    return re.sub(r"\s+", " ", b).strip(" ,.") or company


def commons_candidates(company):
    brand = brand_of(company); seen = {}; ua = "dividenden-rechner.de Magazin-Agent (https://www.dividenden-rechner.de)"
    for term in (f"{brand} headquarters", f"{brand} building", f"{brand} filetype:bitmap"):
        qs = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrsearch": term, "gsrnamespace": 6,
                                     "gsrlimit": 25, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1600})
        try:
            data = json.loads(http("https://commons.wikimedia.org/w/api.php?" + qs, ua=ua))
        except Exception as e:
            print("Commons nicht erreichbar:", e); continue
        for pg in (data.get("query", {}).get("pages", {}) or {}).values():
            ii = (pg.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata", {})
            title = pg.get("title", "")
            lic = _strip(md.get("LicenseShortName", {}).get("value", ""))
            w, h = ii.get("width", 0), ii.get("height", 0)
            if (ii.get("mime") != "image/jpeg" or w < 1400 or h < 700 or not (1.25 <= w / max(h, 1) <= 2.2) or BAD_TITLE.search(title)
                    or not OK_LIC.search(lic) or re.search(r"-(NC|ND)", lic) or _strip(md.get("Restrictions", {}).get("value", ""))
                    or not ii.get("thumburl")):
                continue
            seen[title] = {"title": title, "thumb": ii["thumburl"], "page": ii.get("descriptionurl", ""),
                           "artist": _strip(md.get("Artist", {}).get("value", "")) or "Unbekannt", "lic": lic,
                           "desc": _strip(md.get("ImageDescription", {}).get("value", ""))[:200],
                           "date": _strip(md.get("DateTimeOriginal", {}).get("value", ""))[:10]}
    return list(seen.values())[:12], brand


def pick_photo(company, ticker, key):
    cands, brand = commons_candidates(company)
    print(f"Foto-Kandidaten bei Wikimedia Commons: {len(cands)}")
    if not cands or not key:
        return None
    listing = "\n".join(f"{i}: {c['title']} | {c['desc']} | {c['date']}" for i, c in enumerate(cands))
    prompt = (f"Waehle ein Aufmacherfoto fuer einen sachlichen Boersenartikel ueber die Quartalszahlen von {company}. "
              "Gut: Unternehmenszentrale, Werk, Filiale, Produkt im Alltag, Strassenszene mit klarem Bezug zum Unternehmen. "
              "Schlecht: Portraets von Personen, Logos, Karten, Werbung, Fotos, die nicht eindeutig zu diesem Unternehmen gehoeren, "
              "veraltete oder unpassende Motive. Wenn nichts wirklich passt, antworte -1.\n\n" + listing)
    schema = {"type": "OBJECT", "required": ["index"], "properties": {"index": {"type": "INTEGER"}}}
    try:
        idx = _generate([{"text": prompt}], schema, key)["index"]
    except SystemExit:
        return None
    return cands[idx] if isinstance(idx, int) and 0 <= idx < len(cands) else None


def save_photo(c, slug):
    raw = http(c["thumb"], binary=True, ua="dividenden-rechner.de Magazin-Agent (https://www.dividenden-rechner.de)")
    im = Image.open(BytesIO(raw)).convert("RGB")
    w, h = im.size; tgt = 16 / 9
    if w / h > tgt:
        nw = int(h * tgt); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / tgt); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im = im.resize((1600, 900), Image.LANCZOS)
    rel = f"assets/magazin/{slug}-foto.jpg"
    os.makedirs(os.path.join(ROOT, "assets", "magazin"), exist_ok=True)
    im.save(os.path.join(ROOT, rel), "JPEG", quality=85, optimize=True)
    return rel


# ---------------------------------------------------------------- Berechnete Dividenden-Kennzahlen
def de(v, d=1):
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def derive_report(out):
    """Quoten aus der Kapitalflussrechnung des Berichts (rein rechnerisch, vom Programm berechnet)."""
    cf = out.get("cashflow") or {}
    cfo, capex, div = cf.get("operating_cash_flow"), cf.get("capex"), cf.get("dividends_paid")
    if not (cfo and capex is not None and div):
        return [], []
    u, per = cf.get("unit") or "", cf.get("period_label") or "Berichtszeitraum"
    fcf = cfo - capex
    facts, rows = [], []
    facts.append(f"Rechnerischer Free Cashflow {per} = operativer Cashflow {de(cfo,0)} minus Investitionen in Sachanlagen {de(capex,0)} = {de(fcf,0)} {u}.")
    facts.append(f"Gezahlte Dividenden {per}: {de(div,0)} {u}" + (f" (Vorjahreszeitraum: {de(cf['prior_dividends_paid'],0)} {u})." if cf.get("prior_dividends_paid") else "."))
    if fcf > 0:
        facts.append(f"Dividenden in Prozent des rechnerischen Free Cashflows ({per}): {de(div / fcf * 100, 0)} %.")
        rows.append((f"Dividenden / Free Cashflow ({per})", f"{de(div / fcf * 100, 0)} %", f"{de(div,0)} ÷ ({de(cfo,0)} − {de(capex,0)}) Mio."))
        if cf.get("share_repurchases"):
            tot = div + cf["share_repurchases"]
            facts.append(f"Dividenden plus Aktienrueckkaeufe ({de(cf['share_repurchases'],0)} {u}) in Prozent des Free Cashflows: {de(tot / fcf * 100, 0)} %.")
            rows.append((f"Dividenden + Rückkäufe / Free Cashflow ({per})", f"{de(tot / fcf * 100, 0)} %", f"({de(div,0)} + {de(cf['share_repurchases'],0)}) ÷ {de(fcf,0)} Mio."))
    return facts, rows


def fmp_get(path, **params):
    key = os.environ.get("FMP_API_KEY")
    if not key:
        return None
    qs = urllib.parse.urlencode({**params, "apikey": key})
    try:
        return json.loads(http(f"https://financialmodelingprep.com/stable/{path}?{qs}", timeout=60))
    except urllib.error.HTTPError as e:
        print(f"FMP {path}: HTTP {e.code}")
    except Exception as e:
        print(f"FMP {path}: {type(e).__name__}")
    return None


def fmp_metrics(symbol, have_report_rows=False):
    """Dividendenkennzahlen aus FMP (nur mit FMP_API_KEY, praktisch nur US-Titel). Gibt (facts, rows) zurueck."""
    if not symbol or not os.environ.get("FMP_API_KEY"):
        return [], []
    q = fmp_get("quote", symbol=symbol); dv = fmp_get("dividends", symbol=symbol)
    inc = fmp_get("income-statement", symbol=symbol, period="quarter", limit=4)
    cfs = fmp_get("cash-flow-statement", symbol=symbol, period="quarter", limit=4)
    if not (isinstance(q, list) and q and isinstance(dv, list) and dv):
        print("FMP: keine Kurs-/Dividendendaten fuer", symbol); return [], []
    price = float(q[0].get("price") or 0); today = date.today()
    ds = sorted([(x["date"], float(x.get("dividend") or 0)) for x in dv if x.get("date") and float(x.get("dividend") or 0) > 0], reverse=True)
    last12 = [a for d, a in ds if (today - datetime.strptime(d[:10], "%Y-%m-%d").date()).days <= 365]
    n12 = len(last12)
    facts, rows = [], []
    src = f"Financial Modeling Prep, Stand {today.strftime('%d.%m.%Y')}"
    if n12 and price > 0:
        run = ds[0][1] * n12
        facts.append(f"[{src}] Aktuelle Jahresdividende hochgerechnet: {de(run,2)} USD je Aktie ({n12} Zahlungen in 12 Monaten, letzte Zahlung {de(ds[0][1],2)} USD), Kurs {de(price,2)} USD, Dividendenrendite {de(run / price * 100, 1)} %.")
        rows.append(("Dividendenrendite", f"{de(run / price * 100, 1)} %", f"{de(run,2)} USD ÷ Kurs {de(price,2)} USD"))
        eps = sum(float(x.get("epsDiluted") if x.get("epsDiluted") is not None else (x.get("eps") or 0)) for x in (inc or [])) if isinstance(inc, list) and len(inc) >= 4 else None
        if eps and eps > 0:
            facts.append(f"[{src}] Ergebnis je Aktie der letzten vier Quartale {de(eps,2)} USD: Ausschuettungsquote {de(run / eps * 100, 0)} %, KGV {de(price / eps, 1)}.")
            rows.append(("Ausschüttungsquote (Ergebnis je Aktie)", f"{de(run / eps * 100, 0)} %", f"{de(run,2)} USD ÷ {de(eps,2)} USD (4 Quartale)"))
            rows.append(("KGV", de(price / eps, 1), f"Kurs ÷ {de(eps,2)} USD"))
        if isinstance(cfs, list) and len(cfs) >= 4:
            fcf = sum(float(x.get("freeCashFlow") or 0) for x in cfs)
            dp = abs(sum(float(x.get("commonDividendsPaid") if x.get("commonDividendsPaid") is not None else (x.get("netDividendsPaid") or 0)) for x in cfs))
            if fcf > 0 and dp > 0:
                facts.append(f"[{src}] Letzte vier Quartale: Free Cashflow {de(fcf / 1e6,0)} Mio. USD, gezahlte Dividenden {de(dp / 1e6,0)} Mio. USD, Anteil {de(dp / fcf * 100, 0)} %.")
                if not have_report_rows:
                    rows.append(("Dividenden / Free Cashflow (12 Monate)", f"{de(dp / fcf * 100, 0)} %", f"{de(dp / 1e6,0)} ÷ {de(fcf / 1e6,0)} Mio. USD"))
    # Wann wird die Dividende ueblicherweise erhoeht? (Ankuendigungsmonat der Erhoehungen)
    MON = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
    asc = sorted([x for x in dv if x.get("date") and float(x.get("dividend") or 0) > 0], key=lambda x: x["date"])
    inc_ev = []
    for i in range(1, len(asc)):
        if float(asc[i]["dividend"]) > float(asc[i - 1]["dividend"]) * 1.005 and asc[i]["date"][:4] != asc[i - 1]["date"][:4]:
            dd = (asc[i].get("declarationDate") or "")[:10]
            inc_ev.append((asc[i]["date"][:10], dd, float(asc[i - 1]["dividend"]), float(asc[i]["dividend"])))
    recent = [e for e in inc_ev if int(e[0][:4]) >= today.year - 6][-5:]
    if len(recent) >= 3:
        use_decl = all(e[1] for e in recent)
        months = [int((e[1] if use_decl else e[0])[5:7]) for e in recent]
        top = max(set(months), key=months.count)
        hits = months.count(top)
        label = "angekündigt" if use_decl else "ex"
        years = ", ".join(f"{(e[1] if use_decl else e[0])[:4]}" for e in recent)
        facts.append((f"[{src}] Die Dividendenerhöhungen wurden in {hits} von {len(recent)} Jahren ({years}) im {MON[top - 1]} angekündigt." if use_decl else f"[{src}] Die Dividendenerhöhungen traten in {hits} von {len(recent)} Jahren ({years}) mit dem Ex-Dividenden-Termin im {MON[top - 1]} in Kraft.") + f" Die letzte Erhöhung: von {de(recent[-1][2],2)} auf {de(recent[-1][3],2)} USD je Quartalszahlung ({(recent[-1][1] or recent[-1][0])}). Das ist ein Muster der Vergangenheit, keine Zusage des Unternehmens.")
        rows.append(("Übliche Erhöhung der Dividende", f"{MON[top - 1]}", f"{hits} von {len(recent)} Jahren ({years}), " + ("Ankündigung" if use_decl else "Ex-Termin")))
        if any(int(e[0][:4]) == today.year for e in inc_ev):
            facts.append(f"[{src}] In {today.year} wurde die Dividende bereits erhöht.")
        else:
            facts.append(f"[{src}] In {today.year} gab es bisher keine Erhöhung.")
    yr = {}
    for d, a in ds:
        yr[int(d[:4])] = yr.get(int(d[:4]), 0) + a
    full = sorted(y for y in yr if y < today.year)
    if len(full) >= 2:
        streak = 0
        for y in reversed(full[1:]):
            if yr[y] > yr[y - 1] * 1.0005 if (y - 1) in yr else False:
                streak += 1
            else:
                break
        facts.append(f"[{src}] Dividende je Aktie in Folge erhöht: {streak} Jahre (bis {full[-1]}, jeweils Summe der Kalenderjahre).")
        rows.append(("Dividendenerhöhungen in Folge", f"{streak} Jahre", f"Kalenderjahressummen bis {full[-1]}"))
        y0 = full[-1] - 5
        if y0 in yr and yr[y0] > 0:
            cagr = (yr[full[-1]] / yr[y0]) ** (1 / 5) - 1
            facts.append(f"[{src}] Dividendenwachstum {y0}–{full[-1]}: {de(cagr * 100, 1)} % pro Jahr.")
            rows.append((f"Dividendenwachstum {y0}–{full[-1]}", f"{de(cagr * 100, 1)} % p. a.", "Kalenderjahressummen"))
    return facts, rows



def font(size, bold=False):
    for f in (("/usr/share/fonts/opentype/inter/Inter-Bold.otf" if bold else "/usr/share/fonts/opentype/inter/Inter-Regular.otf"),
              ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def tw(d, t, f):
    return d.textlength(t, font=f)


def wrap(d, t, f, w):
    out, cur = [], ""
    for wd in t.split():
        x = (cur + " " + wd).strip()
        if tw(d, x, f) <= w:
            cur = x
        else:
            out.append(cur); cur = wd
    return out + ([cur] if cur else [])


def draw_graphic(out, path):
    W, H = 1600, 900
    im = Image.new("RGB", (W, H), "#ffffff"); d = ImageDraw.Draw(im)
    green, dark, grey = "#2f9e5b", "#14202b", "#5d6b78"
    d.rectangle([0, 0, W, 16], fill=green)
    d.text((70, 52), f"{out['company']} · {out['period']}".upper(), font=font(28, True), fill=green)
    kp = out["kpis"][:4]
    n = max(1, len(kp)); gap = 24; cw = (W - 140 - gap * (n - 1)) // n
    for i, k in enumerate(kp):
        x = 70 + i * (cw + gap)
        d.rounded_rectangle([x, 110, x + cw, 290], 16, fill="#f0f8f3")
        lf = font(22)
        y = 128
        for ln in wrap(d, k["label"], lf, cw - 36)[:2]:
            d.text((x + 18, y), ln, font=lf, fill=grey); y += 28
        vf = font(40, True)
        vs = k["value"]
        while tw(d, vs, vf) > cw - 36 and vf.size > 24:
            vf = font(vf.size - 2, True)
        d.text((x + 18, 190), vs, font=vf, fill=dark)
        if k.get("change"):
            d.text((x + 18, 244), k["change"] + " ggü. Vorjahr", font=font(21, True), fill=green if not k["change"].strip().startswith(("-", "−", "–")) else "#c0392b")
    ch = out["chart"]
    d.text((70, 330), ch["title"], font=font(30, True), fill=dark)
    d.text((70, 370), ch["unit"], font=font(22), fill=grey)
    bars = ch["bars"][:8]
    top, bot, left, right = 430, H - 130, 70, W - 70
    vmax = max([b["value"] for b in bars] + [0.0001]); vmin = min([b["value"] for b in bars] + [0])
    span = vmax - vmin or 1
    zero = bot - (0 - vmin) / span * (bot - top - 40)
    bw = (right - left) / len(bars)
    d.line([left, zero, right, zero], fill="#c9d3dc", width=2)
    for i, b in enumerate(bars):
        x0 = left + i * bw + bw * 0.18; x1 = left + (i + 1) * bw - bw * 0.18
        yv = zero - (b["value"] - 0) / span * (bot - top - 40)
        y0, y1 = (yv, zero) if b["value"] >= 0 else (zero, yv)
        d.rounded_rectangle([x0, y0, x1, max(y1, y0 + 2)], 6, fill=green if b["value"] >= 0 else "#c0392b")
        vt = ("%g" % b["value"]).replace(".", ",")
        vf = font(28, True)
        d.text(((x0 + x1) / 2 - tw(d, vt, vf) / 2, (y0 - 38) if b["value"] >= 0 else (y1 + 6)), vt, font=vf, fill=dark)
        lf = font(22); ly = bot + 18
        for ln in wrap(d, b["label"], lf, bw - 10)[:2]:
            d.text(((x0 + x1) / 2 - tw(d, ln, lf) / 2, ly), ln, font=lf, fill=grey); ly += 26
    d.text((70, H - 46), f"Quelle: {out['company']}, {out['period']}-Bericht, S. {ch['page']}  ·  dividenden-rechner.de", font=font(22), fill=grey)
    im.save(path, "PNG", optimize=True)


def q(v):
    """YAML-sicher: in Anfuehrungszeichen setzen (Doppelpunkte im Text)."""
    return '"' + str(v).replace('"', "'").replace("\n", " ") + '"'


def build(out, text, src_note, force=False, calc_rows=None, fmp_used=False, figs=None):
    slug = re.sub(r"[^a-z0-9]+", "-", out["article"]["slug"].lower()).strip("-") or "bericht"
    mdpath = os.path.join(ROOT, "content", "magazin", f"{slug}.md")
    if os.path.exists(mdpath) and not force:
        fail(f"Es gibt schon einen Artikel '{slug}.md'. Zum Ueberschreiben --force nutzen oder die Datei vorher loeschen.")
    gpath = os.path.join(ROOT, "assets", "magazin", f"{slug}-grafik.png")
    os.makedirs(os.path.dirname(gpath), exist_ok=True)
    draw_graphic(out, gpath)
    bad = check_numbers(out, text)
    a = out["article"]
    quelle = lambda pg: f"S. {pg}" if (pg or 0) > 0 else "Pressemitteilung"
    rows = "\n".join(f"| {k['label']} | {k['value']} | {k.get('change') or '–'} | {quelle(k.get('page'))} |" for k in out["kpis"])
    photo = None
    try:
        photo = pick_photo(out["company"], out.get("ticker", ""), os.environ.get("GEMINI_API_KEY") if not os.environ.get("IR_MOCK") else None)
    except Exception as e:
        print("Foto-Suche fehlgeschlagen:", e)
    fm = ["---", f"title: {q(a['title'])}", f"description: {q(a['description'])}",
          f"date: {date.today().isoformat()} 08:00", f"author: {q(CFG['author'])}", f"author_bio: {q(CFG['author_bio'])}",
          f"category: {CFG.get('category', 'Zahlen')}"]
    hinweise = []
    if photo:
        rel = save_photo(photo, slug)
        fm += [f"image: {rel}", f"image_alt: {q('Foto zu ' + out['company'] + ': ' + (photo['desc'] or photo['title'].replace('File:', '')))}",
               f"image_credit: {q('Foto: ' + photo['artist'] + ' / Wikimedia Commons, ' + photo['lic'])}", f"image_source: {photo['page']}"]
        hinweise.append("Aufmacherfoto ist automatisch von Wikimedia Commons gewaehlt: bitte pruefen, ob es zum Artikel passt (sonst image-Zeilen entfernen, dann entsteht ein Titelbild automatisch).")
    else:
        hinweise.append("Kein freies Aufmacherfoto gefunden, das Titelbild entsteht automatisch. Eigenes Foto: image, image_alt, image_credit ergaenzen.")
    tk = re.sub(r"[^A-Za-z0-9.\-]", "", out.get("ticker") or "")
    dom_ = re.sub(r"^(https?://)?(www\.)?|/.*$", "", out.get("website_domain") or "")
    if tk:
        fm.append(f"logo_symbol: {tk}")
    if dom_ and re.match(r"^[a-z0-9.\-]+\.[a-z]{2,}$", dom_, re.I):
        fm.append(f"logo_domain: {dom_}")
    fm += ["draft: true", "---", ""]
    if bad:
        hinweise.append("Diese Werte wurden im Berichtstext nicht gefunden: " + "; ".join(bad))
    elif bad is None:
        hinweise.append("Berichtstext nicht lesbar, Zahlen nicht automatisch geprueft.")
    if src_note:
        hinweise.append("Quelle: " + src_note)
    chart_alt = f"{out['chart']['title']} ({out['company']}, {out['period']})"
    body_md = a["body_markdown"].strip()
    used = []
    for fid, f in (figs or {}).items():
        tag = "{{FIG:" + fid + "}}"
        if tag in body_md:
            rel = f"assets/magazin/{slug}-{fid}.png"
            import shutil
            shutil.copy(f["tmp"], os.path.join(ROOT, rel)); used.append(fid)
            alt = f["title"].replace("[", "(").replace("]", ")")
            body_md = body_md.replace(tag, f"![{alt}](/{rel})\n*{f['title']} (Auszug aus der Veröffentlichung von {out['company']})*")
    body_md = re.sub(r"\{\{FIG:[^}]*\}\}", "", body_md)
    if used:
        hinweise.append("Ausschnitte aus dem Bericht im Text (" + ", ".join(used) + "): bitte prüfen, ob Zuschnitt und Platz passen. Unpassende Bildzeilen einfach löschen.")
    parts = body_md.split("\n\n", 1)
    body_md = parts[0] + f"\n\n![{chart_alt}](/assets/magazin/{slug}-grafik.png)\n\n" + (parts[1] if len(parts) > 1 else "")
    head = "".join(f"<!-- PRÜFEN: {h} -->\n" for h in hinweise) + "\n"
    calc_md = ""
    if calc_rows:
        calc_md = ("## Dividendenkennzahlen im Überblick (eigene Berechnung)\n\n| Kennzahl | Wert | Rechenweg |\n|---|---|---|\n"
                   + "\n".join(f"| {a} | {b} | {c} |" for a, b, c in calc_rows) + "\n\n")
    quelle_txt = f"{out['company']}, Pressemitteilung zum {out['period']} vom {out['report_date']}" + (f"; Kurs- und Dividendendaten: Financial Modeling Prep" if fmp_used else "")
    body = (head + body_md + "\n\n## Die wichtigsten Zahlen im Überblick\n\n"
            "| Kennzahl | Wert | Veränderung zum Vorjahr | Quelle |\n|---|---|---|---|\n" + rows + "\n\n" + calc_md +
            f"*Quelle: {quelle_txt}. Rechenwege eigene Berechnung. Keine Anlageberatung.*\n")
    open(mdpath, "w", encoding="utf-8").write("\n".join(fm) + body)
    return mdpath, gpath, bad, photo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?"); ap.add_argument("--ticker"); ap.add_argument("--mock"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not a.pdf and not a.ticker:
        fail("Bitte --ticker KO oder eine PDF angeben.")
    if a.mock:
        os.environ["IR_MOCK"] = "1"
    src = None
    if a.ticker:
        src = sec_release(a.ticker)
    else:
        src = {"kind": "pdf", "path": a.pdf, "url": "", "date": ""}
    text = pdf_text(src["path"]) if src["kind"] == "pdf" else src["text"]
    calc_rows, fmp_used, figs = [], False, {}
    if a.mock:
        out = json.load(open(a.mock, encoding="utf-8"))
        facts, calc_rows = derive_report(out)
    else:
        out = call_gemini(src, read_prompt("ir_prompt.md"))
        facts, calc_rows = derive_report(out)
        sym = (a.ticker or out.get("ticker") or "").upper()
        ff, fr = fmp_metrics(sym, bool(calc_rows)) if re.match(r"^[A-Z0-9.\-]{1,10}$", sym) else ([], [])
        if ff:
            facts += ff; calc_rows += fr; fmp_used = True
        qt = out.get("ceo_quote") or {}
        if qt.get("text_original") and qt.get("text_de"):
            norm = lambda t: re.sub(r"[^a-z0-9]+", "", (t or "").lower().replace("\u2019", "'"))
            if norm(qt["text_original"]) and norm(qt["text_original"]) in norm(text):
                facts.append(f"CEO-Zitat (Originalwortlaut im Bericht verifiziert, hier auf Deutsch): \u201e{qt['text_de']}\u201c \u2013 {qt.get('speaker') or 'Unternehmensleitung'}, {qt.get('role') or ''}".strip(", "))
            else:
                print("Zitat nicht im Berichtstext gefunden, wird weggelassen.")
                out["ceo_quote"] = None
        summary = json.dumps({k: out.get(k) for k in ("company", "ticker", "period", "report_date", "period_end", "prior_period_end", "kpis", "chart", "cashflow")}, ensure_ascii=False)
        fakten = "\n".join("- " + f for f in facts) if facts else "- (keine berechneten Kennzahlen verfuegbar)"
        prompt2 = read_prompt("ir_article_prompt.md") + "\n\nFAKTEN (vom Programm berechnet, Zahlen exakt so uebernehmen):\n" + fakten + "\n\nEXTRAHIERTE KENNZAHLEN (JSON):\n" + summary
        figs = {}
        if src["kind"] == "pdf":
            os.makedirs("/tmp/figs", exist_ok=True)
            for fg in (out.get("figures") or [])[:5]:
                fid = re.sub(r"[^a-z0-9]", "", str(fg.get("id", "")).lower()) or f"f{len(figs) + 1}"
                tmp = f"/tmp/figs/{fid}.png"
                if render_figure(src["path"], fg, tmp):
                    figs[fid] = {"tmp": tmp, "title": fg.get("title") or "Auszug", "page": fg.get("page"), "shows": fg.get("shows") or ""}
        if figs:
            prompt2 += "\n\nVERFUEGBARE AUSSCHNITTE AUS DEM BERICHT (Bilder; setze hoechstens drei davon ein):\n" + "\n".join(
                f"- {fid}: {f['title']} | {f['shows']}" for fid, f in figs.items())
        out["article"] = _generate([doc_part(src), {"text": prompt2}], ARTICLE_SCHEMA, api_key())
        print("FAKTEN:\n" + fakten)
    note = src.get("url") or ""
    md, g, bad, photo = build(out, text, note, a.force, calc_rows, fmp_used, figs if not a.mock else None)
    print("Entwurf:", md); print("Grafik:", g); print("Foto:", photo["title"] if photo else "keins")
    print("Nicht verifizierte Zahlen:", bad if bad else "keine")


if __name__ == "__main__":
    main()
