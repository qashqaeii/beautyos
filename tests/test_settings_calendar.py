import pytest
from django.utils.text import slugify


@pytest.mark.django_db
def test_salon_settings_save(client, user, owner_membership):
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    response = client.get("/settings/")
    assert response.status_code == 200
    salon = owner_membership.salon
    response = client.post(
        "/settings/",
        {
            "form_kind": "profile",
            "name": salon.name,
            "slug": slugify(salon.slug or salon.name, allow_unicode=False) or "salon-alpha",
            "tagline": "تگ جدید",
            "description": "",
            "public_phone": "",
            "address": "",
            "city": "تهران",
            "instagram": "",
            "whatsapp": "",
            "is_accepting_bookings": "on",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    owner_membership.salon.refresh_from_db()
    assert owner_membership.salon.tagline == "تگ جدید"


@pytest.mark.django_db
def test_weekly_calendar(client, user, owner_membership):
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    assert client.get("/appointments/week/").status_code == 200
