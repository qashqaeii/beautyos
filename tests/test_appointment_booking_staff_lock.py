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

@pytest.fixture
def staff_booking_case(client, salon, owner_membership):
    from datetime import time, timedelta

    from django.urls import reverse
    from django.utils import timezone
    from apps.customers.models import Customer
    from apps.staff.models import StaffWorkHours

    category = ServiceCategory.objects.create(salon=salon, name="staff-booking")
    service = Service.objects.create(
        salon=salon, category=category, name="خدمت متخصص",
        duration_minutes=30, price_toman=100_000,
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon, membership=owner_membership,
        defaults={"display_name": "متخصص رزرو", "is_active": True, "is_bookable": True},
    )
    staff.services.add(service)
    customer = Customer.objects.create(salon=salon, full_name="مشتری رزرو", phone="+989121113355")
    day = timezone.localdate() + timedelta(days=2)
    StaffWorkHours.objects.update_or_create(
        salon=salon, staff=staff, weekday=(day.weekday() + 2) % 7,
        defaults={"start_time": time(8), "end_time": time(18), "is_closed": False},
    )
    _login_client(client, salon, owner_membership.user)
    path = reverse("staff:detail", kwargs={"pk": staff.pk})
    payload = {
        "booking_return_path": path,
        "booking_staff_locked": staff.pk,
        "staff": staff.pk,
        "customer": customer.pk,
        "service": service.pk,
        "appointment_date": day.isoformat(),
        "appointment_time": "10:00",
        "status": "confirmed",
    }
    return staff, path, payload


def test_staff_profile_always_renders_booking_and_preserves_edit_form(client, staff_booking_case):
    from apps.staff.forms import StaffProfileForm

    staff, path, _ = staff_booking_case
    response = client.get(path)
    assert response.status_code == 200
    assert not response.context["book_modal_open"]
    assert response.context["booking_staff_locked"] == staff
    assert isinstance(response.context["form"], StaffProfileForm)
    assert isinstance(response.context["appointment_form"], AppointmentForm)
    source = response.content.decode()
    assert 'id="appointment-booking-modal-title"' in source
    assert 'name="booking_staff_locked"' in source
    assert 'id="staff-edit-form"' in source
    assert 'name="display_name"' in source
    assert source.index("appointment-customer-picker.js") < source.index("alpinejs@")
    assert source.index("appointment-deposit-preview.js") < source.index("alpinejs@")
    # A query parameter cannot select a different specialist on this profile.
    response = client.get(path, {"book": "1", "staff": staff.pk + 999, "edit": "1"})
    assert response.status_code == 200
    assert response.context["book_modal_open"]
    assert not response.context["edit_modal_open"]
    assert response.context["booking_staff_locked"] == staff
    assert response.context["appointment_form"].initial["staff"] == staff.pk


def test_staff_booking_success_and_conflict_stay_on_profile(client, staff_booking_case):
    from apps.appointments.models import Appointment
    from apps.staff.forms import StaffProfileForm

    staff, path, payload = staff_booking_case
    first = client.post("/appointments/new/", payload)
    assert first.status_code == 302
    assert first.url == path
    assert Appointment.objects.filter(staff=staff, customer_id=payload["customer"]).count() == 1
    # Retry the same occupied slot: keep the bound booking and independent edit form.
    failed = client.post("/appointments/new/", payload)
    assert failed.status_code == 200
    assert failed.context["book_modal_open"]
    assert failed.context["booking_return_path"] == path
    assert failed.context["booking_staff_locked"] == staff
    assert isinstance(failed.context["form"], StaffProfileForm)
    assert failed.context["appointment_form"].is_bound
    assert "تداخل" in failed.content.decode()
    assert Appointment.objects.filter(staff=staff).count() == 1
    # Correcting the time on that same returned form should succeed.
    retry = client.post("/appointments/new/", {**payload, "appointment_time": "11:00",
        "booking_return_path": failed.context["booking_return_path"]})
    assert retry.status_code == 302
    assert retry.url == path
    assert Appointment.objects.filter(staff=staff).count() == 2


def test_staff_booking_unavailable_states_are_explained(client, staff_booking_case):
    staff, path, _ = staff_booking_case
    staff.services.clear()
    response = client.get(path, {"book": "1"})
    assert response.status_code == 200
    assert response.context["booking_staff_has_no_services"]
    assert "هیچ خدمت فعالی تعریف نشده" in response.content.decode()
    staff.is_bookable = False
    staff.save(update_fields=["is_bookable"])
    response = client.get(path, {"book": "1"})
    assert response.status_code == 200
    assert not response.context["can_book_appointment"]
    assert not response.context["book_modal_open"]
    assert "در حال حاضر قابل رزرو نیست" in response.content.decode()


def test_staff_booking_invalid_customer_id_does_not_raise_500(client, staff_booking_case):
    _, path, payload = staff_booking_case
    response = client.post("/appointments/new/", {**payload, "customer": "invalid"})
    assert response.status_code == 200
    assert response.context["booking_return_path"] == path
    assert response.context["appointment_form"].errors["customer"]


@pytest.mark.parametrize("value", ["//example.com", "/\\example.com", "https://example.com", "/x\r\n"])
def test_booking_return_path_rejects_unsafe_urls(value):
    from apps.appointments.booking import safe_booking_return_path

    # Leading/trailing whitespace is trimmed by the helper; embedded control
    # characters and external redirects must not be accepted.
    if value.endswith("\r\n"):
        value = "/x\r\ny"
    assert safe_booking_return_path(value) is None
