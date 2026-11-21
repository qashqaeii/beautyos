import pytest
from django.core.management import call_command

from apps.core.demo_seed.engine import SALON_A_SLUG, demo_customer_phone_prefix
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.salons.models import Salon


@pytest.mark.django_db
def test_purge_demo_data_clears_seeded_salon():
    call_command("seed_demo_salon", verbosity=0)
    salon = Salon.objects.get(slug=SALON_A_SLUG)
    prefix = demo_customer_phone_prefix(salon.slug)
    assert Customer.scoped(salon).filter(phone__startswith=prefix).exists()

    call_command("purge_demo_data", verbosity=0)

    assert not Salon.objects.filter(slug=SALON_A_SLUG).exists()
    assert not Customer.objects.filter(phone__startswith=prefix).exists()
    assert not Expense.objects.filter(description__contains="گردش نمایشی").exists()