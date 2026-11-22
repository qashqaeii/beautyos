# BeautyOS — Phase 0: Stability and release-image safety

Scope: fix reproducible CI regressions, make the Docker release artifact safe to build, and confirm all GitHub quality gates pass. This phase does **not** deploy production, send customer SMS, or modify business/finance data.

## 0A — Financial chart browser regression

The 1280×720 and 1440×900 Chromium checks measured a 210.09375px insights card, while the old assertion required strictly less than 210px. The finance insight grid intentionally stretches the two peer cards to equal height, and the suite already asserts that card content is not clipped. The regression now checks the trend card against its peer and a realistic upper bound, rather than failing on Chromium fractional pixels. Financial calculations, chart series, and CSS remain unchanged.

## 0B — Docker build-context security

- `.dockerignore` excludes `.env`, Git metadata, local SQLite files, media, caches, tests and logs.
- Release containers default to `DJANGO_SETTINGS_MODULE=config.settings.production`; the development-only Compose service explicitly overrides it with `local`.
- The container runs as the non-root `beautyos` user (UID 10001). `/app/media` and `/app/staticfiles` are writable/readable as appropriate.
- Static files are still collected at build time from vendored/local assets; no runtime third-party CDN is needed.
- CI builds the actual image with fake private files in the build context, and verifies that secrets and local media are not inside the image, static CSS exists, and the process identity/settings are secure.

Note: Development Compose uses the named `beautyos_media` volume. When reusing an older Docker volume created as root, verify its permissions before running the new non-root container; never solve production permissions by running as root.

## 0C — Release gates

1. CI must pass Django system checks, migrations, production release preflight, PostgreSQL regression suite, Chromium browser suite and Docker image-safety job.
2. Review the saved browser screenshots for visual quality and test physical mobile devices for critical workflows.
3. Configure a GitHub ruleset on `main`: require PR review and the quality-gate checks, and block force pushes. This is a GitHub repository setting, not application code.
4. Verify backups, a restore rehearsal, domain/HTTPS, OTP vendor credentials and an isolated staging smoke test before any production rollout.

Production remains opt-in. Do **not** use `docker-compose.yml` for a production deployment; it intentionally loads local settings.
