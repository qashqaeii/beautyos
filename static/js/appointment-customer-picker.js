(function () {
  function registerAppointmentCustomerPicker() {
    if (!window.Alpine) return;

    Alpine.data("appointmentCustomerPicker", (config) => ({
      searchUrl: config.searchUrl || "",
      customerId: config.customerId ? String(config.customerId) : "",
      query: config.initialQuery || "",
      mode: config.initialMode || "new",
      firstName: config.firstName || "",
      lastName: config.lastName || "",
      newPhone: config.newPhone || "",
      selectedName: config.selectedName || "",
      selectedPhone: config.selectedPhone || "",
      duplicateMatch: null,
      results: [],
      open: false,
      activeIndex: -1,
      loading: false,
      debounceTimer: null,
      searchGeneration: 0,
      duplicateGeneration: 0,
      canCreateCustomer: Boolean(config.canCreateCustomer),
      searchOnly: Boolean(config.searchOnly),

      init() {
        const initial = config.initialMode || "new";
        if (this.customerId) {
          this.mode = "selected";
        } else if (this.searchOnly) {
          this.mode = "search";
        } else {
          this.mode = initial;
        }
        if (!this.selectedName && this.query.includes("·")) {
          const parts = this.query.split("·");
          this.selectedName = (parts[0] || "").trim();
          this.selectedPhone = (parts[1] || "").trim();
        }
        this.syncHiddenCustomer();
        this.$watch("customerId", () => this.syncHiddenCustomer());
        const form = this.$root.closest("form");
        if (form && !form.dataset.apptCustomerSubmitHook) {
          form.dataset.apptCustomerSubmitHook = "1";
          form.addEventListener("submit", () => this.prepareSubmit());
        }
      },

      hasNewCustomerInput() {
        return [this.firstName, this.lastName, this.newPhone].some((v) => (v || "").trim());
      },

      prepareSubmit() {
        this.syncHiddenCustomer();
        // Flush hidden values synchronously, before the browser serializes the form.
        const root = this.$root;
        const mode = root.querySelector('input[name="new_customer_mode"]');
        const query = root.querySelector('input[name="customer_search"]');
        if (mode) mode.value = this.isNewCustomerSubmit() ? "on" : "";
        if (query) query.value = this.mode === "new" ? "" : this.query;
      },

      syncHiddenCustomer() {
        const el = this.$refs.customerHidden;
        if (el) el.value = this.customerId || "";
      },

      openSearch() {
        this.searchGeneration += 1;
        this.duplicateGeneration += 1;
        this.mode = "search";
        this.open = false;
        this.results = [];
        this.duplicateMatch = null;
        this.$nextTick(() => {
          const el = this.$refs.searchInput;
          if (el) el.focus();
        });
      },

      changeCustomer() {
        this.searchGeneration += 1;
        this.duplicateGeneration += 1;
        this.customerId = "";
        this.syncHiddenCustomer();
        this.selectedName = "";
        this.selectedPhone = "";
        this.query = "";
        this.duplicateMatch = null;
        if (this.searchOnly) {
          this.mode = "search";
        } else {
          this.mode = "new";
        }
      },

      onInput() {
        this.customerId = "";
        if (this.debounceTimer) clearTimeout(this.debounceTimer);
        this.searchGeneration += 1;
        const q = this.query.trim();
        if (q.length < 1) {
          this.results = [];
          this.open = false;
          return;
        }
        this.debounceTimer = setTimeout(() => this.runSearch(q), 220);
      },

      async fetchResults(q) {
        if (!this.searchUrl) return [];
        this.loading = true;
        try {
          const url = new URL(this.searchUrl, window.location.origin);
          url.searchParams.set("q", q);
          const res = await fetch(url, {
            headers: { Accept: "application/json" },
            credentials: "same-origin",
          });
          if (!res.ok) return [];
          const data = await res.json();
          return data.results || [];
        } catch (_e) {
          return [];
        } finally {
          this.loading = false;
        }
      },

      async runSearch(q) {
        const generation = ++this.searchGeneration;
        const rows = await this.fetchResults(q);
        if (generation !== this.searchGeneration || this.mode !== "search" || this.query.trim() !== q) return;
        this.results = rows;
        this.open = rows.length > 0;
        this.activeIndex = rows.length ? 0 : -1;
      },

      selectCustomer(item) {
        this.searchGeneration += 1;
        this.duplicateGeneration += 1;
        if (this.debounceTimer) clearTimeout(this.debounceTimer);
        this.customerId = String(item.id);
        this.syncHiddenCustomer();
        this.selectedName = item.full_name;
        this.selectedPhone = item.phone_display;
        this.query = `${item.full_name} · ${item.phone_display}`;
        this.mode = "selected";
        this.open = false;
        this.results = [];
        this.duplicateMatch = null;
        this.syncSelectedDom();
      },

      syncSelectedDom() {
        const panel = this.$root.querySelector('[data-panel="selected"]');
        if (!panel) return;
        const nameEl = panel.querySelector(".appt-customer-picker__selected-name:not(.sr-only)");
        const phoneEl = panel.querySelector(".appt-customer-picker__selected-phone:not(.sr-only)");
        if (nameEl) nameEl.textContent = this.selectedName;
        if (phoneEl) phoneEl.textContent = this.selectedPhone;
      },

      async checkPhoneDuplicate() {
        this.duplicateMatch = null;
        const generation = ++this.duplicateGeneration;
        const phone = (this.newPhone || "").trim();
        if (phone.length < 8) return;
        const rows = await this.fetchResults(phone);
        if (generation !== this.duplicateGeneration || this.mode !== "new" || (this.newPhone || "").trim() !== phone) return;
        const norm = (v) => String(v || "").replace(/\D/g, "");
        const target = norm(phone);
        const exact = rows.find(
          (r) =>
            norm(r.phone_display) === target ||
            norm(r.phone_display).endsWith(target.slice(-10))
        );
        if (exact) this.duplicateMatch = exact;
      },

      useDuplicateMatch() {
        if (!this.duplicateMatch) return;
        this.selectCustomer(this.duplicateMatch);
      },

      isNewCustomerSubmit() {
        if (!this.canCreateCustomer || this.customerId) {
          return false;
        }
        return this.mode === "new";
      },

      onKeydown(event) {
        if (this.mode !== "search" || !this.open || !this.results.length) return;
        if (event.key === "ArrowDown") {
          event.preventDefault();
          this.activeIndex = Math.min(this.activeIndex + 1, this.results.length - 1);
        } else if (event.key === "ArrowUp") {
          event.preventDefault();
          this.activeIndex = Math.max(this.activeIndex - 1, 0);
        } else if (event.key === "Enter" && this.activeIndex >= 0) {
          event.preventDefault();
          this.selectCustomer(this.results[this.activeIndex]);
        } else if (event.key === "Escape") {
          event.stopPropagation();
          this.open = false;
        }
      },

      onFocusSearch() {
        const q = this.query.trim();
        if (q.length >= 1 && !this.customerId) this.runSearch(q);
      },

      onBlurList() {
        window.setTimeout(() => {
          this.open = false;
        }, 150);
      },
    }));
  }

  if (window.Alpine) {
    registerAppointmentCustomerPicker();
  } else {
    document.addEventListener("alpine:init", registerAppointmentCustomerPicker);
  }
})();
