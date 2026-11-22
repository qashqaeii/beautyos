"""Post-seed integrity checks and Jalali month summaries (transaction-derived only)."""

from __future__ import annotations

from datetime import date, timedelta

import jdatetime
from django.db.models import Q, Sum
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.appointments.services.scheduling import has_overlap
from apps.commissions.models import CommissionEntry, CommissionSettlement
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.finance.models import Payment
from apps.packages.models import ServicePackage
from apps.services.models import Service
from apps.staff.models import StaffProfile


def _month_slices(reference: date, *, count: int = 3) -> list[tuple[int, int, date, date]]:
    jd = jdatetime.date.fromgregorian(date=reference)
    rows: list[tuple[int, int, date, date]] = []
    y, m = jd.year, jd.month
    for _ in range(count):
        start = jdatetime.date(y, m, 1).togregorian()
        dim = 31 if m <= 6 else (30 if m <= 11 else (30 if jdatetime.date(y, 1, 1).isleap() else 29))
        end = jdatetime.date(y, m, dim).togregorian()
        rows.append((y, m, start, end))
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    rows.reverse()
    return rows


def _payment_revenue(salon, start: date, end: date) -> int:
    from apps.dashboard.role_services import day_bounds

    start_dt, _ = day_bounds(start)
    _, end_dt = day_bounds(end)
    return int(
        Payment.scoped(salon)
        .filter(
            created_at__gte=start_dt,
            created_at__lt=end_dt,
            paid_amount_toman__gt=0,
        )
        .exclude(status=Payment.Status.REFUNDED)
        .aggregate(total=Sum("paid_amount_toman"))["total"]
        or 0
    )


def _expense_total(salon, start: date, end: date) -> int:
    return int(
        Expense.scoped(salon)
        .filter(expense_date__gte=start, expense_date__lte=end)
        .aggregate(total=Sum("amount_toman"))["total"]
        or 0
    )


def count_staff_overlaps(salon) -> int:
    bad = 0
    qs = (
        Appointment.scoped(salon)
        .exclude(status__in=(Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW))
        .only("pk", "staff_id", "start_at", "end_at", "status")
    )
    for appt in qs.iterator():
        if has_overlap(salon, appt.staff_id, appt.start_at, appt.end_at, exclude_id=appt.pk):
            bad += 1
    return bad


def build_seed_report(salon, *, reference: date | None = None) -> dict:
    reference = reference or timezone.localdate()
    months = []
    for jy, jm, start, end in _month_slices(reference, count=3):
        rev = _payment_revenue(salon, start, end)
        exp = _expense_total(salon, start, end)
        months.append(
            {
                "jalali_year": jy,
                "jalali_month": jm,
                "start": start,
                "end": end,
                "revenue_toman": rev,
                "expense_toman": exp,
                "profit_toman": rev - exp,
            }
        )

    pay_qs = Payment.scoped(salon).filter(paid_amount_toman__gt=0).exclude(status=Payment.Status.REFUNDED)
    paid_full = pay_qs.filter(status=Payment.Status.PAID).count()
    partial = pay_qs.filter(status=Payment.Status.PARTIAL).count()
    unpaid_completed = (
        Appointment.scoped(salon)
        .filter(status=Appointment.Status.COMPLETED)
        .filter(
            Q(payments__isnull=True)
            | Q(payments__paid_amount_toman=0)
        )
        .distinct()
        .count()
    )

    commission_accrued = int(
        CommissionEntry.scoped(salon).aggregate(total=Sum("commission_amount_toman"))["total"] or 0
    )
    commission_settled = int(
        CommissionSettlement.scoped(salon).aggregate(total=Sum("amount_toman"))["total"] or 0
    )

    return {
        "customers": Customer.scoped(salon).count(),
        "specialists": StaffProfile.scoped(salon).filter(is_bookable=True).count(),
        "services": Service.scoped(salon).count(),
        "appointments": Appointment.scoped(salon).count(),
        "packages": ServicePackage.scoped(salon).count(),
        "months": months,
        "payments_paid_full": paid_full,
        "payments_partial": partial,
        "completed_without_payment": unpaid_completed,
        "commission_accrued_toman": commission_accrued,
        "commission_settled_toman": commission_settled,
        "overlap_conflicts": count_staff_overlaps(salon),
    }