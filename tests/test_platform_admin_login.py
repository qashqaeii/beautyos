"""Dedicated platform login routing and authorization regression."""
import pytest
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_anonymous_central_entry_uses_platform_login(client):
    response = client.get(reverse("platform_admin:overview"))
    assert response.status_code == 302
    assert response.url == reverse("platform_admin:login")
    page = client.get(reverse("platform_admin:login"))
    assert page.status_code == 200
    assert "مدیریت مرکزی" in page.content.decode()


@pytest.mark.django_db
def test_salon_account_cannot_use_central_login(client):
    salon_user = User.objects.create_user(phone="+989111110001", full_name="مدیر سالن")
    client.force_login(salon_user)
    assert client.get(reverse("platform_admin:overview")).status_code == 403
    assert client.get(reverse("platform_admin:login")).status_code == 200
    assert client.post(reverse("platform_admin:login"), {"step": "phone", "phone": "09111110001"}).status_code == 403


@pytest.mark.django_db
def test_superuser_without_salon_reaches_control(client):
    user = User.objects.create_superuser(phone="+989111110002", password="test-only-password")
    client.force_login(user)
    assert client.get(reverse("platform_admin:login")).url == reverse("platform_admin:overview")
    assert client.get(reverse("platform_admin:overview")).status_code == 200
