# Phase 1 — UI/UX acceptance

- Keep the approved Editorial Rose palette, logo, home hero, calendar, reception, dashboard, finance and modal architecture.
- Complete directory/profile surfaces, packages, commissions, expenses, gallery, inventory, loyalty, member and salon settings with shared patterns.
- Local Alpine, HTMX, Lucide and Persian fonts; runtime browser test explicitly blocks third-party requests.
- Chromium smoke matrix: 360x800, 768x1024, 1440x900, real Django PostgreSQL test records; public and owner workspace navigation, single visible headings, horizontal page overflow, asset errors, JavaScript exceptions, customer/staff/booking dialogs plus mobile account and desktop sidebar interaction.
- Screenshots and JUnit reports are uploaded by GitHub Actions. This is a smoke/regression matrix, not exhaustive cross-browser or visual approval. Extend it with additional role and form submission scenarios as needed.
