import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.demo_seed.engine import DEMO_SALON_SLUGS, SALON_A_SLUG, SALON_B_SLUG, DemoSeedEngine


class Command(BaseCommand):
    help = "Seed idempotent demo salons and showcase data (non-production only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            choices=("full", "minimal", "busy-day", "empty"),
            default="full",
            help="Seed profile (default: full)",
        )
        parser.add_argument(
            "--salon",
            action="append",
            dest="salons",
            help=f"Limit to demo salon slug ({SALON_A_SLUG}, {SALON_B_SLUG}); repeatable",
        )
        parser.add_argument("--reset-demo", action="store_true", help="Clear demo-namespace data before seeding")
        parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")

    def handle(self, *args, **options):
        allowed = (
            settings.DEBUG
            or getattr(settings, "ALLOW_DEMO_SEED", False)
            or os.environ.get("ALLOW_DEMO_SEED") == "1"
        )
        if not allowed:
            raise CommandError(
                "seed_demo is disabled in production. Use DEBUG/ALLOW_DEMO_SEED only on isolated demo hosts."
            )

        scenario = options["scenario"]
        slugs = options["salons"] or list(DEMO_SALON_SLUGS)
        for slug in slugs:
            if slug not in DEMO_SALON_SLUGS:
                raise CommandError(f"Unknown demo salon slug: {slug}. Allowed: {', '.join(DEMO_SALON_SLUGS)}")

        engine = DemoSeedEngine(dry_run=options["dry_run"], stdout=self.stdout)
        if options["reset_demo"] and scenario != "empty":
            engine.reset_demo(slugs)
        plan = engine.run(scenario=scenario, salon_slugs=slugs, reset_first=False)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"Dry-run: {len(plan.actions)} steps planned."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Demo seed completed — scenario={scenario}, salons={slugs}"))
