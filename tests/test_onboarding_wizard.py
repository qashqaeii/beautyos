"""Salon onboarding wizard — security, steps, and completion."""

import pytest
from django.urls import reverse

from apps.salons import onboarding_wizard as ow
from apps.salons.models import Salon, SalonMembership, SalonSettings, SalonWorkHours
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
    assert SalonWorkHours.objects.filter(salon=salon).count() == 7
    assert salon.is_accepting_bookings is False


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


@pytest.mark.django_db
def test_wizard_step_two_requires_completed_first_step_not_created_salon(client):
    from apps.accounts.models import User

    user = User.objects.create_user(phone="+989121000134", full_name="مدیر سالن")
    client.force_login(user)
    step_one = reverse("salons_onboarding:wizard", kwargs={"step": 1})
    step_two = reverse("salons_onboarding:wizard", kwargs={"step": 2})

    direct = client.get(step_two)
    assert direct.status_code == 302
    assert direct.url == step_one

    advance = client.post(step_one, {"name": "سالن نورا"})
    assert advance.status_code == 302
    assert advance.url == step_two
    ready = client.get(step_two)
    assert ready.status_code == 200
    assert "هویت سالن" in ready.content.decode()

@pytest.mark.django_db
def test_unfinished_owner_can_open_dashboard_and_settings(client, owner_membership):
    settings_obj = owner_membership.salon.settings
    settings_obj.onboarding_completed_at = None
    settings_obj.save(update_fields=["onboarding_completed_at"])
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    home = client.get(reverse("dashboard:home"))
    assert home.status_code == 200
    assert home.context["salon_onboarding_auto_open"] is True
    assert 'data-salon-onboarding' in home.content.decode()
    assert 'data-auto-open="true"' in home.content.decode()
    settings_page = client.get(reverse("salons_settings:home"))
    assert settings_page.status_code == 200
    assert 'data-open-salon-onboarding' in settings_page.content.decode()


@pytest.mark.django_db
def test_onboarding_later_persists_without_completing_and_is_owner_only(client, owner_membership):
    from apps.accounts.models import User

    settings_obj = owner_membership.salon.settings
    settings_obj.onboarding_completed_at = None
    settings_obj.save(update_fields=["onboarding_completed_at"])
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    response = client.post(reverse("salons_onboarding:defer"))
    assert response.status_code == 200
    settings_obj.refresh_from_db()
    assert settings_obj.onboarding_deferred_at is not None
    assert settings_obj.onboarding_completed_at is None
    home = client.get(reverse("dashboard:home"))
    assert home.context["salon_onboarding_auto_open"] is False
    assert home.context["salon_onboarding_available"] is True
    assert 'data-auto-open="false"' in home.content.decode()
    employee = User.objects.create_user(phone="+989121000311", full_name="منشی")
    SalonMembership.objects.create(user=employee, salon=owner_membership.salon,
                                   role=SalonMembership.Role.RECEPTIONIST)
    client.force_login(employee)
    assert client.post(reverse("salons_onboarding:defer")).status_code == 403
    assert 'data-salon-onboarding' not in client.get(reverse("dashboard:home")).content.decode()


@pytest.mark.django_db
def test_wizard_modal_partial_redirect_and_resumable_progress(client, owner_membership):
    settings_obj = owner_membership.salon.settings
    settings_obj.onboarding_completed_at = None
    settings_obj.save(update_fields=["onboarding_completed_at"])
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    route = reverse("salons_onboarding:wizard", kwargs={"step": 1}) + "?modal=1"
    opened = client.get(route)
    assert opened.status_code == 200
    html = opened.content.decode()
    assert 'data-onboarding-step="1"' in html
    assert "<html" not in html
    assert 'name="name"' in html
    submitted = client.post(route, {"name": "سالن زیبایی مهتاب"})
    assert submitted.status_code == 302
    assert submitted.url.endswith("/onboarding/wizard/2/?modal=1")
    settings_obj.refresh_from_db()
    assert settings_obj.onboarding_step == 2
    assert client.post(reverse("salons_onboarding:defer")).status_code == 200
    resume = client.get(reverse("salons_settings:home"))
    assert 'data-step-url="/onboarding/wizard/2/?modal=1"' in resume.content.decode()
    next_response = client.get(submitted.url)
    assert next_response.status_code == 200
    assert 'data-onboarding-step="2"' in next_response.content.decode()
    owner_membership.salon.refresh_from_db()
    assert owner_membership.salon.name == "سالن زیبایی مهتاب"


