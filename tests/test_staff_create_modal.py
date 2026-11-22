import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_staff_create_get_redirects_to_list_modal(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    response = client.get(reverse("staff:create"))
    assert response.status_code == 302
    assert response.url.endswith("/staff/?create=1") or "create=1" in response.url


@pytest.mark.django_db
def test_staff_list_create_query_opens_modal(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    response = client.get(reverse("staff:list"), {"create": "1"})
    assert response.status_code == 200
    html = response.content.decode()
    assert "staff-create-modal-title" in html
    assert "createOpen" in html and "x-show=\"createOpen\"" in html


@pytest.mark.django_db
def test_staff_create_post_invalid_reopens_modal(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    response = client.post(reverse("staff:create"), {"first_name": "", "last_name": "", "specialty": "", "phone": ""})
    assert response.status_code == 200
    html = response.content.decode()
    assert "staff-team-page" in html
    assert "staff-create-modal-title" in html


@pytest.mark.django_db
def test_staff_invite_editorial_modal_keeps_existing_fields(client, owner_membership, salon):
    from django.contrib.staticfiles import finders
    from django.urls import reverse

    client.force_login(owner_membership.user)
    response = client.get(reverse("staff:list"), {"create": "1"})
    assert response.status_code == 200
    html = response.content.decode()
    assert "luna-modal--staff-invite" in html
    assert 'aria-describedby="staff-create-modal-description"' in html
    assert "luna-modals.css" in html
    assert "luna-modals.js" in html
    assert "staff-create-form" in html
    for field_name in ("first_name", "last_name", "specialty", "phone"):
        assert f'name="{field_name}"' in html
    assert finders.find("css/luna-modals.css")
    assert finders.find("js/luna-modals.js")
    assert finders.find("images/photos/beautyos-modal-salon.webp")


@pytest.mark.django_db
def test_staff_directory_balanced_grid_and_paginated_table(
    client, owner_membership, salon
):
    from django.contrib.staticfiles import finders
    from django.contrib.auth import get_user_model
    from apps.salons.models import SalonMembership
    from apps.staff.models import StaffProfile
    from pathlib import Path

    for index in range(9):
        user = get_user_model().objects.create_user(
            phone=f"+98912123{index:04d}", full_name=f"کارشناس سالن {index}"
        )
        membership = SalonMembership.objects.create(
            salon=salon, user=user, role=SalonMembership.Role.SPECIALIST
        )
        StaffProfile.objects.create(
            salon=salon, membership=membership, display_name=f"متخصص {index}",
            title="مراقبت و زیبایی"
        )

    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()

    card = client.get(reverse("staff:list"), {"view": "card"})
    assert card.status_code == 200
    html = card.content.decode()
    assert "staff-viewport.css" in html
    assert "staff-board-v2--balanced" in html
    assert html.count('class="staff-team-card suite-staff-card staff-board-card"') == 6
    assert "staff-board-pagination" in html
    assert "staff-create-modal-title" in html

    table = client.get(reverse("staff:list"), {"view": "table"})
    assert table.status_code == 200
    table_html = table.content.decode()
    assert "staff-board-v2--table-balanced" in table_html
    assert table_html.count('href="/staff/') >= 6
    assert table_html.count('class="staff-team-card suite-staff-card staff-board-card"') == 0
    assert 'aria-label="جدول متخصصان"' in table_html
    second = client.get(reverse("staff:list"), {"view": "table", "page": 2})
    assert second.status_code == 200
    assert "staff-board-v2--table-balanced" not in second.content.decode()

    css_path = finders.find("css/staff-viewport.css")
    assert css_path
    css = Path(css_path).read_text(encoding="utf-8")
    assert "100dvh" in css
    assert "minmax(max-content,1fr)" in css
    assert "overflow:visible" in css


@pytest.mark.django_db
def test_staff_invite_specialty_dropdown_uses_active_salon_services_only(
    client, owner_membership, salon,
):
    from apps.services.models import Service
    from apps.salons.models import Salon
    from django.utils.html import escape

    current = Service.objects.create(salon=salon, name="رنگ و لایت")
    second = Service.objects.create(salon=salon, name="میکاپ عروس")
    inactive = Service.objects.create(salon=salon, name="خدمت غیرفعال", is_active=False)
    deleted = Service.objects.create(salon=salon, name="خدمت حذف‌شده", is_deleted=True)
    other_salon = Salon.objects.create(name="سالن مستقل")
    foreign = Service.objects.create(salon=other_salon, name="خدمت سالن دیگر")

    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    response = client.get(reverse("staff:list"), {"create": "1"})
    assert response.status_code == 200
    html = response.content.decode()
    assert '<select name="specialty"' in html or 'name="specialty"' in html
    assert f'value="{current.pk}"' in html
    assert f'value="{second.pk}"' in html
    assert "رنگ و لایت" in html and "میکاپ عروس" in html
    for item in (inactive, deleted, foreign):
        assert f'value="{item.pk}"' not in html
    assert "staff-invite-service-select" in html


@pytest.mark.django_db
def test_staff_invite_selected_service_persisted_until_acceptance(
    client, owner_membership, salon,
):
    from apps.accounts.models import User
    from apps.services.models import Service
    from apps.salons import invitations
    from apps.salons.models import SalonInvitation
    from apps.staff.models import StaffProfile

    service = Service.objects.create(salon=salon, name="رنگ و لایت")
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    response = client.post(reverse("staff:create"), {
        "first_name": "مریم", "last_name": "احمدی",
        "phone": "09123459001", "specialty": str(service.pk),
    })
    assert response.status_code == 302
    invite = SalonInvitation.objects.get(salon=salon, phone="+989123459001")
    assert invite.invitee_service_id == service.pk
    assert invite.invitee_specialty == service.name
    invitee = User.objects.create_user(phone=invite.phone, full_name="")
    membership = invitations.accept_invitation(invite.token, invitee)
    profile = StaffProfile.objects.get(membership=membership)
    assert profile.title == service.name
    assert list(profile.services.values_list("pk", flat=True)) == [service.pk]


@pytest.mark.django_db
def test_staff_invite_rejects_other_salon_and_inactive_service(
    client, owner_membership, salon,
):
    from apps.salons.models import Salon, SalonInvitation
    from apps.services.models import Service

    active = Service.objects.create(salon=salon, name="براشینگ")
    inactive = Service.objects.create(salon=salon, name="خدمت غیرفعال", is_active=False)
    foreign_salon = Salon.objects.create(name="سالن دیگر")
    foreign = Service.objects.create(salon=foreign_salon, name="رنگ مو")
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    for pk in (inactive.pk, foreign.pk, 999999):
        response = client.post(reverse("staff:create"), {
            "first_name": "مریم", "last_name": "رضایی",
            "phone": "09123459002", "specialty": str(pk),
        })
        assert response.status_code == 200
        assert 'name="specialty"' in response.content.decode()
        assert "خدمت انتخاب‌شده معتبر" in response.content.decode()
    assert not SalonInvitation.objects.filter(phone="+989123459002").exists()
    # A valid selection still works after an invalid submission.
    response = client.post(reverse("staff:create"), {
        "first_name": "مریم", "last_name": "رضایی",
        "phone": "09123459002", "specialty": str(active.pk),
    })
    assert response.status_code == 302


@pytest.mark.django_db
def test_staff_invite_without_services_offers_link_to_services(
    client, owner_membership, salon,
):
    from apps.services.models import Service

    assert not Service.scoped(salon).filter(is_active=True, is_deleted=False).exists()
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    response = client.get(reverse("staff:list"), {"create": "1"})
    assert response.status_code == 200
    assert "خدمتی برای انتخاب ثبت نشده است" in response.content.decode()
    assert reverse("services:list") in response.content.decode()
