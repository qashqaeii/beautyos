from datetime import date, timedelta

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.utils.dates import jalali_month_bounds, today_jalali_label, to_jalali
from apps.dashboard.analytics import overview_analytics
from apps.dashboard.nav import (
    can_see_calendar,
    can_see_management,
    can_see_overview,
    can_see_reception,
    can_see_specialists,
)
from apps.dashboard.role_services import day_bounds, get_overview_context, parse_dashboard_day
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import role_at_least
from apps.salons.permissions_policy import P_STAFF_MANAGE, has_permission
from apps.staff.models import StaffProfile, StaffWorkHours


def _finance_range(day, range_key: str):
    day_start, day_end = day_bounds(day)
    if range_key == "week":
        pay_start = day_start - timedelta(days=6)
        return pay_start, day_end
    if range_key == "month":
        pay_start, _ = day_bounds(jalali_month_bounds(day)[0])
        return pay_start, day_end
    return day_start, day_end


@salon_required
def home(request):
    membership = request.membership
    if not membership:
        return redirect("salons_onboarding:create")

    if not can_see_overview(membership):
        if membership.role == SalonMembership.Role.SPECIALIST:
            return redirect("dashboard:specialist_workspace")
        if can_see_calendar(membership):
            url = reverse("appointments:calendar")
            profile = getattr(membership, "staff_profile", None)
            if profile:
                return redirect(f"{url}?staff={profile.pk}")
            return redirect(url)
        raise PermissionDenied

    day = parse_dashboard_day(request)
    # Bound the overview to dates that can safely be converted to Jalali
    # and expanded into adjacent days and a 30-day reporting window.
    if not date(1900, 1, 1) <= day <= date(2200, 12, 31):
        day = timezone.localdate()
    range_key = request.GET.get("range", "day")
    if range_key not in {"day", "week", "month"}:
        range_key = "day"
    trend_days = 30 if request.GET.get("trend") == "30" else 7
    pay_start, pay_end = _finance_range(day, range_key)
    ctx = get_overview_context(request.salon, membership, day, pay_start, pay_end)
    ctx["analytics"] = overview_analytics(request.salon, membership, day, trend_days)
    ctx.update(
        {
            "today_jalali": today_jalali_label(),
            "day_jalali": to_jalali(day),
            "salon": request.salon,
            "membership": membership,
            "range_key": range_key,
            "finance_period_label": {"day": "روز انتخاب‌شده", "week": "۷ روز منتهی به تاریخ انتخابی", "month": "از ابتدای ماه شمسی تا تاریخ انتخابی"}[range_key],
            "trend_days": trend_days,
            "today_iso": timezone.localdate().isoformat(),
            "prev_day": (day - timedelta(days=1)).isoformat(),
            "next_day": (day + timedelta(days=1)).isoformat(),
            "show_finance": ctx["finance"] is not None,
        }
    )
    return render(request, "dashboard/overview.html", ctx)


@salon_required
def management(request):
    membership = request.membership
    if not can_see_management(membership):
        raise PermissionDenied
    from apps.salons.permissions_policy import (
        P_COMMISSION_MANAGE,
        P_CUSTOMER_VIEW,
        P_EXPENSE_MANAGE,
        P_FINANCE_REPORTS,
        P_INVENTORY_MANAGE,
        P_LOYALTY_MANAGE,
        P_MEMBERS_MANAGE,
        P_SALON_SETTINGS,
        P_STAFF_MANAGE,
    )

    links = []
    if has_permission(membership, P_STAFF_MANAGE):
        links.append({"title": "کارکنان و متخصص‌ها", "url": reverse("staff:list"), "icon": "user-round"})
    if has_permission(membership, P_CUSTOMER_VIEW):
        links.append({"title": "مشتریان", "url": reverse("customers:list"), "icon": "users"})
    can_manage_catalog = role_at_least(membership, SalonMembership.Role.MANAGER)
    if can_manage_catalog:
        links.append({"title": "خدمات", "url": reverse("services:list"), "icon": "scissors"})
    if has_permission(membership, P_FINANCE_REPORTS):
        links.append({"title": "درآمد و پرداخت‌ها", "url": reverse("finance:overview"), "icon": "wallet"})
    if has_permission(membership, P_EXPENSE_MANAGE):
        links.append({"title": "هزینه‌ها", "url": reverse("expenses:overview"), "icon": "receipt"})
    if has_permission(membership, P_COMMISSION_MANAGE):
        links.append({"title": "پورسانت", "url": reverse("commissions:overview"), "icon": "percent"})
    if has_permission(membership, P_INVENTORY_MANAGE):
        links.append({"title": "محصولات و موجودی", "url": reverse("inventory:list"), "icon": "boxes"})
    if has_permission(membership, P_LOYALTY_MANAGE):
        links.append({"title": "باشگاه مشتریان", "url": reverse("loyalty:overview"), "icon": "gem"})
    if has_permission(membership, P_MEMBERS_MANAGE):
        links.append({"title": "اعضا و دعوت", "url": reverse("salons_members:home"), "icon": "user-plus"})
    if has_permission(membership, P_SALON_SETTINGS):
        links.append({"title": "اطلاعات سالن", "url": reverse("salons_settings:home"), "icon": "building-2"})
    if can_manage_catalog:
        links.append({"title": "نمونه‌کارها", "url": reverse("portfolio:list"), "icon": "images"})
    descriptions = {
        "user-round": "پروفایل، ساعات کاری و دسترسی تیم",
        "users": "پرونده، سوابق و ارتباط با مشتریان",
        "scissors": "تعرفه، مدت و دسته‌بندی خدمات",
        "wallet": "دریافتی، بدهی و تسویه متخصصان",
        "receipt": "ثبت و مرور هزینه‌های سالن",
        "percent": "قوانین و محاسبه سهم متخصصان",
        "boxes": "موجودی، دسته‌بندی و گردش کالا",
        "gem": "امتیازها و سطح وفاداری مشتریان",
        "user-plus": "عضویت و دعوت همکاران",
        "building-2": "هویت سالن و تنظیمات صفحه عمومی",
        "images": "مدیریت گالری و تصاویر خدمات",
    }
    for link in links:
        link["description"] = descriptions.get(link["icon"], "")
    return render(
        request,
        "dashboard/management.html",
        {"links": links, "membership": membership},
    )


