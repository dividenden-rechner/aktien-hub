"""Startanimation (assets/navigation.js): Logo zieht in einer Bewegung nach links, der Schriftzug gleichzeitig nach rechts heraus.

Aufruf: python3 -m unittest tests/test_intro.py
"""
import functools, http.server, os, shutil, socketserver, threading, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _chrome():
    try:
        import playwright  # noqa: F401
    except ImportError:
        return None
    for c in ("/usr/bin/google-chrome", shutil.which("google-chrome") or "", shutil.which("chromium") or ""):
        if c and os.path.exists(c):
            return c
    return None


MESSUNG = """() => new Promise(res => {
    const img = document.querySelector('#intro img'), b = document.querySelector('#intro .nm b'), nm = document.querySelector('#intro .nm');
    const out = []; const t0 = performance.now();
    (function tick() {
        const t = performance.now() - t0;
        out.push([t, img.getBoundingClientRect().left, b.getBoundingClientRect().right, nm.getBoundingClientRect().width]);
        if (t < 1700) requestAnimationFrame(tick);
        else res({out, w: b.offsetWidth, nmw: nm.getBoundingClientRect().width, aus: getComputedStyle(document.getElementById('intro')).animationDelay});
    })();
})"""


@unittest.skipUnless(_chrome(), "Playwright/Chrome nicht verfügbar")
class Startanimation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Leise(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Leise, directory=ROOT))
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
        cls.httpd.server_close()

    def test_fliessend_und_kuerzer(self):
        for w, h in [(1280, 900), (390, 844)]:
            with self.subTest(breite=w):
                ctx = self.browser.new_context(viewport={"width": w, "height": h})
                page = ctx.new_page()
                page.route("**/*", lambda r: r.abort() if not r.request.url.startswith(f"http://127.0.0.1:{self.port}") else r.continue_())
                page.goto(f"http://127.0.0.1:{self.port}/?intro=1")
                page.wait_for_selector("#intro .nm b")
                werte = page.evaluate(MESSUNG)
                pts = werte["out"]
                logo = [p[1] for p in pts]
                schrift = [p[2] for p in pts]
                # Logo bewegt sich nur nach links, die Schrift nur nach rechts (kleine Rundungstoleranz)
                self.assertTrue(all(b <= a + 0.6 for a, b in zip(logo, logo[1:])), "Logo springt zurück nach rechts")
                self.assertTrue(all(b >= a - 0.6 for a, b in zip(schrift, schrift[1:])), "Schriftzug fährt zwischendurch nach links")
                self.assertLess(logo[-1], logo[0] - 20, "Logo zieht nach links")
                # am Ende ist der Schriftzug ganz sichtbar
                self.assertGreaterEqual(pts[-1][3] + 1, werte["w"])
                self.assertEqual(werte["aus"], "2s", "Ausblenden nach 2 s")
                ctx.close()

    def test_nur_auf_der_startseite(self):
        ctx = self.browser.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{self.port}/altersvorsorgedepot/")
        page.wait_for_timeout(300)
        self.assertEqual(page.evaluate("!!document.getElementById('intro') || !!document.getElementById('intro-pre')"), False, "keine Animation auf Unterseiten")
        page.goto(f"http://127.0.0.1:{self.port}/")
        page.wait_for_timeout(300)
        self.assertTrue(page.evaluate("!!document.getElementById('intro')"), "Animation auf der Startseite")
        ctx.close()

    def test_animation_ohne_layout_animation(self):
        js = open(os.path.join(ROOT, "assets", "navigation.js"), encoding="utf-8").read()
        self.assertNotIn("intro-grow", js, "keine Breiten-Animation (Layout je Frame)")
        self.assertIn("intro-move", js)


if __name__ == "__main__":
    unittest.main()
