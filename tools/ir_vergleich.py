#!/usr/bin/env python3
"""IR-Vergleich: mehrere Berichte (Peer Group oder Lieferkette) -> ein Vergleichsartikel als Entwurf.

Aufruf:  python3 tools/ir_vergleich.py --src ticker:BA --src ticker:AIR.PA --src url:https://... --src datei.pdf --fokus "Triebwerkshersteller und Airbus"
Nutzt die Funktionen aus ir_agent.py (Berichte holen, Zahlen lesen, Gemini) und schreibt den Entwurf nach content/magazin (draft: true)."""
import argparse, glob, json, os, re, sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir_agent as ia

ARTICLE_SCHEMA = {
    "type": "OBJECT", "required": ["title", "description", "slug", "body_markdown", "table", "chart"],
    "properties": {
        "chart": {"type": "OBJECT", "required": ["title", "unit", "series"], "properties": {
            "title": {"type": "STRING"}, "unit": {"type": "STRING"},
            "series": {"type": "ARRAY", "items": {"type": "OBJECT", "required": ["name", "values"], "properties": {
                "name": {"type": "STRING"},
                "values": {"type": "ARRAY", "items": {"type": "OBJECT", "required": ["company", "value"], "properties": {
                    "company": {"type": "STRING"}, "value": {"type": "NUMBER"}}}}}}}}},
        "chart2": {"type": "OBJECT", "required": ["title", "unit", "series"], "properties": {
            "title": {"type": "STRING"}, "unit": {"type": "STRING"},
            "series": {"type": "ARRAY", "items": {"type": "OBJECT", "required": ["name", "values"], "properties": {
                "name": {"type": "STRING"},
                "values": {"type": "ARRAY", "items": {"type": "OBJECT", "required": ["company", "value"], "properties": {
                    "company": {"type": "STRING"}, "value": {"type": "NUMBER"}}}}}}}}},
        "title": {"type": "STRING"}, "description": {"type": "STRING"}, "slug": {"type": "STRING"}, "body_markdown": {"type": "STRING"},
        "table": {"type": "OBJECT", "required": ["rows"], "properties": {"rows": {"type": "ARRAY", "items": {
            "type": "OBJECT", "required": ["metric", "values"], "properties": {
                "metric": {"type": "STRING"},
                "values": {"type": "ARRAY", "items": {"type": "OBJECT", "required": ["company", "value"], "properties": {
                    "company": {"type": "STRING"}, "value": {"type": "STRING"}}}}}}}}},
    },
}


def lade(spec, art):
    """Eine Quelle (ticker:XX, url:..., Dateipfad) in {src, out, text}."""
    if spec.startswith("ticker:"):
        src = ia.sec_release(spec[7:], art)
    elif spec.startswith("url:"):
        src = ia.web_source(spec[4:])
    else:
        src = {"kind": "pdf", "path": spec, "url": "", "date": ""}
    if not src:
        return None
    text = ia.pdf_text(src["path"]) if src["kind"] == "pdf" else src["text"]
    out = ia.call_gemini(src, ia.read_prompt("ir_prompt.md"))
    if spec.startswith("ticker:") and not out.get("ticker"):
        out["ticker"] = spec[7:].upper()
    return {"src": src, "out": out, "text": text}


def netto(entries):
    """Free Cashflow und Nettoverschuldung je Unternehmen (eigene Berechnung aus den Angaben der Berichte)."""
    rows = []
    for e in entries:
        o = e["out"]; cf = o.get("cashflow") or {}; bl = o.get("balance") or {}
        u = cf.get("unit") or "Mio."
        fcf = nd = ""
        if cf.get("operating_cash_flow") is not None and cf.get("capex") is not None:
            fcf = f"{ia.de(cf['operating_cash_flow'] - cf['capex'], 1 if 'Mrd' in u else 0)} {u}"
        if bl.get("cash") is not None and (bl.get("short_term_debt") is not None or bl.get("long_term_debt") is not None):
            bu = bl.get("unit") or "Mio."
            nd = f"{ia.de((bl.get('short_term_debt') or 0) + (bl.get('long_term_debt') or 0) - bl['cash'], 1 if 'Mrd' in bu else 0)} {bu}"
        rows.append((o["company"], cf.get("period_label") or "Berichtszeitraum", fcf or "–", nd or "–"))
    return rows


