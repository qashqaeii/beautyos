import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.demo_seed.salon_engine import DemoSalonSeedEngine


class Command(BaseCommand):
    help = "Seed a comprehensive women's demo salon (demo-salon-a). Non-production only."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Remove demo-salon data before seeding")
        parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")

    def handle(self, *args, **options):
        # Require an explicit settings opt-in outside production. pytest-django
        # turns DEBUG off, so DEBUG alone is not a reliable environment guard.
        # The legacy raw ALLOW_DEMO_SEED environment variable grants no access.
        module = (
            os.environ.get("DJANGO_SETTINGS_MODULE")
            or getattr(settings, "SETTINGS_MODULE", None)
            or ""
        )
        allowed = (
            getattr(settings, "ALLOW_DEMO_SEED", False) is True
            and not module.endswith(".production")
        )
        if not allowed:
            raise CommandError(
                "seed_demo_salon is disabled in production. Use ALLOW_DEMO_SEED=True in non-production settings only."
            )

        engine = DemoSalonSeedEngine(dry_run=options["dry_run"], stdout=self.stdout)
        plan = engine.run(reset_first=options["reset"])

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"Dry-run: {len(plan.actions)} steps planned."))
        else:
            self.stdout.write(self.style.SUCCESS("Demo salon seed completed for demo-salon-a."))
            self.stdout.write("Run: python manage.py seed_demo_salon --reset  # to rebuild from scratch")