from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import OTPChallenge
from apps.accounts.services import otp as otp_service
from apps.accounts.services.otp import OTPInvalid, issue_otp, verify_otp
from apps.accounts.sms import DevSMSProvider
from apps.appointments.models import Appointment, PublicBookingPhoneVerification
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile, StaffWorkHours


@pytest.fixture
def public_booking_setup(salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="pub-book")
    service = Service.objects.create(
        salon=salon,
        category=cat,
        name="مانیکور",
        duration_minutes=30,
        price_toman=200_000,
        is_public=True,
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "نیلوفر", "is_active": True, "is_bookable": True},
    )
    staff.services.add(service)
    day = timezone.localdate() + timedelta(days=21)
    weekday = (day.weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(9, 0), "end_time": time(18, 0)},
    )
    start = timezone.make_aware(
        datetime.combine(day, time(10, 0)),
        timezone.get_current_timezone(),
    )
    return {
        "service": service,
        "staff": staff,
        "day": day,
        "start_iso": start.isoformat(),
        "phone": "+989121000123",
        "phone_input": "09121000123",
        "name": "سارا رزرو",
    }


def _seed_booking_session(client, salon, data):
    session = client.session
    session["booking"] = {
        "salon_id": str(salon.id),
        "service_id": data["service"].pk,
        "staff_id": data["staff"].pk,
        "start_iso": data["start_iso"],
        "name": data["name"],
        "phone": data["phone"],
    }
    session.save()


@pytest.fixture
def capture_otp(monkeypatch):
    captured = {}

    class CapturingProvider(DevSMSProvider):
        def send_otp(self, phone, code, purpose):
            captured["code"] = code
            captured["phone"] = phone

    monkeypatch.setattr(otp_service, "get_sms_provider", lambda: CapturingProvider())
    return captured


@pytest.mark.django_db
def test_otp_failed_attempts_persist_and_block_after_max(settings, monkeypatch, capture_otp):
    settings.BEAUTYOS_OTP_MAX_ATTEMPTS = 5
    phone = "+989121111555"
    issue_otp(phone=phone, purpose=OTPChallenge.Purpose.BOOKING_VERIFY)
    challenge = OTPChallenge.objects.filter(phone=phone).latest("created_at")

    for _ in range(4):
        with pytest.raises(OTPInvalid):
            verify_otp(phone=phone, purpose=OTPChallenge.Purpose.BOOKING_VERIFY, code="000000")
    challenge.refresh_from_db()
    assert challenge.attempts == 4

    issue_otp(phone=phone, purpose=OTPChallenge.Purpose.BOOKING_VERIFY)
    challenge = OTPChallenge.objects.filter(phone=phone, consumed_at__isnull=True).latest("created_at")
    assert challenge.attempts == 4

    with pytest.raises(OTPInvalid):
        verify_otp(phone=phone, purpose=OTPChallenge.Purpose.BOOKING_VERIFY, code="000000")
    challenge.refresh_from_db()
    assert challenge.attempts == 5
    assert challenge.consumed_at is None

    with pytest.raises(OTPInvalid, match="تعداد تلاش"):
        verify_otp(phone=phone, purpose=OTPChallenge.Purpose.BOOKING_VERIFY, code=capture_otp["code"])


@pytest.mark.django_db
def test_contact_redirects_to_verify_and_preserves_booking(client, salon, public_booking_setup, capture_otp):
    data = public_booking_setup
    _seed_booking_session(client, salon, data)
    slug = salon.slug
    url = reverse("salons_public:booking_contact", kwargs={"slug": slug})
    resp = client.post(
        url,
        {"full_name": data["name"], "phone": data["phone_input"]},
        follow=False,
    )
    assert resp.status_code == 302
    assert resp.url == reverse("salons_public:booking_verify", kwargs={"slug": slug})
    booking = client.session.get("booking") or {}
    assert booking.get("service_id") == data["service"].pk
    assert booking.get("staff_id") == data["staff"].pk
    assert booking.get("start_iso") == data["start_iso"]


