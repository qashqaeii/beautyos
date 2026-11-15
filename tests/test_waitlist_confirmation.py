from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.appointments.services.confirmation import pending_confirmation_queue
from apps.customers.models import Customer
from apps.dashboard.role_services import get_reception_context
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile


def _pending_appt(salon, owner_membership, customer, *, offset_hours, name_suffix=""):
    cat = ServiceCategory.objects.create(salon=salon, name=f"wc-{name_suffix}-{offset_hours}")
    service = Service.objects.create(
        salon=salon, category=cat, name=f"خدمت {name_suffix}", duration_minutes=30, price_toman=100_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص", "is_bookable": True},
    )
    start = timezone.now() + timedelta(hours=offset_hours)
    return Appointment.objects.create(
        salon=salon,
        customer=customer,
        staff=staff,
        service=service,
        start_at=start,
        end_at=start + timedelta(minutes=30),
        status=Appointment.Status.PENDING,
        price_toman=100_000,
    )


@pytest.mark.django_db
def test_waitlist_confirm_second_row_renumbers(client, salon, owner_membership):
    customers = [
        Customer.objects.create(salon=salon, full_name="مشتری الف", phone="+98912111001"),
        Customer.objects.create(salon=salon, full_name="مشتری ب", phone="+98912111002"),
        Customer.objects.create(salon=salon, full_name="مشتری ج", phone="+98912111003"),
    ]
    appts = [
        _pending_appt(salon, owner_membership, customers[0], offset_hours=10, name_suffix="a"),
        _pending_appt(salon, owner_membership, customers[1], offset_hours=20, name_suffix="b"),
        _pending_appt(salon, owner_membership, customers[2], offset_hours=30, name_suffix="c"),
    ]
    middle = appts[1]
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    html_before = client.get(reverse("waitlist:queue")).content.decode()
    assert html_before.count("waitlist-confirm-form") == 3
    assert "۳ نوبت در انتظار تأیید" in html_before

    resp = client.post(reverse("waitlist:confirm", kwargs={"pk": middle.pk}), follow=True)
    assert resp.status_code == 200
    middle.refresh_from_db()
    assert middle.status == Appointment.Status.CONFIRMED

    remaining = list(pending_confirmation_queue(salon))
    assert len(remaining) == 2
    html_after = resp.content.decode()
    assert html_after.count('data-row="۱"') == 1
    assert html_after.count('data-row="۲"') == 1
    assert "نوبت تأیید شد" in html_after

    middle.refresh_from_db()
    assert Appointment.scoped(salon).filter(status=Appointment.Status.CONFIRMED, pk=middle.pk).exists()

    day = timezone.localdate()
    ctx = get_reception_context(salon, day, Appointment.scoped(salon).all())
    assert len(ctx["pending_confirm"]) == 2

    cal = client.get(
        reverse("appointments:calendar"),
        {"day": timezone.localtime(middle.start_at).date().isoformat()},
    )
    assert cal.status_code == 200
    assert middle.customer.full_name in cal.content.decode()
