(function () {
  const PERSIAN = "۰۱۲۳۴۵۶۷۸۹";
  const COUNT_MS = 520;
  function formatValue(n, useCommas) {
    let s = String(Math.max(0, Math.round(n)));
    if (useCommas) s = s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return s.replace(/[0-9]/g, d => PERSIAN[Number(d)]);
  }

  function init() {
    const grid = document.querySelector("[data-overview-stat-grid]");
    if (!grid) return;
    if (grid.dataset.animStarted === "1") return;
    // Do not retain financial figures from a previous authenticated session.
    try {
      sessionStorage.removeItem("beautyosOverviewNav");
      sessionStorage.removeItem("beautyosOverviewStats");
    } catch {}
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced || !("IntersectionObserver" in window)) {
      grid.classList.add("anim-disabled");
      return;
    }
    let observer;
    let generation = 0;
    const elements = Array.from(grid.querySelectorAll(".js-overview-stat-value[data-stat-key]"));
    const originalValues = elements.map(el => el.textContent);
    function restore() {
      generation += 1;
      elements.forEach((el, i) => { el.textContent = originalValues[i]; });
      observer?.disconnect();
    }
    function start() {
      if (grid.dataset.animStarted === "1") return;
      grid.dataset.animStarted = "1";
      grid.classList.add("is-in-view");
      const run = ++generation;
      const started = performance.now();
      function tick(now) {
        if (run !== generation) return;
        const elapsed = now - started;
        let active = false;
        elements.forEach((el, i) => {
          const target = Number(el.dataset.statTarget);
          // Keep server-rendered text for unsafe integers or unexpected values.
          if (!Number.isSafeInteger(target) || target <= 0) return;
          const progress = Math.max(0, Math.min(1, (elapsed - i * 45) / COUNT_MS));
          if (progress < 1) {
            active = true;
            el.textContent = formatValue(target * (1 - Math.pow(1-progress, 3)), el.dataset.statCommas === "1");
          } else {
            el.textContent = originalValues[i];
          }
        });
        if (active) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
    }
    grid.classList.add("anim-armed");
    observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        observer.disconnect();
        start();
      }
    }, { threshold: 0.12 });
    observer.observe(grid);
    window.addEventListener("pagehide", restore, { once: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
