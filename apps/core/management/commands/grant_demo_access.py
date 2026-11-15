"""Give a dev user read/write access to demo salons (local showcase)."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.salons.models import Salon, SalonMembership


class Command(BaseCommand):
    help = "Grant manager membership on demo salons to a user (DEBUG / ALLOW_DEMO_SEED only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--phone",
            default=getattr(settings, "BEAUTYOS_DEMO_GRANT_PHONE", "09357930033"),
            help="User phone (default: local superuser)",
        )

    def handle(self, *args, **options):
        if not (settings.DEBUG or getattr(settings, "ALLOW_DEMO_SEED", False)):
            raise CommandError("grant_demo_access is only for local/demo environments.")

        phone = options["phone"].strip()
        if not phone.startswith("+"):
            if phone.startswith("0"):
                phone = "+98" + phone[1:]
            else:
                phone = "+98" + phone.lstrip("0")

        user = User.objects.filter(phone=phone).first()
        if not user:
            raise CommandError(f"No user with phone {phone}")

        for slug in ("demo-salon-a", "demo-barber-b"):
            salon = Salon.objects.filter(slug=slug).first()
            if not salon:
                self.stdout.write(self.style.WARNING(f"Skip missing salon {slug}"))
                continue
            _, created = SalonMembership.objects.get_or_create(
                user=user,
                salon=salon,
                defaults={"role": SalonMembership.Role.MANAGER, "is_active": True},
            )
            if created:
                self.stdout.write(f"Granted manager on {slug} -> {user.display_phone}")
            else:
                self.stdout.write(f"Already member of {slug}")

        self.stdout.write(self.style.SUCCESS("Done. Use salon switcher in header or /onboarding/switch/<uuid>/"))