def pruefen_werte(table, entries):
    """Jede Tabellenzelle muss in den extrahierten Kennzahlen des Unternehmens vorkommen."""
    bad = []
    daten = {e["out"]["company"]: json.dumps(e["out"], ensure_ascii=False) for e in entries}
    for r in table.get("rows", []):
        for v in r.get("values", []):
            val = (v.get("value") or "").strip()
            if val in ("", "–", "-"):
                continue
            blob = daten.get(v.get("company"), "")
            if val not in blob and ia.digits(val) not in ia.digits(blob):
                bad.append(f"{r['metric']} / {v.get('company')}: {val}")
    return bad


def tabelle_md(table, entries):
    namen = [e["out"]["company"] for e in entries]
    zeilen = []
    for r in table.get("rows", []):
        wert = {v.get("company"): (v.get("value") or "–") for v in r.get("values", [])}
        zeilen.append(f"| {r['metric']} | " + " | ".join(wert.get(n, "–") for n in namen) + " |")
    if not zeilen:
        return ""
    return "| Kennzahl | " + " | ".join(namen) + " |\n|---|" + "---|" * len(namen) + "\n" + "\n".join(zeilen) + "\n"


def draw_vergleich(chart, path):
    """Gruppiertes Balkendiagramm: je Unternehmen eine Gruppe, je Reihe ein Balken (Hub-Farben)."""
    from PIL import Image, ImageDraw
    series = [x for x in (chart.get("series") or []) if x.get("values")][:3]
    firms = []
    for x in series:
        for v in x["values"]:
            if v["company"] not in firms: firms.append(v["company"])
    if not series or len(firms) < 2:
        return False
    W, H = 1600, 900
    im = Image.new("RGB", (W, H), "#ffffff"); d = ImageDraw.Draw(im)
    cols = ["#2f6fdb", "#1f9d55", "#0e9aa7"]; red = "#c0392b"; dark, grey = "#14202b", "#5d6b78"
    d.rectangle([0, 0, W, 16], fill="#2f9e5b")
    d.text((70, 50), chart.get("title") or "Vergleich", font=ia.font(34, True), fill=dark)
    d.text((70, 96), chart.get("unit") or "", font=ia.font(22), fill=grey)
    # Legende
    lx = 70
    for i, x in enumerate(series):
        d.rounded_rectangle([lx, 150, lx + 26, 176], 5, fill=cols[i]); d.text((lx + 38, 148), x["name"], font=ia.font(24), fill=dark)
        lx += 60 + int(d.textlength(x["name"], font=ia.font(24)))
    allv = [v["value"] for x in series for v in x["values"]] + [0]
    vmax, vmin = max(allv), min(allv); span = (vmax - vmin) or 1
    top, bot, left, right = 230, H - 150, 70, W - 70
    zero = bot - (0 - vmin) / span * (bot - top)
    gw = (right - left) / len(firms)
    d.line([left, zero, right, zero], fill="#c9d3dc", width=2)
    bw = gw * 0.72 / len(series)
    for gi, f in enumerate(firms):
        gx = left + gi * gw + gw * 0.14
        for si, x in enumerate(series):
            val = next((v["value"] for v in x["values"] if v["company"] == f), None)
            if val is None: continue
            x0 = gx + si * bw + 6; x1 = gx + (si + 1) * bw - 6
            yv = zero - val / span * (bot - top)
            y0, y1 = (yv, zero) if val >= 0 else (zero, yv)
            d.rounded_rectangle([x0, y0, x1, max(y1, y0 + 2)], 6, fill=cols[si] if val >= 0 else red)
            t = ("%g" % val).replace(".", ","); tf = ia.font(26, True)
            d.text(((x0 + x1) / 2 - d.textlength(t, font=tf) / 2, (y0 - 36) if val >= 0 else (y1 + 6)), t, font=tf, fill=dark)
        lf = ia.font(26, True)
        d.text((gx + gw * 0.36 - d.textlength(f, font=lf) / 2, bot + 24), f, font=lf, fill=dark)
    d.text((70, H - 50), "Quelle: Unternehmensberichte, eigene Darstellung  ·  dividenden-rechner.de", font=ia.font(22), fill=grey)
    im.save(path, "PNG", optimize=True)
    return True


