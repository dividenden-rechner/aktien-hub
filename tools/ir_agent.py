#!/usr/bin/env python3
"""IR-Agent: Quartalsbericht -> Kennzahlen (JSON) -> Grafik (PNG) + Aufmacherfoto + Artikelentwurf (Markdown).

Aufruf:
  python3 tools/ir_agent.py --ticker KO                         # US-Titel: Bericht selbst von der SEC holen
  python3 tools/ir_agent.py content/ir-inbox/bericht.pdf        # eigene PDF
  python3 tools/ir_agent.py bericht.pdf --mock antwort.json     # Test ohne API (fertige Modell-Antwort)

Der Entwurf landet mit `draft: true` in content/magazin/. Nichts wird veroeffentlicht,
bevor du `draft: true` entfernst. Zahlen werden gegen den Berichtstext geprueft.
"""
import argparse, base64, glob, html, json, os, re, subprocess, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import date, datetime
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "tools", "ir_config.json"), encoding="utf-8"))
MODEL = os.environ.get("GEMINI_MODEL") or CFG.get("model", "gemini-2.5-flash")

REPORT_TYPES = ["Quartalszahlen", "Halbjahreszahlen", "Jahresbericht", "Dividendenmeldung", "Aktiensplit", "Fusion & Übernahme", "Börsengang", "Insiderkauf", "Kapitalmaßnahme", "Management", "Sonstige Meldung"]
NUM = {"type": "NUMBER"}
SCHEMA = {   # Aufruf 1: Zahlen aus dem Bericht
    "type": "OBJECT",
    "required": ["company", "report_type", "report_date"],
    "properties": {
        "company": {"type": "STRING"}, "ticker": {"type": "STRING"},
        "report_type": {"type": "STRING", "enum": REPORT_TYPES, "description": "Art des Dokuments"},
        "period": {"type": "STRING", "description": "z. B. Q2 2026, H1 2026, GJ 2025; leer bei Ereignismeldungen"},
        "report_date": {"type": "STRING", "description": "YYYY-MM-DD"},
        "website_domain": {"type": "STRING", "description": "Domain der offiziellen Unternehmenswebsite, z. B. verizon.com oder mercedes-benz.com"},
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
        "industry": {"type": "STRING", "enum": ["Pharma", "Tabak", "Konsumgueter", "Finanzen", "BDC", "REIT", "Telekom", "Technologie", "Energie", "Industrie", "Handel", "Versorger", "Sonstige"],
                     "description": "Branche des Unternehmens; BDC fuer Business Development Companies"},
        "details": {"type": "ARRAY", "description": "Fakten aus dem Dokument zur Entwicklung nach Region, Produkt, Segment und zu Branchenkennzahlen, auch Negatives",
            "items": {"type": "OBJECT", "required": ["topic", "fact", "direction"],
                "properties": {"topic": {"type": "STRING", "description": "z. B. Region Asien, Produkt Kisqali, NAV je Aktie, Refinanzierung"},
                               "fact": {"type": "STRING", "description": "Kurzer Satz mit Zahl und Vergleich, wie im Dokument"},
                               "direction": {"type": "STRING", "enum": ["positiv", "negativ", "neutral"]},
                               "page": {"type": "INTEGER"}}}},
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
                           "prior_dividends_paid": NUM, "prior_operating_cash_flow": NUM, "prior_capex": NUM, "prior_share_repurchases": NUM,
                           "page": {"type": "INTEGER"}}},
        "balance": {"type": "OBJECT", "description": "Aus der Bilanz: Schulden und liquide Mittel am Berichtsstichtag und am Vergleichsstichtag (Vorjahresende oder Vorjahresquartal), positive Zahlen in der Berichtseinheit",
            "properties": {"unit": {"type": "STRING"}, "cash": NUM, "short_term_debt": NUM, "long_term_debt": NUM,
                           "prior_cash": NUM, "prior_short_term_debt": NUM, "prior_long_term_debt": NUM,
                           "prior_label": {"type": "STRING", "description": "z. B. 31. Dezember 2025"}}},
    },
}
ARTICLE_SCHEMA = {   # Aufruf 2: Artikeltext
    "type": "OBJECT", "required": ["title", "description", "slug", "body_markdown"],
    "properties": {"title": {"type": "STRING"}, "description": {"type": "STRING"}, "slug": {"type": "STRING"},
                   "body_markdown": {"type": "STRING"}},
}


CORE_SCHEMA = {"type": "OBJECT", "properties": {k: SCHEMA["properties"][k] for k in ("kpis", "cashflow", "balance", "period_end", "prior_period_end")}}
CORE_PROMPT = """Lies aus dem angehaengten Ergebnisdokument nur diese Pflichtangaben, exakt wie im Dokument (Zahlen in der Berichtseinheit, keine Berechnungen):
- kpis: bis zu 6 Kennzahlen in dieser Reihenfolge, soweit im Dokument vorhanden: Umsatz, operatives Ergebnis bzw. operatives Kerngeschaeft, Nettogewinn, Gewinn je Aktie (bereinigt, wenn ausgewiesen), Free Cashflow oder operativer Cashflow, Dividende je Aktie. value auf Deutsch (Komma, Mrd. USD), change = Veraenderung zum Vorjahr nur wenn genannt, page = Seite.
- cashflow: Kapitalflussrechnung, laengster ausgewiesener Zeitraum seit Jahresbeginn: operating_cash_flow, capex (positiv), dividends_paid (positiv), share_repurchases (positiv) und dieselben Werte des Vorjahreszeitraums (prior_*), dazu unit und period_label.
- balance: liquide Mittel, kurzfristige und langfristige Finanzschulden (ohne Leasing) am Stichtag und am Vergleichsstichtag (prior_*), unit, prior_label.
Lass nur weg, was im Dokument wirklich nicht steht."""

EARNINGS = ("Quartalszahlen", "Halbjahreszahlen", "Jahresbericht")
FIG_SCHEMA = {"type": "OBJECT", "properties": {
    "figures": SCHEMA["properties"]["figures"], "chart": SCHEMA["properties"]["chart"]}}
