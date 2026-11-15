import getpass
import os

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
        parser.add_argument(
            "--password-env",
            default="BEAUTYOS_BOOTSTRAP_PASSWORD",
            help="Environment variable name for password",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        phone = normalize_iran_mobile(options["phone"])
        name = options["name"]

        password = os.environ.get(options["password_env"])
        if not password:
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
        user.set_password(password)
        user.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Superuser {'created' if created else 'updated'}: phone={phone} staff={user.is_staff} super={user.is_superuser}"
            )
        )
