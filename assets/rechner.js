/* Rechner für dividenden-rechner / Aktien-Hub. Reines JavaScript, keine Datenabfragen, keine Cookies.
   Diagramme: Chart.js (lokal eingebunden, kein Aufruf an Drittserver). */
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

  /**
   * Dividenden-Wachstums-Rechner (Modell des bisherigen Dividenden-Rechners):
   * Jedes Jahr: Sparrate dazu, Kursplus aufs Kapital, Dividende = Kapital x aktuelle Rendite,
   * Rendite wächst mit dem Dividendenwachstum. Die Netto-Dividende wird optional reinvestiert.
   */
  function growthCalc(o) {
    var years = Math.max(1, Math.round(Math.abs(o.jahre) || 0));
    var cap = Math.abs(o.start) || 0, annual = (Math.abs(o.monat) || 0) * 12;
    var y = (Math.abs(o.rendite) || 0) / 100, gd = (Math.abs(o.divwachstum) || 0) / 100, gp = (Math.abs(o.kurswachstum) || 0) / 100;
    var t = o.steuer || 0, total = 0, rows = [], paid = cap;
    for (var i = 1; i <= years; i++) {
      cap += annual; paid += annual;
      cap *= (1 + gp);
      var gross = cap * y, tax = gross * t, net = gross - tax;
      total += net;
      var re = 0;
      if (o.reinvest) { cap += net; re = net; }
      y *= (1 + gd);
      rows.push({ jahr: i, kapital: cap, netto: net, steuer: tax, reinvest: re, eingezahlt: paid });
    }
    return { endkapital: cap, summeNetto: total, eingezahlt: paid, rows: rows, jahre: years };
  }

  /** Szenarien: Dividendenwachstum -2 / 0 / +2 Prozentpunkte, Netto-Dividende je Jahr. */
  function scenarios(o) {
    return [-0.02, 0, 0.02].map(function (mod) {
      var r = growthCalc({ start: o.start, monat: o.monat, rendite: o.rendite, divwachstum: Math.max(0, (o.divwachstum / 100 + mod)) * 100, kurswachstum: o.kurswachstum, jahre: o.jahre, steuer: o.steuer, reinvest: o.reinvest });
      return r.rows.map(function (x) { return x.netto; });
    });
  }

  var api = { yieldCalc: yieldCalc, compoundCalc: compoundCalc, growthCalc: growthCalc, scenarios: scenarios };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; }
  root.DivCalc = api;

  /* ---------- DOM ---------- */
  if (typeof document === "undefined") return;
  var $ = function (id) { return document.getElementById(id); };
  var fmtPct = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  var cur = { code: "EUR", sym: "€" };
  var money = function (v, d) { return new Intl.NumberFormat("de-DE", { style: "currency", currency: cur.code, maximumFractionDigits: d == null ? 0 : d, minimumFractionDigits: d == null ? 0 : d }).format(v); };
  var dec2 = function (v) { return Number(v).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
  // Zahl aus Eingabefeld: "1.234,5" -> 1234.5, "10.000" -> 10000, "2.5" -> 2.5
  var num = function (id) {
    var el = $(id);
    if (!el) return NaN;
    var v = String(el.value).trim().replace(/\s/g, "");
    if (v.indexOf(",") > -1) v = v.replace(/\./g, "").replace(",", ".");
    else if (/^\d{1,3}(\.\d{3})+$/.test(v)) v = v.replace(/\./g, "");
    return v === "" ? NaN : Number(v);
  };
  var set = function (id, txt) { var el = $(id); if (el) el.textContent = txt; };
  var charts = {};
  var GREEN = "#10b981", BLUE = "#2563eb", RED = "#ef4444", GREY = "#6b7280";

  function draw(id, cfg) {
    var el = $(id);
    if (!el || typeof Chart === "undefined") return;
    if (charts[id]) charts[id].destroy();
    cfg.options = cfg.options || {};
    cfg.options.responsive = true;
    cfg.options.maintainAspectRatio = false;
    charts[id] = new Chart(el.getContext("2d"), cfg);
  }
  var axisMoney = function (v) { return Number(v).toLocaleString("de-DE", { maximumFractionDigits: 0 }); };
  var tipMoney = function (c) { return " " + c.dataset.label + ": " + money(c.parsed.y, 2); };

  function toggle(btnId, boxId, display) {
    var b = $(btnId), box = $(boxId);
    if (!b || !box) return;
    b.addEventListener("click", function () {
      var open = box.style.display === display;
      box.style.display = open ? "none" : display;
      b.setAttribute("aria-expanded", String(!open));
    });
  }

  /* ----- 1) Dividenden-Rechner (Wachstum) ----- */
  var TAX_HINTS = {
    "0.26375": "Standard-Kapitalertragsteuer in Deutschland (26,375 % inkl. Soli, ohne Kirchensteuer).",
    "0.275": "Standard-KESt in Österreich (27,5 %).",
    "0.35": "Schweiz: 35 % Verrechnungssteuer werden direkt abgezogen. Währung auf CHF umgestellt."
  };
  function updateTax() {
    var sel = $("g-tax"); if (!sel) return;
    var v = sel.value, hint = $("g-taxhint");
    cur = v === "0.35" ? { code: "CHF", sym: "CHF" } : { code: "EUR", sym: "€" };
    if (hint) { hint.style.display = TAX_HINTS[v] ? "block" : "none"; hint.textContent = TAX_HINTS[v] || ""; }
    document.querySelectorAll(".currency-symbol").forEach(function (el) { el.textContent = cur.sym; });
  }
  var PRESETS = { defensiv: { y: 3, g: 3, p: 4 }, growth: { y: 1, g: 7, p: 8 }, highyield: { y: 5, g: 1, p: 3 } };

  function initGrowth() {
    var form = $("calc-growth");
    if (!form) return;
    function run() {
      updateTax();
      var o = {
        start: num("g-start"), monat: num("g-rate"), rendite: num("g-yield"), divwachstum: num("g-dg"),
        kurswachstum: num("g-pg"), jahre: num("g-years"), steuer: Number($("g-tax").value), reinvest: $("g-re").value === "1"
      };
      for (var k in o) { if (k !== "reinvest" && isNaN(o[k])) { set("g-err", "Bitte alle Felder mit Zahlen füllen."); return; } }
      if (o.start < 0 || o.monat < 0 || o.rendite < 0 || o.divwachstum < 0 || o.kurswachstum < 0) { set("g-err", "Bitte nur nicht negative Werte eingeben."); return; }
      if (!(o.jahre >= 1 && o.jahre <= 60)) { set("g-err", "Anlagedauer: 1 bis 60 Jahre."); return; }
      set("g-err", "");
      var r = growthCalc(o);
      $("g-out").innerHTML = '<div>Endkapital: <strong>' + money(r.endkapital) + '</strong></div><div class="sub">Summe Netto-Dividenden: ' + money(r.summeNetto) + ' · Eingezahlt: ' + money(r.eingezahlt) + '</div>';
      var labels = r.rows.map(function (x) { return "Jahr " + x.jahr; });
      draw("g-chart", {
        type: "bar",
        data: {
          labels: labels, datasets: [
            { label: "Netto-Dividende / Jahr", data: r.rows.map(function (x) { return x.netto; }), backgroundColor: GREEN, yAxisID: "y1", order: 2 },
            { label: "Gesamtkapital", type: "line", data: r.rows.map(function (x) { return x.kapital; }), borderColor: BLUE, backgroundColor: "rgba(37,99,235,.1)", fill: true, tension: .3, yAxisID: "y", order: 1 }
          ]
        },
        options: {
          interaction: { mode: "index", intersect: false },
          scales: {
            y: { position: "left", title: { display: true, text: "Kapital (" + cur.sym + ")" }, ticks: { callback: axisMoney } },
            y1: { position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "Dividende (" + cur.sym + ")" }, ticks: { callback: axisMoney } }
          },
          plugins: { title: { display: true, text: "Kapitalentwicklung und jährliche Dividenden" }, tooltip: { callbacks: { label: tipMoney } } }
        }
      });
      var sc = scenarios(o), names = ["Pessimistisch (−2 %)", "Neutral", "Optimistisch (+2 %)"], cols = [RED, GREY, GREEN];
      draw("g-scen", {
        type: "line",
        data: { labels: r.rows.map(function (x) { return x.jahr; }), datasets: sc.map(function (d, i) { return { label: names[i], data: d, borderColor: cols[i], tension: .2, fill: false }; }) },
        options: {
          interaction: { mode: "index", intersect: false },
          scales: { y: { title: { display: true, text: "Dividende (" + cur.sym + ")" }, ticks: { callback: axisMoney } }, x: { title: { display: true, text: "Jahr" } } },
          plugins: { title: { display: true, text: "Szenarien: jährliche Netto-Dividende bei ±2 Prozentpunkten Dividendenwachstum" }, tooltip: { callbacks: { label: tipMoney } } }
        }
      });
      var tb = $("g-rows"); tb.innerHTML = "";
      r.rows.forEach(function (x) {
        var tr = document.createElement("tr");
        [[x.jahr, ""], [dec2(x.kapital), ""], [dec2(x.netto), "pos"], [dec2(x.steuer), "neg"], [o.reinvest ? dec2(x.reinvest) : "–", ""]].forEach(function (c) {
          var td = document.createElement("td"); td.textContent = c[0]; if (c[1]) td.className = c[1]; tr.appendChild(td);
        });
        tb.appendChild(tr);
      });
    }
    form.addEventListener("input", run);
    form.addEventListener("change", run);
    form.addEventListener("submit", function (e) { e.preventDefault(); run(); });
    $("g-go").addEventListener("click", run);
    document.querySelectorAll("#g-presets input").forEach(function (r) {
      r.addEventListener("click", function () {
        var p = PRESETS[r.value]; if (!p) return;
        $("g-yield").value = String(p.y).replace(".", ","); $("g-dg").value = String(p.g).replace(".", ","); $("g-pg").value = String(p.p).replace(".", ",");
        run();
      });
    });
    toggle("g-presetbtn", "g-presets", "grid");
    toggle("g-tablebtn", "g-tablewrap", "block");
    run();
  }

  /* ----- 2) Dividendenrendite-Rechner ----- */
  function initYield() {
    var form = $("calc-yield");
    if (!form) return;
    function run() {
      var r = yieldCalc({ dividende: num("y-div"), kurs: num("y-kurs"), anzahl: isNaN(num("y-anz")) ? 0 : num("y-anz"), steuer: isNaN(num("y-tax")) ? 0 : num("y-tax") });
      if (!r) { set("y-err", "Bitte Dividende (≥ 0) und Aktienkurs (> 0) eingeben."); return; }
      set("y-err", "");
      set("o-rendite", fmtPct.format(r.rendite) + " %");
      set("o-rendite-netto", fmtPct.format(r.renditeNetto) + " %");
      set("o-brutto", money(r.brutto, 2));
      set("o-netto", money(r.netto, 2));
      set("o-invest", money(r.invest, 2));
      draw("y-chart", {
        type: "bar",
        data: { labels: ["Brutto-Dividende", "Steuer", "Netto-Dividende"], datasets: [{ label: "Jahresdividende", data: [r.brutto, r.steuer, r.netto], backgroundColor: [BLUE, RED, GREEN] }] },
        options: { plugins: { legend: { display: false }, title: { display: true, text: "Jahresdividende: brutto, Steuer, netto" }, tooltip: { callbacks: { label: function (c) { return " " + money(c.parsed.y, 2); } } } }, scales: { y: { beginAtZero: true, title: { display: true, text: "Euro" }, ticks: { callback: axisMoney } } } }
      });
    }
    form.addEventListener("input", run);
    form.addEventListener("submit", function (e) { e.preventDefault(); run(); });
    run();
  }

  /* ----- 3) Dividenden-Zinseszins-Rechner ----- */
  function initCompound() {
    var form = $("calc-compound");
    if (!form) return;
    function run() {
      var o = {
        start: num("c-start"), sparrate: num("c-rate"), rendite: num("c-yield"),
        divwachstum: num("c-dg"), kurswachstum: num("c-pg"), jahre: num("c-years"),
        steuer: num("c-tax"), reinvest: $("c-re").checked
      };
      for (var k in o) { if (k !== "reinvest" && isNaN(o[k])) { set("c-err", "Bitte alle Felder mit Zahlen füllen."); return; } }
      if (o.start < 0 || o.sparrate < 0 || o.rendite < 0 || o.steuer < 0 || o.steuer > 100) { set("c-err", "Bitte nur sinnvolle, nicht negative Werte eingeben (Steuer 0–100 %)."); return; }
      var r = compoundCalc(o);
      if (!r) { set("c-err", "Anlagedauer: 1 bis 60 Jahre."); return; }
      set("c-err", "");
      set("o-end", money(r.endwert));
      set("o-paid", money(r.eingezahlt));
      set("o-cum", money(r.kumDividende));
      set("o-last", money(r.letzteDividende));
      set("o-lastm", money(r.letzteDividendeMonat));
      var labels = r.rows.map(function (x) { return "Jahr " + x.jahr; });
      draw("c-chart", {
        type: "bar",
        data: {
          labels: labels, datasets: [
            { label: "Netto-Dividende / Jahr", data: r.rows.map(function (x) { return x.div; }), backgroundColor: GREEN, yAxisID: "y1", order: 3 },
            { label: "Depotwert", type: "line", data: r.rows.map(function (x) { return x.wert; }), borderColor: BLUE, backgroundColor: "rgba(37,99,235,.1)", fill: true, tension: .3, yAxisID: "y", order: 1 },
            { label: "Eingezahlt", type: "line", data: r.rows.map(function (x) { return x.eingezahlt; }), borderColor: GREY, borderDash: [6, 4], pointRadius: 0, yAxisID: "y", order: 2 }
          ]
        },
        options: {
          interaction: { mode: "index", intersect: false },
          scales: {
            y: { position: "left", title: { display: true, text: "Depotwert (€)" }, ticks: { callback: axisMoney } },
            y1: { position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "Dividende (€)" }, ticks: { callback: axisMoney } }
          },
          plugins: { title: { display: true, text: "Depotwert, Einzahlungen und jährliche Netto-Dividende" }, tooltip: { callbacks: { label: tipMoney } } }
        }
      });
      var tb = $("c-rows");
      if (tb) {
        tb.innerHTML = "";
        r.rows.forEach(function (row) {
          var tr = document.createElement("tr");
          [row.jahr, dec2(row.eingezahlt), dec2(row.div), dec2(row.wert)].forEach(function (v) {
            var td = document.createElement("td"); td.textContent = v; tr.appendChild(td);
          });
          tb.appendChild(tr);
        });
      }
    }
    form.addEventListener("input", run);
    form.addEventListener("change", run);
    form.addEventListener("submit", function (e) { e.preventDefault(); run(); });
    toggle("c-tablebtn", "c-tablewrap", "block");
    run();
  }

  function init() { initGrowth(); initYield(); initCompound(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})(typeof window !== "undefined" ? window : globalThis);

