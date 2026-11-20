import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_public_home_anonymous(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "ثبت‌نام سالن" in html
    assert "مدیریت هوشمند سالن زیبایی" in html
    assert "در یک پلتفرم کامل" in html
    assert "luna-home-hero.css" in html
    assert "images/logos/beautyos-logo-3d.webp" in html
    assert "images/logos/Logo.webp" not in html
    assert "luna-hero__features" in html
    assert html.count('class="luna-hero-feature"') == 4
    assert html.count('class="luna-hero-feature__icon"') == 4
    assert html.count('class="luna-hero-feature__label"') == 4
    assert "باشگاه مشتریان" in html
    assert "public-announcement" not in html
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

@pytest.mark.django_db
def test_home_selects_available_hero_asset(client, monkeypatch):
    from apps.website import views

    monkeypatch.setattr(views.finders, "find", lambda name: "/tmp/luna-salon-hero.webp")
    response = client.get("/")
    assert response.status_code == 200
    assert response.context["hero_image_path"] == "images/photos/luna-salon-hero.webp"
    assert not response.context["hero_image_is_fallback"]


@pytest.mark.django_db
def test_home_fallback_when_hero_asset_is_missing(client, monkeypatch):
    from apps.website import views

    monkeypatch.setattr(views.finders, "find", lambda name: None)
    response = client.get("/")
    assert response.status_code == 200
    assert response.context["hero_image_is_fallback"]
    assert "Sunlit" in response.content.decode()
    assert "lavender_glow_beauty_portrait.webp" not in response.content.decode()


def test_beautyos_brand_asset_exists():
    from django.contrib.staticfiles import finders

    assert finders.find("images/logos/beautyos-logo-3d.webp")


@pytest.mark.django_db
def test_home_approved_hero_is_versioned_and_rendered(client):
    from django.contrib.staticfiles import finders
    from pathlib import Path

    asset = finders.find("images/photos/luna-salon-hero.webp")
    assert asset and Path(asset).read_bytes()[8:12] == b"WEBP"
    response = client.get("/")
    assert response.status_code == 200
    assert not response.context["hero_image_is_fallback"]
    html = response.content.decode()
    assert "luna-hero__curves" in html
    assert "راهکار تخصصی مدیریت سالن‌های زیبایی" in html
    assert "lavender_glow_beauty_portrait.webp" not in html
    assert reverse("accounts:register") in html
