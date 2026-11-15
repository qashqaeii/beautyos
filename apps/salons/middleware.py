from django.db.models import Case, When

from apps.salons.models import Salon, SalonMembership


def _owner_memberships_qs(user):
    return SalonMembership.objects.filter(
        user=user,
        is_active=True,
        role=SalonMembership.Role.OWNER,
    ).select_related("salon", "salon__settings")


def sole_owner_membership(user):
    """Return owner membership only when the user owns exactly one active salon."""
    qs = _owner_memberships_qs(user)
    if qs.count() == 1:
        return qs.first()
    return None


def prefer_sole_owner_membership(request, membership: SalonMembership | None):
    """
    If the user owns exactly one salon but the session points at another role
    (e.g. manager on a demo salon), use the owner membership for tenant context.
    """
    if membership is None or membership.role == SalonMembership.Role.OWNER:
        return membership
    preferred = sole_owner_membership(request.user)
    if preferred is None or preferred.pk == membership.pk:
        return membership
    request.session["active_salon_id"] = str(preferred.salon_id)
    request.session.modified = True
    return preferred


def sync_login_active_salon(request, user) -> None:
    """After OTP login, pin session to the user's salon when unambiguous."""
    owner = _owner_memberships_qs(user).order_by("-created_at").first()
    if owner:
        request.session["active_salon_id"] = str(owner.salon_id)
        request.session.modified = True
        return
    first = (
        SalonMembership.objects.filter(user=user, is_active=True)
        .order_by(
            Case(
                When(role=SalonMembership.Role.OWNER, then=0),
                default=1,
            ),
            "-created_at",
        )
        .first()
    )
    if first:
        request.session["active_salon_id"] = str(first.salon_id)
        request.session.modified = True


def resolve_active_salon(request):
    if not request.user.is_authenticated:
        return None, None

    salon_id = request.session.get("active_salon_id")
    if salon_id:
        membership = (
            SalonMembership.objects.filter(
                user=request.user,
                salon_id=salon_id,
                is_active=True,
            )
            .select_related("salon", "salon__settings")
            .first()
        )
        if membership:
            membership = prefer_sole_owner_membership(request, membership)
            return membership.salon, membership

    first = (
        SalonMembership.objects.filter(user=request.user, is_active=True)
        .select_related("salon", "salon__settings")
        .order_by(
            Case(
                When(role=SalonMembership.Role.OWNER, then=0),
                default=1,
            ),
            "-created_at",
        )
        .first()
    )
    if first:
        request.session["active_salon_id"] = str(first.salon_id)
        return first.salon, first
    return None, None


class SalonTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        salon, membership = resolve_active_salon(request)
        request.salon = salon
        request.membership = membership
        return self.get_response(request)
