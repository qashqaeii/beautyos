import pytest
from django.urls import reverse

from apps.packages.forms import ServicePackageForm
from apps.packages.models import ServicePackage


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1250000", 1_250_000),
        ("۱.۲۵۰.۰۰۰", 1_250_000),
    ],
)
def test_service_package_form_parses_price(raw, expected):
    form = ServicePackageForm(
        data={
            "name": "پکیج آزمایشی",
            "description": "",
            "price_toman": raw,
            "session_count": 5,
            "validity_days": 365,
            "is_active": True,
        }
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["price_toman"] == expected


@pytest.mark.django_db
def test_package_create_stores_integer_price(client, salon, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    resp = client.post(
        reverse("packages:create"),
        {
            "name": "پکیج قیمت تست",
            "description": "تست",
            "price_toman": "۱.۲۵۰.۰۰۰",
            "session_count": 10,
            "validity_days": 90,
            "is_active": True,
        },
        follow=True,
    )
    assert resp.status_code == 200
    pkg = ServicePackage.scoped(salon).get(name="پکیج قیمت تست")
    assert pkg.price_toman == 1_250_000
