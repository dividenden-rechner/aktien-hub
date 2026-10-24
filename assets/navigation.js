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
