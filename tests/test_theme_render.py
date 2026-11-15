from pathlib import Path

import pytest
from django.test import Client

from apps.salons.models import SalonSettings


@pytest.mark.django_db
def test_dashboard_html_data_theme_luna(owner_membership, client: Client):
    owner_membership.salon.settings.dashboard_theme = SalonSettings.DashboardTheme.ROSE_ATELIER
    owner_membership.salon.settings.save()
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon.id)
    session.save()
    client.force_login(owner_membership.user)
    response = client.get("/app/")
    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-theme="luna_signature"' in html


@pytest.mark.django_db
def test_built_css_contains_luna_theme_block():
    css = (Path(__file__).resolve().parents[1] / "static" / "css" / "beautyos.css").read_text(encoding="utf-8")
    css_lower = css.lower()
    assert "luna_signature" in css_lower
    assert "f5f0ec" in css_lower or "b58d89" in css_lower or "51443f" in css_lower
