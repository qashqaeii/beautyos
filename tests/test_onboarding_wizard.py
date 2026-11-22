"""Salon onboarding wizard — security, steps, and completion."""

import pytest
from django.urls import reverse

from apps.salons import onboarding_wizard as ow
from apps.salons.models import Salon, SalonMembership, SalonSettings
from apps.services.models import Service
from apps.staff.models import StaffProfile, StaffWorkHours


@pytest.mark.django_db
def test_wizard_step1_renders_public_shell(client):
    from apps.accounts.models import User

    user = User.objects.create_user(phone="+989121000001", full_name="مالک")
    client.force_login(user)
    html = client.get(reverse("salons_onboarding:wizard", kwargs={"step": 1})).content.decode()
    assert "public-auth-shell" in html
    assert "اطلاعات اولیه سالن" in html
    assert 'name="business_type"' not in html
    assert "آرایشگاه مردانه" not in html
    assert "سالن ترکیبی" not in html
    assert 'name="name"' in html


@pytest.mark.django_db
def test_wizard_full_flow_creates_salon_and_completes(client):
    from apps.accounts.models import User

    user = User.objects.create_user(phone="+989121000099", full_name="مالک جدید")
    client.force_login(user)

    r1 = client.post(
        reverse("salons_onboarding:wizard", kwargs={"step": 1}),
        {"name": "سالن تست"},
    )
    assert r1.status_code == 302
    assert r1.url.endswith("/onboarding/wizard/2/")

    r2 = client.post(
        reverse("salons_onboarding:wizard", kwargs={"step": 2}),
        {
            "slug": "salon-test-wizard",
            "public_phone": "09121112233",
            "city": "تهران",
            "address": "",
            "tagline": "",
            "description": "",
        },
    )
    assert r2.status_code == 302
    salon = Salon.objects.get(slug="salon-test-wizard")
    assert SalonMembership.objects.filter(user=user, salon=salon, role=SalonMembership.Role.OWNER).exists()

    client.post(
        reverse("salons_onboarding:wizard", kwargs={"step": 3}),
        {"action": "skip"},
    )
    client.post(
        reverse("salons_onboarding:wizard", kwargs={"step": 4}),
        {"display_name": "مالک جدید", "title": "", "is_bookable": "on"},
    )
    client.post(
        reverse("salons_onboarding:wizard", kwargs={"step": 5}),
        {"action": "skip"},
    )
    r6 = client.post(reverse("salons_onboarding:wizard", kwargs={"step": 6}))
    assert r6.status_code == 302
    assert r6.url == reverse("dashboard:home")

    settings = SalonSettings.objects.get(salon=salon)
    assert settings.onboarding_completed_at is not None
    assert StaffProfile.scoped(salon).filter(is_deleted=False).count() >= 1
    assert StaffWorkHours.objects.filter(salon=salon).exists()


@pytest.mark.django_db
def test_completed_onboarding_redirects_away_from_wizard(client, owner_membership):
    client.force_login(owner_membership.user)
    resp = client.get(reverse("salons_onboarding:wizard", kwargs={"step": 1}))
    assert resp.status_code == 302
    assert resp.url == reverse("dashboard:home")


@pytest.mark.django_db
def test_wizard_tenant_isolation_other_user_cannot_use_session_salon(client, owner_membership):
    from apps.accounts.models import User

    other = User.objects.create_user(phone="+989121000002", full_name="غریبه")
    client.force_login(other)
    session = client.session
    session[ow.SESSION_SALON_KEY] = str(owner_membership.salon.id)
    session.save()
    resp = client.get(reverse("salons_onboarding:wizard", kwargs={"step": 3}))
    assert resp.status_code == 302
    assert "wizard/1" in resp.url


@pytest.mark.django_db
def test_complete_onboarding_idempotent(owner_membership):
    settings = owner_membership.salon.settings
    settings.onboarding_completed_at = None
    settings.save(update_fields=["onboarding_completed_at"])
    assert ow.complete_onboarding(owner_membership.salon) is True
    completed_at = SalonSettings.objects.get(pk=settings.pk).onboarding_completed_at
    assert completed_at is not None
    assert ow.complete_onboarding(owner_membership.salon) is False

