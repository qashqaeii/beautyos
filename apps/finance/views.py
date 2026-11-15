from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from apps.commissions.services import create_settlement
from apps.finance.forms import PaymentForm, SalonDebtForm, SalonDebtPaymentForm
from apps.finance.models import Payment, SalonDebt
from apps.finance.services import (
    commission_day_overview,
    customer_payments_in_range,
    income_metrics,
    open_debts_summary,
    parse_finance_range,
    record_salon_debt_payment,
)
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role
from apps.salons.permissions_policy import (
    P_COMMISSION_MANAGE,
    P_FINANCE_REPORTS,
    P_PAYMENT_CREATE,
    has_permission,
)
from apps.staff.models import StaffProfile


def _finance_redirect(**params):
    base = reverse("finance:overview")
    if not params:
        return base
    return f"{base}?{urlencode(params)}"


def _finance_return_url(get_query: QueryDict) -> str:
    q = get_query.copy()
    q.pop("payment", None)
    base = reverse("finance:overview")
    qs = q.urlencode()
    return f"{base}?{qs}" if qs else base


def _append_payment_query(url: str) -> str:
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q["payment"] = "1"
    path = parts.path or reverse("finance:overview")
    qs = urlencode(q)
    return f"{path}?{qs}" if qs else path


def _is_finance_overview_path(path: str) -> bool:
    return path.rstrip("/") == reverse("finance:overview").rstrip("/")


def _finance_get_from_post(post) -> QueryDict:
    qd = QueryDict(mutable=True)
    qd["tab"] = post.get("finance_tab", "income")
    qd["range"] = post.get("finance_range", "today")
    day = post.get("finance_day")
    if day:
        qd["day"] = day
    return qd


class _FinanceGetRequest:
    def __init__(self, request, get_query: QueryDict):
        self.__dict__.update(request.__dict__)
        self.GET = get_query


