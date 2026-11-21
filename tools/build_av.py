#!/usr/bin/env python3
"""Baut den Anbietervergleich in altersvorsorgedepot/index.html aus data/av-anbieter.json (Schema 2).

Datenmodell: Anbieter -> Depotmodell (produkte) -> Kostenbestandteil (bestandteile) mit Zeitraum/Bedingung -> Quelle.
Der Block steht zwischen <!--av-start--> und <!--av-end--> oberhalb des Rechners. Ein älterer, von Hand eingefügter Block
(section#anbieter-bereich außerhalb der Markierung) wird dabei entfernt, damit es keine zwei Datenstände auf der Seite gibt.
Die Kostenlogik (av_kosten_am) entspricht avKostenAm in assets/rechner.js; tests/av.test.js prüft, dass beide gleich rechnen.
"""
import html, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "altersvorsorgedepot", "index.html")
DATA = os.path.join(ROOT, "data", "av-anbieter.json")
esc = html.escape

ART = {"standard": "Standarddepot", "gesteuert": "Gesteuert", "frei": "Frei", "beratung": "Mit Beratung", "garantie": "Garantieprodukt"}
PRUEF = {"primary_verified": "Anbieterquelle", "secondary_lead": "nur Presse", "pending": "offen"}
PCT_ARTEN = {"fund_ter", "service_fee", "management_fee", "total_cost", "custody_fee"}


