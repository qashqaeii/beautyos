import pytest
from django.urls import reverse

from apps.services.models import Service, ServiceCategory


@pytest.mark.django_db
def test_create_service_sets_defaults(client, owner_membership, salon):
    user = owner_membership.user
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    url = reverse("services:create")
    response = client.post(
        url,
        {
            "intent": "save_service",
            "name": "ژلیش",
            "description": "",
            "price_toman": "250000",
            "is_active": "on",
            "is_public": "on",
        },
    )
    assert response.status_code == 302
    service = Service.objects.get(salon=salon, name="ژلیش")
    assert service.duration_minutes == 30
    assert service.is_active is True


@pytest.mark.django_db
def test_inline_category_duplicate_name(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    ServiceCategory.objects.create(salon=salon, name="خدمات ناخن")

    url = reverse("services:create")
    response = client.post(
        url,
        {
            "intent": "add_category",
            "new_category_name": "خدمات ناخن",
            "name": "ژلیش",
            "price_toman": "100000",
        },
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "قبلاً ثبت شده" in html
    assert "services-page" in html
