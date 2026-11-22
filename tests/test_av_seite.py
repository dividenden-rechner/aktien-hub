#!/usr/bin/env python3
"""Tests für den Altersvorsorgedepot-Vergleich: Seitenbau, Prüf-Bot und Darstellung im Browser (Handy und Desktop).

Aufruf: python3 -m unittest tests/test_av_seite.py
Die Browser-Tests laufen mit Playwright und Chrome und werden übersprungen, wenn beides fehlt.
"""
import functools, hashlib, http.server, json, os, shutil, socketserver, subprocess, sys, tempfile, threading, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "altersvorsorgedepot", "index.html")
DATA = os.path.join(ROOT, "data", "av-anbieter.json")
LOG = os.path.join(ROOT, "data", "av-pruefung.json")
sys.path.insert(0, os.path.join(ROOT, "tools"))


def md5(p):
    with open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


class Seitenbau(unittest.TestCase):
    def test_build_ist_idempotent_und_ohne_doppelten_datenstand(self):
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_av.py")], check=True, capture_output=True)
        h1 = md5(PAGE)
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_av.py")], check=True, capture_output=True)
        self.assertEqual(h1, md5(PAGE))
        s = open(PAGE, encoding="utf-8").read()
        self.assertEqual(s.count('id="anbieter-bereich"'), 1)
        self.assertEqual(s.count('id="av-data"'), 1)
        self.assertEqual(s.count("<!--av-start-->"), 1)
        self.assertLess(s.index("<!--av-start-->"), s.index("<!--calc-start-->"), "Vergleich steht wie bisher über dem Rechner")

    def test_kennzahlen_der_tabelle(self):
        import build_av as b
        D = json.load(open(DATA, encoding="utf-8"))
        P = {p["id"]: p for a in D["anbieter"] for p in a["produkte"]}
        self.assertEqual(b.kennzahlen(P["n26-standard"])[0], 0.0)
        self.assertEqual(b.kennzahlen(P["n26-standard"])[2], 0.09)
        self.assertIsNone(b.kennzahlen(P["sb-standard"])[2])
        self.assertEqual(b.fig(0.07, {"max": True}), "max. 0,07 %")
        self.assertEqual(b.fig(None), "noch offen")

    def test_rechtsstand_ohne_veraltete_aussagen(self):
        s = open(PAGE, encoding="utf-8").read()
        self.assertNotIn("verkündet am 26. Mai 2026", s)
        self.assertNotIn("Bundestag und Bundesrat haben noch nicht entschieden", s)
        self.assertIn("29. Mai 2026", s)
        self.assertIn("20. November 2026", s)
        self.assertNotIn("Was ist am günstigsten?", s, "keine Rangaussage ohne Effektivkosten")


class PruefBot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copy(DATA, os.path.join(self.tmp, "d.json"))
        self.had_log = os.path.exists(LOG)
        if self.had_log:
            shutil.copy(LOG, os.path.join(self.tmp, "l.json"))

    def tearDown(self):
        shutil.copy(os.path.join(self.tmp, "d.json"), DATA)
        if self.had_log:
            shutil.copy(os.path.join(self.tmp, "l.json"), LOG)
        shutil.rmtree(self.tmp)

    def test_funde_werden_protokolliert_aber_nicht_uebernommen(self):
        url = "https://n26.com/de-de/altersvorsorgedepot"
        text = ("N26 Altersvorsorgedepot. " * 30) + "Bei N26 betragen die Fondskosten ab 2029 rund 0,09 % pro Jahr. Bei N26 kostet das Depot künftig 0,25 % im Jahr."
        mock = {"seiten": {url: text}, "funde": [
            {"url": url, "anbieter": "N26 – Standarddepot", "kosten_dauer": 0.09, "beleg": "Bei N26 betragen die Fondskosten ab 2029 rund 0,09 % pro Jahr."},
            {"url": url, "anbieter": "N26 – Standarddepot", "kosten_dauer": 0.25, "beleg": "Bei N26 kostet das Depot künftig 0,25 % im Jahr."},
            {"url": url, "anbieter": "N26 – Standarddepot", "kosten_dauer": 0.5, "beleg": "Dieser Satz steht nicht auf der Seite, N26 0,5 %"}]}
        mp = os.path.join(self.tmp, "mock.json")
        json.dump(mock, open(mp, "w", encoding="utf-8"))
        vorher = json.load(open(DATA, encoding="utf-8"))
        env = dict(os.environ, AV_CHECK_MOCK=mp)
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "av_check.py")], check=True, capture_output=True, env=env, cwd=ROOT)
        nachher = json.load(open(DATA, encoding="utf-8"))
        log = json.load(open(LOG, encoding="utf-8"))
        self.assertEqual(vorher["anbieter"], nachher["anbieter"], "Daten dürfen nicht automatisch geändert werden")
        self.assertEqual(len(log["bestaetigt"]), 1)
        self.assertEqual(len(log["abweichungen"]), 1)
        self.assertEqual(log["abweichungen"][0]["gefunden"], 0.25)
        self.assertTrue(any("wortgetreu" in v["grund"] for v in log["verworfen"]))


