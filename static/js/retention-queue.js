(function () {
  function register() {
    Alpine.data("retentionQueue", (config) => ({
      openId: config.openId ?? null,

      init() {
        if (this.openId != null) {
          this.$nextTick(() => this.focusOpen());
        }
      },

      openRow(id) {
        this.openId = id;
        this.$nextTick(() => this.focusOpen());
      },

      focusOpen() {
        const el = this.$root.querySelector(
          `[data-retention-note="${this.openId}"]`
        );
        if (el) {
          el.focus();
          const len = el.value.length;
          try {
            el.setSelectionRange(len, len);
          } catch (_e) {
            /* ignore */
          }
        }
      },

      cancel() {
        this.openId = null;
      },

      prepareSubmit() {
        /* commit handled by native submit */
      },
    }));
  }

  if (window.Alpine) {
    register();
  } else {
    document.addEventListener("alpine:init", register);
  }
})();
