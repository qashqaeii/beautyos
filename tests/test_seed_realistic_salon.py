import pytest
from django.core.management import call_command

from apps.core.sample_seed.dataset import SAMPLE_SALON_SLUG
from apps.core.utils.dates import jalali_month_bounds
from apps.dashboard.role_services import day_bounds
from apps.finance.dashboard import finance_dashboard
from apps.salons.models import Salon


@pytest.mark.django_db
def test_seed_realistic_salon_has_no_demo_markers():
    call_command("seed_realistic_salon", "--reset", verbosity=0)
    salon = Salon.objects.get(slug=SAMPLE_SALON_SLUG)
    assert "demo" not in salon.description.lower()
    assert "نمایشی" not in salon.name
    start_date, end_date = jalali_month_bounds()
    start_dt, _ = day_bounds(start_date)
    _, end_dt = day_bounds(end_date)
    data = finance_dashboard(
        salon,
        {"start_dt": start_dt, "end_dt": end_dt, "start_date": start_date, "end_date": end_date},
    )
    assert data["chart"]["has_data"]
    assert data["total_earned"] > 0
    # Spot-check no demo marker substring in expenses
    from apps.expenses.models import Expense

    assert not Expense.scoped(salon).filter(description__icontains="demo").exists()
    assert not Expense.scoped(salon).filter(description__icontains="گردش نمایشی").exists()