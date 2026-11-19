from apps.salons.models import SalonMembership
from apps.dashboard.nav import (
    can_see_calendar,
    can_see_management,
    can_see_overview,
    can_see_reception,
    can_see_specialists,
)
from apps.salons.permissions_policy import (
    P_SALON_SETTINGS,
    P_FINANCE_REPORTS,
    has_permission,
    membership_permission_codes,
)
from apps.salons.themes import (
    css_variables_for_dashboard,
    css_variables_inline,
    resolve_salon_dashboard_theme,
)


def salon_context(request):
    memberships = []
    active_salon = None
    active_membership = None
    if request.user.is_authenticated:
        memberships = list(
            SalonMembership.objects.filter(user=request.user, is_active=True, salon__is_active=True)
            .select_related("salon")
            .order_by("salon__name")
        )
        active_salon = getattr(request, "salon", None)
        active_membership = getattr(request, "membership", None)
    theme_key = resolve_salon_dashboard_theme(active_salon)
    theme_vars = css_variables_for_dashboard(theme_key)
    theme_style = css_variables_inline(theme_key)

    return {
        "active_salon": active_salon,
        "active_membership": active_membership,
        "user_salons": [m.salon for m in memberships],
        "user_memberships": memberships,
        "dashboard_theme_key": theme_key,
        "dashboard_theme_vars": theme_vars,
        "dashboard_theme_style": theme_style,
        "membership_permissions": sorted(membership_permission_codes(active_membership)),
        "nav_finance": has_permission(active_membership, P_FINANCE_REPORTS),
        "nav_salon_settings": has_permission(active_membership, P_SALON_SETTINGS),
        "nav_overview": can_see_overview(active_membership),
        "nav_management": can_see_management(active_membership),
        "nav_reception": can_see_reception(active_membership),
        "nav_specialists": can_see_specialists(active_membership),
        "nav_calendar": can_see_calendar(active_membership),
    }
