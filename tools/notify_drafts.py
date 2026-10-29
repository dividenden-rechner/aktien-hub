#!/usr/bin/env python3
"""Schickt fuer neue Entwuerfe eine Push-Meldung ueber ntfy, mit Knoepfen 'Freigeben' und 'Verwerfen'.

Aufruf (nach dem Push des Bot-Commits):  python3 tools/notify_drafts.py [--rev HEAD~1] [--dry]
Noetig (GitHub-Secrets/Variablen): NTFY_TOPIC, APPROVE_SECRET, FREIGABE_URL (Adresse des Freigabe-Dienstes).
Die Links sind mit HMAC signiert; der Freigabe-Dienst (worker/freigabe) prueft die Signatur.
"""
import argparse, hashlib, hmac, json, os, re, subprocess, sys, urllib.request

def sign(secret, text):
    return hmac.new(secret.encode(), text.encode(), hashlib.sha256).hexdigest()

def new_drafts(rev):
    out = subprocess.run(["git", "diff", "--name-only", "--diff-filter=A", rev, "HEAD", "--", "content/magazin/*.md"], capture_output=True, text=True).stdout
    res = []
    for f in out.split():
        if os.path.basename(f).startswith(("_", "README")) or not os.path.exists(f):
            continue
        t = open(f, encoding="utf-8").read()
        m = re.match(r"^---\s*\n(.*?)\n---", t, re.S)
        if not m or not re.search(r"^draft:\s*(true|ja|1|yes)\s*$", m.group(1), re.M | re.I):
            continue
        g = lambda k: (re.search(rf'^{k}:\s*"?(.*?)"?\s*$', m.group(1), re.M) or [None, ""])[1]
        res.append({"file": os.path.basename(f), "title": g("title"), "desc": g("description"), "typ": g("typ"), "cat": g("category")})
    return res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--rev", default="HEAD~1"); ap.add_argument("--dry", action="store_true"); a = ap.parse_args()
    topic, secret, base = os.environ.get("NTFY_TOPIC", ""), os.environ.get("APPROVE_SECRET", ""), os.environ.get("FREIGABE_URL", "").rstrip("/")
    if not (topic and secret and base) and not a.dry:
        print("::notice title=Push::NTFY_TOPIC, APPROVE_SECRET oder FREIGABE_URL fehlt, keine Meldung gesendet."); return
    drafts = new_drafts(a.rev)
    print(f"{len(drafts)} neue Entwuerfe")
    for d in drafts:
        link = lambda act: f"{base or 'https://freigabe.example'}/?a={act}&f={d['file']}&t={sign(secret or 'test', act + ':' + d['file'])}"
        kind = "Kurzmeldung (Zahlen prüfen)" if d["typ"] == "kurz" else "Artikel"
        msg = {"topic": topic or "test", "title": f"Entwurf: {d['title']}"[:120], "message": f"{kind} · {d['cat']}\n{d['desc']}"[:400],
               "tags": ["memo"], "priority": 3, "click": f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', 'dividenden-rechner/aktien-hub')}/blob/main/content/magazin/{d['file']}",
               "actions": [{"action": "http", "label": "Freigeben", "url": link("approve"), "method": "POST", "clear": True},
                           {"action": "view", "label": "Verwerfen", "url": link("reject")}]}
        if a.dry:
            print(json.dumps(msg, ensure_ascii=False, indent=1)); continue
        req = urllib.request.Request("https://ntfy.sh/", data=json.dumps(msg).encode(), headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=30).read(); print("gesendet:", d["file"])
        except Exception as e:
            print("::warning::Push fehlgeschlagen:", str(e)[:100])

if __name__ == "__main__":
    main()
