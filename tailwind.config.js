/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./apps/**/templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        espresso: {
          DEFAULT: "var(--color-text-primary)",
          hover: "var(--color-primary-hover)",
          light: "var(--color-primary-hover)",
          active: "var(--color-sidebar-active)",
        },
        accent: { DEFAULT: "var(--color-accent)", soft: "var(--color-accent-soft)" },
        porcelain: "var(--color-background)",
        surface: {
          DEFAULT: "var(--color-surface)",
          muted: "var(--color-surface-muted)",
          elevated: "var(--color-surface-elevated, var(--color-surface))",
          lavender: "var(--color-surface-lavender, var(--color-accent-soft))",
          sage: "var(--color-surface-sage, var(--color-sage-soft))",
        },
        focus: "var(--color-focus, var(--color-accent))",
        divider: "var(--color-divider, var(--color-border-strong))",
        ink: {
          DEFAULT: "var(--color-text-primary)",
          secondary: "var(--color-text-secondary)",
          muted: "var(--color-text-muted)",
        },
        line: { DEFAULT: "var(--color-border)", strong: "var(--color-border-strong)" },
        sage: { DEFAULT: "var(--color-sage, #929f82)", soft: "var(--color-sage-soft, #dde4d8)" },
        blush: "var(--color-blush, #fae8ef)",
        success: "var(--color-success-text, #426B53)",
        warning: "var(--color-warning, #B28650)",
        danger: "var(--color-danger, #C06B72)",
        sidebar: {
          DEFAULT: "var(--color-sidebar)",
          hover: "var(--color-sidebar-hover)",
          active: "var(--color-sidebar-active)",
        },
        aubergine: "var(--color-text-primary)",
        lavender: "var(--color-accent)", /* legacy alias → Editorial Rose accent */
        rose: "var(--color-accent)",
        champagne: "var(--color-accent-soft)",
        ivory: "var(--color-background)",
        charcoal: "var(--color-text-primary)",
        coral: "#B76862",
        emerald: "#557565",
      },
      fontFamily: {
        sans: ["Vazirmatn", "system-ui", "sans-serif"],
        editorial: ["Markazi Text", "Georgia", "serif"],
      },
      boxShadow: {
        card: "var(--shadow-card)",
        lift: "var(--shadow-card)",
        subtle: "var(--shadow-subtle)",
      },
      borderRadius: { xl: "0.75rem", "2xl": "1rem", "3xl": "1.25rem" },
    },
  },
  plugins: [],
};
