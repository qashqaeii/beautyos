import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_public_home_anonymous(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "ثبت‌نام سالن" in html
    assert "آرامش لوکس" in html
    assert "رزرو و نوبت‌دهی آنلاین" in html
    assert reverse("accounts:login") in html or "/auth/login/" in html


@pytest.mark.django_db
def test_public_features(client):
    assert client.get("/features/").status_code == 200


@pytest.mark.django_db
def test_dashboard_moved_to_app(client, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon.id)
    session.save()
    assert client.get("/app/").status_code == 200
    assert client.get("/").status_code == 200


@pytest.mark.django_db
def test_logout_post_redirects_home(client, owner_membership):
    client.force_login(owner_membership.user)
    response = client.post(reverse("accounts:logout"))
    assert response.status_code == 302
    assert response.url == reverse("website:home")
    follow = client.get(response.url)
    assert follow.status_code == 200