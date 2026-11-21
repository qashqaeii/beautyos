from datetime import date, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.utils.dates import to_jalali, week_start_saturday, jalali_month_bounds

from apps.appointments.models import Appointment
from apps.salons import invitations
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.appointments.booking import (
    appointment_booking_context,
    appointment_booking_form,
    parse_appointment_initial_from_request,
)
from apps.salons.permissions_policy import P_APPOINTMENT_CREATE, P_STAFF_MANAGE, has_permission, require_permission
from apps.staff.forms import StaffInviteForm, StaffProfileForm, StaffTimeOffForm, WorkHoursForm
from apps.staff.models import StaffProfile, StaffTimeOff, StaffWorkHours


def _resolve_staff_view_mode(request) -> str:
    view_mode = request.GET.get("view", request.session.get("staff_view", "card"))
    if view_mode in ("card", "table"):
        request.session["staff_view"] = view_mode
    else:
        view_mode = "card"
    return view_mode


def _staff_list_context(
    request,
    *,
    form=None,
    create_modal_open: bool = False,
    view_mode: str | None = None,
):
    membership = getattr(request, "membership", None)
    if view_mode is None:
        view_mode = _resolve_staff_view_mode(request)
    from apps.services.models import Service
    from django.db.models import Prefetch

    salon = request.salon
    staff = list(StaffProfile.scoped(salon).filter(is_deleted=False)
        .select_related("membership__user")
        .prefetch_related(Prefetch("services", queryset=Service.scoped(salon).filter(is_deleted=False).order_by("name", "pk"), to_attr="directory_services"))
        .order_by("display_name", "pk"))
    today = timezone.localdate()
    month_start, month_end = jalali_month_bounds(today)
    daily = Q(start_at__date=today) & ~Q(status__in=(Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW))
    monthly = Q(start_at__date__range=(month_start, month_end), status=Appointment.Status.COMPLETED)
    stats = {row["staff_id"]: row for row in Appointment.scoped(salon).filter(staff_id__in=[s.pk for s in staff])
        .filter(daily | monthly).order_by().values("staff_id").annotate(today_count=Count("pk", filter=daily), month_count=Count("pk", filter=monthly))}
    active_services = set()
    for s in staff:
        s.today_count = stats.get(s.pk, {}).get("today_count", 0)
        s.month_count = stats.get(s.pk, {}).get("month_count", 0)
        s.directory_bookable = s.is_active and s.membership.is_active and s.is_bookable
        s.directory_active = s.is_active and s.membership.is_active
        s.service_count = len(s.directory_services)
        s.service_tags = s.directory_services[:3]
        s.extra_service_count = max(0, s.service_count - 3)
        if s.directory_active:
            active_services.update(service.pk for service in s.directory_services if service.is_active)
    total = len(staff)
    directory_stats = {
        "total": total,
        "active": sum(s.directory_active for s in staff),
        "bookable": sum(s.directory_bookable for s in staff),
        "today": sum(s.today_count for s in staff),
        "services": len(active_services),
    }
    q = (request.GET.get("q") or "").strip()[:120]
    status = request.GET.get("status", "")
    if status not in ("bookable", "unbookable", "inactive"):
        status = ""
    specialty = (request.GET.get("specialty") or "")[:80]
    specialties = sorted({s.title for s in staff if s.title})
    if specialty not in specialties:
        specialty = ""
    filtered = [s for s in staff if
        (not q or q.casefold() in (s.full_display_name + " " + s.title + " " + " ".join(service.name for service in s.directory_services)).casefold())
        and (not specialty or s.title == specialty)
        and (not status or (status == "bookable" and s.directory_bookable)
            or (status == "unbookable" and s.directory_active and not s.directory_bookable)
            or (status == "inactive" and not s.directory_active))]
    # Keep the default desktop table inside the first viewport; remaining rows use pagination.
    page = Paginator(filtered, 6).get_page(request.GET.get("page"))
    if form is None:
        form = StaffInviteForm()
    return {
        "staff_list": page.object_list,
        "staff_page": page, "directory_stats": directory_stats, "q": q,
        "status": status, "specialty": specialty, "specialties": specialties,
        "view_mode": view_mode,
        "can_add_staff": has_permission(membership, P_STAFF_MANAGE),
        "form": form,
        "create_modal_open": create_modal_open,
    }


@salon_required
def staff_list(request):
    membership = getattr(request, "membership", None)
    if not has_permission(membership, P_STAFF_MANAGE):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    create_modal_open = request.GET.get("create") == "1"
    ctx = _staff_list_context(request, create_modal_open=create_modal_open)
    return render(request, "staff/list.html", ctx)


