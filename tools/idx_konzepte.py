"""Diagnose: welche XBRL-Konzepte stehen in den IDX-Prüfberichten (Banken und Industrie, letztes Jahr).
Ausgabe: data/idx/konzepte.json, je Konzept Name, Anzahl und Beispielwert (nur Kontexte ohne Dimensionen)."""
import json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import idx_fundamentals as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMEN = ["BBCA", "BBRI", "ASII", "TLKM"]
JAHRE = [2025, 2024]
AUS = os.path.join(ROOT, "data", "idx", "konzepte.json")


def alle_namen(t):
    namen = collections.OrderedDict()
    for m in re.finditer(r"<(?:idx-cor:)?([A-Za-z0-9_]+)\s([^>]*?contextRef=[^>]*?)>([^<]*)</(?:idx-cor:)?\1>", t):
        name, attrs, val = m.group(1), m.group(2), m.group(3)
        c = re.search(r'contextRef="([^"]+)"', attrs)
        if not c:
            continue
        ktx = F.kontexte(t).get(c.group(1))
        if not ktx or ktx[2]:
            continue
        e = namen.setdefault(name, [0, val.strip()[:30], ktx[0]])
        e[0] += 1
    return namen


def main():
    out = {}
    for kode in FIRMEN:
        for j in JAHRE:
            try:
                nam, t = F.bericht(kode, j)
            except Exception as e:
                out[f"{kode} {j}"] = f"Fehler: {str(e)[:120]}"
                continue
            if not t:
                out[f"{kode} {j}"] = "kein Bericht"
                continue
            out[f"{kode} {j}"] = {n: {"anzahl": a, "beispiel": b, "stichtag": s} for n, (a, b, s) in alle_namen(t).items()}
            break
    os.makedirs(os.path.dirname(AUS), exist_ok=True)
    json.dump(out, open(AUS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print({k: (len(v) if isinstance(v, dict) else v) for k, v in out.items()})


if __name__ == "__main__":
    main()
