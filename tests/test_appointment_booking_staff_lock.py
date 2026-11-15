import pytest
from django import forms

from apps.appointments.booking import appointment_booking_form, resolve_booking_locked_staff
from apps.appointments.forms import AppointmentForm
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile


def _login_client(client, salon, user):
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()


@pytest.mark.django_db
def test_resolve_locked_staff_valid(salon, owner_membership, rf):
    cat = ServiceCategory.objects.create(salon=salon, name="c")
    svc = Service.objects.create(
        salon=salon, category=cat, name="S", duration_minutes=30, price_toman=100_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "قفل‌شده", "is_active": True, "is_bookable": True},
    )
    staff.services.add(svc)
    req = rf.get(f"/appointments/new/?staff={staff.pk}")
    req.salon = salon
    req.membership = owner_membership
    locked = resolve_booking_locked_staff(req, salon)
    assert locked and locked.pk == staff.pk


@pytest.mark.django_db
def test_locked_form_only_offers_staff_services(salon, owner_membership, rf):
    cat = ServiceCategory.objects.create(salon=salon, name="c")
    svc_a = Service.objects.create(
        salon=salon, category=cat, name="A", duration_minutes=30, price_toman=100_000
    )
    svc_b = Service.objects.create(
        salon=salon, category=cat, name="B", duration_minutes=30, price_toman=100_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "تست", "is_active": True, "is_bookable": True},
    )
    staff.services.add(svc_a)
    req = rf.get(f"/appointments/new/?staff={staff.pk}")
    req.salon = salon
    req.membership = owner_membership
    form = appointment_booking_form(req)
    service_ids = list(form.fields["service"].queryset.values_list("pk", flat=True))
    assert service_ids == [svc_a.pk]
    assert svc_b.pk not in service_ids
    assert isinstance(form.fields["staff"].widget, forms.HiddenInput)


@pytest.mark.django_db
def test_booking_page_hides_staff_field(client, salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="c")
    svc = Service.objects.create(
        salon=salon, category=cat, name="S", duration_minutes=30, price_toman=100_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "آلفا", "is_active": True, "is_bookable": True},
    )
    staff.services.add(svc)
    _login_client(client, salon, owner_membership.user)
    resp = client.get(f"/appointments/new/?staff={staff.pk}", HTTP_HOST="127.0.0.1:8000")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "خدمت و متخصص" not in html
    assert 'name="booking_staff_locked"' in html
    assert "appt-booking-fields--staff-locked" in html
    assert 'for="id_staff"' not in html


@pytest.mark.django_db
def test_general_booking_shows_staff_field(client, salon, owner_membership):
    _login_client(client, salon, owner_membership.user)
    resp = client.get("/appointments/new/", HTTP_HOST="127.0.0.1:8000")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "خدمت و متخصص" in html
    assert 'booking_staff_locked' not in html