@salon_required
@require_permission(P_STAFF_MANAGE)
def staff_create(request):
    if request.method == "GET":
        params = request.GET.copy()
        params.pop("create", None)
        params["create"] = "1"
        return redirect(f"{reverse('staff:list')}?{params.urlencode()}")

    form = StaffInviteForm(request.POST)
    if form.is_valid():
        try:
            invitations.create_invitation(
                salon=request.salon,
                inviter=request.user,
                phone=form.cleaned_data["phone"],
                role=SalonMembership.Role.SPECIALIST,
                invitee_first_name=form.cleaned_data["first_name"],
                invitee_last_name=form.cleaned_data["last_name"],
                invitee_specialty=form.cleaned_data["specialty"],
            )
            full_name = f"{form.cleaned_data['first_name']} {form.cleaned_data['last_name']}"
            messages.success(request, f"دعوت برای {full_name} ارسال شد.")
            return redirect("staff:list")
        except ValueError as exc:
            messages.error(request, str(exc))

    ctx = _staff_list_context(request, form=form, create_modal_open=True)
    return render(request, "staff/list.html", ctx)


def _staff_detail_context(
    request,
    profile,
    *,
    edit_form=None,
    edit_modal_open: bool = False,
    time_off_form=None,
    timeoff_modal_open: bool = False,
    booking_form=None,
    book_modal_open: bool = False,
):
    hours = profile.work_hours.order_by("weekday")
    week_start = week_start_saturday(timezone.localdate())
    hours_week = _staff_week_schedule(hours, week_start)
    time_off = profile.time_off.filter(end_date__gte=timezone.localdate()).order_by("start_date")
    upcoming = (
        Appointment.scoped(request.salon)
        .filter(
            staff=profile, start_at__gte=timezone.now(),
            status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED, Appointment.Status.CHECKED_IN],
        )
        .select_related("customer", "service")
        .order_by("start_at")[:10]
    )
    if edit_form is None:
        edit_form = StaffProfileForm(instance=profile, salon=request.salon)
    if time_off_form is None:
        time_off_form = StaffTimeOffForm()
    membership = getattr(request, "membership", None)
    can_book = has_permission(membership, P_APPOINTMENT_CREATE)
    ctx = {
        "profile": profile,
        "hours": hours,
        "hours_week": hours_week,
        "time_off": time_off,
        "upcoming": upcoming,
        "form": edit_form,
        "edit_modal_open": edit_modal_open,
        "time_off_form": time_off_form,
        "timeoff_modal_open": timeoff_modal_open,
        "can_book_appointment": can_book and profile.is_active and profile.is_bookable,
        "booking_unavailable": can_book and not (profile.is_active and profile.is_bookable),
        "book_modal_open": False,
        "staff_detail_url": reverse("staff:detail", kwargs={"pk": profile.pk}),
    }
    # Always render the dialog for eligible specialists, including ordinary GET
    # and failed profile/time-off edits. The profile, never ?staff=, owns the lock.
    if ctx["can_book_appointment"] or (can_book and booking_form is not None):
        if booking_form is None:
            initial = parse_appointment_initial_from_request(request)
            initial["staff"] = profile.pk
            booking_form = appointment_booking_form(request, initial=initial, locked_staff=profile)
        extra = appointment_booking_context(request, form=booking_form, book_modal_open=book_modal_open)
        extra.pop("form", None)  # Keep the separate StaffProfileForm for editing.
        extra["booking_return_path"] = ctx["staff_detail_url"]
        extra["can_book_appointment"] = True
        ctx.update(extra)
    return ctx


@salon_required
@require_permission(P_STAFF_MANAGE)
def staff_detail(request, pk):
    profile = get_object_or_404(
        StaffProfile.scoped(request.salon),
        pk=pk,
        is_deleted=False,
    )
    book_modal_open = request.GET.get("book") == "1"
    edit_modal_open = not book_modal_open and request.GET.get("edit") == "1"
    timeoff_modal_open = not book_modal_open and not edit_modal_open and request.GET.get("timeoff") == "1"
    ctx = _staff_detail_context(
        request, profile,
        edit_modal_open=edit_modal_open,
        timeoff_modal_open=timeoff_modal_open,
        book_modal_open=book_modal_open,
    )
    return render(request, "staff/detail.html", ctx)


