(function () {
  "use strict";

  function initLucideIcons() {
    var api = window.lucide;
    if (!api || typeof api.createIcons !== "function") {
      return false;
    }
    api.createIcons({
      attrs: {
        "stroke-width": "1.75",
        "aria-hidden": "true",
      },
    });
    return true;
  }

  function scheduleInit() {
    if (initLucideIcons()) {
      return;
    }
    var attempts = 0;
    var timer = window.setInterval(function () {
      attempts += 1;
      if (initLucideIcons() || attempts >= 40) {
        window.clearInterval(timer);
      }
    }, 50);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleInit);
  } else {
    scheduleInit();
  }

  window.addEventListener("load", initLucideIcons);
  document.addEventListener("alpine:initialized", initLucideIcons);
  document.body.addEventListener("htmx:afterSwap", initLucideIcons);
  document.addEventListener("beautyos:icons", initLucideIcons);

  window.beautyosInitIcons = initLucideIcons;
})();