"""Regression tests for explicit local-only administrator provisioning."""
import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User


@pytest.mark.django_db
def test_debug_otp_only_provisions_platform_admin_without_salon(settings):
    settings.DEBUG = True
    call_command("ensure_superuser", "--phone", "09357930033",
                 "--name", "مدیر پلتفرم", "--local-otp-only")
    user = User.objects.get(phone="+989357930033")
    assert user.is_active and user.is_staff and user.is_superuser
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_otp_only_provisioning_rejected_in_production(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG=True"):
        call_command("ensure_superuser", "--phone", "09357930033", "--local-otp-only")
    assert not User.objects.filter(phone="+989357930033").exists()


@pytest.mark.django_db
def test_local_provisioning_is_idempotent_and_preserves_existing_password(settings):
    settings.DEBUG = True
    user = User.objects.create_user(phone="+989357930033", password="existing-secure-password")
    call_command("ensure_superuser", "--phone", "09357930033", "--local-otp-only")
    user.refresh_from_db()
    assert user.is_superuser and user.check_password("existing-secure-password")
    call_command("ensure_superuser", "--phone", "09357930033", "--local-otp-only")
    assert User.objects.filter(phone="+989357930033").count() == 1
