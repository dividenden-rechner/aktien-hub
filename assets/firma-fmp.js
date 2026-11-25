/* Nur Testseite: Live-Kurs, Kursziel-Konsens, Analysten und DCF aus FMP (ueber den Zwischenserver) auf Firmenseiten.
   Die oeffentliche Seite bekommt diese Datei nicht (tools/live_filter.py entfernt Skript und Block). */
(function () {
  var box = document.getElementById("fmp-box"); if (!box) return;
  var sym = box.getAttribute("data-sym"), P = "https://fmp-proxy.dividenden-rechner.workers.dev/";
  function num(v, d) { return typeof v === "number" ? v.toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d }) : "–"; }
  function get(path) {
    var ck = "fmpf:" + path + sym;
    try { var c = JSON.parse(localStorage.getItem(ck) || "null"); if (c && Date.now() - c.t < 9e5) return Promise.resolve(c.j); } catch (e) { }
    return fetch(P + path + "?symbol=" + encodeURIComponent(sym)).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      var o = Array.isArray(j) ? j[0] : j; try { localStorage.setItem(ck, JSON.stringify({ t: Date.now(), j: o })); } catch (e) { } return o;
    }).catch(function () { return null; });
  }
  Promise.all([get("quote"), get("price-target-consensus"), get("grades-consensus"), get("discounted-cash-flow")]).then(function (a) {
    var q = a[0], t = a[1], g = a[2], d = a[3], rows = [];
    if (q && typeof q.price === "number") rows.push(["Live-Kurs (zeitverzögert)", num(q.price, 2) + (typeof q.changePercentage === "number" ? " (" + (q.changePercentage > 0 ? "+" : "") + num(q.changePercentage, 2) + " %)" : "")]);
    if (t && t.targetConsensus) rows.push(["Kursziel-Konsens der Analysten", num(t.targetConsensus, 2) + " (Spanne " + num(t.targetLow, 2) + " bis " + num(t.targetHigh, 2) + ")"]);
    if (g && g.consensus) rows.push(["Analystenurteil", g.consensus + " (" + (g.strongBuy + g.buy) + " Kaufen, " + g.hold + " Halten, " + (g.sell + g.strongSell) + " Verkaufen)"]);
    if (d && typeof d.dcf === "number") rows.push(["DCF-Modellwert (FMP)", num(d.dcf, 2)]);
    if (!rows.length) return;
    box.innerHTML = '<h2>Analysten und Bewertung (nur Testseite)</h2><div class="tablewrap"><table><tbody>' +
      rows.map(function (r) { return "<tr><th scope='row'>" + r[0] + "</th><td>" + r[1] + "</td></tr>"; }).join("") +
      '</tbody></table></div><p class="meta">Quelle: Financial Modeling Prep, Kurs zeitverzögert, ohne Gewähr. Keine Anlageberatung.</p>';
  });
})();
