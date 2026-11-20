import pytest
from django.core.management import call_command

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.core.demo_seed.engine import demo_customer_phone_prefix
from apps.salons.models import Salon
from apps.services.models import Service
from apps.staff.models import StaffProfile


@pytest.mark.django_db
def test_seed_demo_salon_idempotent_and_counts():
    call_command("seed_demo_salon", "--reset", verbosity=0)
    salon = Salon.objects.get(slug="demo-salon-a")
    prefix = demo_customer_phone_prefix(salon.slug)

    assert StaffProfile.scoped(salon).filter(bio__startswith="demo_salon_seed").count() == 10
    assert Service.scoped(salon).filter(description__startswith="demo_salon_seed").count() == 40
    assert Customer.scoped(salon).filter(phone__startswith=prefix, is_deleted=False).count() == 30
    appt_count = Appointment.scoped(salon).filter(customer__phone__startswith=prefix).count()
    assert appt_count >= 120

    call_command("seed_demo_salon", verbosity=0)
    assert Appointment.scoped(salon).filter(customer__phone__startswith=prefix).count() == appt_count