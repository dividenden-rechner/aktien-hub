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
.av-jump{font-size:.88rem;margin:4px 0 14px;line-height:1.7}.av-jump a{white-space:nowrap}#anbieter,#aenderungen,#rechner,#rechtsstand{scroll-margin-top:72px}.av-anchor{display:block}.av-h3{font-size:1.05rem;margin:1.8rem 0 .2rem}.av-sub{font-size:.8rem;color:#6b7782;margin:4px 0 10px}
.av-rank{min-width:700px}.av-rank td.t{min-width:200px}.av-rank tr.sel td,.av-rank tr.sel th{background:#f1f9f4}.av-rank tr.off td,.av-rank tr.off th{color:#9aa5af}
.av-rank th:first-child{min-width:220px}.av-rank .av-logo{width:22px;height:22px}.av-rank .dif.pos{color:#0f6b46}.av-rank .dif.neg{color:#b3372d}
.tool .av-pick{padding:3px 10px;font-size:.78rem;font-weight:500;background:#fff;color:#33414d;border:1px solid #d5dce2;border-radius:6px}.tool .av-pick:hover{background:#f6f8fa}
.av-n{font-weight:600}
#anbieter-bereich{max-width:1100px!important}#anbieter-bereich>:not(.av-tablewrap){max-width:760px}
.av-q{min-width:170px}.av-q a{display:block;color:#5b6874;margin:0 0 3px;font-size:.78rem;text-decoration:underline;text-decoration-color:#cfd6dc}
.av-st{font-size:.78rem;white-space:nowrap}.av-st.s2{color:#8a6d1a}
.av-h{color:#8a6d1a;font-size:.78rem;margin-top:4px}
.av-sum{margin:14px 0}.av-sum li{margin:4px 0}
.av-more{border-top:1px solid #e3e7ea;border-bottom:1px solid #e3e7ea;padding:8px 0;margin:14px 0}.av-more summary{cursor:pointer;font-weight:600;color:#1a7f4b}.av-wl{list-style:none;padding:0;margin:10px 0}.av-wl li{padding:6px 0;border-bottom:1px solid #f0f2f4;font-size:.9rem;line-height:1.45}.av-wl .av-id{display:inline-flex;gap:6px;align-items:center;margin-right:4px;vertical-align:middle}
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
if(fa)fa.addEventListener("change",filt);if(fk)fk.addEventListener("change",filt);filt();
})();
</script>"""


def rechts_text(D):
    q = D["quellen"]
    a = lambda k, t: f'<a href="{esc(q[k]["url"])}" target="_blank" rel="noopener nofollow">{esc(t)}</a>'
    return f"""<h2 id="rechtsstand">Das gilt für alle Anbieter</h2>
<ul>
<li><strong>Start und Zertifizierung:</strong> Neue Verträge sind ab dem 1. Januar 2027 möglich. Das Altersvorsorgereformgesetz hat der Bundestag am 27. März 2026 beschlossen, der Bundesrat hat am 8. Mai 2026 zugestimmt, verkündet wurde es am 29. Mai 2026 ({a("bgbl", "BGBl. 2026 I Nr. 156")}). Jeder Vertrag braucht ein Zertifikat des Bundeszentralamts für Steuern.</li>
<li><strong>Förderung:</strong> Grundzulage 50 % der Beiträge bis 360 Euro und 25 % der Beiträge von 360,01 bis 1.800 Euro, zusammen höchstens 540 Euro im Jahr. Kinderzulage 100 % der Beiträge, höchstens 300 Euro je Kind. Wer zu Beginn des Beitragsjahres jünger als 25 ist, bekommt die Grundzulage einmalig um 200 Euro erhöht. Alle Zulagen gibt es nur bei mindestens 120 Euro Eigenbeitrag im Jahr.</li>
<li><strong>Beiträge:</strong> höchstens 6.840 Euro im Jahr je Vertrag, gefördert und als Sonderausgabe absetzbar sind bis zu 1.800 Euro plus Zulagen. Gefördert werden höchstens zwei Verträge nach neuem Recht, ab dem dritten zählen Beiträge nicht mehr als Altersvorsorgebeiträge.</li>
<li><strong>Kosten:</strong> Das Standarddepot darf höchstens 1,0 % Effektivkosten im Jahr haben. Für frei gestaltete Depots und Garantieprodukte (80 oder 100 % der Beiträge und Zulagen) gibt es keinen Deckel.</li>
<li><strong>Anbieterwechsel:</strong> In den ersten fünf Jahren nach Vertragsabschluss darf der bisherige Anbieter höchstens 150 Euro verlangen, danach ist die Übertragung kostenfrei. Der neue Anbieter darf eine einmalige Verwaltungspauschale von höchstens 150 Euro berechnen.</li>
<li><strong>Standarddepot:</strong> zwei Fonds, einer der Risikoklasse 1 oder 2 und einer der Klassen 3 bis 5. Fünf Jahre vor Auszahlungsbeginn höchstens 50 %, zwei Jahre vorher höchstens 30 % im risikoreicheren Fonds, außer du verlangst eine andere Aufteilung.</li>
<li><strong>Steuer:</strong> In der Ansparphase fallen keine Steuern auf Erträge an. Die Auszahlungen werden nachgelagert mit deinem persönlichen Steuersatz versteuert.</li>
<li><strong>Auszahlung:</strong> frühestens ab 65, spätestens ab 70 (ohne Vereinbarung ab 65). Bis zu 30 % des Kapitals sind zu Beginn auf einmal möglich, der Rest als lebenslange Rente oder Auszahlungsplan mindestens bis 85.</li>
<li><strong>Riester:</strong> Verträge, die bis 31.12.2026 abgeschlossen werden, laufen mit Bestandsschutz weiter. Neue Riester-Verträge gibt es ab 2027 nicht mehr.</li>
<li><strong>Frühstartrente:</strong> 10 Euro im Monat vom Staat für Kinder von 6 bis 18 Jahren, angelegt in einem Standarddepot-Vertrag. Der Bundestag hat das Gesetz am 16. Oktober 2026 beschlossen ({a("fsr-bt", "Bundestag")}), der Bundesrat hat am 20. November 2026 zugestimmt ({a("fsr-br", "Handelsblatt")}). Die Verkündung im Bundesgesetzblatt stand bei dieser Prüfung noch aus.</li>
</ul>"""


def im_vergleich(p):
    """In die Tabelle kommt nur, was zertifiziert, vom Anbieter online belegt und ein Depot (keine Garantie) ist."""
    return bool(p.get("zertifikate")) and p["pruefstatus"] == "primary_verified" and p["art"] != "garantie"


def main():
    page = open(PAGE, encoding="utf-8").read()
    D = json.load(open(DATA, encoding="utf-8"))
    Q = D["quellen"]
    flat, rows = [], []
    gruppen = {"befristet": [], "freiwillig": [], "laufend": [], "offen": []}
    n_anb = len(D["anbieter"])
    weitere = []
    for a in D["anbieter"]:
        for p in a["produkte"]:
            if not im_vergleich(p):
                weitere.append((a, p))
                continue
            i = len(flat)
            ks, ksf, kd, kdf, eur = kennzahlen(p)
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
            zt = "<br>".join(f'Nr. {esc(z["nr"])}' for z in p["zertifikate"])
            rows.append(
                f'<tr class="av-row" data-i="{i}" data-n="{esc(a["name"] + " " + p["name"])}" data-art="{p["art"]}" data-dau="{"" if kd is None else kd}" data-sta="{"" if ks is None else ks}">'
                f'<th scope="row"><div class="av-id">{logo(a.get("domain"))}<span><span class="av-n">{esc(a["name"])}</span><small>{esc(p["name"])}</small></span></div></th>'
                f'<td class="num{" offen" if ks is None else ""}"><b>{fig(ks, ksf)}</b></td><td class="num{" offen" if kd is None else ""}"><b>{fig(kd, kdf)}</b>{"<br><small>+ " + str(int(eur)) + " € p. a.</small>" if eur else ""}</td>'
                f'<td>{esc(ART.get(p["art"], p["art"]))}</td>'
                f'<td class="w">{esc(p["kosten_text"])}' + (f'<div class="av-h">{esc(hin)}</div>' if hin else "") + '</td>'
                f'<td class="w">{esc(p["depot_text"])}</td><td>{esc(p["auswahl_text"])}</td>'
                f'<td class="av-st">{zt}</td><td class="av-q">{qs}</td></tr>')
    n_prod = len(flat)
    n_anb_v = len({f["n"] for f in flat})
    # weitere Anbieter für den aufklappbaren Bereich, je Anbieter eine Zeile
    wa = {}
    for a, p in weitere:
        wa.setdefault(a["name"], []).append((a, p))
    def grund(p):
        if p["art"] == "garantie":
            return "Garantieprodukt, kein Altersvorsorgedepot"
        if p["pruefstatus"] != "primary_verified":
            return "nur aus Presseberichten bekannt"
        if not p.get("zertifikate"):
            return "noch kein BZSt-Zertifikat"
        return "noch nicht im Vergleich"
    w_li = []
    for name in sorted(wa, key=str.lower):
        teile = "; ".join(f'{esc(p["name"])}: {esc(p["kosten_text"])} ({grund(p)})' for _, p in wa[name])
        w_li.append(f'<li><span class="av-id">{logo(wa[name][0][0].get("domain"), 20)}<strong>{esc(name)}</strong></span> {teile}</li>')
    w_zert = "".join(f'<li><strong>{esc(x["name"])}:</strong> {esc(x["grund"])}</li>' for x in D.get("weitere_zertifikate", []))
    n_bek = sum(1 for f in flat if f["kd"] is not None)
    li_g = lambda t, k: f"<li><strong>{t}:</strong> {esc(', '.join(gruppen[k]))}.</li>" if gruppen[k] else ""
    aend = "".join(f'<li>{dmy(x["datum"])}: {esc(x["text"])}</li>' for x in D.get("aenderungen", [])[:8])
    nicht = "".join(f'<li><strong>{esc(x["name"])}:</strong> {esc(x["grund"])}</li>' for x in D.get("nicht_bestaetigt", []))
    bm = D.get("marktbenchmark", {})
    bmq = Q.get(bm.get("quelle", ""), {})
    art_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in ART.items())
    body = f"""<nav class="av-jump" aria-label="Sprungmarken">Direkt zu: <a href="#anbieter">Zertifizierte Anbieter</a> · <a href="#rechner">Rechner: selbst durchrechnen</a> · <a href="#aenderungen">Letzte Änderungen ({dmy(D.get("aenderungen", [{}])[0].get("datum", D["stand"]))})</a> · <a href="#rechtsstand">Was für alle gilt</a></nav>
<h2 id="anbieter">Zertifizierte Altersvorsorgedepots im Vergleich</h2>
<p class="lead">Ab dem 1. Januar 2027 können Verträge für das geförderte Altersvorsorgedepot abgeschlossen werden. In der Tabelle stehen nur Depotmodelle, die das Bundeszentralamt für Steuern bereits zertifiziert hat und die der Anbieter auf seiner Website als Altersvorsorgedepot anbietet: derzeit {n_prod} Modelle von {n_anb_v} Anbietern. Viele Banken haben ein Depot angekündigt, aber noch kein Zertifikat. Sie stehen unter der Tabelle zum Aufklappen. Stand: {dmy(D["stand"])}.</p>
<p class="note"><strong>Wichtig:</strong> {esc(D["hinweis"])} {esc(D.get("zertifizierung", ""))} Das ist keine Anlageberatung.</p>
<div class="av-filter" role="group" aria-label="Filter"><label for="av-f-art">Depotart <select id="av-f-art"><option value="">Alle</option>{art_opts}</select></label><label><input type="checkbox" id="av-f-kosten"> Nur mit bekannten Kosten im 10. Jahr</label><span class="av-count" id="av-count" aria-live="polite"></span></div>
<div class="av-tabs" id="avt" role="group" aria-label="Sortierung"><button type="button" class="av-tab" data-s="dau" aria-pressed="true">Kosten im 10. Jahr</button><button type="button" class="av-tab" data-s="sta" aria-pressed="false">Kosten zu Beginn</button><button type="button" class="av-tab" data-s="n" aria-pressed="false">A bis Z</button></div>
<p class="av-scroll-hint">Tabelle seitlich scrollen für alle Spalten →</p>
<div class="av-tablewrap" tabindex="0" role="region" aria-label="Anbietervergleich, seitlich scrollbar"><table class="av-table"><caption>Nur vom Bundeszentralamt für Steuern zertifizierte Altersvorsorgedepots. Laufende Kosten in Prozent pro Jahr bei Eröffnung im Januar 2027, ohne Order- und Sparplangebühren und Spreads. „max.“ = Obergrenze laut Anbieter, „ca.“ = ungefährer Wert, * = freiwillige Erstattung ohne Enddatum.</caption><thead><tr><th scope="col">Anbieter und Depotmodell</th><th scope="col" class="num">Kosten zu Beginn</th><th scope="col" class="num">Kosten im 10. Jahr</th><th scope="col">Art</th><th scope="col">Kosten im Detail</th><th scope="col">Depot und Orders</th><th scope="col">Anlage</th><th scope="col">BZSt-Zertifikat</th><th scope="col">Quellen</th></tr></thead>
<tbody id="avl">
{chr(10).join(rows)}
</tbody></table></div>
<p class="av-sub">Sortierung nach Kosten ist keine Rangliste: Die Angaben umfassen meist nur Fonds- und Servicekosten, nicht die vollständigen Effektivkosten. Die Zertifikatsnummern stammen aus der <a href="{esc(Q["bzst"]["url"])}" target="_blank" rel="noopener nofollow">Liste aller erteilten Zertifikate des BZSt</a>, abgerufen am {dmy(Q["bzst"]["abgerufen"])}.</p>
<p>Die meisten Banken haben ihr Altersvorsorgedepot angekündigt, viele auch schon mit Preisen, etwa N26, ING, die Consorsbank, flatex, die Deka oder die Hannoversche. Zertifiziert ist ihr Produkt aber noch nicht, oder es steht in der BZSt-Liste noch nicht. Ohne Zertifikat darf kein Vertrag mit Förderung abgeschlossen werden. Sobald ein Zertifikat erscheint, nehmen wir das Modell in die Tabelle auf.</p>
<details class="av-more"><summary>Alle weiteren Banken und Anbieter ({len(wa)})</summary>
<ul class="av-wl">{"".join(w_li)}</ul>
<p class="av-sub">Weitere Einträge in der BZSt-Liste mit Wirksamkeit ab 1.1.2027, die nicht in der Tabelle stehen:</p>
<ul>{w_zert}</ul>
<p class="av-sub">Geprüft, aber vom Anbieter nicht bestätigt:</p>
<ul>{nicht}</ul>
</details>
<h3 class="av-h3">Worauf es bei den Kosten ankommt</h3>
<ul class="av-sum">
{li_g("Erstattung zum Start, danach laufende Kosten", "befristet")}
{li_g("Erstattung ohne Enddatum, aber freiwillig und widerruflich", "freiwillig")}
{li_g("Laufende Kosten ohne Erstattung", "laufend")}
{li_g("Kosten noch nicht (vollständig) veröffentlicht", "offen")}
</ul>
<p><a href="#rechner"><strong>Zum Rechner</strong></a>: Dort kannst du die zertifizierten Modelle mit deinen Eingaben durchrechnen, auch mit späterem Vertragsbeginn. Wo die Kosten noch nicht veröffentlicht sind, rechnet der Rechner mit deiner eigenen Annahme.</p>
<p class="av-sub">{esc(bm.get("text", ""))} {f'<a href="{esc(bmq.get("url", ""))}" target="_blank" rel="noopener nofollow">Quelle</a>' if bmq else ""}</p>
<h3 class="av-h3" id="aenderungen">Letzte Änderungen</h3>
<ul class="av-chg">{aend}</ul>
{rechts_text(D)}
<p class="note"><strong>Hinweis:</strong> Keine Anlageberatung. Angaben ohne Gewähr, die Konditionen können sich bis zum Start ändern. Maßgeblich sind die Vertragsunterlagen der Anbieter.</p>
"""
    data = json.dumps(flat, ensure_ascii=False, separators=(",", ":"))
    block = ("<!--av-start-->\n" + '<script type="application/json" id="av-data">' + data.replace("</", "<\\/") + "</script>\n" + CSS
             + '<section id="anbieter-bereich">' + body + "</section>\n" + '<span id="rechner" class="av-anchor"></span>\n' + JS + "\n<!--av-end-->")
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
    assert page.count('id="anbieter-bereich"') == 1 and page.count('id="av-data"') == 1
    title = "Altersvorsorgedepot-Rechner und Anbieter im Vergleich 2027"
    desc = (f"Altersvorsorgedepot berechnen: Zulagen, Depotwert und Auszahlung, dazu die vom BZSt zertifizierten Depotmodelle im Vergleich "
            "(Trade Republic, Scalable, Allianz, ERGO) und alle angekündigten Anbieter mit Kosten und Quellen.")
    page = re.sub(r"<title>.*?</title>", "<title>" + title + "</title>", page, count=1)
    page = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + desc, page, count=1)
    page = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + title, page, count=1)
    page = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + desc, page, count=1)
    open(PAGE, "w", encoding="utf-8").write(page)
    print("ok", n_prod, "zertifizierte Modelle im Vergleich,", len(weitere), "weitere,", n_bek, "mit bekannten Kosten im 10. Jahr")


if __name__ == "__main__":
    main()
