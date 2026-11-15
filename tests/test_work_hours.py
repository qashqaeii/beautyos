import pytest

from apps.staff.forms import WorkHoursForm
from apps.staff.models import StaffWorkHours
from apps.core.utils.time_input import parse_hhmm
from datetime import time


def test_parse_hhmm_compact_and_persian():
    assert parse_hhmm("0900") == time(9, 0)
    assert parse_hhmm("۰۹:۰۰") == time(9, 0)
    assert parse_hhmm("21:00") == time(21, 0)


@pytest.mark.django_db
def test_work_hours_form_rejects_end_before_start():
    form = WorkHoursForm(
        {
            "weekday": StaffWorkHours.Weekday.MON,
            "start_time": "09:00",
            "end_time": "08:00",
            "is_closed": "",
        }
    )
    assert not form.is_valid()
    assert "بعد از ساعت شروع" in form.errors["end_time"][0]


@pytest.mark.django_db
def test_work_hours_form_accepts_compact_input():
    form = WorkHoursForm(
        {
            "weekday": StaffWorkHours.Weekday.TUE,
            "start_time": "0900",
            "end_time": "2100",
            "is_closed": "",
        }
    )
    assert form.is_valid()
    assert form.cleaned_data["start_time"] == time(9, 0)
    assert form.cleaned_data["end_time"] == time(21, 0)


@pytest.mark.django_db
def test_work_hours_form_closed_skips_time_validation():
    form = WorkHoursForm(
        {
            "weekday": StaffWorkHours.Weekday.FRI,
            "is_closed": "on",
        }
    )
    assert form.is_valid()
    assert form.cleaned_data["start_time"] == time(0, 0)
    assert form.cleaned_data["end_time"] == time(0, 0)
    assert form.cleaned_data["is_closed"] is True
