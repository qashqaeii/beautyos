import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.sample_seed.engine import RealisticSalonSeedEngine


class Command(BaseCommand):
    help = "Import a full professional salon dataset without demo markers (non-production only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear existing data for this sample salon before import",
        )
        parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")

    def handle(self, *args, **options):
        module = (
            os.environ.get("DJANGO_SETTINGS_MODULE")
            or getattr(settings, "SETTINGS_MODULE", None)
            or ""
        )
        allowed = (
            getattr(settings, "ALLOW_SAMPLE_SEED", False) is True
            and not module.endswith(".production")
        )
        if not allowed:
            raise CommandError(
                "seed_realistic_salon is disabled in production. Set ALLOW_SAMPLE_SEED=True in non-production settings."
            )

        engine = RealisticSalonSeedEngine(dry_run=options["dry_run"], stdout=self.stdout)
        plan = engine.run(reset_first=options["reset"])
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"Dry-run: {len(plan.actions)} steps planned."))
        else:
            self.stdout.write(self.style.SUCCESS("Realistic salon data imported (slug: atiye-noor)."))
            self.stdout.write(
                "سه ماه شمسی گذشته + نوبت‌های آینده · ۲۰ متخصص · slug: atiye-noor · "
                "پاک‌سازی: seed_realistic_salon --reset"
            )
            self.stdout.write("Owner login: +989150100001 · set password via ensure_superuser or register OTP.")