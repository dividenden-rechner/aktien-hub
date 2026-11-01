/* Earnings-Ergebnis in der Firmenkarte der Artikel: <span class="fk-e" data-earn="INTC"></span>.
   Quelle wie auf der Earnings-Seite: letzter berichteter Termin (Zwischenserver), bei Lücken data/ist-zahlen.json. */
(function () {
  var P = "https://fmp-proxy.dividenden-rechner.workers.dev/earnings?limit=4&symbol=", TTL = 12 * 3600 * 1000;
  var me = document.querySelector('script[src*="assets/fkearn.js"]');
  var ROOT = me ? new URL(me.getAttribute("src").split("assets/fkearn.js")[0] || "./", location.href).href : "./";
  function num(v, d) { return v == null || isNaN(v) ? "–" : Number(v).toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function big(v, cur) { if (v == null || isNaN(v)) return "–"; var a = Math.abs(v), u = a >= 1e9 ? [v / 1e9, " Mrd."] : [v / 1e6, " Mio."]; return num(u[0], a >= 1e9 ? 1 : 0) + u[1] + (cur ? " " + cur : ""); }
  function gr(c, p) { return c == null || p == null || p === 0 || isNaN(c) || isNaN(p) ? null : (c - p) / Math.abs(p); }
  function tone(g) { return g == null || !isFinite(g) ? "eq" : g >= 0.01 ? "up" : g <= -0.01 ? "dn" : "eq"; }
  function gp(g) { return g == null ? "" : '<em class="' + tone(g) + '">' + (g > 0 ? "+" : g < 0 ? "−" : "") + num(Math.abs(g) * 100, 1) + " %</em>"; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function load(sym) {
    var ck = "fkearn_" + sym;
    try { var c = JSON.parse(localStorage.getItem(ck) || "null"); if (c && Date.now() - c.t < TTL) return Promise.resolve(c.j); } catch (e) { }
    return fetch(P + encodeURIComponent(sym)).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (!Array.isArray(j)) return null;
      try { localStorage.setItem(ck, JSON.stringify({ t: Date.now(), j: j })); } catch (e) { }
      return j;
    }).catch(function () { return null; });
  }
  var IST = null;
  function ist() {
    if (IST) return IST;
    return IST = fetch(ROOT + "data/ist-zahlen.json").then(function (r) { return r.ok ? r.json() : { items: [] }; }).then(function (j) { return j.items || []; }).catch(function () { return []; });
  }
  function pick(list) {
    var d = (list || []).filter(function (x) { return x && (x.epsActual != null || x.revenueActual != null); });
    d.sort(function (a, b) { return a.date < b.date ? 1 : -1; });
    return d[0] || null;
  }
  function show(el, r, own) {
    var ge = gr(r.epsActual, r.epsEstimated), gv = gr(r.revenueActual, r.revenueEstimated);
    var a = [ge, gv].filter(function (x) { return x != null && isFinite(x); });
    var up = a.some(function (x) { return x >= 0.01; }), dn = a.some(function (x) { return x <= -0.01; });
    var v = !a.length ? null : up && dn ? ["gemischt", "mix"] : up ? ["übertroffen", "up"] : dn ? ["verfehlt", "dn"] : ["erfüllt", "eq"];
    var d = String(r.date || "").slice(0, 10), dd = d ? d.slice(8) + "." + d.slice(5, 7) + "." : "";
    function cell(title, val, est, g) {
      return '<span class="fk-ec"><small>' + title + "</small><b>" + val + "</b>" + (est ? '<span class="fk-es">Erw. ' + est + " " + gp(g) + "</span>" : "") + "</span>";
    }
    var cur = r.currency || "$";
    el.innerHTML = '<span class="fk-eh"><span class="fk-eb">berichtet' + (dd ? " am " + dd : "") + "</span>" + (v ? '<span class="fk-eb ' + v[1] + '">' + v[0] + "</span>" : "") + "</span>" +
      '<span class="fk-eg">' +
      (r.epsActual != null ? cell("Gewinn je Aktie", num(r.epsActual, 2) + (own ? "" : ""), r.epsEstimated != null ? num(r.epsEstimated, 2) : "", ge) : "") +
      (r.revenueActual != null ? cell("Umsatz", big(r.revenueActual, ""), r.revenueEstimated != null ? big(r.revenueEstimated, "") : "", gv) : "") +
      "</span>";
    el.hidden = false;
  }
  function run() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-earn]"), function (el) {
      var sym = el.getAttribute("data-earn");
      load(sym).then(function (list) {
        var r = pick(list);
        return ist().then(function (items) {
          var base = String(sym).split(".")[0];
          var it = items.filter(function (x) { return x.sym === sym || String(x.sym).split(".")[0] === base; }).sort(function (a, b) { return a.datum < b.datum ? 1 : -1; })[0];
          if (it && (!r || (Date.parse(it.datum) - Date.parse(r.date)) > 4 * 864e5)) r = { date: it.datum, epsActual: it.eps, revenueActual: it.revenue, epsEstimated: null, revenueEstimated: null }, el.setAttribute("data-own", "1");
          else if (it && r && r.epsActual == null && it.eps != null && Math.abs(Date.parse(it.datum) - Date.parse(r.date)) <= 4 * 864e5) { r.epsActual = it.eps; if (r.revenueActual == null) r.revenueActual = it.revenue; }
          if (r) show(el, r, el.getAttribute("data-own"));
        });
      });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
})();
