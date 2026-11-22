#!/usr/bin/env python3
"""Holt neue Videos des YouTube-Kanals (öffentlicher RSS-Feed, kein API-Schlüssel) und ordnet sie zu:
- Sieben-Punkte-Check: Video-Link in data/sieben-punkte-liste.json (Ticker oder Name im Videotitel)
- Artikel: Feld youtube: <id> im neuesten Artikel der letzten 45 Tage zu dieser Firma
Feste Zuordnungen gehen vor: data/youtube.json -> zuordnung {video_id: "artikel-slug"}."""
import json, os, re, glob, datetime, urllib.request, xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
Y = json.load(open("data/youtube.json", encoding="utf-8"))
UA = {"User-Agent": "Mozilla/5.0 (dividenden-rechner.de)"}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "ignore")


if not Y.get("channel_id"):
    m = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', get(Y["kanal"]))
    if not m:
        raise SystemExit("Kanal-ID nicht gefunden")
    Y["channel_id"] = m.group(1)

ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
feed = ET.fromstring(get("https://www.youtube.com/feeds/videos.xml?channel_id=" + Y["channel_id"]))
bekannt = {v["id"] for v in Y["videos"]}
for e in feed.findall("a:entry", ns):
    vid = e.find("yt:videoId", ns).text
    if vid not in bekannt:
        Y["videos"].append({"id": vid, "titel": e.find("a:title", ns).text, "datum": e.find("a:published", ns).text[:10]})
        print("neu:", vid, e.find("a:title", ns).text)

# Sieben-Punkte-Liste
SL = json.load(open("data/sieben-punkte-liste.json", encoding="utf-8"))
geaendert_liste = False
for v in Y["videos"]:
    if "punkte" not in v["titel"].lower():
        continue
    firma = re.split(r"\s+im\s+|:", v["titel"])[0].strip()
    for a in SL["aktien"]:
        if firma and firma in (a["ticker"], a.get("name", ""), a.get("name", "").split()[0]) and not a.get("video"):
            a["video"] = "https://www.youtube.com/watch?v=" + v["id"]; geaendert_liste = True
            print("Rangliste:", a["ticker"], "->", v["id"])
if geaendert_liste:
    json.dump(SL, open("data/sieben-punkte-liste.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# Artikel
def artikel():
    for f in glob.glob("content/magazin/*/*.md"):
        s = open(f, encoding="utf-8").read()
        if not s.startswith("---"):
            continue
        kopf = s.split("\n---", 1)[0]
        g = lambda k: (re.search(rf"^{k}:\s*(.*)$", kopf, re.M) or [None, ""])[1].strip().strip('"')
        yield f, s, kopf, g


heute = datetime.date.today()
for v in Y["videos"]:
    if v.get("artikel"):
        continue
    ziel = Y.get("zuordnung", {}).get(v["id"])
    kand = []
    for f, s, kopf, g in artikel():
        slug = os.path.basename(f).split("-", 1)[1][:-3] if "-" in os.path.basename(f) else ""
        if ziel:
            if slug == ziel:
                kand = [(g("date"), f, s, kopf)]; break
            continue
        if re.search(r"^youtube:", kopf, re.M) or g("draft").lower() == "true":
            continue
        try:
            d = datetime.date.fromisoformat(g("date")[:10])
        except Exception:
            continue
        if (heute - d).days > 45:
            continue
        firma = re.split(r"\s+im\s+|:", v["titel"])[0].strip()
        if len(firma) < 2:
            continue
        if re.search(r"(^|[^\wÄÖÜäöüß])" + re.escape(firma) + r"($|[^\wÄÖÜäöüß])", g("title")) or os.path.basename(g("logo_file")).split(".")[0] == firma.lower():
            kand.append((g("date"), f, s, kopf))
    if kand:
        kand.sort(reverse=True)
        _, f, s, kopf = kand[0]
        s = s.replace(kopf, kopf + f"\nyoutube: {v['id']}", 1)
        open(f, "w", encoding="utf-8").write(s)
        v["artikel"] = f
        print("Artikel:", v["id"], "->", f)

json.dump(Y, open("data/youtube.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