@pytest.mark.django_db
def test_wizard_modal_rejects_non_owner_post_and_get(client, owner_membership):
    from apps.accounts.models import User

    employee = User.objects.create_user(phone="+989121000312", full_name="کارمند")
    SalonMembership.objects.create(user=employee, salon=owner_membership.salon,
                                   role=SalonMembership.Role.RECEPTIONIST)
    client.force_login(employee)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    route = reverse("salons_onboarding:wizard", kwargs={"step": 1}) + "?modal=1"
    assert client.get(route).status_code == 403
    assert client.post(route, {"name": "سالن دیگر"}).status_code == 403


@pytest.mark.django_db
def test_defer_onboarding_requires_csrf(client, owner_membership):
    from django.test import Client

    settings_obj = owner_membership.salon.settings
    settings_obj.onboarding_completed_at = None
    settings_obj.save(update_fields=["onboarding_completed_at"])
    secured = Client(enforce_csrf_checks=True)
    secured.force_login(owner_membership.user)
    assert secured.post(reverse("salons_onboarding:defer")).status_code == 403

@pytest.mark.django_db
def test_wizard_owner_not_created_as_specialist_on_get_or_skip(client, owner_membership):
    salon = owner_membership.salon
    settings_obj = salon.settings
    settings_obj.onboarding_completed_at = None
    settings_obj.save(update_fields=["onboarding_completed_at"])
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()

    staff_step = reverse("salons_onboarding:wizard", kwargs={"step": 4})
    rendered = client.get(staff_step + "?modal=1")
    assert rendered.status_code == 200
    assert 'data-onboarding-step="4"' in rendered.content.decode()
    assert "مالک سالن لازم نیست متخصص باشد" in rendered.content.decode()
    assert not StaffProfile.objects.filter(membership=owner_membership).exists()
    skipped = client.post(staff_step, {"action": "skip"})
    assert skipped.status_code == 302
    assert not StaffProfile.objects.filter(membership=owner_membership).exists()

    hours_step = reverse("salons_onboarding:wizard", kwargs={"step": 5})
    assert client.get(hours_step).status_code == 200
    assert not StaffProfile.objects.filter(membership=owner_membership).exists()
    assert client.post(hours_step, {"action": "skip"}).status_code == 302
    assert SalonWorkHours.objects.filter(salon=salon).count() == 7
    assert not StaffProfile.objects.filter(membership=owner_membership).exists()
    assert not StaffWorkHours.objects.filter(salon=salon).exists()


@pytest.mark.django_db
def test_wizard_explicit_specialist_opt_in_preserves_services(client, owner_membership):
    salon = owner_membership.salon
    salon.settings.onboarding_completed_at = None
    salon.settings.save(update_fields=["onboarding_completed_at"])
    service = Service.objects.create(
        salon=salon, name="فیشیال", duration_minutes=45,
        price_toman=750000, is_active=True, is_public=True,
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    route = reverse("salons_onboarding:wizard", kwargs={"step": 4})
    response = client.post(route, {
        "display_name": "نیلوفر", "title": "متخصص پوست",
        "is_bookable": "on", "services": [str(service.pk)],
    })
    assert response.status_code == 302
    profile = StaffProfile.objects.get(membership=owner_membership)
    assert profile.display_name == "نیلوفر"
    assert profile.title == "متخصص پوست"
    assert profile.is_bookable
    assert list(profile.services.values_list("pk", flat=True)) == [service.pk]

    hours_step = reverse("salons_onboarding:wizard", kwargs={"step": 5})
    assert client.post(hours_step, {"action": "skip"}).status_code == 302
    assert StaffWorkHours.objects.filter(staff=profile).count() == 7


@pytest.mark.django_db
def test_finishing_onboarding_never_silently_enables_public_booking(client, owner_membership):
    salon = owner_membership.salon
    salon.is_accepting_bookings = False
    salon.save(update_fields=["is_accepting_bookings"])
    salon.settings.onboarding_completed_at = None
    salon.settings.save(update_fields=["onboarding_completed_at"])
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    complete = client.post(reverse("salons_onboarding:wizard", kwargs={"step": 6}))
    assert complete.status_code == 302
    assert complete.url == reverse("dashboard:home")
    salon.refresh_from_db()
    assert salon.settings.onboarding_completed_at is not None
    assert not salon.is_accepting_bookings
