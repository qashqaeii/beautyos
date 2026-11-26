from datetime import date
from django.core.paginator import Paginator
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.commissions.forms import CommissionRuleForm, SettlementForm
from apps.commissions.models import CommissionEntry, CommissionRule, CommissionSettlement
from apps.commissions.services import create_settlement, staff_outstanding_commission
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role
from apps.salons.permissions_policy import P_COMMISSION_MANAGE, require_permission
from apps.staff.models import StaffProfile


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def overview(request):
    from apps.core.utils.dates import jalali_month_bounds, to_jalali
    from django.utils import timezone
    staff_list = StaffProfile.scoped(request.salon).order_by("display_name")
    staff_id = request.GET.get("staff", "")
    selected = staff_list.filter(pk=staff_id).first() if staff_id.isascii() and staff_id.isdigit() and len(staff_id) < 19 else None
    base = CommissionEntry.scoped(request.salon)
    payments = CommissionSettlement.scoped(request.salon)
    if selected:
        base = base.filter(staff=selected)
        payments = payments.filter(staff=selected)
    # All-time payable balance is computed per specialist, as in settlement service.
    balances = list(base.filter(status=CommissionEntry.Status.RECOGNIZED)
        .values("staff_id", "staff__display_name")
        .annotate(total=Sum(F("commission_amount_toman") - F("settled_amount_toman")))
        .filter(total__gt=0).order_by("-total"))
    outstanding = sum(row["total"] for row in balances)
    paid = payments.aggregate(total=Sum("amount_toman"))["total"] or 0
    try:
        day = date.fromisoformat(request.GET.get("day", ""))
        if not 1800 <= day.year <= 2200:
            raise ValueError
    except ValueError:
        day = None
    entries = base.select_related("staff", "appointment__service").order_by("-created_at", "-pk")
    if day:
        first, last = jalali_month_bounds(day)
        entries = entries.filter(created_at__date__range=(first, last))
    status = request.GET.get("status", "")
    if status in CommissionEntry.Status.values:
        entries = entries.filter(status=status)
    else:
        status = ""
    page = Paginator(entries, 6).get_page(request.GET.get("page"))
    return render(request, "commissions/overview.html", {
        "entries": page, "by_staff": balances, "staff_list": staff_list,
        "selected_staff": selected, "selected_status": status,
        "statuses": CommissionEntry.Status.choices, "selected_day": day,
        "day_jalali": to_jalali(day) if day else "",
        "paid": paid, "outstanding": outstanding,
        "total": paid + outstanding,
    })


@salon_required
@require_permission(P_COMMISSION_MANAGE)
def rules_list(request):
    rules = CommissionRule.scoped(request.salon).select_related("staff", "service").order_by("-created_at")
    return render(request, "commissions/rules.html", {"rules": rules})


@salon_required
@require_permission(P_COMMISSION_MANAGE)
def rule_create(request):
    form = CommissionRuleForm(request.POST or None, salon=request.salon)
    if request.method == "POST" and form.is_valid():
        rule = form.save(commit=False)
        rule.salon = request.salon
        rule.save()
        messages.success(request, "قانون پورسانت ذخیره شد.")
        return redirect("commissions:rules")
    return render(request, "commissions/rule_form.html", {"form": form})


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def settle_staff(request, staff_id):
    staff = get_object_or_404(StaffProfile, pk=staff_id, salon=request.salon)
    outstanding = staff_outstanding_commission(salon=request.salon, staff=staff)
    form = SettlementForm(request.POST or None, initial={"amount_toman": outstanding})
    if request.method == "POST" and form.is_valid():
        try:
            create_settlement(
                request.salon,
                staff,
                form.cleaned_data["amount_toman"],
                form.cleaned_data.get("note", ""),
            )
        except ValidationError as exc:
            msg = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            form.add_error("amount_toman", msg)
        else:
            messages.success(request, "تسویه پورسانت ثبت شد.")
            return redirect("commissions:overview")
    return render(
        request,
        "commissions/settle.html",
        {"form": form, "staff": staff, "outstanding": outstanding},
    )
