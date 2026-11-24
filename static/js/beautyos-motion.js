(function () {
  "use strict";
  const ROOT = ".maison-app,.pc-shell,.public-site";
  const CARD = [
    ".pc-kpi", ".pc-panel", ".dashboard-stat-mini__surface", ".overview-panel",
    ".dashboard-mgmt-card", ".customers-list-card", ".staff-team-card",
    ".maison-service-card", ".finance-stat-card", ".fin-panel", ".inventory-card",
    ".reception-flow__item", ".public-home-feature-card", ".public-home-step-card",
    ".public-contact-card", ".booking-card", ".checkout-workspace__panel"
  ].join(",");
  // Existing overview counters have their own animation: never touch them.
  const NUMBERS = ".pc-kpi > strong,.pc-alert-strip strong,.overview-customer-grid strong," +
    ".finance-stat-card strong,.fin-balance-item strong,.reception-flow__metrics strong," +
    ".dashboard-mgmt-card strong,.inventory-card strong";
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const persianDigits = "۰۱۲۳۴۵۶۷۸۹";
  const arabicDigits = "٠١٢٣٤٥٦٧٨٩";
  let observer;
  function parseNumeric(el) {
    if (el.children.length || el.closest("[data-overview-stat-grid]")) return null;
    const raw = el.textContent.trim();
    if (!raw || !/^[0-9۰-۹٠-٩,.٬،\s]+$/.test(raw)) return null;
    const ascii = raw.replace(/[۰-۹]/g, c => String(persianDigits.indexOf(c)))
      .replace(/[٠-٩]/g, c => String(arabicDigits.indexOf(c)))
      .replace(/[,.٬،\s]/g, "");
    if (!/^\d+$/.test(ascii)) return null;
    const value = Number(ascii);
    if (!Number.isSafeInteger(value) || value <= 0) return null;
    return { raw, value, persian:/[۰-۹]/.test(raw), arabic:/[٠-٩]/.test(raw),
      separator: raw.match(/[,.٬،]/)?.[0] || "" };
  }
  function format(value, opts) {
    let text = String(Math.round(value));
    if (opts.separator) text = text.replace(/\B(?=(\d{3})+(?!\d))/g, opts.separator);
    if (opts.persian) return text.replace(/\d/g, d => persianDigits[Number(d)]);
    if (opts.arabic) return text.replace(/\d/g, d => arabicDigits[Number(d)]);
    return text;
  }
  function animateNumber(el, opts) {
    const duration = 620;
    const started = performance.now();
    function step(now) {
      if (!el.isConnected || reduced.matches) { el.textContent = opts.raw; return; }
      const t = Math.min(1, (now - started) / duration);
      el.textContent = t >= 1 ? opts.raw : format(opts.value * (1 - Math.pow(1 - t, 3)), opts);
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  function reveal(el) {
    if (el.dataset.boMotionReady) return;
    el.dataset.boMotionReady = "1";
    if (reduced.matches) return;
    el.classList.add("bo-motion-in");
    el.addEventListener("animationend", () => el.classList.remove("bo-motion-in"), { once:true });
  }
  function setup(root) {
    const scope = root && root.querySelectorAll ? root : document;
    if (!document.querySelector(ROOT)) return;
    const cards = Array.from(scope.querySelectorAll(CARD))
      .filter(el => el.closest(ROOT) && !el.dataset.boMotionReady);
    const nums = Array.from(scope.querySelectorAll(NUMBERS)).filter(el => el.closest(ROOT) && !el.dataset.boCountReady);
    nums.forEach(el => {
      el.dataset.boCountReady = "1";
      const opts = parseNumeric(el);
      if (!opts || reduced.matches) return;
      if (observer) observer.observe(el);
      else animateNumber(el, opts);
      el._boNumeric = opts;
    });
    cards.forEach(el => {
      if (observer) observer.observe(el);
      else reveal(el);
    });
  }
  function start() {
    if (!reduced.matches && "IntersectionObserver" in window) {
      observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return;
          observer.unobserve(entry.target);
          if (entry.target._boNumeric) animateNumber(entry.target, entry.target._boNumeric);
          else reveal(entry.target);
        });
      }, { threshold:.08 });
    }
    setup(document);
    document.body.addEventListener("htmx:afterSwap", event => setup(event.detail?.target || document));
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
