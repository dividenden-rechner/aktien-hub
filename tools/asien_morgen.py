#!/usr/bin/env python3
"""Asien-Morgenbriefing: holt Feeds (SCMP, Japan Times, Business Times u. a.), waehlt mit Gemini drei Geschichten zu boersennotierten
Unternehmen (Japan, Suedostasien mit Indonesien und Singapur-Banken, Hongkong/China), recherchiert Fakten per Websuche und schreibt drei
Entwuerfe (draft: true) nach content/magazin. draft_prs.py legt danach je Entwurf einen Pull Request zur Freigabe an.
Von den Zeitungen werden nur Schlagzeile und Anreisser als Anlass genutzt, der Text entsteht aus der Recherche in eigenen Worten.
Aufruf:  python3 tools/asien_morgen.py [--anzahl 3]"""
import argparse, json, os, re, sys, html, datetime, email.utils, urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir_agent as ia
import artikel as A

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8"}
QUELLEN = [   # Name, Region, moegliche Feed-Adressen (die erste, die funktioniert, zaehlt)
    ("South China Morning Post", "Hongkong/China", ["https://www.scmp.com/rss/92/feed"]),
    ("Japan Times", "Japan", ["https://www.japantimes.com/feed/", "https://www.japantimes.com/business/feed/"]),
    ("The Business Times", "Singapur/Suedostasien", ["https://www.businesstimes.com.sg/rss/companies-markets", "https://www.businesstimes.com.sg/rss/top-stories", "https://www.businesstimes.com.sg/rss/banking-finance"]),
    ("Antara", "Indonesien", ["https://en.antaranews.com/rss/economy.xml", "https://en.antaranews.com/rss/business-investment.xml"]),
    ("Jakarta Globe", "Indonesien", ["https://jakartaglobe.id/feed/business", "https://jakartaglobe.id/rss/business"]),
    ("ABC News Australia", "Australien", ["https://www.abc.net.au/news/feed/51892/rss.xml"]),
]
SCHEMA_PICK = {"type": "OBJECT", "required": ["picks"], "properties": {"picks": {"type": "ARRAY", "items": {"type": "OBJECT",
    "required": ["index", "region", "company", "ticker", "fokus"], "properties": {"index": {"type": "INTEGER"}, "region": {"type": "STRING"},
    "company": {"type": "STRING"}, "ticker": {"type": "STRING"}, "fokus": {"type": "STRING"}}}}}}
SCHEMA_ART = {"type": "OBJECT", "required": ["title", "description", "slug", "kurz_points", "body_md", "quellen", "branche"], "properties": {
    "title": {"type": "STRING"}, "description": {"type": "STRING"}, "slug": {"type": "STRING"}, "branche": {"type": "STRING"},
    "kurz_points": {"type": "ARRAY", "items": {"type": "STRING"}}, "body_md": {"type": "STRING"}, "quellen": {"type": "ARRAY", "items": {"type": "STRING"}}}}


def get(u, t=20):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t)
        return r.read(2_000_000).decode("utf-8", "replace")
    except Exception as e:
        return None


def clean(s, n=400):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()[:n]


def parse(body, name, region, hours=40):
    out = []
    try:
        root = ET.fromstring(body.encode("utf-8"))
    except Exception:
        return out
    now = datetime.datetime.now(datetime.timezone.utc)
    for it in root.iter():
        if it.tag.split("}")[-1] not in ("item", "entry"):
            continue
        d = {c.tag.split("}")[-1]: (c.text or "") for c in it}
        link = d.get("link") or next((c.get("href") for c in it if c.tag.split("}")[-1] == "link" and c.get("href")), "")
        when = d.get("pubDate") or d.get("published") or d.get("updated") or ""
        try:
            dt = email.utils.parsedate_to_datetime(when)
            if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            try: dt = datetime.datetime.fromisoformat(when.replace("Z", "+00:00"))
            except Exception: dt = None
        if dt and (now - dt).total_seconds() > hours * 3600:
            continue
        if d.get("title"):
            out.append({"quelle": name, "region": region, "titel": clean(d["title"], 200), "text": clean(d.get("description") or d.get("summary") or "", 350),
                        "link": link.strip(), "zeit": dt.isoformat() if dt else ""})
    return out


