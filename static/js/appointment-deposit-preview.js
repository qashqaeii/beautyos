(function () {
  function register() {
  Alpine.data("appointmentDepositSection", (config) => ({
    prices: config.prices || {},
    serviceId: "",
    deposit: 0,

    init() {
      const serviceEl = document.getElementById(config.serviceSelectId);
      if (serviceEl) {
        this.serviceId = serviceEl.value || "";
        serviceEl.addEventListener("change", () => {
          this.serviceId = serviceEl.value || "";
        });
      }
      const form = this.$el.closest("form");
      if (form) {
        form.addEventListener(
          "input",
          (e) => {
            if (e.target?.name === "deposit_amount_toman") {
              const v = parseInt(e.target.value, 10);
              this.deposit = Number.isFinite(v) && v > 0 ? v : 0;
            }
          },
          true
        );
        const hidden = form.querySelector('input[name="deposit_amount_toman"]');
        if (hidden?.value) {
          const v = parseInt(hidden.value, 10);
          this.deposit = Number.isFinite(v) && v > 0 ? v : 0;
        }
      }
    },

    get appointmentPrice() {
      const p = this.prices[this.serviceId];
      return p != null && p > 0 ? p : null;
    },

    get showMethod() {
      return this.deposit > 0;
    },

    get showSummary() {
      return this.appointmentPrice != null;
    },

    formatAmount(n) {
      if (window.BeautyOSMoney?.formatTomanFa) {
        return window.BeautyOSMoney.formatTomanFa(n);
      }
      return String(n);
    },

    get balanceAfterDeposit() {
      if (this.appointmentPrice == null) return null;
      return Math.max(this.appointmentPrice - this.deposit, 0);
    },
  }));
  }

  if (window.Alpine) {
    register();
  } else {
    document.addEventListener("alpine:init", register);
  }
})();
