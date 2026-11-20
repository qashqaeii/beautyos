from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.utils.dates import jalali_month_bounds
from apps.dashboard.role_services import day_bounds
from apps.expenses.forms import ExpenseForm
from apps.expenses.models import Expense
from apps.finance.models import Payment
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions_policy import P_EXPENSE_MANAGE, require_permission


@salon_required
@require_permission(P_EXPENSE_MANAGE)
def overview(request):
    month_start, month_end = jalali_month_bounds()
    start, _ = day_bounds(month_start)
    _, end = day_bounds(month_end)
    expenses = Expense.scoped(request.salon).filter(expense_date__range=(month_start, month_end)).order_by("-expense_date", "-pk")
    expense_total = expenses.aggregate(t=Sum("amount_toman"))["t"] or 0
    revenue_total = (
        Payment.scoped(request.salon)
        .filter(created_at__gte=start, created_at__lt=end, paid_amount_toman__gt=0)
        .exclude(status=Payment.Status.REFUNDED)
        .aggregate(t=Sum("paid_amount_toman"))["t"]
        or 0
    )
    return render(
        request,
        "expenses/overview.html",
        {
            "expenses": expenses[:30],
            "expense_total": expense_total,
            "revenue_total": revenue_total,
            "operating_estimate": revenue_total - expense_total,
        },
    )


@salon_required
@require_permission(P_EXPENSE_MANAGE)
def create(request):
    form = ExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.salon = request.salon
        with transaction.atomic():
            expense.save()
            AuditLog.objects.create(salon=request.salon, actor=request.user, action=AuditLog.Action.CREATE,
                entity_type="expense", entity_id=str(expense.pk), message="ثبت هزینه سالن",
                metadata={"amount_toman": expense.amount_toman, "category": expense.category})
        messages.success(request, "هزینه ثبت شد.")
        return redirect("expenses:overview")
    return render(request, "expenses/form.html", {"form": form})