@salon_required
@require_permission(P_STAFF_MANAGE)
def staff_edit(request, pk):
    profile = get_object_or_404(StaffProfile.scoped(request.salon), pk=pk, is_deleted=False)
    if request.method == "GET":
        return redirect(f"{reverse('staff:detail', kwargs={'pk': pk})}?edit=1")

    form = StaffProfileForm(request.POST, request.FILES, instance=profile, salon=request.salon)
    if form.is_valid():
        form.save()
        messages.success(request, "اطلاعات ذخیره شد.")
        return redirect("staff:detail", pk=pk)

    ctx = _staff_detail_context(request, profile, edit_form=form, edit_modal_open=True)
    return render(request, "staff/detail.html", ctx)


def _resolve_week_anchor(request) -> date:
    raw = request.GET.get("week")
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return timezone.localdate()


def _staff_week_schedule(hours_qs, week_start: date):
    by_day = {h.weekday: h for h in hours_qs}
    rows = []
    for choice in StaffWorkHours.Weekday:
        day_date = week_start + timedelta(days=choice.value)
        rows.append(
            {
                "weekday": choice.value,
                "label": choice.label,
                "record": by_day.get(choice.value),
                "gregorian": day_date,
                "jalali": to_jalali(day_date),
            }
        )
    return rows


@salon_required
@require_permission(P_STAFF_MANAGE)
def staff_hours(request, pk):
    profile = get_object_or_404(StaffProfile.scoped(request.salon), pk=pk, is_deleted=False)
    week_anchor = _resolve_week_anchor(request)
    week_start = week_start_saturday(week_anchor)
    week_end = week_start + timedelta(days=6)
    hours = list(profile.work_hours.order_by("weekday"))
    schedule = _staff_week_schedule(hours, week_start)
    try:
        selected = int(request.POST.get("weekday") if request.method == "POST" else request.GET.get("day", (week_anchor-week_start).days))
    except (TypeError, ValueError):
        selected = (week_anchor-week_start).days
    if not 0 <= selected <= 6:
        selected = (week_anchor-week_start).days
    selected_row = schedule[selected]
    if request.method == "POST":
        form = WorkHoursForm(request.POST, week_anchor=week_anchor)
        if form.is_valid():
            data = form.cleaned_data
            StaffWorkHours.objects.update_or_create(
                staff=profile,
                weekday=data["weekday"],
                defaults={
                    "salon": request.salon,
                    "start_time": data["start_time"],
                    "end_time": data["end_time"],
                    "is_closed": data["is_closed"],
                },
            )
            messages.success(request, "برنامهٔ هفتگی ذخیره شد.")
            url = reverse("staff:hours", kwargs={"pk": pk})
            return redirect(f"{url}?week={week_start.isoformat()}&day={data['weekday']}")
    else:
        record = selected_row["record"]
        initial = {"weekday": selected, "reference_date": selected_row["gregorian"]}
        if record:
            initial.update(start_time=record.start_time if not record.is_closed else None,
                           end_time=record.end_time if not record.is_closed else None,
                           is_closed=record.is_closed)
        form = WorkHoursForm(week_anchor=selected_row["gregorian"], initial=initial)
    return render(
        request,
        "staff/hours.html",
        {
            "form": form,
            "profile": profile,
            "hours": hours,
            "week_schedule": schedule,
            "selected_day": selected,
            "selected_row": selected_row,
            "work_days": sum(not h.is_closed for h in hours),
            "closed_days": sum(h.is_closed for h in hours),
            "unconfigured_days": 7 - len(hours),
            "week_start": week_start,
            "week_end": week_end,
            "previous_week": week_start - timedelta(days=7),
            "next_week": week_start + timedelta(days=7),
            "week_anchor": week_anchor,
            "week_anchor_jalali": to_jalali(week_anchor),
            "week_range_jalali": f"{to_jalali(week_start)} – {to_jalali(week_end)}",
        },
    )


@salon_required
@require_permission(P_STAFF_MANAGE)
def staff_time_off(request, pk):
    profile = get_object_or_404(StaffProfile.scoped(request.salon), pk=pk, is_deleted=False)
    if request.method == "GET":
        return redirect(f"{reverse('staff:detail', kwargs={'pk': pk})}?timeoff=1")

    form = StaffTimeOffForm(request.POST)
    if form.is_valid():
        off = form.save(commit=False)
        off.salon = request.salon
        off.staff = profile
        off.save()
        messages.success(request, "مرخصی ثبت شد.")
        return redirect("staff:detail", pk=pk)

    ctx = _staff_detail_context(request, profile, time_off_form=form, timeoff_modal_open=True)
    return render(request, "staff/detail.html", ctx)
