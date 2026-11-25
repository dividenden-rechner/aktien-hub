/* Finanz-Diagramme der Firmenseiten: liest die Jahreswerte aus <script id="fin-daten"> und zeichnet sie mit Chart.js.
   Kein Netzwerkzugriff; fehlt Chart.js, bleibt die Tabelle leer, die Seite funktioniert trotzdem. */
(function () {
  function init() {
    var el = document.getElementById("fin-daten");
    if (!el || typeof Chart === "undefined") return;
    var daten;
    try { daten = JSON.parse(el.textContent); } catch (e) { return; }
    var textFarbe = getComputedStyle(document.documentElement).getPropertyValue("--mut") || "#5d6b78";
    daten.forEach(function (c, i) {
      var cv = document.getElementById("fc" + i);
      if (!cv) return;
      var typ = c.typ === "line" ? "line" : "bar";
      var letzt = c.jahre.length - 1;
      var GRAU = "#c3c9d0";
      var sets = c.reihen.map(function (r) {
        var prog = !!c.prognose && r.werte[letzt] !== null && r.werte[letzt] !== undefined;
        var ds = {
          label: r.name,
          data: r.werte,
          backgroundColor: r.farbe,
          borderColor: r.farbe,
          borderWidth: typ === "line" ? 2 : 0,
          pointRadius: typ === "line" ? 3 : 0,
          fill: false,
          spanGaps: true
        };
        if (prog && typ === "bar") {
          ds.backgroundColor = r.werte.map(function (x, i) { return i === letzt ? GRAU : r.farbe; });
        }
        if (prog && typ === "line") {
          ds.pointBackgroundColor = r.werte.map(function (x, i) { return i === letzt ? GRAU : r.farbe; });
          ds.segment = {
            borderDash: function (ctx) { return ctx.p1DataIndex === letzt - 1 ? [5, 4] : undefined; },
            borderColor: function (ctx) { return ctx.p1DataIndex === letzt - 1 ? GRAU : undefined; }
          };
        }
        ds.progRe = prog;
        return ds;
      });
      new Chart(cv, {
        type: typ,
        data: { labels: c.jahre.map(function (j, i) { return "’" + String(j).slice(2) + (c.prognose && i === letzt ? "e" : ""); }), datasets: sets },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: { display: sets.length > 1, position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
            tooltip: { callbacks: { label: function (ctx) {
              var v = ctx.parsed.y;
              if (v === null || v === undefined) return ctx.dataset.label + ": –";
              var zusatz = ctx.dataset.progRe && ctx.dataIndex === letzt ? " (Prognose)" : "";
              return ctx.dataset.label + ": " + v.toLocaleString("de-DE", { maximumFractionDigits: 2 }) + (c.einheit ? " " + c.einheit : "") + zusatz;
            } } }
          },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 11 } } },
            y: { beginAtZero: typ === "bar", ticks: { font: { size: 11 }, callback: function (v) { return v.toLocaleString("de-DE"); } } }
          }
        }
      });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
