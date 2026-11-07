#!/usr/bin/env python3
"""Laedt die gebaute Seite per SFTP auf den Strato-Webspace. Nur geaenderte Dateien (Pruefsumme-Liste .deploy-manifest.json auf dem Server),
entfernte Dateien werden geloescht, aber nur solche, die dieses Skript selbst hochgeladen hat.
Aufruf:  python3 tools/deploy_strato.py _site [--trocken]
Noetig: STRATO_SFTP_HOST, STRATO_SFTP_USER, STRATO_SFTP_PASS (GitHub-Secrets), optional STRATO_SFTP_PORT (22) und STRATO_SFTP_DIR (Standard: Hauptverzeichnis)."""
import argparse, hashlib, io, json, os, posixpath, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
import paramiko

SKIP_DIRS = {"intern-t7q4m9", ".git"}   # Testkopie der GitHub-Pages-Seite gehoert nicht auf Strato
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = ".deploy-manifest.json"


def sha(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def connect():
    host, user, pw = os.environ["STRATO_SFTP_HOST"].strip(), os.environ["STRATO_SFTP_USER"].strip(), os.environ["STRATO_SFTP_PASS"]
    port = int(os.environ.get("STRATO_SFTP_PORT", "22") or 22)
    for attempt in range(4):
        try:
            t = paramiko.Transport((host, port)); t.banner_timeout = 30; t.connect(username=user, password=pw)
            c = paramiko.SFTPClient.from_transport(t); c.get_channel().settimeout(120)
            return c
        except Exception as e:
            print("Verbindungsversuch", attempt + 1, "fehlgeschlagen:", type(e).__name__, str(e)[:120]); time.sleep(5 * (attempt + 1))
    sys.exit("Keine SFTP-Verbindung moeglich (Host, Benutzer, Passwort pruefen).")


def mkdirs(c, d, made):
    if d in made or d in ("", "/", "."):
        return
    mkdirs(c, posixpath.dirname(d), made)
    try:
        c.stat(d)
    except IOError:
        try: c.mkdir(d)
        except IOError: pass
    made.add(d)


def htaccess_text():
    """Zwischenspeicher-Regeln plus 301-Weiterleitungen der alten Google-Sites-Adressen (aus tools/umzug/redirects-entwurf.csv)."""
    import csv, re
    teile = []
    ht = os.path.join(ROOT, "docs", "STRATO-htaccess-cache.txt")
    if os.path.exists(ht):
        teile.append(open(ht, encoding="utf-8").read().rstrip())
    csvp = os.path.join(ROOT, "tools", "umzug", "redirects-entwurf.csv")
    zeilen = ["# Weiterleitungen alter Adressen (Google Sites) auf die neue Seite", "RewriteEngine On"]
    if os.path.exists(csvp):
        for r in csv.DictReader(open(csvp, encoding="utf-8")):
            alt, neu, st = r["alter_pfad"].strip(), r["neuer_pfad"].strip(), (r.get("status") or "").strip().lower()
            if not st.startswith("301") or alt in ("", "/") or alt.rstrip("/") == neu.rstrip("/"):
                continue
            neu = neu.replace("/magazin/", "/news/", 1) if neu.startswith("/magazin/") else neu
            zeilen.append(f"RewriteRule ^{re.escape(alt.strip('/'))}/?$ {neu} [R=301,L,NE]")
    teile.append("\n".join(zeilen))
    return "\n\n".join(teile) + "\n"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("--trocken", action="store_true"); a = ap.parse_args()
    base = os.environ.get("STRATO_SFTP_DIR", "").rstrip("/")
    files = {}
    for dp, dn, fn in os.walk(a.src):
        dn[:] = [d for d in dn if not (dp == a.src and d in SKIP_DIRS)]
        for f in fn:
            p = os.path.join(dp, f); files[os.path.relpath(p, a.src).replace(os.sep, "/")] = p
    hp = os.path.join(ROOT, "_htaccess.tmp")
    open(hp, "w", encoding="utf-8").write(htaccess_text())
    files[".htaccess"] = hp
    print(f"{len(files)} Dateien lokal")
    sums = {k: sha(p) for k, p in files.items()}
    c = connect()
    try:
        old = json.load(c.open(posixpath.join(base, MANIFEST) if base else MANIFEST))
    except Exception:
        old = {}
    if base:
        # Frueher lag die Seite im Hauptverzeichnis: diese (von uns hochgeladenen) Dateien entfernen
        try:
            alt = json.load(c.open(MANIFEST))
        except Exception:
            alt = {}
        if alt and not a.trocken:
            print(f"Raeume {len(alt)} alte Dateien im Hauptverzeichnis auf")
            dirs = set()
            for k in alt:
                try: c.remove(k)
                except IOError: pass
                d = posixpath.dirname(k)
                while d:
                    dirs.add(d); d = posixpath.dirname(d)
            for d in sorted(dirs, key=lambda x: -x.count("/")):
                try: c.rmdir(d)
                except IOError: pass
            try: c.remove(MANIFEST)
            except IOError: pass
    todo = [k for k, s in sums.items() if old.get(k) != s]
    gone = [k for k in old if k not in sums]
    print(f"Hochladen: {len(todo)}, loeschen: {len(gone)}, unveraendert: {len(sums) - len(todo)}")
    if a.trocken:
        return
    rp = lambda k: posixpath.join(base, k) if base else k
    made, lock, done, fails = set(), threading.Lock(), [0], []
    tl = threading.local()

    def up(k):
        if not hasattr(tl, "c"):
            tl.c = connect()
        for attempt in range(3):
            try:
                with lock:
                    mkdirs(tl.c, posixpath.dirname(rp(k)), made)
                tl.c.put(files[k], rp(k))
                with lock:
                    done[0] += 1
                    if done[0] % 200 == 0: print(f"  {done[0]}/{len(todo)}", flush=True)
                return
            except Exception as e:
                try: tl.c = connect()
                except SystemExit: pass
                err = str(e)[:100]
        fails.append((k, err))

    mkdirs(c, base, made)
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(up, todo))
    for k in gone:
        try: c.remove(rp(k))
        except IOError: pass
    neu = {k: s for k, s in sums.items() if k not in {f for f, _ in fails}}
    c.putfo(io.BytesIO(json.dumps(neu).encode()), rp(MANIFEST))
    print(f"Fertig: {done[0]} hochgeladen, {len(gone)} geloescht, {len(fails)} Fehler")
    for k, e in fails[:10]: print("  Fehler:", k, e)
    if fails: sys.exit(1)


if __name__ == "__main__":
    main()
