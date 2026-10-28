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
      el.style.cssText = "font:12px/1.4 system-ui,sans-serif;padding:10px 16px 18px;text-align:center;color:#8a97a3;cursor:pointer";
      el.title = "Anzahl der neuen FMP-Datenabrufe heute durch diesen Browser (bereits gemerkte Daten zählen nicht). Klick blendet aus.";
      el.onclick = function () { el.hidden = true; try { sessionStorage.setItem("fmphide", "1"); } catch (e) { } };
      document.body.appendChild(el);
    }
    try { if (sessionStorage.getItem("fmphide") && !full) { el.hidden = true; return; } } catch (e) { }
    el.hidden = false;
    el.textContent = full ? "FMP-Tageslimit erreicht: neue Daten gibt es erst morgen" : "FMP-Abrufe heute: " + o.n + " von " + L;
    el.style.background = full ? "#fde3e0" : "transparent";
    el.style.color = full ? "#b3372d" : o.n >= L * 0.8 ? "#b26a00" : "#8a97a3";
  }
  /* Zwischenserver (Cloudflare-Worker): Seiten ohne eigenen Schluessel rufen ihn mit apikey=proxy auf.
     Der echte Schluessel liegt dort als Secret und kommt nie in den Browser. */
  var PROXY = "https://fmp-proxy.dividenden-rechner.workers.dev/";
  window.fetch = function (u, init) {
    var url = typeof u === "string" ? u : (u && u.url) || "";
    if (/financialmodelingprep\.com\/stable\//.test(url)) {
      var pu = null; try { pu = new URL(url); } catch (e) { }
      if (pu && pu.searchParams.get("apikey") === "proxy") {
        pu.searchParams.delete("apikey");
        var target = PROXY + pu.pathname.replace(/^\/stable\//, "") + pu.search;
        var pp = of.call(this, target, init);
        pp.then(function (r) {
          if (!r) return;
          if (r.headers && r.headers.get("x-fmp-cache") === "MISS") { var o = get(); o.n++; put(o); badge(); }
          if (r.status === 429) { var q = get(); q.full = 1; put(q); badge(); }
        }, function () { });
        return pp;
      }
      var o = get(); o.n++; put(o); badge();
      var p = of.apply(this, arguments);
      p.then(function (r) { if (r && r.status === 429) { var q = get(); q.full = 1; put(q); badge(); } }, function () { });
      return p;
    }
    return of.apply(this, arguments);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", badge); else badge();
})();
