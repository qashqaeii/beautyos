"""Salon storefronts: one branded editorial layout with tenant-safe public data."""
import re
from urllib.parse import urlparse

from django.shortcuts import get_object_or_404, render

from apps.core.utils.phone import normalize_iran_mobile
from apps.portfolio.models import PortfolioItem
from apps.salons.models import Salon, SalonSettings, SalonWorkHours
from apps.salons.themes import css_variables_inline_public
from apps.services.models import Service
from apps.staff.models import StaffProfile
from apps.website.seo import meta, salon_schema


_THEME_TEMPLATES = {
    Salon.PublicTheme.ELEGANT_BEAUTY: "public/themes/elegant_beauty.html",
    Salon.PublicTheme.MODERN_BARBER: "public/themes/modern_barber.html",
    Salon.PublicTheme.MINIMAL_STUDIO: "public/themes/minimal_studio.html",
}


def _telephone_href(raw):
    digits = re.sub(r"[\s()\-]", "", (raw or "").strip())
    return "tel:" + digits if re.fullmatch(r"\+?[0-9]{8,15}", digits) else None


def _instagram_url(raw):
    raw = (raw or "").strip().lstrip("@")
    if re.fullmatch(r"[A-Za-z0-9._]{1,30}", raw):
        return f"https://www.instagram.com/{raw}/"
    parsed = urlparse(raw)
    if parsed.scheme == "https" and parsed.hostname in ("instagram.com", "www.instagram.com"):
        return raw
    return None


def _whatsapp_url(raw):
    raw = (raw or "").strip()
    try:
        number = normalize_iran_mobile(raw)
        return f"https://wa.me/{number.removeprefix('+')}"
    except ValueError:
        parsed = urlparse(raw)
        if parsed.scheme == "https" and parsed.hostname in ("wa.me", "api.whatsapp.com"):
            return raw
    return None


def public_landing(request, slug):
    salon = get_object_or_404(Salon, slug=slug, is_active=True)
    services = list(Service.scoped(salon).filter(
        is_active=True, is_public=True, is_deleted=False,
    ).order_by("name")[:60])
    staff = list(StaffProfile.scoped(salon).filter(
        is_active=True, is_bookable=True, is_deleted=False,
    ).order_by("display_name")[:30])
    portfolio = list(PortfolioItem.scoped(salon).filter(
        is_published=True, is_deleted=False,
    ).order_by("-created_at")[:12])
    hours = list(SalonWorkHours.objects.filter(salon=salon).order_by("weekday"))
    onboarding_done = SalonSettings.objects.filter(
        salon=salon, onboarding_completed_at__isnull=False,
    ).exists()
    template = _THEME_TEMPLATES.get(
        salon.public_theme, _THEME_TEMPLATES[Salon.PublicTheme.MINIMAL_STUDIO]
    )
    description = (
        salon.description or salon.tagline
        or f"معرفی خدمات، متخصصان، ساعات فعالیت و رزرو آنلاین {salon.name}"
    )
    return render(request, template, {
        "salon": salon,
        "services": services,
        "staff_list": staff,
        "portfolio": portfolio,
        "salon_hours": hours,
        "salon_phone_href": _telephone_href(salon.public_phone),
        "salon_instagram_url": _instagram_url(salon.instagram),
        "salon_whatsapp_url": _whatsapp_url(salon.whatsapp),
        "public_theme_style": css_variables_inline_public(),
        **meta(
            request,
            f"{salon.name} | خدمات و رزرو آنلاین",
            description,
            canonical=salon.get_public_url(),
            schema=salon_schema(request, salon, services),
            image=salon.cover_image.url if salon.cover_image else None,
            robots=(
                "index,follow" if salon.is_accepting_bookings and onboarding_done
                else "noindex,follow"
            ),
        ),
    })
