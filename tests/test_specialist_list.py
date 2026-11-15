import pytest
from datetime import time

from apps.dashboard.specialist_list import build_specialist_rows, today_hours_label
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile, StaffWorkHours
from apps.core.utils.dates import week_start_saturday
from django.utils import timezone


@pytest.mark.django_db
def test_today_hours_closed(salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="c")
    svc = Service.objects.create(
        salon=salon, category=cat, name="S", duration_minutes=30, price_toman=1
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "ت", "is_active": True, "is_bookable": True},
    )
    staff.services.add(svc)
    today = timezone.localdate()
    wd = (today.weekday() + 2) % 7
    StaffWorkHours.objects.update_or_create(
        salon=salon,
        staff=staff,
        weekday=wd,
        defaults={"start_time": time(9, 0), "end_time": time(18, 0), "is_closed": True},
    )
    kind, label = today_hours_label(staff, today)
    assert kind == "closed"
    assert label == "تعطیل"


@pytest.mark.django_db
def test_specialists_page_has_card_markup(client, salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="c")
    Service.objects.create(
        salon=salon, category=cat, name="S", duration_minutes=30, price_toman=1
    )
    StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "کارت تست", "is_active": True, "is_bookable": True},
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    resp = client.get("/app/specialists/", HTTP_HOST="127.0.0.1:8000")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "specialists-page" in html
    assert "specialists-list" in html
    assert "specialists-list__row" in html