def cash_chart(entries):
    """Free Cashflow und Nettoverschuldung als Diagramm (rein rechnerisch aus den Berichten; nur bei gleicher Einheit)."""
    fc, nd, unit_f, unit_n = [], [], set(), set()
    for e in entries:
        o = e["out"]; cf = o.get("cashflow") or {}; bl = o.get("balance") or {}
        if cf.get("operating_cash_flow") is not None and cf.get("capex") is not None:
            fc.append({"company": o["company"], "value": round(cf["operating_cash_flow"] - cf["capex"], 1)}); unit_f.add(cf.get("unit") or "Mio.")
        if bl.get("cash") is not None and (bl.get("short_term_debt") is not None or bl.get("long_term_debt") is not None):
            nd.append({"company": o["company"], "value": round((bl.get("short_term_debt") or 0) + (bl.get("long_term_debt") or 0) - bl["cash"], 1)}); unit_n.add(bl.get("unit") or "Mio.")
    series = []
    if len(fc) >= 2 and len(unit_f) == 1: series.append({"name": "Free Cashflow", "values": fc})
    if len(nd) >= 2 and len(unit_n) == 1 and unit_n == unit_f: series.append({"name": "Nettoverschuldung", "values": nd})
    if not series and len(nd) >= 2 and len(unit_n) == 1: series.append({"name": "Nettoverschuldung", "values": nd}); unit_f = unit_n
    if not series: return None
    return {"title": "Cashflow und Schulden im Vergleich", "unit": "Angaben in " + (next(iter(unit_f)) if unit_f else "Mio.") + " (Währung wie im Bericht, nicht umgerechnet)", "series": series}