FIG_PROMPT = """Du suchst im angehaengten Ergebnisdokument Material fuer einen Artikel. Gib zurueck:
1. figures: zwei bis vier Stellen (Seite ab 1, Bereich [ymin, xmin, ymax, xmax] mit Werten 0 bis 1000, eng um die Tabelle oder Grafik inklusive Ueberschrift, Einheit und Fussnoten). Waehle je nach Branche das, was die Lage am besten zeigt: Gewinn- und Verlustrechnung mit Umsatz, Betriebsergebnis und Nettogewinn bzw. -verlust; Umsatz oder Ertrag nach Region, Segment oder Geschaeftsbereich; Umsatz der wichtigsten Produkte, Marken oder Medikamente; bei Banken und Versicherern Zinsueberschuss, Provisionen, Kreditrisikovorsorge, Kapitalquoten (CET1); bei BDCs und REITs NAV, Net Investment Income, FFO, Portfolio und Ausfaelle; Kapitalflussrechnung; Verschuldung, Bilanz und Faelligkeiten; Prognose. Keine Deckblaetter, keine Textseiten, keine Rechtshinweise. title kurz auf Deutsch, shows ein Satz.
2. chart: eine Datenreihe mit 3 bis 6 Balken aus EINER Tabelle des Dokuments, die die Geschichte der Periode zeigt, zum Beispiel Umsatz, Betriebsergebnis und Nettogewinn (auch Verluste als negative Werte), oder Ertrag je Region, Segment oder Produkt, oder Wachstum in Prozent. Werte wortgetreu aus dem Dokument, title und Balkenbeschriftungen auf Deutsch, unit angeben, page = Seite.
Es gibt in nahezu jedem Ergebnisdokument solche Tabellen: liefere sie."""


def keyword_pages(pdf_path, n=2):
    """Notfall: Seiten mit Kapitalflussrechnung, Segment-/Regionen- oder Produkttabellen per Stichwort finden."""
    words = [("cash flow", 3), ("cash flows", 3), ("net sales by", 3), ("revenue by", 3), ("by region", 3), ("by segment", 3), ("segment", 1),
             ("guidance", 2), ("outlook", 2), ("balance sheet", 3), ("net asset value", 3), ("by product", 3), ("brands", 1), ("top 10", 1)]
    try:
        raw = subprocess.run(["pdftotext", "-layout", pdf_path, "-"], capture_output=True, text=True, check=True).stdout
    except Exception:
        return []
    pages = raw.split("\f"); scored = []
    for i, tx in enumerate(pages, 1):
        low = tx.lower(); digits = len(re.findall(r"\d[\d.,]*", tx))
        if len(tx) < 400 or digits < 25 or i == 1:
            continue
        s = sum(w * low.count(k) for k, w in words) + min(digits, 200) / 40
        scored.append((s, i))
    scored.sort(reverse=True)
    return [i for _, i in scored[:n]]


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


MODELS = None


def model_order(key):
    """Bewaehrtes Modell zuerst, danach die anderen (jedes Modell hat ein eigenes Kontingent)."""
    global MODELS
    if MODELS is None:
        MODELS = candidate_models(key)
    return ([GOOD_MODEL] if GOOD_MODEL else []) + [m for m in MODELS if m != GOOD_MODEL]


def _generate(parts, schema, key):
    """Ruft Gemini auf (mit Wiederholung bei Ueberlastung, Modellwechsel bei Fehlern)."""
    global GOOD_MODEL
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json", "responseSchema": schema}}
    last = ""
    for model in model_order(key):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        res = None
        for attempt in range(3):
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
            try:
                with urllib.request.urlopen(req, timeout=240) as r:
                    res = json.load(r)
                break
            except urllib.error.HTTPError as e:
                eb = e.read().decode()
                last = f"{model}: Fehler {e.code}: {eb[:300]}"
                print("Modell-Problem ->", last)
                if e.code == 429 and ("PerDay" in eb or "per day" in eb.lower()):
                    print("Tageskontingent dieses Modells aufgebraucht, naechstes Modell.")
                    break
                if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep((45 if e.code == 429 else 25) * (attempt + 1)); continue
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


RESEARCH_OFF = False


