/* Aktienkuerzel mit aktuellem Kurs: <span data-kurs="CVX">$CVX</span>. Kurs ueber den Zwischenserver (dort 15 Minuten gemerkt), im Browser ebenfalls 15 Minuten. */
(function () {
  var P = "https://fmp-proxy.dividenden-rechner.workers.dev/quote?symbol=", TTL = 15 * 60 * 1000;
  var CUR = { "": "USD", L: "p", DE: "€", F: "€", PA: "€", AS: "€", MI: "€", MC: "€", BR: "€", HE: "€", VI: "€", LS: "€", IR: "€", SW: "CHF", ST: "SEK", OL: "NOK", CO: "DKK", T: "¥", HK: "HKD", KS: "₩", TO: "CAD", AX: "AUD", SI: "SGD", BK: "THB", KL: "MYR", JK: "IDR", TW: "TWD" };
  function cur(sym) { var m = /\.([A-Z]+)$/.exec(sym); return CUR[m ? m[1] : ""] || ""; }
  function num(v, d) { return v.toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function get(sym) {
    try { var c = JSON.parse(localStorage.getItem("kurs_" + sym) || "null"); if (c && Date.now() - c.t < TTL) return Promise.resolve(c); } catch (e) { }
    return fetch(P + encodeURIComponent(sym)).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      var q = Array.isArray(j) ? j[0] : null; if (!q || typeof q.price !== "number") return null;
      var o = { t: Date.now(), p: q.price, c: q.changePercentage != null ? q.changePercentage : q.changesPercentage };
      try { localStorage.setItem("kurs_" + sym, JSON.stringify(o)); } catch (e) { } return o;
    }).catch(function () { return null; });
  }
  function show(el, o) {
    var sym = el.getAttribute("data-kurs"), c = cur(sym), pence = c === "p";
    var price = pence ? num(o.p, 2) + " p" : num(o.p, 2) + (c ? " " + c : "");
    var ch = typeof o.c === "number" ? o.c : null, cls = ch == null ? "" : ch > 0 ? "up" : ch < 0 ? "down" : "";
    var s = document.createElement("span"); s.className = "kchip-kurs";
    s.innerHTML = price + (ch == null ? "" : ' <span class="' + cls + '">' + (ch > 0 ? "+" : ch < 0 ? "−" : "") + num(Math.abs(ch), 2) + " %</span>");
    el.appendChild(s); el.title = "Kurs zeitverzögert, ohne Gewähr (Quelle: FMP). Keine Anlageberatung.";
  }
  function run() { Array.prototype.forEach.call(document.querySelectorAll("[data-kurs]"), function (el) { get(el.getAttribute("data-kurs")).then(function (o) { if (o) show(el, o); }); }); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
})();
