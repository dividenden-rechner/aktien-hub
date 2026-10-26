/* Zählt die FMP-Abrufe dieses Browsers pro Tag (alle Seiten teilen sich das Tageslimit des Tarifs) und zeigt eine kleine Anzeige.
   Zählt nur echte Netzabrufe; Treffer aus dem 12-Stunden-Cache der Seiten erscheinen hier nicht. */
(function () {
  var of = window.fetch; if (!of || window.__fmpcount) return; window.__fmpcount = 1;
  var day = function () { return new Date().toISOString().slice(0, 10); };
  var lim = function () { try { var v = parseInt(localStorage.getItem("fmplimit") || "", 10); return v > 0 ? v : 250; } catch (e) { return 250; } };
  var get = function () { try { var o = JSON.parse(localStorage.getItem("fmpcalls") || "null"); if (o && o.d === day()) return o; } catch (e) { } return { d: day(), n: 0, full: 0 }; };
  var put = function (o) { try { localStorage.setItem("fmpcalls", JSON.stringify(o)); } catch (e) { } };
  var el = null;
  function badge() {
    if (!document.body) return;
    var o = get(), L = lim(), full = o.full || o.n >= L;
    if (!el) {
      el = document.createElement("div"); el.setAttribute("role", "status");
      el.style.cssText = "position:fixed;left:10px;bottom:10px;z-index:40;font:12.5px/1.35 system-ui,sans-serif;padding:6px 10px;border-radius:999px;border:1px solid #dfe5ea;background:#fff;color:#5d6b78;box-shadow:0 2px 8px rgba(0,0,0,.08);max-width:calc(100vw - 20px);cursor:pointer";
      el.title = "Anzahl der FMP-Datenabrufe heute in diesem Browser (Tageslimit deines Tarifs, bei Gratis 250). Klick blendet aus.";
      el.onclick = function () { el.hidden = true; try { sessionStorage.setItem("fmphide", "1"); } catch (e) { } };
      document.body.appendChild(el);
    }
    try { if (sessionStorage.getItem("fmphide") && !full) { el.hidden = true; return; } } catch (e) { }
    el.hidden = false;
    el.textContent = full ? "FMP-Tageslimit erreicht: neue Daten gibt es erst morgen" : "FMP-Abrufe heute: " + o.n + " von " + L;
    el.style.background = full ? "#fde3e0" : o.n >= L * 0.8 ? "#fff7e6" : "#fff";
    el.style.color = full ? "#b3372d" : "#5d6b78";
  }
  window.fetch = function (u) {
    var url = typeof u === "string" ? u : (u && u.url) || "", p = of.apply(this, arguments);
    if (/financialmodelingprep\.com\/stable\//.test(url)) {
      var o = get(); o.n++; put(o); badge();
      p.then(function (r) { if (r && r.status === 429) { var q = get(); q.full = 1; put(q); badge(); } }, function () { });
    }
    return p;
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", badge); else badge();
})();