@salon_required
def specialists(request):
    membership = request.membership
    if membership and membership.role == SalonMembership.Role.SPECIALIST:
        return redirect("dashboard:specialist_workspace")
    if not can_see_specialists(membership):
        raise PermissionDenied

    from datetime import date

    from apps.appointments.booking import appointment_booking_context
    from apps.core.utils.dates import week_start_saturday
    from apps.dashboard.specialist_list import build_specialist_rows
    from apps.salons.permissions_policy import P_APPOINTMENT_CREATE, has_permission

    week_start = week_start_saturday(date.today())
    profiles = list(
        StaffProfile.scoped(request.salon)
        .filter(is_deleted=False, is_active=True)
        .select_related("membership__user")
        .prefetch_related("services", "work_hours", "time_off")
        .order_by("display_name")
    )
    staff_rows = build_specialist_rows(profiles, week_start=week_start)
    can_book_appointment = has_permission(membership, P_APPOINTMENT_CREATE)

    ctx = {
        "staff_rows": staff_rows,
        "staff_count": len(staff_rows),
        "can_manage_staff": has_permission(membership, P_STAFF_MANAGE),
        "can_book_appointment": can_book_appointment,
        "book_modal_open": False,
    }
    if can_book_appointment and request.GET.get("book") == "1":
        ctx.update(appointment_booking_context(request, book_modal_open=True))
    return render(request, "dashboard/specialists.html", ctx)


@salon_required
def specialist_workspace(request):
    """Private specialist workspace: never accept a staff id from the client."""
    from django.db.models import Sum
    from apps.appointments.models import Appointment
    from apps.commissions.models import CommissionEntry
    from apps.dashboard.role_services import day_bounds
    from apps.staff.models import StaffWorkHours
    from apps.core.utils.dates import jalali_month_bounds

    membership = request.membership
    if not membership or membership.role != SalonMembership.Role.SPECIALIST or not membership.is_active:
        raise PermissionDenied
    profile = StaffProfile.scoped(request.salon).filter(
        membership=membership, is_active=True, is_deleted=False
    ).first()
    if profile is None:
        raise PermissionDenied

    today = timezone.localdate()
    start, end = day_bounds(today)
    now = timezone.now()
    own_appts = Appointment.scoped(request.salon).filter(staff=profile)
    active = own_appts.exclude(status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW])
    today_appts = active.filter(start_at__gte=start, start_at__lt=end).select_related(
        "customer", "service"
    ).order_by("start_at")
    upcoming = active.filter(start_at__gte=now).order_by("start_at")
    month_start, month_end = jalali_month_bounds(today)
    month_start_dt, _ = day_bounds(month_start)
    _, month_end_dt = day_bounds(month_end)
    month_appts = active.filter(start_at__gte=month_start_dt, start_at__lt=month_end_dt)
    completed_month = month_appts.filter(status=Appointment.Status.COMPLETED)
    weekday = (today.weekday() + 2) % 7
    hours = StaffWorkHours.scoped(request.salon).filter(staff=profile, weekday=weekday).first()

    entries = CommissionEntry.scoped(request.salon).filter(
        staff=profile, created_at__gte=month_start_dt, created_at__lt=month_end_dt
    ).exclude(status=CommissionEntry.Status.VOID)
    amounts = entries.aggregate(
        earned=Sum("commission_amount_toman"), settled=Sum("settled_amount_toman")
    )
    earned = int(amounts["earned"] or 0)
    settled = int(amounts["settled"] or 0)
    finance_visible = bool(getattr(request.salon.settings, "specialist_can_view_commission", False))
    return render(request, "dashboard/specialist_workspace.html", {
        "profile": profile,
        "today_jalali": to_jalali(today),
        "today_appointments": today_appts,
        "today_count": today_appts.count(),
        "upcoming_count": upcoming.count(),
        "upcoming_appointments": upcoming[:6],
        "month_count": month_appts.count(),
        "month_completed": completed_month.count(),
        "month_customers": month_appts.values("customer_id").distinct().count(),
        "hours": hours,
        "finance_visible": finance_visible,
        "earned": earned if finance_visible else None,
        "settled": settled if finance_visible else None,
        "outstanding": max(earned - settled, 0) if finance_visible else None,
    })
