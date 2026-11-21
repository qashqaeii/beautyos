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
    assert table_html.count('href="/staff/') >= 8
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
