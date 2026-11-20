(function () {
  "use strict";
  let active=null, opener=null;
  function openDialog(dialog, trigger) {
    if (!dialog || typeof dialog.showModal !== "function") return false;
    if (active && active !== dialog) active.close();
    opener=trigger || null;
    if (!dialog.open) dialog.showModal();
    active=dialog;
    document.documentElement.classList.add("club-dialog-open");
    const invalid=dialog.querySelector("[aria-invalid='true']");
    (invalid || dialog.querySelector("h2"))?.focus({preventScroll:true});
    return true;
  }
  document.addEventListener("click", event => {
    const trigger=event.target.closest("[data-club-open]");
    if (trigger && openDialog(document.getElementById(trigger.dataset.clubOpen),trigger)) {
      event.preventDefault(); return;
    }
    const close=event.target.closest("[data-club-close]");
    if (close) close.closest("dialog")?.close();
    if (event.target === active && active) {
      const rect=active.getBoundingClientRect();
      if (event.clientX<rect.left || event.clientX>rect.right || event.clientY<rect.top || event.clientY>rect.bottom) active.close();
    }
  });
  function init() {
    document.querySelectorAll(".club-dialog").forEach(dialog => {
      dialog.addEventListener("close", () => {
        if (active!==dialog) return;
        if (window.__beautyosJalaliCalendarOpen) {
          dialog.querySelectorAll("[data-jalali-date]").forEach(el=>window.Alpine?.$data(el)?.closeCalendar?.());
        }
        active=null;
        document.documentElement.classList.remove("club-dialog-open");
        if (opener?.isConnected) opener.focus({preventScroll:true});
        opener=null;
      });
      dialog.addEventListener("cancel",event=>{if(window.__beautyosJalaliCalendarOpen)event.preventDefault();});
    });
    const invalid=document.querySelector(".club-dialog[data-club-autopen]");
    if (invalid) openDialog(invalid,document.querySelector('[data-club-open="'+invalid.id+'"]'));
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});else init();
})();