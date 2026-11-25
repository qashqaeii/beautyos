(function () {
  "use strict";
  const initialized = new WeakSet();
  function init(staff) {
    if (initialized.has(staff)) return;
    const form = staff.closest("form");
    const service = form && form.elements.namedItem("service");
    if (!service || service.tagName !== "SELECT") return;
    initialized.add(staff);
    const options = Array.from(staff.options).filter(option => option.value).map(option => option.cloneNode(true));
    const hint = document.createElement("p");
    hint.className = "text-xs text-ink-muted";
    hint.style.marginTop = "4px";
    hint.setAttribute("aria-live", "polite");
    staff.insertAdjacentElement("afterend", hint);
    function filter() {
      const previous = staff.value;
      const eligible = service.value ? options.filter(option =>
        (option.dataset.serviceIds || "").split(",").includes(service.value)) : [];
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = !service.value ? "ابتدا خدمت را انتخاب کنید" :
        eligible.length ? "انتخاب متخصص" : "متخصصی برای این خدمت تعریف نشده";
      staff.replaceChildren(placeholder, ...eligible.map(option => option.cloneNode(true)));
      staff.value = eligible.some(option => option.value === previous) ? previous : "";
      staff.disabled = !service.value || !eligible.length;
      hint.textContent = service.value && !eligible.length ? "ابتدا این خدمت را به یک متخصص فعال و قابل رزرو اختصاص دهید." : "";
      if (staff.value !== previous) staff.dispatchEvent(new Event("change", { bubbles: true }));
    }
    service.addEventListener("change", filter);
    filter();
  }
  function scan(root) {
    if (root.matches?.("select[data-booking-staff-filter]")) init(root);
    root.querySelectorAll?.("select[data-booking-staff-filter]").forEach(init);
  }
  function start() {
    scan(document);
    new MutationObserver(records => {
      for (const record of records) for (const node of record.addedNodes) {
        if (node.nodeType === 1) scan(node);
      }
    }).observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
