#!/usr/bin/env python3
"""Tatsaechlich erreichte Abdeckung -> docs/ABDECKUNG.md und docs/RECHTE.md (nur aus den erzeugten Dateien)."""
import json
import os
import sys
from datetime import date

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASIS)
sys.path.insert(0, BASIS)
from app import rights  # noqa: E402


def lade(p, leer=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return leer


def jahre_verteilung(fund):
    v = {}
    for f in fund.values():
        n = len({d[:4] for d, _ in f.get("k", {}).get("gewinn", []) if "2010" <= d[:4] <= "2025"})
        v[n] = v.get(n, 0) + 1
    return ", ".join(f"{k} J.: {n}" for k, n in sorted(v.items(), reverse=True)) or "–"


def sec_land(land, ordner):
    s = lade(os.path.join(BASIS, "data", "universe", ordner, "summary.json"), {}) or {}
    fund = (lade(os.path.join(BASIS, "data", "fundamentals", f"{ordner}_sec.json"), {}) or {}).get("firmen", {})
    kurse = set((lade(os.path.join(ROOT, "data/kurse/xetra-letzter.json"), {}) or {}).get("k", {}))
    secs = lade(os.path.join(BASIS, "data", "universe", ordner, "securities.json"), []) or []
    if not s:
        return [f"- noch kein Lauf (Workflow americas-sec.yml)"]
    return [f"- Emittenten (Sitz {land} laut SEC, mit SEC-Meldung): **{s['emittenten']}**, Wertpapiere {s['wertpapiere']}, US-Notierungen {s['notierungen']}",
            f"- LEI (GLEIF, exakter Namensabgleich): **{s['mit_lei']}**; ISIN (GLEIF, eindeutig): **{s['mit_isin']}**; davon mit deutschem Börsenkurs: "
            f"**{sum(1 for x in secs if x.get('isin') in kurse)}**",
            f"- Mit SEC-Jahreszahlen: **{len(fund)}**; Jahre 2010–2025 je Firma (Gewinn): {jahre_verteilung(fund)}",
            "- Heimatbörse (TSX/TSXV bzw. BMV/BIVA), Indexmitglieder, Kurs- und Dividendenhistorie: **nicht erfasst** (keine Quelle mit Freigabe)"]


def main():
    b = lade(os.path.join(BASIS, "data", "universe", "brazil", "summary.json"), {}) or {}
    md = [f"# Americas Aktien-Hub – tatsächliche Abdeckung (Stand {date.today().isoformat()})", "",
          "Nur Quellen, deren Nutzungsbedingungen Speicherung, öffentliche Ausgabe und kommerzielle Nutzung ausdrücklich erlauben "
          "(siehe RECHTE.md). Alle Datensätze `verified=false`, `human_review=pending`. Leere Felder = keine freigegebene Quelle.", "",
          "## Brasilien (CVM Dados Abertos, ODbL)", ""]
    if b:
        md += [f"- Emittenten mit Aktien an der B3 (laut CVM-FCA 2010–2026, inkl. beendeter): **{b['emittenten']}**, davon aktiv {b['emittenten_aktiv']}",
               f"- Wertpapiere: **{b['wertpapiere']}** – Gattungen {b['gattungen']}; Notierungen: **{b['notierungen']}** (aktiv {b['notierungen_aktiv']})",
               f"- LEI (GLEIF über CNPJ): **{b['mit_lei']}**; ISIN: **0** (CVM ohne ISIN, B3 = Vergabestelle mit Verbot kommerzieller Nutzung)",
               f"- Mit Jahresabschlüssen (DFP): **{b['mit_finanzdaten']}**; Jahre mit Gewinn je Emittent: "
               + ", ".join(f"{k} J.: {v}" for k, v in b["jahre_mit_gewinn_verteilung"].items()),
               f"- Mit JCP-Zahlungen (getrennt von Dividenden): **{b['mit_jcp']}**; Hub-Dateien: **{b['hub_dateien']}**",
               "- Kurse, Dividende je Aktie, Ex-Tage, Indexmitglieder (IBOV, IBrX, SMLL, IDIV …): **nicht erfasst** (B3: kommerzielle Nutzung untersagt)"]
    md += ["", "## Kanada (SEC EDGAR + GLEIF)", ""] + sec_land("CA", "canada")
    md += ["", "## Mexiko (SEC EDGAR + GLEIF)", ""] + sec_land("MX", "mexico")
    md += ["", "## Bewusst nicht erfasst", "",
           "- S&P/TSX- und S&P/BMV-Indexmitglieder (S&P DJI: lizenzpflichtig, Seiten 403), TSX/TSXV-Listen (TMX: nur nicht-kommerziell),",
           "  BlackRock-ETF-Bestände (öffentliche/kommerzielle Nutzung untersagt), BMV (Reproduktion und Parsing untersagt),",
           "  BIVA und CNBV (Bedingungen nicht lesbar bzw. nicht erreichbar), SEDAR+ (Bot-Schutz, kein maschineller Abruf).", ""]
    open(os.path.join(BASIS, "docs", "ABDECKUNG.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")

    reg = rights.register()
    zw = json.load(open(rights.PFAD, encoding="utf-8"))["zwecke"]
    kurz = {"oeffentlich_einsehbar": "einsehen", "automatischer_download": "Download", "strukturierte_extraktion": "Extraktion",
            "dauerhafte_speicherung": "Speichern", "interne_verarbeitung": "intern", "oeffentliche_api": "öff. API",
            "kommerzielle_weiterverwendung": "kommerziell"}
    r = [f"# Quellen und Nutzungsrechte (Stand {date.today().isoformat()})", "",
         "Keine Rechtsberatung. `unknown` ist nicht `allowed`. Export nur bei `allowed` für Speichern, öffentliche API und kommerzielle Nutzung.", "",
         "| Quelle | Land | " + " | ".join(kurz[z] for z in zw) + " | Export |", "|---|---|" + "---|" * (len(zw) + 1)]
    for q in reg.values():
        r.append(f"| {q['anbieter']} ({q['source_id']}) | {q['land']} | " + " | ".join(q["rechte"][z] for z in zw)
                 + f" | {'ja' if rights.publizierbar([q['source_id']]) else 'nein'} |")
    r += ["", "## Belege", ""]
    for q in reg.values():
        r += [f"### {q['anbieter']}", f"- Datensatz: {q['datensatz']}", f"- Bedingungen: {q['agb_url']} (abgerufen {q['abgerufen']})",
              f"- Beleg: {q['beleg']}"]
        if q.get("bedingungen"):
            r.append("- Auflagen: " + "; ".join(q["bedingungen"]))
        if q.get("rechtsfrage"):
            r.append(f"- **Offene Frage zur rechtlichen Prüfung:** {q['rechtsfrage']}")
        r.append("")
    open(os.path.join(BASIS, "docs", "RECHTE.md"), "w", encoding="utf-8").write("\n".join(r) + "\n")
    print("\n".join(md[4:12]))


if __name__ == "__main__":
    main()
