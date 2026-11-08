#!/usr/bin/env python3
"""Meldet nach dem Deploy geaenderte Seiten per IndexNow bei Bing, DuckDuckGo und Yandex (nicht Google).
Liest _geaendert.txt (von deploy_strato.py geschrieben). Der Schluessel liegt als <schluessel>.txt im Hauptverzeichnis der Seite.
Fehler brechen den Deploy nie ab."""
import glob, json, os, re, sys, urllib.request
HOST = "www.dividenden-rechner.de"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def main():
    lst = os.path.join(ROOT, "_geaendert.txt")
    if not os.path.exists(lst):
        print("Keine Adressliste, nichts zu melden."); return
    pfade = [l.strip() for l in open(lst, encoding="utf-8").read().split("\n")]
    pfade = [p for p in pfade if p is not None]
    schluessel = [os.path.basename(f)[:-4] for f in glob.glob(os.path.join(ROOT, "*.txt")) if re.fullmatch(r"[0-9a-f]{32}", os.path.basename(f)[:-4])]
    if not schluessel:
        print("Kein IndexNow-Schluessel gefunden."); return
    key = schluessel[0]
    urls = ["https://" + HOST + "/" + p for p in dict.fromkeys(pfade)]
    if not urls:
        print("Keine geaenderten Seiten."); return
    for i in range(0, len(urls), 9000):
        body = {"host": HOST, "key": key, "keyLocation": f"https://{HOST}/{key}.txt", "urlList": urls[i:i + 9000]}
        req = urllib.request.Request("https://api.indexnow.org/IndexNow", data=json.dumps(body).encode(), headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            r = urllib.request.urlopen(req, timeout=60); print("IndexNow:", r.status, len(body["urlList"]), "Adressen gemeldet")
        except Exception as e:
            print("IndexNow-Meldung fehlgeschlagen:", str(e)[:160])
main()
