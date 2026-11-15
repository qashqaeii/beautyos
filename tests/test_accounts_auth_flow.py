import pytest
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_login_phone_step_redirects_verify(client, settings, monkeypatch):
    settings.DEBUG = True
    phone = "+989121111111"
    response = client.post(reverse("accounts:login"), {"step": "phone", "phone": "09121111111"})
    assert response.status_code == 302
    assert response.url == reverse("accounts:verify")
    verify = client.get(response.url)
    assert verify.status_code == 200
    assert "دریافت کد" not in verify.content.decode() or "کد ورود" in verify.content.decode()


@pytest.mark.django_db
def test_register_new_user_otp_to_profile(client, settings, monkeypatch):
    settings.DEBUG = True
    phone = "09122223333"
    client.post(reverse("accounts:register"), {"phone": phone})
    verify_get = client.get(reverse("accounts:verify"))
    dev = client.session.get("dev_otp_code")
    assert dev
    client.post(reverse("accounts:verify"), {"code": dev})
    assert client.session.get("register_verification_id")
    client.post(reverse("accounts:register_profile"), {"full_name": "مالک تست"})
    assert User.objects.filter(phone__contains="9122223333").exists()
    response = client.get(reverse("salons_onboarding:create"))
    assert response.status_code in (200, 302)


@pytest.mark.django_db
def test_logout_get_does_not_end_session(client, owner_membership):
    client.force_login(owner_membership.user)
    client.get(reverse("accounts:logout"))
    assert client.get("/app/").status_code == 200