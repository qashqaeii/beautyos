from django.urls import reverse

from apps.salons.models import SalonMembership


def home_url_for_role(role: str) -> str:
    return reverse("dashboard:home")
