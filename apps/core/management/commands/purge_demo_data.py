import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.demo_seed.purge import purge_all_demo_data


class Command(BaseCommand):
    help = "Delete all demo/mock data and remove demo salon records (non-production only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-salons",
            action="store_true",
            help="Clear transactional demo data but keep demo-salon-a and demo-barber-b records.",
        )

    def handle(self, *args, **options):
        module = (
            os.environ.get("DJANGO_SETTINGS_MODULE")
            or getattr(settings, "SETTINGS_MODULE", None)
            or ""
        )
        allowed = getattr(settings, "ALLOW_DEMO_SEED", False) is True and not module.endswith(".production")
        if not allowed:
            raise CommandError(
                "purge_demo_data is disabled in production. Use ALLOW_DEMO_SEED=True in non-production settings only."
            )

        summary = purge_all_demo_data(stdout=self.stdout, destroy_salons=not options["keep_salons"])
        self.stdout.write(self.style.SUCCESS("Demo and mock data purged."))
        self.stdout.write(str(summary))