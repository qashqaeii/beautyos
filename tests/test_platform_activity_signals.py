"""Regression checks for privacy-safe product milestone instrumentation."""
import pytest

from apps.customers.models import Customer
from apps.platform_admin.models import PlatformActivityEvent


@pytest.mark.django_db(transaction=True)
def test_customer_creation_emits_once_after_commit(salon):
    customer = Customer.objects.create(
        salon=salon, full_name="مشتری نمونه", phone="+989121234567",
    )
    key = f"customer-created:{customer.pk}"
    event = PlatformActivityEvent.objects.get(dedupe_key=key)
    assert event.kind == PlatformActivityEvent.Kind.CUSTOMER_CREATED
    assert event.salon_id == salon.pk
    assert event.count == 1
    customer.full_name = "نام ویرایش‌شده"
    customer.save(update_fields=["full_name"])
    assert PlatformActivityEvent.objects.filter(dedupe_key=key).count() == 1
    assert not hasattr(event, "phone")
    assert not hasattr(event, "full_name")
