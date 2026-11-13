#!/usr/bin/env python3
"""Speichert Firmenlogos im Repo: assets/logos/hub/<KUERZEL>.png (eine Datei je Firma).
Quelle: FMP-Symbolbild, sonst Google-Favicon der Firmen-Domain (aus assets/logos.js). Bereits vorhandene Logos bleiben.
Fehlt beides, entsteht keine Datei; die Seite zeigt dann den Buchstaben.
Laeuft im GitHub-Workflow (dort ist das Netz offen)."""
import os, re, json, time, urllib.request, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "logos", "hub")
UA = "Mozilla/5.0 (compatible; DividendenRechnerLogoBot/1.0; +https://www.dividenden-rechner.de)"
SIG = [b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF"]

def universum():
    k = json.load(open(os.path.join(ROOT, "data", "kennzahlen.json")))["werte"]
    syms = set(k.keys())
    fn = os.path.join(ROOT, "data", "firmennews")
    if os.path.isdir(fn):
        syms |= {f[:-5] for f in os.listdir(fn) if f.endswith(".json")}
    return sorted(syms)

def domains():
    # Domains aus assets/logos.js (BY-Map: Kuerzel -> Domain)
    js = open(os.path.join(ROOT, "assets", "logos.js"), encoding="utf-8").read()
    return {m.group(2): m.group(3) for m in re.finditer(r'\["([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\]', js)}

def laden(url):
    try:
        b = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20).read()
        return b if len(b) > 200 and any(b.startswith(s) for s in SIG) else None
    except Exception:
        return None

def main():
    os.makedirs(OUT, exist_ok=True)
    dom = domains(); neu = 0; fehl = []
    for sym in universum():
        ziel = os.path.join(OUT, sym + ".png")
        if os.path.exists(ziel) and os.path.getsize(ziel) > 200: continue
        b = laden("https://images.financialmodelingprep.com/symbol/" + urllib.parse.quote(sym) + ".png")
        if not b and sym in dom:
            b = laden("https://t1.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://" + urllib.parse.quote(dom[sym]) + "&size=128")
        if b:
            open(ziel, "wb").write(b); neu += 1
        else:
            fehl.append(sym)
        time.sleep(0.3)
    print("neu gespeichert:", neu, "| ohne Logo:", len(fehl), fehl[:30])

if __name__ == "__main__":
    main()
