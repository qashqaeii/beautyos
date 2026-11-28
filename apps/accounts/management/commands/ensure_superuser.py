import getpass
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.core.utils.phone import normalize_iran_mobile

DEFAULT_PHONE = "+989357930033"
DEFAULT_NAME = "qashqaeii"


class Command(BaseCommand):
    help = "Create or update Django superuser (phone-based). Password via BEAUTYOS_BOOTSTRAP_PASSWORD or prompt."

    def add_arguments(self, parser):
        parser.add_argument("--phone", default="09357930033", help="Iran mobile")
        parser.add_argument("--name", default=DEFAULT_NAME, help="Display / full name")
        parser.add_argument("--local-otp-only", action="store_true", help="DEBUG-only: provision OTP-only admin without password prompt")
        parser.add_argument(
            "--password-env",
            default="BEAUTYOS_BOOTSTRAP_PASSWORD",
            help="Environment variable name for password",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        phone = normalize_iran_mobile(options["phone"])
        name = options["name"]

        local_otp_only = options["local_otp_only"]
        if local_otp_only and not settings.DEBUG:
            raise CommandError("--local-otp-only is available only when DEBUG=True.")
        password = None if local_otp_only else os.environ.get(options["password_env"])
        if not password and not local_otp_only:
            if not os.isatty(0):
                raise CommandError(
                    "Set BEAUTYOS_BOOTSTRAP_PASSWORD or run interactively for password prompt."
                )
            password = getpass.getpass("Password: ")
            confirm = getpass.getpass("Password (again): ")
            if password != confirm:
                raise CommandError("Passwords do not match.")

        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={"full_name": name, "is_staff": True, "is_superuser": True, "is_active": True},
        )
        user.full_name = name
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        if local_otp_only:
            if created or not user.has_usable_password():
                user.set_unusable_password()
            # Preserve any existing usable password rather than silently disabling it.
        else:
            user.set_password(password)
        user.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Superuser {'created' if created else 'updated'}: phone={phone} staff={user.is_staff} super={user.is_superuser}"
            )
        )
