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
    demo_appointments = Appointment.scoped(salon).filter(customer__phone__startswith=prefix)
    appt_count = demo_appointments.count()
    original_ids = set(demo_appointments.values_list("pk", flat=True))
    assert appt_count >= 120

    # Re-running the seed must not silently add appointments when same-day
    # checkouts from the first pass have moved to a terminal status.
    call_command("seed_demo_salon", verbosity=0)
    current_ids = set(demo_appointments.values_list("pk", flat=True))
    assert current_ids == original_ids
    assert len(current_ids) == appt_count

    # Every deterministic customer/start pair is unique even after re-seeding.
    from django.db.models import Count

    duplicates = (
        demo_appointments.values("customer_id", "start_at")
        .annotate(total=Count("pk"))
        .filter(total__gt=1)
    )
    assert not duplicates.exists()