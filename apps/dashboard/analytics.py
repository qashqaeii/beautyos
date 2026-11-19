"""Read-only, tenant-scoped daily overview analytics."""
from datetime import timedelta

from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.core.utils.dates import to_jalali
from apps.customers.models import Customer
from apps.dashboard.role_services import day_bounds
from apps.finance.models import Payment
from apps.salons.permissions_policy import P_CUSTOMER_VIEW, P_FINANCE_REPORTS, P_STAFF_MANAGE, has_permission


STATUS_COLORS = {
    "pending": "#C79A57", "confirmed": "#9D726E", "checked_in": "#B58D89",
    "completed": "#769B82", "cancelled": "#B96E6C", "no_show": "#9A8B85",
}


def _revenue(salon, day, days):
    first = day - timedelta(days=days - 1)
    start, _ = day_bounds(first)
    _, end = day_bounds(day)
    records = (
        Payment.scoped(salon)
        .filter(created_at__gte=start, created_at__lt=end, paid_amount_toman__gt=0)
        .exclude(status=Payment.Status.REFUNDED)
        .order_by()
        .annotate(local_day=TruncDate("created_at", tzinfo=timezone.get_current_timezone()))
        .values("local_day")
        .annotate(amount=Sum("paid_amount_toman"))
    )
    by_day = {r["local_day"]: int(r["amount"] or 0) for r in records}
    rows = [{"day": first + timedelta(days=i), "amount": by_day.get(first + timedelta(days=i), 0)}
            for i in range(days)]
    max_amount = max((r["amount"] for r in rows), default=0)
    scale = max(max_amount, 1)
    for i, row in enumerate(rows):
        row["x"] = round(12 + 576 * i / max(days - 1, 1), 2)
        row["y"] = round(150 - 126 * row["amount"] / scale, 2)
        row["label"] = to_jalali(row["day"])[5:]
        row["label_position"] = round(row["x"] / 6, 3)
    points = " ".join(f'{r["x"]},{r["y"]}' for r in rows)
    return {
        "rows": rows, "labels": rows if days == 7 else [rows[i] for i in (0, 7, 14, 21, 29)],
        "points": points, "area": f"12,150 {points} 588,150",
        "total": sum(r["amount"] for r in rows), "maximum": max_amount,
    }


def overview_analytics(salon, membership, day, trend_days=7):
    start, end = day_bounds(day)
    daily = Appointment.scoped(salon).filter(start_at__gte=start, start_at__lt=end)
    counts = {r["status"]: r["count"] for r in daily.order_by().values("status").annotate(count=Count("pk"))}
    statuses = [{"label": label, "count": counts.get(code, 0), "color": STATUS_COLORS[code]}
                for code, label in Appointment.Status.choices]
    total = sum(r["count"] for r in statuses)
    cursor, stops = 0, []
    for row in statuses:
        if row["count"] and total:
            finish = cursor + row["count"]
            stops.append(f'{row["color"]} {cursor / total * 100:.4f}% {finish / total * 100:.4f}%')
            cursor = finish
    result = {
        "statuses": statuses, "status_total": total,
        "status_gradient": ", ".join(stops) if stops else "#E9D8D2 0% 100%",
        "revenue": None, "customers": None, "staff": None, "staff_visible": False,
    }
    if has_permission(membership, P_FINANCE_REPORTS):
        result["revenue"] = _revenue(salon, day, 30 if trend_days == 30 else 7)
    if has_permission(membership, P_CUSTOMER_VIEW):
        customers = Customer.scoped(salon).filter(is_deleted=False)
        stats = customers.filter(created_at__lt=end).aggregate(
            new=Count("pk", filter=Q(created_at__gte=start)),
        )
        completed = daily.filter(status=Appointment.Status.COMPLETED, customer__salon=salon, customer__is_deleted=False)
        prior = Appointment.scoped(salon).filter(
            status=Appointment.Status.COMPLETED, start_at__lt=start, customer_id=OuterRef("customer_id"),
        )
        stats["returning"] = completed.annotate(visited_before=Exists(prior)).filter(visited_before=True).values("customer_id").distinct().count()
        stats["visited"] = completed.values("customer_id").distinct().count()
        result["customers"] = stats
    if has_permission(membership, P_STAFF_MANAGE) or has_permission(membership, P_FINANCE_REPORTS):
        rows = list(daily.filter(status=Appointment.Status.COMPLETED, staff__salon=salon)
                    .order_by().values("staff_id", "staff__display_name")
                    .annotate(count=Count("pk")).order_by("-count", "staff_id")[:5])
        top = max((r["count"] for r in rows), default=1)
        result["staff"] = [
            {"name": r["staff__display_name"], "count": r["count"], "percent": r["count"] * 100 // top}
            for r in rows
        ]
        result["staff_visible"] = True
    return result
