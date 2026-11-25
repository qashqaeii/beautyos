from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.commissions.models import CommissionEntry, CommissionSettlement
from apps.core.utils.dates import jalali_month_bounds, jalali_range_label, jalali_three_previous_months_bounds, to_jalali
from apps.dashboard.role_services import day_bounds, parse_dashboard_day
from apps.finance.models import Payment, SalonDebt


def parse_finance_range(request) -> dict:
    range_key = request.GET.get("range", "today")
    selected_day = parse_dashboard_day(request)
    if not date(1900, 1, 1) <= selected_day <= date(2200, 12, 31):
        selected_day = timezone.localdate()

    if range_key == "yesterday":
        selected_day=timezone.localdate()-timedelta(days=1)
        start_d=end_d=selected_day
        label="دیروز"
    elif range_key == "week":
        from apps.core.utils.dates import week_start_saturday
        selected_day=timezone.localdate()
        start_d=week_start_saturday(selected_day)
        end_d=selected_day
        label="این هفته"
    elif range_key == "month":
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
        selected_day = timezone.localdate()
        start_d = end_d = selected_day
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
    return customer_payment_queryset(salon, start_dt, end_dt)[:limit]


def customer_payment_queryset(salon, start_dt: datetime, end_dt: datetime):
    return (
        Payment.scoped(salon)
        .filter(created_at__gte=start_dt, created_at__lt=end_dt, paid_amount_toman__gt=0)
        .exclude(status=Payment.Status.REFUNDED)
        .select_related("customer")
        .order_by("-created_at", "-pk")
    )


def _sparkline(values):
    """Small data-only chart. Do not draw a fictional trend for an empty series."""
    if not any(values):
        return None
    peak = max(values)
    points = " ".join(f"{round(3 + i * 114 / 6, 2)},{round(35 - 30 * amount / peak, 2)}" for i, amount in enumerate(values))
    return {"points": points, "area": f"3,38 {points} 117,38"}


def income_presentation(salon, range_ctx, income):
    """Seven calendar days of actual receipts and distinct customers per day."""
    end_day = min(range_ctx["end_date"], timezone.localdate())
    if end_day < range_ctx["start_date"]:
        return {"series": {}, "comparison": None, "comparison_label": "", "has_previous": False}
    first = end_day - timedelta(days=6)
    start, _ = day_bounds(first)
    _, end = day_bounds(end_day)
    daily = (
        customer_payment_queryset(salon, start, end).order_by()
        .annotate(day=TruncDate("created_at", tzinfo=timezone.get_current_timezone()))
        .values("day")
        .annotate(
            received=Sum("paid_amount_toman"),
            deposits=Count("customer_id", filter=Q(status=Payment.Status.PARTIAL), distinct=True),
            settled=Count("customer_id", filter=Q(status=Payment.Status.PAID), distinct=True),
        )
    )
    by_day = {row["day"]: row for row in daily}
    values = {key: [int(by_day.get(first + timedelta(days=i), {}).get(key) or 0) for i in range(7)]
              for key in ("received", "deposits", "settled")}
    duration = (range_ctx["end_date"] - range_ctx["start_date"]).days + 1
    # For an incomplete current month compare elapsed days to an equally long
    # immediately preceding interval, not a full future-inclusive month.
    elapsed = (end_day - range_ctx["start_date"]).days + 1
    prev_start, _ = day_bounds(range_ctx["start_date"] - timedelta(days=elapsed))
    _, prev_end = day_bounds(range_ctx["start_date"] - timedelta(days=1))
    previous = customer_payment_queryset(salon, prev_start, prev_end).aggregate(total=Sum("paid_amount_toman"))["total"] or 0
    current = income["total_received"]
    if elapsed < duration:
        current = customer_payment_queryset(salon, range_ctx["start_dt"], end).aggregate(total=Sum("paid_amount_toman"))["total"] or 0
    change = round((current - previous) * 100 / previous) if previous else None
    return {
        "series": {key: _sparkline(data) for key, data in values.items()},
        "trend_label": f"روند ۷ روز منتهی به {to_jalali(end_day)}",
        "comparison": abs(change) if change is not None else None,
        "direction": "up" if change is not None and change > 0 else "down" if change is not None and change < 0 else "flat",
        "has_previous": bool(previous),
        "comparison_label": "نسبت به روز قبل" if elapsed == 1 else "نسبت به بازه هم‌طول قبل",
    }


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
        settled_part = int(entry.settled_amount_toman or 0)
        if entry.status == CommissionEntry.Status.SETTLED:
            bucket["paid_total"] += entry.commission_amount_toman
        elif entry.status == CommissionEntry.Status.RECOGNIZED:
            bucket["paid_total"] += settled_part
            bucket["remainder_total"] += max(0, int(entry.commission_amount_toman) - settled_part)

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


@transaction.atomic
def record_salon_debt_payment(
    *,
    salon,
    debt_id,
    amount_toman: int,
    note: str = "",
) -> "SalonDebtPayment":
    """Record a debt payment with row lock — rejects amounts above current balance."""
    from apps.finance.models import SalonDebt, SalonDebtPayment

    if amount_toman <= 0:
        raise ValidationError("مبلغ پرداخت باید بزرگ‌تر از صفر باشد.")

    debt = (
        SalonDebt.objects.select_for_update()
        .filter(pk=debt_id, salon=salon, is_closed=False)
        .first()
    )
    if debt is None:
        raise ValidationError("بدهی یافت نشد یا تسویه شده است.")

    balance = debt.balance_toman
    if amount_toman > balance:
        raise ValidationError(f"مبلغ پرداخت بیش از مانده بدهی است. مانده فعلی: {balance} تومان.")

    payment = SalonDebtPayment.objects.create(
        salon=salon,
        debt=debt,
        amount_toman=amount_toman,
        note=note or "",
    )
    debt.paid_toman = int(debt.paid_toman) + amount_toman
    if debt.balance_toman <= 0:
        debt.is_closed = True
        debt.paid_toman = debt.principal_toman
    debt.save(update_fields=["paid_toman", "is_closed", "updated_at"])
    return payment


