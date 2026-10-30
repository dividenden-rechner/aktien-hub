#!/usr/bin/env python3
"""Schreibt uebliche Ueberschriften ("steigert Umsatz auf ...") veroeffentlichter Kurzmeldungen neu.
Grundlage ist nur der bereits geprueften Text der Meldung; Zahlen im neuen Titel muessen darin vorkommen. --max N, --dry."""
import os, re, sys, glob, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir_agent as ia
import kurzmeldungen as k

SCHEMA = {"type": "OBJECT", "required": ["winkel", "title"], "properties": {
    "winkel": {"type": "STRING", "description": "Gewaehlter Nachrichtenwinkel aus dem Text"},
    "title": {"type": "STRING", "description": "Neue deutsche Ueberschrift, hoechstens 90 Zeichen"}}}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--max", type=int, default=40); ap.add_argument("--dry", action="store_true"); a = ap.parse_args()
    done = 0
    titles = k.recent_titles(40)
    for f in sorted(glob.glob(os.path.join(k.OUT_DIR, "2*.md")), reverse=True):
        if done >= a.max: break
        t = open(f, encoding="utf-8").read()
        head, _, body = t.partition("\n---\n")
        m = re.search(r'^title:\s*"(.*)"\s*$', head, re.M)
        if not m or not re.search(r"^typ:\s*kurz", head, re.M) or re.search(r"^draft:\s*true", head, re.M) or not k.BORING.search(m.group(1)): continue
        prompt = ("Schreibe eine neue Ueberschrift fuer diese Kurzmeldung eines deutschen Finanzportals. Die alte Ueberschrift ist zu uebliche Formel: "
                  f"'{m.group(1)}'. Waehle einen anderen Nachrichtenwinkel aus dem Text (Gewinn, Marge, Prognose, Segment, Dividende, Rueckkauf, Schulden, Sonderposten, Management) "
                  "und nenne eine konkrete Zahl aus dem Text. Kein 'Umsatz steigt', 'steigert Umsatz', 'legt Zahlen vor'. Hoechstens 90 Zeichen, sachlich, ohne Wertung. "
                  "Betraege ab 1.000 Millionen in Milliarden (Mrd.). Nur Fakten und Zahlen, die im Text stehen. Firmenname im Titel. "
                  f"Anderes Muster als diese juengsten Ueberschriften:\n{titles}\n\nTEXT:\n{body[:6000]}")
        try:
            out = ia._generate([{"text": prompt}], SCHEMA, ia.api_key())
        except SystemExit:
            print("Modelle liefern nichts mehr, Abbruch."); break
        new = (out or {}).get("title", "").strip().strip('"')
        if not new or k.BORING.search(new) or k.unverified_numbers(new, body + " " + m.group(1)):
            print("verworfen:", new); continue
        print(m.group(1), "->", new)
        if not a.dry:
            head = head.replace(m.group(0), 'title: "' + new.replace('"', "'") + '"', 1)
            open(f, "w", encoding="utf-8").write(head + "\n---\n" + body)
        done += 1
    print(done, "Ueberschriften neu")

if __name__ == "__main__":
    main()