def _finance_overview_context(
    request,
    *,
    get_query=None,
    payment_form=None,
    payment_modal_open: bool = False,
):
    get_query = get_query or request.GET
    range_req = _FinanceGetRequest(request, get_query)
    range_ctx = parse_finance_range(range_req)
    tab = get_query.get("tab", "income")
    if tab not in ("income", "debts", "commissions"):
        tab = "income"

    membership = getattr(request, "membership", None)
    can_manage_debt = has_permission(membership, P_FINANCE_REPORTS)
    can_settle_commission = has_permission(membership, P_COMMISSION_MANAGE)
    can_payment_create = has_permission(membership, P_PAYMENT_CREATE)

    if payment_modal_open and can_payment_create and payment_form is None:
        payment_form = PaymentForm(salon=request.salon)

    debt_form = SalonDebtForm()
    income = income_metrics(request.salon, range_ctx["start_dt"], range_ctx["end_dt"])
    payments = customer_payments_in_range(request.salon, range_ctx["start_dt"], range_ctx["end_dt"])
    debts = open_debts_summary(request.salon)
    commissions = commission_day_overview(request.salon, range_ctx["selected_day"])

    return {
        **range_ctx,
        "tab": tab,
        "income": income,
        "payments": payments,
        "debt_form": debt_form,
        **debts,
        "commissions": commissions,
        "can_manage_debt": can_manage_debt,
        "can_settle_commission": can_settle_commission,
        "can_payment_create": can_payment_create,
        "payment_form": payment_form,
        "payment_modal_open": payment_modal_open and can_payment_create and payment_form is not None,
        "payment_return_url": _finance_return_url(get_query),
    }


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def finance_overview(request):
    range_ctx = parse_finance_range(request)
    tab = request.GET.get("tab", "income")
    if tab not in ("income", "debts", "commissions"):
        tab = "income"

    if request.method == "POST":
        action = request.POST.get("action")
        redirect_params = {
            "tab": tab,
            "range": range_ctx["range_key"],
            "day": range_ctx["selected_day"].isoformat(),
        }
        membership = getattr(request, "membership", None)
        can_manage_debt = has_permission(membership, P_FINANCE_REPORTS)
        can_settle_commission = has_permission(membership, P_COMMISSION_MANAGE)
        if action == "add_debt":
            if not can_manage_debt:
                raise PermissionDenied
            debt_form = SalonDebtForm(request.POST)
            if debt_form.is_valid():
                debt = debt_form.save(commit=False)
                debt.salon = request.salon
                debt.save()
                messages.success(request, "بدهی ثبت شد.")
                redirect_params["tab"] = "debts"
                return redirect(_finance_redirect(**redirect_params))
        elif action == "pay_debt":
            if not can_manage_debt:
                raise PermissionDenied
            debt = get_object_or_404(SalonDebt, pk=request.POST.get("debt_id"), salon=request.salon, is_closed=False)
            pay_form = SalonDebtPaymentForm(request.POST)
            if pay_form.is_valid():
                try:
                    record_salon_debt_payment(
                        salon=request.salon,
                        debt_id=debt.pk,
                        amount_toman=pay_form.cleaned_data["amount_toman"],
                        note=pay_form.cleaned_data.get("note", ""),
                    )
                except ValidationError as exc:
                    msg = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
                    messages.error(request, msg)
                else:
                    messages.success(request, "پرداخت بدهی ثبت شد.")
                    redirect_params["tab"] = "debts"
                    return redirect(_finance_redirect(**redirect_params))
        elif action == "settle_staff":
            if not can_settle_commission:
                raise PermissionDenied
            staff = get_object_or_404(StaffProfile, pk=request.POST.get("staff_id"), salon=request.salon)
            amount = int(request.POST.get("amount_toman") or 0)
            if amount > 0:
                try:
                    create_settlement(request.salon, staff, amount, request.POST.get("note", ""))
                except ValidationError as exc:
                    msg = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
                    messages.error(request, msg)
                else:
                    messages.success(request, "تسویه متخصص ثبت شد.")
            redirect_params["tab"] = "commissions"
            return redirect(_finance_redirect(**redirect_params))

    payment_modal_open = request.GET.get("payment") == "1"
    ctx = _finance_overview_context(request, payment_modal_open=payment_modal_open)
    return render(request, "finance/overview.html", ctx)


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def payment_create(request):
    next_url = request.POST.get("next") if request.method == "POST" else request.GET.get("next")
    next_url = next_url or reverse("finance:overview")

    if request.method == "GET":
        parts = urlparse(next_url)
        if _is_finance_overview_path(parts.path):
            return redirect(_append_payment_query(next_url))
        return render(
            request,
            "finance/payment_modal_page.html",
            {
                "payment_form": PaymentForm(salon=request.salon),
                "payment_modal_open": True,
                "payment_return_url": next_url,
            },
        )

    form = PaymentForm(request.POST, salon=request.salon)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.salon = request.salon
        payment.save()
        from apps.customers.services import refresh_customer_stats

        refresh_customer_stats(payment.customer)
        messages.success(request, "پرداخت ثبت شد.")
        return redirect(next_url)

    parts = urlparse(next_url)
    if _is_finance_overview_path(parts.path):
        get_q = _finance_get_from_post(request.POST)
        if not request.POST.get("finance_tab"):
            q = dict(parse_qsl(parts.query, keep_blank_values=True))
            get_q = QueryDict(mutable=True)
            get_q["tab"] = q.get("tab", "income")
            get_q["range"] = q.get("range", "today")
            if q.get("day"):
                get_q["day"] = q["day"]
        ctx = _finance_overview_context(
            request,
            get_query=get_q,
            payment_form=form,
            payment_modal_open=True,
        )
        return render(request, "finance/overview.html", ctx)

    return render(
        request,
        "finance/payment_modal_page.html",
        {
            "payment_form": form,
            "payment_modal_open": True,
            "payment_return_url": next_url,
        },
    )
