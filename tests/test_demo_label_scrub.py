import pytest
from django.core.management import call_command
from django.db.models import Q

from apps.core.demo_seed.labels import DEMO_LEGACY_PREFIX, scrub_salon_demo_labels
from apps.customers.models import Customer
from apps.salons.models import Salon
from apps.services.models import ServiceCategory
from apps.staff.models import StaffProfile


@pytest.mark.django_db
def test_scrub_removes_demo_prefix_from_category_and_staff():
    call_command("seed_demo", "--scenario=minimal", verbosity=0)
    salon = Salon.objects.get(slug="demo-salon-a")

    legacy_cat = ServiceCategory.objects.create(salon=salon, name=f"{DEMO_LEGACY_PREFIX} دسته", sort_order=99)
    staff = StaffProfile.scoped(salon).first()
    assert staff is not None
    staff.display_name = f"آرایشگر بتا {DEMO_LEGACY_PREFIX}"
    staff.save(update_fields=["display_name", "updated_at"])

    scrub_salon_demo_labels(salon)

    assert not ServiceCategory.scoped(salon).filter(pk=legacy_cat.pk).exists()
    assert ServiceCategory.scoped(salon).filter(name="خدمات زیبایی").exists()
    assert not ServiceCategory.scoped(salon).filter(name__contains=DEMO_LEGACY_PREFIX).exists()

    staff.refresh_from_db()
    assert DEMO_LEGACY_PREFIX not in staff.display_name
    assert staff.display_name == "آرایشگر بتا"


def _no_demo_label_in_salon(salon) -> bool:
    checks = [
        ServiceCategory.scoped(salon).filter(name__contains=DEMO_LEGACY_PREFIX).exists(),
        Customer.scoped(salon).filter(full_name__contains=DEMO_LEGACY_PREFIX).exists(),
        StaffProfile.scoped(salon).filter(
            Q(display_name__contains=DEMO_LEGACY_PREFIX) | Q(title__contains=DEMO_LEGACY_PREFIX)
        ).exists(),
    ]
    return not any(checks)


@pytest.mark.django_db
def test_seed_demo_full_has_no_visible_demo_markers():
    call_command("seed_demo", "--scenario=full", "--reset-demo", verbosity=0)
    for slug in ("demo-salon-a", "demo-barber-b"):
        salon = Salon.objects.get(slug=slug)
        assert _no_demo_label_in_salon(salon)
