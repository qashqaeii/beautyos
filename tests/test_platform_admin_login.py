"""Dedicated platform login routing and authorization regression."""
import pytest
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_anonymous_central_entry_uses_platform_login(client):
    response = client.get(reverse("platform_admin:overview"))
    assert response.status_code == 302
    assert response.url == reverse("platform_admin:login")
    page = client.get(reverse("platform_admin:login"))
    assert page.status_code == 200
    assert "مدیریت مرکزی" in page.content.decode()


@pytest.mark.django_db
def test_salon_account_cannot_use_central_login(client):
    salon_user = User.objects.create_user(phone="+989111110001", full_name="مدیر سالن")
    client.force_login(salon_user)
    assert client.get(reverse("platform_admin:overview")).status_code == 403
    assert client.get(reverse("platform_admin:login")).status_code == 200
    assert client.post(reverse("platform_admin:login"), {"step": "phone", "phone": "09111110001"}).status_code == 403


@pytest.mark.django_db
def test_superuser_without_salon_reaches_control(client):
    user = User.objects.create_superuser(phone="+989111110002", password="test-only-password")
    client.force_login(user)
    assert client.get(reverse("platform_admin:login")).url == reverse("platform_admin:overview")
    assert client.get(reverse("platform_admin:overview")).status_code == 200


@pytest.mark.django_db
def test_unprovisioned_number_is_rejected_without_creating_superuser(client):
    response = client.post(reverse("platform_admin:login"), {
        "step": "phone", "phone": "09111110003",
    })
    assert response.status_code == 403
    assert "حساب مدیریت مرکزی" in response.content.decode()
    assert not User.objects.filter(phone="+989111110003", is_superuser=True).exists()


@pytest.mark.django_db
def test_provisioned_admin_reaches_existing_otp_flow(client, monkeypatch):
    from types import SimpleNamespace
    from django.utils import timezone
    from apps.accounts.models import OTPChallenge
    import apps.accounts.views as account_views

    User.objects.create_superuser(phone="+989111110004", password="test-only-password")

    def fake_issue_otp(**kwargs):
        assert kwargs["phone"] == "+989111110004"
        return SimpleNamespace(
            dev_code="123456",
            challenge=SimpleNamespace(created_at=timezone.now()),
        )

    monkeypatch.setattr(account_views, "issue_otp", fake_issue_otp)
    response = client.post(reverse("platform_admin:login"), {
        "step": "phone", "phone": "09111110004",
    })
    assert response.status_code == 302
    assert response.url == reverse("accounts:verify")
    assert client.session["auth_phone"] == "+989111110004"
    assert client.session["auth_purpose"] == OTPChallenge.Purpose.LOGIN
    assert client.session.get("auth_flow") == "platform"


@pytest.mark.django_db
def test_platform_operator_end_to_end_otp_login(client, settings):
    from django.core.management import call_command

    settings.DEBUG = True
    call_command(
        "ensure_superuser",
        "--phone",
        "09357930033",
        "--name",
        "مدیر پلتفرم",
        "--local-otp-only",
    )
    user = User.objects.get(phone="+989357930033")
    assert user.is_active and user.is_staff and user.is_superuser

    response = client.post(
        reverse("platform_admin:login"),
        {"step": "phone", "phone": "09357930033"},
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:verify")
    assert client.session.get("auth_flow") == "platform"
    code = client.session.get("dev_otp_code")
    assert code and len(code) == 6

    verify = client.post(reverse("accounts:verify"), {"code": code}, follow=True)
    assert verify.status_code == 200
    assert client.session.get("_auth_user_id")
    assert client.get(reverse("platform_admin:overview")).status_code == 200
