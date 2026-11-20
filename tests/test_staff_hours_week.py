from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.utils.dates import week_start_saturday
from apps.salons.models import SalonMembership
from apps.staff.models import StaffProfile, StaffWorkHours


@pytest.mark.django_db
def test_staff_hours_week_query_changes_jalali_labels(client, owner_membership, salon):
    membership = SalonMembership.objects.create(
        user=User.objects.create_user(phone="+989129992002", full_name="متخصص ساعت"),
        salon=salon,
        role=SalonMembership.Role.SPECIALIST,
    )
    profile = StaffProfile.objects.create(salon=salon, membership=membership, display_name="ساعات")
    StaffWorkHours.objects.create(
        salon=salon,
        staff=profile,
        weekday=StaffWorkHours.Weekday.SAT,
        start_time="09:00",
        end_time="17:00",
        is_closed=False,
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    url = reverse("staff:hours", kwargs={"pk": profile.pk})
    week_a = week_start_saturday(timezone.localdate()).isoformat()
    week_b = (week_start_saturday(timezone.localdate()) + timedelta(days=7)).isoformat()

    body_a = client.get(f"{url}?week={week_a}").content.decode()
    body_b = client.get(f"{url}?week={week_b}").content.decode()
    assert body_a != body_b
    assert "برنامهٔ هفتگی" in body_a
    assert "ذخیره برنامهٔ هفتگی" in body_a


@pytest.mark.django_db
def test_staff_hours_selected_day_prefilled_and_saved(client, owner_membership, salon):
    from datetime import time
    staff, _ = StaffProfile.objects.get_or_create(salon=salon, membership=owner_membership)
    StaffWorkHours.objects.create(salon=salon, staff=staff, weekday=2, start_time=time(9,30), end_time=time(17))
    client.force_login(owner_membership.user)
    week = week_start_saturday(timezone.localdate())
    url = reverse("staff:hours", args=[staff.pk])
    result = client.get(url, {"week":week.isoformat(),"day":2})
    assert result.status_code == 200
    assert result.context["selected_day"] == 2
    assert result.context["form"]["start_time"].value() == time(9,30)
    assert result.context["work_days"] == 1
    assert result.context["unconfigured_days"] == 6
    data = {"weekday":"2","reference_date":(week+timedelta(days=2)).isoformat(),"start_time":"18:00","end_time":"09:00"}
    invalid = client.post(f"{url}?week={week.isoformat()}&day=2",data)
    assert invalid.status_code == 200
    assert invalid.context["form"].errors["end_time"]
    assert StaffWorkHours.objects.get(staff=staff,weekday=2).start_time == time(9,30)
    success = client.post(f"{url}?week={week.isoformat()}&day=2",{**data,"start_time":"10:00","end_time":"19:00"})
    assert success.status_code == 302 and "day=2" in success.url
    assert StaffWorkHours.objects.get(staff=staff,weekday=2).start_time == time(10)
    closed = client.post(f"{url}?week={week.isoformat()}&day=2",{"weekday":"2","reference_date":data["reference_date"],"is_closed":"on"})
    assert closed.status_code == 302
    assert StaffWorkHours.objects.get(staff=staff,weekday=2).is_closed
