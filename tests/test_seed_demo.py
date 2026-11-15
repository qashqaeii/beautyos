import pytest
from django.core.management import call_command

from apps.appointments.models import Appointment
from apps.core.demo_seed.engine import demo_customer_phone_prefix, SALON_A_SLUG
from apps.customers.models import Customer
from apps.salons.models import Salon


def _demo_customers(salon):
    return Customer.scoped(salon).filter(phone__startswith=demo_customer_phone_prefix(salon.slug))


@pytest.mark.django_db
def test_seed_demo_full_idempotent():
    call_command("seed_demo", "--scenario=full", verbosity=0)
    count_a = _demo_customers(Salon.objects.get(slug="demo-salon-a")).count()
    call_command("seed_demo", "--scenario=full", verbosity=0)
    count_b = _demo_customers(Salon.objects.get(slug="demo-salon-a")).count()
    assert count_a == count_b
    assert count_a >= 10
    salon = Salon.objects.get(slug="demo-salon-a")
    assert not Customer.scoped(salon).filter(full_name__contains="[دمو]").exists()


@pytest.mark.django_db
def test_seed_demo_busy_day():
    call_command("seed_demo", "--scenario=full", verbosity=0)
    call_command("seed_demo", "--scenario=busy-day", "--salon=demo-salon-a", verbosity=0)
    from django.utils import timezone

    salon = Salon.objects.get(slug="demo-salon-a")
    prefix = demo_customer_phone_prefix(SALON_A_SLUG)

    appts_today = Appointment.scoped(salon).filter(
        start_at__date=timezone.localdate(),
        customer__phone__startswith=prefix,
    ).count()
    assert appts_today >= 10


@pytest.mark.django_db
def test_seed_demo_reset_empty():
    call_command("seed_demo", "--scenario=minimal", verbosity=0)
    call_command("seed_demo", "--scenario=empty", verbosity=0)
    salon = Salon.objects.get(slug="demo-salon-a")
    assert _demo_customers(salon).filter(is_deleted=False).count() == 0
