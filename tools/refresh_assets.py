#!/usr/bin/env python3
"""Neues Titelfoto (und korrigiertes Logo) fuer einen vorhandenen Artikel.

Aufruf:  python3 tools/refresh_assets.py <artikel-kennung> [--terms "a,b,c"] [--symbol SBUX] [--domain starbucks.com] [--fokus "Text"]
Foto: Suche bei Wikimedia Commons und Unsplash mit den Suchbegriffen, Auswahl durch Gemini, Speichern als
assets/magazin/<kennung>-foto.jpg, image-Felder im Artikel werden aktualisiert.
Logo: logo_symbol/logo_domain im Artikel setzen und logo_file entfernen; tools/fetch_logos.py holt es danach neu.
"""
import argparse, glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir_agent as ia


def setf(head, key, val):
    head = re.sub(rf"^{key}:.*\n?", "", head, flags=re.M).rstrip("\n")
    return head + (f"\n{key}: {val}" if val is not None else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug"); ap.add_argument("--terms", default=""); ap.add_argument("--symbol", default=""); ap.add_argument("--domain", default="")
    ap.add_argument("--fokus", default="")
    a = ap.parse_args()
    path = next((p for p in glob.glob(os.path.join(ia.ROOT, "content", "magazin", "*.md")) if re.sub(r"^\d{4}-\d{2}-\d{2}(-\d{4})?-", "", os.path.basename(p))[:-3] == a.slug), None)
    if not path:
        ia.fail(f"Artikel '{a.slug}' nicht gefunden.")
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    head, body = m.group(1), m.group(2)
    name = (re.search(r'^logo_name:\s*"?(.*?)"?\s*$', head, re.M) or re.search(r'^title:\s*"?(\S+)', head, re.M)).group(1)
    if a.symbol or a.domain:
        if a.symbol: head = setf(head, "logo_symbol", a.symbol)
        if a.domain: head = setf(head, "logo_domain", a.domain)
        head = setf(head, "logo_file", None)
        print("Logo-Angaben gesetzt, fetch_logos holt das Logo neu.")
    if a.terms:
        terms = [t.strip() for t in a.terms.split(",") if t.strip()]
        cands, _ = ia.commons_candidates(name, terms=terms)
        uns = ia.unsplash_candidates(terms)
        cands = cands + uns
        print(f"Foto-Kandidaten: {len(cands)} (Commons {len(cands) - len(uns)}, Unsplash {len(uns)})")
        if cands:
            listing = "\n".join(f"{i}: {c['title']} | {c['desc']} | {c['date']}" for i, c in enumerate(cands))
            prompt = (f"Waehle ein Titelfoto fuer einen Boersenartikel ueber {name}" + (f" ({a.fokus})" if a.fokus else "") + ". "
                      "Gut: Filiale, Produkt im Alltag, Szene, die eindeutig zum Unternehmen gehoert, ansprechende Komposition, helles scharfes Bild. "
                      "Schlecht: Firmenzentrale aus der Ferne, Logos, Karten, Werbung, Portraets, unscharfe oder dunkle Bilder, historische Motive. "
                      "Wenn nichts wirklich passt, antworte -1.\n\n" + listing)
            idx = ia._generate([{"text": prompt}], {"type": "OBJECT", "required": ["index"], "properties": {"index": {"type": "INTEGER"}}}, ia.api_key())["index"]
            if isinstance(idx, int) and 0 <= idx < len(cands):
                ph = cands[idx]
                slug = a.slug
                rel = ia.save_photo(ph, slug)
                q = lambda t: '"' + str(t).replace('"', "'") + '"'
                head = setf(head, "image", rel)
                head = setf(head, "image_alt", q(f"Foto zu {name}: " + (ph["desc"] or ph["title"].replace("File:", ""))))
                head = setf(head, "image_credit", q(ia.photo_credit(ph)))
                head = setf(head, "image_source", ph["page"])
                print("Neues Foto:", ph["title"], "->", rel)
            else:
                print("Kein passendes Foto gefunden, altes bleibt.")
    open(path, "w", encoding="utf-8").write(f"---\n{head}\n---\n{body}")


if __name__ == "__main__":
    main()
