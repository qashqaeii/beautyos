"""Public auth pages use shared public_auth layout and design tokens."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_login_page_uses_public_auth_shell(client):
    html = client.get(reverse("accounts:login")).content.decode()
    assert "public-auth-shell" in html
    assert "public-auth-steps" in html
    assert "public-auth-card" in html
    assert "btn-primary" in html
    assert "input-field" in html
    assert 'data-theme="luna_signature"' in html


@pytest.mark.django_db
def test_register_page_uses_public_auth_shell(client):
    html = client.get(reverse("accounts:register")).content.decode()
    assert "public-auth-shell" in html
    assert "ثبت‌نام سالن جدید" in html
    assert "input-field--tel" in html


@pytest.mark.django_db
def test_verify_page_login_steps(client, settings):
    settings.DEBUG = True
    phone = "09121112233"
    client.post(reverse("accounts:login"), {"step": "phone", "phone": phone})
    html = client.get(reverse("accounts:verify")).content.decode()
    assert "public-auth-shell" in html
    assert "کد ورود" in html
    assert "۱. شماره موبایل" in html


@pytest.mark.django_db
def test_verify_page_register_steps(client, settings):
    settings.DEBUG = True
    phone = "09129998844"
    client.post(reverse("accounts:register"), {"phone": phone})
    html = client.get(reverse("accounts:verify")).content.decode()
    assert "اطلاعات مالک" in html
    assert "تکمیل ثبت‌نام" in html


@pytest.mark.django_db
def test_register_profile_page_shell(client, settings, monkeypatch):
    from apps.accounts.services import otp as otp_service
    from apps.accounts.sms import DevSMSProvider

    captured = {}

    class Cap(DevSMSProvider):
        def send_otp(self, phone, code, purpose):
            captured["code"] = code

    monkeypatch.setattr(otp_service, "get_sms_provider", lambda: Cap())
    settings.DEBUG = True
    phone = "09128887766"
    client.post(reverse("accounts:register"), {"phone": phone})
    response = client.post(reverse("accounts:verify"), {"code": captured["code"]})
    html = response.content.decode()
    assert response.status_code == 200
    assert "public-auth-shell" in html
    assert "اطلاعات مالک سالن" in html