def _chrome():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:
        return None
    for p in ("/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"):
        if os.path.exists(p):
            return p
    return None


@unittest.skipUnless(_chrome(), "Playwright/Chrome nicht verfügbar")
class Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Leise(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        handler = functools.partial(Leise, directory=ROOT)
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=_chrome(), args=["--no-sandbox"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.httpd.shutdown()

    def open(self, w, h):
        ctx = self.browser.new_context(viewport={"width": w, "height": h})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # externe Logos/Analytics blockieren, Test bleibt offline
        page.route("**/*", lambda r: r.abort() if not r.request.url.startswith(f"http://127.0.0.1:{self.port}") else r.continue_())
        page.goto(f"http://127.0.0.1:{self.port}/altersvorsorgedepot/?intro=0")
        page.evaluate("try{sessionStorage.setItem('introSeen','1')}catch(e){}; var i=document.getElementById('intro'); if(i) i.remove();")
        page.wait_for_function("document.getElementById('av-k6') && document.getElementById('av-k6').textContent.trim() !== '–'")
        return ctx, page, errors

    def test_handy_ohne_seitliches_ueberlaufen_und_tabelle_scrollbar(self):
        ctx, page, errors = self.open(390, 844)
        sw = page.evaluate("document.documentElement.scrollWidth")
        self.assertLessEqual(sw, 391, "Seite darf auf dem Handy nicht seitlich überlaufen")
        sc = page.evaluate("(()=>{var w=document.querySelector('#anbieter-bereich .av-tablewrap');return [w.scrollWidth,w.clientWidth]})()")
        self.assertGreater(sc[0], sc[1], "Tabelle ist innerhalb ihres Rahmens seitlich scrollbar")
        self.assertTrue(page.is_visible(".av-scroll-hint"))
        self.assertEqual(errors, [])
        ctx.close()

    def test_aufbau_kopf_uebersicht_rechner_hinweise(self):
        ctx, page, errors = self.open(390, 844)
        reihenfolge = page.evaluate("""() => ['h1.av-title', 'nav.av-kurz', '#anbieter', '#h-altersvorsorgedepot', '#gut-zu-wissen', '#ratgeber']
            .map(s => { const e = document.querySelector(s); return e ? e.getBoundingClientRect().top + scrollY : -1 })""")
        self.assertNotIn(-1, reihenfolge)
        self.assertEqual(reihenfolge, sorted(reihenfolge), "Kopf, Inhalt, Übersicht, Rechner, Hinweise, Fragen in dieser Reihenfolge")
        self.assertEqual(page.evaluate("document.querySelectorAll('h1').length"), 1)
        # Inhaltsbox verlinkt auf vorhandene Ziele
        for href in page.evaluate("Array.from(document.querySelectorAll('nav.av-kurz a')).map(a => a.getAttribute('href'))"):
            self.assertTrue(page.evaluate(f"!!document.querySelector('{href}')"), href)
        # Übersicht zeigt zuerst 8 Modelle, aufklappbar auf alle
        sichtbar = "Array.from(document.querySelectorAll('#avl tr')).filter(r => r.offsetParent !== null).length"
        total = page.evaluate("document.querySelectorAll('#avl tr').length")
        self.assertEqual(page.evaluate(sichtbar), 8)
        page.click("#av-mehr")
        self.assertEqual(page.evaluate(sichtbar), total)
        self.assertEqual(page.get_attribute("#av-mehr", "aria-expanded"), "true")
        # Hinweise stecken in Akkordeons und sind zu
        self.assertGreaterEqual(page.evaluate("document.querySelectorAll('#gut-zu-wissen details.av-acc').length"), 6)
        self.assertEqual(page.evaluate("document.querySelectorAll('#gut-zu-wissen details[open], #ratgeber details[open]').length"), 0)
        self.assertEqual(errors, [])
        ctx.close()

    def test_chart_zwei_anbieter_als_linien_mit_tooltip(self):
        ctx, page, errors = self.open(390, 844)
        ia, ib = page.evaluate("""() => { const l = JSON.parse(document.getElementById('av-data').textContent);
            return [l.findIndex(p => p.id === 'sc-standard'), l.findIndex(p => p.id === 'ing-relax')]; }""")
        page.select_option("#av-prov", str(ia))
        page.select_option("#av-prov2", str(ib))
        page.evaluate("document.getElementById('av-chart').scrollIntoView()")
        page.wait_for_function("window.Chart && Chart.getChart(document.getElementById('av-chart'))", timeout=8000)
        page.wait_for_timeout(400)
        info = page.evaluate("""() => { const c = Chart.getChart(document.getElementById('av-chart'));
            const lines = c.data.datasets.filter(d => d.type === 'line');
            const f = c.options.plugins.tooltip.callbacks.footer([{ dataIndex: c.data.labels.length - 1 }]);
            const lab = c.options.plugins.tooltip.callbacks.label({ dataset: lines[0], parsed: { y: lines[0].data.at(-1) } });
            return { n: lines.length, names: lines.map(d => d.label), last: lines.slice(0, 2).map(d => d.data.at(-1)), f, lab, cap: document.getElementById('av-chartcap').textContent }; }""")
        self.assertEqual(info["n"], 2, "je Anbieter eine Linie")
        self.assertIn("Scalable", info["names"][0]); self.assertIn("ING", info["names"][1])
        self.assertNotEqual(info["last"][0], info["last"][1], "Linien unterscheiden sich")
        self.assertRegex(" ".join(info["f"]), r"Abstand: .* mehr bei (Scalable|ING)")
        self.assertIn("Eingezahlt plus Zulagen", " ".join(info["f"]))
        self.assertIn("Scalable", info["lab"])
        self.assertIn("Graue Balken", info["cap"])
        bars = page.evaluate("Chart.getChart(document.getElementById('av-chart')).data.datasets.filter(d => d.type === 'bar').map(d => d.label)")
        self.assertEqual(bars, ["Deine Einzahlungen", "Zulagen vom Staat"])
        # Linien liegen über den Balken: Depotwert ist am Ende größer als Einzahlungen plus Zulagen
        top = page.evaluate("(() => { const d = Chart.getChart(document.getElementById('av-chart')).data.datasets; return [d[0].data.at(-1) + d[1].data.at(-1), d[2].data.at(-1)] })()")
        self.assertGreater(top[1], top[0])
        # Anbieterwahl verschiebt die Auswahlfelder nicht
        ya = page.evaluate("document.getElementById('av-prov').getBoundingClientRect().top + scrollY")
        yb = page.evaluate("document.getElementById('av-prov2').getBoundingClientRect().top + scrollY")
        page.select_option("#av-prov", "")
        page.wait_for_timeout(200)
        self.assertAlmostEqual(page.evaluate("document.getElementById('av-prov2').getBoundingClientRect().top + scrollY"), yb, delta=1)
        self.assertAlmostEqual(page.evaluate("document.getElementById('av-prov').getBoundingClientRect().top + scrollY"), ya, delta=1)
        self.assertEqual(errors, [])
        ctx.close()

    def test_anbieterfelder_auf_gleicher_hoehe_desktop(self):
        ctx, page, errors = self.open(1280, 900)
        l = page.evaluate("JSON.parse(document.getElementById('av-data').textContent).map(p => p.id)")
        page.select_option("#av-prov", str(l.index("quirion-standard") if "quirion-standard" in l else 0))
        page.select_option("#av-prov2", str(l.index("oskar-standard") if "oskar-standard" in l else 1))
        page.wait_for_timeout(200)
        ya = page.evaluate("document.getElementById('av-prov').getBoundingClientRect().top + scrollY")
        yb = page.evaluate("document.getElementById('av-prov2').getBoundingClientRect().top + scrollY")
        self.assertAlmostEqual(ya, yb, delta=1)
        ctx.close()

    def test_filter_und_sortierung(self):
        ctx, page, errors = self.open(1280, 900)
        total = page.evaluate("document.querySelectorAll('#avl tr').length")
        page.select_option("#av-f-art", "standard")
        arts = page.evaluate("Array.from(document.querySelectorAll('#avl tr')).filter(r=>!r.hidden).map(r=>r.dataset.art)")
        self.assertTrue(arts and all(a == "standard" for a in arts))
        self.assertIn(f"{len(arts)} von {total}", page.text_content("#av-count"))
        page.check("#av-f-kosten")
        dau = page.evaluate("Array.from(document.querySelectorAll('#avl tr')).filter(r=>!r.hidden).map(r=>r.dataset.dau)")
        self.assertTrue(dau and all(d != "" for d in dau))
        page.uncheck("#av-f-kosten")
        page.select_option("#av-f-art", "")
        page.click("#avt .av-tab[data-s='sta']")
        page.click("#avt .av-tab[data-s='dau']")
        vals = page.evaluate("Array.from(document.querySelectorAll('#avl tr')).map(r=>r.dataset.dau)")
        nums = [float(v) for v in vals if v != ""]
        self.assertEqual(nums, sorted(nums))
        self.assertTrue(all(v == "" for v in vals[len(nums):]), "offene Kosten stehen am Ende")
        self.assertEqual(page.get_attribute("#avt .av-tab[data-s='dau']", "aria-pressed"), "true")
        self.assertEqual(errors, [])
        ctx.close()

    def test_rechner_mit_anbieter_und_eroeffnungsmonat(self):
        ctx, page, errors = self.open(1280, 900)
        idx = page.evaluate("JSON.parse(document.getElementById('av-data').textContent).findIndex(p=>p.id==='n26-standard')")
        page.select_option("#av-prov", str(idx))
        page.wait_for_timeout(300)
        n_jan = page.text_content("#av-k6")
        self.assertIn("N26", page.text_content("#av-basis"))
        page.fill("#av-open", "2027-07")
        page.dispatch_event("#av-open", "change")
        page.wait_for_timeout(300)
        n_jul = page.text_content("#av-k6")
        self.assertNotEqual(n_jan, n_jul, "Eröffnung ab Juli 2027 ändert die N26-Kosten")
        self.assertIn("noch offen", page.text_content("#av-rank"))
        # Angebot mit offenen Kosten: Kennzahlen mit eigener Annahme, deutlich gekennzeichnet
        sb = page.evaluate("JSON.parse(document.getElementById('av-data').textContent).findIndex(p=>p.id==='sb-standard')")
        page.select_option("#av-prov", str(sb))
        page.wait_for_timeout(300)
        self.assertIn("Annahme", page.text_content("#av-err"))
        self.assertIn("deiner Annahme", page.text_content("#av-basis"))
        self.assertEqual(errors, [])
        ctx.close()


if __name__ == "__main__":
    unittest.main()
