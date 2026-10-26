#!/usr/bin/env python3
"""IR-Agent: Quartalsbericht (PDF) -> Kennzahlen (JSON) -> Grafik (PNG) + Artikelentwurf (Markdown).

Aufruf:
  python3 tools/ir_agent.py content/ir-inbox/bericht.pdf        # echter Lauf (braucht GEMINI_API_KEY)
  python3 tools/ir_agent.py bericht.pdf --mock antwort.json     # Test ohne API (fertige Modell-Antwort)

Der Entwurf landet mit `draft: true` in content/magazin/. Nichts wird veroeffentlicht,
bevor du `draft: true` entfernst. Zahlen werden gegen den PDF-Text geprueft.
"""
import argparse, base64, json, os, re, subprocess, sys, time, urllib.request, urllib.error
from datetime import date
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "tools", "ir_config.json"), encoding="utf-8"))
MODEL = os.environ.get("GEMINI_MODEL") or CFG.get("model", "gemini-2.5-flash")

SCHEMA = {
    "type": "OBJECT",
    "required": ["company", "period", "report_date", "kpis", "chart", "article"],
    "properties": {
        "company": {"type": "STRING"}, "ticker": {"type": "STRING"},
        "period": {"type": "STRING", "description": "z. B. Q2 2026"},
        "report_date": {"type": "STRING", "description": "YYYY-MM-DD"},
        "kpis": {"type": "ARRAY", "items": {"type": "OBJECT",
            "required": ["label", "value", "page"],
            "properties": {"label": {"type": "STRING"}, "value": {"type": "STRING", "description": "Wert exakt wie im Bericht, z. B. 13,4 Mrd. USD"},
                           "change": {"type": "STRING", "description": "Veraenderung zum Vorjahr, z. B. +7 %"},
                           "page": {"type": "INTEGER"}}}},
        "chart": {"type": "OBJECT", "required": ["title", "unit", "bars", "page"],
            "properties": {"title": {"type": "STRING"}, "unit": {"type": "STRING"}, "page": {"type": "INTEGER"},
                           "bars": {"type": "ARRAY", "items": {"type": "OBJECT", "required": ["label", "value"],
                               "properties": {"label": {"type": "STRING"}, "value": {"type": "NUMBER"}}}}}},
        "article": {"type": "OBJECT", "required": ["title", "description", "slug", "body_markdown"],
            "properties": {"title": {"type": "STRING"}, "description": {"type": "STRING"}, "slug": {"type": "STRING"},
                           "body_markdown": {"type": "STRING"}}},
    },
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


def call_gemini(pdf_path, prompt):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        fail("GEMINI_API_KEY fehlt (GitHub: Settings > Secrets and variables > Actions).")
    data = open(pdf_path, "rb").read()
    if len(data) > 18 * 1024 * 1024:
        fail("PDF ist groesser als 18 MB, bitte kuerzen.")
    body = {
        "contents": [{"parts": [{"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(data).decode()}}, {"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json", "responseSchema": SCHEMA},
    }
    last = ""
    for model in candidate_models(key):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
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
                res = None
                break
            except Exception as e:
                last = f"{model}: {e}"; print("Modell-Problem ->", last)
                res = None
                break
        if res is None:
            continue
        try:
            out = json.loads(res["candidates"][0]["content"]["parts"][0]["text"])
            print("Modell:", model)
            return out
        except Exception:
            last = f"{model}: unerwartete Antwort " + json.dumps(res)[:300]
            continue
    fail("Kein Gemini-Modell hat funktioniert. Letzter Fehler: " + last)


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
    for b in out["chart"]["bars"]:
        n = ("%g" % b["value"])
        if not any(c in flat_raw for c in {n, n.replace(".", ",")}):
            bad.append(f"Grafik {b['label']}: {n}")
    return bad if text else None


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


def build(pdf_path, out, text):
    slug = re.sub(r"[^a-z0-9]+", "-", out["article"]["slug"].lower()).strip("-") or "bericht"
    gpath = os.path.join(ROOT, "assets", "magazin", f"{slug}-grafik.png")
    os.makedirs(os.path.dirname(gpath), exist_ok=True)
    draw_graphic(out, gpath)
    bad = check_numbers(out, text)
    a = out["article"]
    rows = "\n".join(f"| {k['label']} | {k['value']} | {k.get('change') or '–'} | S. {k['page']} |" for k in out["kpis"])
    desc = a["description"].replace('"', "'")
    fm = [
        "---", f"title: {q(a['title'])}", f"description: {q(desc)}",
        f"date: {date.today().isoformat()} 08:00", f"author: {q(CFG['author'])}", f"author_bio: {q(CFG['author_bio'])}",
        f"category: {CFG.get('category', 'Zahlen')}", f"image: assets/magazin/{slug}-grafik.png",
        f"image_alt: {q('Grafik: ' + out['chart']['title'] + ' bei ' + out['company'] + ' (' + out['period'] + ')')}", "draft: true", "---", "",
    ]
    prüf = ""
    if bad:
        prüf = "<!-- PRÜFEN: Diese Werte wurden im PDF-Text nicht gefunden: " + "; ".join(bad) + " -->\n\n"
    elif bad is None:
        prüf = "<!-- PRÜFEN: PDF-Text nicht lesbar, Zahlen nicht automatisch geprüft -->\n\n"
    body = (prüf + a["body_markdown"].strip() + "\n\n## Die wichtigsten Zahlen im Überblick\n\n"
            "| Kennzahl | Wert | Veränderung zum Vorjahr | Quelle |\n|---|---|---|---|\n" + rows + "\n\n"
            f"*Quelle: {out['company']}, Pressemitteilung zum {out['period']} vom {out['report_date']}. Keine Anlageberatung.*\n")
    mdpath = os.path.join(ROOT, "content", "magazin", f"{slug}.md")
    open(mdpath, "w", encoding="utf-8").write("\n".join(fm) + body)
    return mdpath, gpath, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("--mock")
    a = ap.parse_args()
    text = pdf_text(a.pdf)
    if a.mock:
        out = json.load(open(a.mock, encoding="utf-8"))
    else:
        prompt = open(os.path.join(ROOT, "tools", "ir_prompt.md"), encoding="utf-8").read()
        out = call_gemini(a.pdf, prompt)
    md, g, bad = build(a.pdf, out, text)
    print("Entwurf:", md); print("Grafik:", g)
    print("Nicht verifizierte Zahlen:", bad if bad else "keine")


if __name__ == "__main__":
    main()
