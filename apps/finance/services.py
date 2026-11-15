from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from django.db.models import Sum
from django.utils import timezone

from apps.commissions.models import CommissionEntry, CommissionSettlement
from apps.core.utils.dates import jalali_month_bounds, jalali_range_label, jalali_three_previous_months_bounds, to_jalali
from apps.dashboard.role_services import day_bounds, parse_dashboard_day
from apps.finance.models import Payment, SalonDebt


def parse_finance_range(request) -> dict:
    range_key = request.GET.get("range", "today")
    selected_day = parse_dashboard_day(request)
    tz = timezone.get_current_timezone()

    if range_key == "month":
        start_d, end_d = jalali_month_bounds(selected_day)
        label = "ماه جاری"
    elif range_key == "quarter":
        start_d, end_d = jalali_three_previous_months_bounds(selected_day)
        label = "سه ماه گذشته"
    elif range_key == "day":
        start_d = end_d = selected_day
        range_key = "day"
        label = "انتخاب روز"
    else:
        range_key = "today"
        start_d = end_d = timezone.localdate()
        label = "امروز"

    start_dt, _ = day_bounds(start_d)
    _, end_dt = day_bounds(end_d)
    display = jalali_range_label(start_d, end_d)

    return {
        "range_key": range_key,
        "selected_day": selected_day,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "start_date": start_d,
        "end_date": end_d,
        "range_label": label,
        "range_display_jalali": display,
        "prev_day": (selected_day - timedelta(days=1)).isoformat(),
        "next_day": (selected_day + timedelta(days=1)).isoformat(),
        "day_jalali": to_jalali(selected_day),
    }


def income_metrics(salon, start_dt: datetime, end_dt: datetime) -> dict:
    pay_qs = (
        Payment.scoped(salon)
        .filter(created_at__gte=start_dt, created_at__lt=end_dt)
        .exclude(status=Payment.Status.REFUNDED)
    )
    total_received = pay_qs.filter(paid_amount_toman__gt=0).aggregate(t=Sum("paid_amount_toman"))["t"] or 0

    deposit_customers = (
        pay_qs.filter(status=Payment.Status.PARTIAL, paid_amount_toman__gt=0)
        .values("customer_id")
        .distinct()
        .count()
    )
    settled_customers = (
        pay_qs.filter(status=Payment.Status.PAID, paid_amount_toman__gt=0)
        .values("customer_id")
        .distinct()
        .count()
    )
    return {
        "total_received": total_received,
        "deposit_customer_count": deposit_customers,
        "settled_customer_count": settled_customers,
    }


def customer_payments_in_range(salon, start_dt: datetime, end_dt: datetime, *, limit: int = 50):
    return (
        Payment.scoped(salon)
        .filter(created_at__gte=start_dt, created_at__lt=end_dt)
        .exclude(status=Payment.Status.REFUNDED)
        .filter(paid_amount_toman__gt=0)
        .select_related("customer")
        .order_by("-created_at")[:limit]
    )


def open_debts_summary(salon) -> dict:
    open_debts = SalonDebt.scoped(salon).filter(is_closed=False).order_by("due_date", "-created_at")
    total_balance = sum(d.balance_toman for d in open_debts)
    return {"open_debts": open_debts, "total_balance": total_balance}


def commission_day_overview(salon, day: date) -> dict:
    start, end = day_bounds(day)
    entries = list(
        CommissionEntry.scoped(salon)
        .filter(appointment__start_at__gte=start, appointment__start_at__lt=end)
        .exclude(status=CommissionEntry.Status.VOID)
        .select_related("staff", "appointment__service")
    )

    settlements_today = list(
        CommissionSettlement.scoped(salon)
        .filter(settled_at__gte=start, settled_at__lt=end)
        .select_related("staff")
        .order_by("-settled_at")
    )
    settlement_by_staff: dict[int, CommissionSettlement] = {}
    for settlement in settlements_today:
        if settlement.staff_id not in settlement_by_staff:
            settlement_by_staff[settlement.staff_id] = settlement

    by_staff: dict[int, dict] = {}
    for entry in entries:
        staff = entry.staff
        bucket = by_staff.setdefault(
            staff.pk,
            {
                "staff": staff,
                "entries": [],
                "commission_total": 0,
                "paid_total": 0,
                "remainder_total": 0,
            },
        )
        bucket["entries"].append(entry)
        bucket["commission_total"] += entry.commission_amount_toman
        if entry.status == CommissionEntry.Status.SETTLED:
            bucket["paid_total"] += entry.commission_amount_toman
        elif entry.status == CommissionEntry.Status.RECOGNIZED:
            bucket["remainder_total"] += entry.commission_amount_toman

    staff_rows = []
    for row in by_staff.values():
        percents = set()
        for e in row["entries"]:
            snap = e.rule_snapshot or {}
            if snap.get("percent"):
                percents.add(snap["percent"])
            elif snap.get("default_percent"):
                percents.add(snap["default_percent"])
        if len(percents) == 1:
            row["percent_label"] = f"{next(iter(percents))}%"
        elif len(percents) == 0:
            row["percent_label"] = "—"
        else:
            row["percent_label"] = "متغیر"
        row["details"] = _commission_entry_details(row["entries"])
        settlement = settlement_by_staff.get(row["staff"].pk)
        row["settlement_note"] = (settlement.note if settlement else "") or ""
        row["settled_amount_today"] = settlement.amount_toman if settlement else row["paid_total"]
        staff_rows.append(row)

    staff_rows.sort(key=lambda r: r["staff"].display_name or "")

    settled_rows = [r for r in staff_rows if r["commission_total"] > 0 and r["remainder_total"] <= 0]
    pending_rows = [r for r in staff_rows if r["remainder_total"] > 0]

    return {
        "settled_staff_count": len(settled_rows),
        "need_payment_staff_count": len(pending_rows),
        "staff_rows": staff_rows,
        "settled_rows": settled_rows,
        "pending_rows": pending_rows,
        "day_jalali": to_jalali(day),
    }


def _commission_entry_details(entries) -> list[dict]:
    grouped: dict[str, dict] = defaultdict(lambda: {"service": "", "percent": "", "amount": 0})
    for e in entries:
        service_name = e.appointment.service.name if e.appointment and e.appointment.service_id else "خدمت"
        snap = e.rule_snapshot or {}
        pct = snap.get("percent") or snap.get("default_percent") or "—"
        key = f"{service_name}:{pct}"
        grouped[key]["service"] = service_name
        grouped[key]["percent"] = pct
        grouped[key]["amount"] += e.commission_amount_toman
    return list(grouped.values())


def create_appointment_deposit(
    *,
    salon,
    customer,
    appointment,
    amount_toman: int,
    method: str,
):
    """Record deposit at booking — partial payment linked to the appointment."""
    if amount_toman <= 0:
        return None
    from apps.customers.services import refresh_customer_stats

    total = appointment.price_toman
    status = Payment.Status.PAID if amount_toman >= total else Payment.Status.PARTIAL
    payment = Payment.objects.create(
        salon=salon,
        customer=customer,
        appointment=appointment,
        total_amount_toman=total,
        paid_amount_toman=amount_toman,
        method=method,
        status=status,
        notes="بیعانه هنگام رزرو",
    )
    refresh_customer_stats(customer)
    return payment
