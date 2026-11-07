#!/usr/bin/env python3
"""Zeigt die oberste Ebene des Strato-Webspace (Diagnose, ohne Aenderung)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deploy_strato as d
c = d.connect()
print("Aktuelles Verzeichnis:", c.normalize("."))
def show(p, tiefe=0, max_tiefe=2):
    try:
        for a in sorted(c.listdir_attr(p), key=lambda x: x.filename)[:40]:
            kind = "d" if (a.st_mode or 0) & 0o40000 else "-"
            print("  " * (tiefe + 1) + f"{kind} {a.filename} ({a.st_size})")
            if kind == "d" and tiefe < max_tiefe and a.filename not in ("assets", "news", "magazin", "medien", "data", "unternehmensmeldungen", "grundlagen", "fortgeschrittene", "einfuehrung"):
                show(p.rstrip("/") + "/" + a.filename, tiefe + 1, max_tiefe)
    except Exception as e:
        print("  " * (tiefe + 1) + "nicht lesbar:", e)
show(".")