@pytest.mark.django_db
def test_wizard_step_one_accepts_name_only_and_rejects_legacy_type(client):
    from apps.accounts.models import User

    user = User.objects.create_user(phone="+989121000131", full_name="مدیر سالن")
    client.force_login(user)
    first = reverse("salons_onboarding:wizard", kwargs={"step": 1})
    response = client.post(first, {"name": "  سالن زیبایی نورا  "})
    assert response.status_code == 302
    assert response.url == reverse("salons_onboarding:wizard", kwargs={"step": 2})
    assert client.session[ow.SESSION_SALON_NAME] == "سالن زیبایی نورا"
    assert client.session[ow.SESSION_BUSINESS_TYPE] == Salon.BusinessType.BEAUTY_WOMEN
    response = client.post(first, {"name": "سالن نورا",
                                   "business_type": Salon.BusinessType.BARBER_MEN})
    assert response.status_code == 302
    assert client.session[ow.SESSION_BUSINESS_TYPE] == Salon.BusinessType.BEAUTY_WOMEN


@pytest.mark.django_db
def test_wizard_persian_name_has_valid_public_slug_even_if_cleared(client):
    from apps.accounts.models import User

    user = User.objects.create_user(phone="+989121000132", full_name="مدیر سالن")
    client.force_login(user)
    client.post(reverse("salons_onboarding:wizard", kwargs={"step": 1}),
                {"name": "آرایشگاه زیبایی نورا"})
    second = reverse("salons_onboarding:wizard", kwargs={"step": 2})
    initial = client.get(second)
    assert initial.status_code == 200
    suggested = initial.context["form"]["slug"].value()
    assert suggested and suggested.isascii() and suggested.startswith("salon-")
    response = client.post(second, {
        "slug": "", "public_phone": "09121112233", "city": "تهران",
        "address": "", "tagline": "", "description": "",
    })
    assert response.status_code == 302, response.content.decode()[:800]
    assert response.url == reverse("salons_onboarding:wizard", kwargs={"step": 3})
    salon = Salon.objects.get(name="آرایشگاه زیبایی نورا")
    assert salon.slug.startswith("salon-")
    assert salon.business_type == Salon.BusinessType.BEAUTY_WOMEN
    assert SalonMembership.objects.filter(
        user=user, salon=salon, role=SalonMembership.Role.OWNER
    ).exists()


@pytest.mark.django_db
def test_wizard_existing_unfinished_salon_uses_womens_type(client, owner_membership):
    salon = owner_membership.salon
    salon.settings.onboarding_completed_at = None
    salon.settings.save(update_fields=["onboarding_completed_at"])
    salon.business_type = Salon.BusinessType.COMBINED
    salon.save(update_fields=["business_type"])
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    response = client.post(reverse("salons_onboarding:wizard", kwargs={"step": 1}), {
        "name": "سالن زیبایی نوین", "business_type": Salon.BusinessType.COMBINED,
    })
    assert response.status_code == 302
    salon.refresh_from_db()
    assert salon.name == "سالن زیبایی نوین"
    assert salon.business_type == Salon.BusinessType.BEAUTY_WOMEN
    second = client.get(reverse("salons_onboarding:wizard", kwargs={"step": 2}))
    assert second.status_code == 200
    assert second.context["form"]["slug"].value() == salon.slug


@pytest.mark.django_db
def test_wizard_blank_name_renders_inline_error(client):
    from apps.accounts.models import User

    user = User.objects.create_user(phone="+989121000133", full_name="مدیر سالن")
    client.force_login(user)
    response = client.post(reverse("salons_onboarding:wizard", kwargs={"step": 1}),
                           {"name": " "})
    assert response.status_code == 200
    assert 'role="alert"' in response.content.decode()
    assert ow.SESSION_SALON_NAME not in client.session
