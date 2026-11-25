(function () {
  function register() {
    Alpine.data("financePaymentPicker", () => ({
      hint: "",
      kindHint: "",
      init() {
        const form = this.$el;
        const customer = form.elements.customer, appointment = form.elements.appointment;
        if (!customer || !appointment) return;
        const options = Array.from(appointment.options).map(o => o.cloneNode(true));
        const filter = (reset) => {
          const previous = reset ? "" : appointment.value;
          appointment.replaceChildren(...options.filter(o => !o.value || o.dataset.customer === customer.value).map(o => o.cloneNode(true)));
          appointment.value = previous;
          if (appointment.selectedIndex < 0) appointment.value = "";
          this.hint = !customer.value ? "ابتدا مشتری را انتخاب کنید." : appointment.options.length === 1 ? "خدمت دارای مانده برای این مشتری وجود ندارد." : "خدمت موردنظر را انتخاب کنید.";
        };
        const format = value => window.BeautyOSMoney.formatGrouped(value);
        const fields = ["total_amount_toman","discount_toman","paid_amount_toman"];
        const kind = () => form.querySelector('input[name="payment_kind"]:checked')?.value || "service";
        const number = name => Number(String(form.elements[name].value).replace(/[۰-۹]/g,d => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/[.,٬]/g,""));
        const status = () => {
          if (kind() === "deposit") {
            form.elements[fields[1]].value = "۰";
            if (!appointment.value) form.elements[fields[0]].value = form.elements[fields[2]].value;
          }
          const total = number(fields[0]), discount = number(fields[1]), paid = number(fields[2]);
          if ([total,discount,paid].every(Number.isFinite) && discount <= total && paid <= total-discount && paid >= 0) form.elements.status.value = paid === total-discount ? "paid" : paid > 0 ? "partial" : "pending";
        };
        const fill = () => {
          const balance = appointment.selectedOptions[0]?.dataset.balance;
          if (balance !== undefined) {
            form.elements[fields[0]].value = format(balance);
            form.elements[fields[1]].value = "۰";
            form.elements[fields[2]].value = kind() === "deposit" ? "۰" : format(balance);
          } else {
            fields.forEach(name => form.elements[name].value = "۰");
          }
          status();
        };
        fields.forEach(name => {
          const input = form.elements[name];
          input.value = format(input.value);
          input.addEventListener("input", status);
        });
        const updateKind = () => {
          const deposit = kind() === "deposit";
          appointment.required = !deposit;
          form.elements[fields[1]].readOnly = deposit;
          form.elements[fields[0]].readOnly = deposit || !!appointment.value;
          this.kindHint = deposit ? "بیعانه را برای نوبت مشخص یا به صورت پیش‌پرداخت ثبت کنید." : "برای تسویه، خدمت دارای مانده را انتخاب کنید.";
          status();
        };
        form.querySelectorAll('input[name="payment_kind"]').forEach(el => el.addEventListener("change", () => { fill(); updateKind(); }));
        filter(false);
        updateKind();
        customer.addEventListener("change", () => { filter(true); fill(); });
        appointment.addEventListener("change", () => { fill(); updateKind(); });
      }
    }));
  }
  if (window.Alpine) register(); else document.addEventListener("alpine:init", register);
})();
