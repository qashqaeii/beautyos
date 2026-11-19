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
