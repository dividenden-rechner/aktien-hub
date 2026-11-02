#!/usr/bin/env python3
"""Baut altersvorsorgedepot/index.html aus data/av-anbieter.json in die Markierung av-start/av-end der Rechnerseite (erzeugt von tools/split_rechner.py)."""
import html, json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "altersvorsorgedepot", "index.html")
page = open(PAGE, encoding="utf-8").read()
D = json.load(open(os.path.join(ROOT, "data", "av-anbieter.json"), encoding="utf-8"))
esc = html.escape
css = """<style>
[hidden]{display:none!important}
.av-tabs{display:flex;gap:18px;overflow-x:auto;margin:10px 0 10px;border-bottom:1px solid #dfe5ea;white-space:nowrap;scrollbar-width:none}.av-tabs::-webkit-scrollbar{display:none}
.av-tab{flex:0 0 auto;border:0;border-bottom:2px solid transparent;margin-bottom:-1px;background:none;border-radius:0;padding:6px 0 8px;cursor:pointer;font:inherit;font-size:13px;font-weight:500;color:#8a97a3}.av-tab:hover{color:#5b6874}.av-tab[aria-pressed=true]{color:#33414d;font-weight:600;border-bottom-color:#8a97a3}
.av-id{display:flex;gap:10px;align-items:center}.av-logo{width:28px;height:28px;object-fit:contain;border-radius:6px;border:1px solid #eef1f4;background:#fff;padding:2px;flex:none}
.av-scroll-hint{display:none;font-size:.78rem;color:#8a97a3;margin:6px 0 4px}
.av-tablewrap{overflow-x:auto;border:1px solid #e3e8ec;border-radius:8px;margin:6px 0 18px;-webkit-overflow-scrolling:touch}
.av-table{line-height:1.4;border-collapse:separate;border-spacing:0;width:100%;min-width:1180px;font-size:.86rem;color:#33414d}
.av-table th,.av-table td{padding:10px 14px;text-align:left;vertical-align:top;border-bottom:1px solid #eef1f4;background:#fff}
.av-table thead th{position:sticky;top:0;background:#f6f8fa;font-size:.74rem;font-weight:600;color:#5b6874;text-transform:uppercase;letter-spacing:.03em;white-space:nowrap;border-bottom:1px solid #e3e8ec}
.av-table tbody tr:last-child th,.av-table tbody tr:last-child td{border-bottom:0}
.av-table tbody tr:hover td,.av-table tbody tr:hover th{background:#fafcfb}
.av-table th:first-child{position:sticky;left:0;z-index:2;min-width:190px;box-shadow:1px 0 0 #e3e8ec}
.av-table thead th:first-child{z-index:3}
.av-table .num{text-align:right;white-space:nowrap;min-width:96px}.av-table td.num b{font-weight:600;color:#065f46}
.av-table td.w{min-width:260px;max-width:320px}.av-table td,.av-table th[scope=row]{height:1px}
.tool .av-table th,.tool .av-table td{border:0;border-bottom:1px solid #eef1f4}.tool .av-table tbody th{color:#33414d;background:#fff;text-align:left;font-weight:600}.tool .av-table thead th{color:#5b6874;background:#f6f8fa;text-align:left}.tool .av-table .num{text-align:right}.tool .av-table tbody tr:last-child th,.tool .av-table tbody tr:last-child td{border-bottom:0}.tool .av-rank tr.sel th,.tool .av-rank tr.sel td{background:#f1f9f4}.tool .av-rank tr.off th{color:#9aa5af}
.av-jump{font-size:.88rem;margin:-4px 0 14px}.av-h3{font-size:1.05rem;margin:1.8rem 0 .2rem}.av-sub{font-size:.85rem;color:#6b7782;margin:0 0 8px}
.av-rank{min-width:660px}.av-rank td.t{white-space:nowrap}.av-rank tr.sel td,.av-rank tr.sel th{background:#f1f9f4}.av-rank tr.off td,.av-rank tr.off th{color:#9aa5af}
.av-rank th:first-child{min-width:220px}.av-rank .av-id span{white-space:nowrap}.av-rank .av-logo{width:22px;height:22px}.av-rank .dif.pos{color:#0f6b46}.av-rank .dif.neg{color:#b3372d}
.tool .av-pick{padding:3px 10px;font-size:.78rem;font-weight:500;background:#fff;color:#33414d;border:1px solid #d5dce2;border-radius:6px}.tool .av-pick:hover{background:#f6f8fa}
.av-provg{grid-column:1/-1}.av-provg select{max-width:340px}
.av-n{font-weight:600;white-space:nowrap}
#anbieter-bereich{max-width:1100px!important}#anbieter-bereich>:not(.av-tablewrap){max-width:760px}
.av-q{white-space:nowrap;min-width:150px}.av-q a{display:block;color:#5b6874;margin:0 0 3px;font-size:.78rem;text-decoration:underline;text-decoration-color:#cfd6dc}
.av-h{color:#8a6d1a;font-size:.78rem;margin-top:4px}
.av-sum{margin:14px 0}.av-sum li{margin:4px 0}
@media(max-width:900px){.av-scroll-hint{display:block}.av-table th:first-child{min-width:150px}}
</style>
"""
DOM = {"flatex / Degiro (Core)": "flatex.de", "Deka (Sparkassen)": "deka.de", "Scalable Capital": "scalable.capital", "ING": "ing.de", "Trade Republic": "traderepublic.com", "Smartbroker+": "smartbroker.de", "Traders Place": "traders-place.de", "Bitpanda": "bitpanda.com", "Deutsche Bank (DWS)": "deutsche-bank.de", "DWS (VorsorgeDepot)": "dws.com", "Union Investment": "union-investment.de", "quirion": "quirion.de", "comdirect": "comdirect.de", "Consorsbank": "consorsbank.de", "DKB": "dkb.de"}
def logo(name):
    d = DOM.get(name)
    if not d:
        return ""
    return (f'<img class="av-logo" src="https://t1.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://{d}&size=64" '
            f'alt="" width="28" height="28" loading="lazy" onerror="this.style.visibility=\'hidden\'">')
