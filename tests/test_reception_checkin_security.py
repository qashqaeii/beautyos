import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.salons.models import Salon, SalonMembership
from apps.services.models import Service


@pytest.fixture
def confirmed_appt(salon, owner_membership):
    service = Service.objects.create(salon=salon, name="خدمت", duration_minutes=30, price_toman=100_000)
    customer = Customer.objects.create(salon=salon, phone="+989121100100", full_name="مشتری")
    staff = owner_membership.staffprofile if hasattr(owner_membership, "staffprofile") else None
    from apps.staff.models import StaffProfile

    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "استاد", "is_bookable": True},
    )
    start = timezone.now() + timezone.timedelta(hours=1)
    return Appointment.objects.create(
        salon=salon,
        customer=customer,
        staff=staff,
        service=service,
        start_at=start,
        end_at=start + timezone.timedelta(minutes=30),
        status=Appointment.Status.CONFIRMED,
        price_toman=100_000,
    )


@pytest.mark.django_db
def test_checkin_get_does_not_change_status(client, salon, owner_membership, confirmed_appt):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    url = reverse("reception:checkin", kwargs={"pk": confirmed_appt.pk})
    assert client.get(url).status_code == 405
    confirmed_appt.refresh_from_db()
    assert confirmed_appt.status == Appointment.Status.CONFIRMED


@pytest.mark.django_db
def test_checkin_post_success(client, salon, owner_membership, confirmed_appt):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    url = reverse("reception:checkin", kwargs={"pk": confirmed_appt.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    confirmed_appt.refresh_from_db()
    assert confirmed_appt.status == Appointment.Status.CHECKED_IN


@pytest.mark.django_db
def test_checkin_post_requires_csrf(client, salon, owner_membership, confirmed_appt):
    client = client.__class__(enforce_csrf_checks=True)
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    url = reverse("reception:checkin", kwargs={"pk": confirmed_appt.pk})
    assert client.post(url).status_code == 403


@pytest.mark.django_db
def test_checkin_tenant_isolation(client, salon, salon_b, confirmed_appt):
    owner_b = User.objects.create_user(phone="+989121188888", full_name="مالک بتا")
    SalonMembership.objects.create(user=owner_b, salon=salon_b, role=SalonMembership.Role.OWNER)
    client.force_login(owner_b)
    session = client.session
    session["active_salon_id"] = str(salon_b.id)
    session.save()
    url = reverse("reception:checkin", kwargs={"pk": confirmed_appt.pk})
    resp = client.post(url)
    assert resp.status_code == 404
    confirmed_appt.refresh_from_db()
    assert confirmed_appt.status == Appointment.Status.CONFIRMED