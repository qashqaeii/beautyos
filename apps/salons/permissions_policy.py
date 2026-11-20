"""Central permission policy — server-side checks beyond sidebar visibility."""

from __future__ import annotations

from functools import wraps

from django.core.exceptions import PermissionDenied

from apps.salons.models import SalonMembership

# Permission codes
P_CUSTOMER_VIEW = "customer.view"
P_CUSTOMER_CREATE = "customer.create"
P_CUSTOMER_UPDATE = "customer.update"
P_APPOINTMENT_VIEW = "appointment.view"
P_APPOINTMENT_CREATE = "appointment.create"
P_APPOINTMENT_UPDATE = "appointment.update"
P_APPOINTMENT_CANCEL = "appointment.cancel"
P_APPOINTMENT_CHECKIN = "appointment.checkin"
P_APPOINTMENT_COMPLETE = "appointment.complete"
P_PAYMENT_CREATE = "payment.create"
P_PAYMENT_VIEW = "payment.view"
P_FINANCE_REPORTS = "finance.reports"
P_EXPENSE_MANAGE = "expense.manage"
P_COMMISSION_MANAGE = "commission.manage"
P_COMMISSION_VIEW_SELF = "commission.view_self"
P_STAFF_MANAGE = "staff.manage"
P_MEMBERS_MANAGE = "salon.members.manage"
P_SALON_SETTINGS = "salon.settings"
P_INVENTORY_MANAGE = "inventory.manage"
P_LOYALTY_MANAGE = "loyalty.manage"
P_MARKETING_MANAGE = "marketing.manage"
P_WAITLIST_MANAGE = "waitlist.manage"
P_PACKAGE_MANAGE = "package.manage"

ROLE_PERMISSIONS: dict[str, set[str]] = {
    SalonMembership.Role.OWNER: {
        P_CUSTOMER_VIEW,
        P_CUSTOMER_CREATE,
        P_CUSTOMER_UPDATE,
        P_APPOINTMENT_VIEW,
        P_APPOINTMENT_CREATE,
        P_APPOINTMENT_UPDATE,
        P_APPOINTMENT_CANCEL,
        P_APPOINTMENT_CHECKIN,
        P_APPOINTMENT_COMPLETE,
        P_PAYMENT_CREATE,
        P_PAYMENT_VIEW,
        P_FINANCE_REPORTS,
        P_EXPENSE_MANAGE,
        P_COMMISSION_MANAGE,
        P_STAFF_MANAGE,
        P_MEMBERS_MANAGE,
        P_SALON_SETTINGS,
        P_INVENTORY_MANAGE,
        P_LOYALTY_MANAGE,
        P_MARKETING_MANAGE,
        P_WAITLIST_MANAGE,
        P_PACKAGE_MANAGE,
    },
    SalonMembership.Role.MANAGER: {
        P_CUSTOMER_VIEW,
        P_CUSTOMER_CREATE,
        P_CUSTOMER_UPDATE,
        P_APPOINTMENT_VIEW,
        P_APPOINTMENT_CREATE,
        P_APPOINTMENT_UPDATE,
        P_APPOINTMENT_CANCEL,
        P_APPOINTMENT_CHECKIN,
        P_APPOINTMENT_COMPLETE,
        P_PAYMENT_CREATE,
        P_PAYMENT_VIEW,
        P_FINANCE_REPORTS,
        P_EXPENSE_MANAGE,
        P_COMMISSION_MANAGE,
        P_STAFF_MANAGE,
        P_INVENTORY_MANAGE,
        P_LOYALTY_MANAGE,
        P_MARKETING_MANAGE,
        P_WAITLIST_MANAGE,
        P_PACKAGE_MANAGE,
    },
    SalonMembership.Role.RECEPTIONIST: {
        P_CUSTOMER_VIEW,
        P_CUSTOMER_CREATE,
        P_CUSTOMER_UPDATE,
        P_APPOINTMENT_VIEW,
        P_APPOINTMENT_CREATE,
        P_APPOINTMENT_UPDATE,
        P_APPOINTMENT_CANCEL,
        P_APPOINTMENT_CHECKIN,
        P_APPOINTMENT_COMPLETE,
        P_PAYMENT_CREATE,
        P_PAYMENT_VIEW,
        P_WAITLIST_MANAGE,
        P_PACKAGE_MANAGE,
    },
    SalonMembership.Role.SPECIALIST: {
        P_APPOINTMENT_VIEW,
        P_APPOINTMENT_CHECKIN,
        P_APPOINTMENT_COMPLETE,
        P_COMMISSION_VIEW_SELF,
    },
}


def membership_permission_codes(membership: SalonMembership | None) -> set[str]:
    if membership is None or not membership.is_active:
        return set()
    codes = set(ROLE_PERMISSIONS.get(membership.role, set()))
    if membership.role == SalonMembership.Role.RECEPTIONIST and membership.can_manage_staff:
        codes.add(P_STAFF_MANAGE)
    return codes


def has_permission(membership: SalonMembership | None, code: str) -> bool:
    return code in membership_permission_codes(membership)


def require_permission(code: str):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            membership = getattr(request, "membership", None)
            if not has_permission(membership, code):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
