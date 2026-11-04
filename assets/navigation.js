/* Startanimation auf jeder Seite (einmal je Browser-Sitzung): Logo ploppt auf, rutscht nach links, der Schriftzug faehrt dahinter heraus. ?intro=1 erzwingt sie. */
(function () {
  try {
    if (/[?&]intro=1/.test(location.search)) sessionStorage.removeItem("introSeen");
    if (sessionStorage.getItem("introSeen") || document.getElementById("intro")) return;
    var s = document.querySelector('script[src*="assets/navigation.js"]'); if (!s) return;
    var root = new URL(s.getAttribute("src").split("assets/navigation.js")[0] || "./", location.href).href;
    var st = document.createElement("style");
    st.textContent = "#intro{position:fixed;inset:0;z-index:99999;background:#fff;display:flex;align-items:center;justify-content:center;animation:intro-out .45s ease 3.1s forwards;cursor:pointer;font-family:Inter,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}#intro .in{display:flex;align-items:center}#intro img{width:92px;height:92px;display:block;flex:none;transform:scale(0);animation:intro-pop .7s cubic-bezier(.2,1.5,.4,1) .15s forwards;position:relative;z-index:2;background:#fff;border-radius:50%}#intro .nm{display:block;overflow:hidden;white-space:nowrap;max-width:0;animation:intro-grow .95s cubic-bezier(.3,.7,.2,1) 1.05s forwards}#intro .nm b{display:block;font-size:34px;font-weight:700;color:#14202b;padding-left:18px;line-height:1.3;transform:translateX(-105%);animation:intro-slide .95s cubic-bezier(.3,.7,.2,1) 1.05s forwards}#intro .nm b i{font-style:normal;color:#2f9e5b;font-weight:600}@keyframes intro-pop{to{transform:scale(1)}}@keyframes intro-grow{to{max-width:640px}}@keyframes intro-slide{to{transform:translateX(0)}}@keyframes intro-out{to{opacity:0;visibility:hidden}}@media(max-width:420px){#intro img{width:64px;height:64px}#intro .nm b{font-size:17px;padding-left:9px}}";
    document.head.appendChild(st);
    var el = document.createElement("div"); el.id = "intro"; el.setAttribute("aria-hidden", "true");
    el.innerHTML = '<div class="in"><img src="' + root + 'assets/logo-clean.png" alt="" width="92" height="92"><span class="nm"><b>Dividenden-Rechner <i>Aktien-Hub</i></b></span></div>';
    document.body.insertBefore(el, document.body.firstChild);
    var pre = document.getElementById("intro-pre"); if (pre) pre.remove();
    function fin() { var q = document.getElementById("intro-pre"); if (q) q.remove(); try { sessionStorage.setItem("introSeen", "1"); } catch (e) {} if (el.parentNode) el.parentNode.removeChild(el); if (st.parentNode) st.parentNode.removeChild(st); }
    el.addEventListener("click", fin);
    el.addEventListener("animationend", function (e) { if (e.animationName === "intro-out") fin(); });
    setTimeout(fin, 4500);
  } catch (e) {}
})();

/* Dreistrich-Menü für kleine Bildschirme. Ohne JavaScript bleibt die normale, scrollbare Menüzeile erhalten. */
(function () {
  var h = document.getElementById("hub-global-header"); if (!h) return;
  var inner = h.querySelector(".hub-nav-inner"), nav = h.querySelector(".hub-links"); if (!inner || !nav) return;
  if (!nav.id) nav.id = "hub-menu";
  var b = document.createElement("button");
  b.type = "button"; b.className = "hub-burger"; b.setAttribute("aria-label", "Menü öffnen"); b.setAttribute("aria-expanded", "false"); b.setAttribute("aria-controls", nav.id);
  b.innerHTML = "<span></span><span></span><span></span>";
  inner.insertBefore(b, nav); h.classList.add("hub-js");
  function set(o) { h.classList.toggle("hub-open", o); b.setAttribute("aria-expanded", String(o)); b.setAttribute("aria-label", o ? "Menü schließen" : "Menü öffnen"); }
  b.addEventListener("click", function () { set(!h.classList.contains("hub-open")); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && h.classList.contains("hub-open")) { set(false); b.focus(); } });
  document.addEventListener("click", function (e) { if (h.classList.contains("hub-open") && !h.contains(e.target)) set(false); });
  nav.addEventListener("click", function (e) { if (e.target.closest("a")) set(false); });
  window.addEventListener("resize", function () { if (window.innerWidth >= 1120) set(false); });
})();

/* App-Installation (PWA): Manifest ergänzen, falls die Seite keins hat, und Service Worker anmelden. */
(function () {
  try {
    var s = document.querySelector('script[src*="assets/navigation.js"]'); if (!s) return;
    var root = new URL(s.getAttribute("src").split("assets/navigation.js")[0] || "./", location.href).href;
    if (!document.querySelector('link[rel="manifest"]')) {
      var l = document.createElement("link"); l.rel = "manifest"; l.href = root + "manifest.webmanifest"; document.head.appendChild(l);
    }
    if ("serviceWorker" in navigator) navigator.serviceWorker.register(root + "sw.js", { scope: root }).catch(function () {});
  } catch (e) {}
})();
