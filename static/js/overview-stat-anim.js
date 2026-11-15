(function () {
  const NAV_CTX_KEY = "beautyosOverviewNav";
  const COUNT_MS = 900;
  const GRID_PAUSE_MS = 200;
  const CARD_STAGGER_MS = 90;
  const CARD_ENTER_MS = 480;

  const PERSIAN = "۰۱۲۳۴۵۶۷۸۹";

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function formatValue(n, useCommas) {
    let s = String(Math.max(0, Math.round(n)));
    if (useCommas) {
      s = s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    }
    return s.replace(/[0-9]/g, (d) => PERSIAN[Number(d)]);
  }

  function loadNavCtx() {
    try {
      return JSON.parse(sessionStorage.getItem(NAV_CTX_KEY) || "null");
    } catch {
      return null;
    }
  }

  function saveNavCtx(ctx) {
    try {
      sessionStorage.setItem(NAV_CTX_KEY, JSON.stringify(ctx));
    } catch {
      /* ignore */
    }
  }

  function collectTargets(grid) {
    const stats = {};
    grid.querySelectorAll(".js-overview-stat-value[data-stat-key]").forEach((el) => {
      stats[el.dataset.statKey] = Number(el.dataset.statTarget || 0);
    });
    return stats;
  }

  let runId = 0;

  function cancelRunning() {
    runId += 1;
  }

  function cardCountStartDelay(el) {
    const card = el.closest(".dashboard-stat-mini");
    if (!card) return GRID_PAUSE_MS + CARD_ENTER_MS;
    const idx = Number(card.dataset.statIndex || "1");
    return (
      GRID_PAUSE_MS + Math.max(0, idx - 1) * CARD_STAGGER_MS + CARD_ENTER_MS
    );
  }

  function animateValue(el, from, to, useCommas, onDone) {
    const myRun = runId;
    const start = performance.now();
    const range = to - from;
    const discrete = !useCommas && range > 0 && range <= 20;

    function tick(now) {
      if (myRun !== runId) return;
      const elapsed = now - start;
      const t = Math.min(1, elapsed / COUNT_MS);
      let current;
      if (discrete) {
        const stepDur = COUNT_MS / range;
        const stepIndex = Math.min(range, Math.floor(elapsed / stepDur));
        current = from + (t >= 1 ? range : stepIndex);
      } else {
        const eased = 1 - Math.pow(1 - t, 3);
        current = Math.round(from + (to - from) * eased);
      }
      el.textContent = formatValue(current, useCommas);
      if (t < 1) {
        requestAnimationFrame(tick);
      } else {
        el.textContent = formatValue(to, useCommas);
        onDone?.();
      }
    }
    requestAnimationFrame(tick);
  }

  function runCountAnimations(grid) {
    cancelRunning();

    const salonId = String(grid.dataset.salonId || "0");
    const currentDay = grid.dataset.overviewDay || "";

    const navCtx = loadNavCtx();
    const isDateNav =
      navCtx &&
      navCtx.salonId === salonId &&
      navCtx.day &&
      currentDay &&
      navCtx.day !== currentDay &&
      navCtx.stats;

    const valueEls = grid.querySelectorAll(".js-overview-stat-value[data-stat-key]");
    const nextStats = {};
    let pending = 0;

    const finishAll = () => {
      pending -= 1;
      if (pending <= 0) {
        saveNavCtx({ salonId, day: currentDay, stats: nextStats });
      }
    };

    valueEls.forEach((el) => {
      const key = el.dataset.statKey;
      const target = Number(el.dataset.statTarget || 0);
      const useCommas = el.dataset.statCommas === "1";
      nextStats[key] = target;

      if (target === 0) {
        el.textContent = formatValue(0, useCommas);
        return;
      }

      let from = 0;
      if (isDateNav && navCtx.stats[key] !== undefined) {
        from = Number(navCtx.stats[key]);
      }

      if (from === target) {
        return;
      }

      el.textContent = formatValue(from, useCommas);
      pending += 1;
      const delay = cardCountStartDelay(el);
      const myRun = runId;
      window.setTimeout(() => {
        if (myRun !== runId) return;
        animateValue(el, from, target, useCommas, finishAll);
      }, delay);
    });

    if (pending === 0) {
      saveNavCtx({ salonId, day: currentDay, stats: nextStats });
    }
  }

  function beginGridMotion(grid) {
    if (grid.dataset.animStarted === "1") return;
    grid.dataset.animStarted = "1";
    window.setTimeout(() => {
      grid.classList.add("is-in-view");
      runCountAnimations(grid);
    }, GRID_PAUSE_MS);
  }

  function init() {
    const grid = document.querySelector("[data-overview-stat-grid]");
    if (!grid) return;

    try {
      sessionStorage.removeItem("beautyosOverviewStats");
    } catch {
      /* legacy */
    }

    const salonId = String(grid.dataset.salonId || "0");
    const currentDay = grid.dataset.overviewDay || "";

    if (prefersReducedMotion()) {
      grid.classList.add("anim-disabled");
      saveNavCtx({ salonId, day: currentDay, stats: collectTargets(grid) });
      return;
    }

    grid.classList.add("anim-armed");

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && entry.target === grid) {
            beginGridMotion(grid);
            observer.disconnect();
          }
        });
      },
      { root: null, threshold: 0.12, rootMargin: "0px 0px -4% 0px" }
    );

    observer.observe(grid);

    window.addEventListener(
      "pagehide",
      () => {
        cancelRunning();
        observer.disconnect();
      },
      { once: true }
    );
  }

  function boot() {
    init();
    if (window.beautyosInitIcons) {
      window.beautyosInitIcons();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
