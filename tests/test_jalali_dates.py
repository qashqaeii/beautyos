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


def test_jalali_javascript_matches_django_calendar():
    """Use the real Alpine component in Node; compare to jdatetime around boundaries."""
    import json
    import shutil
    import subprocess
    from datetime import timedelta
    from pathlib import Path

    import jdatetime

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for JavaScript calendar parity")
    root = Path(__file__).resolve().parents[1]
    dates = [date(1900, 1, 1), date(2200, 12, 31), date(2026, 11, 20)]
    for year in range(1900, 2201):
        for month, day in ((1, 1), (3, 19), (3, 20), (3, 21), (3, 22), (12, 31)):
            dates.append(date(year, month, day))
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const registry = {};
const sandbox = {
  document: {addEventListener: (_name, callback) => callback()},
  Alpine: {data: (name, factory) => {registry[name] = factory;}},
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), sandbox);
const dates = JSON.parse(fs.readFileSync(0, 'utf8'));
const result = dates.map(iso => {
  const picker = registry.jalaliDaySubmit(iso, iso);
  picker.$el = {closest: () => null};
  picker.$nextTick = () => {};
  picker.init();
  const selected = picker.cells.find(cell => cell.selected);
  return [picker.display, selected ? selected.jd : null, picker.cells.filter(c => c.inMonth).length];
});
process.stdout.write(JSON.stringify(result));
"""
    result = subprocess.run(
        [node, "-e", script, str(root / "static/js/jalali-datepicker.js")],
        input=json.dumps([d.isoformat() for d in dates]), text=True,
        capture_output=True, check=True,
    )
    rows = json.loads(result.stdout)
    for day, (display, selected, length) in zip(dates, rows, strict=True):
        jalali = jdatetime.date.fromgregorian(date=day)
        assert display.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) == to_jalali(day), day
        assert selected == jalali.day, day
        assert length == (31 if jalali.month <= 6 else 30 if jalali.month <= 11 or jalali.isleap() else 29), day
