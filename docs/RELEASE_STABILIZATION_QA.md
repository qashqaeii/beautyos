# Stabilization and final QA

## Verified
- Baseline: the previous two browser failures originated from a Django ORM query inside Playwright's event loop and a strict full-in-viewport assertion on a short laptop. The subsequent upstream commit `99c2b42` corrected both; the associated quality gate passed.
- Production preflight and SMS delivery had already been added by `479fd7e` and `1203164`; do not duplicate those changes.
- Demo seed fail closed: both seed commands now require **both** `DEBUG=True` and `ALLOW_DEMO_SEED=True` in a non-production settings module. The legacy raw environment override cannot opt in production. Parametric guard regressions cover both commands and all disable paths.

## Manual release actions
- GitHub's connected integration exposes no branch-protection/ruleset writing operation; require the quality-gate check on `main` in GitHub Settings > Rules > Rulesets, with pull requests and blocked force pushes.
- Production dispatch remains opt-in; check sender credentials, suppression, and any scheduled jobs in the deployment host before enabling.
- Review responsive browser screenshots and real mobile devices; CI samples Chromium breakpoints but does not certify every view or device.
- **No production deploy** from this change.
