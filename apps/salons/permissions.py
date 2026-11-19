from functools import wraps

from django.core.exceptions import PermissionDenied

from apps.salons.models import SalonMembership


def role_at_least(membership, min_role: str) -> bool:
    if membership is None or not membership.is_active:
        return False
    return membership.role_rank >= SalonMembership.role_rank_for(min_role)


def require_role(min_role: str):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            membership = getattr(request, "membership", None)
            if not role_at_least(membership, min_role):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


# Receptionist+: day-to-day CRM & appointments
CRM_ROLES = (SalonMembership.Role.RECEPTIONIST,)
# Manager+: services, staff, finance settings
MANAGE_ROLES = (SalonMembership.Role.MANAGER,)
