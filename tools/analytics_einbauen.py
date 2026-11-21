"""Baut das Zaehlskript von Cloudflare Web Analytics in alle HTML-Seiten eines Ordners ein.

Laeuft nur beim Strato-Deploy (nach live_filter.py), damit die GitHub-Testseite nicht mitgezaehlt wird.
Cloudflare Web Analytics setzt keine Cookies und speichert keine IP-Adressen.
Aufruf: python3 tools/analytics_einbauen.py _site
"""
import pathlib
import sys

TOKEN = "e716bb24154241518b046b30073a702a"
SNIPPET = (
    "<!-- Cloudflare Web Analytics --><script defer src='https://static.cloudflareinsights.com/beacon.min.js' "
    "data-cf-beacon='{\"token\": \"" + TOKEN + "\"}'></script><!-- End Cloudflare Web Analytics -->"
)
# Versteckte Werkstatt-Seiten nicht zaehlen
AUSNAHMEN = ("story-werkstatt-",)


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    n = 0
    for f in root.rglob("*.html"):
        rel = f.relative_to(root).as_posix()
        if any(a in rel for a in AUSNAHMEN):
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        if "cloudflareinsights.com/beacon" in t:
            continue
        i = t.lower().rfind("</body>")
        if i < 0:
            continue
        f.write_text(t[:i] + SNIPPET + t[i:], encoding="utf-8")
        n += 1
    print(f"Cloudflare Web Analytics in {n} Seiten eingebaut")


if __name__ == "__main__":
    main()
