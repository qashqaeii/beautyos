import pytest
from django.urls import reverse
from django.contrib.staticfiles import finders

from apps.packages.models import ServicePackage
from apps.portfolio.models import PortfolioItem


@pytest.mark.django_db
def test_phase1_package_directory_uses_single_hero_and_real_cards(client, owner_membership, salon):
    ServicePackage.objects.create(
        salon=salon, name="پکیج فاز یک", price_toman=3500000,
        session_count=5, validity_days=45, is_active=True,
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    response = client.get(reverse("packages:list"))
    assert response.status_code == 200
    html = response.content.decode()
    assert html.count("<h1") == 1
    assert "phase1-directory--packages" in html
    assert "phase1-catalog.css" in html
    assert "پکیج فاز یک" in html
    assert 'class="phase1-directory__card"' in html
    assert reverse("packages:create") in html
    assert reverse("packages:sell") in html


@pytest.mark.django_db
def test_phase1_portfolio_directory_preserves_publish_status_and_pager(client, owner_membership, salon):
    for index in range(7):
        PortfolioItem.objects.create(
            salon=salon, title=f"نمونه‌کار {index}",
            is_published=(index % 2 == 0),
            image=f"portfolio/sample-{index}.webp",
        )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    response = client.get(reverse("portfolio:list"))
    assert response.status_code == 200
    html = response.content.decode()
    assert html.count("<h1") == 1
    assert "phase1-directory--portfolio" in html
    assert 'class="phase1-directory__gallery"' in html
    assert html.count('class="phase1-directory__gallery-card"') == 6
    assert 'نمونه‌کارهای ثبت‌شده' in html
    assert 'پیش‌نویس' in html
    assert 'منتشر' in html
    assert reverse("portfolio:create") in html
    assert "/edit/" in html
    assert 'aria-label="صفحه‌بندی"' in html
    assert 'page=2' in html
    assert finders.find("css/phase1-catalog.css")


@pytest.mark.django_db
def test_phase1_portfolio_empty_state_keeps_create_action(client, owner_membership):
    client.force_login(owner_membership.user)
    response = client.get(reverse("portfolio:list"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "گالری خالی است" in html
    assert reverse("portfolio:create") in html
    assert "phase1-directory--portfolio" in html
