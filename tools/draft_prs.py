#!/usr/bin/env python3
"""Legt fuer jeden neuen Entwurf (draft: true in content/magazin/) einen Pull Request an.

Der Entwurf kommt NICHT auf main, sondern auf einen eigenen Zweig 'freigabe/<kennung>' und enthaelt die
veroeffentlichungsfertige Datei (Zeile 'draft: true' entfernt) samt Bild und Grafik. In der GitHub-App erscheint
eine Push-Meldung; ein Tipp auf 'Merge' gibt den Artikel frei, 'Close' verwirft ihn.

Aufruf im Workflow, nach der Erzeugung und VOR dem Commit auf main:  python3 tools/draft_prs.py
Noetig: Umgebungsvariable GH_TOKEN (github.token), Berechtigung pull-requests: write.
"""
import argparse, os, re, subprocess, sys

def sh(*cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout.strip()

DRAFT = re.compile(r"^draft:[ \t]*(true|ja|1|yes)[ \t]*\r?\n", re.M | re.I)

def new_drafts():
    files = sh("git", "ls-files", "--others", "--exclude-standard", "content/magazin").split("\n")
    out = []
    for f in files:
        if not f.endswith(".md") or os.path.basename(f).startswith(("_", "README")):
            continue
        t = open(f, encoding="utf-8").read()
        m = re.match(r"^---\s*\n(.*?)\n---", t, re.S)
        if m and DRAFT.search(m.group(1) + "\n"):
            out.append(f)
    return out

def meta(t, k):
    m = re.search(rf'^{k}:\s*"?(.*?)"?\s*$', t, re.M)
    return m.group(1) if m else ""

def assets_for(md_path, text):
    """Dateien, die zum Entwurf gehoeren (Bilder, Grafiken, Logos), soweit neu oder geaendert."""
    base = re.sub(r"^\d{4}-\d{2}-\d{2}(-\d{4})?-", "", os.path.splitext(os.path.basename(md_path))[0])
    cand = set(re.findall(r"assets/[A-Za-z0-9_./\-]+\.(?:png|jpe?g|webp|svg|gif)", text))
    for g in sh("git", "ls-files", "--others", "--exclude-standard", "assets").split("\n"):
        if g and base in g:
            cand.add(g)
    changed = set(sh("git", "ls-files", "--others", "--modified", "--exclude-standard", "assets").split("\n"))
    return sorted(f for f in cand if f in changed and os.path.exists(f))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry", action="store_true"); ap.add_argument("--no-pr", action="store_true", help="nur Zweig anlegen (Test)")
    a = ap.parse_args()
    drafts = new_drafts()
    print(f"{len(drafts)} neue Entwuerfe")
    if not drafts:
        return
    start = sh("git", "rev-parse", "--abbrev-ref", "HEAD")
    for md in drafts:
        text = open(md, encoding="utf-8").read()
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}(-\d{4})?-", "", os.path.splitext(os.path.basename(md))[0])
        title, desc, kurz = meta(text, "title"), meta(text, "description"), meta(text, "typ") == "kurz"
        extra = assets_for(md, text)
        branch = f"freigabe/{slug}"[:80]
        print(f"- {slug}: {len(extra)} Zusatzdateien -> {branch}")
        if a.dry:
            continue
        try:
            sh("git", "checkout", "-q", "-B", branch)
            neu = DRAFT.sub("", text, count=1)
            open(md, "w", encoding="utf-8").write(neu)
            sh("git", "add", md, *extra)
            sh("git", "-c", "user.name=freigabe-bot", "-c", "user.email=actions@users.noreply.github.com", "commit", "-q", "-m", f"Freigabe: {title}")
            if not a.no_pr:
                sh("git", "push", "-q", "-f", "origin", branch)
        except Exception as e:
            print("::warning::Zweig fehlgeschlagen:", str(e)[:200]); sh("git", "checkout", "-q", start, check=False); continue
        finally:
            sh("git", "checkout", "-q", start, check=False)
        pruef = re.search(r"<!--\s*PRÜFEN(.*?)-->", text, re.S)
        body = (f"**{title}**\n\n{desc}\n\n"
                f"{'Kurzmeldung, automatisch erstellt.' if kurz else 'Lange Ausarbeitung des IR-Agenten.'} "
                f"Datei: `content/magazin/{os.path.basename(md)}`\n\n"
                + (f"⚠️ **Prüfen:**{pruef.group(1).strip()[:600]}\n\n" if pruef else "")
                + "**Merge** = freigeben, der Artikel geht nach etwa einer Minute online. **Close** = verwerfen.")
        if a.no_pr:
            continue
        try:
            sh("gh", "pr", "create", "--base", start if start != "HEAD" else "main", "--head", branch, "--title", f"Freigabe: {title}"[:200], "--body", body)
            print("  Pull Request angelegt")
        except Exception as e:
            print("::warning::Pull Request fehlgeschlagen:", str(e)[:250])

if __name__ == "__main__":
    main()
