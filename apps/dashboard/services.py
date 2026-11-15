from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.finance.models import Payment
from apps.retention.models import FollowUp
from apps.services.models import Service


def get_dashboard_kpis(salon):
    now = timezone.now()
    today_start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today_start + timedelta(days=1)

    appt_qs = Appointment.scoped(salon)
    today_appts = appt_qs.filter(start_at__gte=today_start, start_at__lt=tomorrow)
    pending = appt_qs.filter(
        status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED],
        start_at__gte=now,
    ).count()
    completed_today = today_appts.filter(status=Appointment.Status.COMPLETED).count()
    upcoming = (
        appt_qs.filter(
            start_at__gte=now,
            status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED, Appointment.Status.CHECKED_IN],
        )
        .select_related("customer", "service", "staff")
        .order_by("start_at")[:8]
    )
    timeline = today_appts.select_related("customer", "service", "staff").order_by("start_at")

    new_customers = Customer.scoped(salon).filter(created_at__gte=today_start, is_deleted=False).count()
    revenue_today = (
        Payment.scoped(salon)
        .filter(created_at__gte=today_start, status=Payment.Status.PAID)
        .aggregate(t=Sum("paid_amount_toman"))["t"]
        or 0
    )
    follow_up = FollowUp.scoped(salon).filter(status=FollowUp.Status.OPEN).count()

    week_start = today_start - timedelta(days=6)
    revenue_by_day = []
    for i in range(7):
        day = (week_start + timedelta(days=i)).date()
        amount = (
            Payment.scoped(salon)
            .filter(created_at__date=day, status=Payment.Status.PAID)
            .aggregate(t=Sum("paid_amount_toman"))["t"]
            or 0
        )
        revenue_by_day.append({"day": day, "amount": amount})

    popular = (
        Appointment.scoped(salon)
        .filter(status=Appointment.Status.COMPLETED)
        .values("service__name")
        .annotate(c=Count("id"))
        .order_by("-c")[:5]
    )

    revenue_week_max = max((row["amount"] for row in revenue_by_day), default=0) or 1

    month_start = today_start.replace(day=1)
    expense_month = (
        Expense.scoped(salon)
        .filter(expense_date__gte=month_start.date())
        .aggregate(t=Sum("amount_toman"))["t"]
        or 0
    )
    overdue_payments = Payment.scoped(salon).filter(status__in=[Payment.Status.PENDING, Payment.Status.PARTIAL]).count()
    cancelled_today = today_appts.filter(status=Appointment.Status.CANCELLED).count()
    no_show_today = today_appts.filter(status=Appointment.Status.NO_SHOW).count()
    next_appointment = upcoming[0] if upcoming else None

    return {
        "appointments_today": today_appts.count(),
        "new_customers_today": new_customers,
        "revenue_today": revenue_today,
        "pending_appointments": pending,
        "completed_today": completed_today,
        "follow_up_needed": follow_up,
        "upcoming": upcoming,
        "timeline": timeline,
        "revenue_by_day": revenue_by_day,
        "revenue_week_max": revenue_week_max,
        "expense_month": expense_month,
        "overdue_payments": overdue_payments,
        "popular_services": popular,
        "cancelled_today": cancelled_today,
        "no_show_today": no_show_today,
        "next_appointment": next_appointment,
    }
