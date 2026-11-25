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
      var sets = c.reihen.map(function (r) {
        return {
          label: r.name,
          data: r.werte,
          backgroundColor: r.farbe,
          borderColor: r.farbe,
          borderWidth: typ === "line" ? 2 : 0,
          pointRadius: typ === "line" ? 3 : 0,
          fill: false,
          spanGaps: true
        };
      });
      new Chart(cv, {
        type: typ,
        data: { labels: c.jahre.map(function (j) { return "’" + String(j).slice(2); }), datasets: sets },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: { display: sets.length > 1, position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
            tooltip: { callbacks: { label: function (ctx) {
              var v = ctx.parsed.y;
              if (v === null || v === undefined) return ctx.dataset.label + ": –";
              return ctx.dataset.label + ": " + v.toLocaleString("de-DE", { maximumFractionDigits: 2 }) + (c.einheit ? " " + c.einheit : "");
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
