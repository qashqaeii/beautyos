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
