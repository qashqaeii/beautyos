"""Security regression tests for /accounts register + OTP session binding."""

from __future__ import annotations

import threading

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import OTPChallenge, RegisterPhoneVerification, User
from apps.accounts.services import otp as otp_service
from apps.accounts.sms import DevSMSProvider


class _CapturingSMS(DevSMSProvider):
    last_code: str | None = None

    def send_otp(self, phone, code, purpose):
        _CapturingSMS.last_code = code


def _csrf_client() -> Client:
    return Client(enforce_csrf_checks=True)


def _ensure_csrf_cookie(client: Client) -> None:
    client.get(reverse("accounts:login"))


def _csrf_post(client: Client, url: str, data: dict):
    token = client.cookies.get("csrftoken")
    if token:
        data["csrfmiddlewaretoken"] = token.value
    return client.post(url, data)


@pytest.fixture
def secure_auth_env(settings, monkeypatch):
    settings.DEBUG = False
    _CapturingSMS.last_code = None
    monkeypatch.setattr(otp_service, "get_sms_provider", lambda: _CapturingSMS())
    return settings


def _issue_code(client, url, phone: str, *, login: bool = False) -> str:
    key = "step" if login else None
    payload = {"phone": phone}
    if login:
        payload["step"] = "phone"
    _csrf_post(client, url, payload)
    assert _CapturingSMS.last_code
    return _CapturingSMS.last_code


@pytest.mark.django_db
def test_register_login_session_swap_attack_rejected(secure_auth_env, db):
    """
    A verifies register OTP; same session starts login for existing B without verifying B.
    Profile completion must not attach to B or alter B's data.
    """
    phone_a = "09123334444"
    phone_b = "09124445555"
    phone_b_e164 = "+989124445555"
    victim = User.objects.create_user(phone=phone_b_e164, full_name="قربانی B")

    client = _csrf_client()
    _ensure_csrf_cookie(client)

    _issue_code(client, reverse("accounts:register"), phone_a)
    code_a = _CapturingSMS.last_code
    resp_verify = _csrf_post(client, reverse("accounts:verify"), {"code": code_a})
    assert resp_verify.status_code == 200
    assert client.session.get("register_verification_id")
    assert not client.session.get("register_verified")

    _issue_code(client, reverse("accounts:login"), phone_b, login=True)
    assert client.session.get("auth_phone") == phone_b_e164
    assert client.session.get("auth_purpose") == OTPChallenge.Purpose.LOGIN
    assert client.session.get("register_verification_id") is None

    resp_profile = _csrf_post(
        client,
        reverse("accounts:register_profile"),
        {"full_name": "مهاجم"},
    )
    assert resp_profile.status_code == 302
    assert resp_profile.url == reverse("accounts:register")

    victim.refresh_from_db()
    assert victim.full_name == "قربانی B"
    assert client.session.get("_auth_user_id") is None

    b_login_otp = OTPChallenge.objects.filter(
        phone=phone_b_e164,
        purpose=OTPChallenge.Purpose.LOGIN,
    ).latest("created_at")
    assert b_login_otp.consumed_at is None
    assert not User.objects.filter(phone="+989123334444").exists()


@pytest.mark.django_db
def test_register_profile_requires_server_verification(secure_auth_env, db):
    client = _csrf_client()
    _ensure_csrf_cookie(client)
    client.session["register_verified"] = True
    client.session["auth_phone"] = "+989129998887"
    client.session.save()
    resp = _csrf_post(client, reverse("accounts:register_profile"), {"full_name": "X"})
    assert resp.status_code == 302
    assert resp.url == reverse("accounts:register")
    assert not User.objects.filter(phone="+989129998887").exists()


@pytest.mark.django_db
def test_register_happy_path_csrf(secure_auth_env, db):
    phone = "09125556666"
    phone_e164 = "+989125556666"
    client = _csrf_client()
    _ensure_csrf_cookie(client)
    _issue_code(client, reverse("accounts:register"), phone)
    _csrf_post(client, reverse("accounts:verify"), {"code": _CapturingSMS.last_code})
    vid = client.session.get("register_verification_id")
    assert vid
    resp = _csrf_post(client, reverse("accounts:register_profile"), {"full_name": "مالک جدید"})
    assert resp.status_code == 302
    assert resp.url == reverse("dashboard:home")
    user = User.objects.get(phone=phone_e164)
    assert user.full_name == "مالک جدید"
    from apps.salons.models import SalonMembership
    membership = SalonMembership.objects.select_related("salon__settings").get(user=user)
    assert membership.role == SalonMembership.Role.OWNER
    assert membership.salon.business_type == "beauty_women"
    assert membership.salon.is_accepting_bookings is False
    assert membership.salon.settings.onboarding_completed_at is None
    assert client.get(reverse("dashboard:home")).status_code == 200
    assert RegisterPhoneVerification.objects.get(pk=vid).consumed_at is not None


@pytest.mark.django_db
def test_login_happy_path_csrf(secure_auth_env, owner_membership):
    user = owner_membership.user
    client = _csrf_client()
    _ensure_csrf_cookie(client)
    _issue_code(client, reverse("accounts:login"), user.phone.replace("+98", "0")[:11], login=True)
    resp = _csrf_post(client, reverse("accounts:verify"), {"code": _CapturingSMS.last_code})
    assert resp.status_code == 302
    assert client.session.get("_auth_user_id") == str(user.pk)