def fig(v):
    return "–" if v is None else (f"{v:.2f}".replace(".", ",") + " %")
rows = []
for i, f in enumerate(D["firmen"]):
    q = " ".join(f'<a href="{esc(x["url"])}" target="_blank" rel="noopener nofollow">{esc(x["titel"].split(" (")[0])}</a>' for x in f["quellen"])
    rows.append(
        f'<tr class="av-row" data-i="{i}" data-n="{esc(f["name"])}" data-dau="{"" if f["kosten_dauer"] is None else f["kosten_dauer"]}" data-sta="{"" if f["kosten_start"] is None else f["kosten_start"]}">'
        f'<th scope="row"><div class="av-id">{logo(f["name"])}<span class="av-n">{esc(f["name"])}</span></div></th>'
        f'<td class="num"><b>{fig(f["kosten_start"])}</b></td><td class="num"><b>{fig(f["kosten_dauer"])}</b></td>'
        f'<td class="w">{esc(f["kosten"])}' + (f'<div class="av-h">{esc(f["hinweis"])}</div>' if f["hinweis"] else "") + '</td>'
        f'<td class="w">{esc(f["depot"])}</td><td class="w">{esc(f["fonds"])}</td>'
        f'<td>{esc(f["typ"])}</td><td>{esc(f["status"])}</td><td class="av-q">{q}</td></tr>')
def dmy(s):
    return f"{s[8:10]}.{s[5:7]}.{s[:4]}"
GEPR = (f" Zuletzt automatisch auf Änderungen geprüft am {dmy(D['geprueft'])}." if D.get("geprueft") else "")
FELD = {"kosten_start": "Kosten zu Beginn", "kosten_dauer": "Kosten langfristig", "start_jahre": "Jahre der Erstattung"}
AEND = ""
if D.get("aenderungen"):
    li = "".join(f'<li>{dmy(a["datum"])}: <strong>{esc(a["anbieter"])}</strong>, {FELD.get(a["feld"], a["feld"])} von {"offen" if a["alt"] is None else fig(a["alt"]) if a["feld"] != "start_jahre" else str(a["alt"])} auf {fig(a["neu"]) if a["feld"] != "start_jahre" else str(a["neu"])} (<a href="{esc(a["quelle"])}" target="_blank" rel="noopener nofollow">Quelle</a>)</li>' for a in reversed(D["aenderungen"][-6:]))
    AEND = f'<h3 class="av-h3">Letzte Änderungen</h3><ul class="av-chg">{li}</ul>'
