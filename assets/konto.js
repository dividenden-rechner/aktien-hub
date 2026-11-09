/* Konto und Watchlist-Abgleich. Einzige Stelle fuer die Worker-Adresse: KONTO_URL (leer = Konto noch nicht eingerichtet).
   Die Watchlist im Browser (localStorage "wl", Eintraege {s, n}) bleibt die Hauptquelle; mit Konto wird sie zusaetzlich auf dem Server gespeichert. */
(function () {
  var KONTO_URL = "https://konto.dividenden-rechner.workers.dev";
  var KEY = "konto_session", MAIL = "konto_mail";
  function lies(k) { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } }
  function schreib(k, v) { try { if (v) localStorage.setItem(k, v); else localStorage.removeItem(k); } catch (e) {} }
  function api(methode, pfad, body, ohneSitzung) {
    var h = { "Content-Type": "application/json" }, s = lies(KEY);
    if (s && !ohneSitzung) h.Authorization = "Bearer " + s;
    return fetch(KONTO_URL + pfad, { method: methode, headers: h, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, status: r.status, j: j }; }); });
  }
  function lokal() { try { var a = JSON.parse(localStorage.getItem("wl") || "null"); return Array.isArray(a) ? a.filter(function (x) { return x && x.s; }) : []; } catch (e) { return []; } }
  function lokalSpeichern(liste) { try { localStorage.setItem("wl", JSON.stringify(liste)); } catch (e) {} }
  function vereinen(a, b) {   // Vereinigung nach Kuerzel: nichts geht verloren, wenn Handy und Laptop verschieden gepflegt wurden
    var seen = {}, aus = [];
    a.concat(b).forEach(function (x) { var s = String(x.s).toUpperCase(); if (!seen[s]) { seen[s] = 1; aus.push({ s: s, n: x.n || s, i: x.i }); } });
    return aus;
  }
  var timer = null;
  window.Konto = {
    eingerichtet: function () { return !!KONTO_URL; },
    angemeldet: function () { return !!lies(KEY); },
    email: function () { return lies(MAIL); },
    /* Anmelde-Link anfordern */
    login: function (email, einwilligung, falle) { return api("POST", "/login", { email: email, einwilligung: einwilligung === true, website: falle || "" }, true); },
    /* Link aus der Adresszeile (?t=...) einloesen */
    einloesen: function (t) {
      return api("POST", "/verify", { t: t }, true).then(function (x) {
        if (x.ok && x.j.session) { schreib(KEY, x.j.session); schreib(MAIL, x.j.email); }
        return x;
      });
    },
    /* Beim Laden aufrufen: holt die Server-Liste, vereint sie mit der lokalen und speichert sie auf beiden Seiten */
    abgleichen: function () {
      if (!lies(KEY)) return Promise.resolve(null);
      return api("GET", "/watchlist").then(function (x) {
        if (x.status === 401) { schreib(KEY, ""); schreib(MAIL, ""); return null; }
        if (!x.ok) return null;
        var liste = vereinen(x.j.items || [], lokal());
        lokalSpeichern(liste);
        return api("PUT", "/watchlist", { items: liste }).then(function (y) { return y.ok ? y.j.items : liste; });
      });
    },
    /* Nach jeder Aenderung der Watchlist aufrufen (verzoegert, damit nicht jeder Klick einen Abruf ausloest) */
    speichern: function (liste) {
      if (!lies(KEY)) return;
      clearTimeout(timer);
      timer = setTimeout(function () { api("PUT", "/watchlist", { items: liste }); }, 1200);
    },
    export: function () { return api("GET", "/export"); },
    abmelden: function () { return api("POST", "/logout").then(function (x) { schreib(KEY, ""); schreib(MAIL, ""); return x; }); },
    loeschen: function () { return api("DELETE", "/konto").then(function (x) { if (x.ok) { schreib(KEY, ""); schreib(MAIL, ""); } return x; }); }
  };
})();
