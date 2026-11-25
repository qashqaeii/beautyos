/* Gentle, accessible number reveal for the reception dashboard.
   The server-rendered number remains the source of truth. */
(() => {
  "use strict";
  const persian = (value) => String(value).replace(/[0-9]/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
  const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const animate = (node) => {
    if (node.dataset.countAnimated === "1") return;
    node.dataset.countAnimated = "1";
    const target = Number(node.dataset.countUp);
    if (!Number.isSafeInteger(target) || target < 1 || reduced()) return;
    const fallback = node.textContent;
    let start = 0;
    const duration = 650;
    const tick = (now) => {
      if (!node.isConnected) return;
      if (!start) start = now;
      const progress = Math.min(1, (now - start) / duration);
      const easing = 1 - Math.pow(1 - progress, 3);
      node.textContent = persian(Math.round(target * easing));
      if (progress < 1) requestAnimationFrame(tick);
      else node.textContent = fallback;
    };
    requestAnimationFrame(tick);
  };
  const initialize = () => {
    const nodes = Array.from(document.querySelectorAll(".reception-desk-page [data-count-up]"));
    if (!nodes.length) return;
    if (!("IntersectionObserver" in window) || reduced()) {
      nodes.forEach(animate);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        observer.unobserve(entry.target);
        animate(entry.target);
      });
    }, { threshold: 0.15 });
    nodes.forEach((node) => observer.observe(node));
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();