"""Customer booking self-service regression: OTP, tenant privacy and financial safeguards."""
from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import OTPChallenge, User
from apps.accounts.services import otp as otp_service
from apps.accounts.sms import DevSMSProvider
from apps.appointments.customer_portal import (
    ACCESS_SESSION_KEY, grant_customer_access,
)
from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.finance.models import Payment
from apps.salons.models import Salon
from tests.test_public_booking_flow import public_booking_setup  # noqa: F401


@pytest.fixture
def customer_otp(monkeypatch):
    issued = {}

    class CapturingProvider(DevSMSProvider):
        def send_otp(self, phone, code, purpose):
            issued["phone"], issued["code"], issued["purpose"] = phone, code, purpose

    monkeypatch.setattr(otp_service, "get_sms_provider", lambda: CapturingProvider())
    return issued


def url(salon, name, **kwargs):
    return reverse("salons_public:" + name, kwargs={"slug": salon.slug, **kwargs})


def portal_login(client, salon, phone, customer_otp):
    response = client.post(url(salon, "customer_login"), {"phone": phone})
    assert response.status_code == 302
    assert response.url == url(salon, "customer_verify")
    assert customer_otp["purpose"] == OTPChallenge.Purpose.CUSTOMER_PORTAL
    verified = client.post(url(salon, "customer_verify"), {"code": customer_otp["code"]})
    assert verified.status_code == 302
    assert verified.url == url(salon, "customer_home")


@pytest.fixture
def booked_customer(salon, public_booking_setup):
    data = public_booking_setup
    customer = Customer.objects.create(
        salon=salon, full_name="سارا نمونه", phone=data["phone"],
    )
    appointment = Appointment.objects.create(
        salon=salon, customer=customer, staff=data["staff"],
        service=data["service"],
        start_at=datetime.fromisoformat(data["start_iso"]),
        end_at=datetime.fromisoformat(data["start_iso"]) + timedelta(minutes=30),
        source=Appointment.Source.PUBLIC,
        status=Appointment.Status.CONFIRMED, price_toman=200_000,
    )
    return customer, appointment


@pytest.mark.django_db
def test_customer_portal_requires_otp_and_is_distinct_from_salon_auth(
    client, salon, booked_customer, customer_otp
):
    customer, appointment = booked_customer
    assert client.get(url(salon, "customer_home")).status_code == 302
    assert client.get(url(salon, "customer_appointment", appointment_id=appointment.pk)).status_code == 302
    assert client.post(url(salon, "customer_cancel", appointment_id=appointment.pk)).status_code == 403
    assert not client.session.get(ACCESS_SESSION_KEY)
    portal_login(client, salon, customer.phone, customer_otp)
    assert client.get(url(salon, "customer_home")).status_code == 200
    detail = client.get(url(salon, "customer_appointment", appointment_id=appointment.pk))
    assert detail.status_code == 200
    assert appointment.tracking_code in detail.content.decode()
    assert not client.session.get("_auth_user_id")
    assert detail["Cache-Control"].find("no-store") >= 0
    assert client.post(url(salon, "customer_logout")).status_code == 302
    assert client.get(url(salon, "customer_home")).status_code == 302


@pytest.mark.django_db
def test_portal_never_discloses_whether_a_customer_exists_and_creates_no_account(
    client, salon, customer_otp
):
    count_customer, count_user = Customer.objects.count(), User.objects.count()
    portal_login(client, salon, "09121234567", customer_otp)
    response = client.get(url(salon, "customer_home"))
    assert response.status_code == 200
    assert "نوبت آینده‌ای ندارید" in response.content.decode()
    assert Customer.objects.count() == count_customer
    assert User.objects.count() == count_user


@pytest.mark.django_db
def test_customer_otp_resend_and_failed_code_do_not_grant_access(
    client, salon, customer_otp
):
    client.post(url(salon, "customer_login"), {"phone": "09121234567"})
    bad = client.post(url(salon, "customer_verify"), {"code": "000000"})
    assert bad.status_code == 200
    assert not client.session.get(ACCESS_SESSION_KEY)
    sent = client.post(url(salon, "customer_verify"), {"action": "resend"})
    assert sent.status_code == 302
    assert client.post(url(salon, "customer_verify"), {"code": customer_otp["code"]}).status_code == 302
    assert client.session.get(ACCESS_SESSION_KEY)


@pytest.mark.django_db
def test_expired_portal_session_cannot_be_used(client, salon, booked_customer):
    customer, appointment = booked_customer
    session = client.session
    session[ACCESS_SESSION_KEY] = {
        "salon_id": str(salon.pk), "phone": customer.phone,
        "verified_at": int((timezone.now() - timedelta(days=2)).timestamp()),
    }
    session.save()
    assert client.get(url(salon, "customer_home")).status_code == 302
    assert client.post(url(salon, "customer_cancel", appointment_id=appointment.pk)).status_code == 403
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED


@pytest.mark.django_db
def test_portal_is_strictly_tenant_and_phone_scoped(
    client, salon, salon_b, booked_customer, customer_otp
):
    customer, appointment = booked_customer
    second_customer = Customer.objects.create(
        salon=salon, phone="+989121111222", full_name="مراجع دیگر",
    )
    private = Appointment.objects.create(
        salon=salon, customer=second_customer,
        staff=appointment.staff, service=appointment.service,
        start_at=appointment.start_at + timedelta(days=1),
        end_at=appointment.end_at + timedelta(days=1),
        status=Appointment.Status.CONFIRMED, source=Appointment.Source.PUBLIC,
    )
    portal_login(client, salon, customer.phone, customer_otp)
    assert client.get(url(salon, "customer_appointment", appointment_id=private.pk)).status_code == 404
    assert client.post(url(salon, "customer_cancel", appointment_id=private.pk)).status_code == 404
    assert client.get(url(salon_b, "customer_home")).status_code == 302
    assert client.post(url(salon_b, "customer_cancel", appointment_id=appointment.pk)).status_code == 403


