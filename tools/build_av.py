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
.av-list{border-top:1px solid #dfe5ea}.av-row{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,2.2fr) 120px;gap:6px 18px;padding:14px 0;border-bottom:1px solid #eef1f4;align-items:start}
.av-n{font-weight:600}.av-t{font-size:.82rem;color:#8a97a3;margin-top:2px}.av-k{font-size:.92rem;color:#33414d}.av-d{font-size:.84rem;color:#6b7782;margin-top:4px}.av-d b{font-weight:500;color:#5b6874}
.av-f{text-align:right;font-size:.88rem;color:#33414d;line-height:1.35}.av-f span{display:block;color:#8a97a3;font-size:.75rem}
.av-q{font-size:.78rem;color:#8a97a3;margin-top:6px}.av-q a{color:#5b6874;margin-right:10px}
.av-h{color:#8a6d1a;font-size:.8rem;margin-top:4px}
.av-sum{margin:14px 0}.av-sum li{margin:4px 0}
@media(max-width:700px){.av-row{grid-template-columns:1fr auto}.av-row>div:nth-child(2){grid-column:1/-1;order:3}}
</style>
"""
def fig(v):
    return "–" if v is None else (f"{v:.2f}".replace(".", ",") + " %")
rows = []
for i, f in enumerate(D["firmen"]):
    q = " ".join(f'<a href="{esc(x["url"])}" target="_blank" rel="noopener nofollow">{esc(x["titel"].split(" (")[0])}</a>' for x in f["quellen"])
    rows.append(
        f'<div class="av-row" data-i="{i}" data-n="{esc(f["name"])}" data-dau="{"" if f["kosten_dauer"] is None else f["kosten_dauer"]}" data-sta="{"" if f["kosten_start"] is None else f["kosten_start"]}">'
        f'<div><div class="av-n">{esc(f["name"])}</div><div class="av-t">{esc(f["typ"])} · {esc(f["status"])}</div></div>'
        f'<div><div class="av-k">{esc(f["kosten"])}</div><div class="av-d"><b>Depot und Orders:</b> {esc(f["depot"])}</div><div class="av-d"><b>Auswahl:</b> {esc(f["fonds"])}</div>'
        + (f'<div class="av-h">{esc(f["hinweis"])}</div>' if f["hinweis"] else "") + f'<div class="av-q">Quellen: {q}</div></div>'
        f'<div class="av-f">{fig(f["kosten_start"])}<span>zu Beginn</span><div style="height:6px"></div>{fig(f["kosten_dauer"])}<span>langfristig</span></div></div>')
body = f"""<h2 id="anbieter">Anbieter im Vergleich</h2>
<p class="lead">Ab dem 1. Januar 2027 können Verträge für das neue geförderte Altersvorsorgedepot abgeschlossen werden. Hier siehst du, was Trade Republic, Scalable Capital, ING, Deka und weitere angekündigt haben. Stand der Angaben: {esc(D["stand"][8:10])}.{esc(D["stand"][5:7])}.{esc(D["stand"][:4])}.</p>
<p class="note"><strong>Wichtig:</strong> {esc(D["hinweis"])} Verglichen werden die laufenden Kosten des Standarddepots, die ETF-Erstattungen sind meist befristet. Dein Ergebnis hängt zusätzlich von Förderung, Fondsauswahl und Beitrag ab. Das ist keine Anlageberatung.</p>
<h2>Was ist am günstigsten?</h2>
<ul class="av-sum">
<li><strong>Zum Start kosten fast alle Anbieter nichts</strong> (Trade Republic, Scalable, Smartbroker+, flatex, Traders Place, Bitpanda), weil sie die ETF-Kosten zunächst erstatten. Die Erstattung ist bei den meisten befristet, bei Trade Republic ohne Enddatum, aber nicht vertraglich garantiert.</li>
<li><strong>Langfristig niedrige Kosten nennen:</strong> flatex (höchstens 0,07 % ab Jahr 6), Deka (0,1 %), Scalable (höchstens 0,15 %) und ING (0,20 %).</li>
<li><strong>Teurer, aber mit Beratung oder aktivem Management:</strong> Deutsche Bank/DWS (0,28 bis 1,13 %) und Union Investment (0,55 bis 1,0 %). Der gesetzliche Deckel für das Standarddepot liegt bei 1,0 % Effektivkosten pro Jahr.</li>
<li><strong>Noch offen:</strong> comdirect, Consorsbank und DKB haben ihr Angebot angekündigt, aber keine Konditionen veröffentlicht.</li>
</ul>
<div class="av-tabs" id="avt" role="group" aria-label="Sortierung"><button type="button" class="av-tab" data-s="dau" aria-pressed="true">Günstigste langfristig zuerst</button><button type="button" class="av-tab" data-s="sta" aria-pressed="false">Günstigste zum Start zuerst</button><button type="button" class="av-tab" data-s="n" aria-pressed="false">A bis Z</button></div>
<div class="av-list" id="avl">
{chr(10).join(rows)}
</div>
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
block = "<!--av-start-->\n" + css + '<section id="anbieter-bereich">' + body + "</section>\n" + js + "\n<!--av-end-->"
page = re.sub(r"<!--av-start-->.*?<!--av-end-->", lambda m: block, page, flags=re.S)
title = "Altersvorsorgedepot-Rechner und Anbieter im Vergleich 2027"
desc = "Altersvorsorgedepot berechnen: Zulagen, Depotwert und Auszahlung, dazu die Anbieter 2027 im Vergleich (Trade Republic, Scalable, ING, Deka, comdirect) mit Kosten und Quellen."
page = re.sub(r"<title>.*?</title>", "<title>" + title + "</title>", page, count=1)
page = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + desc, page, count=1)
page = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + title, page, count=1)
page = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + desc, page, count=1)
open(PAGE, "w", encoding="utf-8").write(page)
print("ok", len(page))
