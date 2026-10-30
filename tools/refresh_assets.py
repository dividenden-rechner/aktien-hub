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
    path = __import__("artikel").find(a.slug)
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
        mer = [t[6:].strip() for t in terms if t.startswith("merge:")]
        want = [t[6:].strip() for t in terms if t.startswith("match:")]
        urls = [t[4:].strip() for t in terms if t.startswith("url:")]
        terms = [t for t in terms if not t.startswith(("match:", "url:", "merge:"))]
        if mer:       # zwei vom Redakteur ausgesuchte Unsplash-Fotos zu einem Titelbild verschmelzen: merge:ID1+ID2
            ids = [x.strip() for x in mer[0].split("+") if x.strip()]
            phs = [ia.unsplash_by_id(i) for i in ids[:2]]
            if len(phs) == 2 and all(phs):
                rel = ia.merge_photos(phs[0], phs[1], a.slug)
                q = lambda t: '"' + str(t).replace('"', "'") + '"'
                head = setf(head, "image", rel)
                head = setf(head, "image_alt", q("Collage aus zwei Fotos: Aktienkurse als Kerzendiagramm auf dunklem Bildschirm und ein Mann im Anzug auf der Strasse"))
                head = setf(head, "image_credit", q(f"Fotos: {phs[0]['artist']} und {phs[1]['artist']} auf Unsplash"))
                head = setf(head, "image_source", phs[0]["page"])
                head = setf(head, "image_artist_url", phs[0]["artist_url"])
                head = setf(head, "image_artist_url2", phs[1]["artist_url"])
                head = setf(head, "image_source2", phs[1]["page"])
                print("Zwei Fotos verschmolzen ->", rel)
            else:
                print("Verschmelzen nicht moeglich: Foto nicht gefunden.")
            open(path, "w", encoding="utf-8").write(f"---\n{head}\n---\n{body}")
            return
        if urls:      # Bild von einer Adresse (zum Beispiel Pressebild), Quelle ist das Unternehmen
            ph = {"title": "Pressebild " + name, "thumb": urls[0], "page": urls[0], "artist": name, "lic": "Pressematerial", "quelle": "Unternehmen",
                  "desc": "Bild des Unternehmens", "date": "", "download": ""}
            cands = [ph]; want = ["-"]
            print("Bild von Adresse:", urls[0][:90])
        elif want:      # bestimmtes Unsplash-Foto (vom Redakteur ausgesucht) statt Modellauswahl
            ph = ia.unsplash_find(want[0], terms)
            print("Gefunden:" if ph else "Foto ueber die Suche nicht gefunden (andere Suchbegriffe angeben).", (ph or {}).get("title", ""))
            cands = [ph] if ph else []
        else:
            cands, _ = ia.commons_candidates(name, terms=terms)
        uns = [] if want else ia.unsplash_candidates(terms)
        cands = cands + uns
        print(f"Foto-Kandidaten: {len(cands)} (Commons {len(cands) - len(uns)}, Unsplash {len(uns)})")
        for i, c in enumerate(cands[:30]):
            print(f"  {i}: {c['title']} | {c['desc'][:80]}")
        idx = -1
        if want and cands:
            idx = 0
        elif cands:
            listing = "\n".join(f"{i}: {c['title']} | {c['desc']} | {c['date']}" for i, c in enumerate(cands))
            prompt = (f"Waehle ein Titelfoto fuer einen Boersenartikel ueber {name}" + (f" ({a.fokus})" if a.fokus else "") + ". "
                      "Gut: Filiale, Produkt im Alltag, Szene, die eindeutig zum Unternehmen gehoert, ansprechende Komposition, helles scharfes Bild. "
                      "Schlecht: Firmenzentralen und Buerogebaeude (auch aus der Naehe), Logos, Karten, Werbung, Portraets, unscharfe oder dunkle Bilder, historische Motive. "
                      "Wenn nichts wirklich passt, antworte -1.\n\n" + listing)
            idx = ia._generate([{"text": prompt}], {"type": "OBJECT", "required": ["index"], "properties": {"index": {"type": "INTEGER"}}}, ia.api_key())["index"]
            print("Auswahl durch das Modell:", idx)
        if isinstance(idx, int) and 0 <= idx < len(cands):
            ph = cands[idx]
            slug = a.slug
            rel = ia.save_photo(ph, slug)
            q = lambda t: '"' + str(t).replace('"', "'") + '"'
            head = setf(head, "image", rel)
            head = setf(head, "image_alt", q(f"Foto zu {name}: " + (ph["desc"] or ph["title"].replace("File:", ""))))
            head = setf(head, "image_credit", q(ia.photo_credit(ph)))
            head = setf(head, "image_source", ph["page"])
            head = setf(head, "image_artist_url", ph.get("artist_url") or "")
            print("Neues Foto:", ph["title"], "->", rel)
            if want:      # vom Redakteur ausgesucht: fuer kuenftige Artikel dieser Firma merken (ersetzt das alte)
                sym = (a.symbol or (re.search(r"^logo_symbol:\s*\"?([A-Za-z0-9.\-]+)", head, re.M) or [None, ""])[1]).strip()
                if sym:
                    ia.bib_set(sym, dict(ph, firma=name))
                    print("In der Bildbibliothek gemerkt fuer", sym)
        else:
            print("Kein passendes Foto gefunden, altes bleibt.")
    open(path, "w", encoding="utf-8").write(f"---\n{head}\n---\n{body}")


if __name__ == "__main__":
    main()
