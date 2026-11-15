from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.expenses.forms import ExpenseForm
from apps.expenses.models import Expense
from apps.finance.models import Payment
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions_policy import P_EXPENSE_MANAGE, require_permission


@salon_required
@require_permission(P_EXPENSE_MANAGE)
def overview(request):
    month_start = timezone.localdate().replace(day=1)
    expenses = Expense.scoped(request.salon).filter(expense_date__gte=month_start).order_by("-expense_date")
    expense_total = expenses.aggregate(t=Sum("amount_toman"))["t"] or 0
    revenue_total = (
        Payment.scoped(request.salon)
        .filter(created_at__date__gte=month_start, status=Payment.Status.PAID)
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
        expense.save()
        messages.success(request, "هزینه ثبت شد.")
        return redirect("expenses:overview")
    return render(request, "expenses/form.html", {"form": form})
