#!/usr/bin/env python3
"""Tatsaechlich erreichte Abdeckung -> docs/ABDECKUNG.md (nur aus den erzeugten Dateien, keine Annahmen)."""
import json
import os
from datetime import date

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASIS)
UNI = os.path.join(BASIS, "data", "universe", "canada")


def lade(p, leer=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return leer


def main():
    s = lade(os.path.join(UNI, "summary.json"), {})
    cik = lade(os.path.join(UNI, "sec_cik.json"), {}) or {}
    fund = (lade(os.path.join(BASIS, "data", "fundamentals", "canada_sec.json"), {}) or {}).get("firmen", {})
    kurse = set((lade(os.path.join(ROOT, "data/kurse/xetra-letzter.json"), {}) or {}).get("k", {}))
    lst = lade(os.path.join(UNI, "listings.json"), []) or []
    mit_kurs = sum(1 for l in lst if l.get("isin") in kurse)
    jahre = {}
    for f in fund.values():
        ys = {d[:4] for r in f.get("k", {}).values() for d, _ in r}
        n = len([y for y in ys if "2010" <= y <= "2025"])
        jahre[n] = jahre.get(n, 0) + 1
    idx = s.get("index", {})
    md = [f"# Americas Aktien-Hub – tatsächliche Abdeckung (Stand {date.today().isoformat()})", "",
          "Alle Datensätze `verified=false`, `human_review=pending`. Leere Felder = nicht aus amtlicher/nachvollziehbarer Quelle belegt.", "",
          "## Kanada (S&P/TSX Composite)", "",
          f"- Mitgliederliste: {idx.get('quelle')} – Stichtag **{idx.get('stichtag')}**, abgerufen {idx.get('abgerufen')} ({idx.get('art')})",
          f"- Indexmitglieder: **{s.get('mitglieder')}**, Emittenten {s.get('emittenten')}, Wertpapiere {s.get('wertpapiere')}, Notierungen (TSX) {s.get('notierungen')}",
          f"- ISIN + LEI aus ESMA FIRDS (eindeutig): **{s.get('mit_isin')}**; ohne ISIN (mehrdeutig/nicht gefunden, siehe review.json): **{s.get('ohne_isin')}**",
          f"- Wertpapierarten: {s.get('arten')}",
          f"- Mit deutschem Börsenkurs (Deutsche Börse, EUR): **{mit_kurs}**",
          f"- SEC-CIK eindeutig zugeordnet (meldet bei der SEC, meist 40-F): **{len(cik)}**",
          f"- Mit SEC-Jahreszahlen (XBRL): **{len(fund)}**; Verteilung Anzahl Jahre 2010–2025 je Firma: "
          + (", ".join(f"{k} J.: {v}" for k, v in sorted(jahre.items(), reverse=True)) or "noch kein Lauf"), "",
          "### Fehlt (Kanada)", "",
          "- Amtliche S&P-Mitgliederlisten und historische Indexmitgliedschaften (lizenzpflichtig).",
          "- Finanzhistorie für Firmen ohne SEC-Meldung (nur SEDAR+, kein maschineller Zugriff) und vor Beginn der XBRL-Pflicht.",
          "- Kurshistorie in CAD von der TSX (Nutzungsbedingungen: nur nicht-kommerziell); Dividendenhistorie je Aktie.",
          "- TSXV/Venture-Werte: bewusst nicht im Umfang (nur Composite).", "",
          "## Brasilien, Mexiko", "",
          "- Noch nicht importiert: Quellen geprüft (docs/QUELLENPRUEFUNG.md), Umfang und Nutzung der B3-/BIVA-Daten offen.", ""]
    open(os.path.join(BASIS, "docs", "ABDECKUNG.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md[4:13]))


if __name__ == "__main__":
    main()
