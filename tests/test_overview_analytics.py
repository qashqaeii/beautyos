from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.dashboard.analytics import overview_analytics
from apps.dashboard.role_services import day_bounds
from apps.finance.models import Payment
from apps.salons.models import SalonMembership


@pytest.mark.django_db
def test_overview_revenue_is_scoped_and_permission_checked(salon, salon_b, owner_membership):
    day = timezone.localdate()
    start, _ = day_bounds(day)
    for tenant, amount, status in [(salon, 400000, Payment.Status.PAID), (salon_b, 900000, Payment.Status.PAID), (salon, 200000, Payment.Status.REFUNDED)]:
        customer = Customer.objects.create(salon=tenant, full_name="تست", phone=str(amount))
        payment = Payment.objects.create(salon=tenant, customer=customer, paid_amount_toman=amount, status=status)
        Payment.objects.filter(pk=payment.pk).update(created_at=start + timedelta(hours=1))
    data = overview_analytics(salon, owner_membership, day, 7)
    assert data["revenue"]["total"] == 400000
    assert len(data["revenue"]["rows"]) == 7
    assert len(overview_analytics(salon, owner_membership, day, 30)["revenue"]["rows"]) == 30
    receptionist = SalonMembership.objects.create(
        salon=salon, user=User.objects.create_user(phone="+989121234588"), role=SalonMembership.Role.RECEPTIONIST,
    )
    assert overview_analytics(salon, receptionist, day)["revenue"] is None


@pytest.mark.django_db
def test_overview_is_analytical_and_handles_empty_data(client, owner_membership):
    client.force_login(owner_membership.user)
    response = client.get("/app/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "روند دریافتی سالن" in html
    assert "وضعیت نوبت‌ها" in html
    assert "عملکرد متخصصان" in html
    assert "آمار مشتریان" in html
    assert response.context["analytics"]["status_total"] == 0
    assert response.context["analytics"]["revenue"]["total"] == 0
