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
    "type": "OBJECT", "required": ["title", "description", "slug", "body_markdown", "table"],
    "properties": {
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", action="append", default=[], help="ticker:KO, url:https://..., oder Pfad zu einer PDF (mehrfach)")
    ap.add_argument("--dir", help="Ordner mit PDFs (alle PDFs darin werden verglichen)")
    ap.add_argument("--fokus", default="")
    ap.add_argument("--art", default=os.environ.get("ART") or "ergebnisse")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    specs = list(a.src)
    if a.dir:
        specs += sorted(glob.glob(os.path.join(a.dir, "*.pdf")))
    if len(specs) < 2:
        ia.fail("Fuer einen Vergleich werden mindestens zwei Berichte gebraucht (--src mehrfach oder --dir).")
    entries = []
    for s in specs:
        try:
            e = lade(s, a.art)
        except SystemExit:
            e = None
        if e:
            entries.append(e); print("Gelesen:", e["out"].get("company"), e["out"].get("period"))
        else:
            print(f"::warning::Quelle {s} konnte nicht gelesen werden, wird uebersprungen.")
    if len(entries) < 2:
        ia.fail("Weniger als zwei Berichte lesbar, kein Vergleich moeglich.")
    daten = [{k: e["out"].get(k) for k in ("company", "ticker", "report_type", "industry", "period", "report_date", "period_end", "prior_period_end", "kpis", "cashflow", "balance", "details")} for e in entries]
    fakten = "\n".join(f"- {n}: Free Cashflow ({per}) {f}; Nettoverschuldung {nd} (eigene Berechnung aus Angaben des Berichts)" for n, per, f, nd in netto(entries))
    prompt = (ia.read_prompt("ir_vergleich_prompt.md") + (f"\n\nFOKUS DES REDAKTEURS: {a.fokus}" if a.fokus.strip() else "")
              + "\n\nFAKTEN (vom Programm berechnet, exakt uebernehmen):\n" + fakten
              + "\n\nEXTRAHIERTE KENNZAHLEN JE UNTERNEHMEN (JSON):\n" + json.dumps(daten, ensure_ascii=False))
    art = ia._generate([{"text": prompt}], ARTICLE_SCHEMA, ia.api_key())
    bad = pruefen_werte(art.get("table") or {}, entries)
    # Schreiben
    slug = re.sub(r"[^a-z0-9]+", "-", art["slug"].lower()).strip("-") or "vergleich"
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
          f"author_bio: {ia.q(ia.CFG['author_bio'])}", "category: Branchenvergleich", "logo_name: " + ia.q(first["company"])]
    if tk: fm.append(f"logo_symbol: {tk}")
    if dom and re.match(r"^[a-z0-9.\-]+\.[a-z]{2,}$", dom, re.I): fm.append(f"logo_domain: {dom}")
    fm += ["draft: true", "---", ""]
    hinweise = ["Vergleichsartikel: Kasten, Tabelle und Aussagen bitte gegen die Berichte pruefen. Titelbild entsteht automatisch (Logo: " + first["company"] + "); eigenes Foto: image, image_alt, image_credit ergaenzen."]
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
    nd = netto(entries)
    if any(f != "–" or n != "–" for _, _, f, n in nd):
        body += "\n\n## Cashflow und Schulden im Vergleich\n\n| Unternehmen | Free Cashflow | Nettoverschuldung |\n|---|---|---|\n" + "\n".join(f"| {c} | {f} ({p}) | {n} |" for c, p, f, n in nd) + "\n\n*Free Cashflow = operativer Cashflow minus Investitionen, Nettoverschuldung = Finanzschulden minus liquide Mittel. Eigene Berechnung aus Angaben der Berichte.*\n"
    body += "\n*Quellen: " + "; ".join(re.sub(r"\s*\(\[Link\]\([^)]*\)\)", "", q) for q in quellen) + ". Keine Anlageberatung.*\n"
    head = "".join(f"<!-- PRÜFEN: {h} -->\n" for h in hinweise) + "\n"
    open(md, "w", encoding="utf-8").write("\n".join(fm) + head + body + "\n")
    print("Entwurf:", md); print("Nicht verifizierte Tabellenwerte:", bad if bad else "keine")


if __name__ == "__main__":
    main()
