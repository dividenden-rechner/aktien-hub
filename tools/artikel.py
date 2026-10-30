"""Ablage der Magazin-Artikel: content/magazin/<Tagesordner>/<Datei>.md

Damit die Liste auf GitHub (sortiert nach Name, aufsteigend) die NEUESTEN OBEN zeigt, beginnen die Namen mit einer umgekehrten Zahl:
  Tagesordner:  79738969_2026-10-30        (99999999 minus Datum)
  Datei:        8197_1802-abbvie-q3.md     (9999 minus Uhrzeit, dann Uhrzeit und Titelkuerzel)
Der jüngste Tag steht oben, darin der jüngste Artikel. Alte Dateien im Hauptordner (2026-10-30-1802-slug.md) werden von sortiere() einsortiert."""
import glob, os, re, shutil
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "content", "magazin")
OLD = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:-(\d{2})(\d{2}))?-(.+)\.md$")
NEW = re.compile(r"^\d{4}_(\d{2})(\d{2})-(.+)\.md$")
DAY = re.compile(r"^\d{8}_(\d{4})-(\d{2})-(\d{2})$")


def _folder(y, m, d):
    return "%08d_%s-%s-%s" % (99999999 - int("%s%s%s" % (y, m, d)), y, m, d)


def path_for(stamp, slug):
    """stamp = 'YYYY-MM-DD-HHMM'. Legt den Tagesordner an und liefert den vollen Dateipfad."""
    y, m, d, hh, mm = stamp[:4], stamp[5:7], stamp[8:10], stamp[11:13] or "00", stamp[13:15] or "00"
    folder = os.path.join(DIR, _folder(y, m, d))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "%04d_%s%s-%s.md" % (9999 - int(hh + mm), hh, mm, slug))


def slug_of(name):
    n = os.path.basename(name)
    m = NEW.match(n) or OLD.match(n)
    if m: return m.group(3) if n[4] == "_" else m.group(6)
    return n[:-3] if n.endswith(".md") else n


def stamp_of(path):
    """Sortierschluessel 'YYYY-MM-DD-HHMM' aus Ordner und Dateiname (alte Namen eingeschlossen)."""
    n = os.path.basename(path)
    m = OLD.match(n)
    if m: return "%s-%s-%s-%s%s" % (m.group(1), m.group(2), m.group(3), m.group(4) or "00", m.group(5) or "00")
    m = NEW.match(n); d = DAY.match(os.path.basename(os.path.dirname(path)))
    if m and d: return "%s-%s-%s-%s%s" % (d.group(1), d.group(2), d.group(3), m.group(1), m.group(2))
    return "0000-00-00-0000"


def all_md():
    """Alle Artikel (ohne README und Dateien mit _), neueste zuerst. Volle Pfade."""
    fs = [f for f in glob.glob(os.path.join(DIR, "**", "*.md"), recursive=True)
          if not os.path.basename(f).startswith(("_", "README"))]
    return sorted(fs, key=lambda f: (stamp_of(f), f), reverse=True)


def rel_all():
    return [os.path.relpath(f, DIR) for f in all_md()]


def find(slug):
    """Vorhandener Artikel zu diesem Titelkuerzel oder None."""
    return next((f for f in all_md() if slug_of(f) == slug), None)


def sortiere():
    """Einzelne Dateien im Hauptordner in Tagesordner verschieben. Liefert die Zahl der verschobenen Dateien."""
    n = 0
    for f in glob.glob(os.path.join(DIR, "*.md")):
        b = os.path.basename(f)
        if b.startswith(("README", "_")): continue
        m = OLD.match(b)
        if m:
            stamp = "%s-%s-%s-%s%s" % (m.group(1), m.group(2), m.group(3), m.group(4) or "00", m.group(5) or "00"); slug = m.group(6)
        else:   # Name ohne Datum: Datum aus dem Kopfbereich
            d = re.search(r"^date:\s*(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?", open(f, encoding="utf-8").read(2000), re.M)
            if not d: continue
            stamp = "%s-%s-%s-%s%s" % (d.group(1), d.group(2), d.group(3), d.group(4) or "00", d.group(5) or "00"); slug = b[:-3]
        dst = path_for(stamp, slug)
        if os.path.exists(dst): continue
        shutil.move(f, dst); n += 1
    return n


if __name__ == "__main__":
    print(sortiere(), "Dateien einsortiert")
