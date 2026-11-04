"""Baut maerkte/index.html aus data/markt.json: kompakte Marktuebersicht, die auf einen Handy-Bildschirm passt (Screenshot-tauglich)."""
import json, os, sys, datetime
sys.path.insert(0, os.path.dirname(__file__))
import build_magazin as m

def de(s):
    """53,430.00 -> 53.430,00 ; 1.1215 -> 1,1215"""
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")

def main():
    d = json.load(open("data/markt.json", encoding="utf-8"))
    st = datetime.datetime.fromisoformat(d["stand"])
    stand = st.strftime("%d.%m.%Y, %H:%M Uhr")
    title = "Märkte im Überblick: Indizes, Rohstoffe und Devisen"
    desc = "Kompakte Marktübersicht mit US-, Europa- und Asien-Indizes, Gold, Öl und Euro-Dollar auf einen Blick."
    depth = 1; pre = "../"
    rows = ""
    for z in d["zeilen"]:
        c = z["c"]; cls = "up" if c > 0 else "down" if c < 0 else ""
        sg = "+" if c > 0 else "−" if c < 0 else ""
        rows += f'<tr><td>{m.esc(z["n"])}</td><td class="r">{m.esc(de(z["l"]))}</td><td class="r {cls}">{sg}{abs(c):.2f}'.replace(".", ",") + " %</td></tr>\n"
    css = ("<style>.mk{max-width:520px;margin:0 auto}.mk h1{font-size:22px;margin:8px 0 2px}.mk .meta{font-size:12px;color:#6b7782;margin:0 0 6px}"
           ".mk table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}.mk th{font-size:12px;font-weight:600;color:#6b7782;text-align:left;padding:4px 6px;border-bottom:2px solid #14202b}"
           ".mk td{padding:5px 6px;border-bottom:1px solid #e3e8ec;line-height:1.25}.mk .r{text-align:right;white-space:nowrap}.mk th.r{text-align:right}.mk .up{color:#1f8a4c;font-weight:600}.mk .down{color:#c0392b;font-weight:600}"
           ".mk .fn{font-size:11px;color:#8a97a3;margin:6px 0 0}</style>\n")
    extra = css
    o = m.head(depth, title, desc, "maerkte/", "website", m.BASE + "assets/logo.png", extra) + m.nav_html(depth, "") + "</nav></div></header>\n"
    o += f'<script src="{pre}assets/navigation.js"></script>\n<main class="wrap"><div class="mk">\n<h1>Märkte im Überblick</h1>\n<p class="meta">Stand: {stand} · Quelle: {m.esc(d.get("quelle",""))}</p>\n'
    o += '<table><thead><tr><th>Name</th><th class="r">Letzter</th><th class="r">Veränd.</th></tr></thead>\n<tbody>\n' + rows + '</tbody></table>\n'
    o += '<p class="fn">Stand zum genannten Zeitpunkt, ohne Gewähr, keine Anlageberatung. Futures und Indizes sind keine Kurse einzelner Aktien.</p>\n</div></main>\n' + m.footer_html(depth) + "\n</body>\n</html>\n"
    os.makedirs("maerkte", exist_ok=True)
    open("maerkte/index.html", "w", encoding="utf-8").write(o)
    print("maerkte/index.html gebaut,", len(d["zeilen"]), "Zeilen")

if __name__ == "__main__":
    main()
