import pytest
from django.urls import reverse

from apps.services.models import Service, ServiceCategory


@pytest.mark.django_db
def test_create_service_sets_defaults(client, owner_membership, salon):
    user = owner_membership.user
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    url = reverse("services:create")
    response = client.post(
        url,
        {
            "intent": "save_service",
            "name": "ژلیش",
            "description": "",
            "price_toman": "250000",
            "is_active": "on",
            "is_public": "on",
        },
    )
    assert response.status_code == 302
    service = Service.objects.get(salon=salon, name="ژلیش")
    assert service.duration_minutes == 30
    assert service.is_active is True


@pytest.mark.django_db
def test_inline_category_duplicate_name(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    ServiceCategory.objects.create(salon=salon, name="خدمات ناخن")

    url = reverse("services:create")
    response = client.post(
        url,
        {
            "intent": "add_category",
            "new_category_name": "خدمات ناخن",
            "name": "ژلیش",
            "price_toman": "100000",
        },
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "قبلاً ثبت شده" in html
    assert "services-page" in html


@pytest.mark.django_db
def test_service_directory_uses_premium_hero_and_preserves_modal_actions(client, owner_membership, salon):
    from django.contrib.staticfiles import finders
    from pathlib import Path
    client.force_login(owner_membership.user)
    session=client.session
    session["active_salon_id"]=str(salon.id)
    session.save()

    for i in range(9):
        Service.objects.create(salon=salon, name=f"خدمت سالن {i}", price_toman=100_000+i*10_000)

    response=client.get(reverse("services:list"))
    assert response.status_code==200
    html=response.content.decode()
    assert 'services-hero' in html
    assert "services-catalog-hero.svg" in html
    assert "services-premium.css" in html
    assert "services-page--full-grid" in html
    assert html.count('class="maison-service-card suite-service-card services-card"') == 9
    assert 'service-create-modal-title' in html
    assert 'luna-service-paired-grid' in html
    assert 'luna-modal--service' in html
    assert 'service-edit-form' in client.get(reverse("services:list")+"?edit="+str(Service.objects.filter(salon=salon).first().pk)).content.decode()
    css_path=finders.find("css/services-premium.css")
    illustration_path=finders.find("images/services-catalog-hero.svg")
    assert css_path and illustration_path
    css=Path(css_path).read_text(encoding="utf-8")
    assert "100dvh" in css and "grid-template-rows:repeat(3" in css


@pytest.mark.django_db
def test_service_price_uses_shared_grouped_money_widget(salon):
    from apps.core.widgets import TomanAmountWidget
    from apps.services.forms import ServiceCreateForm, ServiceForm
    for form_class in (ServiceCreateForm, ServiceForm):
        form = form_class(salon=salon)
        assert isinstance(form.fields["price_toman"].widget, TomanAmountWidget)
        assert 'data-show-zero="true"' in str(form["price_toman"])
    for amount in ("850000", "0"):
        form = ServiceCreateForm({"name": "خدمت", "price_toman": amount}, salon=salon)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["price_toman"] == int(amount)
