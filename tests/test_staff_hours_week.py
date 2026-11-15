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
