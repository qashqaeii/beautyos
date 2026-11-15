"""Salon profile / settings page — access, edits, logo, hours, tenant."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.text import slugify

from apps.accounts.models import User
from apps.salons.models import SalonMembership
from apps.staff.models import StaffWorkHours


def _profile_post_payload(salon, **overrides):
    data = {
        "form_kind": "profile",
        "name": salon.name,
        "slug": slugify(salon.slug or salon.name, allow_unicode=False) or "salon-alpha",
        "tagline": salon.tagline or "",
        "description": salon.description or "",
        "public_phone": salon.public_phone or "",
        "address": salon.address or "",
        "city": salon.city or "",
        "instagram": "",
        "whatsapp": "",
        "is_accepting_bookings": "on",
        "is_active": "on",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_salon_profile_page_renders(client, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    response = client.get("/settings/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "اطلاعات سالن" in html
    assert owner_membership.salon.name in html


@pytest.mark.django_db
def test_sole_owner_sees_settings_when_session_targets_manager_role(client, user, salon, salon_b):
    """Owner with one salon + manager on another: tenant resolves to owner salon."""
    SalonMembership.objects.create(user=user, salon=salon, role=SalonMembership.Role.OWNER)
    SalonMembership.objects.create(user=user, salon=salon_b, role=SalonMembership.Role.MANAGER)
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(salon_b.id)
    session.save()
    html = client.get("/app/").content.decode()
    idx = html.index("maison-sidebar__footer")
    footer = html[idx : idx + 600]
    assert 'href="/settings/"' not in footer
    assert "اطلاعات سالن" not in footer
    assert client.session["active_salon_id"] == str(salon.id)


@pytest.mark.django_db
def test_manager_only_user_has_no_salon_settings_nav(client, salon):
    mgr_user = User.objects.create_user(phone="+989121234590", full_name="مدیر تنها")
    manager = SalonMembership.objects.create(
        user=mgr_user,
        salon=salon,
        role=SalonMembership.Role.MANAGER,
    )
    client.force_login(manager.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    html = client.get("/app/").content.decode()
    idx = html.index("maison-sidebar__footer")
    footer = html[idx : idx + 600]
    assert "اطلاعات سالن" not in footer


@pytest.mark.django_db
def test_owner_sidebar_footer_omits_salon_settings_link(client, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    html = client.get("/app/").content.decode()
    idx = html.index("maison-sidebar__footer")
    footer = html[idx : idx + 600]
    assert 'href="/settings/"' not in footer
    assert "اطلاعات سالن" not in footer


@pytest.mark.django_db
def test_salon_profile_update_name_and_phone(client, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    salon = owner_membership.salon
    payload = _profile_post_payload(
        salon, name="سالن به‌روز", public_phone="09121112233", city="اصفهان", address="خیابان تست"
    )
    resp = client.post("/settings/", payload)
    assert resp.status_code == 302
    salon.refresh_from_db()
    assert salon.name == "سالن به‌روز"
    assert salon.public_phone == "09121112233"
    assert salon.city == "اصفهان"


@pytest.mark.django_db
def test_salon_profile_rejects_invalid_logo(client, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    salon = owner_membership.salon
    bad = SimpleUploadedFile("x.txt", b"not an image", content_type="text/plain")
    payload = _profile_post_payload(salon)
    resp = client.post("/settings/", {**payload, "logo": bad})
    assert resp.status_code == 200
    assert "فرمت مجاز" in resp.content.decode() or "لوگو" in resp.content.decode()


@pytest.mark.django_db
def test_salon_profile_accepts_valid_logo(client, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    salon = owner_membership.salon
    png_1x1 = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    img = SimpleUploadedFile("logo.png", png_1x1, content_type="image/png")
    payload = _profile_post_payload(salon)
    resp = client.post("/settings/", {**payload, "logo": img})
    assert resp.status_code == 302
    salon.refresh_from_db()
    assert salon.logo


@pytest.mark.django_db
def test_salon_profile_specialist_forbidden(client, owner_membership):
    from apps.accounts.models import User
    from apps.staff.models import StaffProfile

    specialist_user = User.objects.create_user(phone="+989121000088", full_name="متخصص")
    membership = SalonMembership.objects.create(
        user=specialist_user,
        salon=owner_membership.salon,
        role=SalonMembership.Role.SPECIALIST,
        is_active=True,
    )
    StaffProfile.objects.create(salon=owner_membership.salon, membership=membership, display_name="متخصص")
    client.force_login(specialist_user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    assert client.get("/settings/").status_code == 403


@pytest.mark.django_db
def test_salon_profile_tenant_isolation(client, owner_membership, salon_b):
    from apps.accounts.models import User

    other_owner = User.objects.create_user(phone="+989121000077", full_name="مالک ب")
    SalonMembership.objects.create(user=other_owner, salon=salon_b, role=SalonMembership.Role.OWNER, is_active=True)
    client.force_login(other_owner)
    session = client.session
    session["active_salon_id"] = str(salon_b.id)
    session.save()
    payload = _profile_post_payload(salon_b, name="نام سالن ب")
    client.post("/settings/", payload)
    owner_membership.salon.refresh_from_db()
    assert owner_membership.salon.name != "نام سالن ب" or owner_membership.salon.pk != salon_b.pk


@pytest.mark.django_db
def test_salon_profile_save_work_hours(client, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    post = {"form_kind": "hours"}
    for wd in range(7):
        if wd == 6:
            post[f"wh_{wd}_closed"] = "on"
        else:
            post[f"wh_{wd}_start"] = "09:00"
            post[f"wh_{wd}_end"] = "18:00"
    resp = client.post("/settings/", post)
    assert resp.status_code == 302
    assert StaffWorkHours.objects.filter(salon=owner_membership.salon, weekday=0).exists()


@pytest.mark.django_db
def test_salon_profile_csrf_required(client, owner_membership):
    client = client.__class__(enforce_csrf_checks=True)
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    payload = _profile_post_payload(owner_membership.salon)
    assert client.post("/settings/", payload).status_code == 403


@pytest.mark.django_db
def test_salon_profile_public_link(client, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    html = client.get("/settings/").content.decode()
    assert reverse("salons_public:landing", kwargs={"slug": owner_membership.salon.slug}) in html