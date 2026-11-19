/* Newsletter-Anmeldung: jedes Formular mit data-nl (Footer und Artikel-Teaser). Einzige Stelle fuer die Worker-Adresse: NEWSLETTER_URL (bei Umzug zu Strato nur hier aendern). */
(function () {
  var NEWSLETTER_URL = "https://newsletter.dividenden-rechner.workers.dev/anmelden";
  document.querySelectorAll("form[data-nl]").forEach(bind);
  function bind(f) {
    var msg = f.querySelector("[role=status]"), btn = f.querySelector("button");
    if (!msg || !btn) return;
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      msg.textContent = "Einen Moment …"; msg.className = msg.className.replace(/\s?(ok|err)/g, ""); btn.disabled = true;
      fetch(NEWSLETTER_URL, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: f.email.value, einwilligung: f.einwilligung.checked, website: f.website.value })
      }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (x) {
          if (x.ok) { msg.textContent = "Fast geschafft: Wir haben dir eine E-Mail geschickt. Bitte bestätige dort deine Anmeldung."; msg.className = (msg.className + " ok").trim(); f.reset(); }
          else { msg.textContent = x.j.fehler || "Das hat leider nicht geklappt."; msg.className = (msg.className + " err").trim(); }
        }).catch(function () { msg.textContent = "Keine Verbindung. Bitte später erneut versuchen."; msg.className = (msg.className + " err").trim(); })
        .then(function () { btn.disabled = false; });
    });
  }
})();
