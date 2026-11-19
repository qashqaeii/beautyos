import pytest

from apps.accounts.models import User
from apps.customers.models import Customer


@pytest.mark.django_db
def test_customer_scoped_per_salon(salon, salon_b):
    Customer.objects.create(salon=salon, full_name="علی", phone="+989131111111")
    Customer.objects.create(salon=salon_b, full_name="رضا", phone="+989132222222")

    assert Customer.scoped(salon).count() == 1
    assert Customer.scoped(salon_b).count() == 1
    assert Customer.scoped(salon).first().full_name == "علی"


@pytest.mark.django_db
def test_dashboard_with_membership(client, user, owner_membership):
    client.force_login(user)
    response = client.get("/app/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_dashboard_redirect_without_salon(client, user):
    client.force_login(user)
    response = client.get("/app/")
    assert response.status_code == 302
    assert "/onboarding/create/" in response.url


@pytest.mark.django_db
def test_switch_salon_preserves_explicit_choice_and_rejects_external_redirect(client, owner_membership, salon_b):
    from django.urls import reverse
    from apps.salons.models import SalonMembership
    SalonMembership.objects.create(user=owner_membership.user, salon=salon_b, role=SalonMembership.Role.MANAGER)
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    url = reverse("salons_onboarding:switch", args=[salon_b.pk])
    assert client.get(url).status_code == 405
    response = client.post(url, {"next": "https://example.com"})
    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")
    response = client.get(response.url)
    assert response.status_code == 200
    assert response.wsgi_request.salon.pk == salon_b.pk
    assert client.session["active_salon_id"] == str(salon_b.pk)
    salon_b.is_active = False
    salon_b.save(update_fields=["is_active"])
    assert client.post(url).status_code == 403
    assert client.get(reverse("dashboard:home")).wsgi_request.salon.pk == owner_membership.salon_id


@pytest.mark.django_db
def test_switch_rejects_unrelated_salon_and_invalid_session(client, owner_membership, salon_b):
    from django.urls import reverse
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = "not-a-uuid"
    session.save()
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 200
    assert response.wsgi_request.salon.pk == owner_membership.salon_id
    assert client.post(reverse("salons_onboarding:switch", args=[salon_b.pk])).status_code == 403
