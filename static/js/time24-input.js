(function () {
  const persianDigits = "۰۱۲۳۴۵۶۷۸۹";
  const toAscii = (value) =>
    String(value).replace(/[۰-۹]/g, (ch) => String(persianDigits.indexOf(ch)));

  const extractDigits = (value) => toAscii(value).replace(/\D/g, "").slice(0, 4);

  const formatTimeDigits = (digits, { autoColon }) => {
    if (!digits) return "";
    if (digits.length <= 2) {
      return autoColon && digits.length === 2 ? digits + ":" : digits;
    }
    return digits.slice(0, 2) + ":" + digits.slice(2);
  };

  const caretAfterFormat = (formatted, digits, autoColon) => {
    if (!formatted) return 0;
    if (autoColon && digits.length === 2) return 3;
    return formatted.length;
  };

  function handleTimeInput(el, event) {
    const deleting = Boolean(event && event.inputType && event.inputType.startsWith("delete"));
    const digits = extractDigits(el.value);
    const autoColon = !deleting && digits.length === 2;
    const formatted = formatTimeDigits(digits, { autoColon });
    el.value = formatted;
    const pos = caretAfterFormat(formatted, digits, autoColon);
    requestAnimationFrame(() => {
      try {
        el.setSelectionRange(pos, pos);
      } catch (_err) {
        /* noop */
      }
    });
  }

  window.initTime24Fields = function initTime24Fields(root) {
    const scope = root && root.querySelectorAll ? root : document;
    const fields = scope.querySelectorAll
      ? scope.querySelectorAll(".input-field--time24")
      : [];
    fields.forEach((el) => {
      if (el.dataset.time24Bound === "1") return;
      el.dataset.time24Bound = "1";
      el.addEventListener("input", (event) => handleTimeInput(el, event));
    });
  };

  document.addEventListener("DOMContentLoaded", function () {
    window.initTime24Fields(document);
  });
})();
