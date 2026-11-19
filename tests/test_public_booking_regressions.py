"""Public booking GET side effects and final-step staff/service revalidation."""

import pytest
from django.urls import reverse

from apps.accounts.services import otp as otp_service
from apps.accounts.sms import DevSMSProvider
from apps.customers.models import Customer
from tests.test_public_booking_flow import public_booking_setup  # noqa: F401 — pytest fixture


@pytest.fixture
def capture_otp(monkeypatch):
    captured = {}

    class CapturingProvider(DevSMSProvider):
        def send_otp(self, phone, code, purpose):
            captured["code"] = code

    monkeypatch.setattr(otp_service, "get_sms_provider", lambda: CapturingProvider())
    return captured


def _seed(client, salon, data):
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


@pytest.mark.django_db
def test_confirm_get_does_not_create_customer(client, salon, public_booking_setup, capture_otp):
    data = public_booking_setup
    _seed(client, salon, data)
    slug = salon.slug
    client.post(
        reverse("salons_public:booking_contact", kwargs={"slug": slug}),
        {"full_name": data["name"], "phone": data["phone_input"]},
    )
    client.post(
        reverse("salons_public:booking_verify", kwargs={"slug": slug}),
        {"code": capture_otp["code"]},
    )
    before = Customer.scoped(salon).count()
    resp = client.get(reverse("salons_public:booking_confirm", kwargs={"slug": slug}))
    assert resp.status_code == 200
    assert Customer.scoped(salon).count() == before


@pytest.mark.django_db
def test_confirm_rejected_when_staff_loses_service(
    client, salon, public_booking_setup, capture_otp
):
    data = public_booking_setup
    _seed(client, salon, data)
    slug = salon.slug
    client.post(
        reverse("salons_public:booking_contact", kwargs={"slug": slug}),
        {"full_name": data["name"], "phone": data["phone_input"]},
    )
    client.post(
        reverse("salons_public:booking_verify", kwargs={"slug": slug}),
        {"code": capture_otp["code"]},
    )
    data["staff"].services.clear()
    resp = client.post(reverse("salons_public:booking_confirm", kwargs={"slug": slug}))
    body = resp.content.decode()
    assert resp.status_code == 200
    assert "ارائه نمی‌دهد" in body or "قابل رزرو نیست" in body

@pytest.mark.django_db
def test_public_booking_invalid_day_and_slot_are_safe(client, salon, public_booking_setup):
    data = public_booking_setup
    session = client.session
    session["booking"] = {"salon_id":str(salon.pk),"service_id":data["service"].pk,"staff_id":data["staff"].pk}
    session.save()
    response = client.get(reverse("salons_public:booking_datetime", kwargs={"slug": salon.slug}), {"day": "bad-date"})
    assert response.status_code == 200
    response = client.post(reverse("salons_public:booking_pick_slot", kwargs={"slug": salon.slug}), {"start_iso": "not-a-date"})
    assert response.status_code == 302
    assert "/datetime/" in response.url