def research(out, key):
    """Hintergrundrecherche mit Google-Suche (Gemini Grounding): Vergangenheit, Makro, Branche. Liefert (Text, [(Titel, URL)])."""
    ind = out.get("industry") or "Sonstige"
    spez = {
        "BDC": "NAV je Aktie im Verlauf der letzten Quartale, Net Investment Income (NII) je Aktie und Deckung der Dividende, PIK-Anteil, Non-Accruals, Kurs im Vergleich zum NAV (Aufschlag/Abschlag), Zinsumfeld (Basiszinsen, Spreads), Fälligkeiten und Refinanzierung der Schulden.",
        "Tabak": "Entwicklung der klassischen Zigarette (Absatzmengen, Preise) gegenüber neuen Produkten (rauchfreie Produkte, Nikotinbeutel, Heat-not-Burn, E-Zigaretten) mit Wachstum und Verlusten je Produkt, Regulierung, Rechtsstreit.",
        "Pharma": "Wachstumsprodukte, Patentabläufe, Pipeline und Studienergebnisse, Preisdruck und Gesundheitspolitik, Zölle.",
        "Konsumgueter": "Entwicklung nach Weltregionen, Mengen und Preise, Rohstoffkosten, Konsumstimmung.",
        "Finanzen": "Zinsmarge, Kreditausfälle, Kapitalquoten, Zinsumfeld, Regulierung.",
        "REIT": "FFO/AFFO je Aktie, Belegung, Mietwachstum, Zinsumfeld, Fälligkeiten und Refinanzierung der Schulden, Kurs im Vergleich zum NAV.",
    }.get(ind, "Entwicklung nach Regionen und Produkten, Branchenlage.")
    prompt = (f"Recherchiere mit der Websuche Hintergrund für einen Artikel über {out.get('company')} ({out.get('ticker') or ''}), Dokument: {out.get('report_type')} {out.get('period') or ''}, "
              f"Branche {ind}. Berichte sachlich und kritisch, nicht nur Positives. Liefere knappe Stichpunkte auf Deutsch mit konkreten Zahlen und Zeitangaben zu: "
              "1. Entwicklung des Unternehmens in den letzten zwei bis drei Jahren und den letzten Quartalen (Umsatz, Gewinn, Dividende, Schulden), damit Trends erkennbar sind. "
              "2. Dem Makroumfeld, soweit es für dieses Unternehmen relevant ist (Inflation, Zinsen, Währungen, Rohstoffe). "
              "3. Geopolitischer Lage und Regulierung, soweit relevant (Zölle, Sanktionen, Konflikte). "
              f"4. Branchenspezifisch: {spez} "
              "5. Schulden: Fälligkeitsprofil und Refinanzierung, Ratings. "
              "Nenne zu jeder Zahl Jahr oder Quartal. Erfinde nichts; was du nicht findest, lässt du weg.")
    body = {"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}], "generationConfig": {"temperature": 0.2}}
    global RESEARCH_OFF
    if RESEARCH_OFF:
        return "", []
    for model in model_order(key)[:2]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
            with urllib.request.urlopen(req, timeout=240) as r:
                res = json.load(r)
            cand = res["candidates"][0]
            text = "".join(p.get("text", "") for p in cand["content"]["parts"]).strip()
            src = []
            for ch in (cand.get("groundingMetadata", {}).get("groundingChunks") or []):
                w = ch.get("web") or {}
                if w.get("uri") and (w.get("title"), w["uri"]) not in src:
                    src.append((w.get("title") or w["uri"], w["uri"]))
            if text:
                return text, src[:8]
        except urllib.error.HTTPError as e:
            print("Recherche-Problem ->", model, e.code, e.read().decode()[:200])
            if e.code in (400, 403, 404, 429):
                if e.code == 429:
                    RESEARCH_OFF = True; break
                continue
            time.sleep(20)
        except Exception as e:
            print("Recherche-Problem ->", model, e)
    print("::notice title=IR-Agent::Hintergrundrecherche nicht moeglich (Websuche des Keys nicht verfuegbar), Artikel nur aus dem Dokument.")
    return "", []


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


def clean_text(t):
    """Gemini liefert manchmal HTML-Entities (&auml;) oder Bruchschreibweise (3-3/4); beides wird lesbar gemacht."""
    t = html.unescape(t or "")
    t = re.sub(r"(\d+)[- ]3/4\b", lambda m: f"{m.group(1)},75", t)
    t = re.sub(r"(\d+)[- ]1/2\b", lambda m: f"{m.group(1)},5", t)
    t = re.sub(r"(\d+)[- ]1/4\b", lambda m: f"{m.group(1)},25", t)
    return t


def clean_article(a):
    for k in ("title", "description", "slug", "body_markdown"):
        if isinstance(a.get(k), str):
            a[k] = clean_text(a[k])
    return a


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
    for k in out.get("kpis") or []:
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
    bl = out.get("balance") or {}
    for f in ("cash", "short_term_debt", "long_term_debt", "prior_cash", "prior_short_term_debt", "prior_long_term_debt"):
        v = bl.get(f)
        if v:
            cands = {f"{v:,.0f}", f"{v:,.0f}".replace(",", "."), f"{v:,.0f}".replace(",", " "), "%g" % v}
            if not any(c in flat_raw for c in cands):
                bad.append(f"Bilanz {f}: {v:g}")
    for b in (out.get("chart") or {}).get("bars", []):
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


def sec_lookup(ticker):
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
    return t, hit, cik, sub["filings"]["recent"]


def _age(fdate):
    return (date.today() - datetime.strptime(fdate, "%Y-%m-%d").date()).days


def _src_from_file(raw, name, base, hit, fdate, render=True):
    if name.lower().endswith(".pdf"):
        path = "/tmp/sec_release.pdf"; open(path, "wb").write(raw)
        return {"kind": "pdf", "path": path, "company": hit["title"], "url": base + name, "date": fdate}
    rawtxt = raw.decode("utf-8", "replace")
    txt = html_to_text(rawtxt) if not name.lower().endswith(".txt") else rawtxt
    if render and name.lower().endswith((".htm", ".html")) and html_to_pdf(rawtxt, base, "/tmp/sec_release.pdf"):
        print("Meldung als PDF gerendert (Seiten und Ausschnitte moeglich).")
        return {"kind": "pdf", "path": "/tmp/sec_release.pdf", "company": hit["title"], "url": base + name, "date": fdate, "pages_real": False}
    return {"kind": "text", "text": txt, "company": hit["title"], "url": base + name, "date": fdate, "pages_real": False}


def _exhibit(base, rec, i):
    files = [x["name"] for x in json.loads(http(base + "index.json"))["directory"]["item"]]
    cand = [f for f in files if re.search(r"\.(htm|html|txt|pdf)$", f, re.I) and not re.search(r"(-index|^R\d+\.|xbrl)", f, re.I)]
    prim = rec["primaryDocument"][i]
    order = ([f for f in cand if re.search(r"99[-_.]?0?1", f)] or [f for f in cand if "99" in f]
             or [f for f in cand if re.search(r"(earnings|release)", f, re.I)] or [f for f in cand if f != prim] or cand)
    return order[0] if order else prim


EVENT_ITEMS = {"1.01", "2.01", "3.03", "5.01", "5.02", "5.03", "8.01"}


def sec_release(ticker, art="ergebnisse"):
    """Dokument eines US-Titels von der SEC: Ergebnismeldung (8-K 2.02), Jahresbericht (10-K), Quartalsbericht (10-Q),
    neueste Ereignismeldung (8-K) oder Insidergeschaefte (Form 4)."""
    t, hit, cik, rec = sec_lookup(ticker)
    n = len(rec["form"])
    if art == "insider":
        return sec_insider(t, hit, cik, rec)
    if art in ("jahresbericht", "quartalsbericht"):
        form = "10-K" if art == "jahresbericht" else "10-Q"
        for i in range(n):
            if rec["form"][i] != form:
                continue
            nod = rec["accessionNumber"][i].replace("-", ""); prim = rec["primaryDocument"][i]
            base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nod}/"
            raw = http(base + prim, binary=True, timeout=120)
            print(f"SEC: {hit['title']} ({t}), {form} vom {rec['filingDate'][i]}, Datei {prim}")
            src = _src_from_file(raw, prim, base, hit, rec["filingDate"][i], render=False)
            if src["kind"] == "text":
                src["text"] = src["text"][:450000]
            return src
        fail(f"Kein {form} von {t} gefunden.")
    for i in range(n):
        if rec["form"][i] != "8-K":
            continue
        items = set(str(rec["items"][i]).split(","))
        if art == "ergebnisse" and "2.02" not in items:
            continue
        if art == "meldung" and (not (items & EVENT_ITEMS) or _age(rec["filingDate"][i]) > 90):
            continue
        fdate = rec["filingDate"][i]; nod = rec["accessionNumber"][i].replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nod}/"
        name = _exhibit(base, rec, i)
        raw = http(base + name, binary=True)
        if art == "ergebnisse" and _age(fdate) > 150:
            print(f"::warning title=IR-Agent::Neueste Ergebnismeldung von {t} ist {_age(fdate)} Tage alt ({fdate}).")
        print(f"SEC: {hit['title']} ({t}), 8-K ({', '.join(sorted(items))}) vom {fdate}, Datei {name}")
        return _src_from_file(raw, name, base, hit, fdate)
    fail("Keine Ergebnismeldung (8-K, Item 2.02) von %s gefunden." % t if art == "ergebnisse" else "Keine passende Meldung (8-K der letzten 90 Tage) von %s gefunden." % t)


