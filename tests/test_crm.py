import pytest

from apps.customers.models import Customer, CustomerActivity
from apps.customers.services import log_activity


@pytest.mark.django_db
def test_customer_crud_tenant(client, user, owner_membership, salon_b):
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()

    response = client.post(
        "/customers/new/",
        {
            "phone_input": "09125551234",
            "full_name": "مشتری تست",
            "email": "",
            "status": "new",
            "marketing_consent": "",
            "is_vip": "",
        },
    )
    assert response.status_code == 302
    assert Customer.scoped(owner_membership.salon).filter(full_name="مشتری تست").exists()
    assert Customer.scoped(salon_b).filter(full_name="مشتری تست").count() == 0


@pytest.mark.django_db
def test_customer_idor(salon, salon_b, user, owner_membership):
    other = Customer.objects.create(salon=salon_b, full_name="محرمانه", phone="+989139999999")
    from django.test import Client

    client = Client()
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    response = client.get(f"/customers/{other.pk}/")
    assert response.status_code == 404
