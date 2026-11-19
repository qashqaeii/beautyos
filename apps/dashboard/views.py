from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.core.utils.dates import today_jalali_label, to_jalali
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
from apps.salons.permissions_policy import P_STAFF_MANAGE, has_permission
from apps.staff.models import StaffProfile, StaffWorkHours


def _finance_range(day, range_key: str):
    day_start, day_end = day_bounds(day)
    if range_key == "week":
        pay_start = day_start - timedelta(days=6)
        return pay_start, day_end
    if range_key == "month":
        pay_start = day_start.replace(day=1)
        return pay_start, day_end
    return day_start, day_end


@salon_required
def home(request):
    membership = request.membership
    if not membership:
        return redirect("salons_onboarding:create")

    if not can_see_overview(membership):
        if can_see_calendar(membership):
            url = reverse("appointments:calendar")
            profile = getattr(membership, "staff_profile", None)
            if profile:
                return redirect(f"{url}?staff={profile.pk}")
            return redirect(url)
        raise PermissionDenied

    day = parse_dashboard_day(request)
    range_key = request.GET.get("range", "day")
    pay_start, pay_end = _finance_range(day, range_key)
    ctx = get_overview_context(request.salon, membership, day, pay_start, pay_end)
    ctx.update(
        {
            "today_jalali": today_jalali_label(),
            "day_jalali": to_jalali(day),
            "salon": request.salon,
            "membership": membership,
            "range_key": range_key,
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
