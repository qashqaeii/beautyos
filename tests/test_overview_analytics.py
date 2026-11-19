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


@pytest.mark.django_db
def test_overview_day_filter_and_customer_distinct_counts(salon, salon_b, owner_membership, client):
    from apps.appointments.models import Appointment
    from apps.services.models import Service
    from apps.staff.models import StaffProfile
    from apps.dashboard.role_services import get_overview_context

    day = timezone.localdate()
    start, end = day_bounds(day)
    customer = Customer.objects.create(salon=salon, full_name="مشتری", phone="09121112223")
    service = Service.objects.create(salon=salon, name="اصلاح", duration_minutes=30, price_toman=100000)
    member = SalonMembership.objects.create(
        salon=salon, user=User.objects.create_user(phone="+989121234589"),
        role=SalonMembership.Role.SPECIALIST,
    )
    staff = StaffProfile.objects.create(salon=salon, membership=member, display_name="متخصص")
    for offset, status in [(-24, Appointment.Status.COMPLETED), (1, Appointment.Status.COMPLETED),
                           (2, Appointment.Status.COMPLETED), (3, Appointment.Status.PENDING),
                           (4, Appointment.Status.CANCELLED), (25, Appointment.Status.PENDING)]:
        when = start + timedelta(hours=offset)
        Appointment.objects.create(salon=salon, customer=customer, service=service, staff=staff,
                                   start_at=when, end_at=when + timedelta(minutes=30), status=status)
    data = overview_analytics(salon, owner_membership, day)
    assert data["status_total"] == 4
    assert data["customers"]["visited"] == 1
    assert data["customers"]["returning"] == 1
    assert data["staff"][0]["count"] == 2
    overview = get_overview_context(salon, owner_membership, day, start, end)["overview"]
    assert overview["pending_count"] == 1
    assert overview["appointments_count"] == 3
    client.force_login(owner_membership.user)
    response = client.get("/app/", {"day": day.isoformat(), "trend": "30"})
    assert response.status_code == 200
    assert response.context["trend_days"] == 30


@pytest.mark.django_db
def test_overview_receptionist_finance_not_rendered_and_invalid_date(client, salon):
    receptionist = SalonMembership.objects.create(
        salon=salon, user=User.objects.create_user(phone="+989121234590"),
        role=SalonMembership.Role.RECEPTIONIST,
    )
    client.force_login(receptionist.user)
    response = client.get("/app/", {"day": "0001-01-01", "trend": "invalid"})
    assert response.status_code == 200
    assert response.context["selected_day"] == timezone.localdate()
    assert response.context["trend_days"] == 7
    assert response.context["analytics"]["revenue"] is None
    assert "overview-revenue-title" not in response.content.decode()
    assert 'data-stat-key="total_received"' not in response.content.decode()
