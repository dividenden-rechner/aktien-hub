/* Entfernt die Startanimation nach dem Ablauf; sie laeuft nur einmal je Browser-Sitzung. */
(function () {
  var el = document.getElementById("intro"); if (!el) return;
  function fin() { try { sessionStorage.setItem("introSeen", "1"); } catch (e) {} if (el.parentNode) el.parentNode.removeChild(el); document.documentElement.classList.remove("intro-run"); }
  el.addEventListener("click", fin);
  el.addEventListener("animationend", function (e) { if (e.animationName === "intro-out") fin(); });
  setTimeout(fin, 4500);
})();
