import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.sample_seed.dataset import SAMPLE_SALON_SLUG
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
        parser.add_argument(
            "--slug",
            default=None,
            help="Target salon slug (default: atiye-noor). Example: salon-nora",
        )

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

        slug = (options["slug"] or "").strip() or SAMPLE_SALON_SLUG
        engine = RealisticSalonSeedEngine(
            salon_slug=slug,
            dry_run=options["dry_run"],
            stdout=self.stdout,
        )
        plan = engine.run(reset_first=options["reset"])
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"Dry-run: {len(plan.actions)} steps planned."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Realistic salon data imported (slug: {slug})."))
            self.stdout.write(
                f"سه ماه شمسی گذشته + نوبت‌های آینده · ۲۰ متخصص · slug: {slug} · "
                f"پاک‌سازی: seed_realistic_salon --reset --slug {slug}"
            )
            self.stdout.write("Owner login: +989150100001 · set password via ensure_superuser or register OTP.")