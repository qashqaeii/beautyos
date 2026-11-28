"""Read-only platform subscription inventory. Salon revenue is not SaaS revenue."""
from django.db.models import Count, Q
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect

from apps.platform_admin.guards import platform_required
from apps.platform_admin.models import SalonSubscription, SubscriptionPlan, SubscriptionChangeLog, PlatformSubscriptionOrder
from apps.platform_admin.subscription_health import subscription_health
from apps.platform_admin.subscription_lifecycle import change_subscription


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
        "recent_orders": PlatformSubscriptionOrder.objects.select_related("salon", "plan").order_by("-created_at")[:20],
        "verified_order_count": PlatformSubscriptionOrder.objects.filter(status=PlatformSubscriptionOrder.Status.VERIFIED).count(),
        "health": subscription_health(),
        "recent_changes": SubscriptionChangeLog.objects.select_related("subscription__salon", "actor").order_by("-changed_at")[:15],
        "subscriptions": items[:100],
        "status_filter": status,
        "subscriptions_total": SalonSubscription.objects.count(),
        "unassigned_count": _unassigned_count(),
    })


def _unassigned_count():
    from apps.salons.models import Salon
    return Salon.objects.filter(platform_subscription__isnull=True).count()


@platform_required
@require_POST
def correct_subscription_status(request, subscription_id):
    """Restricted status correction, never an activation, extension or charge."""
    subscription = get_object_or_404(SalonSubscription, pk=subscription_id)
    target = request.POST.get("status", "")
    reason = request.POST.get("reason", "")
    allowed = {SalonSubscription.Status.EXPIRED, SalonSubscription.Status.CANCELED,
               SalonSubscription.Status.PAST_DUE}
    if target not in allowed:
        messages.error(request, "فعال‌سازی یا تمدید فقط پس از پیاده‌سازی تأیید پرداخت مجاز است.")
        return redirect("platform_admin:subscriptions")
    if target == SalonSubscription.Status.EXPIRED and subscription.ends_at > timezone.now():
        messages.error(request, "اشتراک هنوز از نظر تاریخ منقضی نشده است.")
        return redirect("platform_admin:subscriptions")
    try:
        _, changed = change_subscription(
            subscription_id=subscription.pk, new_status=target,
            new_ends_at=subscription.ends_at, reason=reason,
            actor=request.user, source="operator",
        )
    except ValidationError as exc:
        messages.error(request, "؛ ".join(exc.messages))
    else:
        messages.success(request, "وضعیت اشتراک ثبت شد." if changed else "تغییری لازم نبود.")
    return redirect("platform_admin:subscriptions")