def sec_insider(t, hit, cik, rec):
    """Insiderkaeufe und -verkaeufe (Form 4, offener Markt) der letzten 120 Tage, Summen rechnet das Programm."""
    import xml.etree.ElementTree as ET
    tx = []; seen = 0
    for i in range(len(rec["form"])):
        if rec["form"][i] not in ("4", "4/A") or _age(rec["filingDate"][i]) > 120:
            continue
        seen += 1
        if seen > 40:
            break
        nod = rec["accessionNumber"][i].replace("-", ""); prim = rec["primaryDocument"][i].split("/")[-1]
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nod}/"
        try:
            root = ET.fromstring(http(base + prim))
        except Exception as e:
            print("Form 4 nicht lesbar:", prim, type(e).__name__); continue
        name = (root.findtext(".//reportingOwner/reportingOwnerId/rptOwnerName") or "").strip().title()
        rel = root.find(".//reportingOwner/reportingOwnerRelationship")
        role = ""
        if rel is not None:
            role = (rel.findtext("officerTitle") or "").strip() or ("Direktor" if rel.findtext("isDirector") in ("1", "true") else "") or ("10-%-Eigner" if rel.findtext("isTenPercentOwner") in ("1", "true") else "")
        for e in root.findall(".//nonDerivativeTransaction"):
            code = e.findtext("transactionCoding/transactionCode")
            if code not in ("P", "S"):
                continue
            try:
                sh = float(e.findtext("transactionAmounts/transactionShares/value")); pr = float(e.findtext("transactionAmounts/transactionPricePerShare/value") or 0)
            except Exception:
                continue
            tx.append({"date": e.findtext("transactionDate/value")[:10], "name": name, "role": role, "code": code, "shares": sh, "price": pr})
    buys = [x for x in tx if x["code"] == "P"]; sells = [x for x in tx if x["code"] == "S"]
    if not buys:
        print(f"::notice title=IR-Agent::Keine Insiderkaeufe von {t} in den letzten 120 Tagen (Verkaeufe: {len(sells)}). Kein Artikel erzeugt.")
        return None
    tx.sort(key=lambda x: x["date"], reverse=True)
    lines = ["Datum | Name | Funktion | Art | Stück | Preis (USD) | Betrag (USD)"]
    for x in tx:
        lines.append(f"{x['date']} | {x['name']} | {x['role'] or '–'} | {'Kauf' if x['code'] == 'P' else 'Verkauf'} (offener Markt) | {x['shares']:,.0f} | {x['price']:,.2f} | {x['shares'] * x['price']:,.0f}")
    tot = lambda L: sum(x["shares"] * x["price"] for x in L)
    facts = [f"Insiderkäufe am offenen Markt in den letzten 120 Tagen: {len(buys)} Transaktionen von {len({x['name'] for x in buys})} Personen, zusammen {de(tot(buys),0)} USD ({de(sum(x['shares'] for x in buys),0)} Aktien, Durchschnittspreis {de(tot(buys) / sum(x['shares'] for x in buys), 2)} USD)."]
    big = max(buys, key=lambda x: x["shares"] * x["price"])
    facts.append(f"Größter Kauf: {big['name']} ({big['role'] or 'Insider'}) am {big['date']}, {de(big['shares'],0)} Aktien zu {de(big['price'],2)} USD = {de(big['shares'] * big['price'],0)} USD.")
    if sells:
        facts.append(f"Im selben Zeitraum gab es {len(sells)} Verkäufe am offenen Markt über zusammen {de(tot(sells),0)} USD.")
    else:
        facts.append("Im selben Zeitraum gab es keine Verkäufe am offenen Markt.")
    text = f"INSIDERGESCHÄFTE {hit['title']} ({t}), Meldungen nach SEC Form 4, Stand {date.today().isoformat()}\n\n" + "\n".join(lines)
    print(f"SEC Form 4: {len(buys)} Kaeufe, {len(sells)} Verkaeufe")
    return {"kind": "text", "text": text, "company": hit["title"], "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=40",
            "date": date.today().isoformat(), "pages_real": False, "extra_facts": facts}


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
    im.save(out_path, "PNG", optimize=True)   # unveraenderte Pixel, nur zugeschnitten
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
    iip = {"prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1600}
    queries = []
    # Bilder aus dem Wikipedia-Artikel des Unternehmens (meist Zentrale, Standorte)
    try:
        for lang in ("en", "de"):
            s = json.loads(http(f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
                {"action": "query", "format": "json", "list": "search", "srsearch": f"{company} company", "srlimit": 1}), ua=ua))
            hit = (s.get("query", {}).get("search") or [{}])[0].get("title")
            if hit:
                im_ = json.loads(http(f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
                    {"action": "query", "format": "json", "titles": hit, "prop": "images", "imlimit": 40}), ua=ua))
                names = [i["title"] for pg in im_.get("query", {}).get("pages", {}).values() for i in pg.get("images", [])
                         if i["title"].lower().endswith((".jpg", ".jpeg"))]
                if names:
                    queries.append({"action": "query", "format": "json", "titles": "|".join(names[:40]), **iip})
    except Exception as e:
        print("Wikipedia-Bilder nicht erreichbar:", e)
    for term in (f"{brand} headquarters", f"{brand} building", f"{brand} office", f"{company} headquarters", f"{brand} filetype:bitmap"):
        queries.append({"action": "query", "format": "json", "generator": "search", "gsrsearch": term, "gsrnamespace": 6, "gsrlimit": 25, **iip})
    for qd in queries:
        qs = urllib.parse.urlencode(qd)
        try:
            data = json.loads(http("https://commons.wikimedia.org/w/api.php?" + qs, ua=ua))
        except Exception as e:
            print("Commons nicht erreichbar:", e); continue
        for pg in (data.get("query", {}).get("pages", {}) or {}).values():
            ii = (pg.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata", {})
            title = pg.get("title", "")
            lic = _strip(md.get("LicenseShortName", {}).get("value", ""))
            w, h = ii.get("width", 0), ii.get("height", 0)
            if (ii.get("mime") != "image/jpeg" or w < 1200 or h < 650 or not (1.2 <= w / max(h, 1) <= 2.4) or BAD_TITLE.search(title)
                    or not OK_LIC.search(lic) or re.search(r"-(NC|ND)", lic) or _strip(md.get("Restrictions", {}).get("value", ""))
                    or not ii.get("thumburl")):
                continue
            seen[title] = {"title": title, "thumb": ii["thumburl"], "page": ii.get("descriptionurl", ""),
                           "artist": _strip(md.get("Artist", {}).get("value", "")) or "Unbekannt", "lic": lic,
                           "desc": _strip(md.get("ImageDescription", {}).get("value", ""))[:200],
                           "date": _strip(md.get("DateTimeOriginal", {}).get("value", ""))[:10]}
    return list(seen.values())[:15], brand


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


def derive_balance(out):
    """Nettoverschuldung aus der Bilanz des Berichts (Stichtag gegen Vergleichsstichtag)."""
    b = out.get("balance") or {}
    if b.get("cash") is None or (b.get("short_term_debt") is None and b.get("long_term_debt") is None):
        return [], []
    u = b.get("unit") or "Mio."
    debt = (b.get("short_term_debt") or 0) + (b.get("long_term_debt") or 0)
    net = debt - b["cash"]
    facts = [f"Bilanz zum Stichtag: Finanzschulden {de(debt,0)} {u} (kurz- plus langfristig), liquide Mittel {de(b['cash'],0)} {u}, Nettoverschuldung rechnerisch {de(net,0)} {u}."]
    rows = [("Nettoverschuldung (Bilanzstichtag)", f"{de(net,0)} {u}", f"{de(debt,0)} − {de(b['cash'],0)}")]
    if b.get("prior_cash") is not None and (b.get("prior_short_term_debt") is not None or b.get("prior_long_term_debt") is not None):
        pdebt = (b.get("prior_short_term_debt") or 0) + (b.get("prior_long_term_debt") or 0)
        pnet = pdebt - b["prior_cash"]; lab = b.get("prior_label") or "Vergleichsstichtag"
        ch = net - pnet
        facts.append(f"Zum Vergleichsstichtag ({lab}) lag die Nettoverschuldung rechnerisch bei {de(pnet,0)} {u}; Veränderung {'+' if ch >= 0 else '−'}{de(abs(ch),0)} {u}. Finanzschulden damals {de(pdebt,0)} {u}.")
        rows.append((f"Nettoverschuldung ({lab})", f"{de(pnet,0)} {u}", f"{de(pdebt,0)} − {de(b['prior_cash'],0)}"))
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
    # Mehrjahres-Entwicklung: Cashflow, Investitionen, Verschuldung (Geschaeftsjahre)
    cfa = fmp_get("cash-flow-statement", symbol=symbol, period="annual", limit=5)
    bsa = fmp_get("balance-sheet-statement", symbol=symbol, period="annual", limit=5)
    ina = fmp_get("income-statement", symbol=symbol, period="annual", limit=5)
    def yearkey(x): return str(x.get("fiscalYear") or (x.get("date") or "")[:4])
    if isinstance(cfa, list) and cfa:
        cs = sorted(cfa, key=yearkey)
        fcfs = "; ".join(f"{yearkey(x)}: {de(float(x.get('freeCashFlow') or 0) / 1e9, 1)}" for x in cs)
        cap = "; ".join(f"{yearkey(x)}: {de(abs(float(x.get('capitalExpenditure') or 0)) / 1e9, 1)}" for x in cs)
        facts.append(f"[{src}] Free Cashflow der letzten Geschäftsjahre in Mrd. USD: {fcfs}. Investitionen (Capex) in Mrd. USD: {cap}.")
        rows.append(("Free Cashflow, Geschäftsjahre (Mrd. USD)", fcfs, "Kapitalflussrechnung laut FMP"))
    if isinstance(bsa, list) and bsa:
        bs = sorted(bsa, key=yearkey); eb = {yearkey(x): float(x.get("ebitda") or 0) for x in (ina if isinstance(ina, list) else [])}
        nd = []
        for x in bs:
            net = x.get("netDebt")
            net = float(net) if net is not None else float(x.get("totalDebt") or 0) - float(x.get("cashAndCashEquivalents") or 0)
            nd.append((yearkey(x), net))
        nds = "; ".join(f"{y}: {de(v / 1e9, 1)}" for y, v in nd)
        facts.append(f"[{src}] Nettoverschuldung zum Jahresende in Mrd. USD: {nds}.")
        lev = [(y, v / eb[y]) for y, v in nd if eb.get(y, 0) > 0 and v > 0]
        if lev:
            ls = "; ".join(f"{y}: {de(v, 1)}" for y, v in lev)
            facts.append(f"[{src}] Nettoverschuldung im Verhältnis zum EBITDA (Faktor): {ls}.")
            rows.append(("Nettoverschuldung / EBITDA, Jahresende", ls, "Bilanz und Gewinn- und Verlustrechnung laut FMP"))
        else:
            rows.append(("Nettoverschuldung, Jahresende (Mrd. USD)", nds, "Bilanz laut FMP"))
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
    d.text((70, 52), f"{out['company']} · {out.get('period') or out.get('report_type') or ''}".strip(" ·").upper(), font=font(28, True), fill=green)
    kp = (out.get("kpis") or [])[:4]
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
    ch = out.get("chart") or {}
    if not ch.get("bars"):
        d.text((70, 312), f"Quelle: {out['company']}, {out.get('report_type') or 'Bericht'} {out.get('period') or ''}  ·  dividenden-rechner.de", font=font(20), fill=grey)
        im.crop((0, 0, W, 360)).save(path, "PNG", optimize=True); return
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
    pg = ch.get("page") or 0
    d.text((70, H - 46), f"Quelle: {out['company']}, Pressemitteilung {out.get('period') or ''}".strip() + (f", S. {pg}" if pg else "") + "  ·  dividenden-rechner.de", font=font(22), fill=grey)
    im.save(path, "PNG", optimize=True)


def q(v):
    """YAML-sicher: in Anfuehrungszeichen setzen (Doppelpunkte im Text)."""
    return '"' + str(v).replace('"', "'").replace("\n", " ") + '"'


def compare_table(out):
    """Vergleichstabelle Cashflow und Bilanz: aktuell gegen Vorjahr bzw. Vergleichsstichtag (aus dem Bericht, FCF und Nettoschulden gerechnet)."""
    cf, bl = out.get("cashflow") or {}, out.get("balance") or {}
    rows = []

    def row(label, cur, pri, unit, calc=False):
        if cur is None:
            return
        ch = ""
        if pri not in (None, 0):
            pc = (cur / pri - 1) * 100
            ch = f"{'+' if pc >= 0 else '−'}{de(abs(pc), 1)} %"
        rows.append(f"| {label}{' (berechnet)' if calc else ''} | {de(cur, 0)} {unit} | {(de(pri, 0) + ' ' + unit) if pri is not None else '–'} | {ch or '–'} |")
    u = cf.get("unit") or "Mio."
    per = cf.get("period_label") or "Berichtszeitraum"
    if cf.get("operating_cash_flow") is not None:
        cfo, cap, pcfo, pcap = cf["operating_cash_flow"], cf.get("capex"), cf.get("prior_operating_cash_flow"), cf.get("prior_capex")
        row(f"Operativer Cashflow, {per}", cfo, pcfo, u)
        row("Investitionen (Capex)", cap, pcap, u)
        if cap is not None:
            row("Free Cashflow", cfo - cap, (pcfo - pcap) if (pcfo is not None and pcap is not None) else None, u, True)
        row("Gezahlte Dividenden", cf.get("dividends_paid"), cf.get("prior_dividends_paid"), u)
        row("Aktienrückkäufe", cf.get("share_repurchases"), cf.get("prior_share_repurchases"), u)
    if bl.get("cash") is not None and (bl.get("short_term_debt") is not None or bl.get("long_term_debt") is not None):
        bu = bl.get("unit") or "Mio."
        debt = (bl.get("short_term_debt") or 0) + (bl.get("long_term_debt") or 0)
        pdebt = None
        if bl.get("prior_cash") is not None and (bl.get("prior_short_term_debt") is not None or bl.get("prior_long_term_debt") is not None):
            pdebt = (bl.get("prior_short_term_debt") or 0) + (bl.get("prior_long_term_debt") or 0)
        row("Liquide Mittel", bl["cash"], bl.get("prior_cash"), bu)
        row("Finanzschulden", debt, pdebt, bu)
        row("Nettoverschuldung", debt - bl["cash"], (pdebt - bl["prior_cash"]) if pdebt is not None else None, bu, True)
    if not rows:
        return ""
    lab = bl.get("prior_label") or "Vorjahr"
    return ("## Cashflow und Bilanz im Vergleich\n\n| Kennzahl | Aktuell | Vorjahr / " + lab + " | Veränderung |\n|---|---|---|---|\n" + "\n".join(rows) +
            "\n\n*Cashflow: Zeitraum seit Jahresbeginn, Vergleich mit dem Vorjahreszeitraum. Bilanz: Vergleich mit dem angegebenen Stichtag. Free Cashflow und Nettoverschuldung eigene Berechnung aus Angaben des Berichts.*\n\n")


def build(out, text, src_note, force=False, calc_rows=None, fmp_used=False, figs=None, src=None):
    out["period"] = out.get("period") or ""
    out["report_date"] = out.get("report_date") or date.today().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", out["article"]["slug"].lower()).strip("-") or "bericht"
    stamp = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d-%H%M")   # Dateiname beginnt mit Datum, damit die Liste auf GitHub geordnet ist
    vorhanden = glob.glob(os.path.join(ROOT, "content", "magazin", f"*{slug}.md"))
    vorhanden = [v for v in vorhanden if re.fullmatch(r"(\d{4}-\d{2}-\d{2}(-\d{4})?-)?" + re.escape(slug) + r"\.md", os.path.basename(v))]
    mdpath = vorhanden[0] if vorhanden else os.path.join(ROOT, "content", "magazin", f"{stamp}-{slug}.md")
    if os.path.exists(mdpath) and not force:
        fail(f"Es gibt schon einen Artikel '{slug}.md'. Zum Ueberschreiben --force nutzen oder die Datei vorher loeschen.")
    gpath = os.path.join(ROOT, "assets", "magazin", f"{slug}-grafik.png")
    os.makedirs(os.path.dirname(gpath), exist_ok=True)
    has_chart = bool((out.get("chart") or {}).get("bars"))
    cf_ = out.get("cashflow") or {}
    has_tiles = bool(out.get("kpis")) and out.get("report_type") in EARNINGS
    if not has_chart and out.get("kpis") and cf_.get("operating_cash_flow") and cf_.get("capex") is not None:
        bars = [{"label": "Operativer Cashflow", "value": cf_["operating_cash_flow"]},
                {"label": "Investitionen", "value": cf_["capex"]},
                {"label": "Free Cashflow (berechnet)", "value": round(cf_["operating_cash_flow"] - cf_["capex"], 1)}]
        if cf_.get("dividends_paid"):
            bars.append({"label": "Gezahlte Dividenden", "value": cf_["dividends_paid"]})
        out["chart"] = {"title": f"Cashflow und Dividenden, {cf_.get('period_label') or 'Berichtszeitraum'}", "unit": cf_.get("unit") or "",
                        "bars": bars, "page": 0}
        has_chart = True
    if has_chart or has_tiles:
        draw_graphic(out, gpath)
        has_chart = True
    bad = check_numbers(out, text)
    rtype = out.get("report_type") or "Quartalszahlen"
    doc = f"{rtype} {out.get('period') or ''}".strip()
    a = out["article"]
    quelle = lambda pg: f"S. {pg}" if (pg or 0) > 0 else "Pressemitteilung"
    rows = "\n".join(f"| {k['label']} | {k['value']} | {k.get('change') or '–'} | {quelle(k.get('page'))} |" for k in (out.get("kpis") or []))
    photo = None
    try:
        photo = pick_photo(out["company"], out.get("ticker", ""), os.environ.get("GEMINI_API_KEY") if not os.environ.get("IR_MOCK") else None)
    except Exception as e:
        print("Foto-Suche fehlgeschlagen:", e)
    fm = ["---", f"title: {q(a['title'])}", f"description: {q(a['description'])}",
          f"date: {datetime.now(ZoneInfo('Europe/Berlin')).strftime('%Y-%m-%d %H:%M')}", f"author: {q(CFG['author'])}", f"author_bio: {q(CFG['author_bio'])}",
          f"category: {rtype}"]
    hinweise = []
    if photo:
        rel = save_photo(photo, slug)
        fm += [f"image: {rel}", f"image_alt: {q('Foto zu ' + out['company'] + ': ' + (photo['desc'] or photo['title'].replace('File:', '')))}",
               f"image_credit: {q('Foto: ' + photo['artist'] + ' / Wikimedia Commons, ' + photo['lic'])}", f"image_source: {photo['page']}"]
        hinweise.append("Aufmacherfoto ist automatisch von Wikimedia Commons gewaehlt: bitte pruefen, ob es zum Artikel passt (sonst image-Zeilen entfernen, dann entsteht ein Titelbild automatisch).")
    else:
        hinweise.append("Kein freies Aufmacherfoto gefunden, das Titelbild entsteht automatisch. Eigenes Foto: image, image_alt, image_credit ergaenzen.")
    tk = re.sub(r"[^A-Za-z0-9.\-]", "", out.get("ticker") or "")
    if os.environ.get("FMP_API_KEY") and not os.environ.get("IR_MOCK"):
        try:   # passendes FMP-Symbol (auch Auslandsboersen wie MBG.DE) ueber die Namenssuche
            res = fmp_get("search-name", query=out["company"], limit=6) or []
            syms = [r.get("symbol", "") for r in res if r.get("symbol")]
            if syms and tk not in syms:
                tk = syms[0]
        except Exception as e:
            print("Symbolsuche fehlgeschlagen:", e)
    dom_ = re.sub(r"^(https?://)?(www\.)?|/.*$", "", out.get("website_domain") or "")
    fm.append("logo_name: " + q(out["company"]))
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
    chart_alt = (f"{(out.get('chart') or {}).get('title') or 'Kennzahlen'} ({out['company']}, {doc})") if has_chart else ""
    body_md = a["body_markdown"].strip()
    used = []
    for fid, f in (figs or {}).items():
        tag = "{{FIG:" + fid + "}}"
        if tag in body_md:
            rel = f"assets/magazin/{slug}-{fid}.png"
            import shutil
            shutil.copy(f["tmp"], os.path.join(ROOT, rel)); used.append(fid)
            alt = f["title"].replace("[", "(").replace("]", ")")
            pg = f.get("page") if (src or {}).get("pages_real", True) and f.get("page") else None
            link = f" · [Original]({src['url']})" if (src or {}).get("url", "").startswith("http") else ""
            body_md = body_md.replace(tag, f"![{alt}](/{rel})\n*{f['title']}. Quelle: {out['company']}, {doc} vom {out['report_date']}" + (f", S. {pg}" if pg else "") + f"{link}. Ausschnitt nur zugeschnitten, sonst unverändert.*")
    body_md = re.sub(r"\{\{FIG:[^}]*\}\}", "", body_md)
    if used:
        hinweise.append("Ausschnitte aus dem Bericht im Text (" + ", ".join(used) + "): bitte prüfen, ob Zuschnitt und Platz passen. Unpassende Bildzeilen einfach löschen.")
    if has_chart:
        mm = re.search(r"## Die ausführliche Version\n+(?:###[^\n]*\n+)?[^\n]+\n", body_md)   # nach dem Einstieg der ausfuehrlichen Version, nie im Kurz-Kasten
        if mm:
            parts = [body_md[:mm.end()].rstrip("\n"), body_md[mm.end():].lstrip("\n")]
        else:
            parts = body_md.split("\n\n", 1)
        glink = f" · [Original]({src['url']})" if (src or {}).get("url", "").startswith("http") else ""
        body_md = parts[0] + f"\n\n![{chart_alt}](/assets/magazin/{slug}-grafik.png)\n*Eigene Darstellung nach Daten aus: {out['company']}, {doc} vom {out['report_date']}{glink}.*\n\n" + (parts[1] if len(parts) > 1 else "")
    head = "".join(f"<!-- PRÜFEN: {h} -->\n" for h in hinweise) + "\n"
    calc_md = ""
    if calc_rows:
        calc_md = (("## Dividendenkennzahlen im Überblick (eigene Berechnung)" if rtype in ("Quartalszahlen", "Halbjahreszahlen", "Jahresbericht", "Dividendenmeldung") else "## Kennzahlen im Überblick (eigene Berechnung)") + "\n\n| Kennzahl | Wert | Rechenweg |\n|---|---|---|\n"
                   + "\n".join(f"| {a} | {b} | {c} |" for a, b, c in calc_rows) + "\n\n")
    quelle_txt = f"{out['company']}, {doc} vom {out['report_date']}" + (f"; Kurs- und Dividendendaten: Financial Modeling Prep" if fmp_used else "")
    kpi_md = ("## Die wichtigsten Zahlen im Überblick\n\n| Kennzahl | Wert | Veränderung zum Vorjahr | Quelle |\n|---|---|---|---|\n" + rows + "\n\n") if rows else ""
    body = (head + body_md + "\n\n" + kpi_md + compare_table(out) + calc_md +
            f"*Quelle: {quelle_txt}. Rechenwege eigene Berechnung. Keine Anlageberatung.*\n")
    open(mdpath, "w", encoding="utf-8").write("\n".join(fm) + body)
    return mdpath, gpath, bad, photo


def chrome_exe():
    return next((c for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if subprocess.run(["which", c], capture_output=True).returncode == 0), None)


CHROME_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def chrome_fetch(url):
    """Seite mit echtem Chrome laden (umgeht einfache Bot-Sperren, fuehrt JavaScript aus). Gibt (HTML, PDF-Pfad oder None) zurueck."""
    exe = chrome_exe()
    if not exe:
        return "", None
    base = [exe, "--headless=new", "--no-sandbox", "--disable-gpu", f"--user-agent={CHROME_UA}", "--lang=de-DE", "--virtual-time-budget=15000"]
    htm = ""
    try:
        r = subprocess.run(base + ["--dump-dom", url], capture_output=True, timeout=120)
        htm = r.stdout.decode("utf-8", "replace")
    except Exception as e:
        print("Chrome-Abruf fehlgeschlagen:", e)
    pdf = None
    try:
        subprocess.run(base + ["--no-pdf-header-footer", "--print-to-pdf=/tmp/web_source.pdf", url], capture_output=True, timeout=150)
        if os.path.exists("/tmp/web_source.pdf") and os.path.getsize("/tmp/web_source.pdf") > 5000:
            pdf = "/tmp/web_source.pdf"
    except Exception as e:
        print("Chrome-PDF fehlgeschlagen:", e)
    return htm, pdf


def web_source(url):
    """Normale Webseite (z. B. Ad-hoc-Meldung, Pressemitteilung) als Quelle: Text lesen und als PDF rendern."""
    raw = b""
    try:
        raw = http(url, binary=True, ua=CHROME_UA, timeout=90)
    except Exception as e:
        print(f"Direkter Abruf nicht moeglich ({e}), versuche es mit Chrome.")
    if raw[:5] == b"%PDF-":
        open("/tmp/web_source.pdf", "wb").write(raw)
        return {"kind": "pdf", "path": "/tmp/web_source.pdf", "url": url, "date": ""}

    def extract(h):
        m = re.search(r"(?is)<main\b.*?</main>|<article\b.*?</article>", h)
        mt = html_to_text(m.group(0)) if m else ""
        return mt if len(mt.strip()) > 600 else html_to_text(h)
    h = raw.decode("utf-8", "replace") if raw else ""
    txt = extract(h) if h else ""
    pdf = None
    if len(txt.strip()) < 600:
        h, pdf = chrome_fetch(url)
        txt = extract(h) if h else ""
    if len(txt.strip()) < 600:
        fail("Die Webseite ist fuer den Agenten nicht lesbar (Bot-Sperre oder kaum Text). Bitte die Seite im Browser als PDF speichern und die PDF nutzen.")
    if pdf:
        print("Webseite mit Chrome geladen und als PDF gerendert (Seiten und Ausschnitte moeglich).")
        return {"kind": "pdf", "path": pdf, "url": url, "date": "", "pages_real": False}
    base = url if url.endswith("/") else url.rsplit("/", 1)[0] + "/"
    if html_to_pdf(h, base, "/tmp/web_source.pdf"):
        return {"kind": "pdf", "path": "/tmp/web_source.pdf", "url": url, "date": "", "pages_real": False}
    return {"kind": "text", "text": txt, "url": url, "date": "", "pages_real": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?"); ap.add_argument("--ticker"); ap.add_argument("--url"); ap.add_argument("--art", default=os.environ.get("ART") or "ergebnisse"); ap.add_argument("--mock"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not a.pdf and not a.ticker and not a.url:
        fail("Bitte --ticker KO, eine PDF oder --url angeben.")
    if a.mock:
        os.environ["IR_MOCK"] = "1"
    src = None
    if a.url:
        src = web_source(a.url)
    elif a.ticker:
        src = sec_release(a.ticker, a.art)
        if src is None:
            return
    else:
        src = {"kind": "pdf", "path": a.pdf, "url": "", "date": ""}
    text = pdf_text(src["path"]) if src["kind"] == "pdf" else src["text"]
    calc_rows, fmp_used, figs = [], False, {}
    if a.mock:
        out = json.load(open(a.mock, encoding="utf-8"))
        facts, calc_rows = derive_report(out)
    else:
        out = call_gemini(src, read_prompt("ir_prompt.md"))
        if out.get("report_type") in EARNINGS and not (out.get("kpis") and out.get("cashflow") and out.get("balance")):
            print("::notice title=IR-Agent::Kennzahlen, Cashflow oder Bilanz fehlten, gezielte Nachfrage.")
            try:
                core = _generate([doc_part(src), {"text": CORE_PROMPT}], CORE_SCHEMA, api_key())
                for k in ("kpis", "cashflow", "balance", "period_end", "prior_period_end"):
                    if core.get(k) and not out.get(k):
                        out[k] = core[k]
            except SystemExit:
                print("::notice title=IR-Agent::Gezielte Nachfrage fehlgeschlagen.")
        if out.get("report_type") in EARNINGS and src["kind"] == "pdf" and not (out.get("figures") and (out.get("chart") or {}).get("bars")):
            try:
                extra = _generate([doc_part(src), {"text": FIG_PROMPT + f"\n\nUnternehmen: {out.get('company')}, Branche: {out.get('industry') or 'unbekannt'}."}], FIG_SCHEMA, api_key())
                if extra.get("figures") and not out.get("figures"):
                    out["figures"] = extra["figures"]
                if (extra.get("chart") or {}).get("bars") and not (out.get("chart") or {}).get("bars"):
                    out["chart"] = extra["chart"]
            except SystemExit:
                print("::notice title=IR-Agent::Gezielte Suche nach Ausschnitten fehlgeschlagen.")
        facts, calc_rows = derive_report(out)
        have_rep = bool(calc_rows)
        bf, br = derive_balance(out)
        facts += bf + (src.get("extra_facts") or []); calc_rows += br
        sym = (a.ticker or out.get("ticker") or "").upper()
        ff, fr = fmp_metrics(sym, have_rep) if re.match(r"^[A-Z0-9.\-]{1,10}$", sym) else ([], [])
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
        summary = json.dumps({k: out.get(k) for k in ("company", "ticker", "report_type", "industry", "period", "report_date", "period_end", "prior_period_end", "kpis", "chart", "cashflow", "balance", "details")}, ensure_ascii=False)
        fakten = "\n".join("- " + f for f in facts) if facts else "- (keine berechneten Kennzahlen verfuegbar)"
        prompt2 = read_prompt("ir_article_prompt.md") + f"\n\nART DES DOKUMENTS: {out.get('report_type')}" + "\n\nFAKTEN (vom Programm berechnet, Zahlen exakt so uebernehmen):\n" + fakten + "\n\nEXTRAHIERTE KENNZAHLEN (JSON):\n" + summary
        bg_text, bg_src = research(out, api_key())
        if bg_text:
            prompt2 += ("\n\nHINTERGRUND (per Websuche recherchiert; nutze ihn fuer Einordnung, Vergleich mit frueheren Quartalen, Makro- und Branchenlage; "
                        "Zahlen daraus nur mit Zeit- bzw. Quellenbezug im Text, etwa 'laut Medienberichten' oder 'im Vorjahr'; Unsicheres weglassen):\n" + bg_text[:9000])
        figs = {}
        if src["kind"] == "pdf":
            os.makedirs("/tmp/figs", exist_ok=True)
            for fg in (out.get("figures") or [])[:5]:
                fid = re.sub(r"[^a-z0-9]", "", str(fg.get("id", "")).lower()) or f"f{len(figs) + 1}"
                tmp = f"/tmp/figs/{fid}.png"
                if render_figure(src["path"], fg, tmp):
                    figs[fid] = {"tmp": tmp, "title": fg.get("title") or "Auszug", "page": fg.get("page"), "shows": fg.get("shows") or ""}
        if not figs and src["kind"] == "pdf" and out.get("report_type") in EARNINGS:
            os.makedirs("/tmp/figs", exist_ok=True)
            for k, pg in enumerate(keyword_pages(src["path"]), 1):
                tmp = f"/tmp/figs/k{k}.png"
                if render_figure(src["path"], {"page": pg, "box": []}, tmp):
                    figs[f"k{k}"] = {"tmp": tmp, "title": f"Auszug aus dem Bericht (Seite {pg})", "page": pg, "shows": "Tabelle oder Folie aus dem Bericht mit Zahlen zum Thema"}
            out.setdefault("figures", [])
        print(f"::notice title=IR-Agent::Ausschnitte: {len(figs)} von {len(out.get('figures') or [])} gerendert, Diagramm: {'ja' if (out.get('chart') or {}).get('bars') else 'nein'}, Quelle: {src['kind']}")
        if figs:
            prompt2 += "\n\nVERFUEGBARE AUSSCHNITTE AUS DEM BERICHT (Bilder; setze hoechstens drei davon ein):\n" + "\n".join(
                f"- {fid}: {f['title']} | {f['shows']}" for fid, f in figs.items())
        out["article"] = clean_article(_generate([doc_part(src), {"text": prompt2}], ARTICLE_SCHEMA, api_key()))
        if bg_src:
            out["article"]["body_markdown"] = out["article"]["body_markdown"].rstrip() + "\n\nWeitere Quellen zum Hintergrund: " + " · ".join(f"[{(ti or u)[:60]}]({u})" for ti, u in bg_src) + "\n"
        print("FAKTEN:\n" + fakten)
    note = src.get("url") or ""
    md, g, bad, photo = build(out, text, note, a.force, calc_rows, fmp_used, figs if not a.mock else None, src)
    print("Entwurf:", md); print("Grafik:", g); print("Foto:", photo["title"] if photo else "keins")
    print("Nicht verifizierte Zahlen:", bad if bad else "keine")


if __name__ == "__main__":
    main()
