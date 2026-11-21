import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.core.utils.dates import jalali_month_bounds
from apps.dashboard.role_services import day_bounds
from apps.finance.dashboard import finance_dashboard
from apps.salons.models import Salon


@pytest.mark.django_db
def test_seed_demo_salon_finance_chart_has_data():
    call_command("seed_demo_salon", "--reset", verbosity=0)
    salon = Salon.objects.get(slug="demo-salon-a")
    start_date, end_date = jalali_month_bounds()
    start_dt, _ = day_bounds(start_date)
    _, end_dt = day_bounds(end_date)
    data = finance_dashboard(
        salon,
        {"start_dt": start_dt, "end_dt": end_dt, "start_date": start_date, "end_date": end_date},
    )
    assert data["chart"]["has_data"]
    assert data["total_earned"] > 0
    assert data["revenue_mix_valid"]