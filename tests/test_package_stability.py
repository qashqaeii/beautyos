import pytest
from django.urls import reverse
from apps.packages.forms import ServicePackageForm
from apps.packages.models import CustomerPackage, ServicePackage
from apps.customers.models import Customer
from apps.salons.models import SalonMembership
from apps.accounts.models import User


def test_package_rejects_zero_sessions_and_validity():
    form = ServicePackageForm({"name": "test", "price_toman": "1000", "session_count": 0, "validity_days": 0, "is_active": True})
    assert not form.is_valid()
    assert "session_count" in form.errors
    assert "validity_days" in form.errors


@pytest.mark.django_db
def test_receptionist_package_sale_returns_to_permitted_page(client, salon):
    user = User.objects.create_user(phone="+989121222797")
    SalonMembership.objects.create(salon=salon, user=user, role=SalonMembership.Role.RECEPTIONIST)
    customer = Customer.objects.create(salon=salon, full_name="مشتری", phone="+989121222798")
    package = ServicePackage.objects.create(salon=salon, name="پکیج", price_toman=1000, session_count=2, validity_days=30)
    client.force_login(user)
    response = client.post(reverse("packages:sell"), {"customer": customer.pk, "package": package.pk}, follow=True)
    assert response.status_code == 200
    assert CustomerPackage.scoped(salon).filter(customer=customer, package=package).count() == 1


@pytest.mark.django_db
def test_package_cannot_be_used_for_another_customer(salon, owner_membership):
    from datetime import timedelta
    from django.core.exceptions import ValidationError
    from django.utils import timezone
    from apps.appointments.models import Appointment
    from apps.packages.services import consume_package_session
    from apps.packages.models import PackageSessionUse
    from apps.services.models import Service
    from apps.staff.models import StaffProfile

    first = Customer.objects.create(salon=salon, full_name="اول", phone="+989121222799")
    second = Customer.objects.create(salon=salon, full_name="دوم", phone="+989121222800")
    package = ServicePackage.objects.create(salon=salon, name="پکیج", price_toman=1000, session_count=2)
    sale = CustomerPackage.objects.create(salon=salon, customer=first, package=package,
        sessions_total=2, expires_at=timezone.now() + timedelta(days=30), price_paid_toman=1000)
    staff, _ = StaffProfile.objects.get_or_create(salon=salon, membership=owner_membership)
    service = Service.objects.create(salon=salon, name="خدمت", duration_minutes=30, price_toman=1000)
    start = timezone.now() + timedelta(days=1)
    appointment = Appointment.objects.create(salon=salon, customer=second, staff=staff, service=service,
        start_at=start, end_at=start + timedelta(minutes=30))
    with pytest.raises(ValidationError):
        consume_package_session(sale, appointment)
    sale.refresh_from_db()
    assert sale.sessions_used == 0
    assert not PackageSessionUse.objects.filter(appointment=appointment).exists()
