"""Read-only platform subscription inventory. Salon revenue is not SaaS revenue."""
from django.db.models import Count, Q
from django.shortcuts import render

from apps.platform_admin.guards import platform_required
from apps.platform_admin.models import SalonSubscription, SubscriptionPlan


@platform_required
def subscriptions(request):
    status = request.GET.get("status", "")
    allowed = {value for value, _ in SalonSubscription.Status.choices}
    items = SalonSubscription.objects.select_related("salon", "plan").order_by("ends_at", "pk")
    if status in allowed:
        items = items.filter(status=status)
    else:
        status = ""
    plans = SubscriptionPlan.objects.annotate(
        enrolled=Count("subscriptions"),
        active_enrolled=Count(
            "subscriptions",
            filter=Q(subscriptions__status=SalonSubscription.Status.ACTIVE),
        ),
    ).order_by("price_toman", "pk")
    return render(request, "platform_admin/subscriptions.html", {
        "plans": plans,
        "subscriptions": items[:100],
        "status_filter": status,
        "subscriptions_total": SalonSubscription.objects.count(),
        "unassigned_count": _unassigned_count(),
    })


def _unassigned_count():
    from apps.salons.models import Salon
    return Salon.objects.filter(platform_subscription__isnull=True).count()