def av_monat(eroeffnung, t):
    y0, m0 = (int(x) for x in eroeffnung.split("-")[:2])
    mm = (m0 - 1) + t
    ky, km = y0 + mm // 12, mm % 12 + 1
    return {"jahr": t // 12 + 1, "kalender": ky, "ym": f"{ky}-{km:02d}"}


def av_aktiv(b, z, eroeffnung):
    ym, e = z["ym"], eroeffnung[:7]
    if b.get("ab_kalender") and ym < b["ab_kalender"][:7]:
        return False
    if b.get("bis_kalender") and ym > b["bis_kalender"][:7]:
        return False
    if b.get("ab_vertragsjahr") and z["jahr"] < b["ab_vertragsjahr"]:
        return False
    if b.get("bis_vertragsjahr") and z["jahr"] > b["bis_vertragsjahr"]:
        return False
    if b.get("eroeffnung_ab") and e < b["eroeffnung_ab"][:7]:
        return False
    if b.get("eroeffnung_bis") and e > b["eroeffnung_bis"][:7]:
        return False
    return True


def av_kosten_am(p, t, bal=0.0, eroeffnung="2027-01", freiwillig=True):
    """Kosten in Prozent p. a. im Vertragsmonat t. Rückgabe dict mit offen/pct/eur/flags. Unbekanntes wird nie geschätzt."""
    bs = p.get("bestandteile") or []
    if not bs or p.get("konditionen") == "offen":
        return {"offen": True}
    z = av_monat(eroeffnung, t)
    ter, ter_offen, rest, eur, flags, erst = 0.0, False, 0.0, 0.0, {}, []
    for b in bs:
        if not av_aktiv(b, z, eroeffnung):
            continue
        if b["art"] == "ter_erstattung":
            if not b.get("freiwillig") or freiwillig:
                erst.append(b)
            continue
        if b.get("eur_jahr"):
            eur += b["eur_jahr"]
        if b["art"] not in PCT_ARTEN:
            continue
        if b.get("pct") is None:
            if b.get("eur_jahr"):
                continue
            if b["art"] == "fund_ter":
                ter_offen = True
                continue
            return {"offen": True}
        if b.get("ca"):
            flags["ca"] = True
        if b.get("obergrenze"):
            flags["max"] = True
        if b["art"] == "fund_ter":
            ter += b["pct"]
        else:
            rest += b["pct"]
    anteil = 0.0
    for b in erst:
        cap = b.get("max_volumen")
        a = cap / bal if cap and bal > cap else 1.0
        if b.get("freiwillig"):
            flags["freiwillig"] = True
        anteil = max(anteil, a)
    if ter_offen and anteil < 1:
        return {"offen": True}
    pct = (0.0 if ter_offen else ter * (1 - anteil)) + rest
    if anteil > 0 and ter * (1 - anteil) + rest == 0:
        flags.pop("max", None)
        flags.pop("ca", None)
    return {"offen": False, "pct": round(pct, 6), "eur": eur, "flags": flags}


def kennzahlen(p):
    a, b = av_kosten_am(p, 0), av_kosten_am(p, 9 * 12)
    return (None if a["offen"] else a["pct"], a.get("flags", {}), None if b["offen"] else b["pct"], b.get("flags", {}), 0 if a["offen"] else a["eur"])


def fig(v, fl=None):
    if v is None:
        return "noch offen"
    fl = fl or {}
    pre = "max. " if fl.get("max") else "ca. " if fl.get("ca") else ""
    return pre + f"{v:.2f}".replace(".", ",") + " %" + ("*" if fl.get("freiwillig") else "")


def dmy(s):
    return f"{s[8:10]}.{s[5:7]}.{s[:4]}" if s else ""


def logo(domain, size=28):
    if not domain:
        return ""
    return (f'<img class="av-logo" src="https://t1.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://{esc(domain)}&size=64" '
            f'alt="" width="{size}" height="{size}" loading="lazy" onerror="this.style.visibility=\'hidden\'">')


CSS = """<style>
.av-title{font-size:clamp(1.55rem,4.6vw,2.1rem);line-height:1.2;margin:18px 0 10px}
.av-teaser{font-size:1.06rem;line-height:1.6;color:#33414d;margin:0 0 16px}
.av-kurz{background:#f0f8f3;border:1px solid #bfe0cd;border-left:5px solid #1a7f4b;border-radius:0 12px 12px 0;padding:14px 18px;margin:0 0 26px}
.av-kurz-t{font-size:13px;letter-spacing:.06em;text-transform:uppercase;font-weight:700;color:#1a7f4b;margin-bottom:6px}
.av-kurz ol{margin:0;padding-left:20px}.av-kurz li{margin:6px 0;line-height:1.4}.av-kurz li a{font-weight:600;color:#14202b}
.av-kurz li span{display:block;font-size:.88rem;color:#5b6874}.av-kurz-s{font-size:.8rem;color:#5b6874;margin-top:8px}
.tool h2#h-altersvorsorgedepot{font-size:1.45rem;margin-top:6px}.av-x{display:none}.av-mehr{display:block;width:100%;margin:10px 0 4px;padding:10px;border:1px solid #bfe0cd;background:#f0f8f3;color:#1a7f4b;font-weight:600;border-radius:10px;cursor:pointer;font-size:.95rem}
.av-acc>div{padding:0 0 12px}.av-acc>div p{line-height:1.6;margin:8px 0}.av-unten{margin-top:28px}.av-links{font-size:.92rem;margin-top:16px}

[hidden]{display:none!important}
.av-tabs{display:flex;gap:18px;overflow-x:auto;margin:10px 0 6px;border-bottom:1px solid #dfe5ea;white-space:nowrap;scrollbar-width:none}.av-tabs::-webkit-scrollbar{display:none}
.av-tab{flex:0 0 auto;border:0;border-bottom:2px solid transparent;margin-bottom:-1px;background:none;border-radius:0;padding:6px 0 8px;cursor:pointer;font:inherit;font-size:13px;font-weight:500;color:#8a97a3}.av-tab:hover{color:#5b6874}.av-tab[aria-pressed=true]{color:#33414d;font-weight:600;border-bottom-color:#8a97a3}
.av-filter{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;margin:8px 0 6px;font-size:.84rem;color:#5b6874}.av-filter label{display:flex;gap:6px;align-items:center}.av-filter select{font:inherit;font-size:.84rem;padding:3px 6px;border:1px solid #d5dce2;border-radius:6px;background:#fff;color:#33414d}
.av-count{font-size:.8rem;color:#8a97a3}
.av-id{display:flex;gap:10px;align-items:center}.av-logo{width:28px;height:28px;object-fit:contain;border-radius:6px;border:1px solid #eef1f4;background:#fff;padding:2px;flex:none}
.av-id small{display:block;font-weight:400;color:#6b7782;font-size:.78rem;white-space:normal}
.av-scroll-hint{display:none;font-size:.78rem;color:#8a97a3;margin:6px 0 4px}
.av-tablewrap{overflow-x:auto;border:1px solid #e3e8ec;border-radius:8px;margin:6px 0 10px;-webkit-overflow-scrolling:touch}
.av-tablewrap:focus{outline:2px solid #8a97a3;outline-offset:2px}
.av-table{line-height:1.4;border-collapse:separate;border-spacing:0;width:100%;min-width:1180px;font-size:.86rem;color:#33414d}
.av-table caption{caption-side:top;text-align:left;font-size:.8rem;color:#6b7782;padding:8px 14px}
.av-table th,.av-table td{padding:10px 14px;text-align:left;vertical-align:top;border-bottom:1px solid #eef1f4;background:#fff}
.av-table thead th{position:sticky;top:0;background:#f6f8fa;font-size:.74rem;font-weight:600;color:#5b6874;text-transform:uppercase;letter-spacing:.03em;white-space:nowrap;border-bottom:1px solid #e3e8ec}
.av-table tbody tr:last-child th,.av-table tbody tr:last-child td{border-bottom:0}
.av-table tbody tr:hover td,.av-table tbody tr:hover th{background:#fafcfb}
.av-table th:first-child{position:sticky;left:0;z-index:2;min-width:200px;max-width:240px;box-shadow:1px 0 0 #e3e8ec}
.av-table thead th:first-child{z-index:3}
.av-table .num{text-align:right;white-space:nowrap;min-width:96px}.av-table td.num b{font-weight:600;color:#065f46}.av-table td.num.offen b{color:#8a97a3;font-weight:500}
.av-table td.w{min-width:260px;max-width:320px}
.tool .av-table th,.tool .av-table td{border:0;border-bottom:1px solid #eef1f4}.tool .av-table tbody th{color:#33414d;background:#fff;text-align:left;font-weight:600}.tool .av-table thead th{color:#5b6874;background:#f6f8fa;text-align:left}.tool .av-table .num{text-align:right}.tool .av-table tbody tr:last-child th,.tool .av-table tbody tr:last-child td{border-bottom:0}.tool .av-rank tr.sel th,.tool .av-rank tr.sel td{background:#f1f9f4}.tool .av-rank tr.off th{color:#9aa5af}
.av-jump{font-size:.88rem;margin:-4px 0 14px}.av-h3{font-size:1.05rem;margin:1.8rem 0 .2rem}.av-sub{font-size:.8rem;color:#6b7782;margin:4px 0 10px}
.av-rank{min-width:700px}.av-rank td.t{min-width:200px}.av-rank tr.sel td,.av-rank tr.sel th{background:#f1f9f4}.av-rank tr.off td,.av-rank tr.off th{color:#9aa5af}
.av-rank th:first-child{min-width:220px}.av-rank .av-logo{width:22px;height:22px}.av-rank .dif.pos{color:#0f6b46}.av-rank .dif.neg{color:#b3372d}
.tool .av-pick{padding:3px 10px;font-size:.78rem;font-weight:500;background:#fff;color:#33414d;border:1px solid #d5dce2;border-radius:6px}.tool .av-pick:hover{background:#f6f8fa}
.av-n{font-weight:600}
#anbieter-bereich{max-width:1100px!important}#anbieter-bereich>:not(.av-tablewrap){max-width:760px}
.av-q{min-width:170px}.av-q a{display:block;color:#5b6874;margin:0 0 3px;font-size:.78rem;text-decoration:underline;text-decoration-color:#cfd6dc}
.av-st{font-size:.78rem;white-space:nowrap}.av-st.s2{color:#8a6d1a}
.av-h{color:#8a6d1a;font-size:.78rem;margin-top:4px}
.av-sum{margin:14px 0}.av-sum li{margin:4px 0}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
@media(max-width:900px){.av-scroll-hint{display:block}.av-table th:first-child{min-width:140px;max-width:160px}.av-table thead th:first-child{white-space:normal}.av-table .num{min-width:84px}}
</style>
"""

JS = """<script>
(function(){var l=document.getElementById("avl"),t=document.getElementById("avt"),fa=document.getElementById("av-f-art"),fk=document.getElementById("av-f-kosten"),cnt=document.getElementById("av-count");if(!l||!t)return;
function key(r,s){if(s==="n")return r.dataset.n.toLowerCase();var v=r.dataset[s];return v===""?1e9:parseFloat(v)}
function filt(){var a=fa?fa.value:"",k=fk&&fk.checked,n=0;Array.prototype.forEach.call(l.children,function(r){var ok=(!a||r.dataset.art===a)&&(!k||r.dataset.dau!=="");r.hidden=!ok;if(ok)n++});if(cnt)cnt.textContent=n+" von "+l.children.length+" Depotmodellen"}
t.addEventListener("click",function(e){var b=e.target.closest(".av-tab");if(!b)return;var s=b.dataset.s;Array.prototype.forEach.call(t.children,function(x){x.setAttribute("aria-pressed",x===b?"true":"false")});
var rows=Array.prototype.slice.call(l.children);rows.sort(function(a,b){var x=key(a,s),y=key(b,s);return x<y?-1:x>y?1:(+a.dataset.i)-(+b.dataset.i)});rows.forEach(function(r){l.appendChild(r)})});
var mb=document.getElementById("av-mehr"),zu=true,N=8;
function kurz(){var n=0,tot=0;Array.prototype.forEach.call(l.children,function(r){if(r.hidden){r.classList.remove("av-x");return}tot++;n++;r.classList.toggle("av-x",zu&&n>N)});if(mb){mb.hidden=tot<=N;mb.setAttribute("aria-expanded",zu?"false":"true");mb.textContent=zu?"Alle "+tot+" Depotmodelle anzeigen":"Weniger anzeigen"}}
if(mb)mb.addEventListener("click",function(){zu=!zu;kurz();if(zu)document.getElementById("anbieter").scrollIntoView({block:"start"})});
var f0=filt;filt=function(){f0();kurz()};t.addEventListener("click",function(){setTimeout(kurz,0)});
if(fa)fa.addEventListener("change",filt);if(fk)fk.addEventListener("change",filt);filt();
})();
</script>"""


def rechts_text(D):
    q = D["quellen"]
    a = lambda k, t: f'<a href="{esc(q[k]["url"])}" target="_blank" rel="noopener nofollow">{esc(t)}</a>'
    acc = lambda t, x: f'<details class="av-acc"><summary>{t}</summary><div>{x}</div></details>'
    return "\n".join([
        acc("Förderung und Beiträge", f"""<p>Neue Verträge gibt es ab dem 1. Januar 2027, jeder braucht ein Zertifikat des Bundeszentralamts für Steuern. Grundlage ist das Altersvorsorgereformgesetz, verkündet am 29. Mai 2026 ({a("bgbl", "BGBl. 2026 I Nr. 156")}).</p>
<p>Auf die ersten 360 Euro Eigenbeitrag im Jahr legt der Staat 50 Prozent drauf, auf alles darüber bis 1.800 Euro noch 25 Prozent, zusammen höchstens 540 Euro. Für jedes Kind kommen bis zu 300 Euro dazu, wer zu Beginn des Jahres jünger als 25 ist, bekommt einmalig 200 Euro extra. Voraussetzung sind mindestens 120 Euro Eigenbeitrag im Jahr. Einzahlen kannst du bis zu 6.840 Euro, gefördert und als Sonderausgabe absetzbar sind 1.800 Euro plus Zulagen, und das für höchstens zwei Verträge.</p>"""),
        acc("Kosten, Standarddepot und Anbieterwechsel", """<p>Im Standarddepot dürfen die Effektivkosten höchstens 1,0 Prozent im Jahr betragen. Für frei gestaltete Depots und Garantieprodukte gibt es keinen Deckel.</p>
<p>Das Standarddepot besteht aus zwei Fonds: einem sicheren der Risikoklasse 1 oder 2 und einem chancenreicheren der Klassen 3 bis 5. Fünf Jahre vor der Auszahlung liegen höchstens 50 Prozent im chancenreicheren Fonds, zwei Jahre vorher höchstens 30 Prozent, wenn du nichts anderes verlangst.</p>
<p>Wer in den ersten fünf Jahren den Anbieter wechselt, zahlt dem alten höchstens 150 Euro, danach ist der Wechsel kostenlos. Der neue Anbieter darf einmalig bis zu 150 Euro berechnen.</p>"""),
        acc("Steuer und Auszahlung", """<p>In der Ansparphase fallen auf Erträge keine Steuern an, versteuert wird erst die Auszahlung mit deinem persönlichen Steuersatz. Ausgezahlt wird frühestens ab 65 und spätestens ab 70. Bis zu 30 Prozent kannst du zu Beginn auf einmal nehmen, den Rest als lebenslange Rente oder als Auszahlplan bis mindestens 85.</p>"""),
        acc("Riester und Frühstartrente", f"""<p>Riester-Verträge, die bis Ende 2026 abgeschlossen werden, laufen weiter, neue gibt es ab 2027 nicht mehr.</p>
<p>Für Kinder von 6 bis 18 Jahren kommt die Frühstartrente: 10 Euro im Monat vom Staat, angelegt in einem Standarddepot. Der Bundestag hat am 16. Oktober 2026 zugestimmt ({a("fsr-bt", "Bundestag")}), der Bundesrat am 20. November 2026 ({a("fsr-br", "Handelsblatt")}). Die Verkündung im Bundesgesetzblatt stand bei dieser Prüfung noch aus.</p>"""),
    ])


ERKL = os.path.join(ROOT, "data", "av-rechner-erklaerung.html")


def ohne_kommentar(t):
    return re.sub(r"^<!--.*?-->\n", "", t, flags=re.S).strip()


def umbau_rechner(page):
    """Rechner bekommt eine h2 (die h1 steht jetzt oben), Intro neu, Erklärkasten wandert nach unten."""
    page = re.sub(r'<h[12] id="h-altersvorsorgedepot">.*?</h[12]>',
                  '<h2 id="h-altersvorsorgedepot">Dein Rechner: Zulagen, Depotwert und zwei Anbieter im Vergleich</h2>', page, count=1, flags=re.S)
    page = re.sub(r'(<h2 id="h-altersvorsorgedepot">.*?</h2>\n)<p class="intro">.*?</p>\n(?:<p class="av-jump">.*?</p>\n)?',
                  lambda m: m.group(1) + '<p class="intro">Wähle einen oder zwei Anbieter und gib Beitrag, Alter und Rentenbeginn ein. Der Rechner nimmt die heutigen Kosten der Anbieter und zeigt, was bis zur Rente übrig bleibt, mit Zulagen und Steuer.</p>\n',
                  page, count=1, flags=re.S)
    page = re.sub(r'<div class="explain">\n.*?</div>\n(</div>\n<!--calc-end-->)', r"\1", page, count=1, flags=re.S)
    return page


def umbau_ratgeber(page):
    """Ratgeber-Abschnitte (von build_seo.py) als Akkordeons. Läuft nach build_seo.py."""
    m = re.search(r'<section class="seo" id="ratgeber">\n(.*?)</section>', page, flags=re.S)
    if not m or 'data-acc="1"' in m.group(0):
        return page
    teile = re.split(r"<h2>(.*?)</h2>\n", m.group(1))
    out, links = [], ""
    for i in range(1, len(teile), 2):
        titel, inhalt = teile[i], teile[i + 1].strip()
        if titel.startswith("Passende"):
            links = f'<p class="av-links"><strong>Passend dazu:</strong> ' + " · ".join(re.findall(r"<a [^>]+>.*?</a>", inhalt)) + "</p>"
            continue
        if "faq-extra" in inhalt:
            titel = "Häufige Fragen"
        inhalt = re.sub(r"<ul>\n(.*?)</ul>", lambda u: re.sub(r"<li>(.*?)</li>", r"<p>\1</p>", u.group(1)), inhalt, flags=re.S)
        out.append(f'<details class="av-acc"><summary>{titel}</summary><div>{inhalt}</div></details>')
    neu = '<section class="seo" id="ratgeber" data-acc="1">\n<h2>Beispiele und Fragen</h2>\n' + "\n".join(out) + "\n" + links + "\n</section>"
    return page[:m.start()] + neu + page[m.end():]


def main():
    page = open(PAGE, encoding="utf-8").read()
    D = json.load(open(DATA, encoding="utf-8"))
    Q = D["quellen"]
    flat, rows = [], []
    gruppen = {"befristet": [], "freiwillig": [], "laufend": [], "offen": []}
    n_anb = len(D["anbieter"])
    ohne = {}  # Anbieter -> Modelle ohne veröffentlichte Konditionen (nicht in Tabelle und Rechner)
    for a in D["anbieter"]:
        for p in a["produkte"]:
            ks, ksf, kd, kdf, eur = kennzahlen(p)
            if p["konditionen"] == "offen" or (ks is None and kd is None):
                ohne.setdefault(a["name"], []).append(p["name"])
                continue
            i = len(flat)
            flat.append({"i": i, "id": p["id"], "n": a["name"], "p": p["name"], "d": a.get("domain", ""), "art": p["art"], "pr": p["pruefstatus"],
                         "k": p["konditionen"], "r": bool(p.get("im_rechner")) and p["pruefstatus"] == "primary_verified",
                         "b": p["bestandteile"], "ks": ks, "kd": kd})
            if p["art"] in ("standard", "gesteuert") and p["pruefstatus"] == "primary_verified":
                label = f'{a["name"]} ({p["name"]})'
                if kd is None:
                    gruppen["offen"].append(label)
                elif kdf.get("freiwillig"):
                    gruppen["freiwillig"].append(label)
                elif ks is not None and ks < kd:
                    gruppen["befristet"].append(label)
                else:
                    gruppen["laufend"].append(label)
            qs = " ".join(f'<a href="{esc(Q[k]["url"])}" target="_blank" rel="noopener nofollow">{esc(Q[k]["titel"].split(":")[0])}{", " + dmy(Q[k]["datum"]) if Q[k].get("datum") else ""}</a>' for k in p["quellen"])
            hin = " ".join(x for x in [p.get("hinweis", ""), a.get("hinweis", "")] if x)
            stl = PRUEF.get(p["pruefstatus"], p["pruefstatus"])
            rows.append(
                f'<tr class="av-row" data-i="{i}" data-n="{esc(a["name"] + " " + p["name"])}" data-art="{p["art"]}" data-dau="{"" if kd is None else kd}" data-sta="{"" if ks is None else ks}">'
                f'<th scope="row"><div class="av-id">{logo(a.get("domain"))}<span><span class="av-n">{esc(a["name"])}</span><small>{esc(p["name"])}</small></span></div></th>'
                f'<td class="num{" offen" if ks is None else ""}"><b>{fig(ks, ksf)}</b></td><td class="num{" offen" if kd is None else ""}"><b>{fig(kd, kdf)}</b>{"<br><small>+ " + str(int(eur)) + " € p. a.</small>" if eur else ""}</td>'
                f'<td>{esc(ART.get(p["art"], p["art"]))}</td>'
                f'<td class="w">{esc(p["kosten_text"])}' + (f'<div class="av-h">{esc(hin)}</div>' if hin else "") + '</td>'
                f'<td class="w">{esc(p["depot_text"])}</td><td>{esc(p["auswahl_text"])}</td>'
                f'<td class="av-st{" s2" if p["pruefstatus"] != "primary_verified" else ""}">{esc(stl)}</td><td class="av-q">{qs}</td></tr>')
    n_prod = len(flat)
    n_anb_t = len({f["n"] for f in flat})
    ohne_txt = ", ".join(sorted((n for n in ohne if n not in {f["n"] for f in flat}), key=str.lower))
    n_ohne = sum(len(v) for v in ohne.values())
    n_bek = sum(1 for f in flat if f["kd"] is not None)
    aend = "".join(f'<li>{dmy(x["datum"])}: {esc(x["text"])}</li>' for x in D.get("aenderungen", [])[:8])
    nicht = "".join(f'<li><strong>{esc(x["name"])}:</strong> {esc(x["grund"])}</li>' for x in D.get("nicht_bestaetigt", []))
    bm = D.get("marktbenchmark", {})
    bmq = Q.get(bm.get("quelle", ""), {})
    art_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in ART.items())
    stand = dmy(D["stand"])
    li_g = lambda t, k: f"<p><strong>{t}:</strong> {esc(', '.join(gruppen[k]))}.</p>" if gruppen[k] else ""
    kopf = f"""<h1 class="av-title">Altersvorsorgedepot 2027: {n_anb_t} Anbieter im Vergleich</h1>
<p class="av-teaser">Ab Januar legt der Staat bis zu 540 Euro im Jahr auf deine Altersvorsorge, für jedes Kind 300 Euro mehr. Wie viel davon bis zur Rente übrig bleibt, entscheiden die Kosten des Anbieters. Hier siehst du, was Banken, Broker und Versicherer verlangen, und rechnest zwei Angebote direkt gegeneinander.</p>
<nav class="av-kurz" aria-label="Inhalt"><div class="av-kurz-t">Auf dieser Seite</div><ol>
<li><a href="#anbieter">Alle Anbieter im Überblick</a><span>{n_prod} Depotmodelle mit bekannten Konditionen, Kosten heute und im zehnten Jahr</span></li>
<li><a href="#h-altersvorsorgedepot">Dein Rechner</a><span>Zulagen, Depotwert und Auszahlung, zwei Anbieter im direkten Vergleich</span></li>
<li><a href="#gut-zu-wissen">Gut zu wissen</a><span>Förderung, Kosten, Steuer und Auszahlung kurz erklärt</span></li>
<li><a href="#ratgeber">Beispiele und Fragen</a><span>Rechenbeispiele und häufige Fragen</span></li>
</ol><div class="av-kurz-s">Stand: {stand} · keine Anlageberatung</div></nav>
"""
    body = f"""<h2 id="anbieter">Alle Anbieter im Überblick</h2>
<p>Verglichen werden alle {n_prod} Depotmodelle von {n_anb_t} Anbietern, für die es schon Konditionen gibt, direkt bei den Anbietern geprüft. Sortiere nach den Kosten heute oder im zehnten Jahr.</p>
<div class="av-filter" role="group" aria-label="Filter"><label for="av-f-art">Depotart <select id="av-f-art"><option value="">Alle</option>{art_opts}</select></label><label><input type="checkbox" id="av-f-kosten"> Nur mit bekannten Kosten im 10. Jahr</label><span class="av-count" id="av-count" aria-live="polite"></span></div>
<div class="av-tabs" id="avt" role="group" aria-label="Sortierung"><button type="button" class="av-tab" data-s="dau" aria-pressed="true">Kosten im 10. Jahr</button><button type="button" class="av-tab" data-s="sta" aria-pressed="false">Kosten zu Beginn</button><button type="button" class="av-tab" data-s="n" aria-pressed="false">A bis Z</button></div>
<p class="av-scroll-hint">Tabelle seitlich scrollen für alle Spalten →</p>
<div class="av-tablewrap" tabindex="0" role="region" aria-label="Anbietervergleich, seitlich scrollbar"><table class="av-table"><caption>Laufende Kosten in Prozent pro Jahr bei Eröffnung im Januar 2027, ohne Order- und Sparplangebühren und Spreads. „max.“ = Obergrenze laut Anbieter, „ca.“ = ungefährer Wert, * = freiwillige Erstattung ohne Enddatum.</caption><thead><tr><th scope="col">Anbieter und Depotmodell</th><th scope="col" class="num">Kosten zu Beginn</th><th scope="col" class="num">Kosten im 10. Jahr</th><th scope="col">Art</th><th scope="col">Kosten im Detail</th><th scope="col">Depot und Orders</th><th scope="col">Anlage</th><th scope="col">Beleg</th><th scope="col">Quellen</th></tr></thead>
<tbody id="avl">
{chr(10).join(rows)}
</tbody></table></div>
<button type="button" class="av-mehr" id="av-mehr" aria-expanded="false">Alle {n_prod} Depotmodelle anzeigen</button>
<p class="av-sub">Noch ohne veröffentlichte Konditionen und deshalb nicht in der Tabelle: {esc(ohne_txt)}. Ebenfalls nicht dabei sind frei gestaltete Depots, deren Kosten erst von den gewählten Fonds abhängen. Sobald Preise feststehen, nehmen wir die Modelle auf.</p>
<p class="av-sub">Die Sortierung ist keine Rangliste: Die Angaben umfassen meist nur Fonds- und Servicekosten. „nur Presse“: Zahlen aus Presseberichten, vom Anbieter online nicht bestätigt, deshalb nicht im Rechner. {esc(D["hinweis"])}</p>
"""
    unten = f"""<section id="gut-zu-wissen" class="av-unten">
<h2>Gut zu wissen</h2>
{rechts_text(D)}
<details class="av-acc"><summary>So rechnet der Rechner</summary><div>{ohne_kommentar(open(ERKL, encoding="utf-8").read())}</div></details>
<details class="av-acc"><summary>Worauf es bei den Kosten der Anbieter ankommt</summary><div>
{li_g("Erstattung zum Start, danach laufende Kosten", "befristet")}
{li_g("Erstattung ohne Enddatum, aber freiwillig und widerruflich", "freiwillig")}
{li_g("Laufende Kosten ohne Erstattung", "laufend")}
{li_g("Kosten noch nicht vollständig veröffentlicht", "offen")}
<p class="av-sub">{esc(bm.get("text", ""))} {f'<a href="{esc(bmq.get("url", ""))}" target="_blank" rel="noopener nofollow">Quelle</a>' if bmq else ""}</p></div></details>
<details class="av-acc"><summary>Geprüft, aber nicht bestätigt</summary><div><ul>{nicht}</ul></div></details>
<details class="av-acc"><summary>Änderungsprotokoll</summary><div><ul class="av-chg">{aend}</ul></div></details>
<p class="av-sub">Keine Anlageberatung. Angaben ohne Gewähr, die Konditionen können sich bis zum Start ändern. Maßgeblich sind die Vertragsunterlagen der Anbieter.</p>
</section>"""
    data = json.dumps(flat, ensure_ascii=False, separators=(",", ":"))
    block = ("<!--av-start-->\n" + '<script type="application/json" id="av-data">' + data.replace("</", "<\\/") + "</script>\n" + CSS
             + kopf + '<section id="anbieter-bereich">' + body + "</section>\n" + JS + "\n<!--av-end-->")
    block2 = "<!--av2-start-->\n" + unten + "\n<!--av2-end-->"
    # alten Handblock oberhalb des Rechners entfernen (außerhalb der Markierung), Position merken
    m_old = re.search(r'<section id="anbieter-bereich">.*?</section>\s*(?=<!--calc-start-->)', page, flags=re.S)
    page = re.sub(r"<!--av-start-->.*?<!--av-end-->\n?", "", page, flags=re.S)
    m_old = re.search(r'<section id="anbieter-bereich">.*?</section>\s*(?=<!--calc-start-->)', page, flags=re.S)
    if m_old:
        page = page[:m_old.start()] + block + "\n" + page[m_old.end():]
    elif "<!--calc-start-->" in page:
        page = page.replace("<!--calc-start-->", block + "\n<!--calc-start-->", 1)
    else:
        raise SystemExit("Einfügestelle nicht gefunden")
    page = re.sub(r"<!--av2-start-->.*?<!--av2-end-->\n?", "", page, flags=re.S)
    page = page.replace("<!--calc-end-->\n", "<!--calc-end-->\n" + block2 + "\n", 1)
    page = umbau_rechner(page)
    page = umbau_ratgeber(page)
    assert page.count('id="anbieter-bereich"') == 1 and page.count('id="av-data"') == 1 and page.count('id="gut-zu-wissen"') == 1
    assert page.count("<h1") == 1, "genau eine h1"
    title = "Altersvorsorgedepot-Rechner und Anbieter im Vergleich 2027"
    desc = (f"Altersvorsorgedepot berechnen: Zulagen, Depotwert und Auszahlung, dazu {n_anb_t} Anbieter mit {n_prod} Depotmodellen im Vergleich "
            "(N26, Trade Republic, Scalable, ING, Deka, Consorsbank) mit zeitabhängigen Kosten und Quellen.")
    page = re.sub(r"<title>.*?</title>", "<title>" + title + "</title>", page, count=1)
    page = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + desc, page, count=1)
    page = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + title, page, count=1)
    page = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + desc, page, count=1)
    open(PAGE, "w", encoding="utf-8").write(page)
    print("ok", n_anb_t, "Anbieter,", n_prod, "Depotmodelle in der Tabelle,", n_ohne, "ohne Konditionen ausgeblendet,", n_bek, "mit bekannten Kosten im 10. Jahr")


if __name__ == "__main__":
    main()
