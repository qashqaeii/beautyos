/**
 * Persian toman display/parsing — mirrors ``fa_money`` (dot thousands, Persian digits).
 */
(function () {
  const PERSIAN = "۰۱۲۳۴۵۶۷۸۹";
  const ENGLISH = "0123456789";

  function toEnDigits(s) {
    return String(s).replace(/[٠-٩]/g, d => "٠١٢٣٤٥٦٧٨٩".indexOf(d)).replace(/[۰-۹]/g, (d) => {
      const i = PERSIAN.indexOf(d);
      return i >= 0 ? ENGLISH[i] : d;
    });
  }

  function extractDigits(s) {
    return toEnDigits(s).replace(/[^\d]/g, "");
  }

  /** Groups from digit 4 onward: 1320024 → 1.320.024 then Persian digits. */
  function formatTomanFa(n) {
    if (n === null || n === undefined || n === "") return "";
    const num = Math.round(Number(n));
    if (!Number.isFinite(num) || num < 0) return "";
    if (num === 0) return "";
    let s = String(num);
    s = s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return s.replace(/[0-9]/g, (d) => PERSIAN[Number(d)]);
  }

  function parseTomanDisplay(display) {
    const digits = extractDigits(display);
    if (!digits) return null;
    const n = parseInt(digits, 10);
    return Number.isFinite(n) ? n : null;
  }

  function digitIndexForCaret(formatted, digitsBefore) {
    if (digitsBefore <= 0) return 0;
    let counted = 0;
    for (let i = 0; i < formatted.length; i++) {
      if (/[۰-۹]/.test(formatted[i])) {
        counted += 1;
        if (counted >= digitsBefore) return i + 1;
      }
    }
    return formatted.length;
  }

  function registerTomanAlpine() {
    Alpine.data("tomanAmountField", (config) => ({
      name: config.name,
      amount: "",
      display: "",
      _formSubmitHandler: null,
      showZero: false,

      init() {
        this.showZero = this.$refs.displayInput?.dataset.showZero === "true";
        const n = Number(config.amount);
        if (Number.isFinite(n) && (n > 0 || (n === 0 && this.showZero))) {
          this.amount = n;
          this.display = n === 0 && this.showZero ? "۰" : formatTomanFa(n);
        } else {
          this.amount = "";
          this.display = "";
        }
        this.syncHiddenDom();

        const form = this.$el.closest("form");
        if (form) {
          this._formSubmitHandler = () => this.commitBeforeSubmit();
          form.addEventListener("submit", this._formSubmitHandler, { capture: true });
        }
      },

      get hiddenValue() {
        if (this.amount === "" || this.amount === null || this.amount === undefined) {
          return "";
        }
        return String(this.amount);
      },

      syncHiddenDom() {
        const h = this.$refs.hiddenInput;
        if (h) h.value = this.hiddenValue;
      },

      commitBeforeSubmit() {
        const parsed = parseTomanDisplay(this.display);
        this.amount = parsed === null ? "" : parsed;
        this.syncHiddenDom();
      },

      applyFromDigits(digits, el, digitsBeforeCaret) {
        if (!digits) {
          this.amount = "";
          this.display = "";
          this.syncHiddenDom();
          if (el) {
            this.$nextTick(() => {
              try {
                el.setSelectionRange(0, 0);
              } catch {
                /* ignore */
              }
            });
          }
          return;
        }
        const parsed = parseInt(digits, 10);
        this.amount = parsed;
        this.display = parsed === 0 && this.showZero ? "۰" : formatTomanFa(parsed);
        this.syncHiddenDom();
        if (!el) return;
        this.$nextTick(() => {
          const pos = digitIndexForCaret(this.display, digitsBeforeCaret);
          try {
            el.setSelectionRange(pos, pos);
          } catch {
            /* ignore */
          }
        });
      },

      onDisplayInput(event) {
        const el = event.target;
        const start = el.selectionStart ?? el.value.length;
        const digitsBefore = extractDigits(el.value.slice(0, start)).length;
        const digits = extractDigits(el.value);
        this.applyFromDigits(digits, el, digitsBefore);
      },

      onDisplayPaste(event) {
        event.preventDefault();
        const text =
          (event.clipboardData || window.clipboardData).getData("text") || "";
        const el = this.$refs.displayInput;
        const digits = extractDigits(text);
        const selStart = el?.selectionStart ?? 0;
        const selEnd = el?.selectionEnd ?? selStart;
        const before = extractDigits(el.value.slice(0, selStart));
        const after = extractDigits(el.value.slice(selEnd));
        const merged = `${before}${digits}${after}`;
        const digitsBefore = before.length + digits.length;
        this.applyFromDigits(merged, el, digitsBefore);
      },
    }));
  }

  // Delegated handlers work for teleported dialogs and dynamically inserted forms.
  function formatGrouped(value) {
    const raw = toEnDigits(value);
    if (!/^[0-9.,٬]*$/.test(raw)) return value;
    const digits = raw.replace(/[.,٬]/g, "").replace(/^0+(?=[0-9])/, "");
    return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".").replace(/[0-9]/g, d => PERSIAN[Number(d)]);
  }
  document.addEventListener("input", event => {
    const el = event.target;
    if (!el.matches?.("input[data-grouped-toman]")) return;
    const before = extractDigits(el.value.slice(0, el.selectionStart ?? el.value.length)).length;
    el.value = formatGrouped(el.value);
    if (/^[۰-۹.]*$/.test(el.value)) {
      const pos = digitIndexForCaret(el.value, before);
      el.setSelectionRange(pos, pos);
    }
  }, true);
  document.addEventListener("focusin", event => {
    const el = event.target;
    if (el.matches?.("input[data-grouped-toman]")) el.value = formatGrouped(el.value);
  });
  window.BeautyOSMoney = {
    formatTomanFa,
    formatGrouped,
    parseTomanDisplay,
    extractDigits,
  };

  if (window.Alpine) {
    registerTomanAlpine();
  } else {
    document.addEventListener("alpine:init", registerTomanAlpine);
  }
})();