@pytest.mark.django_db
def test_register_profile_empty_name_keeps_verification(secure_auth_env, db):
    phone = "09126667777"
    client = _csrf_client()
    _ensure_csrf_cookie(client)
    _issue_code(client, reverse("accounts:register"), phone)
    _csrf_post(client, reverse("accounts:verify"), {"code": _CapturingSMS.last_code})
    vid = client.session["register_verification_id"]
    before = RegisterPhoneVerification.objects.get(pk=vid)
    resp = _csrf_post(client, reverse("accounts:register_profile"), {"full_name": ""})
    assert resp.status_code == 200
    after = RegisterPhoneVerification.objects.get(pk=vid)
    assert after.consumed_at is None
    assert before.pk == after.pk


@pytest.mark.django_db
def test_resend_invalidates_previous_register_code(secure_auth_env, db, monkeypatch):
    from apps.accounts import views as account_views

    monkeypatch.setattr(account_views, "OTP_RESEND_COOLDOWN_SECONDS", 0)
    phone = "09127778888"
    client = _csrf_client()
    _ensure_csrf_cookie(client)
    _issue_code(client, reverse("accounts:register"), phone)
    first_code = _CapturingSMS.last_code
    _csrf_post(client, reverse("accounts:verify"), {"action": "resend"})
    second_code = _CapturingSMS.last_code
    assert second_code
    assert second_code != first_code
    resp = _csrf_post(client, reverse("accounts:verify"), {"code": first_code})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "نادرست" in body or "منقضی" in body or "یافت نشد" in body


@pytest.mark.django_db
def test_expired_register_verification_rejected(secure_auth_env, db):
    phone = "09129990001"
    client = _csrf_client()
    _ensure_csrf_cookie(client)
    _issue_code(client, reverse("accounts:register"), phone)
    _csrf_post(client, reverse("accounts:verify"), {"code": _CapturingSMS.last_code})
    vid = client.session["register_verification_id"]
    RegisterPhoneVerification.objects.filter(pk=vid).update(
        expires_at=timezone.now() - timezone.timedelta(seconds=1)
    )
    resp = _csrf_post(client, reverse("accounts:register_profile"), {"full_name": "دیررس"})
    assert resp.status_code == 302
    assert resp.url == reverse("accounts:register")


@pytest.mark.django_db
def test_register_verification_cannot_be_reused(secure_auth_env, db):
    phone = "09129990002"
    client = _csrf_client()
    _ensure_csrf_cookie(client)
    _issue_code(client, reverse("accounts:register"), phone)
    _csrf_post(client, reverse("accounts:verify"), {"code": _CapturingSMS.last_code})
    first = _csrf_post(client, reverse("accounts:register_profile"), {"full_name": "اول"})
    assert first.status_code == 302
    second = _csrf_post(client, reverse("accounts:register_profile"), {"full_name": "دوم"})
    assert second.status_code == 302
    assert second.url == reverse("accounts:register")


@pytest.mark.django_db
def test_register_profile_when_account_exists_redirects_login(secure_auth_env, db):
    phone_e164 = "+989128889999"
    phone = "09128889999"
    client = _csrf_client()
    _ensure_csrf_cookie(client)
    _issue_code(client, reverse("accounts:register"), phone)
    _csrf_post(client, reverse("accounts:verify"), {"code": _CapturingSMS.last_code})
    User.objects.create_user(phone=phone_e164, full_name="موجود")
    resp = _csrf_post(client, reverse("accounts:register_profile"), {"full_name": "جدید"})
    assert resp.status_code == 302
    assert resp.url == reverse("accounts:login")
    assert User.objects.get(phone=phone_e164).full_name == "موجود"


def _is_postgresql() -> bool:
    return "postgresql" in settings.DATABASES["default"]["ENGINE"]


requires_postgresql = pytest.mark.skipif(
    not _is_postgresql(),
    reason="PostgreSQL required for concurrent register profile test",
)


@pytest.mark.django_db(transaction=True)
@requires_postgresql
def test_concurrent_register_profile_single_user(secure_auth_env, db):
    phone = "09120001122"
    phone_e164 = "+989120001122"
    _CapturingSMS.last_code = None

    setup = _csrf_client()
    _ensure_csrf_cookie(setup)
    _issue_code(setup, reverse("accounts:register"), phone)
    _csrf_post(setup, reverse("accounts:verify"), {"code": _CapturingSMS.last_code})
    session_cookie = setup.cookies["sessionid"].value
    vid = setup.session.get("register_verification_id")

    barrier = threading.Barrier(2)
    results: list[int] = []

    def worker():
        from django.db import connections

        connections.close_all()
        c = _csrf_client()
        c.cookies["sessionid"] = session_cookie
        c.cookies["csrftoken"] = setup.cookies["csrftoken"].value
        barrier.wait(timeout=15)
        r = _csrf_post(c, reverse("accounts:register_profile"), {"full_name": "هم‌زمان"})
        results.append(r.status_code)
        connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert User.objects.filter(phone=phone_e164).count() == 1
    assert RegisterPhoneVerification.objects.get(pk=vid).consumed_at is not None
    assert 302 in results
