"""Strip legacy ``[دمو]`` markers from user-visible fields on demo salons."""

from __future__ import annotations

import re

from django.db.models import Q

from apps.customers.models import Customer, CustomerTag
from apps.inventory.models import InventoryItem
from apps.packages.models import ServicePackage
from apps.portfolio.models import PortfolioItem
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile

from apps.core.demo_seed.personas import BARBER_CUSTOMERS, BEAUTY_CUSTOMERS

DEMO_LEGACY_PREFIX = "[دمو]"

_DEMO_LABEL_RE = re.compile(
    rf"^\s*{re.escape(DEMO_LEGACY_PREFIX)}\s*|\s*{re.escape(DEMO_LEGACY_PREFIX)}\s*$"
)


def strip_demo_label(text: str | None) -> str:
    if not text:
        return ""
    return _DEMO_LABEL_RE.sub("", text.strip()).strip()


def demo_customer_index_from_phone(salon_slug: str, phone: str) -> int | None:
    digit = "31" if salon_slug == "demo-salon-a" else "32"
    prefix = f"+98912{digit}"
    if not phone.startswith(prefix):
        return None
    base = 3_100_000 if salon_slug == "demo-salon-a" else 3_200_000
    try:
        tail = int(phone.replace("+98912", "", 1))
    except ValueError:
        return None
    idx = tail - base
    return idx if idx >= 1 else None


def demo_customer_name_for_scrub(salon_slug: str, index: int) -> str:
    pool = BEAUTY_CUSTOMERS if salon_slug == "demo-salon-a" else BARBER_CUSTOMERS
    return pool[(index - 1) % len(pool)]


def contains_demo_label(text: str | None) -> bool:
    if not text:
        return False
    return DEMO_LEGACY_PREFIX in text


def canonical_service_category_name(salon) -> str:
    from apps.salons.models import Salon

    if salon.business_type == Salon.BusinessType.BEAUTY_WOMEN:
        return "خدمات زیبایی"
    return "خدمات آرایشگری"


def _save_if_changed(instance, fields: list[str]) -> bool:
    if not fields:
        return False
    fields.append("updated_at")
    instance.save(update_fields=fields)
    return True


def _normalize_category_name(salon, raw_name: str) -> str:
    name = strip_demo_label(raw_name)
    if name in ("", "دسته", "دسته‌بندی", "category"):
        return canonical_service_category_name(salon)
    return name


def scrub_salon_demo_labels(salon) -> int:
    """Remove ``[دمو]`` from display fields; return count of updated rows."""
    if not salon:
        return 0
    updated = 0

    canonical_cat = canonical_service_category_name(salon)
    cat_target, _ = ServiceCategory.objects.get_or_create(
        salon=salon,
        name=canonical_cat,
        defaults={"sort_order": 1},
    )

    for cat in ServiceCategory.scoped(salon).filter(
        Q(name__contains=DEMO_LEGACY_PREFIX) | Q(name__in=("دسته", "دسته‌بندی"))
    ):
        new_name = _normalize_category_name(salon, cat.name)
        if new_name == canonical_cat and cat.pk != cat_target.pk:
            Service.scoped(salon).filter(category_id=cat.pk).update(category=cat_target)
            if not Service.scoped(salon).filter(category_id=cat.pk).exists():
                cat.delete()
                updated += 1
            continue
        if new_name != cat.name:
            existing = ServiceCategory.scoped(salon).filter(name=new_name).exclude(pk=cat.pk).first()
            if existing:
                Service.scoped(salon).filter(category_id=cat.pk).update(category=existing)
                if not Service.scoped(salon).filter(category_id=cat.pk).exists():
                    cat.delete()
                    updated += 1
            else:
                cat.name = new_name
                _save_if_changed(cat, ["name"])
                updated += 1

    for svc in Service.scoped(salon).filter(
        Q(name__contains=DEMO_LEGACY_PREFIX) | Q(description__contains=DEMO_LEGACY_PREFIX)
    ):
        fields = []
        new_name = strip_demo_label(svc.name)
        if new_name and new_name != svc.name:
            svc.name = new_name
            fields.append("name")
        if svc.description and contains_demo_label(svc.description):
            svc.description = strip_demo_label(svc.description)
            fields.append("description")
        if _save_if_changed(svc, fields):
            updated += 1

    for staff in StaffProfile.scoped(salon).filter(
        Q(display_name__contains=DEMO_LEGACY_PREFIX) | Q(title__contains=DEMO_LEGACY_PREFIX)
    ):
        fields = []
        for attr in ("display_name", "title"):
            val = getattr(staff, attr) or ""
            if contains_demo_label(val):
                setattr(staff, attr, strip_demo_label(val))
                fields.append(attr)
        if _save_if_changed(staff, fields):
            updated += 1

    for c in Customer.scoped(salon).filter(full_name__contains=DEMO_LEGACY_PREFIX):
        fields = []
        idx = demo_customer_index_from_phone(salon.slug, c.phone or "")
        if idx is not None:
            new_name = demo_customer_name_for_scrub(salon.slug, idx)
        else:
            new_name = strip_demo_label(c.full_name)
        if new_name and new_name != c.full_name:
            c.full_name = new_name
            fields.append("full_name")
        if _save_if_changed(c, fields):
            updated += 1

    for tag in CustomerTag.scoped(salon).filter(name__contains=DEMO_LEGACY_PREFIX):
        tag.name = strip_demo_label(tag.name)
        if _save_if_changed(tag, ["name"]):
            updated += 1

    for pkg in ServicePackage.scoped(salon).filter(
        Q(name__contains=DEMO_LEGACY_PREFIX) | Q(description__contains=DEMO_LEGACY_PREFIX)
    ):
        fields = []
        new_name = strip_demo_label(pkg.name)
        if new_name and new_name != pkg.name:
            pkg.name = new_name
            fields.append("name")
        if pkg.description and contains_demo_label(pkg.description):
            pkg.description = strip_demo_label(pkg.description)
            fields.append("description")
        if _save_if_changed(pkg, fields):
            updated += 1

    for item in InventoryItem.scoped(salon).filter(name__contains=DEMO_LEGACY_PREFIX):
        item.name = strip_demo_label(item.name)
        if _save_if_changed(item, ["name"]):
            updated += 1

    for photo in PortfolioItem.scoped(salon).filter(
        Q(title__contains=DEMO_LEGACY_PREFIX) | Q(description__contains=DEMO_LEGACY_PREFIX)
    ):
        fields = []
        new_title = strip_demo_label(photo.title)
        if new_title and new_title != photo.title:
            photo.title = new_title
            fields.append("title")
        if photo.description and contains_demo_label(photo.description):
            photo.description = strip_demo_label(photo.description)
            fields.append("description")
        if _save_if_changed(photo, fields):
            updated += 1

    return updated
