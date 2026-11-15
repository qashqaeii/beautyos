import json
from datetime import time, timedelta
from urllib.parse import quote

import pytest
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile, StaffWorkHours


def _appt_post_fields(start, staff, service, **extra):
    local = timezone.localtime(start)
    base = {
        "staff": staff.pk,
        "service": service.pk,
        "appointment_date": local.date().isoformat(),
        "appointment_time": local.strftime("%H:%M"),
        "notes": "",
        "status": Appointment.Status.CONFIRMED,
    }
    base.update(extra)
    return base


@pytest.mark.django_db
def test_customer_search_api(client, salon, owner_membership):
    Customer.objects.create(salon=salon, full_name="علی رضایی", phone="+989121111101")
    Customer.objects.create(salon=salon, full_name="علی کریمی", phone="+989121111102")
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    resp = client.get("/customers/search/", {"q": "علی"})
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert len(data["results"]) == 2
    assert all("phone_display" in row for row in data["results"])


@pytest.mark.django_db
def test_appointment_form_prefills_customer_from_profile_link(client, salon, owner_membership):
    customer = Customer.objects.create(salon=salon, full_name="سارا", phone="+989121111103")
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    resp = client.get(f"/appointments/new/?customer={customer.pk}", follow=True)
    html = resp.content.decode()
    assert customer.full_name in html
    assert "appointment_date" in html
    assert "رزرو نوبت" in html
    assert "customer-detail-booking-lock" in html


