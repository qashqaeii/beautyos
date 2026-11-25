(function () {
  function register() {
    Alpine.data("financePaymentPicker", () => ({
      hint: "",
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
        const format = value => {
          const digits = String(value).replace(/[۰-۹]/g,d => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/[٠-٩]/g,d => "٠١٢٣٤٥٦٧٨٩".indexOf(d));
          if (!/^[0-9.,٬]*$/.test(digits)) return value;
          return digits.replace(/[.,٬]/g,"").replace(/\B(?=(\d{3})+(?!\d))/g,".").replace(/[0-9]/g,d => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]);
        };
        const fields = ["total_amount_toman","discount_toman","paid_amount_toman"];
        const number = name => Number(String(form.elements[name].value).replace(/[۰-۹]/g,d => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/[.,٬]/g,""));
        const status = () => {
          const total = number(fields[0]), discount = number(fields[1]), paid = number(fields[2]);
          if ([total,discount,paid].every(Number.isFinite) && discount <= total && paid <= total-discount && paid >= 0) form.elements.status.value = paid === total-discount ? "paid" : paid > 0 ? "partial" : "pending";
        };
        const fill = () => {
          const balance = appointment.selectedOptions[0]?.dataset.balance;
          if (balance !== undefined) {
            form.elements[fields[0]].value = format(balance);
            form.elements[fields[1]].value = "۰";
            form.elements[fields[2]].value = format(balance);
          } else {
            fields.forEach(name => form.elements[name].value = "۰");
          }
          status();
        };
        fields.forEach(name => {
          const input = form.elements[name];
          input.value = format(input.value);
          input.addEventListener("input", () => {
            const end = input.selectionStart === input.value.length;
            const old = input.selectionStart;
            const before = input.value.length;
            input.value = format(input.value);
            const pos = end ? input.value.length : Math.max(0, old + input.value.length - before);
            input.setSelectionRange(pos,pos);
            status();
          });
        });
        filter(false);
        customer.addEventListener("change", () => { filter(true); fill(); });
        appointment.addEventListener("change", fill);
      }
    }));
  }
  if (window.Alpine) register(); else document.addEventListener("alpine:init", register);
})();
