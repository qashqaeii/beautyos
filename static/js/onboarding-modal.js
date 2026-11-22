/* Same-origin guided setup without external runtime dependencies. */
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    var root = document.querySelector("[data-salon-onboarding]");
    if (!root) return;
    var dialog = root.querySelector(".salon-onboarding-dialog");
    var body = root.querySelector("[data-onboarding-body]");
    var errorBox = root.querySelector("[data-onboarding-error]");
    var later = root.querySelector("[data-onboarding-later]");
    var busy = false;
    var opened = false;
    var previousFocus = null;
    var currentUrl = root.dataset.stepUrl;
    function showError(message) { errorBox.textContent = message; errorBox.hidden = false; }
    function clearError() { errorBox.textContent = ""; errorBox.hidden = true; }
    function icons() {
      if (window.beautyosInitIcons) window.beautyosInitIcons();
      else if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
    }
    function setupHours() {
      body.querySelectorAll("[data-hours-closed]").forEach(function (check) {
        function update() {
          var row = check.closest("li");
          if (!row) return;
          row.querySelectorAll("[data-hours-times] input").forEach(function (input) {
            input.disabled = check.checked;
          });
        }
        check.addEventListener("change", update);
        update();
      });
    }
    async function load(url, options) {
      if (busy) return;
      busy = true;
      body.setAttribute("aria-busy", "true");
      clearError();
      try {
        var response = await fetch(url, Object.assign({
          credentials: "same-origin", headers: {"X-Requested-With": "XMLHttpRequest"}
        }, options || {}));
        if (!response.ok) throw new Error("HTTP " + response.status);
        var destination = new URL(response.url, window.location.href);
        if (!destination.pathname.match(/^\/onboarding\/wizard\/\d+\/$/)) {
          window.location.assign(response.url);
          return;
        }
        var html = await response.text();
        if (!html.includes("data-onboarding-step=")) throw new Error("Unexpected wizard response");
        currentUrl = destination.pathname + destination.search;
        body.innerHTML = html;
        setupHours();
        if (window.initTime24Fields) window.initTime24Fields(body);
        icons();
        var focus = body.querySelector('input:not([type="hidden"]):not([disabled]), button, a');
        if (focus) focus.focus({preventScroll: true});
        else dialog.focus({preventScroll: true});
      } catch (e) {
        showError("در دریافت اطلاعات مشکلی پیش آمد. دوباره تلاش کنید.");
      } finally { busy = false; body.removeAttribute("aria-busy"); }
    }
    function open() {
      if (opened) return;
      opened = true;
      previousFocus = document.activeElement;
      root.hidden = false;
      document.body.classList.add("salon-onboarding-open");
      dialog.focus({preventScroll: true});
      load(root.dataset.stepUrl);
    }
    async function defer() {
      if (busy) return;
      busy = true;
      later.disabled = true;
      clearError();
      try {
        var response = await fetch(root.dataset.deferUrl, {
          method: "POST", credentials: "same-origin",
          headers: {"X-CSRFToken": root.dataset.csrf, "X-Requested-With": "XMLHttpRequest"}
        });
        if (!response.ok) throw new Error("HTTP " + response.status);
        opened = false;
        root.hidden = true;
        root.dataset.autoOpen = "false";
        document.body.classList.remove("salon-onboarding-open");
        if (previousFocus && previousFocus.isConnected) previousFocus.focus({preventScroll: true});
      } catch (e) { showError("ذخیره انتخاب «بعداً» انجام نشد. دوباره تلاش کنید."); }
      finally { busy = false; later.disabled = false; }
    }
    document.querySelectorAll("[data-open-salon-onboarding]").forEach(function (trigger) {
      trigger.addEventListener("click", open);
    });
    later.addEventListener("click", defer);
    root.addEventListener("click", function (event) {
      var link = event.target.closest("a[href]");
      if (!link || !body.contains(link)) return;
      var url = new URL(link.href, window.location.href);
      if (url.origin === window.location.origin && url.pathname.match(/^\/onboarding\/wizard\/\d+\/$/)) {
        event.preventDefault();
        load(url.pathname + (url.search || "?modal=1"));
      }
    });
    root.addEventListener("submit", function (event) {
      var form = event.target;
      if (!body.contains(form)) return;
      event.preventDefault();
      if (busy) return;
      var data = new FormData(form);
      if (event.submitter && event.submitter.name) data.append(event.submitter.name, event.submitter.value);
      load(currentUrl, {method: "POST", body: data});
    });
    root.addEventListener("keydown", function (event) {
      if (event.key === "Escape") { event.preventDefault(); defer(); return; }
      if (event.key !== "Tab") return;
      var focusable = Array.from(dialog.querySelectorAll("a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),textarea:not([disabled]),select:not([disabled])"))
        .filter(function (el) { return el.getClientRects().length > 0; });
      if (!focusable.length) { event.preventDefault(); dialog.focus(); return; }
      if (event.shiftKey && document.activeElement === focusable[0]) {
        event.preventDefault(); focusable[focusable.length - 1].focus();
      }
      if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
        event.preventDefault(); focusable[0].focus();
      }
    });
    if (root.dataset.autoOpen === "true") open();
  });
})();
