from pathlib import Path

import pytest
from django.test import Client

from apps.salons.models import SalonSettings
from apps.salons.themes import DashboardTheme, GLOBAL_DASHBOARD_THEME, resolve_salon_dashboard_theme


@pytest.mark.django_db
def test_resolver_ignores_stored_dashboard_theme(owner_membership):
    owner_membership.salon.settings.dashboard_theme = SalonSettings.DashboardTheme.SIGNATURE_NEUTRAL
    owner_membership.salon.settings.save()
    assert resolve_salon_dashboard_theme(owner_membership.salon) == GLOBAL_DASHBOARD_THEME


@pytest.mark.django_db
def test_dashboard_html_luna_for_neutral_db_theme(owner_membership, client: Client):
    owner_membership.salon.settings.dashboard_theme = SalonSettings.DashboardTheme.SIGNATURE_NEUTRAL
    owner_membership.salon.settings.save()
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon.id)
    session.save()
    client.force_login(owner_membership.user)
    html = client.get("/app/").content.decode()
    assert 'data-theme="luna_signature"' in html


@pytest.mark.django_db
def test_dashboard_sidebar_omits_salon_switcher(owner_membership, client: Client):
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon.id)
    session.save()
    client.force_login(owner_membership.user)
    response = client.get("/app/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "maison-sidebar-switcher" not in html
    assert "maison-sidebar__salon-row" not in html
    assert "app-salon-chip" not in html


@pytest.mark.django_db
def test_dashboard_luna_after_salon_switch(owner_membership, client: Client, salon_b):
    from apps.salons.models import SalonMembership

    SalonMembership.objects.create(user=owner_membership.user, salon=salon_b, role=SalonMembership.Role.OWNER)
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon.id)
    session.save()
    assert 'data-theme="luna_signature"' in client.get("/app/").content.decode()
    session["active_salon_id"] = str(salon_b.id)
    session.save()
    assert 'data-theme="luna_signature"' in client.get("/app/").content.decode()


@pytest.mark.django_db
def test_public_landing_luna_palette(client: Client, owner_membership):
    slug = owner_membership.salon.slug
    html = client.get(f"/s/{slug}/").content.decode()
    assert 'data-theme="luna_signature"' in html


@pytest.mark.django_db
def test_settings_preserves_stored_theme_without_picker(client: Client, user, owner_membership):
    stored = owner_membership.salon.settings.dashboard_theme
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon.id)
    session.save()
    html = client.get("/settings/").content.decode()
    assert "اطلاعات سالن" in html
    assert 'data-theme="luna_signature"' in html
    assert "dashboard_theme" not in html
    owner_membership.salon.settings.refresh_from_db()
    assert owner_membership.salon.settings.dashboard_theme == stored


@pytest.mark.django_db
def test_built_css_contains_luna_signature_token():
    css = (Path(__file__).resolve().parents[1] / "static" / "css" / "beautyos.css").read_text(encoding="utf-8")
    css_lower = css.lower()
    assert "luna_signature" in css_lower
    assert "f5f0ec" in css_lower or "b58d89" in css_lower or "51443f" in css_lower


def test_global_theme_constant():
    assert GLOBAL_DASHBOARD_THEME == DashboardTheme.LUNA_SIGNATURE