/* Rechner-Sammlung: Dividenden-Vergleich, Von Dividenden leben, Rentenlücke, Rentenstrategie,
   Dividenden reinvestieren, Altersvorsorgedepot, Vorabpauschale, ETF-Rechner.
   Läuft komplett im Browser. Benötigt calc.js (DivCalc) und Chart.js. Alle Werte sind Annahmen, keine Prognosen. */
(function (root) {
  "use strict";
  var DC = root.DivCalc || (typeof require !== "undefined" ? require("./calc.js") : null);

  /* ---------- Finanzmathematik (rein, testbar) ---------- */
  var pos = function (v) { return Math.max(0, v); };
  var monthly = function (r) { return Math.pow(1 + r, 1 / 12) - 1; };

  /** Dividenden-Vergleich: zwei Szenarien mit gleichen Rahmendaten. */
  function compareCalc(o) {
    var mk = function (s) { return DC.growthCalc({ start: o.start, monat: o.monat, rendite: s.rendite, divwachstum: s.dg, kurswachstum: s.pg, jahre: o.jahre, steuer: (s.steuer != null ? s.steuer : o.steuer), reinvest: o.reinvest }); };
    var a = mk(o.a), b = mk(o.b), cross = null;
    for (var i = 0; i < a.rows.length; i++) { if (b.rows[i].netto > a.rows[i].netto) { cross = i + 1; break; } }
    return { a: a, b: b, ueberholJahr: cross };
  }

  /** Brutto-Dividende, die für ein gewünschtes Netto nötig ist (mit Sparer-Pauschbetrag F). */
  function grossForNet(net, t, F) {
    if (F > 0 && net <= F) return net;
    return F > 0 ? (net - t * F) / (1 - t) : net / (1 - t);
  }

  /** Von Dividenden leben: nötiges Kapital und Zeit bis zum Ziel. */
  function livingCalc(o) {
    var netYear = o.wunsch * 12, y = o.rendite / 100;
    var gross = grossForNet(netYear, o.steuer, o.freibetrag);
    var out = { bruttoJahr: gross, kapital: y > 0 ? gross / y : Infinity, rows: [], jahrErreicht: null };
    var cap = o.start, yy = y, gp = o.kurswachstum / 100, gd = o.divwachstum / 100, infl = o.inflation / 100;
    for (var i = 1; i <= o.jahre; i++) {
      cap += o.monat * 12;
      cap *= (1 + gp);
      var g = cap * yy, tax = pos(g - o.freibetrag) * o.steuer, net = g - tax;
      var target = netYear * Math.pow(1 + infl, i);
      cap += net;
      yy *= (1 + gd);
      out.rows.push({ jahr: i, kapital: cap, nettoMonat: net / 12, zielMonat: target / 12 });
      if (out.jahrErreicht === null && net >= target) out.jahrErreicht = i;
    }
    return out;
  }

  /** Barwert einer wachsenden Zahlung (vorschüssig): P, Wachstum i, Rendite r, N Jahre. */
  function growingAnnuityDue(P, i, r, N) {
    var q = (1 + i) / (1 + r);
    if (Math.abs(q - 1) < 1e-12) return P * N;
    return P * (1 - Math.pow(q, N)) / (1 - q);
  }
  /** Monatliche Sparrate, damit nach n Jahren der Zielwert erreicht wird (Startkapital S0). */
  function savingsFor(target, S0, rAnnual, years) {
    var rm = monthly(rAnnual), n = years * 12;
    var fv0 = S0 * Math.pow(1 + rAnnual, years);
    var need = pos(target - fv0);
    if (need === 0) return { rate: 0, fv0: fv0 };
    return { rate: rm === 0 ? need / n : need * rm / (Math.pow(1 + rm, n) - 1), fv0: fv0 };
  }
  function accumulate(S0, rate, rAnnual, years) {
    var rm = monthly(rAnnual), bal = S0, paid = S0, rows = [];
    for (var y = 1; y <= years; y++) {
      for (var m = 0; m < 12; m++) { bal = bal * (1 + rm) + rate; }
      paid += rate * 12;
      rows.push({ jahr: y, wert: bal, eingezahlt: paid });
    }
    return rows;
  }

  /** Rentenlücke füllen. Alle Eingaben in heutiger Kaufkraft, Ergebnis nominal zum Rentenbeginn. */
  function gapCalc(o) {
    var years = o.rentenalter - o.alter, N = o.endalter - o.rentenalter;
    if (!(years >= 1) || !(N >= 1)) return null;
    var infl = o.inflation / 100, gapReal = pos(o.wunsch - o.rente);
    var gapNomYear = gapReal * 12 * Math.pow(1 + infl, years);
    // A) Kapitalverzehr: Netto-Lücke -> brutto Entnahme
    var wA = gapNomYear / (1 - o.steuerEntnahme);
    var kA = growingAnnuityDue(wA, infl, o.rRuhestand / 100, N);
    // B) nur Dividenden: Kapital bleibt erhalten
    var wB = gapNomYear / (1 - o.steuerDiv);
    var kB = o.divRendite > 0 ? wB / (o.divRendite / 100) : Infinity;
    var sA = savingsFor(kA, o.start, o.rAnspar / 100, years), sB = savingsFor(kB, o.start, o.rAnspar / 100, years);
    return {
      jahre: years, dauer: N, luckeHeute: gapReal, luckeNominalMonat: gapNomYear / 12,
      kapitalVerzehr: kA, kapitalDividende: kB, sparrateVerzehr: sA.rate, sparrateDividende: sB.rate,
      rowsA: accumulate(o.start, sA.rate, o.rAnspar / 100, years), rowsB: accumulate(o.start, sB.rate, o.rAnspar / 100, years)
    };
  }

  /** Rentenstrategien: A nur Dividenden, B inflationsangepasste Entnahme (z. B. 4 %), C feste Zeitrente. */
  function strategyCalc(o) {
    var N = o.endalter - o.rentenalter;
    if (!(N >= 1)) return null;
    var K0 = o.kapital, r = o.gesamtrendite / 100, y0 = o.divRendite / 100, gp = r - y0, dg = o.divwachstum / 100, infl = o.inflation / 100;
    var A = [], B = [], C = [], i, k;
    for (i = 0; i < N; i++) {
      A.push({ alter: o.rentenalter + i, netto: K0 * y0 * Math.pow(1 + dg, i) * (1 - o.steuerDiv), kapital: K0 * Math.pow(1 + gp, i) });
    }
    var W0 = K0 * o.entnahme / 100, kb = K0, bLeer = null;
    for (i = 0; i < N; i++) {
      var w = Math.min(kb, W0 * Math.pow(1 + infl, i));
      B.push({ alter: o.rentenalter + i, netto: w * (1 - o.steuerEntnahme), kapital: kb });
      if (kb <= 0 && bLeer === null) bLeer = o.rentenalter + i;
      kb = (kb - w) * (1 + r);
      if (kb < 1e-6 && bLeer === null && i < N - 1) bLeer = o.rentenalter + i + 1;
    }
    var sum = 0; for (k = 0; k < N; k++) sum += Math.pow(1 + r, -k);
    var P = K0 / sum, kc = K0;
    for (i = 0; i < N; i++) {
      C.push({ alter: o.rentenalter + i, netto: P * (1 - o.steuerEntnahme), kapital: kc });
      kc = (kc - P) * (1 + r);
    }
    var tot = function (rows) { return rows.reduce(function (s, x) { return s + x.netto; }, 0); };
    return {
      N: N, A: A, B: B, C: C, bLeerAlter: bLeer,
      endA: K0 * Math.pow(1 + gp, N), endB: kb, endC: Math.max(0, kc),
      summeA: tot(A), summeB: tot(B), summeC: tot(C)
    };
  }

  /** Förderung Altersvorsorgedepot (Stand Oktober 2026, Altersvorsorgereformgesetz, ab 2027). */
  function zulage(C, kinderAktiv) {
    // Mindestbeitrag 120 Euro im Jahr. Kinderzulage: 1 Euro je Euro, höchstens 300 Euro je kindergeldberechtigtem Kind; derselbe Eigenbeitrag zählt für alle Kinder.
    if (C < 120) return { grund: 0, kind: 0 };
    var grund = 0.5 * Math.min(C, 360) + 0.25 * pos(Math.min(C, 1800) - 360);
    var kind = (kinderAktiv || 0) * Math.min(C, 300);
    return { grund: grund, kind: kind };
  }
  function pension(W, rAnnual, N) { // monatliche Entnahme, nachschüssig, Kapital am Ende leer
    var rm = monthly(rAnnual), n = N * 12;
    return rm === 0 ? W / n : W * rm / (1 - Math.pow(1 + rm, -n));
  }
  function avdCalc(o) {
    var years = o.rentenalter - o.alter, N = o.endalter - o.rentenalter, C = o.beitrag * 12;
    if (!(years >= 1) || !(N >= 1)) return null;
    var kids = o.kinderAlter || [], bis = o.kindBis || 18;
    var rm = monthly((o.rendite - o.kosten) / 100), rm1 = (o.startJahre > 0 && o.kostenStart != null) ? monthly((o.rendite - o.kostenStart) / 100) : rm, bal = 0, paid = 0, zg = 0, zk = 0, bonus = 0, rows = [];
    for (var y = 1; y <= years; y++) {
      var rmy = y <= (o.startJahre || 0) ? rm1 : rm;
      for (var m = 0; m < 12; m++) bal = bal * (1 + rmy) + o.beitrag;
      paid += C;
      var nk = 0; for (var ki = 0; ki < kids.length; ki++) if (kids[ki] + (y - 1) < bis) nk++;
      var z = zulage(C, nk);
      var b = (y === 1 && o.einsteiger) ? 200 : 0;
      bal += z.grund + z.kind + b; zg += z.grund; zk += z.kind; bonus += b;
      rows.push({ jahr: y, wert: bal, eingezahlt: paid, zulagen: zg + zk + bonus });
    }
    var gross = pension(bal, o.rAus / 100, N), net = gross * (1 - o.steuerAlter / 100);
    // Vergleich: ETF-Sparplan ohne Förderung, gleiche Eigenbeiträge
    var rme = monthly((o.rendite - o.ter) / 100), be = 0, rowsE = [];
    for (var y2 = 1; y2 <= years; y2++) { for (var m2 = 0; m2 < 12; m2++) be = be * (1 + rme) + o.beitrag; rowsE.push({ jahr: y2, wert: be }); }
    var gain = pos(be - paid), tax = pos(gain * (1 - 0.3) - 1000) * 0.26375, beNet = be - tax;
    var netE = pension(beNet, o.rAus / 100, N);
    return { jahre: years, dauer: N, wert: bal, eingezahlt: paid, zulagen: zg + zk + bonus, grund: zg, kind: zk, bonus: bonus, ertrag: bal - paid - (zg + zk + bonus), brutto: gross, netto: net, rows: rows, etfWert: be, etfSteuer: tax, etfNetto: netE, etfRows: rowsE, zulageJahr: rows[0] ? zulage(C, kids.filter(function (a) { return a < bis; }).length) : zulage(C, 0), kinderJahre: kids.map(function (a) { return Math.max(0, Math.min(years, bis - a)); }) };
  }

  /** Vorabpauschale (§ 18 InvStG). */
  function vorabCalc(o) {
    var basis = o.wert1 * o.basiszins / 100 * 0.7;
    var anteil = (12 - o.monateVorher) / 12;
    var mehrbetrag = pos(o.wert2 - o.wert1 + o.ausschuettung);
    var zuwachs = pos(o.wert2 - o.wert1);
    var vp = pos(Math.min(basis, mehrbetrag) - o.ausschuettung) * anteil;
    var steuerpfl = vp * (1 - o.teilfreistellung / 100);
    var steuer = pos(steuerpfl - o.freibetrag) * o.steuer;
    return { basis: basis, zuwachs: zuwachs, vp: vp, steuerpfl: steuerpfl, steuer: steuer, mitFreibetrag: pos(steuerpfl - o.freibetrag) };
  }

  /** ETF-Sparplan. */
  function etfCalc(o) {
    var years = Math.round(o.jahre);
    if (!(years >= 1 && years <= 60)) return null;
    var rm = monthly((o.rendite - o.ter) / 100), bal = o.start, paid = o.start, rate = o.rate, rows = [];
    for (var y = 1; y <= years; y++) {
      for (var m = 0; m < 12; m++) { bal = bal * (1 + rm) + rate; }
      paid += rate * 12;
      rows.push({ jahr: y, wert: bal, eingezahlt: paid });
      rate *= (1 + o.dynamik / 100);
    }
    var gain = pos(bal - paid), taxable = pos(gain * (1 - o.teilfreistellung / 100) - o.freibetrag), tax = taxable * o.steuer;
    return { wert: bal, eingezahlt: paid, gewinn: gain, steuer: tax, netto: bal - tax, rows: rows };
  }

  /** Dividenden reinvestieren: gleiche Annahmen mit und ohne Wiederanlage. */
  function reinvestCalc(o) {
    var a = DC.compoundCalc(Object.assign({}, o, { reinvest: true })), b = DC.compoundCalc(Object.assign({}, o, { reinvest: false }));
    return (a && b) ? { mit: a, ohne: b, vorteil: a.endwert - b.endwert } : null;
  }

  var api = { compareCalc: compareCalc, livingCalc: livingCalc, grossForNet: grossForNet, gapCalc: gapCalc, strategyCalc: strategyCalc, avdCalc: avdCalc, zulage: zulage, vorabCalc: vorabCalc, etfCalc: etfCalc, reinvestCalc: reinvestCalc, growingAnnuityDue: growingAnnuityDue, pension: pension };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.RechnerMath = api;
  if (typeof document === "undefined") return;

  /* ---------- Oberfläche ---------- */
  var $ = function (id) { return document.getElementById(id); };
  var money = function (v, d) { return isFinite(v) ? new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: d || 0, minimumFractionDigits: d || 0 }).format(v) : "–"; };
  var dec2 = function (v) { return Number(v).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
  var num = function (id) {
    var el = $(id); if (!el) return NaN;
    var v = String(el.value).trim().replace(/\s/g, "");
    if (v.indexOf(",") > -1) v = v.replace(/\./g, "").replace(",", ".");
    else if (/^\d{1,3}(\.\d{3})+$/.test(v)) v = v.replace(/\./g, "");
    return v === "" ? NaN : Number(v);
  };
  var set = function (id, t) { var e = $(id); if (e) e.textContent = t; };
  var GREEN = "#10b981", BLUE = "#2563eb", RED = "#ef4444", GREY = "#6b7280", AMBER = "#f59e0b";
  var charts = {};
  function draw(id, cfg) {
    var el = $(id); if (!el || typeof Chart === "undefined") return;
    if (charts[id]) charts[id].destroy();
    cfg.options = cfg.options || {}; cfg.options.responsive = true; cfg.options.maintainAspectRatio = false;
    charts[id] = new Chart(el.getContext("2d"), cfg);
  }
  var axis = function (v) { return Number(v).toLocaleString("de-DE", { maximumFractionDigits: 0 }); };
  var tip = function (c) { return " " + c.dataset.label + ": " + money(c.parsed.y, 0); };
  var ytitle = function (t) { return { title: { display: true, text: t }, ticks: { callback: axis } }; };
  var inter = { mode: "index", intersect: false };
  function allNum(o, skip) { for (var k in o) { if (skip && skip.indexOf(k) > -1) continue; if (typeof o[k] === "number" && isNaN(o[k])) return false; } return true; }
  function err(id, msg) { set(id, msg || ""); return !msg; }
  function table(tbodyId, rows) {
    var tb = $(tbodyId); if (!tb) return; tb.innerHTML = "";
    rows.forEach(function (r) { var tr = document.createElement("tr"); r.forEach(function (v) { var td = document.createElement("td"); td.textContent = v; tr.appendChild(td); }); tb.appendChild(tr); });
  }
  function bindToggle(btn, box) {
    var b = $(btn), x = $(box); if (!b || !x) return;
    b.addEventListener("click", function () { var open = x.hidden; x.hidden = !open; b.setAttribute("aria-expanded", String(open)); });
  }
  var T = {}; // id -> run()

  /* 1) Dividenden-Vergleich */

  /** Gesamtsteuer auf die Brutto-Dividende (Bruchteil): Quellensteuer im Ausland plus deutsche Abgeltungsteuer abzüglich Anrechnung.
   *  c = { einbehalt, anrechenbar } in Prozent; refund = Erstattung des nicht anrechenbaren Teils einrechnen. */
  function gesamtSteuer(t, c, refund) {
    if (!c) return t;
    var w = c.einbehalt / 100, a = c.anrechenbar / 100;
    if (refund) w = Math.min(w, a);
    var credit = Math.min(w, a, t);
    return Math.min(1, w + (t - credit));
  }
  var QS = null;
  function loadQS() {
    var sa = document.getElementById("v-al"), sb = document.getElementById("v-bl"), form = document.getElementById("f-dividenden-vergleich");
    if (!sa || !sb || typeof fetch === "undefined") return;
    fetch("../data/quellensteuer.json").then(function (r) { return r.json(); }).then(function (j) {
      QS = j.laender; var keys = Object.keys(QS);
      keys.sort(function (x, y) { return x === "deutschland" ? -1 : y === "deutschland" ? 1 : QS[x].name.localeCompare(QS[y].name, "de"); });
      [sa, sb].forEach(function (sel) { sel.innerHTML = keys.map(function (k) { return '<option value="' + k + '">' + QS[k].name + (k === "deutschland" ? " (kein Abzug im Ausland)" : "") + "</option>"; }).join(""); });
      if (form) form.dispatchEvent(new Event("input", { bubbles: true }));
    }).catch(function () {});
  }

  if (typeof document !== "undefined" && root.RECHNER_ID === "dividenden-vergleich") { if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", loadQS); else loadQS(); }
  T["dividenden-vergleich"] = function () {
    var o = { start: num("v-start"), monat: num("v-rate"), jahre: num("v-years"), steuer: num("v-tax") / 100, reinvest: $("v-re").value === "1",
      a: { rendite: num("v-ay"), dg: num("v-ag"), pg: num("v-ap") }, b: { rendite: num("v-by"), dg: num("v-bg"), pg: num("v-bp") } };
    if (!allNum({ s: o.start, m: o.monat, j: o.jahre, t: o.steuer, ay: o.a.rendite, ag: o.a.dg, ap: o.a.pg, by: o.b.rendite, bg: o.b.dg, bp: o.b.pg }, [])) return err("v-err", "Bitte alle Felder mit Zahlen füllen.");
    if (!(o.jahre >= 1 && o.jahre <= 60)) return err("v-err", "Anlagedauer: 1 bis 60 Jahre.");
    err("v-err", "");
    var refund = $("v-rf") && $("v-rf").value === "1", ca = QS && $("v-al") ? QS[$("v-al").value] : null, cb = QS && $("v-bl") ? QS[$("v-bl").value] : null;
    o.a.steuer = gesamtSteuer(o.steuer, ca, refund); o.b.steuer = gesamtSteuer(o.steuer, cb, refund);
    var r = compareCalc(o), na = ($("v-an").value || "Aktie A").trim(), nb = ($("v-bn").value || "Aktie B").trim();
    var qsTxt = function (n, c, t) { if (!c || c.einbehalt === 0 && c.anrechenbar === 0) return ""; var pc = function (x) { return (x * 100).toLocaleString("de-DE", { maximumFractionDigits: 3 }) + " %"; }; var ex = refund ? 0 : Math.max(0, c.einbehalt - c.anrechenbar); return n + " (" + c.name.replace(/ \(.*$/, "") + "): Quellensteuer " + pc(c.einbehalt / 100) + ", insgesamt " + pc(t) + " Steuer auf die Brutto-Dividende" + (ex > 0 ? "; davon " + (ex).toLocaleString("de-DE", { maximumFractionDigits: 3 }) + " Prozentpunkte nicht anrechenbar, nur auf Antrag erstattbar" : "") + ". "; };
    set("v-qs", (qsTxt(na, ca, o.a.steuer) + qsTxt(nb, cb, o.b.steuer)).trim());
    var la = r.a.rows[r.a.rows.length - 1], lb = r.b.rows[r.b.rows.length - 1];
    set("v-k1", money(r.a.endkapital)); set("v-k2", money(r.b.endkapital));
    set("v-k3", money(la.netto)); set("v-k4", money(lb.netto));
    set("v-k5", money(r.a.summeNetto)); set("v-k6", money(r.b.summeNetto));
    set("v-n1", na); set("v-n2", nb);
    set("v-cross", r.ueberholJahr ? nb + " zahlt ab Jahr " + r.ueberholJahr + " mehr Netto-Dividende pro Jahr als " + na + "." : "In diesem Zeitraum überholt keine Variante die andere bei der jährlichen Netto-Dividende, oder " + na + " liegt durchgehend vorn.");
    var labels = r.a.rows.map(function (x) { return "Jahr " + x.jahr; });
    draw("v-chart1", { type: "line", data: { labels: labels, datasets: [{ label: na, data: r.a.rows.map(function (x) { return x.kapital; }), borderColor: BLUE, tension: .3 }, { label: nb, data: r.b.rows.map(function (x) { return x.kapital; }), borderColor: GREEN, tension: .3 }] }, options: { interaction: inter, scales: { y: ytitle("Kapital (€)") }, plugins: { title: { display: true, text: "Kapitalentwicklung" }, tooltip: { callbacks: { label: tip } } } } });
    draw("v-chart2", { type: "bar", data: { labels: labels, datasets: [{ label: na, data: r.a.rows.map(function (x) { return x.netto; }), backgroundColor: BLUE }, { label: nb, data: r.b.rows.map(function (x) { return x.netto; }), backgroundColor: GREEN }] }, options: { interaction: inter, scales: { y: ytitle("Netto-Dividende (€)") }, plugins: { title: { display: true, text: "Netto-Dividende pro Jahr" }, tooltip: { callbacks: { label: tip } } } } });
    return true;
  };

  /* 2) Von Dividenden leben */
  T["von-dividenden-leben"] = function () {
    var o = { wunsch: num("l-wish"), rendite: num("l-yield"), steuer: num("l-tax") / 100, freibetrag: num("l-free"), start: num("l-start"), monat: num("l-rate"), kurswachstum: num("l-pg"), divwachstum: num("l-dg"), inflation: num("l-inf"), jahre: 50 };
    if (!allNum(o)) return err("l-err", "Bitte alle Felder mit Zahlen füllen.");
    if (o.wunsch <= 0 || o.rendite <= 0) return err("l-err", "Wunsch-Einkommen und Dividendenrendite müssen größer als 0 sein.");
    err("l-err", "");
    var r = livingCalc(o);
    set("l-k1", money(r.kapital)); set("l-k2", money(r.bruttoJahr / 12)); set("l-k3", r.jahrErreicht ? "nach " + r.jahrErreicht + " Jahren" : "nicht in 50 Jahren");
    set("l-k4", money(r.rows[r.rows.length - 1].nettoMonat));
    var rows = r.rows.slice(0, Math.min(50, (r.jahrErreicht || 30) + 5)), labels = rows.map(function (x) { return "Jahr " + x.jahr; });
    draw("l-chart", { type: "line", data: { labels: labels, datasets: [{ label: "Netto-Dividende pro Monat", data: rows.map(function (x) { return x.nettoMonat; }), borderColor: GREEN, backgroundColor: "rgba(16,185,129,.12)", fill: true, tension: .3 }, { label: "Wunsch-Einkommen (inflationsbereinigt)", data: rows.map(function (x) { return x.zielMonat; }), borderColor: RED, borderDash: [6, 4], pointRadius: 0 }] }, options: { interaction: inter, scales: { y: ytitle("Euro pro Monat") }, plugins: { title: { display: true, text: "Wann reichen die Dividenden zum Leben?" }, tooltip: { callbacks: { label: tip } } } } });
    return true;
  };

  /* 3) Rentenlücke füllen */
  T["rentenluecke"] = function () {
    var o = { alter: num("rl-age"), rentenalter: num("rl-ret"), endalter: num("rl-end"), wunsch: num("rl-wish"), rente: num("rl-pen"), inflation: num("rl-inf"), start: num("rl-start"), rAnspar: num("rl-ra"), rRuhestand: num("rl-rr"), divRendite: num("rl-dy"), steuerEntnahme: num("rl-te") / 100, steuerDiv: num("rl-td") / 100 };
    if (!allNum(o)) return err("rl-err", "Bitte alle Felder mit Zahlen füllen.");
    var r = gapCalc(o);
    if (!r) return err("rl-err", "Das Rentenalter muss nach dem heutigen Alter liegen und das Endalter nach dem Rentenalter.");
    err("rl-err", "");
    set("rl-k1", money(r.luckeHeute)); set("rl-k2", money(r.luckeNominalMonat));
    set("rl-k3", money(r.kapitalVerzehr)); set("rl-k4", money(r.sparrateVerzehr, 0));
    set("rl-k5", money(r.kapitalDividende)); set("rl-k6", money(r.sparrateDividende, 0));
    var labels = r.rowsA.map(function (x) { return "Alter " + (o.alter + x.jahr); });
    draw("rl-chart", { type: "line", data: { labels: labels, datasets: [{ label: "Kapital bei Strategie Dividenden (Kapital bleibt)", data: r.rowsB.map(function (x) { return x.wert; }), borderColor: GREEN, tension: .3 }, { label: "Kapital bei Strategie Kapitalverzehr", data: r.rowsA.map(function (x) { return x.wert; }), borderColor: BLUE, tension: .3 }, { label: "Eingezahlt (Kapitalverzehr)", data: r.rowsA.map(function (x) { return x.eingezahlt; }), borderColor: GREY, borderDash: [6, 4], pointRadius: 0 }] }, options: { interaction: inter, scales: { y: ytitle("Kapital (€, nominal)") }, plugins: { title: { display: true, text: "Vermögensaufbau bis zum Rentenbeginn" }, tooltip: { callbacks: { label: tip } } } } });
    return true;
  };

  /* 4) Rentenstrategie */
  T["rentenstrategie"] = function () {
    var o = { rentenalter: num("rs-ret"), endalter: num("rs-end"), kapital: num("rs-cap"), gesamtrendite: num("rs-r"), divRendite: num("rs-y"), divwachstum: num("rs-g"), inflation: num("rs-inf"), entnahme: num("rs-w"), steuerDiv: num("rs-td") / 100, steuerEntnahme: num("rs-te") / 100 };
    if (!allNum(o)) return err("rs-err", "Bitte alle Felder mit Zahlen füllen.");
    var r = strategyCalc(o);
    if (!r) return err("rs-err", "Das Endalter muss nach dem Rentenalter liegen.");
    if (o.divRendite >= o.gesamtrendite) return err("rs-err", "Die Dividendenrendite muss unter der Gesamtrendite liegen, sonst bleibt kein Kurswachstum.");
    err("rs-err", "");
    var last = r.N - 1, mid = Math.min(19, last);
    set("rs-a1", money(r.A[0].netto / 12)); set("rs-b1", money(r.B[0].netto / 12)); set("rs-c1", money(r.C[0].netto / 12));
    set("rs-a2", money(r.A[mid].netto / 12)); set("rs-b2", money(r.B[mid].netto / 12)); set("rs-c2", money(r.C[mid].netto / 12));
    set("rs-a3", money(r.endA)); set("rs-b3", r.bLeerAlter ? "leer mit " + r.bLeerAlter : money(r.endB)); set("rs-c3", money(r.endC));
    set("rs-a4", money(r.summeA)); set("rs-b4", money(r.summeB)); set("rs-c4", money(r.summeC));
    set("rs-mid", "nach " + (mid) + " Jahren");
    var labels = r.A.map(function (x) { return "Alter " + x.alter; });
    draw("rs-chart1", { type: "line", data: { labels: labels, datasets: [{ label: "A: Nur Dividenden", data: r.A.map(function (x) { return x.netto / 12; }), borderColor: GREEN, tension: .3 }, { label: "B: Inflationsangepasste Entnahme", data: r.B.map(function (x) { return x.netto / 12; }), borderColor: BLUE, tension: .3 }, { label: "C: Feste Zeitrente", data: r.C.map(function (x) { return x.netto / 12; }), borderColor: AMBER, tension: .3 }] }, options: { interaction: inter, scales: { y: ytitle("Netto pro Monat (€, nominal)") }, plugins: { title: { display: true, text: "Monatliches Netto-Einkommen" }, tooltip: { callbacks: { label: tip } } } } });
    draw("rs-chart2", { type: "line", data: { labels: labels, datasets: [{ label: "A: Nur Dividenden", data: r.A.map(function (x) { return x.kapital; }), borderColor: GREEN, tension: .3 }, { label: "B: Inflationsangepasste Entnahme", data: r.B.map(function (x) { return x.kapital; }), borderColor: BLUE, tension: .3 }, { label: "C: Feste Zeitrente", data: r.C.map(function (x) { return x.kapital; }), borderColor: AMBER, tension: .3 }] }, options: { interaction: inter, scales: { y: ytitle("Kapital zu Jahresbeginn (€)") }, plugins: { title: { display: true, text: "Kapitalverlauf" }, tooltip: { callbacks: { label: tip } } } } });
    return true;
  };

  /* 5) Dividenden reinvestieren */
  T["reinvestieren"] = function () {
    var o = { start: num("ri-start"), sparrate: num("ri-rate"), rendite: num("ri-y"), divwachstum: num("ri-g"), kurswachstum: num("ri-p"), jahre: num("ri-years"), steuer: num("ri-tax") };
    if (!allNum(o)) return err("ri-err", "Bitte alle Felder mit Zahlen füllen.");
    if (o.start < 0 || o.sparrate < 0 || o.rendite < 0 || o.steuer < 0 || o.steuer > 100) return err("ri-err", "Bitte nur sinnvolle, nicht negative Werte eingeben (Steuer 0–100 %).");
    var r = reinvestCalc(o);
    if (!r) return err("ri-err", "Anlagedauer: 1 bis 60 Jahre.");
    err("ri-err", "");
    set("ri-k1", money(r.mit.endwert)); set("ri-k2", money(r.ohne.endwert)); set("ri-k3", money(r.vorteil));
    set("ri-k4", money(r.mit.letzteDividendeMonat)); set("ri-k5", money(r.ohne.letzteDividendeMonat)); set("ri-k6", money(r.ohne.kumDividende));
    var labels = r.mit.rows.map(function (x) { return "Jahr " + x.jahr; });
    draw("ri-chart1", { type: "line", data: { labels: labels, datasets: [{ label: "Mit Reinvestition: Depotwert", data: r.mit.rows.map(function (x) { return x.wert; }), borderColor: GREEN, backgroundColor: "rgba(16,185,129,.1)", fill: true, tension: .3 }, { label: "Ohne Reinvestition: Depotwert", data: r.ohne.rows.map(function (x) { return x.wert; }), borderColor: BLUE, tension: .3 }, { label: "Eingezahlt", data: r.mit.rows.map(function (x) { return x.eingezahlt; }), borderColor: GREY, borderDash: [6, 4], pointRadius: 0 }] }, options: { interaction: inter, scales: { y: ytitle("Euro") }, plugins: { title: { display: true, text: "Depotwert mit und ohne Reinvestition" }, tooltip: { callbacks: { label: tip } } } } });
    draw("ri-chart2", { type: "bar", data: { labels: labels, datasets: [{ label: "Netto-Dividende mit Reinvestition", data: r.mit.rows.map(function (x) { return x.div; }), backgroundColor: GREEN }, { label: "Netto-Dividende ohne Reinvestition", data: r.ohne.rows.map(function (x) { return x.div; }), backgroundColor: BLUE }] }, options: { interaction: inter, scales: { y: ytitle("Netto-Dividende pro Jahr (€)") }, plugins: { title: { display: true, text: "Jährliche Netto-Dividende" }, tooltip: { callbacks: { label: tip } } } } });
    return true;
  };

  /* Anbieter im Altersvorsorgedepot-Rechner: Kosten je Anbieter, Auswahl und Rangliste fuer die eigenen Eingaben */
  var AVSEL = null, AVSELB = null, AVD = null;
  function avData() {
    if (AVD) return AVD;
    var el = $("av-data"); AVD = [];
    try { if (el) AVD = JSON.parse(el.textContent); } catch (e) { }
    return AVD;
  }
  function avKosten(a, manuell) {
    var kd = a.kd, ks = a.ks, j = a.j || 0, offen = false;
    if (kd == null && ks == null) return null;
    if (kd == null) { kd = manuell; offen = true; }
    if (ks == null) { ks = kd; j = 0; }
    return { ks: ks, kd: kd, j: j, offen: offen };
  }
  function pct(v) { return String(Math.round(v * 100) / 100).replace(".", ",") + " %"; }
  function avRank(o, cur) {
    var box = $("av-rank"); if (!box) return;
    var list = avData(), rows = [];
    list.forEach(function (a, i) {
      var k = avKosten(a, o.kosten);
      if (!k) { rows.push({ i: i, a: a, offen: true }); return; }
      var r = avdCalc(Object.assign({}, o, { kosten: k.kd, kostenStart: k.ks, startJahre: k.j }));
      if (r) rows.push({ i: i, a: a, k: k, r: r });
    });
    rows.sort(function (x, y) { return (y.r ? y.r.netto : -1) - (x.r ? x.r.netto : -1); });
    var sel = AVSEL ? AVSEL.i : -1, selNetto = null;
    rows.forEach(function (x) { if (x.i === sel && x.r) selNetto = x.r.netto; });
    var base = selNetto == null ? cur.netto : selNetto;
    var h = rows.map(function (x) {
      var logo = x.a.d ? '<img class="av-logo" src="https://t1.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://' + x.a.d + '&size=64" alt="" width="22" height="22" loading="lazy" onerror="this.style.visibility=\'hidden\'">' : "";
      var n = '<th scope="row"><span class="av-id">' + logo + '<span>' + x.a.n + '</span></span></th>';
      if (x.offen) return '<tr class="off">' + n + '<td class="t">Konditionen noch offen</td><td class="num">–</td><td class="num">–</td><td class="num">–</td><td></td></tr>';
      var kt = x.k.j > 0 && x.k.ks !== x.k.kd ? pct(x.k.ks) + " für " + x.k.j + " J., danach " + pct(x.k.kd) + (x.k.offen ? " (dein Wert)" : "") : pct(x.k.kd) + (x.k.offen ? " (dein Wert)" : "");
      var diff = x.r.netto - base, ds = Math.abs(diff) < 0.5 ? "" : (diff > 0 ? "+" : "−") + money(Math.abs(diff), 0);
      return '<tr' + (x.i === sel ? ' class="sel"' : "") + '>' + n + '<td class="t">' + kt + '</td><td class="num">' + money(x.r.wert) + '</td><td class="num"><b>' + money(x.r.netto) + '</b></td><td class="num dif ' + (diff < -0.5 ? "neg" : "pos") + '">' + ds + '</td><td class="num"><button type="button" class="av-pick" data-i="' + x.i + '">' + (x.i === sel ? "gewählt" : "als A") + '</button> <button type="button" class="av-pick" data-b="' + x.i + '">' + (x.i === AVSELB ? "B gewählt" : "als B") + '</button></td></tr>';
    }).join("");
    var html = '<div class="av-tablewrap"><table class="av-table av-rank"><thead><tr><th scope="col">Anbieter</th><th scope="col">Kosten p. a.</th><th scope="col" class="num">Depotwert</th><th scope="col" class="num">Auszahlung netto / Monat</th><th scope="col" class="num">Abstand' + (selNetto == null ? " zu deiner Eingabe" : " zur Auswahl") + '</th><th scope="col"></th></tr></thead><tbody>' + h + '</tbody></table></div>';
    if (box.dataset.h !== html) { box.dataset.h = html; box.innerHTML = html; }
  }
  function avSetProv(i) {
    var list = avData(), sel = $("av-prov"), cost = $("av-cost"), hint = $("av-prov-hint");
    if (i == null || i < 0 || !list[i]) { AVSEL = null; if (sel) sel.value = ""; if (hint) hint.textContent = ""; return; }
    var a = list[i], k = avKosten(a, num("av-cost"));
    if (!k) { AVSEL = null; if (sel) sel.value = String(i); if (hint) hint.textContent = "Dieser Anbieter hat noch keine Konditionen veröffentlicht. Es gilt dein eigener Wert."; return; }
    AVSEL = { i: i, ks: k.ks, j: k.j };
    if (sel) sel.value = String(i);
    if (!k.offen && cost) cost.value = String(k.kd).replace(".", ",");
    if (hint) hint.textContent = (k.j > 0 && k.ks !== k.kd ? "Erste " + k.j + " Jahre " + pct(k.ks) + ", danach " + pct(k.kd) + ". " : "Laufende Kosten " + pct(k.kd) + ". ") + (k.offen ? "Die Kosten nach der Erstattung sind offen, es gilt dein Wert im Feld Kosten. " : "") + "Angaben laut Ankündigung, Quellen im Vergleich unten.";
  }
  function avInit() {
    var sel = $("av-prov"); if (!sel || sel.dataset.ready) return; sel.dataset.ready = "1";
    var list = avData();
    sel.innerHTML = '<option value="">Eigene Eingabe</option>' + list.map(function (a, i) { return '<option value="' + i + '">' + a.n + "</option>"; }).join("");
    sel.addEventListener("change", function () { avSetProv(sel.value === "" ? null : +sel.value); });
    var selB = $("av-prov2");
    if (selB) {
      selB.innerHTML = '<option value="">Keiner (nur ein Anbieter)</option>' + list.map(function (a, i) { return '<option value="' + i + '">' + a.n + "</option>"; }).join("");
      selB.addEventListener("change", function () { AVSELB = selB.value === "" ? null : +selB.value; var hb = $("av-prov2-hint"); if (hb) { var A = AVSELB == null ? null : list[AVSELB], k = A ? avKosten(A, num("av-cost")) : null; hb.textContent = !A ? "" : !k ? "Noch keine Konditionen veröffentlicht, es gilt dein Wert bei Kosten." : (k.j > 0 && k.ks !== k.kd ? "Erste " + k.j + " Jahre " + pct(k.ks) + ", danach " + pct(k.kd) + "." : "Laufende Kosten " + pct(k.kd) + "."); } });
    }
    var cost = $("av-cost"); if (cost) cost.addEventListener("input", function () { if (AVSEL) { AVSEL = null; sel.value = ""; var h = $("av-prov-hint"); if (h) h.textContent = ""; } });
    var box = $("av-rank");
    if (box) box.addEventListener("click", function (e) { var b = e.target.closest(".av-pick"); if (!b) return; if (b.dataset.b != null) { AVSELB = +b.dataset.b; var sb = $("av-prov2"); if (sb) { sb.value = String(AVSELB); sb.dispatchEvent(new Event("change")); } } else avSetProv(+b.dataset.i); T["altersvorsorgedepot"](); var f = $("av-prov"); if (f && f.scrollIntoView) f.scrollIntoView({ behavior: "smooth", block: "center" }); });
    var m = /[#&?]anbieter=(\d+)/.exec(location.search + location.hash); if (m) avSetProv(+m[1]);
  }

  /* 6) Altersvorsorgedepot */
  function avAges() {
    var el = $("av-kids"), raw = el ? el.value.trim() : "";
    if (!raw) return [];
    var out = [], parts = raw.split(/[\s,;]+/);
    for (var i = 0; i < parts.length; i++) { if (parts[i] === "") continue; var v = parseFloat(parts[i].replace(",", ".")); if (!isFinite(v) || v < 0 || v > 24) return null; out.push(Math.floor(v)); }
    return out.length > 8 ? null : out;
  }
  function avProvCalc(o, i) {
    var a = avData()[i]; if (!a) return null;
    var k = avKosten(a, o.kosten); if (!k) return null;
    var r = avdCalc(Object.assign({}, o, { kosten: k.kd, kostenStart: k.ks, startJahre: k.j }));
    return r ? { r: r, k: k, name: a.n } : null;
  }
  T["altersvorsorgedepot"] = function () {
    avInit();
    var ages = avAges();
    if (ages === null) return err("av-err", "Alter der Kinder: Zahlen von 0 bis 24, durch Komma getrennt, höchstens acht Kinder (leer lassen, wenn keine Kinder).");
    var o = { alter: num("av-age"), rentenalter: num("av-ret"), endalter: num("av-end"), beitrag: num("av-rate"), kinderAlter: ages, kindBis: $("av-k25").checked ? 25 : 18, einsteiger: $("av-start").checked, rendite: num("av-r"), kosten: num("av-cost"), rAus: num("av-ra"), steuerAlter: num("av-tax"), ter: num("av-ter") };
    if (!allNum(o)) return err("av-err", "Bitte alle Felder mit Zahlen füllen.");
    if (o.beitrag < 0 || o.beitrag * 12 > 6840) return err("av-err", "Der Eigenbeitrag darf höchstens 6.840 € pro Jahr betragen (570 € pro Monat).");
    if (o.rentenalter < 65 || o.rentenalter > 70) return err("av-err", "Der Auszahlungsbeginn ist laut Gesetz zwischen 65 und 70 Jahren vorgesehen.");
    if (o.endalter < 85) return err("av-err", "Der Auszahlplan muss mindestens bis zum Alter 85 laufen.");
    var bonusOk = o.alter < 25, cb = $("av-start");
    if (cb) { cb.disabled = !bonusOk; if (!bonusOk) { cb.checked = false; o.einsteiger = false; } }
    set("av-start-hint", bonusOk ? "" : "Nur bei Abschluss vor dem 25. Geburtstag.");
    o.kostenStart = AVSEL ? AVSEL.ks : null; o.startJahre = AVSEL ? AVSEL.j : 0;
    var r = avdCalc(o);
    if (!r) return err("av-err", "Das Rentenalter muss nach dem heutigen Alter liegen und das Endalter nach dem Rentenalter.");
    var warn = [];
    if (o.beitrag * 12 > 1800) warn.push("Gefördert werden nur 1.800 € Eigenbeitrag im Jahr. Für den Teil darüber gelten andere steuerliche Regeln, der Rechner nimmt trotzdem deinen Steuersatz im Alter.");
    if (o.beitrag * 12 < 120 && o.beitrag > 0) warn.push("Unter 120 € Eigenbeitrag im Jahr (10 € im Monat) gibt es keine Zulage.");
    err("av-err", warn.join(" "));
    var kh = $("av-kid-hint");
    if (kh) {
      if (!ages.length) kh.textContent = "";
      else kh.textContent = ages.map(function (a, i) { var y = Math.max(0, Math.min(r.jahre, o.kindBis - a)); return "Kind " + (i + 1) + " (" + a + " J.): " + (y > 0 ? "Zulage " + y + (y === 1 ? " Jahr" : " Jahre") + ", bis " + (o.alter + y) + " Jahre des Elternteils" : "keine Zulage mehr") ; }).join("; ") + ". Kinderzulagen insgesamt: " + money(r.kind) + ".";
    }
    set("av-k1", money(r.wert)); set("av-k2", money(r.eingezahlt)); set("av-k3", money(r.zulagen)); set("av-k4", money(r.ertrag));
    set("av-k5", money(r.zulageJahr.grund + r.zulageJahr.kind)); set("av-k6", money(r.netto) + " / Monat"); set("av-k7", money(r.etfNetto) + " / Monat"); set("av-k8", money(r.etfWert - r.etfSteuer));
    avRank(o, r);
    // Zweiter Anbieter
    var nameA = AVSEL ? avData()[AVSEL.i].n : "Eigene Eingabe", B = AVSELB != null ? avProvCalc(o, AVSELB) : null;
    var cmp = $("av-cmp"), yrs = $("av-years");
    if (cmp) cmp.hidden = !B; if (yrs) yrs.hidden = !B; 
    var labels = r.rows.map(function (x) { return "Alter " + (o.alter + x.jahr); });
    var ds = [{ label: "Balken: Eigenbeiträge", data: r.rows.map(function (x) { return x.eingezahlt; }), backgroundColor: GREY, stack: "d" }, { label: "Balken: Zulagen vom Staat", data: r.rows.map(function (x) { return x.zulagen; }), backgroundColor: GREEN, stack: "d" }, { label: "Balken: Erträge", data: r.rows.map(function (x) { return x.wert - x.eingezahlt - x.zulagen; }), backgroundColor: BLUE, stack: "d" }];
    if (B) ds.push({ label: "Linie: Depotwert " + B.name, type: "line", data: B.r.rows.map(function (x) { return x.wert; }), borderColor: "#7c3aed", borderWidth: 3, pointRadius: 0, tension: .2 });
    var cap = $("av-chartcap"); if (cap) cap.textContent = B ? "Die Balken zeigen das Depot von " + nameA + ": grau deine Beiträge, grün die Zulagen vom Staat, blau die Erträge. Die lila Linie ist der Depotwert von " + B.name + " bei gleichen Eingaben." : "Die Balken zeigen, woraus dein Depot besteht: grau deine Beiträge, grün die Zulagen vom Staat, blau die Erträge am Kapitalmarkt. Den Vergleich mit einem ETF-Sparplan nach Steuern findest du oben in den Kennzahlen.";
    draw("av-chart", { type: "bar", data: { labels: labels, datasets: ds }, options: { interaction: inter, scales: { x: { stacked: true }, y: Object.assign({ stacked: true }, ytitle("Euro")) }, plugins: { title: { display: true, text: B ? "Depotwert: " + nameA + " (Balken) gegen " + B.name + " (Linie)" : "Altersvorsorgedepot: Zusammensetzung des Depots" }, tooltip: { callbacks: { label: tip } } } } });
    if (B) {
      var dm = r.netto - B.r.netto;
      set("av-cmp-text", nameA + ": " + money(r.netto) + " netto im Monat. " + B.name + ": " + money(B.r.netto) + " netto im Monat. Abstand: " + (dm >= 0 ? "+" : "−") + money(Math.abs(dm)) + " im Monat zugunsten von " + (dm >= 0 ? nameA : B.name) + (B.k.offen ? ". Bei " + B.name + " sind die Kosten nach der Erstattung offen, es gilt dein Wert im Feld Kosten." : "."));
      var rowsH = r.rows.map(function (x, i) { var g = x.wert - B.r.rows[i].wert; return "<tr><td>" + (o.alter + x.jahr) + "</td><td class=\"num\">" + money(x.wert) + "</td><td class=\"num\">" + money(B.r.rows[i].wert) + "</td><td class=\"num " + (g < -0.5 ? "neg" : "pos") + "\">" + (g >= 0 ? "+" : "−") + money(Math.abs(g)) + "</td></tr>"; }).join("");
      var html = "<table class=\"av-table av-yt\"><thead><tr><th>Alter</th><th class=\"num\">" + nameA + "</th><th class=\"num\">" + B.name + "</th><th class=\"num\">Abstand</th></tr></thead><tbody>" + rowsH + "</tbody></table>";
      var yb = $("av-years-body"); if (yb && yb.dataset.h !== html) { yb.dataset.h = html; yb.innerHTML = html; }
    }
    return true;
  };

  /* 7) Vorabpauschale */
  T["vorabpauschale"] = function () {
    var o = { wert1: num("vp-w1"), wert2: num("vp-w2"), ausschuettung: num("vp-div"), basiszins: num("vp-bz"), monateVorher: num("vp-m"), teilfreistellung: num("vp-tf"), freibetrag: num("vp-free"), steuer: num("vp-tax") / 100 };
    if (!allNum(o)) return err("vp-err", "Bitte alle Felder mit Zahlen füllen.");
    if (o.wert1 < 0 || o.monateVorher < 0 || o.monateVorher > 11) return err("vp-err", "Monate vor dem Kauf: 0 bis 11. Fondswerte dürfen nicht negativ sein.");
    err("vp-err", "");
    var r = vorabCalc(o);
    set("vp-k1", money(r.basis, 2)); set("vp-k2", money(r.vp, 2)); set("vp-k3", money(r.steuerpfl, 2)); set("vp-k4", money(r.steuer, 2));
    set("vp-hint", r.vp === 0 ? "Keine Vorabpauschale: Der Fonds hat entweder weniger zugelegt als der Basisertrag, die Ausschüttungen decken ihn ab oder der Wert ist gesunken." : (r.steuer === 0 ? "Mit deinem freien Sparer-Pauschbetrag fällt keine Steuer an." : "Die Steuer wird in der Regel im Januar des Folgejahres von deinem Verrechnungskonto eingezogen."));
    draw("vp-chart", { type: "bar", data: { labels: ["Basisertrag", "Vorabpauschale", "nach Teilfreistellung", "nach Freibetrag", "Steuer"], datasets: [{ label: "Euro", data: [r.basis, r.vp, r.steuerpfl, r.mitFreibetrag, r.steuer], backgroundColor: [GREY, BLUE, BLUE, BLUE, RED] }] }, options: { plugins: { legend: { display: false }, title: { display: true, text: "Von der Vorabpauschale zur Steuer" }, tooltip: { callbacks: { label: function (c) { return " " + money(c.parsed.y, 2); } } } }, scales: { y: { beginAtZero: true, title: { display: true, text: "Euro" } } } } });
    return true;
  };

  /* 8) ETF-Rechner */
  T["etf-rechner"] = function () {
    var o = { start: num("e-start"), rate: num("e-rate"), dynamik: num("e-dyn"), jahre: num("e-years"), rendite: num("e-r"), ter: num("e-ter"), teilfreistellung: num("e-tf"), freibetrag: num("e-free"), steuer: num("e-tax") / 100 };
    if (!allNum(o)) return err("e-err", "Bitte alle Felder mit Zahlen füllen.");
    if (o.start < 0 || o.rate < 0) return err("e-err", "Startkapital und Sparrate dürfen nicht negativ sein.");
    var r = etfCalc(o);
    if (!r) return err("e-err", "Anlagedauer: 1 bis 60 Jahre.");
    err("e-err", "");
    set("e-k1", money(r.wert)); set("e-k2", money(r.eingezahlt)); set("e-k3", money(r.gewinn)); set("e-k4", money(r.steuer)); set("e-k5", money(r.netto));
    var labels = r.rows.map(function (x) { return "Jahr " + x.jahr; });
    draw("e-chart", { type: "bar", data: { labels: labels, datasets: [{ label: "Eingezahlt", data: r.rows.map(function (x) { return x.eingezahlt; }), backgroundColor: GREY, stack: "s" }, { label: "Erträge", data: r.rows.map(function (x) { return x.wert - x.eingezahlt; }), backgroundColor: GREEN, stack: "s" }] }, options: { interaction: inter, scales: { x: { stacked: true }, y: Object.assign({ stacked: true }, ytitle("Euro")) }, plugins: { title: { display: true, text: "Depotwert: Einzahlungen und Erträge (vor Steuern)" }, tooltip: { callbacks: { label: tip } } } } });
    table("e-rows", r.rows.map(function (x) { return [x.jahr, dec2(x.eingezahlt), dec2(x.wert - x.eingezahlt), dec2(x.wert)]; }));
    return true;
  };

  /* ---------- Menü, Umschalten, Eingaben ---------- */
  var ORDER = ["dividenden-rechner", "dividenden-vergleich", "von-dividenden-leben", "rentenluecke", "rentenstrategie", "reinvestieren", "altersvorsorgedepot", "vorabpauschale", "etf-rechner"];
  var current = null;
  function show(id, push) {
    if (ORDER.indexOf(id) < 0) id = ORDER[0];
    current = id;
    ORDER.forEach(function (k) {
      var sec = $("t-" + k), btn = $("m-" + k);
      if (sec) sec.hidden = k !== id;
      if (btn) btn.setAttribute("aria-pressed", String(k === id));
    });
    if (push) { try { history.replaceState(null, "", "#" + id); } catch (e) { location.hash = id; } }
    if (T[id]) T[id]();
    else if (root.dispatchEvent) { try { root.dispatchEvent(new Event("resize")); } catch (e) { } }
    var h = $("t-" + id); if (h && push) h.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function init() {
    var rid = root.RECHNER_ID || "dividenden-rechner";
    var SLUG = {"dividenden-vergleich": "dividenden-vergleich", "von-dividenden-leben": "von-dividenden-leben", "rentenluecke": "rentenluecke", "rentenstrategie": "rentenstrategie", "reinvestieren": "dividenden-reinvestieren", "altersvorsorgedepot": "altersvorsorgedepot", "vorabpauschale": "vorabpauschale-rechner", "etf-rechner": "etf-rechner"};
    var h0 = (location.hash || "").replace("#", "");
    if (SLUG[h0] && h0 !== rid) { location.replace((root.RECHNER_BASE || "") + SLUG[h0] + "/"); return; }
    if (!$("t-" + rid)) return;
    ORDER.forEach(function (k) {
      var b = $("m-" + k); if (b) b.addEventListener("click", function () { show(k, true); });
      var f = $("t-" + k);
      if (f && T[k]) {
        var upd = function () { if (current === k) T[k](); };
        f.addEventListener("input", upd); f.addEventListener("change", upd);
        f.addEventListener("submit", function (e) { e.preventDefault(); });
      }
    });
    bindToggle("e-tablebtn", "e-tablewrap");
    show(rid, false);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})(typeof window !== "undefined" ? window : globalThis);

