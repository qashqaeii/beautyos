"""Spread demo payments and expenses across calendar ranges for finance dashboards."""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

import jdatetime
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.appointments.services.lifecycle import complete_appointment
from apps.core.utils.dates import add_jalali_months
from apps.expenses.models import Expense
from apps.finance.models import Payment

TIMELINE_NOTE = " · گردش نمایشی"


def _stamp_payment(payment_id: int, when) -> None:
    Payment.objects.filter(pk=payment_id).update(created_at=when, updated_at=when)


def backdate_salon_payment_timestamps(salon) -> int:
    """Align receipt timestamps with visit completion so trend charts populate."""
    updated = 0
    payments = (
        Payment.scoped(salon)
        .filter(paid_amount_toman__gt=0)
        .exclude(status=Payment.Status.REFUNDED)
        .select_related("appointment")
    )
    for payment in payments:
        when = None
        if payment.appointment_id:
            appt = payment.appointment
            when = appt.completed_at or appt.start_at
        if when and abs((payment.created_at - when).total_seconds()) > 120:
            _stamp_payment(payment.pk, when)
            updated += 1
    return updated


def seed_expense_timeline(salon, *, marker: str, days: int = 90) -> int:
    """Idempotent scattered operating expenses for chart + KPI realism."""
    today = timezone.localdate()
    rng = random.Random(20251121)
    created = 0
    rolling = [
        (Expense.Category.SUPPLIES, 420_000, 1_380_000, "خرید مواد مصرفی و رنگ"),
        (Expense.Category.UTILITIES, 280_000, 880_000, "برق، آب و گاز"),
        (Expense.Category.MARKETING, 350_000, 1_600_000, "تبلیغات شبکه‌های اجتماعی"),
        (Expense.Category.OTHER, 150_000, 520_000, "پذیرایی و نگهبانی"),
        (Expense.Category.EQUIPMENT, 0, 2_200_000, "تعمیر و نگهداری تجهیزات"),
    ]
    for offset in range(0, days, 3):
        expense_date = today - timedelta(days=offset)
        if expense_date.weekday() == 4:
            continue
        cat, lo, hi, title = rolling[(offset // 3) % len(rolling)]
        if cat == Expense.Category.EQUIPMENT and offset % 21 != 0:
            continue
        if cat == Expense.Category.MARKETING and offset % 9 != 0:
            continue
        amount = max(lo, ((lo + rng.randint(0, max(1, hi - lo))) // 10_000) * 10_000)
        note = f"{marker}{TIMELINE_NOTE} — {title}"
        _, was_created = Expense.objects.get_or_create(
            salon=salon,
            category=cat,
            expense_date=expense_date,
            description=note,
            defaults={"amount_toman": amount},
        )
        if was_created:
            created += 1

    jd = jdatetime.date.fromgregorian(date=today)
    for delta in range(3):
        jy, jm = add_jalali_months(jd.year, jd.month, -delta)
        month_start = jdatetime.date(jy, jm, 1).togregorian()
        rent_note = f"{marker}{TIMELINE_NOTE} — اجاره ماه"
        _, was_created = Expense.objects.get_or_create(
            salon=salon,
            category=Expense.Category.RENT,
            expense_date=month_start,
            description=rent_note,
            defaults={"amount_toman": 13_500_000 + delta * 250_000},
        )
        if was_created:
            created += 1
    return created


def complete_recent_demo_checkouts(salon, actor, *, count: int = 4) -> int:
    """Turn a few same-day checked-in visits into paid completions for today's range."""
    today = timezone.localdate()
    tz = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(today, time.min), tz)
    done = 0
    candidates = (
        Appointment.scoped(salon)
        .filter(
            status__in=(Appointment.Status.CHECKED_IN, Appointment.Status.CONFIRMED),
            start_at__gte=day_start,
        )
        .select_related("customer", "service", "staff")
        .order_by("start_at")[:count]
    )
    methods = [Payment.Method.CASH, Payment.Method.CARD, Payment.Method.TRANSFER]
    for index, appt in enumerate(candidates):
        if timezone.localtime(appt.start_at).date() != today:
            continue
        if Payment.scoped(salon).filter(appointment=appt, paid_amount_toman__gt=0).exists():
            continue
        if appt.status != Appointment.Status.COMPLETED:
            try:
                complete_appointment(salon=salon, appointment_id=appt.pk)
                appt.refresh_from_db()
            except Exception:
                appt.status = Appointment.Status.COMPLETED
                appt.completed_at = appt.end_at or appt.start_at
                appt.save(update_fields=["status", "completed_at", "updated_at"])
        when = appt.completed_at or appt.start_at
        payment = Payment.objects.create(
            salon=salon,
            customer=appt.customer,
            appointment=appt,
            total_amount_toman=appt.price_toman,
            paid_amount_toman=appt.price_toman,
            discount_toman=30_000 if index % 2 == 0 else 0,
            method=methods[index % len(methods)],
            status=Payment.Status.PAID,
        )
        _stamp_payment(payment.pk, when)
        done += 1
    return done