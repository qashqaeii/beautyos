import pytest
from django.core.management import call_command

from apps.core.sample_seed.dataset import SAMPLE_SALON_SLUG, SEED_SPECIALIST_COUNT, compute_seed_calendar
from apps.core.sample_seed.seed_verify import build_seed_report
from apps.core.utils.dates import jalali_month_bounds
from apps.dashboard.role_services import day_bounds
from apps.finance.dashboard import finance_dashboard
from apps.salons.models import Salon
from apps.staff.models import StaffProfile


@pytest.mark.django_db
def test_seed_realistic_salon_has_no_demo_markers():
    call_command("seed_realistic_salon", "--reset", verbosity=0)
    salon = Salon.objects.get(slug=SAMPLE_SALON_SLUG)
    assert "demo" not in salon.description.lower()
    assert "نمایشی" not in salon.name
    assert "فیک" not in salon.name.lower()
    assert "تست" not in salon.tagline.lower()
    start_date, end_date = jalali_month_bounds()
    start_dt, _ = day_bounds(start_date)
    _, end_dt = day_bounds(end_date)
    data = finance_dashboard(
        salon,
        {"start_dt": start_dt, "end_dt": end_dt, "start_date": start_date, "end_date": end_date},
    )
    assert data["chart"]["has_data"]
    assert data["total_earned"] > 0
    from apps.expenses.models import Expense

    assert not Expense.scoped(salon).filter(description__icontains="demo").exists()
    assert not Expense.scoped(salon).filter(description__icontains="گردش نمایشی").exists()
    from apps.appointments.models import Appointment
    from apps.customers.models import Customer

    assert Customer.scoped(salon).count() >= 50
    assert StaffProfile.scoped(salon).filter(is_bookable=True).count() == SEED_SPECIALIST_COUNT
    assert Appointment.scoped(salon).count() >= 400

    report = build_seed_report(salon)
    assert len(report["months"]) == 3
    assert report["overlap_conflicts"] == 0
    assert all(m["revenue_toman"] > 0 for m in report["months"])
    assert report["payments_paid_full"] > report["payments_partial"]

    period_start, period_end, history_days, target = compute_seed_calendar()
    assert history_days >= 80
    assert target >= 450