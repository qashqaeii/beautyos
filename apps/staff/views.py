from datetime import date, timedelta

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.utils.dates import to_jalali, week_start_saturday

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
    staff = (
        StaffProfile.scoped(request.salon)
        .filter(is_deleted=False)
        .select_related("membership__user")
        .prefetch_related("services")
    )
    if form is None:
        form = StaffInviteForm()
    return {
        "staff_list": staff,
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
):
    hours = profile.work_hours.order_by("weekday")
    week_start = week_start_saturday(timezone.localdate())
    hours_week = _staff_week_schedule(hours, week_start)
    time_off = profile.time_off.filter(end_date__gte=timezone.localdate()).order_by("start_date")
    upcoming = (
        Appointment.scoped(request.salon)
        .filter(staff=profile, start_at__gte=timezone.now())
        .select_related("customer", "service")
        .order_by("start_at")[:10]
    )
    if edit_form is None:
        edit_form = StaffProfileForm(instance=profile, salon=request.salon)
    if time_off_form is None:
        time_off_form = StaffTimeOffForm()
    membership = getattr(request, "membership", None)
    return {
        "profile": profile,
        "hours": hours,
        "hours_week": hours_week,
        "time_off": time_off,
        "upcoming": upcoming,
        "form": edit_form,
        "edit_modal_open": edit_modal_open,
        "time_off_form": time_off_form,
        "timeoff_modal_open": timeoff_modal_open,
        "can_book_appointment": has_permission(membership, P_APPOINTMENT_CREATE),
    }


@salon_required
@require_permission(P_STAFF_MANAGE)
def staff_detail(request, pk):
    profile = get_object_or_404(
        StaffProfile.scoped(request.salon),
        pk=pk,
        is_deleted=False,
    )
    edit_modal_open = request.GET.get("edit") == "1"
    timeoff_modal_open = request.GET.get("timeoff") == "1"
    book_modal_open = request.GET.get("book") == "1"
    ctx = _staff_detail_context(
        request,
        profile,
        edit_modal_open=edit_modal_open,
        timeoff_modal_open=timeoff_modal_open,
    )
    booking_form = getattr(request, "booking_form_override", None)
    if book_modal_open or booking_form is not None:
        if booking_form is None:
            initial = parse_appointment_initial_from_request(request)
            initial.setdefault("staff", profile.pk)
            booking_form = appointment_booking_form(request, initial=initial)
        ctx.update(
            appointment_booking_context(
                request,
                form=booking_form,
                book_modal_open=True,
            )
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
            return redirect(f"{url}?week={week_start.isoformat()}")
    else:
        form = WorkHoursForm(week_anchor=week_anchor)
    hours = profile.work_hours.order_by("weekday")
    return render(
        request,
        "staff/hours.html",
        {
            "form": form,
            "profile": profile,
            "hours": hours,
            "week_schedule": _staff_week_schedule(hours, week_start),
            "week_start": week_start,
            "week_end": week_end,
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
