/* Newsletter-Formular im Footer. Einzige Stelle fuer die Worker-Adresse: NEWSLETTER_URL (bei Umzug zu Strato nur hier aendern). */
(function () {
  var NEWSLETTER_URL = "https://newsletter.dividenden-rechner.workers.dev/anmelden";
  var f = document.getElementById("nl-form"); if (!f) return;
  var msg = document.getElementById("nl-msg"), btn = f.querySelector("button");
  f.addEventListener("submit", function (e) {
    e.preventDefault();
    msg.textContent = "Einen Moment …"; msg.className = ""; btn.disabled = true;
    fetch(NEWSLETTER_URL, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: f.email.value, einwilligung: f.einwilligung.checked, website: f.website.value })
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (x) {
        if (x.ok) { msg.textContent = "Fast geschafft: Wir haben dir eine E-Mail geschickt. Bitte bestätige dort deine Anmeldung."; msg.className = "ok"; f.reset(); }
        else { msg.textContent = x.j.fehler || "Das hat leider nicht geklappt."; msg.className = "err"; }
      }).catch(function () { msg.textContent = "Keine Verbindung. Bitte später erneut versuchen."; msg.className = "err"; })
      .then(function () { btn.disabled = false; });
  });
})();
