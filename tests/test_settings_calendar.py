import pytest


@pytest.mark.django_db
def test_salon_settings_save(client, user, owner_membership):
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    response = client.get("/settings/")
    assert response.status_code == 200
    response = client.post(
        "/settings/",
        {
            "name": owner_membership.salon.name,
            "tagline": "تگ جدید",
            "description": "",
            "public_phone": "",
            "address": "",
            "city": "تهران",
            "public_theme": owner_membership.salon.public_theme,
            "instagram": "",
            "whatsapp": "",
            "is_accepting_bookings": "on",
            "retention_days_30": 30,
            "retention_days_60": 60,
            "retention_days_90": 90,
            "booking_lead_time_minutes": 60,
            "cancellation_notice_hours": 2,
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
