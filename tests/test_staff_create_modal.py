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
