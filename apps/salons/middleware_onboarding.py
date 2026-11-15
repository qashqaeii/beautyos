from django.shortcuts import redirect

from apps.salons import onboarding_wizard as ow
from apps.salons.models import SalonMembership


class OnboardingGateMiddleware:
    """Owners with incomplete onboarding stay in wizard (existing salons backfilled)."""

    SAFE_PREFIXES = (
        "/auth/",
        "/onboarding/",
        "/admin/",
        "/health/",
        "/static/",
        "/media/",
        "/s/",
        "/features/",
        "/blog/",
        "/contact/",
        "/faq/",
        "/privacy/",
        "/terms/",
    )

    MARKETING_PREFIXES = (
        "/features/",
        "/blog/",
        "/contact/",
        "/faq/",
        "/privacy/",
        "/terms/",
    )

    @classmethod
    def _is_public_marketing(cls, path: str) -> bool:
        if path == "/":
            return True
        return any(path.startswith(p) for p in cls.MARKETING_PREFIXES)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.salon and not request.user.is_superuser:
            path = request.path
            if not any(path.startswith(p) for p in self.SAFE_PREFIXES) and not self._is_public_marketing(path):
                settings = getattr(request.salon, "settings", None)
                if settings and ow.salon_needs_onboarding(request.salon):
                    if request.membership and request.membership.role_rank >= SalonMembership.role_rank_for(
                        SalonMembership.Role.MANAGER
                    ):
                        return redirect("salons_onboarding:wizard", step=1)
        return self.get_response(request)