body = f"""<h2 id="anbieter">Anbieter im Vergleich</h2>
<p class="lead">Ab dem 1. Januar 2027 können Verträge für das neue geförderte Altersvorsorgedepot abgeschlossen werden. Hier siehst du, was Trade Republic, Scalable Capital, ING, Deka und weitere angekündigt haben. Stand der Angaben: {esc(D["stand"][8:10])}.{esc(D["stand"][5:7])}.{esc(D["stand"][:4])}.{GEPR}</p>
<p class="note"><strong>Wichtig:</strong> {esc(D["hinweis"])} Verglichen werden die laufenden Kosten des Standarddepots, die ETF-Erstattungen sind meist befristet. Dein Ergebnis hängt zusätzlich von Förderung, Fondsauswahl und Beitrag ab. Das ist keine Anlageberatung.</p>
<h2>Was ist am günstigsten?</h2>
<ul class="av-sum">
<li><strong>Zum Start kosten fast alle Anbieter nichts</strong> (Trade Republic, Scalable, Smartbroker+, flatex, Traders Place, Bitpanda), weil sie die ETF-Kosten zunächst erstatten. Die Erstattung ist bei den meisten befristet, bei Trade Republic ohne Enddatum, aber nicht vertraglich garantiert.</li>
<li><strong>Langfristig niedrige Kosten nennen:</strong> flatex (höchstens 0,07 % ab Jahr 6), Deka (0,1 %), Scalable (höchstens 0,15 %) und ING (0,20 %).</li>
<li><strong>Teurer, aber mit Beratung oder aktivem Management:</strong> Deutsche Bank/DWS (0,28 bis 1,13 %) und Union Investment (0,55 bis 1,0 %). Der gesetzliche Deckel für das Standarddepot liegt bei 1,0 % Effektivkosten pro Jahr.</li>
<li><strong>Noch offen:</strong> comdirect, Consorsbank und DKB haben ihr Angebot angekündigt, aber keine Konditionen veröffentlicht.</li>
</ul>
<div class="av-tabs" id="avt" role="group" aria-label="Sortierung"><button type="button" class="av-tab" data-s="dau" aria-pressed="true">Günstigste langfristig zuerst</button><button type="button" class="av-tab" data-s="sta" aria-pressed="false">Günstigste zum Start zuerst</button><button type="button" class="av-tab" data-s="n" aria-pressed="false">A bis Z</button></div>
<p class="av-scroll-hint">Tabelle seitlich scrollen für alle Spalten →</p>
<div class="av-tablewrap" tabindex="0" role="region" aria-label="Anbietervergleich, seitlich scrollbar"><table class="av-table"><thead><tr><th scope="col">Anbieter</th><th scope="col" class="num">Kosten zu Beginn</th><th scope="col" class="num">Kosten langfristig</th><th scope="col">Kosten im Detail</th><th scope="col">Depot und Orders</th><th scope="col">Auswahl</th><th scope="col">Typ</th><th scope="col">Stand</th><th scope="col">Quellen</th></tr></thead>
<tbody id="avl">
{chr(10).join(rows)}
</tbody></table></div>
{AEND}
<h2>Das gilt für alle Anbieter</h2>
<ul>
<li><strong>Start:</strong> 1. Januar 2027. Das Gesetz zur Reform der privaten Altersvorsorge hat der Bundestag am 27. März 2026 beschlossen, der Bundesrat hat am 8. Mai 2026 zugestimmt. Vor der Zertifizierung durch das Bundeszentralamt für Steuern darf kein Anbieter Verträge verkaufen.</li>
<li><strong>Förderung:</strong> 50 Cent je Euro auf die ersten 360 Euro Eigenbeitrag im Jahr, 25 Cent je Euro bis 1.800 Euro, zusammen höchstens 540 Euro Grundzulage. Kinderzulage 1 Euro je Euro, höchstens 300 Euro je Kind. Einmalig 200 Euro Bonus bei Abschluss vor dem 25. Geburtstag.</li>
<li><strong>Beiträge:</strong> mindestens 120 Euro im Jahr, höchstens 6.840 Euro (570 Euro im Monat), davon gefördert bis 1.800 Euro.</li>
<li><strong>Kosten:</strong> Jeder Anbieter muss ein Standarddepot mit höchstens 1,0 % Effektivkosten pro Jahr anbieten. Beim frei gestalteten Depot gibt es keinen gesetzlichen Deckel. Der Anbieterwechsel ist nach fünf Jahren kostenfrei, der neue Anbieter darf höchstens 150 Euro berechnen.</li>
<li><strong>Steuer:</strong> Keine Steuer in der Ansparphase, auch keine Vorabpauschale. Die Auszahlung wird nachgelagert mit deinem persönlichen Steuersatz versteuert, frühestens ab 65 und spätestens ab 70, als Rente oder Auszahlplan mindestens bis 85.</li>
<li><strong>Riester:</strong> Bestehende Verträge laufen weiter. Neue Riester-Verträge gibt es ab 2027 nicht mehr.</li>
<li><strong>Frühstartrente:</strong> Der Bund will Kindern vom 6. bis zum 18. Lebensjahr 10 Euro im Monat zahlen. Das Kabinett hat den Entwurf am 12. August 2026 beschlossen, Bundestag und Bundesrat haben noch nicht entschieden (Stand 20.10.2026).</li>
</ul>
<p>Trage die Kosten deines Anbieters im Rechner oben unter „Kosten im Altersvorsorgedepot“ ein, dann siehst du die Förderung und den Vergleich mit einem ETF-Sparplan.</p>
<h2>Quellen</h2>
<ul>
<li><a href="https://www.test.de/Altersvorsorgedepot-Preiskampf-der-Anbieter-ING-Trade-Republic-Smartbroker-6335719-0/" target="_blank" rel="noopener nofollow">Stiftung Warentest, 13.10.2026</a></li>
<li><a href="https://finanzwissen.de/vergleich/depot/altersvorsorge/" target="_blank" rel="noopener nofollow">finanzwissen.de, Stand 29.10.2026</a></li>
<li><a href="https://www.capitalo.de/depot/altersvorsorgedepot" target="_blank" rel="noopener nofollow">Capitalo, Stand 22.10.2026</a></li>
<li><a href="https://www.cash-online.de/a/ing-bringt-altersvorsorgedepot-2027-ohne-order-und-depotgebuehren-728576/" target="_blank" rel="noopener nofollow">Cash., 26.10.2026</a>, <a href="https://www.cash-online.de/a/neobroker-trade-republic-verschaerft-preiskampf-um-altersvorsorgedepots-727533/" target="_blank" rel="noopener nofollow">Cash., 13.10.2026</a></li>
<li><a href="https://www.ing.de/wissen/altersvorsorgedepot/" target="_blank" rel="noopener nofollow">ING, Stand 14.07.2026</a></li>
</ul>
<p class="note"><strong>Hinweis:</strong> Keine Anlageberatung. Angaben ohne Gewähr, die Konditionen können sich bis zum Start ändern. Maßgeblich sind die Vertragsunterlagen der Anbieter.</p>
"""
js = """<script>
(function(){var l=document.getElementById("avl"),t=document.getElementById("avt");
function key(r,s){if(s==="n")return r.dataset.n.toLowerCase();var v=r.dataset[s];return v===""?1e9:parseFloat(v)}
t.onclick=function(e){var b=e.target.closest(".av-tab");if(!b)return;var s=b.dataset.s;Array.prototype.forEach.call(t.children,function(x){x.setAttribute("aria-pressed",x===b)});
var rows=Array.prototype.slice.call(l.children);rows.sort(function(a,b){var x=key(a,s),y=key(b,s);return x<y?-1:x>y?1:(+a.dataset.i)-(+b.dataset.i)});rows.forEach(function(r){l.appendChild(r)})};
})();
</script>"""
data = json.dumps([{"n": f["name"], "d": DOM.get(f["name"], ""), "ks": f["kosten_start"], "kd": f["kosten_dauer"], "j": f.get("start_jahre", 0)} for f in D["firmen"]], ensure_ascii=False)
block = "<!--av-start-->\n" + '<script type="application/json" id="av-data">' + data + "</script>\n" + css + '<section id="anbieter-bereich">' + body + "</section>\n" + js + "\n<!--av-end-->"
page = re.sub(r"<!--av-start-->.*?<!--av-end-->", lambda m: block, page, flags=re.S)
title = "Altersvorsorgedepot-Rechner und Anbieter im Vergleich 2027"
desc = "Altersvorsorgedepot berechnen: Zulagen, Depotwert und Auszahlung, dazu die Anbieter 2027 im Vergleich (Trade Republic, Scalable, ING, Deka, comdirect) mit Kosten und Quellen."
page = re.sub(r"<title>.*?</title>", "<title>" + title + "</title>", page, count=1)
page = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + desc, page, count=1)
page = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + title, page, count=1)
page = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + desc, page, count=1)
open(PAGE, "w", encoding="utf-8").write(page)
print("ok", len(page))