@pytest.mark.django_db
def test_customer_can_cancel_unpaid_public_booking(client, salon, booked_customer, customer_otp):
    customer, appointment = booked_customer
    portal_login(client, salon, customer.phone, customer_otp)
    get_response = client.get(url(salon, "customer_cancel", appointment_id=appointment.pk))
    assert get_response.status_code == 405
    response = client.post(url(salon, "customer_cancel", appointment_id=appointment.pk))
    assert response.status_code == 302
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CANCELLED
    assert appointment.cancelled_at is not None
    again = client.post(url(salon, "customer_cancel", appointment_id=appointment.pk))
    assert again.status_code == 302
    assert Appointment.objects.filter(pk=appointment.pk, status=Appointment.Status.CANCELLED).count() == 1


@pytest.mark.django_db
def test_paid_or_internal_booking_cannot_be_canceled_or_moved(
    client, salon, booked_customer, customer_otp
):
    customer, appointment = booked_customer
    portal_login(client, salon, customer.phone, customer_otp)
    Payment.objects.create(
        salon=salon, customer=customer, appointment=appointment,
        total_amount_toman=200_000, paid_amount_toman=60_000,
        status=Payment.Status.PARTIAL,
    )
    canceled = client.post(url(salon, "customer_cancel", appointment_id=appointment.pk))
    assert canceled.status_code == 302
    new_slot = (appointment.start_at + timedelta(hours=2)).isoformat()
    moved = client.post(
        url(salon, "customer_reschedule", appointment_id=appointment.pk),
        {"start_iso": new_slot},
    )
    assert moved.status_code == 302
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED
    original = appointment.start_at
    assert appointment.start_at == original

    Payment.objects.filter(appointment=appointment).delete()
    appointment.source = Appointment.Source.INTERNAL
    appointment.save(update_fields=["source"])
    client.post(url(salon, "customer_cancel", appointment_id=appointment.pk))
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED


@pytest.mark.django_db
def test_customer_reschedules_atomically_and_respects_another_booking(
    client, salon, booked_customer, customer_otp
):
    customer, appointment = booked_customer
    portal_login(client, salon, customer.phone, customer_otp)
    target = appointment.start_at + timedelta(hours=2)
    page = client.get(url(salon, "customer_reschedule", appointment_id=appointment.pk),
                      {"day": target.date().isoformat()})
    assert page.status_code == 200
    assert target.isoformat() in page.content.decode()
    response = client.post(url(salon, "customer_reschedule", appointment_id=appointment.pk),
                           {"start_iso": target.isoformat()})
    assert response.status_code == 302
    appointment.refresh_from_db()
    assert appointment.start_at == target
    assert appointment.status == Appointment.Status.PENDING
    assert appointment.end_at == target + timedelta(minutes=30)

    other = Appointment.objects.create(
        salon=salon, customer=customer, staff=appointment.staff,
        service=appointment.service, start_at=target + timedelta(hours=1),
        end_at=target + timedelta(hours=1, minutes=30),
        source=Appointment.Source.PUBLIC, status=Appointment.Status.CONFIRMED,
    )
    response = client.post(url(salon, "customer_reschedule", appointment_id=appointment.pk),
                           {"start_iso": other.start_at.isoformat()})
    assert response.status_code == 302
    appointment.refresh_from_db()
    assert appointment.start_at == target


@pytest.mark.django_db
def test_notice_window_and_closed_online_booking_are_enforced(
    client, salon, booked_customer, customer_otp
):
    customer, appointment = booked_customer
    portal_login(client, salon, customer.phone, customer_otp)
    appointment.start_at = timezone.now() + timedelta(minutes=30)
    appointment.end_at = appointment.start_at + timedelta(minutes=30)
    appointment.save(update_fields=["start_at", "end_at"])
    client.post(url(salon, "customer_cancel", appointment_id=appointment.pk))
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED
    appointment.start_at += timedelta(days=10)
    appointment.end_at += timedelta(days=10)
    appointment.save(update_fields=["start_at", "end_at"])
    salon.is_accepting_bookings = False
    salon.save(update_fields=["is_accepting_bookings"])
    assert client.get(url(salon, "customer_home")).status_code == 200
    changed = client.post(
        url(salon, "customer_reschedule", appointment_id=appointment.pk),
        {"start_iso": (appointment.start_at + timedelta(hours=1)).isoformat()},
    )
    assert changed.status_code == 302
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED


@pytest.mark.django_db
def test_booking_otp_purpose_is_not_interchangeable_with_portal_otp(
    client, salon, customer_otp
):
    from apps.accounts.services.otp import issue_otp
    booked = issue_otp(
        phone="09121234567", purpose=OTPChallenge.Purpose.BOOKING_VERIFY,
    )
    client.post(url(salon, "customer_login"), {"phone": "09121234567"})
    assert OTPChallenge.objects.get(pk=booked.challenge.pk).consumed_at is None
    assert OTPChallenge.objects.get(pk=booked.challenge.pk).expires_at > timezone.now()
    assert customer_otp["purpose"] == OTPChallenge.Purpose.CUSTOMER_PORTAL
