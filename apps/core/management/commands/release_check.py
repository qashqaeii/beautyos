"""Read-only release gate: security, DB readiness, migrations and static files.

Run after migrate and collectstatic with DJANGO_SETTINGS_MODULE=config.settings.production.
No deployments, seed data, SMS or migrations are executed by this command.
"""
from pathlib import Path

from django.conf import settings
from django.core.checks import ERROR, WARNING, run_checks
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor


def release_findings():
    findings = []
    if settings.DEBUG:
        findings.append("DEBUG must be disabled.")
    if settings.SETTINGS_MODULE != "config.settings.production":
        findings.append("DJANGO_SETTINGS_MODULE must be config.settings.production.")
    findings += [
        str(item)
        for item in run_checks(include_deployment_checks=True)
        if item.level >= WARNING
    ]
    try:
        connection = connections["default"]
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone()[0] != 1:
                findings.append("Database readiness returned an unexpected value.")
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            findings.append(f"{len(plan)} unapplied migration(s) found.")
    except Exception:
        findings.append("Database connection or migration inspection failed.")
    static_root = Path(settings.STATIC_ROOT)
    if not (static_root / "css" / "beautyos.css").is_file():
        findings.append("Collected static assets are missing (run collectstatic).")
    return findings


class Command(BaseCommand):
    help = "Read-only production release preflight (exits nonzero on unsafe state)."

    def handle(self, *args, **options):
        findings = release_findings()
        if findings:
            raise CommandError("Release check failed:\n - " + "\n - ".join(findings))
        self.stdout.write(self.style.SUCCESS("Release checks passed: secure settings, DB, migrations, static assets."))