@pytest.mark.django_db
def test_appointment_customer_fields_visible_with_day_query(client, salon, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    html = client.get("/appointments/new/?day=2026-11-13").content.decode()
    assert '"initialMode": "new"' in html
    assert 'class="appt-customer-picker__new-fields"' in html
    assert 'id="id_new_customer_first_name"' in html
    assert "انتخاب مشتری موجود" in html


@pytest.mark.django_db
def test_appointment_form_shows_three_customer_fields_by_default(client, salon, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    html = client.get("/appointments/new/").content.decode()
    assert 'id="id_new_customer_first_name"' in html
    assert 'id="id_new_customer_last_name"' in html
    assert 'id="id_new_customer_phone"' in html
    assert "انتخاب مشتری موجود" in html


@pytest.mark.django_db
def test_appointment_prefill_from_start_query(client, salon, owner_membership):
    start = timezone.localtime(timezone.now() + timedelta(days=2)).replace(
        hour=14, minute=30, second=0, microsecond=0
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    html = client.get(f"/appointments/new/?start={quote(start.isoformat(), safe='')}").content.decode()
    assert "14:30" in html or "۱۴:۳۰" in html


@pytest.mark.django_db
def test_appointment_new_customer_not_saved_on_scheduling_error(client, salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="c")
    service = Service.objects.create(
        salon=salon, category=cat, name="svc", duration_minutes=60, price_toman=100_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص", "is_bookable": True},
    )
    staff.services.add(service)
    existing = Customer.objects.create(salon=salon, full_name="قدیمی", phone="+989121111104")
    start = timezone.localtime(timezone.now() + timedelta(days=2)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    weekday = (start.date().weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(8, 0), "end_time": time(22, 0)},
    )
    from apps.appointments.services.scheduling import create_appointment

    create_appointment(
        salon=salon,
        customer=existing,
        staff=staff,
        service=service,
        start=start,
        actor=owner_membership.user,
    )
    before_count = Customer.objects.filter(salon=salon).count()
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    fields = _appt_post_fields(
        start,
        staff,
        service,
        customer_search="",
        new_customer_mode="on",
        new_customer_first_name="مشتری",
        new_customer_last_name="تازه",
        new_customer_phone="09121111005",
    )
    resp = client.post("/appointments/new/", fields)
    assert resp.status_code == 200
    assert Customer.objects.filter(salon=salon).count() == before_count


@pytest.mark.django_db
def test_appointment_select_existing_customer_and_book(client, salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="c2")
    service = Service.objects.create(
        salon=salon, category=cat, name="svc2", duration_minutes=30, price_toman=80_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص۲", "is_bookable": True},
    )
    staff.services.add(service)
    customer = Customer.objects.create(salon=salon, full_name="نازنین", phone="+989121111106")
    start = timezone.localtime(timezone.now() + timedelta(days=3)).replace(
        hour=11, minute=0, second=0, microsecond=0
    )
    weekday = (start.date().weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(8, 0), "end_time": time(22, 0)},
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    fields = _appt_post_fields(
        start,
        staff,
        service,
        customer=customer.pk,
        customer_search=f"{customer.full_name} · 09121111106",
    )
    resp = client.post("/appointments/new/", fields, follow=True)
    assert resp.status_code == 200
    assert Appointment.objects.filter(customer=customer, staff=staff).exists()


@pytest.mark.django_db
def test_appointment_new_customer_duplicate_phone_uses_existing(client, salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="c3")
    service = Service.objects.create(
        salon=salon, category=cat, name="svc3", duration_minutes=30, price_toman=50_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص۳", "is_bookable": True},
    )
    staff.services.add(service)
    customer = Customer.objects.create(salon=salon, full_name="پوریا", phone="+989121111107")
    start = timezone.localtime(timezone.now() + timedelta(days=4)).replace(
        hour=9, minute=30, second=0, microsecond=0
    )
    weekday = (start.date().weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(8, 0), "end_time": time(22, 0)},
    )
    before = Customer.objects.filter(salon=salon).count()
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    fields = _appt_post_fields(
        start,
        staff,
        service,
        new_customer_mode="on",
        new_customer_first_name="نام",
        new_customer_last_name="دیگر",
        new_customer_phone="09121111107",
    )
    resp = client.post("/appointments/new/", fields, follow=True)
    assert resp.status_code == 200
    assert Customer.objects.filter(salon=salon).count() == before
    assert Appointment.objects.filter(customer=customer).exists()


@pytest.mark.django_db
def test_appointment_new_customer_three_fields_create(client, salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="c4")
    service = Service.objects.create(
        salon=salon, category=cat, name="svc4", duration_minutes=30, price_toman=50_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص۴", "is_bookable": True},
    )
    staff.services.add(service)
    start = timezone.localtime(timezone.now() + timedelta(days=5)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    weekday = (start.date().weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(8, 0), "end_time": time(22, 0)},
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    fields = _appt_post_fields(
        start,
        staff,
        service,
        new_customer_mode="on",
        new_customer_first_name="مینا",
        new_customer_last_name="احمدی",
        new_customer_phone="09121111088",
    )
    resp = client.post("/appointments/new/", fields, follow=True)
    assert resp.status_code == 200
    assert Customer.objects.filter(salon=salon, phone="+989121111088").exists()
    assert Appointment.objects.filter(customer__full_name="مینا احمدی").exists()


@pytest.mark.django_db
def test_internal_booking_post_renders_after_scheduling_error_without_typeerror(
    client, salon, owner_membership
):
    """Regression: picker_context used any(a,b,c) causing 500 on invalid POST re-render."""
    cat = ServiceCategory.objects.create(salon=salon, name="reg-cat")
    service = Service.objects.create(
        salon=salon, category=cat, name="خدمت", duration_minutes=60, price_toman=200_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص", "is_bookable": True},
    )
    staff.services.add(service)
    existing = Customer.objects.create(salon=salon, full_name="اشغال", phone="+989121111199")
    start = timezone.localtime(timezone.now() + timedelta(days=6)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    weekday = (start.date().weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(8, 0), "end_time": time(22, 0)},
    )
    from apps.appointments.services.scheduling import create_appointment

    create_appointment(
        salon=salon,
        customer=existing,
        staff=staff,
        service=service,
        start=start,
        actor=owner_membership.user,
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    fields = _appt_post_fields(
        start,
        staff,
        service,
        new_customer_first_name="مشتری",
        new_customer_last_name="جدید",
        new_customer_phone="09121111888",
    )
    resp = client.post("/appointments/new/", fields)
    assert resp.status_code == 200
    assert "تداخل" in resp.content.decode() or "non_field_errors" in resp.content.decode()


@pytest.mark.django_db
def test_internal_booking_post_success_with_deposit(client, salon, owner_membership):
    from apps.finance.models import Payment

    cat = ServiceCategory.objects.create(salon=salon, name="dep-cat")
    service = Service.objects.create(
        salon=salon, category=cat, name="خدمت بیعانه", duration_minutes=30, price_toman=1_000_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص", "is_bookable": True},
    )
    staff.services.add(service)
    customer = Customer.objects.create(salon=salon, full_name="بیعانه", phone="+989121117777")
    start = timezone.localtime(timezone.now() + timedelta(days=7)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    weekday = (start.date().weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(8, 0), "end_time": time(22, 0)},
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    fields = _appt_post_fields(
        start,
        staff,
        service,
        customer=customer.pk,
        customer_search="بیعانه",
        deposit_amount_toman="150000",
        deposit_method=Payment.Method.CASH,
    )
    resp = client.post("/appointments/new/", fields, follow=False)
    assert resp.status_code == 302
    appt = Appointment.objects.get(staff=staff, start_at=start)
    assert appt.customer_id == customer.pk
    assert Payment.scoped(salon).filter(appointment=appt, paid_amount_toman=150_000).exists()