def combo_logo(entries, slug):
    """Logos der Unternehmen als leicht ueberlappende Plaketten in einer PNG-Datei (assets/logos/combo-<slug>.png)."""
    import io
    from PIL import Image, ImageDraw, ImageFilter
    import fetch_logos as fl
    tiles = []
    for e in entries[:3]:
        o = e["out"]; tk = re.sub(r"[^A-Za-z0-9.\-]", "", o.get("ticker") or "")
        dom = re.sub(r"^(https?://)?(www\.)?|/.*$", "", (o.get("website_domain") or "").lower())
        png = None
        for fn, arg in ((fl.from_fmp, tk), (fl.from_site, dom), (fl.from_google, dom), (fl.from_ddg, dom)):
            try: png = fn(arg)
            except Exception: png = None
            if png: break
        if png: tiles.append(Image.open(io.BytesIO(png)).convert("RGBA"))
        else: tiles.append(Image.open(io.BytesIO(fl.monogram(o["company"]))).convert("RGBA"))
    S, step, pad = 104, 70, 12
    W, H = S + step * (len(tiles) - 1) + 2 * pad, S + 2 * pad
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for i, lg in enumerate(tiles):
        x = pad + i * step
        px = [q for q in lg.resize((48, 48)).getdata() if q[3] > 128]
        lum = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b, a in px) / len(px) if px else 0
        bg = "#14202b" if lum > 215 else "#ffffff"
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([x, pad + 4, x + S, pad + 4 + S], 24, fill=(0, 0, 0, 80))
        out = Image.alpha_composite(out, sh.filter(ImageFilter.GaussianBlur(5)))
        tile = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(tile)
        d.rounded_rectangle([x, pad, x + S, pad + S], 24, fill=bg, outline="#ffffff" if i else None, width=4)
        inner = lg.resize((S - 28, S - 28), Image.LANCZOS); tile.paste(inner, (x + 14, pad + 14), inner)
        out = Image.alpha_composite(out, tile)
    rel = f"assets/logos/combo-{slug}.png"
    os.makedirs(os.path.join(ia.ROOT, "assets", "logos"), exist_ok=True)
    out.save(os.path.join(ia.ROOT, rel), "PNG", optimize=True)
    return rel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", action="append", default=[], help="ticker:KO, url:https://..., oder Pfad zu einer PDF (mehrfach)")
    ap.add_argument("--dir", help="Ordner mit PDFs (alle PDFs darin werden verglichen)")
    ap.add_argument("--fokus", default="")
    ap.add_argument("--art", default=os.environ.get("ART") or "ergebnisse")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    specs = [x for x in a.src if not x.startswith("url:") or x[4:].startswith("http")]
    if a.dir:
        specs += sorted(glob.glob(os.path.join(a.dir, "*.pdf")))
    if len(specs) < 2:
        ia.fail("Fuer einen Vergleich werden mindestens zwei Berichte gebraucht (--src mehrfach oder --dir).")
    key = ia.api_key()
    entries = []
    for s_ in specs:
        try:
            e = lade(s_, a.art)
        except SystemExit:
            e = None
        if e:
            if e["src"]["kind"] == "pdf":   # eigene Kopie, damit spaetere Quellen sie nicht ueberschreiben
                import shutil
                cp = f"/tmp/vg{len(entries) + 1}.pdf"; shutil.copy(e["src"]["path"], cp); e["src"]["path"] = cp
            entries.append(e); print("Gelesen:", e["out"].get("company"), e["out"].get("period"))
        else:
            print(f"::warning::Quelle {s_} konnte nicht gelesen werden, wird uebersprungen.")
    if len(entries) < 2:
        ia.fail("Weniger als zwei Berichte lesbar, kein Vergleich moeglich.")
    namen = [e["out"]["company"] for e in entries]
    # Hintergrund: je Unternehmen (letzte Quartale und Jahre) und Markt/Politik
    hint = ""; weitere = []
    for i, e in enumerate(entries):
        try:
            t, srcs = ia.research(e["out"], key)
        except SystemExit:
            t, srcs = "", []
        if t:
            hint += f"\n\nHINTERGRUND {e['out']['company']}:\n{t[:7000]}"
            weitere += srcs[:4]
    try:
        mt, ms = ia.ground(("Recherchiere mit der Websuche fuer einen Vergleichsartikel ueber " + ", ".join(namen) + (f" (Thema: {a.fokus})" if a.fokus.strip() else "") +
                            ". Liefere knappe Stichpunkte auf Deutsch mit Zahlen und Zeitangaben zu: 1. Lage und Nachfrage in der Branche, aktuelle Marktentwicklung (Preise, Lieferketten, Auftragslage, Bewertung der Branche). "
                            "2. Geopolitik und Regulierung (Zoelle, Sanktionen, Konflikte, Genehmigungen), die diese Unternehmen unterschiedlich treffen. 3. Konjunktur, Zinsen, Waehrungen. "
                            "4. Wie die Prognosen (Guidance) der Unternehmen von Analysten eingeschaetzt werden. Sachlich und kritisch, Chancen und Risiken. Erfinde nichts, lass Unbelegtes weg."), key)
    except SystemExit:
        mt, ms = "", []
    if mt:
        hint += "\n\nMARKT UND POLITIK:\n" + mt[:8000]; weitere += ms[:6]
    # Ausschnitte aus den Berichten
    os.makedirs("/tmp/vfigs", exist_ok=True); figs = {}
    for e in entries:
        if e["src"]["kind"] == "pdf" and len(e["out"].get("figures") or []) < 2:
            try:
                extra = ia._generate([ia.doc_part(e["src"]), {"text": ia.FIG_PROMPT + f"\n\nUnternehmen: {e['out'].get('company')}, Branche: {e['out'].get('industry') or 'unbekannt'}."}], ia.FIG_SCHEMA, key)
                if extra.get("figures"): e["out"]["figures"] = (e["out"].get("figures") or []) + [f for f in extra["figures"] if f not in (e["out"].get("figures") or [])]
            except SystemExit:
                print("::notice title=IR-Vergleich::Gezielte Suche nach Ausschnitten fehlgeschlagen.")
    for i, e in enumerate(entries, 1):
        if e["src"]["kind"] != "pdf": continue
        for j, fg in enumerate((e["out"].get("figures") or [])[:4], 1):
            fid = f"c{i}f{j}"; tmp = f"/tmp/vfigs/{fid}.png"
            if ia.render_figure(e["src"]["path"], fg, tmp):
                figs[fid] = {"tmp": tmp, "title": fg.get("title") or "Auszug", "page": fg.get("page"), "shows": fg.get("shows") or "", "company": e["out"]["company"], "e": e}
    daten = [{k: e["out"].get(k) for k in ("company", "ticker", "report_type", "industry", "period", "report_date", "period_end", "prior_period_end", "kpis", "cashflow", "balance", "details")} for e in entries]
    fakten = "\n".join(f"- {n}: Free Cashflow ({per}) {f}; Nettoverschuldung {nd} (eigene Berechnung aus Angaben des Berichts)" for n, per, f, nd in netto(entries))
    prompt = (ia.read_prompt("ir_vergleich_prompt.md") + (f"\n\nFOKUS DES REDAKTEURS: {a.fokus}" if a.fokus.strip() else "")
              + "\n\nFAKTEN (vom Programm berechnet, exakt uebernehmen):\n" + fakten
              + "\n\nEXTRAHIERTE KENNZAHLEN JE UNTERNEHMEN (JSON):\n" + json.dumps(daten, ensure_ascii=False) + hint
              + ("\n\nAUSSCHNITTE (Bilder aus den Berichten):\n" + "\n".join(f"- {k}: {v['company']}: {v['title']} | {v['shows']}" for k, v in figs.items()) if figs else ""))
    parts = [{"text": f"BERICHT {e['out']['company']} ({e['out'].get('report_type') or ''} {e['out'].get('period') or ''}):\n\n{(e['text'] or '')[:140000]}"} for e in entries] + [{"text": prompt}]
    art = ia.clean_article(ia._generate(parts, ARTICLE_SCHEMA, key))
    bad = pruefen_werte(art.get("table") or {}, entries)
    # Diagramm pruefen und zeichnen
    slug = re.sub(r"[^a-z0-9]+", "-", art["slug"].lower()).strip("-") or "vergleich"
    chart = art.get("chart") or {}
    toks = set()
    for d_ in daten:
        for k in d_.get("kpis") or []:
            for fld in ("value", "change"):
                for n in re.findall(r"\d+(?:[.,]\d+)?", k.get(fld) or ""):
                    toks.add(n.replace(",", ".").rstrip("0").rstrip(".") if "." in n.replace(",", ".") else n)
    def belegt(x):
        t = ("%g" % abs(x)); return t in toks
    for ser in chart.get("series") or []:
        ser["values"] = [v for v in ser.get("values") or [] if belegt(v["value"])]
    chart2 = art.get("chart2") or {}
    for ser in chart2.get("series") or []:
        ser["values"] = [v for v in ser.get("values") or [] if belegt(v["value"])]
    gpath = os.path.join(ia.ROOT, "assets", "magazin", f"{slug}-vergleich.png")
    os.makedirs(os.path.dirname(gpath), exist_ok=True)
    has_chart = draw_vergleich(chart, gpath)
    g2path = os.path.join(ia.ROOT, "assets", "magazin", f"{slug}-vergleich2.png")
    has_chart2 = draw_vergleich(chart2, g2path) if chart2 else False
    cchart = cash_chart(entries)
    cpath = os.path.join(ia.ROOT, "assets", "magazin", f"{slug}-cash.png")
    has_cash = draw_vergleich(cchart, cpath) if cchart else False
    # Schreiben
    stamp = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d-%H%M")
    vorh = [v for v in glob.glob(os.path.join(ia.ROOT, "content", "magazin", f"*{slug}.md"))
            if re.fullmatch(r"(\d{4}-\d{2}-\d{2}(-\d{4})?-)?" + re.escape(slug) + r"\.md", os.path.basename(v))]
    md = vorh[0] if vorh else os.path.join(ia.ROOT, "content", "magazin", f"{stamp}-{slug}.md")
    if os.path.exists(md) and not a.force:
        ia.fail(f"Es gibt schon einen Artikel '{slug}.md'. Datei vorher loeschen oder --force nutzen.")
    first = entries[0]["out"]
    tk = re.sub(r"[^A-Za-z0-9.\-]", "", first.get("ticker") or "")
    dom = re.sub(r"^(https?://)?(www\.)?|/.*$", "", first.get("website_domain") or "")
    fm = ["---", f"title: {ia.q(art['title'])}", f"description: {ia.q(art['description'])}",
          f"date: {datetime.now(ZoneInfo('Europe/Berlin')).strftime('%Y-%m-%d %H:%M')}", f"author: {ia.q(ia.CFG['author'])}",
          f"author_bio: {ia.q(ia.CFG['author_bio'])}", "category: Branchenvergleich"]
    hinweise = []
    photo = None
    try:
        photo = ia.pick_photo_topic(namen, a.fokus, first.get("industry") or "", key)
        if not photo:
            photo = ia.pick_photo(first["company"], first.get("ticker", ""), key)
    except Exception as ex:
        print("Foto-Suche fehlgeschlagen:", ex)
    if photo:
        rel = ia.save_photo(photo, slug)
        fm += [f"image: {rel}", f"image_alt: {ia.q('Foto zum Thema ' + ' und '.join(namen) + ': ' + (photo['desc'] or photo['title'].replace('File:', '')))}",
               f"image_credit: {ia.q('Foto: ' + photo['artist'] + ' / Wikimedia Commons, ' + photo['lic'])}", f"image_source: {photo['page']}"]
        hinweise.append("Aufmacherfoto ist automatisch von Wikimedia Commons zum Thema gewaehlt: bitte pruefen, ob es zum Vergleich passt.")
    else:
        hinweise.append("Kein freies Aufmacherfoto gefunden, das Titelbild entsteht automatisch. Eigenes Foto: image, image_alt, image_credit ergaenzen.")
    fm.append("logo_name: " + ia.q(first["company"]))
    if tk: fm.append(f"logo_symbol: {tk}")
    if dom and re.match(r"^[a-z0-9.\-]+\.[a-z]{2,}$", dom, re.I): fm.append(f"logo_domain: {dom}")
    try:
        fm.append("logo_file: " + combo_logo(entries, slug))
    except Exception as ex:
        print("Gemeinsames Logo nicht erstellt:", ex)
    fm += ["draft: true", "---", ""]
    hinweise.insert(0, "Vergleichsartikel: Kasten, Tabelle, Diagramm und Aussagen bitte gegen die Berichte pruefen; Hintergrundaussagen stammen aus einer Websuche.")
    if bad:
        hinweise.append("Diese Tabellenwerte stehen nicht woertlich in den ausgelesenen Kennzahlen: " + "; ".join(bad))
    quellen = []
    for e in entries:
        o = e["out"]; link = e["src"].get("url", "")
        quellen.append(f"{o['company']}, {o.get('report_type') or 'Bericht'} {o.get('period') or ''}".strip() + (f" ([Link]({link}))" if link.startswith("http") else ""))
    hinweise.append("Quellen: " + "; ".join(quellen))
    tab = tabelle_md(art.get("table") or {}, entries)
    body = art["body_markdown"].strip()
    if "{{TABELLE}}" in body:
        body = body.replace("{{TABELLE}}", "## Die Zahlen im Vergleich\n\n" + tab + "\n*Werte aus den jeweiligen Berichten, nicht umgerechnet; Zeiträume und Rechnungslegung können abweichen.*\n")
    elif tab:
        body += "\n\n## Die Zahlen im Vergleich\n\n" + tab
    gtxt = f"![{chart.get('title') or 'Vergleich'}](/assets/magazin/{slug}-vergleich.png)\n*Eigene Darstellung nach Daten aus den Berichten ({', '.join(namen)}).*"
    if has_chart:
        if "{{GRAFIK}}" in body: body = body.replace("{{GRAFIK}}", gtxt)
        else:
            m_ = re.search(r"## Die ausführliche Version\n+(?:###[^\n]*\n+)?[^\n]+\n", body)
            body = (body[:m_.end()] + "\n" + gtxt + "\n" + body[m_.end():]) if m_ else body + "\n\n" + gtxt
    body = body.replace("{{GRAFIK}}", "")
    def bild(path_key, title, has, marker, alt_after):
        nonlocal body
        if not has: body = body.replace(marker, ""); return
        txt = f"![{title}](/assets/magazin/{slug}-{path_key}.png)\n*Eigene Darstellung nach Daten aus den Berichten ({', '.join(namen)}).*"
        if marker in body: body = body.replace(marker, txt)
        else:
            m_ = re.search(alt_after, body)
            body = (body[:m_.start()] + txt + "\n\n" + body[m_.start():]) if m_ else body + "\n\n" + txt
    bild("vergleich2", chart2.get("title") or "Vergleich", has_chart2, "{{GRAFIK2}}", r"\n###? [^\n]*(Ausblick|Prognose|Chancen)[^\n]*\n")
    bild("cash", (cchart or {}).get("title") or "Cashflow", has_cash, "{{CASHGRAFIK}}", r"\n###? [^\n]*(Ausblick|Prognose|Chancen)[^\n]*\n")
    used = []
    import shutil
    for fid, f in figs.items():
        tag = "{{FIG:" + fid + "}}"
        if tag in body:
            rel = f"assets/magazin/{slug}-{fid}.png"; shutil.copy(f["tmp"], os.path.join(ia.ROOT, rel)); used.append(fid)
            o = f["e"]["out"]; link = f["e"]["src"].get("url", ""); lk = f" · [Original]({link})" if link.startswith("http") else ""
            pg = f.get("page") if f["e"]["src"].get("pages_real", True) and f.get("page") else None
            body = body.replace(tag, f"![{f['title'].replace('[', '(').replace(']', ')')}](/{rel})\n*{f['title']}. Quelle: {o['company']}, {o.get('report_type') or 'Bericht'} {o.get('period') or ''}" + (f", S. {pg}" if pg else "") + f"{lk}. Ausschnitt nur zugeschnitten, sonst unverändert.*")
    body = re.sub(r"\{\{FIG:[^}]*\}\}", "", body)
    if used: hinweise.append("Ausschnitte aus den Berichten im Text (" + ", ".join(used) + "): bitte Zuschnitt und Platz pruefen, unpassende Bildzeilen loeschen.")
    nd = netto(entries)
    if any(f != "–" or n != "–" for _, _, f, n in nd):
        body += "\n\n## Cashflow und Schulden im Vergleich\n\n| Unternehmen | Free Cashflow | Nettoverschuldung |\n|---|---|---|\n" + "\n".join(f"| {c} | {f} ({p}) | {n} |" for c, p, f, n in nd) + "\n\n*Free Cashflow = operativer Cashflow minus Investitionen, Nettoverschuldung = Finanzschulden minus liquide Mittel. Eigene Berechnung aus Angaben der Berichte.*\n"
    if weitere:
        seen = []; [seen.append(x) for x in weitere if x[1] not in [y[1] for y in seen]]
        body += "\nWeitere Quellen zum Hintergrund: " + " · ".join(f"[{(ti or u)[:60]}]({u})" for ti, u in seen[:8]) + "\n"
    body += "\n*Quellen: " + "; ".join(re.sub(r"\s*\(\[Link\]\([^)]*\)\)", "", q) for q in quellen) + ". Keine Anlageberatung.*\n"
    head = "".join(f"<!-- PRÜFEN: {h} -->\n" for h in hinweise) + "\n"
    open(md, "w", encoding="utf-8").write("\n".join(fm) + head + body + "\n")
    print("Entwurf:", md); print("Nicht verifizierte Tabellenwerte:", bad if bad else "keine"); print("Diagramm:", "ja" if has_chart else "nein", "· Ausschnitte:", ", ".join(used) or "keine")


if __name__ == "__main__":
    main()
