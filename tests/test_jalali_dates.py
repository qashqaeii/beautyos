from datetime import date

import pytest

from apps.core.utils.dates import parse_jalali_date, to_jalali


def test_parse_jalali_persian_digits():
    g = parse_jalali_date("۱۴۰۳/۰۱/۰۱")
    assert isinstance(g, date)


def test_parse_jalali_latin():
    g = parse_jalali_date("1403/01/01")
    j = to_jalali(g)
    assert j == "1403/01/01"


def _staff_profile(owner_membership, salon):
    from apps.accounts.models import User
    from apps.salons.models import SalonMembership
    from apps.staff.models import StaffProfile

    profile = StaffProfile.scoped(salon).filter(is_active=True).first()
    if profile:
        return profile
    membership = SalonMembership.objects.create(
        user=User.objects.create_user(phone="+989129990001", full_name="متخصص مرخصی"),
        salon=salon,
        role=SalonMembership.Role.SPECIALIST,
    )
    return StaffProfile.objects.create(
        salon=salon,
        membership=membership,
        display_name="متخصص تست",
    )


@pytest.mark.django_db
def test_staff_time_off_end_before_start(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    profile = _staff_profile(owner_membership, salon)

    from django.urls import reverse

    url = reverse("staff:time_off", kwargs={"pk": profile.pk})
    response = client.post(
        url,
        {
            "start_date": "2026-11-15",
            "end_date": "2026-11-10",
            "reason": "",
        },
    )
    assert response.status_code == 200
    assert "قبل از تاریخ شروع" in response.content.decode()


@pytest.mark.django_db
def test_staff_time_off_single_day(client, owner_membership, salon):
    from apps.staff.models import StaffTimeOff

    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    profile = _staff_profile(owner_membership, salon)

    from django.urls import reverse

    url = reverse("staff:time_off", kwargs={"pk": profile.pk})
    iso = "2026-11-20"
    before = StaffTimeOff.objects.filter(staff=profile).count()
    response = client.post(url, {"start_date": iso, "end_date": iso, "reason": "تست"})
    assert response.status_code == 302
    assert StaffTimeOff.objects.filter(staff=profile).count() == before + 1