def sammeln():
    items, status = [], {}
    for name, region, urls in QUELLEN:
        status[name] = "kein Feed erreichbar"
        for u in urls:
            body = get(u)
            if not body or "<" not in body[:500]:
                continue
            got = parse(body, name, region)
            if got:
                items += got; status[name] = f"{len(got)} Eintraege aus {u}"
                break
            status[name] = f"Feed ohne frische Eintraege: {u}"
    os.makedirs(os.path.join(ia.ROOT, "data"), exist_ok=True)
    json.dump({"stand": datetime.datetime.utcnow().isoformat(timespec="minutes") + "Z", "status": status}, open(os.path.join(ia.ROOT, "data", "asien-feeds-status.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, v in status.items(): print(f"  {k}: {v}")
    return items


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--anzahl", type=int, default=3); a = ap.parse_args()
    now = datetime.datetime.now(ZoneInfo("Europe/Berlin")); key = ia.api_key()
    items = sammeln()
    if not items:
        ia.fail("Keine Feeds erreichbar, kein Asien-Briefing erstellt.")
    items = items[:120]
    listing = "\n".join(f"{i}: [{x['quelle']} | {x['region']}] {x['titel']} | {x['text'][:160]}" for i, x in enumerate(items))
    prompt = (f"Aus den folgenden Schlagzeilen (Feeds asiatischer Zeitungen, heute {now.strftime('%d.%m.%Y')}) waehle genau {a.anzahl} Geschichten fuer Dividendenanleger aus. "
              "Jede Geschichte muss ein konkretes, boersennotiertes Unternehmen betreffen (Aktiengesellschaft), das fuer Anleger relevant ist: Zahlen, Dividende, Uebernahme, Prognose, Management, Kapitalmassnahme. "
              "Reine Politik oder Konjunktur ohne klaren Firmenbezug gilt nicht. Verteilung: eine Geschichte aus Japan, eine aus Suedostasien (Schwerpunkt Indonesien, auch Singapur, besonders Banken wie DBS, OCBC, UOB), eine aus Hongkong oder China. "
              "Gibt es fuer eine Region heute nichts Passendes, nimm die beste Geschichte der uebrigen Regionen, verwende aber jede Firma nur einmal. "
              "Gib je Auswahl den Index, die Region, den Firmennamen, das Boersenkuerzel (zum Beispiel 7203.T, BBCA.JK, D05.SI, 0700.HK) und einen Fokus in einem Satz zurueck.\n\n" + listing)
    picks = ia._generate([{"text": prompt}], SCHEMA_PICK, key).get("picks", [])[: a.anzahl]
    print("Auswahl:", [(p["company"], p["region"]) for p in picks])
    made = 0
    for p in picks:
        try:
            it = items[p["index"]]
        except Exception:
            continue
        company, ticker = p["company"], p["ticker"]
        rp = (f"Recherchiere mit der Websuche aktuelle Fakten zu {company} ({ticker}) zum Thema: {p['fokus']} (Anlass: Schlagzeile '{it['titel']}', {it['quelle']}, {now.strftime('%d.%m.%Y')}). "
              "Gib knappe Stichpunkte mit konkreten Zahlen, Datum und Quellenname: Was ist passiert, Zahlen mit Vergleich zum Vorjahr oder Vorquartal, Dividende (Hoehe je Aktie, Rendite, Auszahlungsquote), Verschuldung und Finanzlage, "
              "Kursreaktion, Einordnung durch Analysten, Vergleich mit Wettbewerbern. Erfinde nichts, lasse Unbelegtes weg.")
        text, srcs = ia.ground(rp, key)
        if not text:
            print("Keine Recherche fuer", company, ", uebersprungen"); continue
        prompt = (ia.read_prompt("asien_prompt.md") + f"\n\nDATUM: {now.strftime('%d.%m.%Y')}\nUNTERNEHMEN: {company} ({ticker}), Region {p['region']}\n"
                  f"ANLASS (nur Hinweis, nicht uebernehmen): {it['quelle']}: {it['titel']} | {it['text']}\n\nRECHERCHE:\n{text}\n\nQUELLEN DER RECHERCHE: " + "; ".join(t for t, _ in srcs))
        out = ia._generate([{"text": prompt}], SCHEMA_ART, key)
        slug = re.sub(r"[^a-z0-9]+", "-", out["slug"].lower()).strip("-")[:70] or re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
        if A.find(slug):
            slug += "-" + now.strftime("%Y%m%d")
        q = lambda t: '"' + str(t).replace('"', "'") + '"'
        head = ["---", f"title: {q(out['title'])}", f"description: {q(out['description'])}", f"date: {now.strftime('%Y-%m-%d %H:%M')}",
                f'author: "{ia.CFG["author"]}"', f'author_bio: "{ia.CFG["author_bio"]}"', "category: Analyse", "kein_logo: ja", "draft: true"]
        try:
            ph = ia.pick_photo_topic([company], p["fokus"], out.get("branche", ""), key, only_unsplash=True)
            if ph:
                rel = ia.save_photo(ph, slug)
                head += [f"image: {rel}", f"image_alt: {q('Foto zum Thema ' + company + ': ' + (ph.get('desc') or out.get('branche') or 'Asien'))}", f"image_credit: {q(ia.photo_credit(ph))}",
                         f"image_source: {ph['page']}", f"image_artist_url: {ph.get('artist_url') or ''}"]
        except Exception as e:
            print("Foto uebersprungen:", e)
        head.append("---")
        kurz = "!!! kurz \"Kurz gesagt\"\n" + "\n".join(f"    {i + 1}. {s}" for i, s in enumerate(out["kurz_points"][:3]))
        body = (f"<!-- PRÜFEN: Asien-Morgenbriefing, {p['region']}. Zahlen und Quellen kurz gegenprüfen, dann Freigabe. Anlass: {it['quelle']} -->\n\n"
                + kurz + "\n\n" + out["body_md"].strip() + "\n\n## Quellen\n\n" + "\n".join("- " + s for s in out["quellen"]) + "\n\n"
                "*Dieser Beitrag fasst Informationen aus den genannten Quellen in eigenen Worten zusammen. Keine Anlageberatung.*\n")
        path = A.path_for(now.strftime("%Y-%m-%d-%H%M"), slug)
        open(path, "w", encoding="utf-8").write("\n".join(head) + "\n" + body)
        print("Entwurf:", path); made += 1
    if not made:
        ia.fail("Kein Entwurf erzeugt.")


if __name__ == "__main__":
    main()