def audit_debt_payment_consistency(*, salon=None) -> list[dict]:
    """Read-only check: paid_toman vs sum of payment rows."""
    from django.db.models import Sum

    from apps.finance.models import SalonDebt

    qs = SalonDebt.objects.all() if salon is None else SalonDebt.scoped(salon)
    qs = qs.annotate(payments_sum=Sum("payments__amount_toman"))
    issues = []
    for debt in qs:
        paid_rows = int(debt.payments_sum or 0)
        if int(debt.paid_toman) != paid_rows:
            issues.append(
                {
                    "debt_id": debt.pk,
                    "paid_toman": int(debt.paid_toman),
                    "payments_sum": paid_rows,
                    "principal_toman": int(debt.principal_toman),
                }
            )
    return issues


@transaction.atomic
def record_customer_payment(*, salon, form, actor):
    """Serialize linked receipts and validate against the current appointment balance."""
    from apps.appointments.models import Appointment
    from apps.audit.models import AuditLog
    from apps.customers.services import refresh_customer_stats
    from apps.dashboard.role_services import appointment_payment_summary

    payment = form.save(commit=False)
    payment.is_deposit = form.cleaned_data.get("payment_kind") == "deposit"
    payment.salon = salon
    if payment.customer.salon_id != salon.pk:
        raise ValidationError("مشتری متعلق به این سالن نیست.")
    if form.cleaned_data.get("payment_kind") == "settlement":
        # Settle completed services only, with the same lock order as checkout.
        appointments = list(Appointment.scoped(salon).select_for_update().filter(
            customer_id=payment.customer_id, status=Appointment.Status.COMPLETED
        ).order_by("pk"))
        balances = [(a, appointment_payment_summary(a)["owed_toman"]) for a in appointments]
        balances = [(a, amount) for a, amount in balances if amount > 0]
        total = sum(amount for _, amount in balances)
        if not total:
            raise ValidationError("این مشتری مانده خدمات انجام‌شده ندارد.")
        if payment.paid_amount_toman != total:
            raise ValidationError(f"برای تسویه کامل، مبلغ دریافتی باید برابر مانده کل مشتری باشد: {total:,} تومان.")
        from apps.finance.models import InvoiceLine
        from apps.loyalty.automation import award_payment
        receipts = []
        for appointment, amount in balances:
            line = InvoiceLine.scoped(salon).filter(appointment=appointment).first()
            receipt = Payment.objects.create(
                salon=salon, customer=payment.customer, appointment=appointment,
                invoice_id=line.invoice_id if line else None, total_amount_toman=amount,
                paid_amount_toman=amount, discount_toman=0, status=Payment.Status.PAID,
                method=payment.method, notes=payment.notes, is_deposit=False,
            )
            award_payment(receipt)
            AuditLog.objects.create(salon=salon, actor=actor, action=AuditLog.Action.CREATE,
                entity_type="payment", entity_id=str(receipt.pk), message="تسویه کامل مشتری",
                metadata={"paid_amount_toman": amount, "appointment_id": appointment.pk})
            receipts.append(receipt)
        refresh_customer_stats(payment.customer)
        return receipts[0]
    if payment.appointment_id:
        appointment = Appointment.scoped(salon).select_for_update().filter(pk=payment.appointment_id).first()
        if appointment is None or appointment.customer_id != payment.customer_id:
            raise ValidationError("نوبت معتبر نیست.")
        if appointment.status in (Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW):
            raise ValidationError("ثبت پرداخت برای نوبت لغوشده یا عدم حضور مجاز نیست.")
        balance = appointment_payment_summary(appointment)["owed_toman"]
        if balance == 0:
            raise ValidationError("این نوبت قبلاً تسویه شده است.")
        if payment.total_amount_toman != balance:
            raise ValidationError(f"مبلغ قابل پرداخت پیش از تخفیف باید برابر مانده نوبت باشد: {balance:,} تومان.")
        from apps.finance.models import InvoiceLine
        line=InvoiceLine.scoped(salon).filter(appointment=appointment).first()
        if line:
            payment.invoice_id=line.invoice_id
    payment.save()
    from apps.loyalty.automation import award_payment
    award_payment(payment)
    refresh_customer_stats(payment.customer)
    AuditLog.objects.create(salon=salon, actor=actor, action=AuditLog.Action.CREATE,
        entity_type="payment", entity_id=str(payment.pk),
        message="ثبت پرداخت مشتری", metadata={"paid_amount_toman": payment.paid_amount_toman, "status": payment.status})
    return payment


@transaction.atomic
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
    if amount_toman > total or appointment.salon_id != salon.pk or appointment.customer_id != customer.pk:
        raise ValidationError("مبلغ یا اطلاعات بیعانه معتبر نیست.")
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
        is_deposit=True,
    )
    from apps.loyalty.automation import award_payment
    award_payment(payment)
    refresh_customer_stats(customer)
    return payment
