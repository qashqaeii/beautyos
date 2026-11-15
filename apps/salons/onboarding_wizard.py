from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from django.utils.text import slugify

from apps.salons.business_catalog import presets_for
from apps.salons.models import Salon, SalonMembership, SalonSettings
from apps.salons.themes import BUSINESS_TYPE_DEFAULTS
from apps.services.models import Service


SESSION_SALON_KEY = "onboarding_salon_id"
SESSION_BUSINESS_TYPE = "onboarding_business_type"
SESSION_CUSTOM_SERVICES = "onboarding_custom_services"


def salon_needs_onboarding(salon: Salon | None) -> bool:
    if salon is None:
        return True
    settings = getattr(salon, "settings", None)
    if settings is None:
        return True
    return settings.onboarding_completed_at is None


def apply_business_defaults(salon: Salon, business_type: str) -> None:
    dashboard_key, public_key = BUSINESS_TYPE_DEFAULTS.get(
        business_type,
        BUSINESS_TYPE_DEFAULTS[Salon.BusinessType.COMBINED],
    )
    salon.business_type = business_type
    salon.public_theme = public_key
    salon.save(update_fields=["business_type", "public_theme", "updated_at"])
    settings, _ = SalonSettings.objects.get_or_create(salon=salon)
    settings.dashboard_theme = dashboard_key
    settings.save(update_fields=["dashboard_theme", "updated_at"])


@transaction.atomic
def create_salon_for_owner(user, *, name, slug, public_phone, city, address, tagline, description, business_type, logo=None):
    salon = Salon(
        name=name,
        slug=slugify(slug) if slug else "",
        public_phone=public_phone or "",
        city=city or "",
        address=address or "",
        tagline=tagline or "",
        description=description or "",
        business_type=business_type,
    )
    if logo:
        salon.logo = logo
    salon.save()
    SalonSettings.objects.get_or_create(salon=salon)
    SalonMembership.objects.create(user=user, salon=salon, role=SalonMembership.Role.OWNER)
    apply_business_defaults(salon, business_type)
    return salon


@transaction.atomic
def create_selected_services(salon: Salon, selected_keys: list[str], custom_rows: list[dict]) -> int:
    """selected_keys are indexes as strings matching preset list."""
    presets = presets_for(salon.business_type)
    created = 0
    for key in selected_keys:
        try:
            idx = int(key)
            row = presets[idx]
        except (ValueError, IndexError):
            continue
        if Service.scoped(salon).filter(name=row["name"], is_deleted=False).exists():
            continue
        Service.objects.create(
            salon=salon,
            name=row["name"],
            duration_minutes=row["duration_minutes"],
            price_toman=row["price_toman"],
            is_active=True,
            is_public=True,
        )
        created += 1
    for row in custom_rows:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        if Service.scoped(salon).filter(name=name, is_deleted=False).exists():
            continue
        Service.objects.create(
            salon=salon,
            name=name,
            duration_minutes=int(row.get("duration_minutes") or 30),
            price_toman=int(row.get("price_toman") or 0),
            is_active=True,
            is_public=True,
        )
        created += 1
    return created


def complete_onboarding(salon: Salon) -> None:
    settings = salon.settings
    settings.onboarding_completed_at = timezone.now()
    settings.save(update_fields=["onboarding_completed_at", "updated_at"])
