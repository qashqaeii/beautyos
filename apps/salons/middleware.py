from django.db.models import Case, When

from apps.salons.models import Salon, SalonMembership


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
