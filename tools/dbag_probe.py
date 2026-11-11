#!/usr/bin/env python3
"""PROBE (11.11.2026): Was steckt in den kostenlosen, 15 Minuten verzoegerten MiFID-Daten der Deutschen Boerse (Xetra Post-Trade)?
Laedt die Dateiliste und die neueste Datei, schreibt Felder, Beispielzeilen und Abdeckung nach data/dbag-probe.md. Aendert sonst nichts."""
import gzip, io, json, re, urllib.request, collections

UA = {"User-Agent": "Mozilla/5.0 (dividenden-rechner.de Datenpruefung)"}
QUELLEN = ["https://mfs.deutsche-boerse.com/DETR-posttrade", "https://mfs.deutsche-boerse.com/api/DETR-posttrade",
           "https://mifid2-apa-data.deutsche-boerse.com/DETR-posttrade/"]
TEST = {"DE0007164600": "SAP", "DE0008404005": "Allianz", "DE0007236101": "Siemens", "DE0005557508": "Dt. Telekom",
        "DE000BASF111": "BASF", "DE0008430026": "Münchener Rück", "US0378331005": "Apple", "US1912161007": "Coca-Cola"}


def hole(url, n=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read() if n is None else r.read(n), r.geturl(), r.headers.get("Content-Type", "")


def main():
    md = ["# Probe: Deutsche Börse, verzögerte Daten (Xetra Post-Trade)", ""]
    dateien, basis = [], None
    for u in QUELLEN:
        try:
            raw, final, ct = hole(u)
            txt = raw.decode("utf-8", "replace")
            md += [f"## Liste {u}", f"- Status ok, Typ {ct}, {len(raw)} Bytes, Ziel {final}", "", "```", txt[:1500], "```", ""]
            gef = re.findall(r'[\w\-./:]*?\.json\.gz', txt)
            if gef and not dateien:
                dateien, basis = gef, final
        except Exception as e:
            md += [f"## Liste {u}", f"- Fehler: {str(e)[:150]}", ""]
    md.append(f"Gefundene .json.gz-Dateien: {len(dateien)}")
    if dateien:
        name = sorted(set(dateien))[-1]
        url = name if name.startswith("http") else urllib.parse.urljoin(basis.rstrip("/") + "/", name)
        try:
            raw, _, _ = hole(url)
            data = gzip.decompress(raw).decode("utf-8", "replace")
            md += ["", f"## Neueste Datei {url}", f"- {len(raw)} Bytes gepackt, {len(data)} Zeichen entpackt", ""]
            zeilen = []
            try:
                j = json.loads(data); zeilen = j if isinstance(j, list) else j.get("data") or j.get("records") or [j]
            except Exception:
                zeilen = [json.loads(l) for l in data.splitlines() if l.strip().startswith("{")]
            md.append(f"- Datensätze: {len(zeilen)}")
            keys = collections.Counter(k for z in zeilen[:5000] if isinstance(z, dict) for k in z)
            md += ["- Felder: " + ", ".join(f"{k} ({n})" for k, n in keys.most_common(40)), "", "```"]
            md += [json.dumps(z, ensure_ascii=False)[:400] for z in zeilen[:5]] + ["```", ""]
            isins = collections.Counter()
            for z in zeilen:
                if isinstance(z, dict):
                    for k, v in z.items():
                        if isinstance(v, str) and re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", v):
                            isins[v] += 1
            md.append(f"- Verschiedene ISINs in dieser Datei: {len(isins)}")
            for i, n in TEST.items():
                md.append(f"  - {n} ({i}): {isins.get(i, 0)} Einträge")
        except Exception as e:
            md += [f"- Download/Entpacken fehlgeschlagen: {str(e)[:200]}"]
    open("data/dbag-probe.md", "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    import urllib.parse
    main()
