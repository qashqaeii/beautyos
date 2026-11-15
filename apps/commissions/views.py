from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.commissions.forms import CommissionRuleForm, SettlementForm
from apps.commissions.models import CommissionEntry, CommissionRule
from apps.commissions.services import create_settlement, staff_outstanding_commission
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role
from apps.salons.permissions_policy import P_COMMISSION_MANAGE, require_permission
from apps.staff.models import StaffProfile


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def overview(request):
    entries = (
        CommissionEntry.scoped(request.salon)
        .select_related("staff", "appointment__customer")
        .order_by("-created_at")[:50]
    )
    by_staff = (
        CommissionEntry.scoped(request.salon)
        .filter(status=CommissionEntry.Status.RECOGNIZED)
        .values("staff_id", "staff__display_name")
        .annotate(total=Sum("commission_amount_toman"))
    )
    return render(
        request,
        "commissions/overview.html",
        {"entries": entries, "by_staff": by_staff, "staff_list": StaffProfile.scoped(request.salon).filter(is_active=True)},
    )


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
