from django.shortcuts import redirect

from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role


@salon_required
@require_role(SalonMembership.Role.SPECIALIST)
def home(request):
    from django.urls import reverse

    url = reverse("dashboard:home")
    if request.GET:
        url = f"{url}?{request.GET.urlencode()}"
    return redirect(url)
