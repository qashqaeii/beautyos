from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import reverse
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
    return _overview(request, open_modal=request.GET.get("expense") == "1")


def _overview(request, *, form=None, open_modal=False, status=200):
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
            "expense_form": form if form is not None else ExpenseForm(initial={"expense_date": timezone.localdate()}),
            "expense_modal_open": open_modal,
            "expense_return_url": reverse("expenses:overview"),
            "expenses": expenses[:30],
            "expense_total": expense_total,
            "revenue_total": revenue_total,
            "operating_estimate": revenue_total - expense_total,
        },
        status=status,
    )


@salon_required
@require_permission(P_EXPENSE_MANAGE)
def create(request):
    if request.method == "GET":
        return redirect(reverse("expenses:overview") + "?expense=1")
    form = ExpenseForm(request.POST)
    from django.utils.http import url_has_allowed_host_and_scheme
    from urllib.parse import urlsplit
    target = request.POST.get("next", "")
    if not target.startswith("/") or target.startswith("//") or not url_has_allowed_host_and_scheme(target, allowed_hosts=set()) or urlsplit(target).path != reverse("finance:overview"):
        target = reverse("expenses:overview")
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.salon = request.salon
        with transaction.atomic():
            expense.save()
            AuditLog.objects.create(salon=request.salon, actor=request.user, action=AuditLog.Action.CREATE,
                entity_type="expense", entity_id=str(expense.pk), message="ثبت هزینه سالن",
                metadata={"amount_toman": expense.amount_toman, "category": expense.category})
        messages.success(request, "هزینه ثبت شد.")
        return redirect(target)
    if target != reverse("expenses:overview"):
        from django.http import QueryDict
        from apps.finance.views import _finance_overview_context
        from django.core.exceptions import PermissionDenied
        try:
            ctx = _finance_overview_context(request, get_query=QueryDict(urlsplit(target).query))
        except PermissionDenied:
            pass
        else:
            ctx.update(expense_form=form, expense_modal_open=True, expense_return_url=target)
            return render(request, "finance/overview.html", ctx, status=400)
    return _overview(request, form=form, open_modal=True, status=400)
