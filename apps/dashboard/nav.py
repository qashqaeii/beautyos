"""دسترسی منوی پنج‌گانهٔ داشبورد."""

from __future__ import annotations

from apps.salons.models import SalonMembership
from apps.salons.permissions import role_at_least
from django.urls import reverse

from apps.salons.permissions_policy import (
    P_APPOINTMENT_VIEW,
    P_COMMISSION_MANAGE,
    P_CUSTOMER_VIEW,
    P_EXPENSE_MANAGE,
    P_FINANCE_REPORTS,
    P_INVENTORY_MANAGE,
    P_LOYALTY_MANAGE,
    P_MEMBERS_MANAGE,
    P_PACKAGE_MANAGE,
    P_SALON_SETTINGS,
    P_STAFF_MANAGE,
    P_WAITLIST_MANAGE,
    has_permission,
    membership_permission_codes,
)


def can_see_overview(membership: SalonMembership | None) -> bool:
    return bool(membership and membership.role != SalonMembership.Role.SPECIALIST)


def can_see_management(membership: SalonMembership | None) -> bool:
    if not membership or not membership.is_active:
        return False
    if membership.role_rank >= SalonMembership.role_rank_for(SalonMembership.Role.MANAGER):
        return True
    codes = membership_permission_codes(membership)
    manage_codes = {
        P_FINANCE_REPORTS,
        P_EXPENSE_MANAGE,
        P_COMMISSION_MANAGE,
        P_STAFF_MANAGE,
        P_INVENTORY_MANAGE,
        P_LOYALTY_MANAGE,
        P_MEMBERS_MANAGE,
        P_SALON_SETTINGS,
    }
    return bool(codes & manage_codes)


def can_see_reception(membership: SalonMembership | None) -> bool:
    return bool(
        membership
        and membership.role_rank >= SalonMembership.role_rank_for(SalonMembership.Role.RECEPTIONIST)
    )


def can_see_specialists(membership: SalonMembership | None) -> bool:
    return bool(membership and membership.is_active and (can_see_reception(membership) or membership.role == SalonMembership.Role.SPECIALIST))


def can_see_calendar(membership: SalonMembership | None) -> bool:
    return has_permission(membership, P_APPOINTMENT_VIEW)


def reception_quick_access_links(membership: SalonMembership | None) -> list[dict]:
    """میان‌برهای میز پذیرش — همان مجوزهای قبلی کارت‌های مدیریت."""
    if not membership:
        return []
    links: list[dict] = []
    if has_permission(membership, P_WAITLIST_MANAGE):
        links.append(
            {
                "title": "لیست انتظار",
                "url": reverse("waitlist:queue"),
                "icon": "list-ordered",
                "permission": P_WAITLIST_MANAGE,
            }
        )
    if has_permission(membership, P_PACKAGE_MANAGE):
        if role_at_least(membership, SalonMembership.Role.MANAGER):
            links.append(
                {
                    "title": "پکیج‌ها",
                    "url": reverse("packages:list"),
                    "icon": "package",
                    "permission": P_PACKAGE_MANAGE,
                }
            )
        elif role_at_least(membership, SalonMembership.Role.RECEPTIONIST):
            links.append(
                {
                    "title": "فروش پکیج",
                    "url": reverse("packages:sell"),
                    "icon": "package",
                    "permission": P_PACKAGE_MANAGE,
                }
            )
    if has_permission(membership, P_CUSTOMER_VIEW):
        links.append(
            {
                "title": "پیگیری مشتریان",
                "url": reverse("retention:queue"),
                "icon": "heart-handshake",
                "permission": P_CUSTOMER_VIEW,
            }
        )
    return links
