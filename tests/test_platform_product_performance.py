"""Comparative reporting does not invent growth when no activity exists."""
import pytest
from django.urls import reverse

from apps.platform_admin.product_performance import product_performance


@pytest.mark.django_db
def test_product_performance_empty_database():
    result = product_performance(days=30)
    assert result["online_share"] is None
    assert result["active_booking_salons"] == 0
    assert result["active_customer_salons"] == 0
    assert len(result["comparison"]) == 3
    assert all(item["current"] == 0 and item["previous"] == 0 for item in result["comparison"])
    with pytest.raises(ValueError):
        product_performance(days=10)


@pytest.mark.django_db
def test_customer_creation_appears_in_reporting(salon):
    from apps.customers.models import Customer
    Customer.objects.create(salon=salon, full_name="مشتری گزارش", phone="+989121234588")
    result = product_performance(days=30)
    customers = next(item for item in result["comparison"] if item["key"] == "customers")
    assert customers["current"] == 1
    assert result["active_customer_salons"] == 1


@pytest.mark.django_db
def test_salon_performance_is_scoped_and_reports_empty_share(salon, salon_b):
    from apps.customers.models import Customer
    from apps.platform_admin.product_performance import salon_product_performance

    Customer.objects.create(salon=salon_b, full_name="مشتری سالن دیگر", phone="+989121234599")
    result = salon_product_performance(salon=salon, days=7)
    assert result["online_share"] is None
    assert all(row["current"] == 0 for row in result["comparison"])
    Customer.objects.create(salon=salon, full_name="مشتری سالن", phone="+989121234577")
    result = salon_product_performance(salon=salon, days=7)
    customers = next(row for row in result["comparison"] if row["label"] == "مشتریان جدید")
    assert customers["current"] == 1
    with pytest.raises(ValueError):
        salon_product_performance(salon=salon, days=5)
