/* Rechner für dividenden-rechner / Aktien-Hub. Reines JavaScript, keine Datenabfragen, keine Cookies. */
(function (root) {
  "use strict";

  /** Dividendenrendite: Dividende / Kurs. Gibt Brutto-/Netto-Werte zurück. */
  function yieldCalc(o) {
    var d = o.dividende, k = o.kurs, n = o.anzahl || 0, t = (o.steuer || 0) / 100;
    if (!(d >= 0) || !(k > 0)) return null;
    var rendite = d / k * 100;
    var brutto = d * n;
    var steuer = brutto * t;
    return {
      rendite: rendite,
      renditeNetto: rendite * (1 - t),
      brutto: brutto,
      steuer: steuer,
      netto: brutto - steuer,
      invest: k * n
    };
  }

  /**
   * Dividenden-Zinseszins: jährliche Betrachtung.
   * Kapital/Sparrate werden zum Jahresanfang zum aktuellen Kurs investiert,
   * die Netto-Dividende wird zum Jahresende-Kurs wieder angelegt.
   */
  function compoundCalc(o) {
    var years = Math.round(o.jahre);
    if (!(years >= 1 && years <= 60)) return null;
    var P = 1, D = o.rendite / 100 * P; // Startkurs normiert auf 1
    var gp = o.kurswachstum / 100, gd = o.divwachstum / 100, t = o.steuer / 100;
    var shares = o.start / P, paidIn = o.start, cumDiv = 0, lastDiv = 0, rows = [];
    for (var y = 0; y < years; y++) {
      var price = P * Math.pow(1 + gp, y);
      var dps = D * Math.pow(1 + gd, y);
      shares += (o.sparrate * 12) / price;
      paidIn += o.sparrate * 12;
      var divNet = shares * dps * (1 - t);
      cumDiv += divNet;
      lastDiv = divNet;
      var endPrice = price * (1 + gp);
      if (o.reinvest) shares += divNet / endPrice;
      rows.push({ jahr: y + 1, wert: shares * endPrice, div: divNet, eingezahlt: paidIn });
    }
    var endPriceFinal = P * Math.pow(1 + gp, years);
    return {
      endwert: shares * endPriceFinal,
      eingezahlt: paidIn,
      kumDividende: cumDiv,
      letzteDividende: lastDiv,
      letzteDividendeMonat: lastDiv / 12,
      rows: rows
    };
  }

  var api = { yieldCalc: yieldCalc, compoundCalc: compoundCalc };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; }
  root.DivCalc = api;

  /* ---------- DOM ---------- */
  if (typeof document === "undefined") return;
  var fmtEUR = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });
  var fmtPct = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  var num = function (id) {
    var el = document.getElementById(id);
    if (!el) return NaN;
    var v = el.value.trim();
    if (v.indexOf(",") > -1) v = v.replace(/\./g, "").replace(",", "."); // 1.234,5 -> 1234.5
    else if (/^\d{1,3}(\.\d{3})+$/.test(v)) v = v.replace(/\./g, ""); // 10.000 -> 10000
    return v === "" ? NaN : Number(v);
  };
  var set = function (id, txt) { var el = document.getElementById(id); if (el) el.textContent = txt; };

  function initYield() {
    var form = document.getElementById("calc-yield");
    if (!form) return;
    function run() {
      var r = yieldCalc({ dividende: num("y-div"), kurs: num("y-kurs"), anzahl: isNaN(num("y-anz")) ? 0 : num("y-anz"), steuer: isNaN(num("y-tax")) ? 0 : num("y-tax") });
      if (!r) { set("y-err", "Bitte Dividende (≥ 0) und Aktienkurs (> 0) eingeben."); return; }
      set("y-err", "");
      set("o-rendite", fmtPct.format(r.rendite) + " %");
      set("o-rendite-netto", fmtPct.format(r.renditeNetto) + " %");
      set("o-brutto", fmtEUR.format(r.brutto));
      set("o-netto", fmtEUR.format(r.netto));
      set("o-invest", fmtEUR.format(r.invest));
    }
    form.addEventListener("input", run);
    form.addEventListener("submit", function (e) { e.preventDefault(); run(); });
    run();
  }

  function initCompound() {
    var form = document.getElementById("calc-compound");
    if (!form) return;
    function run() {
      var o = {
        start: num("c-start"), sparrate: num("c-rate"), rendite: num("c-yield"),
        divwachstum: num("c-dg"), kurswachstum: num("c-pg"), jahre: num("c-years"),
        steuer: num("c-tax"), reinvest: document.getElementById("c-re").checked
      };
      for (var k in o) { if (k !== "reinvest" && isNaN(o[k])) { set("c-err", "Bitte alle Felder mit Zahlen füllen."); return; } }
      if (o.start < 0 || o.sparrate < 0 || o.rendite < 0 || o.steuer < 0 || o.steuer > 100) { set("c-err", "Bitte nur sinnvolle, nicht negative Werte eingeben (Steuer 0–100 %)."); return; }
      var r = compoundCalc(o);
      if (!r) { set("c-err", "Anlagedauer: 1 bis 60 Jahre."); return; }
      set("c-err", "");
      set("o-end", fmtEUR.format(r.endwert));
      set("o-paid", fmtEUR.format(r.eingezahlt));
      set("o-cum", fmtEUR.format(r.kumDividende));
      set("o-last", fmtEUR.format(r.letzteDividende));
      set("o-lastm", fmtEUR.format(r.letzteDividendeMonat));
      var tb = document.getElementById("c-rows");
      if (tb) {
        tb.innerHTML = "";
        r.rows.forEach(function (row) {
          var tr = document.createElement("tr");
          [row.jahr, fmtEUR.format(row.eingezahlt), fmtEUR.format(row.div), fmtEUR.format(row.wert)].forEach(function (v, i) {
            var td = document.createElement("td"); if (i) td.className = "n"; td.textContent = v; tr.appendChild(td);
          });
          tb.appendChild(tr);
        });
      }
    }
    form.addEventListener("input", run);
    form.addEventListener("change", run);
    form.addEventListener("submit", function (e) { e.preventDefault(); run(); });
    run();
  }

  function init() { initYield(); initCompound(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})(typeof window !== "undefined" ? window : globalThis);
