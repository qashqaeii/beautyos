from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.role_services import bookable_staff_for_service, first_available_slots
from apps.services.models import Service, ServiceCategory
from apps.staff.display import staff_booking_label
from apps.staff.models import StaffProfile, StaffWorkHours


@pytest.mark.django_db
def test_staff_booking_label_with_and_without_title(salon, owner_membership):
    profile, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "مریم احمدی", "is_bookable": True},
    )
    profile.display_name = "مریم احمدی"
    profile.title = "رنگ مو"
    profile.save()
    assert staff_booking_label(profile) == "مریم احمدی (رنگ مو)"
    profile.title = ""
    profile.save()
    assert staff_booking_label(profile) == "مریم احمدی"


@pytest.mark.django_db
def test_first_available_slots_single_staff_filter(salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="r-slot")
    service = Service.objects.create(
        salon=salon, category=cat, name="رنگ", duration_minutes=60, price_toman=500_000
    )
    staff_a, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "الف", "is_bookable": True},
    )
    staff_a.services.add(service)
    day = timezone.localdate() + timedelta(days=14)
    weekday = (day.weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff_a,
        weekday=weekday,
        defaults={"start_time": time(9, 0), "end_time": time(18, 0)},
    )
    slots_all = first_available_slots(salon, day, service)
    assert len(slots_all) >= 1
    slots_one = first_available_slots(salon, day, service, staff_id=staff_a.pk)
    assert len(slots_one) == 1
    assert slots_one[0]["staff"].pk == staff_a.pk
    assert slots_one[0]["start"] == slots_all[0]["start"]


@pytest.mark.django_db
def test_reception_desk_staff_filter_reset_when_invalid_service(client, salon, owner_membership):
    from apps.accounts.models import User
    from apps.salons.models import SalonMembership

    rec_user = User.objects.create_user(phone="+989121200099", full_name="منشی")
    rec = SalonMembership.objects.create(user=rec_user, salon=salon, role=SalonMembership.Role.RECEPTIONIST)
    cat = ServiceCategory.objects.create(salon=salon, name="r-desk")
    svc_a = Service.objects.create(salon=salon, category=cat, name="A", duration_minutes=30, price_toman=100_000)
    svc_b = Service.objects.create(salon=salon, category=cat, name="B", duration_minutes=30, price_toman=100_000)
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص واحد", "is_bookable": True, "title": "اصلاح"},
    )
    staff.services.add(svc_a)
    day = timezone.localdate() + timedelta(days=15)
    client.force_login(rec.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    html = client.get(
        reverse("reception:desk"),
        {"day": day.isoformat(), "service": svc_b.pk, "staff": staff.pk},
    ).content.decode()
    assert "reception-desk-page" in html
    assert f'<option value="{staff.pk}" selected' not in html
    assert bookable_staff_for_service(salon, svc_b).count() == 0


@pytest.mark.django_db
def test_reception_staff_filter_no_slot_message(client, salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="r-msg")
    service = Service.objects.create(
        salon=salon, category=cat, name="خدمت پیام", duration_minutes=120, price_toman=200_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص پیام", "title": "تست", "is_bookable": True},
    )
    staff.services.add(service)
    day = timezone.localdate()
    weekday = (day.weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(7, 0), "end_time": time(8, 0)},
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    html = client.get(
        reverse("reception:desk"),
        {"day": day.isoformat(), "service": service.pk, "staff": staff.pk},
    ).content.decode()
    assert "reception-week__days" in html


@pytest.mark.django_db
def test_reception_editorial_layout_preserves_booking_and_single_header(client, salon, owner_membership):
    from django.contrib.staticfiles import finders

    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    url = reverse("reception:desk")
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    assert html.count("<h1") == 1
    assert 'class="maison-unified-header ' not in html
    assert "luna-reception-shell" in html
    assert "luna-reception.css" in html
    assert "reception-desk-quick__link--primary" in html
    assert html.index("reception-desk-quick dashboard-enter") < html.index("reception-desk-layout reception-calendar-layout")
    assert "ثبت نوبت جدید" in html
    assert "reception-overview-kpis" in html
    assert "reception-week__days" in html
    assert "reception-flow__list" in html
    for name in ("next", "pending"):
        asset = f"images/photos/beautyos-reception-{name}.webp"
        assert finders.find(asset)
    response = client.get(url, {"book": "1"})
    assert response.status_code == 200
    assert response.context["book_modal_open"]
    assert "appointment-booking-modal-title" in response.content.decode()