@pytest.mark.django_db
def test_successful_booking_after_verify(client, salon, public_booking_setup, capture_otp):
    data = public_booking_setup
    _seed_booking_session(client, salon, data)
    slug = salon.slug

    client.post(
        reverse("salons_public:booking_contact", kwargs={"slug": slug}),
        {"full_name": data["name"], "phone": data["phone_input"]},
    )
    verify_url = reverse("salons_public:booking_verify", kwargs={"slug": slug})
    resp = client.post(verify_url, {"code": capture_otp["code"]}, follow=False)
    assert resp.status_code == 302
    assert resp.url == reverse("salons_public:booking_confirm", kwargs={"slug": slug})

    booking = client.session.get("booking") or {}
    assert booking.get("phone_verification_id")

    confirm_url = reverse("salons_public:booking_confirm", kwargs={"slug": slug})
    resp = client.post(confirm_url, follow=False)
    assert resp.status_code == 200
    assert Appointment.objects.filter(salon=salon, source=Appointment.Source.PUBLIC).count() == 1
    verification = PublicBookingPhoneVerification.objects.get(pk=booking["phone_verification_id"])
    assert verification.consumed_at is not None


@pytest.mark.django_db
def test_direct_confirm_post_rejected_without_verify(client, salon, public_booking_setup):
    data = public_booking_setup
    _seed_booking_session(client, salon, data)
    slug = salon.slug
    confirm_url = reverse("salons_public:booking_confirm", kwargs={"slug": slug})
    get_resp = client.get(confirm_url, follow=False)
    assert get_resp.status_code == 302
    assert reverse("salons_public:booking_verify", kwargs={"slug": slug}) in get_resp.url

    post_resp = client.post(confirm_url, follow=False)
    assert post_resp.status_code == 302
    assert Appointment.objects.filter(salon=salon, source=Appointment.Source.PUBLIC).count() == 0


@pytest.mark.django_db
def test_confirm_consumes_verification_once(client, salon, public_booking_setup, capture_otp):
    data = public_booking_setup
    _seed_booking_session(client, salon, data)
    slug = salon.slug
    client.post(
        reverse("salons_public:booking_contact", kwargs={"slug": slug}),
        {"full_name": data["name"], "phone": data["phone_input"]},
    )
    client.post(reverse("salons_public:booking_verify", kwargs={"slug": slug}), {"code": capture_otp["code"]})
    confirm_url = reverse("salons_public:booking_confirm", kwargs={"slug": slug})
    client.post(confirm_url)
    second = client.post(confirm_url, follow=False)
    assert second.status_code == 302
    assert Appointment.objects.filter(salon=salon, source=Appointment.Source.PUBLIC).count() == 1


@pytest.mark.django_db
def test_changing_phone_invalidates_prior_verification(client, salon, public_booking_setup, capture_otp):
    data = public_booking_setup
    _seed_booking_session(client, salon, data)
    slug = salon.slug
    contact = reverse("salons_public:booking_contact", kwargs={"slug": slug})
    verify = reverse("salons_public:booking_verify", kwargs={"slug": slug})

    client.post(contact, {"full_name": data["name"], "phone": data["phone_input"]})
    code_one = capture_otp["code"]
    client.post(verify, {"code": code_one})
    vid_one = client.session["booking"]["phone_verification_id"]

    client.post(contact, {"full_name": data["name"], "phone": "09129998877"})
    code_two = capture_otp["code"]
    client.post(verify, {"code": code_two})

    old = PublicBookingPhoneVerification.objects.get(pk=vid_one)
    assert old.expires_at <= timezone.now()

    confirm_url = reverse("salons_public:booking_confirm", kwargs={"slug": slug})
    client.post(confirm_url)
    assert Appointment.objects.filter(salon=salon, customer__phone="+989129998877").exists()