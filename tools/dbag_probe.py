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
            md += [f"## Liste {u}", f"- Status ok, Typ {ct}, {len(raw)} Bytes, Ziel {final}", "", "```", txt[:600], "```", ""]
            gef = re.findall(r'[\w\-./:]*?\.json\.gz', txt)
            if gef and not dateien:
                dateien, basis = gef, final
        except Exception as e:
            md += [f"## Liste {u}", f"- Fehler: {str(e)[:150]}", ""]
    md.append(f"Gefundene .json.gz-Dateien: {len(dateien)}")
    if dateien:
        name = sorted(set(dateien))[-1].split("/")[-1]
        # Download-Pfad aus dem JavaScript der Seite suchen, sonst bekannte Varianten probieren
        kand = []
        try:
            html = hole("https://mfs.deutsche-boerse.com/DETR-posttrade")[0].decode("utf-8", "replace")
            for js in re.findall(r'src="([^"]+\.js)"', html):
                try:
                    jt = hole(urllib.parse.urljoin("https://mfs.deutsche-boerse.com/", js))[0].decode("utf-8", "replace")
                    for m in re.findall(r'["\'`](/?api/[a-zA-Z/]*download[a-zA-Z/]*)', jt):
                        kand.append(urllib.parse.urljoin("https://mfs.deutsche-boerse.com/", m.rstrip("/") + "/" + name))
                    md.append(f"- JS {js}: " + ", ".join(sorted(set(re.findall(r'api/[\w/\-]+', jt)))[:10]))
                except Exception as e:
                    md.append(f"- JS {js}: {str(e)[:80]}")
        except Exception:
            pass
        kand += [f"https://mfs.deutsche-boerse.com/api/download/{name}", f"https://mfs.deutsche-boerse.com/DETR-posttrade/{name}",
                 f"https://mfs.deutsche-boerse.com/api/DETR-posttrade/{name}", f"https://mfs.deutsche-boerse.com/{name}"]
        raw, url = None, None
        for k in kand:
            try:
                r_, _, ct = hole(k)
                md.append(f"- Versuch {k}: {len(r_)} Bytes, {ct}, Anfang {r_[:2]!r}")
                if r_[:2] == b"\x1f\x8b":
                    raw, url = r_, k; break
            except Exception as e:
                md.append(f"- Versuch {k}: {str(e)[:80]}")
        try:
            if raw is None:
                raise RuntimeError("keine gz-Datei gefunden")
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
